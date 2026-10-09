from pathlib import Path
import random
import shutil
import tempfile
import unittest

from native_runner import EventRunner, policy_context
from territorial_doctrine.model import ConstructionPledge, integration_cost, round_probability, claim_infamy, RULES
from territorial_doctrine.script import formula, load, parse
from tools.generate import outputs
from tools.validate import validate

ROOT = Path(__file__).resolve().parents[1]


class NativeFormulaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.definitions = {e.key: e.value for p in (ROOT / 'mod/common/script_values').glob('*.txt') for e in load(p)}

    def test_native_probability_matches_reference_for_500_cases(self):
        rng = random.Random(113)
        for _ in range(500):
            support = rng.uniform(0, 100)
            opposition = rng.uniform(0, 100 - support)
            legitimacy = rng.uniform(0, 100)
            government = rng.choice(('monarchy', 'republic', 'other'))
            power = rng.choice(tuple(RULES['regimes']))
            reason = rng.choice((None, *RULES['reasons']))
            war, crisis = rng.choice((False, True)), rng.choice((False, True))
            ratio = rng.choice((0, .199, .2, .499, .5, 1))
            context = policy_context(government, power, reason=reason)
            context.update({'var:td_support': support, 'var:td_opposition': opposition,
                'legitimacy': legitimacy, 'is_at_war': war, 'scaled_debt': .9 if crisis else .1,
                'var:td_population_ratio': ratio})
            expected = round_probability(support, opposition, legitimacy=legitimacy,
                reason=reason, government=government, power=power,
                fiscal_crisis=crisis, at_war=war, target_population_ratio=ratio)
            self.assertAlmostEqual(formula('td_success_probability', context, self.definitions) / 100, expected)

    def test_native_cost_matches_reference(self):
        rng = random.Random(313)
        for _ in range(500):
            doctrine = rng.choice(tuple(RULES['doctrines']))
            population = rng.choice((1, 999_999, 1_000_000, 4_000_000, 4_000_001))
            actor, source = (rng.choice(tuple(RULES['regimes'])) for _ in range(2))
            reason = rng.choice((None, *RULES['reasons']))
            turmoil, devastation, accepted = (rng.random() for _ in range(3))
            context = policy_context(power=actor, doctrine=doctrine, reason=reason)
            context.update({'var:td_target.state_population': population,
                'var:td_target.var:td_source_administration': RULES['regimes'][source]['inherited_administration_multiplier'],
                'var:td_target.turmoil': turmoil, 'var:td_target.devastation': devastation,
                'var:td_accepted_share': accepted})
            for fast in (False, True):
                self.assertEqual(formula('td_fast_project_cost' if fast else 'td_regular_project_cost', context, self.definitions),
                    integration_cost(population, doctrine, fast=fast, reason=reason, actor_power=actor,
                                     source_power=source, turmoil=turmoil, devastation=devastation, accepted_share=accepted))

    def test_target_regime_changes_claim_cost_and_never_admission_infamy(self):
        for doctrine in RULES['doctrines']:
            for reason in RULES['reasons']:
                for target in RULES['regimes']:
                    context = policy_context(doctrine=doctrine, reason=reason)
                    context['var:td_target.var:td_live_diplomatic'] = RULES['regimes'][target]['diplomatic_multiplier']
                    context['var:td_bill'] = 1
                    self.assertEqual(formula('td_claim_infamy', context, self.definitions), claim_infamy(doctrine, reason, target))
                    for kind in (2, 3):
                        context['var:td_bill'] = kind
                        self.assertEqual(formula('td_claim_infamy', context, self.definitions), 0)

    def test_foreign_claim_forecast_uses_current_target_regime(self):
        context = policy_context()
        context.update({'var:td_target.var:td_source_administration': 1,
                        'var:td_target.var:td_live_administration': 1.15})
        self.assertEqual(formula('td_inherited_cost_multiplier', context, self.definitions), 1)
        context['var:td_pending_bill'] = 1
        self.assertEqual(formula('td_inherited_cost_multiplier', context, self.definitions), 1.15)

    def test_active_fast_cost_is_not_double_counted(self):
        context = policy_context()
        context.update({'var:td_target.state_population': 1_000_000, 'has_variable:td_fast': True,
                        'var:td_target.var:td_source_administration': 1,
                        'var:td_target.turmoil': 0, 'var:td_target.devastation': 0, 'var:td_accepted_share': 1})
        self.assertEqual(formula('td_unpaid_project_cost', context, self.definitions), 0)


