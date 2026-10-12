"""Plan regressions using emitted scripts and explicit geography/war fixtures.

JSON roundtrips exercise persisted variables, queues and counters in the symbolic
runner. They do not emulate a Vic3 save format, engine target discovery or PRNG.
"""
from copy import deepcopy
import heapq
import json
from pathlib import Path
import unittest

from native_runner import EventRunner, WarRunner, policy_context
from territorial_doctrine.model import RULES
from territorial_doctrine.script import formula, load

ROOT = Path(__file__).resolve().parents[1]


class GeographyRunner(EventRunner):
    """Execute real candidate predicates; supply engine geography explicitly."""
    def __init__(self, rolls=(), *, country='POR'):
        super().__init__(rolls, country=country)
        self.inputs.clear()
        self.policy.update(policy_context(doctrine='imperial_expansion'))
        self.policy.pop('var:td_target.td_colonial_target_trigger')
        self.interests = {'R1', 'R2'}
        self.adjacent_states = set()
        for key, state in self.states.items():
            state.update(owner='ENEMY', state_region='REGION_'+key,
                         subject_of_root=False, decentralized=False,
                         is_under_colonization=False)

    def context(self):
        context = super().context()
        # Formula evaluator requires an explicit engine result for scoped reads;
        # candidate/bill predicates still execute the actual trigger definition.
        target = self.variables.get('td_target')
        if target:
            context['var:td_target.td_colonial_target_trigger'] = self.states[target].get('colonial_cost_fixture',False)
        if self.scope in self.states:
            context.update({k:v for k,v in self.states[self.scope].items()
                            if k not in ('variables','modifiers')})
        return context

    def resolve(self, value):
        if value == 'prev.region':
            return self.states[self.previous_scope]['region']
        return super().resolve(value)

    def check(self, entries):
        for e in entries:
            if e.key in ('root', 'owner') and isinstance(e.value, list):
                previous_scope, previous_prev = self.scope, self.previous_scope
                self.previous_scope = self.scope
                self.scope = None
                result = self.check(e.value)
                self.scope, self.previous_scope = previous_scope, previous_prev
            elif e.key in ('any_state', 'any_scope_state'):
                previous = self.scope
                result = False
                for key in self.states:
                    if e.key == 'any_scope_state' and self.states[key]['owner'] != self.country:
                        continue
                    self.scope = key
                    if self.check(e.value):
                        result = True
                        break
                self.scope = previous
            elif e.key == 'is_subject_of':
                result = self.states[self.previous_scope]['subject_of_root']
            elif e.key == 'is_country_type':
                result = e.value == 'decentralized' and self.states[self.previous_scope]['decentralized']
            elif e.key == 'has_claim_by':
                region = self.states[self.scope]['state_region']
                result = self.scope in self.claims or any(
                    self.states[s]['state_region'] == region for s in self.claims if s in self.states)
            elif e.key == 'state_region' and isinstance(e.value, str):
                result = self.states[self.scope]['state_region'] == e.value.removeprefix('s:')
            elif e.key == 'this':
                result = self.country == e.value.removeprefix('c:')
            elif e.key == 'is_adjacent_to_state':
                result = self.resolve(e.value) in self.adjacent_states
            elif e.key == 'has_interest_marker_in_region':
                result = self.resolve(e.value) in self.interests
            else:
                result = super().check([e])
            if not result:
                return False
        return True


def set_colonial_policy(runner, policy):
    runner.policy['has_law:law_type:law_no_colonial_affairs'] = policy == 'none'
    for key, info in RULES['colonial']['policies'].items():
        if 'law' in info:
            runner.policy['has_law:law_type:'+info['law']] = key == policy


