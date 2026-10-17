#!/usr/bin/env python3
"""Install, update or remove VTD in Victoria 3's user-data mod directory."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
NAME = 'territorial_doctrine'
MARKER = '.vtd-install.json'


def windows_documents() -> Path | None:
    """Honor the Windows Documents known-folder redirection, including OneDrive."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r'Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders') as key:
            value, _ = winreg.QueryValueEx(key, 'Personal')
        return Path(os.path.expandvars(value))
    except (ImportError, OSError):
        return None


def find_mod_dir(explicit: Path | None = None, *, platform: str | None = None,
                 home: Path | None = None, environ: dict | None = None) -> Path:
    platform = platform or sys.platform
    home = home or Path.home()
    env = os.environ if environ is None else environ
    if explicit is not None:
        return explicit.expanduser().resolve()
    if env.get('VTD_MOD_DIR'):
        return Path(env['VTD_MOD_DIR']).expanduser().resolve()
    suffix = Path('Paradox Interactive') / 'Victoria 3' / 'mod'
    if platform == 'win32':
        documents = windows_documents()
        if documents:
            return (documents / suffix).resolve()
        candidates = [Path(env[name]) / 'Documents' / suffix
                      for name in ('OneDrive', 'OneDriveConsumer', 'OneDriveCommercial') if env.get(name)]
        candidates.append(home / 'Documents' / suffix)
        existing = list(dict.fromkeys(p.resolve() for p in candidates if p.parent.is_dir()))
        if len(existing) > 1:
            raise ValueError('Multiple Victoria 3 profiles found; select one with --mod-dir.')
        return existing[0] if existing else (home / 'Documents' / suffix).resolve()
    if platform == 'darwin':
        return (home / 'Documents' / suffix).resolve()
    if platform.startswith('linux'):
        base = Path(env.get('XDG_DATA_HOME') or home / '.local' / 'share').expanduser()
        return (base / suffix).resolve()
    raise ValueError('Unknown platform; specify the user-data mod directory with --mod-dir.')


def validate_destination(destination: Path) -> Path:
    destination = destination.expanduser().resolve()
    folder = destination / NAME
    checkout = ROOT.resolve()
    if (destination == checkout or checkout in destination.parents or
            folder == checkout or folder in checkout.parents):
        raise ValueError('The installation must be outside the source checkout.')
    if any(c in destination.as_posix() for c in ('"', '\n', '\r')):
        raise ValueError('The mod directory cannot contain quotes or line breaks.')
    if destination.exists() and not destination.is_dir():
        raise ValueError(f'Not a directory: {destination}')
    for target in (folder, destination / f'{NAME}.mod'):
        if target.is_symlink():
            raise ValueError(f'Refusing to replace a symbolic link: {target}')
    return destination


def inspect_installation(destination: Path) -> dict:
    """Recognize managed and old ZIP/package installations without following links."""
    folder, launcher = destination / NAME, destination / f'{NAME}.mod'
    result = {'present': folder.exists() or launcher.exists(), 'version': None,
              'managed': False, 'partial': not (folder.exists() and launcher.exists())}
    if not result['present']:
        return result
    if folder.exists():
        if not folder.is_dir():
            raise ValueError(f'Existing payload is not a directory: {folder}')
        metadata = folder / '.metadata' / 'metadata.json'
        if (folder / '.metadata').is_symlink() or metadata.is_symlink():
            raise ValueError('Installation metadata must not be a symbolic link.')
        try:
            data = json.loads(metadata.read_text(encoding='utf-8-sig'))
        except (OSError, ValueError) as exc:
            raise ValueError(f'Cannot identify existing folder as VTD; it was left untouched: {folder}') from exc
        if data.get('id') != NAME or data.get('game_id') != 'victoria3':
            raise ValueError(f'Existing folder belongs to another mod; left untouched: {folder}')
        result['version'] = data.get('version', 'unknown')
        result['managed'] = (folder / MARKER).is_file() and not (folder / MARKER).is_symlink()
    if launcher.exists():
        if not launcher.is_file():
            raise ValueError(f'Launcher descriptor is not a file: {launcher}')
        text = launcher.read_text(encoding='utf-8-sig')
        paths = re.findall(r'^\s*path\s*=\s*"([^"\r\n]+)"\s*$', text, re.M)
        names = re.findall(r'^\s*name\s*=\s*"([^"\r\n]+)"\s*$', text, re.M)
        if len(paths) != 1 or len(names) != 1 or (not folder.exists() and names != ['Territorial Doctrine']):
            raise ValueError(f'Cannot identify the launcher descriptor as VTD: {launcher}')
        path = Path(paths[0])
        if not path.is_absolute():
            path = destination.parent / path
        if path.resolve() != folder.resolve():
            raise ValueError(f'Launcher points to another folder; left untouched: {launcher}')
    return result


