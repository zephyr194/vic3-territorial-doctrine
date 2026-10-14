"""Execute civic decisions/effects with explicit vanilla budget/institution data."""
from copy import deepcopy
from pathlib import Path
import re
import unittest

from test_bargaining import agenda, resolve
from test_plan_delivery import GeographyRunner, roundtrip
from territorial_doctrine.model import RULES
from territorial_doctrine.script import load, walk
from tools.generate import outputs
from tools.validate import validate

ROOT=Path(__file__).resolve().parents[1]


def enable(r, module):
    decision=r.definitions['td_enable_'+module+'_accounting']
    r.execute(next(e.value for e in decision if e.key=='when_taken'))


def observed(*, war=False, legitimacy=70):
    r=GeographyRunner(country='POR');r.real_politics=True;r.legitimacy=legitimacy
    r.institutions={'institution_schools':3,'institution_health_system':2}
    r.states['A']['owner']='POR'
    r.variables['td_expansion_program']=1;r.expirations['td_expansion_program']=1095
    r.at_war=war
    if war:
        r.wars={'W1':{'variables':{}}};r.attacker_warleaders={'W1':'POR'};r.participants={'W1':{'POR','ENEMY'}}
    return r


def rate(r, state='A'):
    mods=r.states[state]['modifiers']
    maximum=RULES['civic_accounting']['conscription_max_multiplier']
    return maximum*mods.get('td_conscription_high_trust',0)-maximum*mods.get('td_conscription_low_trust',0)


