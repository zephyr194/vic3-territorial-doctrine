from pathlib import Path
import random
import shutil
import tempfile
import unittest

from native_runner import EventRunner
from territorial_doctrine.model import ConstructionPledge, integration_cost, round_probability
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
            monarchy, autocracy, supportive, war, crisis = (rng.choice((False, True)) for _ in range(5))
            ratio = rng.choice((0, .199, .2, .499, .5, 1))
            context = {
                'var:td_support': support, 'var:td_opposition': opposition,
                'legitimacy': legitimacy, 'exists:ruler.interest_group': True,
                'ruler.interest_group.var:td_score': 5 if supportive else -5,
                'has_law:law_type:law_monarchy': monarchy,
                'has_law:law_type:law_autocracy': autocracy,
                'is_at_war': war, 'scaled_debt': .9 if crisis else .1,
                'var:td_population_ratio': ratio,
            }
            expected = round_probability(support, opposition, legitimacy=legitimacy,
                monarch_supports=monarchy and supportive, autocrat_supports=autocracy and supportive,
                fiscal_crisis=crisis, at_war=war, target_population_ratio=ratio)
            self.assertAlmostEqual(formula('td_success_probability', context, self.definitions) / 100, expected)

    def test_native_cost_matches_reference(self):
        for doctrine in ('status_quo', 'historical_rights', 'strategic_frontiers', 'imperial_expansion'):
            for population in (1, 999_999, 1_000_000, 4_000_000, 4_000_001):
                context = {'s:STATE_AL_RIF.region_state:SPA.state_population': population}
                context.update({f'has_law:law_type:law_td_{d}': d == doctrine for d in
                                ('status_quo', 'historical_rights', 'strategic_frontiers', 'imperial_expansion')})
                for fast in (False, True):
                    self.assertEqual(formula('td_fast_project_cost' if fast else 'td_regular_project_cost', context, self.definitions),
                                     integration_cost(population, doctrine, fast=fast))

    def test_active_fast_cost_is_not_double_counted(self):
        context = {'s:STATE_AL_RIF.region_state:SPA.state_population': 1_000_000,
                   'has_variable:td_fast': True}
        context.update({f'has_law:law_type:law_td_{d}': d == 'strategic_frontiers' for d in
                       ('status_quo', 'historical_rights', 'strategic_frontiers', 'imperial_expansion')})
        self.assertEqual(formula('td_unpaid_project_cost', context, self.definitions), 0)


class NativeEventTests(unittest.TestCase):
    def test_claim_and_admission_are_separate_and_charge_once(self):
        runner = EventRunner((.1, .8, .2, .7, .3, .1, .1, .1))
        runner.variables['td_bill'] = 1
        runner.execute(runner.definitions['td_start_bill_effect'])
        self.assertEqual(runner.queue[0][0], 90)
        for _ in range(5):
            runner.next_event()
        self.assertTrue(runner.claimed)
        self.assertNotIn('td_admitted', runner.variables)
        self.assertNotIn('td_bill', runner.variables)
        self.assertEqual(runner.variables['infamy'], 2)
        self.assertFalse(runner.queue)
        runner.variables['td_bill'] = 2
        runner.execute(runner.definitions['td_start_bill_effect'])
        for _ in range(3):
            runner.next_event()
        self.assertIn('td_admitted', runner.variables)
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
