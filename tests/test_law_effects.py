"""Design regressions against the actual laws and text shipped to players."""
import json
from pathlib import Path
import unittest

from native_runner import EventRunner, policy_context
from territorial_doctrine.model import DOCTRINES, RULES
from territorial_doctrine.script import load
from tools.law_text import INDUSTRY_EFFECTS

ROOT = Path(__file__).resolve().parents[1]


def localization(language, filename):
    text = (ROOT / 'mod/localization' / language / f'{filename}_l_{language}.yml').read_text(encoding='utf-8-sig')
    return {line.strip().partition(':0 ')[0]: json.loads(line.partition(':0 ')[2])
            for line in text.splitlines()[1:] if ':0 ' in line}


class LawEffectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.laws = {law.key: law.value for law in load(ROOT / 'mod/common/laws/td_laws.txt')}
        cls.effects = {name: {effect.key: float(effect.value)
                             for effect in next(entry.value for entry in law if entry.key == 'modifier')}
                       for name, law in cls.laws.items()}

    def test_laws_provide_distinct_political_benefits_and_national_tradeoffs(self):
        effects = {d: self.effects['law_td_' + d] for d in DOCTRINES}
        self.assertEqual(effects['status_quo']['interest_group_ig_trade_unions_pol_str_mult'], .10)
        self.assertEqual(effects['status_quo']['country_bureaucracy_mult'], .05)
        self.assertLess(effects['status_quo']['country_prestige_mult'], 0)
        self.assertEqual(effects['historical_rights']['interest_group_ig_petty_bourgeoisie_pol_str_mult'], .15)
        self.assertEqual(effects['historical_rights']['country_authority_add'], 25)
        self.assertEqual(effects['strategic_frontiers']['interest_group_ig_armed_forces_pol_str_mult'], .15)
        self.assertEqual(effects['strategic_frontiers']['country_diplomatic_play_maneuvers_add'], 10)
        self.assertGreater(effects['strategic_frontiers']['country_military_goods_cost_mult'], 0)
        self.assertGreater(effects['imperial_expansion']['interest_group_ig_armed_forces_pol_str_mult'],
                           effects['strategic_frontiers']['interest_group_ig_armed_forces_pol_str_mult'])
        self.assertGreater(effects['imperial_expansion']['country_military_goods_cost_mult'],
                           effects['strategic_frontiers']['country_military_goods_cost_mult'])
        self.assertLess(effects['imperial_expansion']['country_bureaucracy_mult'], 0)
        self.assertEqual(len({tuple(sorted(e.items())) for e in effects.values()}), 4)

    def test_group_beneficiaries_follow_baseline_political_interests(self):
        for index, doctrine in enumerate(DOCTRINES):
            for key, value in self.effects['law_td_' + doctrine].items():
                if key.startswith('interest_group_ig_'):
                    group = key.removeprefix('interest_group_ig_').removesuffix('_pol_str_mult')
                    self.assertGreaterEqual(RULES['groups'][group][index] * value, 0)
                    self.assertLessEqual(abs(value), .20)  # Avoid overpowering other law groups.
        self.assertEqual(RULES['bill']['base_probability'], 10)

    def test_descriptions_report_each_enacted_effect_and_policy_scope(self):
        countries = {
            'country_bureaucracy_mult': ('行政力', 'Bureaucracy', 100),
            'country_prestige_mult': ('威望', 'Prestige', 100),
            'country_authority_add': ('权威力', 'Authority', 1),
            'country_diplomatic_play_maneuvers_add': ('外交博弈机动点', 'Diplomatic play maneuvers', 1),
            'country_military_goods_cost_mult': ('军事物资花费', 'Military goods cost', 100),
            'country_infamy_generation_mult': ('恶名产生', 'Infamy generation', 100),
            'country_infamy_decay_mult': ('恶名衰减', 'Infamy decay', 100),
            'country_legitimacy_base_add': ('基础合法性', 'Base legitimacy', 1),
        }
        for language, label in (('english', 'en'), ('simp_chinese', 'zh')):
            loc = localization(language, 'td_laws')
            descriptions = []
            for doctrine in DOCTRINES:
                description = loc['law_td_' + doctrine + '_desc']
                descriptions.append(description)
                self.assertIn(RULES['doctrines'][doctrine]['eligibility'][label], description)
                for key, value in self.effects['law_td_' + doctrine].items():
                    if key.startswith('interest_group_ig_'):
                        group = key.removeprefix('interest_group_ig_').removesuffix('_pol_str_mult')
                        name, scale = RULES['group_politics'][group][label], 100
                    elif key in INDUSTRY_EFFECTS:
                        zh, en = INDUSTRY_EFFECTS[key]
                        name, scale = (zh if label == 'zh' else en), 100
                    else:
                        zh, en, scale = countries[key]
                        name = zh if label == 'zh' else en
                    number = f'{value * scale:+g}' + ('%' if scale == 100 else '')
                    self.assertIn(name + ' ' + number, description)
            self.assertEqual(len(set(descriptions)), 4)
            for doctrine in DOCTRINES[1:]:
                self.assertNotIn('北非', loc['td_focus_' + doctrine])
                self.assertNotIn('North African', loc['td_focus_' + doctrine])

    def test_dynamic_group_text_matches_its_current_native_law_positions(self):
        ideologies = load(ROOT / 'mod/common/ideologies/td_colonial_ideologies.txt')
        wording = {
            'zh': {'strongly_approve': '强烈支持', 'approve': '支持', 'neutral': '中立',
                   'disapprove': '反对', 'strongly_disapprove': '强烈反对'},
            'en': {'strongly_approve': 'Strongly support', 'approve': 'Support', 'neutral': 'Neutral',
                   'disapprove': 'Oppose', 'strongly_disapprove': 'Strongly oppose'},
        }
        for language, label in (('english', 'en'), ('simp_chinese', 'zh')):
            loc = localization(language, 'td_policies')
            for ideology in ideologies:
                positions = next(e.value for e in ideology.value if e.key == 'lawgroup_territorial_doctrine')
                for position in positions:
                    name = RULES['doctrines'][position.key.removeprefix('law_td_')][label]
                    self.assertIn(name + ': ' + wording[label][position.value], loc[ideology.key + '_desc'])

    def test_disabled_cleanup_deactivates_legacy_laws_without_touching_vanilla(self):
        for doctrine in DOCTRINES:
            runner = EventRunner()
            runner.globals.clear()
            runner.policy.update(policy_context(government='monarchy', doctrine=doctrine))
            runner.execute(runner.definitions['td_disabled_cleanup_effect'])
            for law in DOCTRINES:
                self.assertFalse(runner.policy['has_law:law_type:law_td_' + law])
            self.assertTrue(runner.policy['has_law:law_type:law_monarchy'])
            epoch = runner.variables['td_focus_epoch']
            runner.execute(runner.definitions['td_disabled_cleanup_effect'])
            self.assertEqual(runner.variables['td_focus_epoch'], epoch)


if __name__ == '__main__':
    unittest.main()