def roundtrip(runner, *, rolls=()):
    """Reload a fresh runner from only persisted test state, not Python objects."""
    fields = ('variables','states','policy','globals','saved','expirations',
              'modifiers','day','serial','bureaucracy','notifications')
    payload = {name:getattr(runner,name) for name in fields}
    payload.update(lists={k:sorted(v) for k,v in runner.lists.items()},
                   claims=sorted(runner.claims), queue=runner.queue,
                   modifier_expirations=[[scope,name,day] for (scope,name),day in runner.modifier_expirations.items()],
                   groups={k:{'variables':v['variables'],'ideologies':sorted(v['ideologies'])}
                           for k,v in runner.groups.items()})
    if isinstance(runner, WarRunner):
        payload.update(wars=runner.wars, attacker_warleaders=runner.attacker_warleaders,
                       targets={k:sorted(v) for k,v in runner.targets.items()},
                       participants={k:sorted(v) for k,v in runner.participants.items()})
    if isinstance(runner, GeographyRunner):
        payload.update(interests=sorted(runner.interests), adjacent_states=sorted(runner.adjacent_states))
    saved = json.loads(json.dumps(payload))
    restored = type(runner)(country=runner.country)
    restored.rolls = iter(rolls)
    for name in fields:
        setattr(restored,name,saved[name])
    restored.inputs = runner.inputs.copy()
    restored.claims = set(saved['claims'])
    restored.lists = {k:set(v) for k,v in saved['lists'].items()}
    restored.queue = [(day,serial,event,scope) for day,serial,event,scope in saved['queue']]
    heapq.heapify(restored.queue)
    restored.groups = {k:{'variables':v['variables'],'ideologies':set(v['ideologies'])}
                       for k,v in saved['groups'].items()}
    restored.modifier_expirations = {(scope,name):day for scope,name,day in saved['modifier_expirations']}
    for state in restored.states.values():
        if 'political_changes' in state:
            state['political_changes'] = [tuple(change) for change in state['political_changes']]
    if isinstance(restored, WarRunner):
        restored.wars = saved['wars']
        restored.attacker_warleaders = saved['attacker_warleaders']
        restored.targets = {k:set(v) for k,v in saved['targets'].items()}
        restored.participants = {k:set(v) for k,v in saved['participants'].items()}
    if isinstance(restored, GeographyRunner):
        restored.interests = set(saved['interests'])
        restored.adjacent_states = set(saved['adjacent_states'])
    return restored