@contextmanager
def install_lock(destination: Path):
    path = destination / '.vtd-install.lock'
    try:
        handle = path.open('x', encoding='utf-8')
    except FileExistsError as exc:
        raise ValueError(f'Another VTD operation may be running: {path}. If it crashed, remove this lock after checking it has stopped.') from exc
    try:
        with handle:
            handle.write(str(os.getpid()))
        yield
    finally:
        path.unlink()


def validate_source(*, generate: bool = False) -> None:
    # Removal/status never import the gameplay model or validate the checkout.
    if (ROOT / 'mod').is_symlink() or (ROOT / 'LICENSE').is_symlink() or any(p.is_symlink() for p in (ROOT / 'mod').rglob('*')):
        raise ValueError('Source payload contains symbolic links; use regular files for installation.')
    if generate:
        print('Regenerating source assets...', flush=True)
        result = subprocess.run([sys.executable, str(ROOT / 'tools' / 'generate.py')], cwd=ROOT,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding='utf-8', errors='replace')
        print(result.stdout, end='', flush=True)
        result.check_returncode()
    from tools.package import check
    check()


def stage_payload(staging: Path, destination: Path) -> None:
    from tools.package import descriptor
    shutil.copytree(ROOT / 'mod', staging / 'next_payload')
    shutil.copy2(ROOT / 'LICENSE', staging / 'next_payload' / 'LICENSE')
    metadata = json.loads((staging / 'next_payload' / '.metadata' / 'metadata.json').read_text(encoding='utf-8-sig'))
    if metadata.get('id') != NAME or metadata.get('game_id') != 'victoria3':
        raise ValueError('Source metadata does not identify the VTD mod.')
    marker = {'tool': 'vtd-installer', 'schema': 1, 'version': metadata['version']}
    (staging / 'next_payload' / MARKER).write_text(json.dumps(marker, indent=2) + '\n', encoding='utf-8')
    (staging / 'next.mod').write_text(descriptor((destination / NAME).as_posix()), encoding='utf-8')


def backup_installation(destination: Path, operation: str) -> Path:
    base = destination.parent / 'vtd-backups'
    if base.is_symlink():
        raise ValueError(f'Backup directory must not be a symbolic link: {base}')
    base.mkdir(parents=True, exist_ok=True)
    label = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + operation + '-' + uuid.uuid4().hex[:8]
    with tempfile.TemporaryDirectory(prefix='.incomplete-', dir=base) as tmp:
        temporary = Path(tmp)
        if (destination / NAME).exists():
            shutil.copytree(destination / NAME, temporary / NAME, symlinks=True)
        if (destination / f'{NAME}.mod').exists():
            shutil.copy2(destination / f'{NAME}.mod', temporary / f'{NAME}.mod')
        (temporary / 'backup.json').write_text(json.dumps({'operation': operation, 'mod_dir': str(destination)}, indent=2) + '\n', encoding='utf-8')
        # Publish only a complete snapshot. Copies do not traverse nested links.
        backup = base / label
        temporary.rename(backup)
    return backup


def swap_installation(destination: Path, staging: Path, *, remove: bool, backup: Path | None) -> None:
    folder, launcher = destination / NAME, destination / f'{NAME}.mod'
    old_folder, old_launcher = staging / 'previous_payload', staging / 'previous.mod'
    new_folder = new_launcher = False
    try:
        if folder.exists():
            folder.rename(old_folder)
        if launcher.exists():
            launcher.rename(old_launcher)
        if not remove:
            (staging / 'next_payload').rename(folder)
            new_folder = True
            os.replace(staging / 'next.mod', launcher)
            new_launcher = True
    except BaseException as exc:
        try:
            if new_launcher or (not remove and not (staging / 'next.mod').exists() and launcher.exists()):
                launcher.unlink()
            if new_folder or (not remove and not (staging / 'next_payload').exists() and folder.exists()):
                folder.rename(staging / 'failed_payload')
            if old_folder.exists():
                old_folder.rename(folder)
            if old_launcher.exists():
                old_launcher.rename(launcher)
        except OSError as recovery_error:
            raise RuntimeError(f'Rollback could not finish; recover the previous installation from {backup}: {recovery_error}') from exc
        raise


