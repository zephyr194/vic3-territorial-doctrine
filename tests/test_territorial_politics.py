"""Legacy economic and population incentives must not survive the new design."""
from pathlib import Path
import unittest
from native_runner import EventRunner
from territorial_doctrine.script import parse, load, walk

ROOT=Path(__file__).resolve().parents[1]

class TerritorialPoliticsTests(unittest.TestCase):
    def test_no_countrywide_rewards_or_state_bonuses_in_laws(self):
        for law in load(ROOT/'mod/common/laws/td_laws.txt'):
            self.assertEqual(next(e.value for e in law.value if e.key=='modifier'),[])

    def test_legacy_legitimacy_modifiers_are_cleared(self):
        r=EventRunner();r.modifiers['td_success_imperial_expansion']=1
        r.variables.update(td_success_window=1,td_success_state='A')
        r.execute(r.definitions['td_refresh_success_credit_effect'])
        self.assertFalse(r.modifiers)
        self.assertNotIn('td_success_window',r.variables)

    def test_original_territory_registry_is_not_overwritten_on_recovery(self):
        r=EventRunner(country='POR');r.execute(parse('every_state = { td_register_original_territory_effect = yes }'))
        r.states['A']['owner']='CHI'
        r.execute(parse('every_state = { td_register_original_territory_effect = yes }'))
        self.assertEqual(r.states['A']['variables']['td_original_owner'],'POR')

    def test_admission_still_records_only_one_state_without_population_rewards(self):
        r=EventRunner((.01,)*3,country='POR');r.variables.update(td_bill=2,td_reason=4)
        r.execute(r.definitions['td_start_bill_effect']);r.run_until(635)
        self.assertTrue(r.states['A']['incorporated'])
        self.assertFalse(r.states['B']['incorporated'])
        self.assertFalse(r.modifiers)
        self.assertTrue(all('political_changes' not in s for s in r.states.values()))

if __name__=='__main__':unittest.main()
