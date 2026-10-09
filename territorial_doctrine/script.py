"""Small strict text parser and formula evaluator used by offline checks.

This is not the Victoria 3 engine or a replacement for its scope validator.
Repeated keys and naked list items are preserved (both are legal Jomini syntax).
"""
from dataclasses import dataclass
from pathlib import Path
import re

TOKEN = re.compile(r'\s+|\#[^\n]*|"(?:\\.|[^"\\])*"|>=|<=|!=|\?=|[{}=<>]|[^\s{}=<>!"#]+')


@dataclass(frozen=True)
class Entry:
    key: str
    operator: str | None
    value: str | list['Entry'] | None


def parse(text: str) -> list[Entry]:
    text = text.removeprefix('\ufeff')
    tokens = []
    pos = 0
    while pos < len(text):
        match = TOKEN.match(text, pos)
        if not match:
            raise ValueError(f'Invalid token at offset {pos}: {text[pos:pos+30]!r}')
        token = match.group()
        pos = match.end()
        if not token.isspace() and not token.startswith('#'):
            tokens.append(token)
    index = 0

    def block(nested: bool) -> list[Entry]:
        nonlocal index
        entries = []
        while index < len(tokens):
            key = tokens[index]
            index += 1
            if key == '}':
                if not nested:
                    raise ValueError('Unexpected closing brace')
                return entries
            if key in {'{', '=', '<', '>', '>=', '<=', '!=', '?='}:
                raise ValueError(f'Expected key, found {key}')
            if index < len(tokens) and tokens[index] in {'=', '<', '>', '>=', '<=', '!=', '?='}:
                operator = tokens[index]
                index += 1
                if index == len(tokens) or tokens[index] == '}':
                    raise ValueError(f'Missing value for {key}')
                value = tokens[index]
                index += 1
                if value == '{':
                    value = block(True)
                elif value in {'=', '<', '>', '>=', '<=', '!=', '?='}:
                    raise ValueError(f'Unexpected operator after {key}')
                entries.append(Entry(key, operator, value))
            else:
                entries.append(Entry(key, None, None))
        if nested:
            raise ValueError('Unclosed block')
        return entries

    return block(False)


def load(path: Path) -> list[Entry]:
    return parse(path.read_text(encoding='utf-8-sig'))


def walk(entries: list[Entry]):
    for entry in entries:
        yield entry
        if isinstance(entry.value, list):
            yield from walk(entry.value)


def triggers(entries: list[Entry], context: dict[str, float | bool]) -> bool:
    for e in entries:
        if e.key == 'OR':
            result = any(triggers([v], context) for v in e.value)
        elif e.key == 'NOT':
            result = not triggers(e.value, context)
        elif e.key == 'AND':
            result = triggers(e.value, context)
        elif isinstance(e.value, list):
            # Flatten scoped predicate paths, e.g. ruler.interest_group.var:td_score.
            prefix = e.key + '.'
            result = triggers(e.value, {k.removeprefix(prefix): v for k, v in context.items() if k.startswith(prefix)})
        elif e.key == 'exists':
            result = bool(context.get('exists:' + e.value, False))
        elif e.key in ('has_law', 'has_variable'):
            result = bool(context.get(e.key + ':' + e.value, False))
        else:
            lhs = context[e.key]
            rhs = {'yes': True, 'no': False}.get(e.value)
            if rhs is None:
                rhs = float(e.value) if re.fullmatch(r'-?\d+(\.\d+)?', e.value) else context[e.value]
            result = {'=': lambda: lhs == rhs, '>=': lambda: lhs >= rhs,
                      '<=': lambda: lhs <= rhs, '>': lambda: lhs > rhs,
                      '<': lambda: lhs < rhs, '!=': lambda: lhs != rhs}[e.operator]()
        if not result:
            return False
    return True


def formula(value: str | list[Entry], context: dict, definitions: dict, active=()) -> float:
    if isinstance(value, str):
        if re.fullmatch(r'-?\d+(\.\d+)?', value):
            return float(value)
        if value in definitions:
            if value in active:
                raise ValueError(f'Recursive formula: {value}')
            return formula(definitions[value], context, definitions, (*active, value))
        return float(context[value])
    total = 0.0
    previous_if = False
    from math import ceil, floor
    for e in value:
        if e.key in ('if', 'else_if', 'else'):
            body = [v for v in e.value if v.key != 'limit']
            limit = next((v.value for v in e.value if v.key == 'limit'), [])
            enabled = (e.key == 'if' or not previous_if) and triggers(limit, context)
            if e.key == 'if':
                previous_if = False
            if enabled:
                # Apply conditional operations to the existing accumulator.
                total = formula([Entry('value', '=', str(total)), *body], context, definitions, active)
                previous_if = True
            continue
        if e.key in ('ceiling', 'floor', 'round'):
            total = {'ceiling': ceil, 'floor': floor, 'round': round}[e.key](total)
            continue
        rhs = formula(e.value, context, definitions, active)
        if e.key == 'value':
            total = rhs
        elif e.key == 'add':
            total += rhs
        elif e.key == 'subtract':
            total -= rhs
        elif e.key == 'multiply':
            total *= rhs
        elif e.key == 'divide':
            total /= rhs
        elif e.key == 'min':
            total = min(total, rhs)
        elif e.key == 'max':
            total = max(total, rhs)
        else:
            raise ValueError(f'Unsupported formula operator: {e.key}')
    return total
