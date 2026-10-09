"""Symbolic control-flow checks of actual emitted scripts, not a game emulator.

Politics, eligibility, population enumeration and engine scopes are explicit
fixtures. Saved event values and per-state storage are tracked to catch timer
and target-isolation regressions. Calendar months here use 30 days.
"""
import heapq
from pathlib import Path

from territorial_doctrine.model import RULES
from territorial_doctrine.script import Entry, formula, load, triggers

ROOT = Path(__file__).resolve().parents[1]


def policy_context(government='other', power='other', doctrine='strategic_frontiers', reason=None):
    context = {f'has_law:law_type:law_td_{d}': d == doctrine for d in RULES['doctrines']}
    context.update({f'has_law:law_type:law_{law}': enabled for law, enabled in {
        'monarchy': government == 'monarchy', 'presidential_republic': government == 'republic',
        'parliamentary_republic': False, 'autocracy': power == 'autocracy',
        'single_party_state': False, 'census_suffrage': False,
        'universal_suffrage': power == 'democracy',
    }.items()})
    context['var:td_reason'] = RULES['reasons'][reason]['id'] if reason else 0
    context.update({'var:td_bill': 0, 'var:td_pending_bill': 0})
    return context


class EventRunner:
    def __init__(self, rolls=()):
        self.definitions = {}
        self.values = {}
        for path in (ROOT / 'mod').rglob('*.txt'):
            for e in load(path):
                self.definitions[e.key] = e.value
                if path.parent.name == 'script_values':
                    self.values[e.key] = e.value
        self.variables = {'td_target': 'A', 'td_generation': 0, 'td_reason': 1}
        self.lists = {}
        self.expirations = {}
        self.modifiers = {}
        self.states = {key: {'owner': 'SPA', 'state_population': 1_000_000,
                            'turmoil': 0, 'devastation': 0, 'incorporated': False,
                            'variables': {'td_source_administration': 1,
                                          'td_live_administration': 1, 'td_live_diplomatic': 1},
                            'modifiers': {'td_requires_admission': 1}} for key in ('A', 'B')}
        self.claims = set()
        self.scope = None  # None is country; a letter identifies a state.
        self.saved = {}
        self.inputs = {'td_bill_target_valid_trigger': True, 'td_can_legislate_trigger': True,
                       'td_admission_target_valid_trigger': True, 'td_fast_ready_trigger': True}
        self.rolls = iter(rolls)
        self.day = 0
        self.queue = []
        self.serial = 0
        self.notifications = []

    @property
    def claimed(self):
        return 'A' in self.claims

    @property
    def incorporated(self):
        return self.states['A']['incorporated']

    def storage(self):
        return self.states[self.scope]['variables'] if self.scope else self.variables

    def context(self):
        for key in [k for k, day in self.expirations.items() if day <= self.day]:
            self.variables.pop(key, None)
            del self.expirations[key]
        context = policy_context()
        context.update({'var:' + k: v for k, v in self.variables.items()})
        context.update({'scope:' + k: v for k, v in self.saved.items()})
        context.update({'is_player': True, 'bureaucracy': 1000})
        target = self.variables.get('td_target')
        if target:
            state = self.states[target]
            context.update({'var:td_target.' + k: v for k, v in state.items() if k not in ('variables', 'modifiers')})
            context.update({'var:td_target.var:' + k: v for k, v in state['variables'].items()})
            context['var:td_accepted_share'] = 1
        context.update({'has_variable:' + k: True for k in self.variables})
        if self.scope:
            context.update({'var:' + k: v for k, v in self.storage().items()})
            context.update(owner=self.states[self.scope]['owner'], root='SPA')
        return context

    def resolve(self, value):
        if value == 'owner':
            return self.states[self.scope]['owner']
        if value == 'root':
            return 'SPA'
        if value.startswith('root.var:'):
            return self.variables[value.removeprefix('root.var:')]
        if value == 'var:td_target.state_region':
            return self.variables['td_target']
        context = self.context()
        if value in context:
            return context[value]
        return formula(value, context, self.values)

    def check(self, entries):
        for e in entries:
            if e.key in ('OR', 'AND', 'NOT'):
                result = (any(self.check([v]) for v in e.value) if e.key == 'OR'
                          else not self.check(e.value) if e.key == 'NOT' else self.check(e.value))
            elif e.key == 'has_variable':
                result = e.value in self.storage()
            elif e.key in self.inputs:
                result = self.inputs[e.key] == (e.value == 'yes')
            elif e.key in self.definitions and e.key not in self.values:
                result = self.check(self.definitions[e.key]) == (e.value == 'yes')
            else:
                result = triggers([e], self.context(), self.values)
            if not result:
                return False
        return True

    def execute(self, entries):
        previous_if = False
        for e in entries:
            if e.key in ('if', 'else_if', 'else'):
                limit = next((v.value for v in e.value if v.key == 'limit'), [])
                enabled = (e.key == 'if' or not previous_if) and self.check(limit)
                if e.key == 'if':
                    previous_if = False
                if enabled:
                    self.execute([v for v in e.value if v.key != 'limit'])
                    previous_if = True
            elif e.key == 'set_variable':
                if isinstance(e.value, str):
                    self.storage()[e.value] = 1
                else:
                    settings = {v.key: v.value for v in e.value}
                    name = settings['name']
                    value = settings.get('value', '1')
                    self.storage()[name] = (self.resolve(value) if isinstance(value, str)
                                            else formula(value, self.context(), self.values))
                    for unit, days in [('days', 1), ('months', 30), ('years', 365)]:
                        if unit in settings:
                            self.expirations[name] = self.day + days * formula(settings[unit], self.context(), self.values)
            elif e.key == 'change_variable':
                settings = {v.key: v.value for v in e.value}
                name = settings['name']
                self.storage()[name] = formula([Entry('value', '=', str(self.storage()[name])),
                    *[v for v in e.value if v.key != 'name']], self.context(), self.values)
            elif e.key == 'remove_variable':
                self.storage().pop(e.value, None)
                self.expirations.pop(e.value, None)
            elif e.key == 'save_scope_value_as':
                settings = {v.key: v.value for v in e.value}
                self.saved[settings['name']] = self.resolve(settings['value'])
            elif e.key == 'trigger_event':
                if isinstance(e.value, str):
                    self.fire(e.value)
                else:
                    settings = {v.key: v.value for v in e.value}
                    delay = sum(days * formula(settings[unit], self.context(), self.values)
                                for unit, days in [('days', 1), ('months', 30), ('years', 365)] if unit in settings)
                    self.serial += 1
                    heapq.heappush(self.queue, (self.day + delay, self.serial, settings['id'], self.saved.copy()))
            elif e.key == 'random_list':
                branches = []
                for branch in e.value:
                    modifier = next((v.value for v in branch.value if v.key == 'modifier'), [])
                    weight = float(branch.key) * formula([Entry('value', '=', '1'), *modifier], self.context(), self.values)
                    branches.append((weight, [v for v in branch.value if v.key != 'modifier']))
                cut = next(self.rolls) * sum(weight for weight, _ in branches)
                for weight, body in branches:
                    if cut < weight:
                        self.execute(body)
                        break
                    cut -= weight
            elif e.key == 'td_calculate_politics_effect':
                self.variables['td_chance'] = 42  # Formula itself tested separately.
            elif e.key == 'td_refresh_target_effect':
                pass  # Explicit population and eligibility fixtures.
            elif e.key == 'add_modifier':
                settings = {v.key: v.value for v in e.value}
                modifiers = self.states[self.scope]['modifiers'] if self.scope else self.modifiers
                modifiers[settings['name']] = formula(settings.get('multiplier', '1'), self.context(), self.values)
            elif e.key == 'remove_modifier':
                modifiers = self.states[self.scope]['modifiers'] if self.scope else self.modifiers
                modifiers.pop(e.value, None)
            elif e.key in ('var:td_target', 'var:td_project_target', 'var:td_target.state_region'):
                previous_scope = self.scope
                self.scope = self.variables['td_project_target' if e.key == 'var:td_project_target' else 'td_target']
                self.execute(e.value)
                self.scope = previous_scope
            elif e.key == 'add_claim':
                self.claims.add(self.scope)
            elif e.key == 'remove_claim':
                self.claims.discard(self.scope)
            elif e.key == 'add_to_variable_list':
                settings = {v.key: v.value for v in e.value}
                self.lists.setdefault(settings['name'], set()).add(self.resolve(settings['target']))
            elif e.key == 'set_state_type':
                self.states[self.scope]['incorporated'] = e.value == 'incorporated'
            elif e.key == 'change_infamy':
                self.variables['infamy'] = self.variables.get('infamy', 0) + self.resolve(e.value)
            elif e.key in self.definitions:
                self.execute(self.definitions[e.key])
            else:
                raise ValueError(f'Unimplemented symbolic action: {e.key}')

    def fire(self, name):
        event = self.definitions[name]
        if any(e.key == 'hidden' and e.value == 'yes' for e in event):
            for e in event:
                if e.key == 'immediate':
                    self.execute(e.value)
        else:
            self.notifications.append(name)

    def next_event(self):
        self.day, _, name, self.saved = heapq.heappop(self.queue)
        self.fire(name)