def manage(action: str, destination: Path, *, dry_run: bool = False, generate: bool = False) -> Path | None:
    destination = validate_destination(destination)
    existing = inspect_installation(destination)
    if action == 'status':
        print(f'Mod directory: {destination}')
        if existing['present']:
            state = 'partial (update repairs it)' if existing['partial'] else 'installed'
            print(f'VTD: {state}; version {existing["version"] or "unknown"}')
        else:
            print('VTD: not installed')
        return None
    if action not in ('install', 'update', 'remove'):
        raise ValueError(f'Unknown operation: {action}')
    if action == 'install' and existing['present']:
        raise ValueError('VTD already exists. Use update to replace it with an automatic backup.')
    if action in ('update', 'remove') and not existing['present']:
        if action == 'remove':
            print(f'VTD is already absent: {destination}')
            return None
        raise ValueError('VTD is not installed here. Run install first.')
    print(f'{action.capitalize()} VTD: {destination}')
    if dry_run:
        print('Preview only; no files or source assets changed.')
        if generate and action != 'remove':
            print('Would regenerate and validate source assets before copying.')
        if existing['present']:
            print(f'Would back up the old payload and descriptor under {destination.parent / "vtd-backups"}.')
        return None
    if action != 'remove':
        print('Validating source assets...', flush=True)
        validate_source(generate=generate)
    destination.mkdir(parents=True, exist_ok=True)
    with install_lock(destination):
        # Re-check after taking the lock: never replace an install created meanwhile.
        existing = inspect_installation(destination)
        if action == 'install' and existing['present']:
            raise ValueError('An installation appeared; use update.')
        if action != 'install' and not existing['present']:
            raise ValueError('The installation changed; run status before trying again.')
        with tempfile.TemporaryDirectory(prefix='.vtd-stage-', dir=destination) as tmp:
            staging = Path(tmp)
            if action != 'remove':
                print('Staging mod files...', flush=True)
                stage_payload(staging, destination)
            if existing['present']:
                print('Backing up the previous installation...', flush=True)
            backup = backup_installation(destination, action) if existing['present'] else None
            print('Applying installation changes...', flush=True)
            swap_installation(destination, staging, remove=action == 'remove', backup=backup)
    print('Removed VTD.' if action == 'remove' else 'VTD ready. Restart the launcher and enable it in a playset.')
    if backup:
        print(f'Previous installation backed up: {backup}')
    return backup


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, epilog='update copies the current local checkout; run git pull --ff-only first for remote changes.')
    parser.add_argument('--mod-dir', type=Path, help='Victoria 3 user-data mod folder; also VTD_MOD_DIR')
    parser.add_argument('--dry-run', action='store_true', help='preview without changing files')
    parser.add_argument('--menu', action='store_true', help='open the menu even when console input is redirected')
    subparsers = parser.add_subparsers(dest='action')
    for action in ('install', 'update', 'remove', 'status'):
        sub = subparsers.add_parser(action)
        sub.add_argument('--mod-dir', type=Path, default=argparse.SUPPRESS)
        sub.add_argument('--dry-run', action='store_true', default=argparse.SUPPRESS)
        if action in ('install', 'update'):
            sub.add_argument('--generate', action='store_true', help='regenerate shared assets before validation')
    args = parser.parse_args(argv)
    try:
        destination = find_mod_dir(args.mod_dir)
        if args.action is None:
            if not args.menu and not sys.stdin.isatty():
                parser.print_help()
                return 2
            print(f'VTD local test installer / 本地测试安装工具\nMod directory: {destination}')
            print('1 Install / 安装\n2 Update local copy / 更新本地安装\n3 Remove / 移除\n4 Status / 状态\n0 Exit / 退出')
            actions = {'1':'install', '2':'update', '3':'remove', '4':'status'}
            choice = input('Choose / 选择: ').strip()
            if choice == '0':
                return 0
            if choice not in actions:
                raise ValueError('Choose 0, 1, 2, 3 or 4.')
            args.action = actions[choice]
        manage(args.action, destination, dry_run=args.dry_run, generate=getattr(args, 'generate', False))
    except (ValueError, OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f'VTD: {exc}', file=sys.stderr)
        return 1
    except (EOFError, KeyboardInterrupt):
        print('VTD: cancelled.', file=sys.stderr)
        return 130
    return 0


if __name__ == '__main__':
    sys.path.insert(0, str(ROOT))
    raise SystemExit(main())
