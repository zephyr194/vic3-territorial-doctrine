"""Reported 1.13 engine errors, with explicit block-trigger fixtures."""
from pathlib import Path
import shutil
import tempfile
import unittest

from native_runner import EventRunner
from test_plan_delivery import GeographyRunner
from territorial_doctrine.script import load, parse
from tools.generate import outputs
from tools.validate import validate

ROOT = Path(__file__).resolve().parents[1]


class CountingRunner(EventRunner):
    def __init__(self):
        super().__init__()
        self.building_queries = 0

    def check(self, entries):
        self.building_queries += sum(e.key == 'state_has_building_type_levels' for e in entries)
        return super().check(entries)


class Engine113SyntaxTests(unittest.TestCase):
    def test_accounts_decision_reaches_file_local_namespaced_event(self):
        tree = load(ROOT/'mod/events/td_civic_events.txt')
        self.assertEqual((tree[0].key, tree[0].value), ('namespace', 'td'))
        r = EventRunner()
        r.globals['td_fiscal_enabled'] = 1
        decision = r.definitions['td_civic_accounts']
        r.execute(next(e.value for e in decision if e.key == 'when_taken'))
        self.assertEqual(r.notifications[-1], 'td.40')
        self.assertIn('td_weekly_balance', r.variables)

    def test_baseline_snapshot_is_exact_and_logarithmic_for_both_buildings(self):
        for kind, building in (('navy', 'naval_base'), ('railway', 'railway')):
            for levels in (0, 1, 2, 3, 7, 8, 9, 999, 1000, 1001, 4096, 2_000_000):
                with self.subTest(kind=kind, levels=levels):
                    r = CountingRunner()
                    r.variables.update({f'td_{kind}_target': 'A', 'td_target': 'B'})
                    r.states['A']['buildings'] = {building: levels}
                    r.states['B']['buildings'] = {building: levels + 100}
                    r.execute(r.definitions[f'td_snapshot_{kind}_baseline_effect'])
                    self.assertEqual(r.variables[f'td_{kind}_baseline'], levels)
                    self.assertNotIn(f'td_{kind}_probe', r.variables)
                    self.assertNotIn(f'td_{kind}_candidate', r.variables)
                    self.assertLessEqual(r.building_queries, 2 * levels.bit_length() + 2)
                    self.assertEqual(r.variables['td_target'], 'B')

    def test_missing_snapshot_target_never_replaces_cached_baseline(self):
        r = EventRunner()
        r.variables['td_navy_baseline'] = 12
        r.execute(r.definitions['td_snapshot_navy_baseline_effect'])
        self.assertEqual(r.variables['td_navy_baseline'], 12)

    def test_block_building_trigger_checks_the_scoped_state_and_strict_growth(self):
        r = EventRunner()
        r.variables['td_navy_baseline'] = 10
        r.states['A']['buildings'] = {'naval_base': 10}
        r.states['B']['buildings'] = {'naval_base': 99}
        condition = parse('var:td_target = { state_has_building_type_levels = { target = bt:building_naval_base value > root.var:td_navy_baseline } }')
        self.assertFalse(r.check(condition))
        r.states['A']['buildings']['naval_base'] = 11
        self.assertTrue(r.check(condition))
        r.states['A']['buildings']['naval_base'] = 9
        self.assertFalse(r.check(condition))

    def test_effect_if_is_rejected_in_fixture_trigger_evaluation(self):
        with self.assertRaisesRegex(AssertionError, 'trigger_if'):
            EventRunner().check(parse('if = { limit = { is_player = yes } bureaucracy > 0 }'))

    def test_focus_conditional_trigger_enforces_only_the_current_law_cost(self):
        r = GeographyRunner()
        r.variables.update(td_pending_bill=1, td_target='A')
        for doctrine, bureaucracy, authority in (('historical_rights', 25, 0),
                                                ('strategic_frontiers', 50, 25),
                                                ('imperial_expansion', 75, 50)):
            for name in ('status_quo', 'historical_rights', 'strategic_frontiers', 'imperial_expansion'):
                r.policy['has_law:law_type:law_td_'+name] = name == doctrine
            # GeographyRunner supplies engine interests. Numeric authority is an
            # explicit fixture; the emitted trigger_if blocks execute unchanged.
            condition = r.definitions['td_can_designate_focus_trigger']
            original = r.context
            r.context = lambda: {**original(), 'authority': authority}
            r.bureaucracy = bureaucracy
            self.assertTrue(r.check(condition), doctrine)
            r.bureaucracy = bureaucracy - 1
            self.assertFalse(r.check(condition), doctrine)
            r.bureaucracy = bureaucracy
            if authority:
                r.context = lambda: {**original(), 'authority': authority - 1}
                self.assertFalse(r.check(condition), doctrine)
            r.context = original

    def test_declared_bankruptcy_blocks_legislation_and_both_tax_actions(self):
        r = EventRunner()
        r.globals['td_fiscal_enabled'] = 1
        original = r.context
        r.context = lambda: {**original(), 'has_modifier:declared_bankruptcy': True}
        self.assertFalse(r.check(r.definitions['td_can_legislate_trigger']))
        for name, balance in (('td_can_raise_budget_tax_trigger', -100), ('td_can_lower_budget_tax_trigger', 100)):
            r.weekly_balance = balance
            self.assertFalse(r.check(r.definitions[name]))
        r.context = original
        self.assertTrue(r.check(r.definitions['td_can_legislate_trigger']))

    def test_census_voting_classifies_the_actor_as_democratic(self):
        from territorial_doctrine.script import formula
        r = EventRunner()
        r.policy['has_law:law_type:law_census_voting'] = True
        self.assertEqual(formula('td_power_category', r.context(), r.values), 2)

    def test_all_scripts_keep_bom_through_regeneration(self):
        generated = outputs()
        for p in (ROOT/'mod').rglob('*.txt'):
            self.assertTrue(p.read_bytes().startswith(b'\xef\xbb\xbf'), str(p))
            self.assertTrue(generated[p].startswith(b'\xef\xbb\xbf'), str(p))
            self.assertEqual(generated[p], p.read_bytes())

    def test_validator_rejects_every_reported_syntax_regression(self):
        cases = (
            ('events/td_civic_events.txt', 'namespace = td', '', 'needs namespace'),
            ('common/scripted_triggers/td_triggers.txt', 'trigger_if =', 'if =', 'effect-style if/else'),
            ('common/scripted_triggers/td_triggers.txt', 'declared_bankruptcy', 'country_bankruptcy', 'obsolete engine identifier'),
            ('common/static_modifiers/td_modifiers.txt', 'state_disallow_incorporation_bool', 'state_disallow_incorporation', 'obsolete engine identifier'),
            ('common/script_values/td_policy_values.txt', 'law_census_voting', 'law_census_suffrage', 'obsolete engine identifier'),
            ('common/scripted_effects/td_bargaining.txt', 'state_has_building_type_levels = { target = bt:building_naval_base value > root.var:td_navy_baseline }', 'state_has_building_type_levels:bt:building_naval_base > root.var:td_navy_baseline', 'block trigger'),
        )
        with tempfile.TemporaryDirectory() as tmp:
            mod = Path(tmp)/'mod'
            shutil.copytree(ROOT/'mod', mod)
            for filename, before, after, expected in cases:
                with self.subTest(filename=filename, defect=after):
                    path = mod/filename
                    original = path.read_text(encoding='utf-8-sig')
                    self.assertIn(before, original)
                    path.write_text(original.replace(before, after, 1), encoding='utf-8-sig')
                    self.assertTrue(any(expected in error for error in validate(mod)))
                    path.write_text(original, encoding='utf-8-sig')

    def test_validator_rejects_numeric_building_links_and_missing_script_bom(self):
        with tempfile.TemporaryDirectory() as tmp:
            mod = Path(tmp)/'mod'
            shutil.copytree(ROOT/'mod', mod)
            path = mod/'common/scripted_effects/td_regression.txt'
            path.write_text('td_regression = { set_variable = { name = td_number value = var:td_bill_target.state_has_building_type_levels:bt:building_railway } }', encoding='utf-8')
            errors = validate(mod)
            self.assertTrue(any('script must have UTF-8 BOM' in error for error in errors))
            self.assertTrue(any('block trigger, not a numeric/event-target link' in error for error in errors))


if __name__ == '__main__':
    unittest.main()