class CivicTests(unittest.TestCase):
    def test_modules_require_opt_in_doctrine(self):
        r=observed();r.globals.clear()
        for m in ('fiscal','recruitment','services'):enable(r,m)
        self.assertFalse(r.globals)
        self.assertFalse(r.check(r.definitions['td_civic_any_enabled_trigger']))

    def test_modules_are_independent_persistent_and_cannot_be_disabled(self):
        r=observed();enable(r,'fiscal');r.variables['sentinel']=3
        enable(r,'fiscal');restored=roundtrip(r)
        self.assertEqual(restored.globals,{'td_system_enabled':1,'td_fiscal_enabled':1})
        self.assertEqual(restored.variables['sentinel'],3)
        trees=[load(p) for p in (ROOT/'mod').rglob('*.txt')]
        self.assertFalse(any(e.key=='remove_global_variable' and e.value in ('td_fiscal_enabled','td_recruitment_enabled','td_services_enabled') for tree in trees for e in walk(tree)))

    def test_disabled_modules_do_not_change_clout_tax_or_treasury(self):
        r=observed(war=True);gold=r.gold_reserves
        r.execute(r.definitions['td_refresh_country_civic_effect'])
        self.assertEqual(rate(r),0);self.assertEqual(r.tax_level,'medium');self.assertEqual(r.gold_reserves,gold)
        self.assertNotIn('td_weekly_balance',r.variables)

    def test_budget_records_actual_deficit_without_charging_again(self):
        r=observed();r.weekly_balance=-250;r.weekly_expenses=800;r.bureaucracy=-100;r.bureaucracy_usage=500
        enable(r,'fiscal');gold=r.gold_reserves
        for _ in range(4):r.execute(r.definitions['td_refresh_country_civic_effect'])
        self.assertEqual(r.variables['td_weekly_funding_gap'],250)
        self.assertEqual(r.variables['td_service_pressure_percent'],20)
        self.assertEqual(r.gold_reserves,gold);self.assertEqual(r.bureaucracy,-100)

    def test_raising_tax_changes_exactly_one_vanilla_step_and_observes_cooldown(self):
        r=observed();enable(r,'fiscal');r.weekly_balance=-1
        r.execute(r.definitions['td_raise_budget_tax_effect'])
        self.assertEqual(r.tax_level,'high')
        r.execute(r.definitions['td_raise_budget_tax_effect']);self.assertEqual(r.tax_level,'high')
        r.day=31;r.execute(r.definitions['td_raise_budget_tax_effect']);self.assertEqual(r.tax_level,'very_high')
        r.day=62;r.execute(r.definitions['td_raise_budget_tax_effect']);self.assertEqual(r.tax_level,'very_high')

    def test_all_tax_steps_in_both_directions_respect_budget_and_limits(self):
        levels=('very_low','low','medium','high','very_high')
        for index,level in enumerate(levels):
            for direction,balance,wanted in (('raise',-10,levels[min(4,index+1)]),('lower',10,levels[max(0,index-1)])):
                with self.subTest(level=level,direction=direction):
                    r=observed();enable(r,'fiscal');r.tax_level=level;r.weekly_balance=balance
                    r.execute(r.definitions['td_'+direction+'_budget_tax_effect']);self.assertEqual(r.tax_level,wanted)
        r=observed();enable(r,'fiscal');r.weekly_balance=0
        r.execute(r.definitions['td_raise_budget_tax_effect']);r.execute(r.definitions['td_lower_budget_tax_effect'])
        self.assertEqual(r.tax_level,'medium')

    def test_tax_cut_needs_reserves_and_does_not_award_free_support(self):
        r=agenda(owned=True,kind=2);enable(r,'fiscal');r.gold_reserves=0
        r.execute(r.definitions['td_lower_budget_tax_effect']);self.assertEqual(r.tax_level,'medium')
        r.gold_reserves=1000;r.execute(r.definitions['td_lower_budget_tax_effect'])
        self.assertEqual(r.tax_level,'low');self.assertEqual(r.gold_reserves,1000)
        self.assertTrue(all(g['variables']['td_component_fiscal']==0 for g in r.groups.values()))

    def test_tax_burden_is_target_bill_baseline_and_actual_law_specific(self):
        cases={'land_based_taxation':('landowners','rural_folk'),
               'per_capita_based_taxation':('trade_unions','rural_folk','petty_bourgeoisie'),
               'consumption_based_taxation':('trade_unions','rural_folk','petty_bourgeoisie'),
               'proportional_taxation':('landowners','industrialists','trade_unions','petty_bourgeoisie'),
               'graduated_taxation':('landowners','industrialists')}
        for law,groups in cases.items():
            with self.subTest(law=law):
                r=agenda();enable(r,'fiscal');r.policy['has_law:law_type:law_'+law]=True;r.tax_level='high'
                r.execute(r.definitions['td_calculate_politics_effect'])
                self.assertEqual(r.variables['td_bill_tax_baseline'],3)
                for key,group in r.groups.items():self.assertEqual(group['variables']['td_component_fiscal'],-5 if key[6:] in groups else 0)
                r.tax_level='very_high';r.execute(r.definitions['td_calculate_politics_effect'])
                self.assertEqual(r.groups['ig:ig_'+groups[0]]['variables']['td_component_fiscal'],-10)
                r.execute(r.definitions['td_calculate_politics_effect'])
                self.assertEqual(r.groups['ig:ig_'+groups[0]]['variables']['td_component_fiscal'],-10)

    def test_unknown_tax_law_is_not_assigned_a_fabricated_group_burden(self):
        r=agenda();enable(r,'fiscal');r.tax_level='very_high';r.execute(r.definitions['td_calculate_politics_effect'])
        self.assertEqual(r.variables['td_budget_tax_law'],0)
        self.assertTrue(all(g['variables']['td_component_fiscal']==0 for g in r.groups.values()))

    def test_recruitment_matches_continuous_legitimacy_formula(self):
        for legitimacy in (0,20,40,50,60,80,100):
            with self.subTest(legitimacy=legitimacy):
                r=observed(war=True,legitimacy=legitimacy);enable(r,'recruitment')
                self.assertAlmostEqual(rate(r),.1*(legitimacy-50)/50)
                self.assertAlmostEqual(r.variables['td_recruitment_percent'],100*rate(r))
                self.assertEqual(rate(r,'B'),0)

    def test_recruitment_requires_approval_doctrine_and_offensive_warleader(self):
        for missing in ('approval','doctrine','war','attacker','participant'):
            with self.subTest(missing=missing):
                r=observed(war=True)
                if missing=='approval':r.variables.pop('td_expansion_program')
                elif missing=='doctrine':
                    r.policy['has_law:law_type:law_td_imperial_expansion']=False
                    r.policy['has_law:law_type:law_td_status_quo']=True
                elif missing=='war':r.at_war=False
                elif missing=='attacker':r.attacker_warleaders['W1']='ENEMY'
                else:r.participants['W1']={'ENEMY'}
                enable(r,'recruitment');self.assertEqual(rate(r),0)

    def test_recruitment_never_applies_to_treaty_ports(self):
        r=observed(war=True);r.states['A']['treaty_port']=True;enable(r,'recruitment')
        self.assertEqual(rate(r),0)

    def test_recruitment_replaces_sign_instead_of_stacking_and_ends_at_peace(self):
        r=observed(war=True,legitimacy=100);enable(r,'recruitment')
        r.execute(r.definitions['td_refresh_country_civic_effect']);self.assertEqual(rate(r),.1)
        r.legitimacy=0;r.execute(r.definitions['td_refresh_country_civic_effect'])
        self.assertEqual(rate(r),-.1);self.assertEqual({key for key in r.states['A']['modifiers'] if key.startswith('td_conscription_')},{'td_conscription_low_trust'})
        r.at_war=False;r.execute(r.definitions['td_refresh_country_civic_effect']);self.assertEqual(rate(r),0)
        self.assertIn('td_recruitment_enabled',r.globals)

    def test_expired_program_cannot_be_restored_by_reloading(self):
        r=observed(war=True);enable(r,'recruitment');r.day=1096
        r=roundtrip(r);r.execute(r.definitions['td_refresh_country_civic_effect'])
        self.assertNotIn('td_expansion_program',r.variables);self.assertEqual(rate(r),0)
        self.assertIn('td_recruitment_enabled',r.globals)

    def test_returning_to_peace_retains_paid_contracts_and_permanent_modules(self):
        r=agenda();enable(r,'fiscal');r.execute(r.definitions['td_sign_navy_pledge_effect']);resolve(r,3)
        gold=r.gold_reserves;deadline=r.variables['td_navy_acquisition_deadline'];generation=r.variables['td_bill_generation']
        self.assertIn('td_expansion_program',r.variables)
        r.execute(r.definitions['td_return_peace_budget_effect'])
        self.assertNotIn('td_expansion_program',r.variables);self.assertEqual(r.variables['td_civic_phase'],0)
        self.assertEqual(r.variables['td_navy_acquisition_deadline'],deadline);self.assertEqual(r.gold_reserves,gold)
        self.assertEqual(r.variables['td_bill_generation'],generation);self.assertIn('td_fiscal_enabled',r.globals)

    def test_active_claim_cannot_be_hidden_by_switching_budget_mode(self):
        r=agenda();enable(r,'fiscal');r.variables['td_expansion_program']=1
        r.execute(r.definitions['td_return_peace_budget_effect'])
        self.assertIn('td_expansion_program',r.variables);self.assertEqual(r.variables['td_civic_phase'],1)
        self.assertEqual(r.variables['td_recruitment_active'],0)

    def test_services_read_actual_institutions_and_pressure_without_reducing_them(self):
        r=observed();enable(r,'services');r.institutions['institution_schools']=2;r.bureaucracy=-100;r.bureaucracy_usage=400
        r.execute(r.definitions['td_refresh_country_civic_effect'])
        self.assertEqual(r.variables['td_service_education_gap'],1)
        self.assertEqual(r.variables['td_service_health_gap'],0)
        self.assertEqual(r.variables['td_service_pressure_percent'],25)
        self.assertEqual(r.institutions,{'institution_schools':2,'institution_health_system':2})
        self.assertEqual(r.bureaucracy,-100)

    def test_absent_services_and_zero_usage_are_safe_and_do_not_fake_coverage(self):
        r=observed();r.institutions={};r.bureaucracy=-100;r.bureaucracy_usage=0;enable(r,'services')
        self.assertEqual(r.variables['td_service_education'],0);self.assertEqual(r.variables['td_service_health'],0)
        self.assertEqual(r.variables['td_service_pressure_percent'],100)

    def test_service_feedback_is_actual_cuts_and_deficit_in_expansion_or_peace(self):
        for kind in (1,2,3):
            with self.subTest(kind=kind):
                r=agenda(owned=kind==2,kind=kind)
                r.institutions={'institution_schools':3,'institution_health_system':2}
                r.execute(r.definitions['td_snapshot_civic_bill_effect']);enable(r,'services')
                r.institutions['institution_schools']=2;r.institutions['institution_health_system']=0;r.bureaucracy=-1
                r.execute(r.definitions['td_calculate_politics_effect'])
                self.assertEqual(r.groups['ig:ig_intelligentsia']['variables']['td_component_services'],-10)
                self.assertEqual(r.groups['ig:ig_trade_unions']['variables']['td_component_services'],-10)
                self.assertEqual(r.groups['ig:ig_petty_bourgeoisie']['variables']['td_component_services'],-5)
                r.institutions={'institution_schools':3,'institution_health_system':2};r.bureaucracy=1000
                r.execute(r.definitions['td_calculate_politics_effect'])
                self.assertTrue(all(g['variables']['td_component_services']==0 for g in r.groups.values()))

    def test_reload_keeps_module_flags_baselines_and_tax_cooldown(self):
        r=agenda();r.institutions={'institution_schools':2};enable(r,'fiscal');enable(r,'services')
        r.weekly_balance=-10;r.execute(r.definitions['td_raise_budget_tax_effect']);r=roundtrip(r)
        before=deepcopy(r.variables);r.execute(r.definitions['td_raise_budget_tax_effect'])
        self.assertEqual(r.tax_level,'high');self.assertEqual(r.variables,before)
        self.assertEqual(r.variables['td_bill_tax_baseline'],3)
        self.assertEqual(r.variables['td_service_reference_education'],2)

    def test_all_catalog_entries_have_one_vtd_prefix_and_regeneration_is_stable(self):
        for path in (ROOT/'mod/localization').rglob('*.yml'):
            for line in path.read_text(encoding='utf-8-sig').splitlines()[1:]:
                if not line.strip() or line.lstrip().startswith('#'):continue
                self.assertRegex(line,r'^\s+[\w.]+:\d+ "VTD ')
                self.assertNotIn('"VTD VTD ',line)
        self.assertEqual(outputs(),outputs())
        self.assertEqual(validate(ROOT/'mod'),[])

    def test_monthly_owner_and_load_paths_refresh_or_clear_recruitment(self):
        callbacks=load(ROOT/'mod/common/on_actions/td_on_actions.txt')
        self.assertTrue(any(e.key=='td_refresh_country_civic_effect' for e in walk(callbacks)))
        states=load(ROOT/'mod/common/scripted_effects/td_states.txt')
        self.assertTrue(any(e.key=='td_maybe_clear_conscription_state_effect' for e in walk(states)))
        r=observed(war=True);enable(r,'recruitment');self.assertGreater(rate(r),0)
        r.states['A']['variables']['td_recorded_owner']='POR'
        r.scope='A';r.execute(r.definitions['td_maybe_clear_conscription_state_effect'])
        self.assertGreater(rate(r),0)  # Same-owner refresh/load must preserve the effect.
        r.states['A']['owner']='ENEMY';r.execute(r.definitions['td_maybe_clear_conscription_state_effect']);r.scope=None
        self.assertEqual(rate(r),0)
        r.execute(r.definitions['td_refresh_country_civic_effect']);self.assertEqual(rate(r),0)
        effects=load(ROOT/'mod/common/scripted_effects/td_civic.txt')
        self.assertTrue(any(e.key=='multiplier' and e.value=='owner.var:td_mobilization_scale' for e in walk(effects)))


if __name__=='__main__':unittest.main()
