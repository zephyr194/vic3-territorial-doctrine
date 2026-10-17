#!/usr/bin/env python3
"""Validate and package the mod, or install into an explicitly chosen mod folder."""
import argparse
from pathlib import Path
import sys
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
    return (f'name="Territorial Doctrine"\nversion="{RULES["version"]}"\n'
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
        # Keep relative links between installation, rules and acceptance docs
        # usable in the delivered ZIP, without needing the GitHub checkout.
        for document in sorted((ROOT / 'docs').glob('*.md')):
            archive.write(document, document.name)
    print(f'Packaged: {output.resolve()}')


def install(destination: Path) -> None:
    # Keep the previous public entry point; use the same ownership checks and
    # transaction code as the local test installer.
    from tools.install import manage
    manage('install', destination)


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
