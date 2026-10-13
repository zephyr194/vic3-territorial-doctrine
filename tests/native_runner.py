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
    context.update({'var:td_bill': 0, 'var:td_pending_bill': 0,
        'has_claim:var:td_target.state_region': False,
        'var:td_target.td_colonial_target_trigger': False})
    for p in RULES['colonial']['policies'].values():
        if 'law' in p:
            context['has_law:law_type:' + p['law']] = False
    for tech in RULES['colonial']['humanitarian_technologies']:
        context['has_technology_researched:' + tech] = False
    return context


class EventRunner:
    def __init__(self, rolls=(), *, country='SPA'):
        self.country = country
        self.bureaucracy = 1000
        self.gold_reserves = 1000000
        self.total_population = 10000000
        self.legitimacy = 70
        self.auto_negotiate = True
        self.real_politics = False
        self.windows = []
        self.checking_leader = False
        self.scoped_expirations = {}
        self.previous_scope = None
        self.definitions = {}
        self.values = {}
        for path in (ROOT / 'mod').rglob('*.txt'):
            for e in load(path):
                self.definitions[e.key] = e.value
                if path.parent.name == 'script_values':
                    self.values[e.key] = e.value
        self.globals = {'td_system_enabled': 1}
        self.policy = policy_context()
        self.groups = {f'ig:ig_{g}': {'variables': {}, 'ideologies': set(), 'modifiers': {},
                        'approval': 0, 'clout': 1/8, 'leader_ideologies': set(), 'leader_exists': True}
                       for g in RULES['groups']}
        self.owner_updates = 0
        self.variables = {'td_target': 'A', 'td_generation': 0, 'td_reason': 1, 'td_focus_epoch': 0, 'td_focus_count': 0}
        self.lists = {}
        self.expirations = {}
        self.modifiers = {}
        self.modifier_expirations = {}
        self.states = {key: {'owner': country, 'state_population': 1_000_000,
                            'turmoil': 0, 'devastation': 0, 'incorporated': False,
                            'homeland': False, 'treaty_port': False,
                            'region': 'R1' if key == 'A' else 'R2',
                            'variables': {'td_source_administration': 1,
                                          'td_live_administration': 1, 'td_live_diplomatic': 1},
                            'modifiers': {'td_requires_admission': 1}} for key in ('A', 'B')}
        self.claims = set()
        self.scope = None  # None is country; a letter identifies a state.
        self.saved = {}
        self.inputs = {'td_bill_target_valid_trigger': True,
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
        for name,day in list(self.expirations.items()):
            if day <= self.day:
                self.variables.pop(name,None)
                del self.expirations[name]
        for (scope,name),day in list(self.scoped_expirations.items()):
            if day <= self.day:
                (self.groups[scope] if scope in self.groups else self.states[scope])['variables'].pop(name,None)
                del self.scoped_expirations[scope,name]
        if self.scope in self.groups:
            return self.groups[self.scope]['variables']
        return self.states[self.scope]['variables'] if self.scope else self.variables

    def modifier_storage(self, scope=None):
        if scope in self.groups:
            return self.groups[scope]['modifiers']
        return self.states[scope]['modifiers'] if scope else self.modifiers

    def context(self):
        for (scope,name),day in list(self.scoped_expirations.items()):
            if day <= self.day:
                (self.groups[scope] if scope in self.groups else self.states[scope])['variables'].pop(name,None)
                del self.scoped_expirations[scope,name]
        for key, day in list(self.modifier_expirations.items()):
            if day <= self.day:
                scope, modifier = key
                self.modifier_storage(scope).pop(modifier, None)
                del self.modifier_expirations[key]
        for key in [k for k, day in self.expirations.items() if day <= self.day]:
            self.variables.pop(key, None)
            del self.expirations[key]
        context = self.policy.copy()
        context.update({'var:' + k: v for k, v in self.variables.items()})
        context.update({'root.var:' + k: v for k, v in self.variables.items()})
        context.update({'scope:' + k: v for k, v in self.saved.items()})
        planning = sum(RULES['negotiation']['planning_bureaucracy'] for kind in ('navy','railway') if 'td_'+kind+'_planning' in self.modifiers)
        context.update({'is_player': True, 'bureaucracy': self.bureaucracy-planning, 'gold_reserves': self.gold_reserves, 'authority': 1000, 'root': self.country,
                        'is_subject':False,'is_revolutionary':False,'legitimacy':self.legitimacy,
                        'is_at_war':False,'scaled_debt':0,'total_population':self.total_population,
                        'has_modifier:country_bankruptcy':False,
                        'has_interest_marker_in_region:var:td_target.region':True,
                        'prev': self.previous_scope})
        for name,key in self.variables.items():
            if isinstance(key,str) and key in self.states:
                state = self.states[key]
                for prop in ('state_population','turmoil','devastation','owner','region'):
                    context['var:'+name+'.'+prop] = state[prop]
                for building in ('naval_base','railway'):
                    context['var:'+name+'.state_has_building_type_levels:bt:building_'+building] = state.get('buildings',{}).get(building,0)
        if self.previous_scope in self.groups:
            context['prev.ig_clout'] = self.groups[self.previous_scope]['clout']
            context.update({'prev.var:'+k:v for k,v in self.groups[self.previous_scope]['variables'].items()})
        context['has_claim:var:td_target.state_region'] = self.variables.get('td_target') in self.claims
        target = self.variables.get('td_target')
        if target in self.states:
            state = self.states[target]
            context.update({'var:td_target.' + k: v for k, v in state.items() if k not in ('variables', 'modifiers')})
            context.update({'var:td_target.var:' + k: v for k, v in state['variables'].items()})
            context['var:td_accepted_share'] = self.variables.get('td_accepted_share', 1)
        context.update({'has_variable:' + k: True for k in self.variables})
        if self.scope in self.groups:
            group = self.groups[self.scope]
            context['ig_approval'] = group['approval'] + sum(
                RULES['negotiation']['fulfilled_approval'] if name=='td_pledge_fulfilled' else
                RULES['negotiation']['broken_approval'] if name=='td_pledge_broken' else 0
                for name in group['modifiers'])
            context.update({'owner.var:' + k: v for k, v in self.variables.items()})
            for name in ('td_colonial_expansion_pull','td_colonial_admission_pull'):
                context['owner.' + name] = formula(name, context, self.values)
            context.update({'var:' + k: v for k, v in self.storage().items()})
            context['owner'] = self.country
        elif self.scope:
            context.update({'var:' + k: v for k, v in self.storage().items()})
            context.update(owner=self.states[self.scope]['owner'], root=self.country)
            context['is_treaty_port'] = self.states[self.scope]['treaty_port']
            context['is_coastal'] = self.states[self.scope].get('coastal',True)
            for building in ('naval_base','railway'):
                context['state_has_building_type_levels:bt:building_'+building] = self.states[self.scope].get('buildings',{}).get(building,0)
        return context

    def resolve(self, value):
        if value == 'prev':
            return self.previous_scope
        if value == 'prev.state_region':
            return self.states[self.previous_scope].get('state_region', self.previous_scope)
        if value.startswith('prev.state_has_building_type_levels:bt:building_'):
            return self.states[self.previous_scope].get('buildings',{}).get(value.split('building_')[-1],0)
        if value.startswith('var:') and value.endswith('.state_region'):
            key = self.variables[value[4:].split('.')[0]]
            return self.states[key].get('state_region',key)
        if value == 'owner':
            return self.country if self.scope in self.groups or self.scope is None else self.states[self.scope]['owner']
        if value == 'root':
            return self.country
        if value.startswith('owner.var:'):
            return self.variables[value.removeprefix('owner.var:')]
        if value.startswith('root.var:'):
            return self.variables[value.removeprefix('root.var:')]
        if value == 'var:td_target.state_region':
            target = self.variables['td_target']
            return self.states[target].get('state_region', target)
        context = self.context()
        if value in context:
            return context[value]
        return formula(value, context, self.values)

    def check(self, entries):
        for e in entries:
            if e.key in ('OR', 'AND', 'NOT'):
                result = (any(self.check([v]) for v in e.value) if e.key == 'OR'
                          else not self.check(e.value) if e.key == 'NOT' else self.check(e.value))
            elif e.key == 'if':
                limit=next((v.value for v in e.value if v.key=='limit'),[])
                result=not self.check(limit) or self.check([v for v in e.value if v.key!='limit'])
            elif e.key == 'is_target_in_variable_list':
                settings={v.key:v.value for v in e.value}
                result=self.resolve(settings['target']) in self.lists.get(settings['name'],set())
            elif e.key in ('root','owner') and isinstance(e.value, list):
                previous_scope = self.scope
                self.scope = None
                result = self.check(e.value)
                self.scope = previous_scope
            elif e.key.startswith('var:') and isinstance(e.value, list):
                previous_scope = self.scope
                self.scope = self.variables[e.key.removeprefix('var:')]
                result = self.check(e.value)
                self.scope = previous_scope
            elif e.key == 'exists':
                result = ((e.value.removeprefix('var:') in self.storage()) if e.value.startswith('var:')
                          else (e.value.removeprefix('scope:') in self.saved))
                if e.value == 'leader':
                    result = self.scope in self.groups and self.groups[self.scope]['leader_exists']
                if result and e.value.startswith('var:') and e.value.endswith(('target','state')):
                    result = self.storage()[e.value.removeprefix('var:')] in self.states
            elif e.key == 'has_claim':
                region = self.resolve(e.value)
                result = region in self.claims or any(
                    self.states[s].get('state_region', s) == region for s in self.claims if s in self.states)
            elif e.key == 'has_global_variable':
                result = e.value in self.globals
            elif e.key == 'has_ideology':
                result = e.value.removeprefix('ideology:') in self.groups[self.scope]['leader_ideologies' if self.checking_leader else 'ideologies']
            elif e.key == 'leader' and isinstance(e.value,list):
                old = self.checking_leader
                self.checking_leader = True
                result = self.check(e.value)
                self.checking_leader = old
            elif e.key == 'is_interest_group_type':
                result = self.scope == 'ig:' + e.value
            elif e.key == 'td_non_homeland_state_trigger':
                state = self.states[self.scope]
                result = (not state['incorporated'] and not state['homeland'] and not state['treaty_port']) == (e.value == 'yes')
            elif e.key == 'is_homeland_of_country_cultures':
                result = self.states[self.scope]['homeland']
            elif e.key == 'td_colonial_target_trigger' and 'var:td_target.td_colonial_target_trigger' in self.policy:
                result = self.policy['var:td_target.td_colonial_target_trigger'] == (e.value == 'yes')
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
            elif e.key in ('scope:td_mandate_war','every_scope_war','add_war_exhaustion'):
                self.execute([e])
            elif e.key == 'set_global_variable':
                self.globals[e.value] = 1
            elif e.key in ('every_country','root','owner'):
                previous_scope = self.scope
                self.previous_scope = previous_scope
                self.scope = None
                self.execute(e.value)
                self.scope = previous_scope
            elif e.key in ('every_state','every_scope_state','every_interest_group'):
                previous_scope = self.scope
                for scoped in (self.groups if e.key == 'every_interest_group' else self.states):
                    if e.key == 'every_scope_state' and self.states[scoped]['owner'] != self.country:
                        continue
                    self.scope = scoped
                    self.execute(e.value)
                self.scope = previous_scope
            elif e.key in ('ordered_state', 'ordered_scope_state'):
                previous_scope = self.scope
                limit = next((v.value for v in e.value if v.key == 'limit'), [])
                candidates = []
                for state in self.states:
                    if e.key == 'ordered_scope_state' and self.states[state]['owner'] != self.country:
                        continue
                    self.scope = state
                    if self.check(limit):
                        candidates.append(state)
                # Explicit fixture for the engine's population ordering.
                candidates.sort(key=lambda s: self.states[s]['state_population'], reverse=True)
                maximum = next((int(v.value) for v in e.value if v.key == 'max'), len(candidates))
                body = [v for v in e.value if v.key not in ('limit', 'order_by', 'max')]
                for state in candidates[:maximum]:
                    self.scope = state
                    self.execute(body)
                self.scope = previous_scope
            elif e.key == 'prev':
                previous_scope = self.scope
                self.scope = self.previous_scope
                self.execute(e.value)
                self.scope = previous_scope
            elif e.key in self.groups:
                previous_scope = self.scope
                self.scope = e.key
                self.execute(e.value)
                self.scope = previous_scope
            elif e.key in ('add_ideology','remove_ideology'):
                if e.key == 'add_ideology':
                    self.groups[self.scope]['ideologies'].add(e.value)
                else:
                    self.groups[self.scope]['ideologies'].discard(e.value)
            elif e.key == 'td_update_state_owner_effect':
                self.owner_updates += 1  # Owner history is a separate model fixture.
            elif e.key == 'clear_variable_list':
                self.lists.pop(e.value, None)
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
                            until = self.day + days * formula(settings[unit], self.context(), self.values)
                            if self.scope:
                                self.scoped_expirations[self.scope,name] = until
                            else:
                                self.expirations[name] = until
            elif e.key == 'change_variable':
                settings = {v.key: v.value for v in e.value}
                name = settings['name']
                self.storage()[name] = formula([Entry('value', '=', str(self.storage()[name])),
                    *[v for v in e.value if v.key != 'name']], self.context(), self.values)
            elif e.key == 'remove_variable':
                self.storage().pop(e.value, None)
                self.expirations.pop(e.value, None)
            elif e.key == 'save_scope_as':
                self.saved[e.value]=self.scope
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
                if self.real_politics:
                    self.execute(self.definitions[e.key])
                else:
                    self.variables['td_chance'] = 42  # Explicit old probability fixture.
            elif e.key == 'td_refresh_target_effect':
                pass  # Explicit population and eligibility fixtures.
            elif e.key in ('activate_law', 'deactivate_law'):
                if e.key == 'activate_law':
                    for doctrine in RULES['doctrines']:
                        self.policy['has_law:law_type:law_td_' + doctrine] = False
                self.policy['has_law:' + e.value] = e.key == 'activate_law'
            elif e.key == 'add_modifier':
                settings = ({'name':e.value} if isinstance(e.value, str) else {v.key:v.value for v in e.value})
                modifiers = self.modifier_storage(self.scope)
                modifiers[settings['name']] = formula(settings.get('multiplier', '1'), self.context(), self.values)
                delay = sum(days * formula(settings[unit], self.context(), self.values)
                            for unit, days in [('days', 1), ('months', 30), ('years', 365)] if unit in settings)
                if delay:
                    self.modifier_expirations[self.scope, settings['name']] = self.day + delay
            elif e.key == 'remove_modifier':
                modifiers = self.modifier_storage(self.scope)
                modifiers.pop(e.value, None)
                self.modifier_expirations.pop((self.scope, e.value), None)
            elif e.key in ('add_radicals_in_state', 'add_loyalists_in_state'):
                settings = {v.key: v.value for v in e.value}
                self.states[self.scope].setdefault('political_changes', []).append(
                    (e.key, formula(settings['value'], self.context(), self.values)))
            elif e.key.startswith('var:') and isinstance(e.value,list):
                previous_scope = self.scope
                self.scope = (self.states[self.variables['td_target']]['region'] if e.key == 'var:td_target.region'
                              else self.variables[e.key[4:].split('.')[0]])
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
            elif e.key == 'add_treasury':
                self.gold_reserves += formula(e.value,self.context(),self.values)
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
            for e in event:
                if e.key == 'immediate':
                    self.execute(e.value)
            if name == 'td.32' and self.auto_negotiate:
                self.execute(self.definitions['td_resolve_round_effect'])
                return
            self.windows.append({'name':name,'saved':self.saved.copy()})
            self.notifications.append(name)

    def choose(self, window, option):
        self.saved = window['saved'].copy()
        event = self.definitions[window['name']]
        block = next(e.value for e in event if e.key == 'option' and any(v.key == 'name' and v.value == option for v in e.value))
        condition = next((e.value for e in block if e.key == 'trigger'),[])
        if not self.check(condition):
            return False
        self.execute([e for e in block if e.key not in ('name','trigger','ai_chance')])
        return True

    def next_event(self):
        self.day, _, name, self.saved = heapq.heappop(self.queue)
        self.fire(name)

    def run_until(self, day):
        while self.queue and self.queue[0][0] <= day:
            self.next_event()
        self.day = day


class WarRunner(EventRunner):
    """Actual war-effect branches with explicit game target-query fixtures.

    Membership of a state in this war's conquest/annexation targets is supplied
    by tests. This deliberately does not claim to emulate 1.13 war-goal scopes.
    """
    def __init__(self, *, country='SPA'):
        super().__init__(country=country)
        self.wars = {'W1': {'variables': {}, 'engine_exhaustion': 0},
                     'W2': {'variables': {}, 'engine_exhaustion': 0}}
        self.targets = {'W1': {'A','B'}, 'W2': {'B'}}
        self.attacker_warleaders = {'W1': country, 'W2': country}
        self.participants = {'W1': {country, 'ENEMY'}, 'W2': {country, 'ENEMY'}}
        self.claims.update(('A','B'))
        self.saved['td_mandate_war'] = 'W1'
        self.previous_scope = None

    def storage(self):
        if self.scope in getattr(self,'wars',{}):
            return self.wars[self.scope]['variables']
        return super().storage()

    def context(self):
        if self.scope not in self.wars:
            return super().context()
        previous = self.scope
        self.scope = None
        context = super().context()
        self.scope = previous
        context.update({'var:'+k:v for k,v in self.storage().items()})
        return context

    def resolve(self, value):
        return super().resolve(value)

    def check(self, entries):
        for e in entries:
            if e.key == 'scope:td_mandate_war':
                previous = self.scope
                self.scope = self.saved['td_mandate_war']
                result = self.check(e.value)
                self.scope = previous
            elif e.key == 'any_state':
                previous = self.scope
                result = False
                for state in self.states:
                    self.scope = state
                    if self.check(e.value):
                        result = True
                        break
                self.scope = previous
            elif e.key == 'td_war_expansion_target_trigger':
                result = (self.scope in self.targets[self.saved['td_mandate_war']]) == (e.value == 'yes')
            elif e.key == 'attacker_warleader':
                result = self.attacker_warleaders[self.scope] == self.resolve(e.value)
            elif e.key == 'is_war_participant':
                result = self.resolve(e.value) in self.participants[self.scope]
            elif e.key == 'has_claim_by':
                result = self.scope in self.claims
            elif e.key == 'root' and isinstance(e.value,list):
                previous = self.scope
                self.previous_scope = previous
                self.scope = None
                result = self.check(e.value)
                self.scope = previous
            elif e.key == 'is_target_in_variable_list':
                settings = {v.key:v.value for v in e.value}
                result = self.resolve(settings['target']) in self.lists.get(settings['name'],set())
            else:
                result = super().check([e])
            if not result:
                return False
        return True

    def execute(self, entries):
        if len(entries) != 1:
            # Most bodies contain ordinary effects; base dispatch calls back
            # through this method for nested scoped blocks.
            return super().execute(entries)
        e = entries[0]
        if e.key == 'scope:td_mandate_war':
            previous = self.scope
            self.scope = self.saved['td_mandate_war']
            self.execute(e.value)
            self.scope = previous
        elif e.key == 'every_scope_war':
            previous = self.scope
            limit = next((v.value for v in e.value if v.key == 'limit'),[])
            for war in self.wars:
                self.scope = war
                if self.check(limit):
                    self.execute([v for v in e.value if v.key != 'limit'])
            self.scope = previous
        elif e.key == 'add_war_exhaustion':
            settings = {v.key:v.value for v in e.value}
            if self.resolve(settings['target']) != self.country:
                raise ValueError('Unexpected exhaustion recipient')
            self.wars[self.scope]['engine_exhaustion'] += self.resolve(settings['value'])
        else:
            super().execute(entries)
