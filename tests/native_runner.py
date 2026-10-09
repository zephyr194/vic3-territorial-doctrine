"""Symbolic execution of emitted event control flow, not a game emulator.

Eligibility, population enumeration and politics are explicit test inputs.
This checks timers, branches and cleanup in actual files; engine scopes remain
an in-game validation requirement.
"""
import heapq
from pathlib import Path

from territorial_doctrine.script import Entry, formula, load, triggers

ROOT = Path(__file__).resolve().parents[1]


class EventRunner:
    def __init__(self, rolls=()):
        self.definitions = {}
        self.values = {}
        for path in (ROOT / 'mod').rglob('*.txt'):
            for e in load(path):
                self.definitions[e.key] = e.value
                if path.parent.name == 'script_values':
                    self.values[e.key] = e.value
        self.variables = {}
        self.expirations = {}
        self.modifiers = {}
        self.inputs = {'td_bill_target_valid_trigger': True, 'td_can_legislate_trigger': True,
                       'td_admission_target_valid_trigger': True, 'td_fast_ready_trigger': True}
        self.rolls = iter(rolls)
        self.day = 0
        self.queue = []
        self.serial = 0
        self.notifications = []
        self.claimed = False
        self.incorporated = False

    def context(self):
        expired = [k for k, day in self.expirations.items() if day <= self.day]
        for key in expired:
            self.variables.pop(key, None)
            del self.expirations[key]
        return {'var:' + k: v for k, v in self.variables.items()} | {
            's:STATE_AL_RIF.region_state:SPA.state_population': 1_000_000,
            'has_law:law_type:law_td_strategic_frontiers': True,
            'has_law:law_type:law_td_status_quo': False,
            'has_law:law_type:law_td_historical_rights': False,
            'has_law:law_type:law_td_imperial_expansion': False,
        }

    def check(self, entries):
        context = self.context()
        for e in entries:
            if e.key in ('OR', 'AND', 'NOT'):
                result = (any(self.check([v]) for v in e.value) if e.key == 'OR'
                          else not self.check(e.value) if e.key == 'NOT' else self.check(e.value))
            elif e.key == 'has_variable':
                result = e.value in self.variables
            elif e.key in self.inputs:
                result = self.inputs[e.key] == (e.value == 'yes')
            else:
                value = e.value
                if isinstance(value, str) and value in self.values:
                    e = Entry(e.key, e.operator, str(formula(value, context, self.values)))
                result = triggers([e], context)
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
                    self.variables[e.value] = 1
                else:
                    settings = {v.key: v.value for v in e.value}
                    name = settings['name']
                    self.variables[name] = formula(settings.get('value', '1'), self.context(), self.values)
                    for unit, days in [('days', 1), ('months', 30), ('years', 365)]:
                        if unit in settings:
                            self.expirations[name] = self.day + days * formula(settings[unit], self.context(), self.values)
            elif e.key == 'change_variable':
                settings = {v.key: v.value for v in e.value}
                name = settings.pop('name')
                self.variables[name] = formula([
                    Entry('value', '=', str(self.variables[name])),
                    *[v for v in e.value if v.key != 'name']], self.context(), self.values)
            elif e.key == 'remove_variable':
                self.variables.pop(e.value, None)
                self.expirations.pop(e.value, None)
            elif e.key == 'trigger_event':
                if isinstance(e.value, str):
                    self.fire(e.value)
                else:
                    settings = {v.key: v.value for v in e.value}
                    delay = sum(days * formula(settings[unit], self.context(), self.values)
                                for unit, days in [('days', 1), ('months', 30), ('years', 365)] if unit in settings)
                    self.serial += 1
                    heapq.heappush(self.queue, (self.day + delay, self.serial, settings['id']))
            elif e.key == 'random_list':
                branches = []
                for branch in e.value:
                    weight = float(branch.key)
                    modifier = next((v.value for v in branch.value if v.key == 'modifier'), [])
                    weight *= formula([Entry('value', '=', '1'), *modifier], self.context(), self.values)
                    branches.append((weight, [v for v in branch.value if v.key != 'modifier']))
                cut = next(self.rolls) * sum(weight for weight, _ in branches)
                for weight, body in branches:
                    if cut < weight:
                        self.execute(body)
                        break
                    cut -= weight
            elif e.key == 'td_calculate_politics_effect':
                self.variables['td_chance'] = 50
            elif e.key == 'td_refresh_admission_effect':
                pass  # Explicit input; no actual game pops in the runner.
            elif e.key == 'add_modifier':
                settings = {v.key: v.value for v in e.value}
                self.modifiers[settings['name']] = formula(settings.get('multiplier', '1'), self.context(), self.values)
            elif e.key == 'remove_modifier':
                self.modifiers.pop(e.value, None)
            elif e.key == 's:STATE_AL_RIF':
                self.execute(e.value)
            elif e.key == 'add_claim':
                self.claimed = True
            elif e.key == 's:STATE_AL_RIF.region_state:SPA':
                self.execute(e.value)
            elif e.key == 'set_state_type':
                self.incorporated = e.value == 'incorporated'
            elif e.key == 'change_infamy':
                self.variables['infamy'] = self.variables.get('infamy', 0) + float(e.value)
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
        self.day, _, name = heapq.heappop(self.queue)
        self.fire(name)
