from dataclasses import replace
from itertools import product
import unittest

from territorial_doctrine.model import (Bill, BillStatus, Conditions, Integration,
    Target, final_probability, group_scores, integration_cost, political_forces,
    political_weight, round_probability)


class PoliticsTests(unittest.TestCase):
    def test_weight_boundaries(self):
        for score, weight in [(-20, -1), (-19, -.5), (-5, -.5), (-4, 0),
                              (4, 0), (5, .5), (19, .5), (20, 1)]:
            with self.subTest(score=score):
                self.assertEqual(political_weight(score), weight)

    def test_weighted_clout_is_not_flat_probability_bonus(self):
        self.assertEqual(political_forces({'a': 20, 'b': -5, 'c': 0},
                                         {'a': 40, 'b': 30, 'c': 30}), (40, 15))

    def test_claim_and_admission_are_distinct(self):
        claim = group_scores('strategic_frontiers', security=True)
        admit = group_scores('strategic_frontiers', security=True, admission=True)
        self.assertEqual(claim['intelligentsia'], -10)
        self.assertEqual(admit['intelligentsia'], 5)

    def test_pledge_changes_a_group_score(self):
        scores = group_scores('strategic_frontiers', pledges=('industrialists',))
        self.assertEqual(scores['industrialists'], 20)
        self.assertEqual(scores['armed_forces'], 20)

    def test_duplicate_or_excessive_pledges_rejected(self):
        for pledges in [('devout', 'devout'), ('devout', 'industrialists', 'trade_unions')]:
            with self.assertRaises(ValueError):
                group_scores('status_quo', pledges=pledges)

    def test_prior_conversation_examples(self):
        self.assertAlmostEqual(round_probability(55, 20, legitimacy=50,
            monarch_supports=True, autocrat_supports=True), .5)
        self.assertAlmostEqual(round_probability(75, 20, legitimacy=75), .52)

    def test_probability_bounds_and_risk(self):
        self.assertEqual(round_probability(0, 100, legitimacy=0, at_war=True), .05)
        self.assertEqual(round_probability(100, 0, legitimacy=100,
            monarch_supports=True, autocrat_supports=True), .85)
        baseline = round_probability(55, 20, legitimacy=50)
        self.assertAlmostEqual(round_probability(55, 20, legitimacy=50,
            target_population_ratio=.2), baseline - .05)
        self.assertAlmostEqual(round_probability(55, 20, legitimacy=50,
            target_population_ratio=.5), baseline - .1)

    def test_clout_and_roll_validation(self):
        with self.assertRaises(ValueError):
            political_forces({'a': 20, 'b': 20}, {'a': 60, 'b': 60})
        with self.assertRaises(ValueError):
            round_probability(80, 80, legitimacy=50)

    def test_exact_eventual_probability(self):
        self.assertAlmostEqual(final_probability(.3), .16308)
        self.assertAlmostEqual(final_probability(.5), .5)
        self.assertAlmostEqual(final_probability(.7), .83692)


class TargetTests(unittest.TestCase):
    def test_status_quo_never_creates_claims(self):
        self.assertFalse(Target(1_000_000, adjacent=True, historical_registry=True).eligible('status_quo'))

    def test_history_requires_preexisting_basis(self):
        target = Target(1_000_000, adjacent=True, focus_ready=True)
        self.assertFalse(target.eligible('historical_rights'))
        self.assertTrue(replace(target, historical_registry=True).eligible('historical_rights'))

    def test_frontier_adjacent_or_focused_basis(self):
        target = Target(1_000_000, strategic_site=True)
        self.assertFalse(target.eligible('strategic_frontiers'))
        self.assertTrue(replace(target, focus_ready=True).eligible('strategic_frontiers'))
        self.assertTrue(replace(target, adjacent=True).eligible('strategic_frontiers'))

    def test_no_undiscovered_resource_claim(self):
        target = Target(1_000_000, focus_ready=True, resource_levels=5,
                        price_ratio=1.21, shortage_months=3)
        self.assertFalse(target.eligible('strategic_frontiers'))
        self.assertTrue(replace(target, discovered_resource=True).eligible('strategic_frontiers'))
        self.assertFalse(replace(target, discovered_resource=True, price_ratio=1.2).eligible('strategic_frontiers'))

    def test_compatriot_population_needs_both_thresholds(self):
        target = Target(1_000_000, focus_ready=True, compatriot_population=200_000)
        self.assertTrue(target.eligible('strategic_frontiers'))
        self.assertFalse(replace(target, compatriot_population=199_999).eligible('strategic_frontiers'))
        self.assertFalse(replace(target, population=100_000, compatriot_population=49_999).eligible('strategic_frontiers'))

    def test_imperial_and_foreign_target_requirements(self):
        target = Target(1_000_000, focus_ready=True)
        self.assertTrue(target.eligible('imperial_expansion'))
        self.assertFalse(replace(target, foreign=False).eligible('imperial_expansion'))
        self.assertFalse(replace(target, diplomatic_target=False).eligible('imperial_expansion'))


