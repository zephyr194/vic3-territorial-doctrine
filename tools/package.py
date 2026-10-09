#!/usr/bin/env python3
"""Validate and package the mod, or install into an explicitly chosen mod folder."""
import argparse
from pathlib import Path
import shutil
import sys
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools'))
from generate import outputs  # noqa: E402
from validate import validate  # noqa: E402
from territorial_doctrine.model import RULES  # noqa: E402

NAME = 'territorial_doctrine'


def descriptor(path: str) -> str:
    if any(c in path for c in ('"', '\n', '\r')):
        raise ValueError('Installation path contains unsupported characters')
    return (f'name="Territorial Doctrine - 国家领土原则"\nversion="{RULES["version"]}"\n'
            'supported_version="1.13.*"\ntags={ "Gameplay" "Politics" }\n'
            f'path="{path}"\n')


def check() -> None:
    errors = validate(ROOT / 'mod')
    for path, expected in outputs().items():
        if not path.exists() or path.read_bytes() != expected:
            errors.append(f'Stale generated file: {path.relative_to(ROOT)}')
    if errors:
        raise ValueError('\n'.join(errors))


def package(output: Path) -> None:
    check()
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, 'w', compression=ZIP_DEFLATED) as archive:
        for file in sorted((ROOT / 'mod').rglob('*')):
            if file.is_file():
                archive.write(file, Path(NAME) / file.relative_to(ROOT / 'mod'))
        archive.write(ROOT / 'LICENSE', f'{NAME}/LICENSE')
        archive.writestr(f'{NAME}.mod', descriptor(f'mod/{NAME}'))
        archive.write(ROOT / 'docs/INSTALL.md', 'INSTALL.md')
    print(f'Packaged: {output.resolve()}')


def install(destination: Path) -> None:
    check()
    destination = destination.expanduser().resolve()
    checkout = ROOT.resolve()
    if destination == checkout or checkout in destination.parents:
        raise ValueError('Choose the game user-data mod directory outside the source checkout')
    folder = destination / NAME
    launcher = destination / f'{NAME}.mod'
    if folder.exists() or launcher.exists():
        raise ValueError('Installation already exists; move or remove it yourself before installing. No files overwritten.')
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.td-install-', dir=destination) as tmp:
        staging = Path(tmp) / NAME
        shutil.copytree(ROOT / 'mod', staging)
        shutil.copyfile(ROOT / 'LICENSE', staging / 'LICENSE')
        # Exclusive creation protects a preexisting launcher file.
        with launcher.open('x', encoding='utf-8') as file:
            file.write(descriptor(folder.as_posix()))
        try:
            staging.rename(folder)
        except BaseException:
            launcher.unlink()
            raise
    print(f'Installed: {folder}; enable it in a launcher playset.')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--output', type=Path, default=None)
    group.add_argument('--install-dir', type=Path, help='Victoria 3 user-data mod directory')
    args = parser.parse_args()
    try:
        if args.install_dir:
            install(args.install_dir)
        else:
            package(args.output or ROOT / 'dist' / f'{NAME}-{RULES["version"]}.zip')
    except (ValueError, OSError) as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
