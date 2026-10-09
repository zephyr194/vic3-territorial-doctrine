from dataclasses import replace
from itertools import product
import unittest

from territorial_doctrine.model import (Bill, BillStatus, Conditions, Integration,
    Target, final_probability, group_scores, integration_cost, political_forces,
    political_weight, round_probability, reason_bonus, claim_infamy,
    OwnedTerritory, TerritorialAgenda, LostTerritory, RULES)


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

    def test_common_base_and_reason_example(self):
        self.assertAlmostEqual(round_probability(55, 20, legitimacy=50,
            reason='security', government='monarchy', power='autocracy'), .42)
        self.assertAlmostEqual(round_probability(55, 20, legitimacy=50), .35)
        self.assertAlmostEqual(round_probability(75, 20, legitimacy=75), .52)

    def test_every_structure_has_the_same_starting_rate(self):
        for government, power in product(('monarchy', 'republic', 'other'), RULES['regimes']):
            self.assertEqual(round_probability(0, 0, legitimacy=50,
                government=government, power=power), .10)

    def test_reason_fit_changes_sign(self):
        self.assertEqual(reason_bonus('security', 'monarchy', 'autocracy'), 7)
        self.assertEqual(reason_bonus('security', 'republic', 'democracy'), -2)
        self.assertEqual(reason_bonus('equal_rights', 'monarchy', 'autocracy'), -7)
        self.assertEqual(reason_bonus('equal_rights', 'republic', 'democracy'), 8)

    def test_renunciation_has_distinct_politics(self):
        normal = group_scores('historical_rights')
        waived = group_scores('historical_rights', renunciation=True)
        self.assertEqual(waived['armed_forces'], normal['armed_forces'] - 20)
        self.assertEqual(waived['intelligentsia'], normal['intelligentsia'] + 10)

    def test_probability_bounds_and_risk(self):
        self.assertEqual(round_probability(0, 100, legitimacy=0, at_war=True), .05)
        self.assertEqual(round_probability(100, 0, legitimacy=100,
            reason='equal_rights', government='republic', power='democracy'), .85)
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


class IndividualTerritoryTests(unittest.TestCase):
    def test_each_state_requires_its_own_bill(self):
        a, b = OwnedTerritory('A', 'SPA'), OwnedTerritory('B', 'SPA')
        agenda = TerritorialAgenda('SPA')
        agenda.start(a, 0)
        with self.assertRaises(ValueError):
            agenda.start(b, 1)
        with self.assertRaises(ValueError):
            agenda.resolve(b, passed=True, day=270, reason='civil_administration')
        agenda.resolve(a, passed=True, day=270, reason='civil_administration')
        self.assertFalse(a.needs_admission('SPA'))
        self.assertTrue(b.needs_admission('SPA'))
        agenda.start(b, 271)
        agenda.resolve(b, passed=True, day=541, reason='equal_rights')
        self.assertEqual(b.reason, 'equal_rights')

    def test_foreign_occupation_homeland_and_treaty_port_are_excluded(self):
        for state in (OwnedTerritory('A', 'MOR'), OwnedTerritory('A', 'SPA', homeland=True),
                      OwnedTerritory('A', 'SPA', treaty_port=True),
                      OwnedTerritory('A', 'SPA', incorporated=True)):
            self.assertFalse(state.needs_admission('SPA'))

    def test_owner_change_invalidates_admission_even_after_reacquisition(self):
        state = OwnedTerritory('A', 'SPA', admitted_owner='SPA', incorporated=True)
        state.transfer('FRA', 'autocracy')
        self.assertTrue(state.needs_admission('FRA'))
        self.assertFalse(state.incorporated)
        self.assertEqual(state.source_power, 'autocracy')
        state.transfer('SPA', 'democracy')
        self.assertTrue(state.needs_admission('SPA'))
        self.assertIsNone(state.admitted_owner)
        self.assertEqual(state.source_power, 'democracy')

    def test_loss_during_bill_cannot_approve_foreign_state(self):
        state = OwnedTerritory('A', 'SPA')
        agenda = TerritorialAgenda('SPA')
        agenda.start(state, 0)
        state.transfer('FRA', 'autocracy')
        agenda.resolve(state, passed=True, day=90, reason='civil_administration')
        self.assertIsNone(state.admitted_owner)
        self.assertEqual(agenda.cooldown_until, 820)

    def test_waive_lost_homeland_claim_keeps_culture_and_owner(self):
        lost = LostTerritory('Outer Manchuria', 'RUS', 'CHI', homeland=True, claimed=True)
        other = LostTerritory('Other region', 'RUS', 'CHI', homeland=True, claimed=True)
        lost.renounce()
        self.assertTrue(lost.homeland)
        self.assertEqual(lost.owner, 'RUS')
        self.assertFalse(lost.claimed)
        self.assertFalse(lost.eligible())
        self.assertTrue(other.claimed)
        self.assertTrue(other.eligible())
        for doctrine in RULES['doctrines']:
            self.assertFalse(Target(1_000_000, focus_ready=True, primary_homeland=True,
                                    adjacent=True, renounced=True).eligible(doctrine))
        with self.assertRaises(ValueError):
            lost.renounce()

    def test_only_foreign_lost_claim_or_homeland_can_be_waived(self):
        self.assertTrue(LostTerritory('A', 'RUS', 'CHI', homeland=True).eligible())
        self.assertFalse(LostTerritory('A', 'CHI', 'CHI', claimed=True).eligible())
        self.assertFalse(LostTerritory('A', 'RUS', 'CHI').eligible())

    def test_target_regime_and_local_conditions_change_cost(self):
        self.assertEqual(claim_infamy('strategic_frontiers', 'security', 'autocracy'), 2)
        self.assertEqual(claim_infamy('strategic_frontiers', 'security', 'democracy'), 3)
        neutral = integration_cost(1_000_000, 'strategic_frontiers', fast=False)
        inherited = integration_cost(1_000_000, 'strategic_frontiers', fast=False, source_power='autocracy')
        damaged = integration_cost(1_000_000, 'strategic_frontiers', fast=False, turmoil=.5,
                                   devastation=.5, accepted_share=.5)
        self.assertGreater(inherited, neutral)
        self.assertGreater(damaged, inherited)
        with self.assertRaises(ValueError):
            integration_cost(1, 'status_quo', fast=False, accepted_share=1.1)


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