class BillTests(unittest.TestCase):
    def test_all_possible_round_sequences_terminate_by_five(self):
        passed = 0
        for results in product((False, True), repeat=5):
            bill = Bill()
            for index, success in enumerate(results, 1):
                bill.checkpoint(90 * index, .5, .1 if success else .9)
                if bill.status != BillStatus.ACTIVE:
                    break
            self.assertIn(bill.status, (BillStatus.PASSED, BillStatus.REJECTED))
            self.assertGreaterEqual(index, 3)
            passed += bill.status == BillStatus.PASSED
        self.assertEqual(passed, 16)

    def test_no_early_or_duplicate_checkpoint(self):
        bill = Bill()
        with self.assertRaises(ValueError):
            bill.checkpoint(89, .5, .1)
        bill.checkpoint(90, .5, .1)
        with self.assertRaises(ValueError):
            bill.checkpoint(90, .5, .1)

    def test_cancel_cools_down_and_old_queue_cannot_run(self):
        bill = Bill()
        bill.cancel(40)
        self.assertEqual(bill.cooldown_until, 770)
        with self.assertRaises(ValueError):
            bill.checkpoint(90, .5, .1)

    def test_failure_cooldown_and_terminal_guard(self):
        bill = Bill()
        for day in (90, 180, 270):
            bill.checkpoint(day, .5, .9)
        self.assertEqual(bill.cooldown_until, 1000)
        with self.assertRaises(ValueError):
            bill.cancel(271)


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.conditions = Conditions(True, True, 60, 0, .19, .09, .9, .8)

    def test_documented_costs_and_rounding(self):
        self.assertEqual(integration_cost(1_000_000, 'strategic_frontiers', fast=False), 50)
        self.assertEqual(integration_cost(1_000_000, 'strategic_frontiers', fast=True), 100)
        self.assertEqual(integration_cost(4_000_000, 'imperial_expansion', fast=True), 313)

    def test_every_condition_blocks(self):
        for field, value in [('sovereign_owner', False), ('admitted', False),
                             ('legitimacy', 59), ('bureaucracy_after_cost', -1),
                             ('turmoil', .2), ('devastation', .1),
                             ('market_access', .89), ('accepted_population_share', .79)]:
            with self.subTest(field=field):
                self.assertFalse(replace(self.conditions, **{field: value}).valid())

    def test_twelve_valid_months_and_pause(self):
        project = Integration()
        for _ in range(6):
            project.tick(self.conditions)
        project.tick(replace(self.conditions, turmoil=.3))
        self.assertEqual(project.months, 6)
        for _ in range(6):
            project.tick(self.conditions)
        self.assertEqual(project.status, 'incorporated')

    def test_consecutive_invalid_resets_after_valid_month(self):
        project = Integration()
        invalid = replace(self.conditions, market_access=.5)
        for _ in range(5):
            project.tick(invalid)
        project.tick(self.conditions)
        self.assertEqual(project.consecutive_invalid, 0)
        for _ in range(6):
            project.tick(invalid)
        self.assertEqual(project.status, 'regular')
        with self.assertRaises(ValueError):
            project.tick(self.conditions)

    def test_occupation_or_loss_cannot_complete_integration(self):
        project = Integration(months=11)
        self.assertEqual(project.tick(replace(self.conditions, sovereign_owner=False)), 'lost')


if __name__ == '__main__':
    unittest.main()