class NativeEventTests(unittest.TestCase):
    def test_old_selection_menu_cannot_change_active_target(self):
        for flag in ('td_bill', 'td_fast', 'td_regular'):
            runner = EventRunner()
            runner.variables[flag] = 1
            for effect in ('td_select_owned_effect', 'td_select_lost_effect', 'td_select_admitted_effect'):
                runner.execute(runner.definitions[effect])
                self.assertEqual(runner.variables['td_target'], 'A')
                self.assertEqual(runner.variables['td_reason'], 1)

    def test_claim_and_admission_are_separate_and_charge_once(self):
        runner = EventRunner((.1, .8, .2, .7, .3, .1, .1, .1))
        runner.variables['td_bill'] = 1
        runner.execute(runner.definitions['td_start_bill_effect'])
        self.assertEqual(runner.queue[0][0], 90)
        for _ in range(5):
            runner.next_event()
        self.assertTrue(runner.claimed)
        self.assertNotIn('td_admitted_owner', runner.states['A']['variables'])
        self.assertNotIn('td_bill', runner.variables)
        self.assertEqual(runner.variables['infamy'], 2)
        self.assertFalse(runner.queue)
        runner.variables['td_bill'] = 2
        runner.execute(runner.definitions['td_start_bill_effect'])
        for _ in range(3):
            runner.next_event()
        self.assertEqual(runner.states['A']['variables']['td_admitted_owner'], 'SPA')
        self.assertNotIn('td_admitted_owner', runner.states['B']['variables'])
        self.assertIn('td_requires_admission', runner.states['B']['modifiers'])
        self.assertFalse(runner.incorporated)
        self.assertEqual(runner.variables['infamy'], 2)

    def test_cancelled_scheduled_round_does_not_restart(self):
        runner = EventRunner(())
        runner.variables['td_bill'] = 1
        runner.execute(runner.definitions['td_start_bill_effect'])
        runner.execute(runner.definitions['td_cancel_bill_effect'])
        runner.next_event()
        self.assertFalse(runner.queue)
        self.assertFalse(runner.claimed)
        self.assertEqual(runner.expirations['td_bill_cooldown'], 730)

    def test_rejection_drops_new_pledges_but_preserves_prior_obligations(self):
        runner = EventRunner((.9, .9, .9))
        runner.variables.update(td_bill=1, td_bill_pledge_navy=1, td_pending_railway=1)
        runner.execute(runner.definitions['td_start_bill_effect'])
        for _ in range(3):
            runner.next_event()
        self.assertNotIn('td_bill_pledge_navy', runner.variables)
        self.assertNotIn('td_pending_navy', runner.variables)
        self.assertIn('td_pending_railway', runner.variables)
        self.assertEqual(runner.expirations['td_bill_cooldown'], 270 + 730)

    def test_invalid_target_cancels_without_rng(self):
        runner = EventRunner(())
        runner.variables['td_bill'] = 1
        runner.inputs['td_bill_target_valid_trigger'] = False
        runner.execute(runner.definitions['td_start_bill_effect'])
        runner.next_event()
        self.assertIn('td_bill_cooldown', runner.variables)
        self.assertIn('td.14', runner.notifications)

    def test_integration_waits_twelve_checks_and_releases_cost(self):
        runner = EventRunner()
        runner.execute(runner.definitions['td_start_fast_effect'])
        self.assertEqual(runner.modifiers['td_project_cost'], 100)
        self.assertEqual(runner.queue[0][0], 30)
        for _ in range(11):
            runner.next_event()
            self.assertFalse(runner.incorporated)
        runner.next_event()
        self.assertTrue(runner.incorporated)
        self.assertNotIn('td_project_cost', runner.modifiers)
        self.assertFalse(runner.queue)

    def test_pause_resets_and_six_bad_months_fall_back(self):
        runner = EventRunner()
        runner.execute(runner.definitions['td_start_fast_effect'])
        runner.inputs['td_fast_ready_trigger'] = False
        for _ in range(5):
            runner.next_event()
        runner.inputs['td_fast_ready_trigger'] = True
        runner.next_event()
        self.assertEqual(runner.variables['td_invalid_months'], 0)
        runner.inputs['td_fast_ready_trigger'] = False
        for _ in range(6):
            runner.next_event()
        self.assertNotIn('td_fast', runner.variables)
        self.assertIn('td_regular', runner.variables)
        self.assertEqual(runner.modifiers['td_project_cost'], 50)
        self.assertFalse(runner.incorporated)
        self.assertFalse(runner.queue)

    def test_losing_target_releases_project_without_incorporation(self):
        runner = EventRunner()
        runner.execute(runner.definitions['td_start_fast_effect'])
        runner.inputs['td_admission_target_valid_trigger'] = False
        runner.next_event()
        self.assertNotIn('td_project_cost', runner.modifiers)
        self.assertNotIn('td_fast', runner.variables)
        self.assertFalse(runner.incorporated)

    def test_renunciation_only_removes_selected_claim(self):
        runner = EventRunner((.1, .1, .1))
        runner.claims.update(('A', 'B'))
        runner.variables.update(td_bill=3, td_reason=5)
        runner.execute(runner.definitions['td_start_bill_effect'])
        for _ in range(3):
            runner.next_event()
        self.assertEqual(runner.claims, {'B'})
        self.assertEqual(runner.lists['td_renounced_regions'], {'A'})
        self.assertNotIn('infamy', runner.variables)
        self.assertEqual(runner.states['A']['owner'], 'SPA')
        self.assertIn('td.19', runner.notifications)

    def test_second_state_integration_is_isolated(self):
        runner = EventRunner()
        runner.variables['td_target'] = 'B'
        runner.execute(runner.definitions['td_start_fast_effect'])
        for _ in range(12):
            runner.next_event()
        self.assertTrue(runner.states['B']['incorporated'])
        self.assertFalse(runner.states['A']['incorporated'])

    def test_old_project_timer_cannot_advance_new_project(self):
        runner = EventRunner()
        runner.execute(runner.definitions['td_start_fast_effect'])
        runner.execute(runner.definitions['td_end_project_effect'])
        runner.variables['td_target'] = 'B'
        runner.execute(runner.definitions['td_start_fast_effect'])
        runner.next_event()  # Timer saved for the old generation.
        self.assertEqual(runner.variables['td_valid_months'], 0)
        runner.next_event()  # New project gets its first month.
        self.assertEqual(runner.variables['td_valid_months'], 1)
        for _ in range(11):
            runner.next_event()
        self.assertFalse(runner.states['A']['incorporated'])
        self.assertTrue(runner.states['B']['incorporated'])


