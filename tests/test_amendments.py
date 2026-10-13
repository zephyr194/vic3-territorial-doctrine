"""Individual legal deadlines and doctrine development isolation regressions."""
from copy import deepcopy
from pathlib import Path
import unittest

from native_runner import EventRunner, policy_context
from territorial_doctrine.model import RULES, claim_infamy
from territorial_doctrine.script import load, parse
from tools.law_text import TERRITORY_EFFECTS, INDUSTRY_EFFECTS
from test_law_effects import localization

ROOT = Path(__file__).resolve().parents[1]


class AdmissionAmendmentTests(unittest.TestCase):
    def portuguese_split_state(self, rolls=(.1,.1,.1)):
        runner = EventRunner(rolls, country='POR')
        runner.inputs.clear()  # Exercise real eligibility/ownership predicates.
        runner.variables.update(td_bill=2, td_pending_bill=2, td_reason=4, td_accepted_share=0)
        runner.states['A'].update(state_region='STATE_GUANGDONG', turmoil=.8, devastation=.5)
        runner.states['B'].update(owner='CHI', state_region='STATE_GUANGDONG')
        runner.states['C'] = deepcopy(runner.states['A'])
        runner.states['C']['state_region'] = 'STATE_ANGOLA'
        runner.execute(runner.definitions['td_start_bill_effect'])
        return runner

    def test_portugal_ratifies_only_western_guangdong_and_completes_one_year(self):
        runner = self.portuguese_split_state()
        runner.run_until(270)
        self.assertEqual(runner.states['A']['variables']['td_admitted_owner'], 'POR')
        self.assertIn('td_admission_ratified', runner.states['A']['modifiers'])
        self.assertIn('td_annual_integration', runner.states['A']['modifiers'])
        self.assertEqual(runner.variables['td_project_target'], 'A')
        for other in ('B','C'):
            self.assertNotIn('td_admitted_owner', runner.states[other]['variables'])
            self.assertIn('td_requires_admission', runner.states[other]['modifiers'])
        runner.run_until(634)
        self.assertFalse(runner.states['A']['incorporated'])
        runner.run_until(635)
        self.assertTrue(runner.states['A']['incorporated'])
        self.assertFalse(runner.states['B']['incorporated'])
        self.assertFalse(runner.states['C']['incorporated'])
        self.assertEqual(runner.states['B']['owner'], 'CHI')
        self.assertFalse(runner.states['A']['homeland'])  # Legal integration does not rewrite culture.
        self.assertNotIn('td_annual_integration', runner.states['A']['modifiers'])
        self.assertNotIn('td_project_cost', runner.modifiers)

    def test_low_budget_keeps_only_selected_amendment_ratified_until_funded(self):
        runner = self.portuguese_split_state()
        runner.bureaucracy = 0
        runner.run_until(270)
        self.assertIn('td_admission_ratified', runner.states['A']['modifiers'])
        self.assertIn('td_requires_admission', runner.states['A']['modifiers'])
        self.assertNotIn('td_fast', runner.variables)
        self.assertFalse(runner.queue)
        runner.bureaucracy = 1000
        runner.execute(runner.definitions['td_start_fast_effect'])
        runner.run_until(635)
        self.assertTrue(runner.states['A']['incorporated'])

    def test_bill_target_snapshot_prevents_retargeting_another_state(self):
        runner = self.portuguese_split_state()
        runner.variables['td_target'] = 'C'  # A stale external UI/script changed the preview.
        runner.run_until(270)
        self.assertEqual(runner.variables['td_project_target'], 'A')
        self.assertNotIn('td_admitted_owner', runner.states['C']['variables'])

    def test_losing_ownership_during_review_cannot_ratify_foreign_land(self):
        runner = self.portuguese_split_state()
        runner.states['A']['owner'] = 'CHI'
        runner.run_until(90)
        self.assertNotIn('td_admitted_owner', runner.states['A']['variables'])
        self.assertNotIn('td_fast', runner.variables)
        self.assertIn('td_bill_cooldown', runner.variables)

    def test_losing_a_funded_state_cancels_its_timer_and_releases_cost(self):
        runner = self.portuguese_split_state()
        runner.run_until(270)
        runner.states['A']['owner'] = 'CHI'
        runner.run_until(635)
        self.assertFalse(runner.states['A']['incorporated'])
        self.assertNotIn('td_fast', runner.variables)
        self.assertNotIn('td_project_cost', runner.modifiers)

    def test_later_cultural_home_status_does_not_extend_legal_deadline(self):
        runner = self.portuguese_split_state()
        runner.run_until(270)
        runner.states['A']['homeland'] = True
        runner.run_until(635)
        self.assertTrue(runner.states['A']['incorporated'])

    def test_repeated_start_cannot_charge_again_or_restart_the_clock(self):
        runner = self.portuguese_split_state()
        runner.run_until(270)
        queue = deepcopy(runner.queue)
        generation = runner.variables['td_generation']
        runner.execute(runner.definitions['td_start_fast_effect'])
        self.assertEqual(runner.queue, queue)
        self.assertEqual(runner.variables['td_generation'], generation)

    def test_saved_project_keeps_its_original_state_and_anniversary(self):
        runner = self.portuguese_split_state()
        runner.run_until(450)
        restored = deepcopy(runner)
        restored.bureaucracy = -100
        restored.run_until(635)
        self.assertTrue(restored.states['A']['incorporated'])
        self.assertFalse(restored.states['C']['incorporated'])

    def test_old_bill_timer_cannot_vote_on_a_new_state_amendment(self):
        runner = self.portuguese_split_state()
        runner.run_until(90)
        runner.execute(runner.definitions['td_cancel_bill_effect'])
        # Simulate a later script-authorized restart while an old timer remains.
        runner.variables.update(td_bill=2,td_pending_bill=2,td_reason=4,td_target='C')
        runner.execute(runner.definitions['td_start_bill_effect'])
        runner.run_until(180)
        self.assertEqual(runner.variables['td_successes'],1)
        self.assertEqual(runner.variables['td_bill_target'],'C')
        self.assertNotIn('td_admitted_owner',runner.states['A']['variables'])

    def test_treaty_port_requires_ordinary_territorial_sovereignty_first(self):
        runner = self.portuguese_split_state()
        runner.states['A']['treaty_port'] = True
        runner.run_until(270)
        self.assertNotIn('td_admitted_owner',runner.states['A']['variables'])
        self.assertNotIn('td_fast',runner.variables)

    def test_review_journal_and_ratification_title_name_the_individual_state(self):
        for language in ('english','simp_chinese'):
            loc = localization(language,'td_gameplay')
            self.assertIn("Var('td_bill_target').GetState.GetName", loc['je_td_admission_amendment'])
            self.assertIn("Var('td_target').GetState.GetName", loc['td.30.t'])
            self.assertIn("SCOPE.sState('td_notice_target')", loc['td.12.t'])


class DevelopmentTests(unittest.TestCase):
    def test_legacy_state_packages_are_removed_from_all_owned_states(self):
        runner=EventRunner(country='POR')
        for state in runner.states.values():
            state['modifiers']['td_territory_imperial_expansion']=1
            state['variables']['td_development_profile']=4
        runner.execute(parse('every_scope_state = { td_refresh_state_development_effect = yes }'))
        for state in runner.states.values():
            self.assertNotIn('td_territory_imperial_expansion',state['modifiers'])
            self.assertNotIn('td_development_profile',state['variables'])

    def test_acquisition_and_admission_do_not_create_population_changes(self):
        runner=EventRunner(country='POR')
        runner.execute(parse('every_scope_state = { td_process_acquisition_effect = yes td_admission_reaction_effect = yes }'))
        self.assertTrue(all('political_changes' not in s for s in runner.states.values()))

    def test_old_package_definitions_have_no_effects(self):
        for e in load(ROOT/'mod/common/static_modifiers/td_territory_modifiers.txt'):
            self.assertEqual(e.value,[])


if __name__ == '__main__':unittest.main()