class PlanDeliveryTests(unittest.TestCase):
    def test_policy_switch_and_humanitarian_stages_keep_common_base_rate(self):
        runner = EventRunner()
        expected = {'none':(0,0), 'resettlement':(15,-10), 'exploitation':(20,-20)}
        for policy in ('none','resettlement','exploitation','none'):
            set_colonial_policy(runner, policy)
            runner.execute(runner.definitions['td_refresh_colonial_profile_effect'])
            self.assertEqual((runner.variables['td_expansion_pull'],runner.variables['td_admission_pull']),expected[policy])
        set_colonial_policy(runner,'exploitation')
        for stage, pulls in enumerate(((20,-20),(5,-5),(-10,10))):
            for i, tech in enumerate(RULES['colonial']['humanitarian_technologies']):
                runner.policy['has_technology_researched:'+tech] = i < stage
            runner.execute(runner.definitions['td_refresh_colonial_profile_effect'])
            self.assertEqual((runner.variables['td_expansion_pull'],runner.variables['td_admission_pull']),pulls)
            self.assertEqual(formula('td_bill_base_probability',runner.context(),runner.values),10)

    def test_medical_and_military_research_never_increment_humanitarian_stage(self):
        runner = EventRunner()
        set_colonial_policy(runner,'exploitation')
        for tech in ('quinine','malaria_prevention','pharmaceuticals','breech_loading_artillery'):
            runner.policy['has_technology_researched:'+tech] = True
        runner.execute(runner.definitions['td_refresh_colonial_profile_effect'])
        self.assertEqual(runner.variables['td_humanitarian_level'],0)
        self.assertEqual(runner.variables['td_expansion_pull'],20)
        for tech in RULES['colonial']['humanitarian_technologies']:
            runner.policy['has_technology_researched:'+tech] = True
            self.assertEqual(formula('td_humanitarian_stage',runner.context(),runner.values),1)
            runner.policy['has_technology_researched:'+tech] = False

    def test_policy_and_ideologies_survive_json_reload_without_duplicates(self):
        runner = EventRunner()
        set_colonial_policy(runner,'exploitation')
        runner.policy['has_technology_researched:egalitarianism'] = True
        runner.execute(runner.definitions['td_refresh_colonial_profile_effect'])
        restored = roundtrip(runner)
        groups = deepcopy(restored.groups)
        restored.execute(restored.definitions['td_refresh_colonial_profile_effect'])
        self.assertEqual(restored.groups,groups)
        set_colonial_policy(restored,'resettlement')
        restored.execute(restored.definitions['td_refresh_colonial_profile_effect'])
        self.assertEqual((restored.variables['td_expansion_pull'],restored.variables['td_admission_pull']),(0,5))
        self.assertTrue(all(len(g['ideologies']) == 1 for g in restored.groups.values()))

    def test_generic_candidates_exclude_owned_ports_subjects_and_empty_states(self):
        for country in ('POR','FRA','JAP'):
            runner = GeographyRunner(country=country)
            for key, changes in (('OWN',{'owner':country}),('PORT',{'treaty_port':True}),
                                 ('SUBJECT',{'subject_of_root':True}),('EMPTY',{'state_population':0})):
                runner.states[key] = deepcopy(runner.states['A'])
                runner.states[key].update(changes,state_region='REGION_'+key)
            for _ in range(3):
                runner.execute(runner.definitions['td_select_claim_effect'])
                self.assertIn(runner.variables['td_target'],('A','B'))
                self.assertEqual(runner.variables['td_pending_bill'],1)
            self.assertEqual(runner.lists['td_seen_claim_regions'],{'REGION_A'})

    def test_frontier_requires_adjacency_or_active_colonial_interest(self):
        runner = GeographyRunner()
        runner.policy.update(policy_context(doctrine='strategic_frontiers'))
        runner.policy.pop('var:td_target.td_colonial_target_trigger')
        runner.adjacent_states.add('A')
        set_colonial_policy(runner,'none')
        runner.states['B']['decentralized'] = True
        runner.execute(runner.definitions['td_select_claim_effect'])
        self.assertEqual(runner.variables['td_target'],'A')
        set_colonial_policy(runner,'exploitation')
        runner.execute(runner.definitions['td_select_claim_effect'])
        self.assertEqual(runner.variables['td_target'],'B')
        runner.interests.clear()
        runner.execute(runner.definitions['td_select_claim_effect'])
        self.assertEqual(runner.variables['td_target'],'A')

    def test_empty_generic_menu_never_opens_invalid_state_preview(self):
        runner = GeographyRunner()
        runner.interests.clear()
        runner.execute(runner.definitions['td_select_claim_effect'])
        runner.execute(runner.definitions['td_open_target_menu_effect'])
        self.assertNotIn('td_target',runner.variables)
        self.assertNotIn('td_pending_bill',runner.variables)
        self.assertEqual(runner.notifications,['td.31'])
        self.assertFalse(runner.queue)
        self.assertFalse(runner.modifiers)
        runner.execute(runner.definitions['td_open_review_effect'])
        runner.execute(runner.definitions['td_open_integration_menu_effect'])
        self.assertEqual(runner.notifications,['td.31']*3)

    def test_old_generic_menu_cannot_replace_active_bill_or_project(self):
        for flag in ('td_bill','td_fast','td_regular'):
            runner = GeographyRunner()
            runner.variables[flag] = 1
            before = deepcopy(runner.variables)
            runner.execute(runner.definitions['td_select_claim_effect'])
            self.assertEqual(runner.variables,before)

    def test_portuguese_generic_bills_really_supply_all_war_target_mandates(self):
        runner = GeographyRunner((.1,)*6)
        for state in ('A','B'):
            runner.execute(runner.definitions['td_select_claim_effect'])
            self.assertEqual(runner.variables['td_target'],state)
            runner.execute(runner.definitions['td_designate_focus_effect'])
            runner.run_until(runner.day+360)
            self.assertIn(runner.states[state]['region'],runner.lists['td_ready_focus_regions'])
            runner.variables.update(td_reason=7,td_bill=1)
            runner.execute(runner.definitions['td_start_bill_effect'])
            runner.run_until(runner.day+270)
            self.assertIn(runner.states[state]['state_region'],runner.lists['td_approved_claim_regions'])
        war = WarRunner(country='POR')
        war.policy.update(policy_context(doctrine='imperial_expansion'))
        war.states = deepcopy(runner.states)
        war.claims = runner.claims.copy()
        war.lists = deepcopy(runner.lists)
        war.execute(war.definitions['td_snapshot_war_mandate_effect'])
        self.assertNotIn('td_unauthorized_war',war.wars['W1']['variables'])
        war.execute(war.definitions['td_war_monthly_effect'])
        self.assertEqual(war.wars['W1']['engine_exhaustion'],0)

    def test_colonial_admission_reload_keeps_one_state_one_deadline(self):
        runner = GeographyRunner((.1,)*3)
        for state in runner.states.values():
            state.update(owner='POR',accepted_share=0,culture='cantonese',religion='mahayana',colonial_cost_fixture=True)
            state['variables']['td_colonial_origin'] = 1
        set_colonial_policy(runner,'exploitation')
        runner.policy['has_technology_researched:egalitarianism'] = True
        runner.policy['has_technology_researched:human_rights'] = True
        runner.variables.update(td_bill=2,td_pending_bill=2,td_reason=4,td_accepted_share=0)
        runner.execute(runner.definitions['td_start_bill_effect'])
        runner.run_until(90)
        restored = roundtrip(runner,rolls=(.1,.1))
        restored.variables['td_target'] = 'B'  # Another preview cannot change the frozen bill.
        restored.run_until(270)
        self.assertEqual(restored.variables['td_project_target'],'A')
        self.assertEqual(restored.states['A']['variables']['td_admitted_owner'],'POR')
        self.assertNotIn('td_admitted_owner',restored.states['B']['variables'])
        self.assertEqual(restored.modifiers['td_project_cost'],235)
        restored = roundtrip(restored)
        restored.bureaucracy = -100
        restored.run_until(634)
        self.assertFalse(restored.states['A']['incorporated'])
        restored.run_until(635)
        self.assertTrue(restored.states['A']['incorporated'])
        self.assertFalse(restored.states['B']['incorporated'])
        self.assertEqual(restored.states['A']['culture'],'cantonese')
        self.assertEqual(restored.states['A']['religion'],'mahayana')
        self.assertEqual(restored.states['A']['accepted_share'],0)

    def test_colonial_law_and_generic_owned_selector_never_batch_admit(self):
        runner = GeographyRunner((.1,)*3)
        for state in runner.states.values():
            state.update(owner='POR',colonial_cost_fixture=True)
            state['variables']['td_colonial_origin'] = 1
        set_colonial_policy(runner,'exploitation')
        runner.execute(runner.definitions['td_refresh_colonial_profile_effect'])
        self.assertTrue(all('td_admitted_owner' not in s['variables'] for s in runner.states.values()))
        runner.execute(runner.definitions['td_select_owned_effect'])
        self.assertEqual(runner.variables['td_target'],'A')
        runner.variables.update(td_bill=2,td_reason=4)
        runner.execute(runner.definitions['td_start_bill_effect'])
        runner.run_until(270)
        self.assertEqual(runner.states['A']['variables']['td_admitted_owner'],'POR')
        self.assertNotIn('td_admitted_owner',runner.states['B']['variables'])
        runner.run_until(635)
        runner.execute(runner.definitions['td_select_owned_effect'])
        self.assertEqual(runner.variables['td_target'],'B')
        self.assertEqual(runner.variables['td_pending_bill'],2)

    def test_defender_cannot_initialize_attacking_country_snapshot(self):
        runner = WarRunner(country='POR')
        runner.attacker_warleaders['W1'] = 'ENEMY'
        runner.execute(runner.definitions['td_snapshot_war_mandate_effect'])
        runner.execute(runner.definitions['td_war_monthly_effect'])
        self.assertFalse(runner.wars['W1']['variables'])
        self.assertEqual(runner.wars['W1']['engine_exhaustion'],0)

    def test_pending_bill_and_missing_real_claim_do_not_authorize_war(self):
        for pending in (True,False):
            runner = WarRunner()
            if pending:
                runner.variables.update(td_bill=1,td_bill_target='A',td_successes=2)
            else:
                runner.lists['td_approved_claim_regions'] = {'A','B'}
                runner.claims.remove('B')
            runner.execute(runner.definitions['td_snapshot_war_mandate_effect'])
            self.assertIn('td_unauthorized_war',runner.wars['W1']['variables'])

    def test_departed_attacker_gets_no_more_exhaustion_or_new_snapshot(self):
        runner = WarRunner()
        runner.execute(runner.definitions['td_snapshot_war_mandate_effect'])
        runner.execute(runner.definitions['td_war_monthly_effect'])
        runner.participants['W1'].remove(runner.country)
        runner.execute(runner.definitions['td_war_monthly_effect'])
        self.assertEqual(runner.wars['W1']['engine_exhaustion'],2)
        runner.saved['td_mandate_war'] = 'W2'
        runner.participants['W2'].remove(runner.country)
        runner.execute(runner.definitions['td_snapshot_war_mandate_effect'])
        self.assertFalse(runner.wars['W2']['variables'])

    def test_added_target_and_json_reload_preserve_per_war_caps(self):
        runner = WarRunner()
        runner.lists['td_approved_claim_regions'] = {'A'}
        runner.targets['W1'] = {'A'}
        runner.execute(runner.definitions['td_snapshot_war_mandate_effect'])
        self.assertNotIn('td_unauthorized_war',runner.wars['W1']['variables'])
        runner.targets['W1'].add('B')
        runner.execute(runner.definitions['td_snapshot_war_mandate_effect'])
        for _ in range(4):
            runner.execute(runner.definitions['td_war_monthly_effect'])
        restored = roundtrip(runner)
        restored.lists['td_approved_claim_regions'].add('B')
        restored.execute(restored.definitions['td_snapshot_war_mandate_effect'])
        self.assertEqual(restored.wars['W1']['variables']['td_extra_exhaustion'],8)
        for _ in range(12):
            restored.execute(restored.definitions['td_war_monthly_effect'])
        self.assertEqual(restored.wars['W1']['engine_exhaustion'],20)
        self.assertEqual(restored.wars['W2']['engine_exhaustion'],0)

    def test_defensive_return_state_target_fixture_is_not_checked_as_expansion(self):
        runner = WarRunner()
        runner.policy.update(policy_context(doctrine='status_quo'))
        runner.targets['W1'].clear()  # Engine fixture: pure return_state has no expansion targets.
        runner.execute(runner.definitions['td_snapshot_war_mandate_effect'])
        runner.execute(runner.definitions['td_war_monthly_effect'])
        self.assertNotIn('td_unauthorized_war',runner.wars['W1']['variables'])
        self.assertEqual(runner.wars['W1']['engine_exhaustion'],0)


if __name__ == '__main__':
    unittest.main()