class PledgeTests(unittest.TestCase):
    def test_acquisition_starts_deadline_and_requires_new_building(self):
        pledge = ConstructionPledge('armed_forces')
        self.assertEqual(pledge.tick(0, owns_target=False, building_levels=9), 'awaiting_acquisition')
        self.assertEqual(pledge.tick(300, owns_target=True, building_levels=9), 'pending')
        self.assertEqual(pledge.deadline, 1395)
        self.assertEqual(pledge.tick(301, owns_target=True, building_levels=10), 'fulfilled')

    def test_loss_and_reacquisition_cannot_reset_deadline(self):
        pledge = ConstructionPledge('industrialists')
        pledge.tick(0, owns_target=True, building_levels=2)
        pledge.tick(100, owns_target=False, building_levels=0)
        pledge.tick(1000, owns_target=True, building_levels=2)
        self.assertEqual(pledge.deadline, 1095)
        self.assertEqual(pledge.tick(1095, owns_target=True, building_levels=3), 'broken')
        self.assertEqual(pledge.penalty_until, 2920)


class ValidatorTests(unittest.TestCase):
    def test_generated_assets_and_actual_mod(self):
        self.assertFalse(validate(ROOT / 'mod'))
        for path, expected in outputs().items():
            self.assertEqual(path.read_bytes(), expected, str(path))

    def test_unclosed_script_fails(self):
        with self.assertRaises(ValueError):
            parse('td_bad = { value = 1')

    def test_unlocalized_decision_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            mod = Path(tmp) / 'mod'
            shutil.copytree(ROOT / 'mod', mod)
            (mod / 'common/decisions/td_missing.txt').write_text('td_missing = { when_taken = { } }')
            self.assertTrue(any('missing localization td_missing' in e for e in validate(mod)))

    def test_unknown_custom_reference_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            mod = Path(tmp) / 'mod'
            shutil.copytree(ROOT / 'mod', mod)
            (mod / 'common/scripted_effects/td_bad.txt').write_text('td_bad = { td_unknown_effect = yes }')
            self.assertTrue(any('undefined custom name td_unknown_effect' in e for e in validate(mod)))


if __name__ == '__main__':
    unittest.main()
