"""Run distribution clauses against explicit institutional/market/faith fixtures."""
from copy import deepcopy
from pathlib import Path
import unittest
from test_bargaining import agenda, resolve
from test_plan_delivery import roundtrip, set_colonial_policy
from territorial_doctrine.model import RULES, colonial_group_tendencies
from territorial_doctrine.script import load, walk

ROOT=Path(__file__).resolve().parents[1]
KINDS=('religious_schools','public_schools','health_services','land_settlement','low_tax')


def candidate(kind, *, owned=True):
    r=agenda(owned=owned,kind=2 if owned else 1)
    r.institutions={'institution_schools':2,'institution_health_system':2}
    r.policy['has_law:law_type:law_'+('public_schools' if kind=='public_schools' else 'religious_schools')]=True
    r.policy['has_law:law_type:law_serfdom']=True
    r.tax_level='low';r.globals['td_fiscal_enabled']=1
    return r


def sign(r,kind):r.execute(r.definitions['td_sign_'+kind+'_allocation_effect'])
def audit(r):r.execute(r.definitions['td_allocations_monthly_effect'])


class AllocationTests(unittest.TestCase):
    def test_two_slots_are_shared_with_existing_paid_construction(self):
        r=candidate('low_tax');sign(r,'low_tax');r.execute(r.definitions['td_sign_navy_pledge_effect'])
        self.assertEqual(r.variables['td_bill_allocation_count'],2);gold=r.gold_reserves
        r.execute(r.definitions['td_sign_railway_pledge_effect']);sign(r,'health_services')
        self.assertEqual(r.gold_reserves,gold);self.assertNotIn('td_pending_health_services',r.variables)
        self.assertNotIn('td_pending_railway',r.variables)

    def test_each_clause_pays_and_reserves_resources_without_free_power(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                r=candidate(kind);clout=[g['clout'] for g in r.groups.values()];sign(r,kind)
                self.assertEqual(r.gold_reserves,990000);self.assertEqual(r.context()['bureaucracy'],990)
                self.assertEqual(r.variables['td_bill_allocation_count'],1)
                self.assertEqual([g['clout'] for g in r.groups.values()],clout)
                sign(r,kind);self.assertEqual(r.gold_reserves,990000)

    def test_cash_and_administration_are_required_for_every_clause(self):
        for kind in KINDS:
            for resource in ('cash','administration'):
                with self.subTest(kind=kind,resource=resource):
                    r=candidate(kind)
                    if resource=='cash':r.gold_reserves=4999
                    else:r.bureaucracy=9
                    sign(r,kind);self.assertNotIn('td_pending_'+kind,r.variables)

    def test_schools_cannot_be_allocated_to_both_institutional_roles(self):
        r=candidate('religious_schools');r.policy['has_law:law_type:law_public_schools']=True
        sign(r,'religious_schools');sign(r,'public_schools')
        self.assertNotIn('td_pending_public_schools',r.variables);self.assertEqual(r.gold_reserves,990000)

    def test_institutions_must_exist_and_have_investment_headroom(self):
        for kind,inst in (('religious_schools','institution_schools'),('public_schools','institution_schools'),('health_services','institution_health_system')):
            for missing in ('institution','capacity'):
                with self.subTest(kind=kind,missing=missing):
                    r=candidate(kind)
                    if missing=='institution':r.institutions.pop(inst)
                    else:r.institutions[inst]=r.institution_max[inst]
                    sign(r,kind);self.assertNotIn('td_pending_'+kind,r.variables)

    def test_low_tax_guarantee_requires_actual_low_tax_and_funded_budget(self):
        for missing in ('tax','fiscal_module','budget'):
            r=candidate('low_tax')
            if missing=='tax':r.tax_level='medium'
            elif missing=='fiscal_module':r.globals.pop('td_fiscal_enabled')
            else:r.weekly_balance=-1
            sign(r,'low_tax');self.assertNotIn('td_pending_low_tax',r.variables)

    def test_land_clause_does_not_claim_unverified_property_transfers(self):
        r=candidate('land_settlement');r.policy['has_law:law_type:law_serfdom']=False
        r.policy['has_law:law_type:law_homesteading']=True
        sign(r,'land_settlement');self.assertNotIn('td_pending_land_settlement',r.variables)
        r.policy['has_law:law_type:law_tenant_farmers']=True;sign(r,'land_settlement')
        self.assertEqual(r.variables['td_land_settlement_land_law'],2)
        self.assertEqual(r.states['A']['owner'],r.country)

    def test_group_allocations_create_opposed_interests(self):
        cases=(('religious_schools','devout','intelligentsia'),('public_schools','intelligentsia','devout'),('land_settlement','landowners','rural_folk'))
        for kind,beneficiary,opponent in cases:
            r=candidate(kind);sign(r,kind)
            self.assertEqual(r.groups['ig:ig_'+beneficiary]['variables']['td_component_allocation'],10)
            self.assertEqual(r.groups['ig:ig_'+opponent]['variables']['td_component_allocation'],-5)
        r=candidate('low_tax');sign(r,'low_tax')
        self.assertEqual(r.groups['ig:ig_rural_folk']['variables']['td_component_allocation'],10)
        self.assertEqual(r.groups['ig:ig_petty_bourgeoisie']['variables']['td_component_allocation'],10)
        r=candidate('health_services');sign(r,'health_services')
        self.assertEqual(r.groups['ig:ig_trade_unions']['variables']['td_component_allocation'],10)

    def test_unratified_incompatible_clause_releases_slot_without_refund(self):
        r=candidate('religious_schools');sign(r,'religious_schools')
        r.policy['has_law:law_type:law_religious_schools']=False
        r.execute(r.definitions['td_calculate_politics_effect'])
        self.assertNotIn('td_pending_religious_schools',r.variables)
        self.assertNotIn('td_bill_religious_schools',r.variables)
        self.assertEqual(r.variables['td_bill_allocation_count'],0);self.assertEqual(r.gold_reserves,990000)
        self.assertEqual(r.groups['ig:ig_devout']['variables']['td_component_allocation'],0)

    def test_cancellation_releases_all_unratified_clauses(self):
        r=candidate('low_tax');sign(r,'low_tax');sign(r,'health_services')
        r.execute(r.definitions['td_cancel_bill_effect'])
        self.assertNotIn('td_pending_low_tax',r.variables);self.assertNotIn('td_pending_health_services',r.variables)
        self.assertNotIn('td_low_tax_planning',r.modifiers);self.assertEqual(r.gold_reserves,980000)

    def test_institution_delivery_needs_both_real_investment_and_exact_state_incorporation(self):
        for kind,inst in (('religious_schools','institution_schools'),('public_schools','institution_schools'),('health_services','institution_health_system')):
            r=candidate(kind);sign(r,kind);resolve(r,3)
            r.states['B']['incorporated']=True;r.institutions[inst]=3;audit(r)
            self.assertIn('td_pending_'+kind,r.variables)
            r.states['A']['incorporated']=True;r.institutions[inst]=2;audit(r)
            self.assertIn('td_pending_'+kind,r.variables)
            r.institutions[inst]=3;audit(r);self.assertNotIn('td_pending_'+kind,r.variables)
            self.assertEqual(r.gold_reserves,990000)

    def test_maintenance_guarantee_needs_a_full_year_and_keeps_original_deadline(self):
        for kind in ('low_tax','land_settlement'):
            r=candidate(kind);sign(r,kind);resolve(r,3);passed=r.day
            deadline=r.expirations['td_'+kind+'_deadline']
            r.day=passed+364;audit(r);self.assertIn('td_pending_'+kind,r.variables)
            r=roundtrip(r);self.assertEqual(r.expirations['td_'+kind+'_deadline'],deadline)
            r.day=passed+365;audit(r);self.assertNotIn('td_pending_'+kind,r.variables)

    def test_ratifed_guarantee_breaches_on_real_policy_change(self):
        for kind in KINDS:
            r=candidate(kind);sign(r,kind);resolve(r,3)
            if kind=='religious_schools':r.policy['has_law:law_type:law_religious_schools']=False
            elif kind=='public_schools':r.policy['has_law:law_type:law_public_schools']=False
            elif kind=='health_services':r.institutions.pop('institution_health_system')
            elif kind=='land_settlement':r.policy['has_law:law_type:law_serfdom']=False;r.policy['has_law:law_type:law_tenant_farmers']=True
            else:r.tax_level='medium'
            audit(r);self.assertNotIn('td_pending_'+kind,r.variables)
            self.assertIn('td.18',r.notifications)
            self.assertNotIn('td_'+kind+'_planning',r.modifiers)

    def test_religious_contract_preserves_the_recorded_faith(self):
        r=candidate('religious_schools');sign(r,'religious_schools');resolve(r,3)
        r.religion='OTHER_FAITH';audit(r)
        self.assertNotIn('td_pending_religious_schools',r.variables)
        self.assertIn('td_broken_pledge',r.groups['ig:ig_devout']['variables'])

    def test_foreign_acquisition_keeps_paid_signing_baseline_and_binds_real_state(self):
        r=candidate('health_services',owned=False);sign(r,'health_services');resolve(r,3)
        r.institutions['institution_health_system']=3;r.states['B']['owner']=r.country;audit(r)
        self.assertNotIn('td_health_services_started',r.variables)
        r.states['A']['owner']=r.country;audit(r)
        self.assertEqual(r.variables['td_health_services_target'],'A');self.assertEqual(r.variables['td_health_services_baseline'],2)
        deadline=r.expirations['td_health_services_deadline'];r=roundtrip(r)
        self.assertEqual(r.expirations['td_health_services_deadline'],deadline)
        r.states['A']['incorporated']=True;r.institutions['institution_health_system']=3;audit(r)
        self.assertNotIn('td_pending_health_services',r.variables)

    def test_never_acquired_expires_without_construction_breach(self):
        r=candidate('health_services',owned=False);sign(r,'health_services');resolve(r,3)
        r.day=r.expirations['td_health_services_acquisition_deadline'];audit(r)
        self.assertNotIn('td_pending_health_services',r.variables);self.assertNotIn('td.18',r.notifications)

    def test_partial_region_treaty_ports_and_invalid_bill_never_charge(self):
        for missing in ('partial','port','invalid'):
            r=candidate('health_services',owned=False)
            if missing=='partial':r.states['B']['state_region']=r.states['A']['state_region'];r.states['B']['owner']=r.country
            elif missing=='port':r.states['A']['treaty_port']=True
            else:r.interests.clear()
            sign(r,'health_services');self.assertEqual(r.gold_reserves,1000000)

    def test_new_bill_cancellation_preserves_old_ratified_allocation(self):
        r=candidate('low_tax');sign(r,'low_tax');resolve(r,3);deadline=r.expirations['td_low_tax_deadline']
        self.assertNotIn('td_bill_low_tax',r.variables)
        r.variables.update(td_target='B',td_bill=1,td_reason=7)
        r.execute(r.definitions['td_start_bill_effect']);r.execute(r.definitions['td_cancel_bill_effect'])
        self.assertIn('td_pending_low_tax',r.variables);self.assertEqual(r.expirations['td_low_tax_deadline'],deadline)

    def test_old_negotiation_window_cannot_sign_new_allocations(self):
        r=candidate('health_services');r.next_event();window=deepcopy(r.windows[-1])
        resolve(r);gold=r.gold_reserves
        self.assertFalse(r.choose(window,'td.allocate.health_services'));self.assertEqual(r.gold_reserves,gold)

    def test_delivered_allocations_do_not_repeat_rewards(self):
        r=candidate('health_services');sign(r,'health_services');resolve(r,3)
        r.states['A']['incorporated']=True;r.institutions['institution_health_system']=3;audit(r)
        expires=deepcopy(r.modifier_expirations);r.day+=100;audit(r)
        self.assertEqual(r.modifier_expirations,expires)
        self.assertNotIn('td_health_services_planning',r.modifiers)

    def test_unfinished_institutions_breach_once_without_reversing_after_late_delivery(self):
        r=candidate('health_services');sign(r,'health_services');resolve(r,3)
        r.states['A']['incorporated']=True;r.day=r.expirations['td_health_services_deadline'];audit(r)
        self.assertIn('td_pledge_broken',r.groups['ig:ig_trade_unions']['modifiers'])
        self.assertNotIn('td_pledge_broken',r.groups['ig:ig_devout']['modifiers'])
        self.assertNotIn('td_pending_health_services',r.variables)
        before=deepcopy(r.modifier_expirations)
        r.institutions['institution_health_system']=4;r.day+=100;audit(r)
        self.assertEqual(r.modifier_expirations,before)

    def test_loss_and_reacquisition_do_not_reset_delivery_baseline_or_deadline(self):
        r=candidate('health_services');sign(r,'health_services');resolve(r,3)
        deadline=r.expirations['td_health_services_deadline'];baseline=r.variables['td_health_services_baseline']
        r.states['A']['owner']='ENEMY';r.institutions['institution_health_system']=3;audit(r)
        self.assertIn('td_pending_health_services',r.variables)
        r=roundtrip(r);r.states['A']['owner']=r.country;r.states['A']['incorporated']=False;audit(r)
        self.assertEqual(r.expirations['td_health_services_deadline'],deadline)
        self.assertEqual(r.variables['td_health_services_baseline'],baseline)
        r.states['A']['incorporated']=True;audit(r);self.assertNotIn('td_pending_health_services',r.variables)

    def test_same_market_never_counts_as_new_market_opportunity(self):
        r=agenda();r.states['A']['market']='M_ACTOR';r.execute(r.definitions['td_calculate_politics_effect'])
        self.assertEqual(r.variables['td_fact_new_market'],0)
        r.states['A']['market']='M_FOREIGN';r.states['A']['market_access']=.4;r.execute(r.definitions['td_calculate_politics_effect'])
        self.assertEqual(r.variables['td_fact_new_market'],0)
        r.states['A']['market_access']=.9;r.execute(r.definitions['td_calculate_politics_effect'])
        self.assertEqual(r.variables['td_fact_new_market'],1)
        self.assertEqual(r.groups['ig:ig_industrialists']['variables']['td_component_opportunity'],5)

    def test_mission_opportunity_needs_actual_school_law_and_religious_demographics(self):
        r=agenda();r.states['A']['actor_religion_share']=.2;r.execute(r.definitions['td_calculate_politics_effect'])
        self.assertEqual(r.variables['td_fact_mission_space'],0)
        r.policy['has_law:law_type:law_religious_schools']=True;r.execute(r.definitions['td_calculate_politics_effect'])
        self.assertEqual(r.variables['td_fact_mission_space'],1)
        r.states['A']['actor_religion_share']=.5;r.execute(r.definitions['td_calculate_politics_effect'])
        self.assertEqual(r.variables['td_fact_mission_space'],0)

    def test_all_eight_groups_have_a_funded_route_without_automatic_strength(self):
        scripts=[load(p) for p in (ROOT/'mod/common/scripted_effects').glob('*.txt')]
        self.assertFalse(any(e.key in ('add_radicals','add_loyalists','convert_population') or e.key.endswith('_pol_str_mult') for tree in scripts for e in walk(tree)))
        intended={'armed_forces','industrialists','devout','intelligentsia','trade_unions','landowners','rural_folk','petty_bourgeoisie'}
        from tools.allocation_assets import CONTRACTS
        available={'armed_forces','industrialists'}|{g for c in CONTRACTS.values() for g in c['groups']}
        self.assertEqual(available,intended)

    def test_colonial_opportunities_and_humanitarian_stages_are_group_specific(self):
        self.assertEqual(colonial_group_tendencies('devout','exploitation',2),(0,0))
        self.assertEqual(colonial_group_tendencies('armed_forces','exploitation',0),colonial_group_tendencies('armed_forces','exploitation',2))
        self.assertLess(colonial_group_tendencies('rural_folk','exploitation',0)[0],0)
        self.assertGreater(colonial_group_tendencies('industrialists','exploitation',0)[0],0)
        self.assertLess(colonial_group_tendencies('intelligentsia','exploitation',2)[0],0)
        self.assertGreater(colonial_group_tendencies('intelligentsia','exploitation',2)[1],0)


if __name__=='__main__':unittest.main()
