"""State-only incentives, earned political credit and nonrepeatable local reactions."""
from copy import deepcopy
from pathlib import Path
import unittest

from native_runner import EventRunner, policy_context
from territorial_doctrine.model import RULES
from territorial_doctrine.script import load, parse, walk
from test_law_effects import localization

ROOT = Path(__file__).resolve().parents[1]


def acquired(doctrine='imperial_expansion', *, authorized=True):
    runner = EventRunner(country='POR')
    runner.inputs.clear()
    runner.policy.update(policy_context(doctrine=doctrine))
    runner.states['A']['variables'].update(td_original_owner='CHI', td_acquired_owner='POR')
    runner.states['A']['state_region'] = 'STATE_GUANGDONG'
    # Portugal's original portion is in the same region: it must stay unbuffed.
    runner.states['B']['variables']['td_original_owner'] = 'POR'
    runner.states['B']['state_region'] = 'STATE_GUANGDONG'
    if authorized:
        runner.claims.add('A')
        runner.lists['td_approved_claim_regions'] = {'STATE_GUANGDONG'}
    return runner


def in_state(runner, effect, state='A'):
    previous = runner.scope
    runner.scope = state
    runner.execute(runner.definitions[effect])
    runner.scope = previous


class TerritorialPoliticsTests(unittest.TestCase):
    def test_original_states_including_non_homelands_remain_unbuffed(self):
        runner = EventRunner(country='POR')
        runner.execute(parse('every_state = { td_register_original_territory_effect = yes }'))
        # Even a false acquisition marker cannot turn original states into colonies.
        runner.states['A']['variables']['td_acquired_owner'] = 'POR'
        runner.execute(parse('every_scope_state = { td_refresh_state_development_effect = yes }'))
        for state in runner.states.values():
            self.assertEqual(state['variables']['td_original_owner'], 'POR')
            self.assertFalse(any(m.startswith('td_territory_') for m in state['modifiers']))

    def test_same_region_original_portion_and_other_foreign_states_are_isolated(self):
        runner = acquired()
        runner.states['C'] = deepcopy(runner.states['A'])
        runner.states['C']['owner'] = 'CHI'
        runner.execute(parse('every_scope_state = { td_refresh_state_development_effect = yes }'))
        self.assertIn('td_territory_imperial_expansion', runner.states['A']['modifiers'])
        for s in ('B', 'C'):
            self.assertNotIn('td_territory_imperial_expansion', runner.states[s]['modifiers'])
        # The state remains eligible after its individual administrative integration.
        runner.states['A']['incorporated'] = True
        in_state(runner, 'td_refresh_state_development_effect')
        self.assertIn('td_territory_imperial_expansion', runner.states['A']['modifiers'])

    def test_original_registration_survives_save_load_and_recovery(self):
        runner = acquired()
        in_state(runner, 'td_register_original_territory_effect')
        self.assertEqual(runner.states['A']['variables']['td_original_owner'], 'CHI')
        runner.states['A']['owner'] = 'CHI'
        runner.states['A']['variables']['td_acquired_owner'] = 'CHI'
        in_state(runner, 'td_refresh_state_development_effect')
        self.assertNotIn('td_territory_imperial_expansion', runner.states['A']['modifiers'])
        # Registry callbacks only snapshot once across reloads.
        runner.globals['td_original_registry_ready'] = 1
        original = deepcopy(runner.states)
        runner.execute(next(e.value for e in runner.definitions['td_initialize_world'] if e.key == 'effect'))
        self.assertEqual(runner.states, original)

    def test_laws_never_grant_national_throughput_or_static_legitimacy(self):
        laws = load(ROOT/'mod/common/laws/td_laws.txt')
        for law in laws:
            effects = next(e.value for e in law.value if e.key == 'modifier')
            self.assertFalse(any(e.key.endswith('_throughput_mult') for e in effects))
            self.assertFalse(any(e.key == 'country_legitimacy_base_add' for e in effects))
        modifiers = {e.key:e.value for e in load(ROOT/'mod/common/static_modifiers/td_territory_modifiers.txt')}
        for d, rule in RULES['doctrines'].items():
            actual = {e.key:float(e.value) for e in modifiers['td_territory_'+d]}
            self.assertEqual(actual, rule['territory_modifiers'] | rule['industry_modifiers'])
        legal = {e.key:e.value for e in load(ROOT/'mod/common/static_modifiers/td_modifiers.txt')}
        self.assertEqual(legal['td_admission_ratified'], [])

    def test_authorized_actual_acquisition_earns_more_credit_for_expansion(self):
        success = {e.key:e.value for e in load(ROOT/'mod/common/static_modifiers/td_success_modifiers.txt')}
        for doctrine, amount in RULES['territorial_success']['acquisition_legitimacy'].items():
            runner = acquired(doctrine)
            in_state(runner, 'td_process_acquisition_effect')
            if amount:
                self.assertIn('td_success_'+doctrine, runner.modifiers)
                self.assertEqual(float(success['td_success_'+doctrine][0].value), amount)
                self.assertEqual(runner.variables['td_success_state'], 'A')
            else:
                self.assertFalse(any(m.startswith('td_success_') for m in runner.modifiers))
        self.assertGreater(RULES['territorial_success']['acquisition_legitimacy']['imperial_expansion'],
                           RULES['territorial_success']['acquisition_legitimacy']['historical_rights'])

    def test_claims_declarations_unapproved_targets_and_expired_claims_earn_no_credit(self):
        for authorized, claim_valid in ((False, False), (True, False), (False, True)):
            runner = acquired(authorized=authorized)
            runner.claims = {'A'} if claim_valid else set()
            in_state(runner, 'td_process_acquisition_effect')
            self.assertNotIn('td_success_imperial_expansion', runner.modifiers)
        runner = acquired()
        runner.states['A']['variables'].pop('td_acquired_owner')
        in_state(runner, 'td_process_acquisition_effect')
        self.assertFalse(runner.modifiers)
        runner = acquired()
        runner.lists['td_renounced_regions'] = {'STATE_GUANGDONG'}
        in_state(runner, 'td_process_acquisition_effect')
        self.assertFalse(runner.modifiers)

    def test_success_neither_stacks_nor_renews_and_expires_in_36_months(self):
        runner = acquired()
        in_state(runner, 'td_process_acquisition_effect')
        expiration = runner.modifier_expirations[None, 'td_success_imperial_expansion']
        runner.day = 300
        runner.states['B']['variables'].update(td_acquired_owner='POR', td_original_owner='CHI')
        in_state(runner, 'td_process_acquisition_effect', 'B')
        self.assertEqual(runner.variables['td_success_state'], 'A')
        self.assertEqual(runner.modifier_expirations[None, 'td_success_imperial_expansion'], expiration)
        runner.day = expiration - 1
        runner.context()
        self.assertIn('td_success_imperial_expansion', runner.modifiers)
        runner.day = expiration
        runner.context()
        self.assertNotIn('td_success_imperial_expansion', runner.modifiers)
        self.assertNotIn('td_success_window', runner.variables)
        in_state(runner, 'td_process_acquisition_effect')
        self.assertNotIn('td_success_imperial_expansion', runner.modifiers)

    def test_losing_reward_state_revokes_credit_without_clearing_the_window(self):
        runner = acquired()
        in_state(runner, 'td_process_acquisition_effect')
        runner.previous_scope = 'B'
        runner.execute(runner.definitions['td_revoke_success_on_prev_state_effect'])
        self.assertIn('td_success_imperial_expansion', runner.modifiers)
        runner.previous_scope = 'A'
        runner.execute(runner.definitions['td_revoke_success_on_prev_state_effect'])
        self.assertNotIn('td_success_imperial_expansion', runner.modifiers)
        self.assertIn('td_success_window', runner.variables)
        self.assertNotIn('td_success_state', runner.variables)
        runner = acquired()
        in_state(runner, 'td_process_acquisition_effect')
        runner.states['A']['owner'] = 'CHI'
        runner.execute(runner.definitions['td_refresh_success_credit_effect'])
        self.assertNotIn('td_success_imperial_expansion', runner.modifiers)
        self.assertIn('td_success_window', runner.variables)
        # A deleted credited state is checked without needing its old owner scope.
        runner = acquired()
        in_state(runner, 'td_process_acquisition_effect')
        runner.variables['td_target'] = 'B'
        del runner.states['A']
        runner.execute(runner.definitions['td_refresh_success_credit_effect'])
        self.assertNotIn('td_success_imperial_expansion', runner.modifiers)
        self.assertIn('td_success_window', runner.variables)

    def test_acquisition_reactions_are_local_and_not_repeated_monthly(self):
        for doctrine, info in RULES['doctrines'].items():
            runner = acquired(doctrine)
            in_state(runner, 'td_process_acquisition_effect')
            expected = [('add_'+kind+'_in_state', share) for kind, share in info['acquisition_reaction'].items() if share]
            self.assertEqual(runner.states['A'].get('political_changes', []), expected)
            for _ in range(12):
                in_state(runner, 'td_process_acquisition_effect')
            self.assertEqual(runner.states['A'].get('political_changes', []), expected)
            self.assertNotIn('political_changes', runner.states['B'])

    def test_admission_relief_is_one_time_and_reason_sensitive(self):
        for reason, share in ((3,.03),(4,.02)):
            runner = acquired()
            runner.variables['td_reason'] = reason
            runner.states['A']['variables']['td_admitted_owner'] = 'POR'
            in_state(runner, 'td_admission_reaction_effect')
            in_state(runner, 'td_admission_reaction_effect')
            self.assertEqual(runner.states['A']['political_changes'],
                             [('add_radicals_in_state',-share),('add_loyalists_in_state',share)])
            self.assertNotIn('political_changes', runner.states['B'])

    def test_disabled_feature_and_ports_have_no_reactions_or_rewards(self):
        for disabled, port in ((True,False),(False,True)):
            runner = acquired()
            if disabled:
                runner.globals.clear()
            runner.states['A']['treaty_port'] = port
            in_state(runner, 'td_process_acquisition_effect')
            in_state(runner, 'td_refresh_state_development_effect')
            self.assertFalse(runner.modifiers)
            self.assertNotIn('political_changes', runner.states['A'])
            self.assertNotIn('td_territory_imperial_expansion', runner.states['A']['modifiers'])

    def test_completed_amendment_grants_credit_only_after_actual_one_year(self):
        runner = acquired('status_quo')
        runner.states['A']['variables']['td_admitted_owner'] = 'POR'
        runner.execute(runner.definitions['td_start_fast_effect'])
        runner.run_until(364)
        self.assertNotIn('td_success_admission', runner.modifiers)
        runner.run_until(365)
        self.assertIn('td_success_admission', runner.modifiers)
        self.assertEqual(runner.variables['td_success_state'], 'A')
        self.assertTrue(runner.states['A']['incorporated'])
        self.assertFalse(runner.states['B']['incorporated'])

    def test_documented_reward_names_and_no_countrywide_population_effects(self):
        effects = load(ROOT/'mod/common/scripted_effects/td_success.txt')
        self.assertFalse(any(e.key in ('add_radicals','add_loyalists') for e in walk(effects)))
        names = [e.key for e in load(ROOT/'mod/common/static_modifiers/td_success_modifiers.txt')]
        for language in ('english','simp_chinese'):
            loc = localization(language, 'td_laws')
            for name in names:
                self.assertIn(name, loc)


if __name__ == '__main__':
    unittest.main()
