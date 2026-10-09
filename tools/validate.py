#!/usr/bin/env python3
"""Offline syntax, names, localization and optional engine-symbol checks."""
import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from territorial_doctrine.script import load, walk  # noqa: E402
from territorial_doctrine.model import RULES  # noqa: E402


def validate(mod: Path, schema: Path | None = None, game: Path | None = None) -> list[str]:
    errors = []
    trees = {}
    definitions = {}
    for path in sorted(mod.rglob('*.txt')):
        try:
            tree = load(path)
            trees[path] = tree
            for e in tree:
                if e.key == 'namespace':
                    continue
                if e.key in definitions:
                    errors.append(f'Duplicate definition {e.key} in {path}')
                definitions[e.key] = path
        except (ValueError, UnicodeError) as exc:
            errors.append(f'{path}: {exc}')
    variables = {e.value for tree in trees.values() for e in walk(tree)
                 if e.key == 'name' and isinstance(e.value, str) and e.value.startswith('td_')}
    variables |= {e.value for tree in trees.values() for e in walk(tree)
                  if e.key == 'set_variable' and isinstance(e.value, str)}
    scopes = {e.value for tree in trees.values() for e in walk(tree) if e.key == 'save_scope_as'}
    for path, tree in trees.items():
        for e in walk(tree):
            for token in (e.key, e.value if isinstance(e.value, str) else ''):
                if token.startswith('"'):
                    continue
                if token.startswith(('td_', 'law_td_', 'lawgroup_territorial_', 'ideology_td_', 'je_td_', 'td.')):
                    loc_reference = e.key in ('title', 'desc', 'flavor') or e.key == 'name' and token.startswith('td.')
                    if token not in definitions and token not in variables | scopes and not loc_reference:
                        errors.append(f'{path}: undefined custom name {token}')
                for ref in re.findall(r'(?:var|scope):([A-Za-z_][A-Za-z0-9_]*)', token):
                    if ref.startswith('td_') and ref not in variables | scopes:
                        errors.append(f'{path}: undefined variable/scope {ref}')
                for ref in re.findall(r'(?:law_type|ideology):(\w+)', token):
                    if ('_td_' in ref) and ref not in definitions:
                        errors.append(f'{path}: undefined law/ideology {ref}')
    localizations = {}
    for lang in ('english', 'simp_chinese'):
        keys = {}
        for path in sorted((mod / 'localization' / lang).glob('*.yml')):
            raw = path.read_bytes()
            if not raw.startswith(b'\xef\xbb\xbf'):
                errors.append(f'{path}: localization must have UTF-8 BOM')
            text = raw.decode('utf-8-sig')
            lines = text.splitlines()
            if not lines or lines[0] != f'l_{lang}:':
                errors.append(f'{path}: wrong language header')
            for number, line in enumerate(lines[1:], 2):
                if not line.strip() or line.lstrip().startswith('#'):
                    continue
                m = re.fullmatch(r'\s+([\w.]+):\d+\s+"(?:\\.|[^"\\])*"\s*', line)
                if not m:
                    errors.append(f'{path}:{number}: malformed localization')
                elif m[1] in keys:
                    errors.append(f'{path}:{number}: duplicate key {m[1]}')
                else:
                    keys[m[1]] = path
        localizations[lang] = keys
    if localizations['english'].keys() != localizations['simp_chinese'].keys():
        errors.append('English/Chinese localization keys differ')
    required = set()
    for name, path in definitions.items():
        category = path.parent.name
        if category in ('laws', 'law_groups', 'ideologies', 'decisions'):
            required.update((name, name + '_desc'))
        elif category == 'journal_entries':
            required.update((name, name + '_reason'))
        elif category == 'journal_entry_groups':
            required.add(name)
    for path, tree in trees.items():
        for e in walk(tree):
            if e.key in ('title', 'desc', 'flavor') or e.key == 'name' and isinstance(e.value, str) and e.value.startswith('td.'):
                if isinstance(e.value, str) and e.value.startswith('td.'):
                    required.add(e.value)
            if e.key == 'icon' and isinstance(e.value, str):
                asset = e.value.strip('"')
                if asset.startswith('gfx/') and not (mod / asset).is_file():
                    errors.append(f'{path}: missing icon {asset}')
    for lang, keys in localizations.items():
        for key in sorted(required - keys.keys()):
            errors.append(f'{lang}: missing localization {key}')
    metadata = mod / '.metadata/metadata.json'
    try:
        data = json.loads(metadata.read_text(encoding='utf-8-sig'))
        if data.get('game_id') != 'victoria3' or data.get('supported_game_version') != '1.13.*':
            errors.append('Metadata must target Victoria 3 1.13.*')
    except (OSError, ValueError) as exc:
        errors.append(f'Metadata: {exc}')
    if schema:
        # Symbol coverage only. Does not claim CWT scope/type/cardinality validation.
        symbols = {'root', 'this', 'prev', 'namespace', 'days', 'weeks', 'months', 'years'}
        symbols |= set(definitions)
        for path in schema.rglob('*.cwt'):
            text = path.read_text(encoding='utf-8-sig')
            symbols.update(re.findall(r'alias\[(?:effect|trigger|arithmetic_operation):([\w]+)\]', text))
            symbols.update(re.findall(r'^\s*([A-Za-z_]\w*)\s*(?:==|=)', text, re.M))
        if not any(schema.rglob('effects.cwt')):
            errors.append(f'{schema}: no CWT effects schema found')
        for path, tree in trees.items():
            for e in walk(tree):
                if e.operator and ':' not in e.key and '.' not in e.key and not e.key.isdigit() and e.key not in symbols:
                    errors.append(f'{path}: engine key absent from schema: {e.key}')
    if game:
        # Validate vanilla database identifiers against user-supplied 1.13 files.
        if not (game / 'common').is_dir():
            errors.append(f'{game}: expected the game/ directory containing common/')
        else:
            vanilla = set()
            for directory in ('common', 'map_data/state_regions'):
                for path in (game / directory).rglob('*.txt'):
                    # Only identifiers; do not require parsing the whole base game.
                    vanilla.update(re.findall(r'^\s*([A-Za-z_]\w*)\s*=\s*\{', path.read_text(encoding='utf-8-sig', errors='replace'), re.M))
            required_vanilla = {'SPA', 'MOR', 'STATE_AL_RIF', 'region_north_africa', 'country_bankruptcy',
                                'law_monarchy', 'law_autocracy', 'building_naval_base', 'building_railway',
                                'acceptance_status_5'} | {f'ig_{g}' for g in RULES['groups']}
            for name in sorted(required_vanilla - vanilla):
                errors.append(f'Vanilla identifier missing: {name}; check 1.13 game files before loading')
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--schema', type=Path, help='optional cwtools-vic3-config checkout')
    parser.add_argument('--game-dir', type=Path, help='optional installed Victoria 3/game directory')
    args = parser.parse_args()
    errors = validate(ROOT / 'mod', args.schema, args.game_dir)
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    print('PASS: script structure, custom references, localization and metadata.')
    if args.schema:
        print('PASS: engine symbol coverage against supplied CWT schema (not scope validation).')
    if args.game_dir:
        print('PASS: required vanilla identifiers exist in supplied game files.')
    else:
        print('UNRUN: Victoria 3 1.13 database and in-game behavior; game files are not supplied.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
