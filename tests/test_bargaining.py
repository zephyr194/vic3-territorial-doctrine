"""Execute actual bargaining and contract scripts with explicit engine fixtures."""
from copy import deepcopy
from pathlib import Path
import unittest

from test_plan_delivery import GeographyRunner, roundtrip, set_colonial_policy
from territorial_doctrine.script import load, parse, walk
from territorial_doctrine.model import RULES

ROOT = Path(__file__).resolve().parents[1]


def agenda(*, owned=False, country='POR', kind=1):
    r = GeographyRunner((.01,)*30,country=country)
    r.auto_negotiate = False
    r.real_politics = True
    r.policy['has_technology_researched:railways'] = True
    for s in r.states.values():
        s.update(coastal=True,buildings={'naval_base':2,'railway':1})
    if owned:
        r.states['A']['owner'] = country
    r.variables.update(td_target='A',td_bill=kind,td_pending_bill=kind,td_reason=4 if kind==2 else 7)
    r.execute(r.definitions['td_start_bill_effect'])
    return r


def resolve(r, rounds=1):
    for _ in range(rounds):
        while not r.variables.get('td_waiting_round'):
            r.next_event()
        window = next(w for w in reversed(r.windows) if w['name']=='td.32')
        if not r.choose(window,'td.negotiate.continue'):
            raise AssertionError('A current negotiation cannot proceed')


class BargainingTests(unittest.TestCase):
    def test_player_round_requires_an_explicit_choice(self):
        r=agenda();r.next_event()
        self.assertIn('td_waiting_round',r.variables)
        self.assertEqual(r.variables['td_successes'],0)
        self.assertFalse(r.queue)
        self.assertEqual(r.windows[-1]['name'],'td.32')
        r.execute(r.definitions['td_open_negotiation_effect'])
        resolve(r)
        self.assertEqual(r.variables['td_successes'],1)
        self.assertEqual(r.queue[0][0],180)

    def test_funding_changes_support_with_real_payment_and_reserve(self):
        r=agenda();r.next_event();old=r.variables['td_chance']
        clout=[g['clout'] for g in r.groups.values()]
        r.choose(r.windows[-1],'td.negotiate.navy')
        self.assertEqual(r.gold_reserves,990000)
        self.assertIn('td_navy_planning',r.modifiers)
        self.assertEqual(r.context()['bureaucracy'],990)
        af=r.groups['ig:ig_armed_forces']['variables']
        self.assertEqual(af['td_component_funded'],10)
        self.assertEqual(af['td_score'],20)
        self.assertGreater(r.variables['td_chance'],old)
        self.assertEqual([g['clout'] for g in r.groups.values()],clout)

    def test_duplicate_funding_cannot_charge_or_stack(self):
        r=agenda();r.execute(r.definitions['td_sign_navy_pledge_effect'])
        before=deepcopy((r.variables,r.modifiers,r.gold_reserves))
        r.execute(r.definitions['td_sign_navy_pledge_effect'])
        self.assertEqual((r.variables,r.modifiers,r.gold_reserves),before)

    def test_insufficient_cash_or_administration_gives_no_support(self):
        for cash,admin in ((9999,1000),(1000000,9)):
            r=agenda();r.gold_reserves=cash;r.bureaucracy=admin
            r.execute(r.definitions['td_sign_navy_pledge_effect'])
            self.assertEqual(r.gold_reserves,cash)
            self.assertNotIn('td_pending_navy',r.variables)
            self.assertNotIn('td_navy_planning',r.modifiers)
            self.assertEqual(r.groups['ig:ig_armed_forces']['variables']['td_component_funded'],0)

    def test_inland_and_unresearched_projects_cannot_be_promised(self):
        r=agenda();r.states['A']['coastal']=False
        r.execute(r.definitions['td_sign_navy_pledge_effect'])
        r.policy['has_technology_researched:railways']=False
        r.execute(r.definitions['td_sign_railway_pledge_effect'])
        self.assertEqual(r.gold_reserves,1000000)
        self.assertFalse(r.modifiers)

    def test_foreign_split_with_existing_own_portion_cannot_bind_old_land(self):
        r=agenda();r.states['B'].update(owner='POR',state_region='REGION_A')
        r.execute(r.definitions['td_sign_navy_pledge_effect'])
        self.assertNotIn('td_pending_navy',r.variables)
        self.assertEqual(r.gold_reserves,1000000)

    def test_frozen_bill_target_wins_over_preview_or_project_target(self):
        r=agenda(owned=True,kind=2)
        r.variables['td_target']='B'
        r.execute(r.definitions['td_sign_railway_pledge_effect'])
        self.assertEqual(r.variables['td_railway_target'],'A')
        self.assertEqual(r.variables['td_railway_region'],'REGION_A')
        self.assertEqual(r.variables['td_railway_baseline'],1)

    def test_old_round_dialog_cannot_vote_in_a_later_round(self):
        r=agenda();r.next_event();old=deepcopy(r.windows[-1])
        r.choose(old,'td.negotiate.continue')
        r.next_event()
        current=r.variables['td_successes']
        self.assertFalse(r.choose(old,'td.negotiate.continue'))
        self.assertFalse(r.choose(old,'td.negotiate.navy'))
        self.assertEqual(r.variables['td_successes'],current)
        self.assertEqual(r.gold_reserves,1000000)

    def test_duplicate_old_round_timer_cannot_open_an_extra_round(self):
        r=agenda();old_saved=deepcopy(r.queue[0][3]);r.next_event();resolve(r)
        r.saved=old_saved;r.fire('td.1')
        self.assertNotIn('td_waiting_round',r.variables)
        self.assertEqual(len(r.queue),1)

    def test_cancel_releases_only_unratified_reserves_without_refund(self):
        r=agenda();r.execute(r.definitions['td_sign_navy_pledge_effect'])
        r.execute(r.definitions['td_sign_railway_pledge_effect'])
        r.execute(r.definitions['td_cancel_bill_effect'])
        self.assertEqual(r.gold_reserves,980000)
        self.assertFalse(r.modifiers)
        self.assertNotIn('td_pending_navy',r.variables)
        self.assertNotIn('td_pending_railway',r.variables)
        self.assertNotIn('td_bill',r.variables)

    def test_canceling_later_bill_does_not_erase_ratified_contract(self):
        r=agenda();r.execute(r.definitions['td_sign_navy_pledge_effect']);resolve(r,3)
        contract=deepcopy({k:v for k,v in r.variables.items() if k.startswith('td_navy_')})
        r.variables.update(td_bill=2,td_bill_target='B')
        r.execute(r.definitions['td_cancel_bill_effect'])
        self.assertIn('td_pending_navy',r.variables)
        self.assertEqual({k:v for k,v in r.variables.items() if k.startswith('td_navy_')},contract)

    def test_owned_state_baseline_is_from_signing_not_a_later_preview(self):
        r=agenda(owned=True,kind=2);r.execute(r.definitions['td_sign_railway_pledge_effect'])
        self.assertEqual(r.variables['td_railway_baseline'],1)
        r.states['A']['buildings']['railway']=2
        resolve(r,3)
        r.execute(r.definitions['td_pledges_monthly_effect'])
        self.assertNotIn('td_pending_railway',r.variables)
        self.assertIn('td_pledge_fulfilled',r.groups['ig:ig_industrialists']['modifiers'])
        self.assertNotIn('td_railway_planning',r.modifiers)

    def test_other_state_construction_does_not_fulfill_pledge(self):
        r=agenda(owned=True,kind=2);r.states['B']['owner']='POR'
        r.execute(r.definitions['td_sign_navy_pledge_effect']);resolve(r,3)
        r.states['B']['buildings']['naval_base']=100
        r.execute(r.definitions['td_pledges_monthly_effect'])
        self.assertIn('td_pending_navy',r.variables)
        self.assertFalse(r.groups['ig:ig_armed_forces']['modifiers'])

    def test_foreign_contract_starts_only_after_actual_region_acquisition(self):
        r=agenda();r.execute(r.definitions['td_sign_navy_pledge_effect']);resolve(r,3)
        r.states['B']['owner']='POR'
        r.execute(r.definitions['td_pledges_monthly_effect'])
        self.assertNotIn('td_navy_started',r.variables)
        r.states['A']['owner']='POR'
        r.execute(r.definitions['td_pledges_monthly_effect'])
        self.assertEqual(r.variables['td_navy_target'],'A')
        self.assertEqual(r.variables['td_navy_baseline'],2)
        deadline=r.expirations['td_navy_deadline']
        r.day+=100;r.execute(r.definitions['td_pledges_monthly_effect'])
        self.assertEqual(r.expirations['td_navy_deadline'],deadline)
        r.states['A']['buildings']['naval_base']=3
        r.execute(r.definitions['td_pledges_monthly_effect'])
        self.assertIn('td_pledge_fulfilled',r.groups['ig:ig_armed_forces']['modifiers'])

    def test_never_acquired_contract_closes_without_construction_breach(self):
        r=agenda();r.execute(r.definitions['td_sign_navy_pledge_effect']);resolve(r,3)
        r.day=r.expirations['td_navy_acquisition_deadline']
        r.execute(r.definitions['td_pledges_monthly_effect'])
        self.assertNotIn('td_pending_navy',r.variables)
        self.assertNotIn('td_navy_planning',r.modifiers)
        self.assertFalse(r.groups['ig:ig_armed_forces']['modifiers'])
        self.assertEqual(r.gold_reserves,990000)

    def test_loss_recovery_and_doctrine_change_do_not_restart_delivery(self):
        r=agenda(owned=True,kind=2);r.execute(r.definitions['td_sign_navy_pledge_effect']);resolve(r,3)
        deadline=r.expirations['td_navy_deadline']
        r.states['A']['owner']='ENEMY';r.day+=200
        r.execute(r.definitions['td_doctrine_changed_effect'])
        r.execute(r.definitions['td_pledges_monthly_effect'])
        r.states['A']['owner']='POR'
        r.execute(r.definitions['td_pledges_monthly_effect'])
        self.assertEqual(r.expirations['td_navy_deadline'],deadline)
        self.assertEqual(r.variables['td_navy_baseline'],2)

    def test_breach_changes_only_related_group_and_expires(self):
        r=agenda(owned=True,kind=2);r.execute(r.definitions['td_sign_navy_pledge_effect']);resolve(r,3)
        r.day=r.expirations['td_navy_deadline'];r.execute(r.definitions['td_pledges_monthly_effect'])
        af=r.groups['ig:ig_armed_forces']
        self.assertIn('td_pledge_broken',af['modifiers'])
        self.assertIn('td_broken_pledge',af['variables'])
        self.assertFalse(r.groups['ig:ig_industrialists']['modifiers'])
        self.assertNotIn('td_navy_planning',r.modifiers)
        r.day+=5*365;r.context()
        self.assertNotIn('td_broken_pledge',af['variables'])
        self.assertNotIn('td_pledge_broken',af['modifiers'])

    def test_late_building_does_not_reverse_expired_breach(self):
        r=agenda(owned=True,kind=2);r.execute(r.definitions['td_sign_navy_pledge_effect']);resolve(r,3)
        r.day=r.expirations['td_navy_deadline']
        r.states['A']['buildings']['naval_base']=3
        r.execute(r.definitions['td_pledges_monthly_effect'])
        self.assertIn('td_pledge_broken',r.groups['ig:ig_armed_forces']['modifiers'])
        self.assertNotIn('td_pledge_fulfilled',r.groups['ig:ig_armed_forces']['modifiers'])

    def test_serialized_dialog_and_contract_keep_payment_target_and_deadline(self):
        r=agenda(owned=True,kind=2);r.next_event();r.choose(r.windows[-1],'td.negotiate.navy')
        old_window=deepcopy(r.windows[-1]);r=roundtrip(r,rolls=(.01,)*10)
        self.assertEqual(r.gold_reserves,990000)
        r.choose(old_window,'td.negotiate.continue');resolve(r,2)
        deadline=r.expirations['td_navy_deadline'];r=roundtrip(r)
        r.day+=300;r.execute(r.definitions['td_pledges_monthly_effect'])
        self.assertEqual(r.variables['td_navy_target'],'A')
        self.assertEqual(r.expirations['td_navy_deadline'],deadline)
        self.assertEqual(r.gold_reserves,990000)

    def test_real_group_approval_and_leader_ideology_are_ledger_components(self):
        r=agenda();af=r.groups['ig:ig_armed_forces'];af['approval']=20
        af['leader_ideologies'].add('ideology_pacifist')
        r.execute(r.definitions['td_calculate_politics_effect'])
        self.assertEqual(af['variables']['td_component_trust'],5)
        self.assertEqual(af['variables']['td_component_leader'],-10)
        self.assertEqual(r.variables['td_view_armed_forces_component_trust'],5)
        af['leader_ideologies']={'ideology_jingoist'}
        r.execute(r.definitions['td_calculate_politics_effect'])
        self.assertEqual(af['variables']['td_component_leader'],10)

    def test_equal_rights_argument_does_not_fake_citizenship(self):
        r=agenda(owned=True,kind=2);r.variables['td_reason']=3
        r.execute(r.definitions['td_calculate_politics_effect'])
        intellect=r.groups['ig:ig_intelligentsia']['variables']
        before=intellect['td_component_target']
        r.policy['has_law:law_type:law_multicultural']=True
        r.policy['has_law:law_type:law_total_separation']=True
        r.execute(r.definitions['td_calculate_politics_effect'])
        self.assertEqual(intellect['td_component_target']-before,15)
        self.assertFalse(r.states['A']['homeland'])
        self.assertNotIn('political_changes',r.states['A'])

    def test_integration_does_not_freeze_another_bill_or_swap_its_target(self):
        r=agenda(owned=True,kind=2);resolve(r,3)
        self.assertEqual(r.variables['td_project_target'],'A')
        self.assertTrue(r.check(r.definitions['td_can_start_bill_trigger']))
        r.execute(r.definitions['td_select_claim_effect'])
        self.assertEqual(r.variables['td_target'],'B')
        r.variables.update(td_bill=1,td_reason=7)
        r.execute(r.definitions['td_start_bill_effect'])
        r.run_until(360)
        window=next(w for w in reversed(r.windows) if w['name']=='td.32')
        r.run_until(635)
        self.assertTrue(r.states['A']['incorporated'])
        self.assertEqual(r.variables['td_bill_target'],'B')
        self.assertTrue(r.choose(window,'td.negotiate.continue'))
        self.assertFalse(r.states['B']['incorporated'])

    def test_ai_funds_valid_commitments_and_keeps_automatic_rounds(self):
        r=agenda();r.policy['is_player']=False
        # Engine player predicate is supplied separately by the fixture below.
        original=r.check
        r.check=lambda entries: all((e.value=='no') if e.key=='is_player' else original([e]) for e in entries)
        r.next_event()
        self.assertEqual(r.variables['td_successes'],1)
        self.assertEqual(r.gold_reserves,980000)
        self.assertFalse(r.windows)

    def test_no_unconditional_attribute_or_population_rewards_remain(self):
        for path in ('common/laws/td_laws.txt','common/static_modifiers/td_territory_modifiers.txt','common/static_modifiers/td_success_modifiers.txt'):
            tree=load(ROOT/'mod'/path)
            self.assertFalse(any(e.key.endswith(('throughput_mult','pol_str_mult','migration_pull_mult','construction_mult','legitimacy_base_add')) for e in walk(tree)))
        trees=[load(p) for p in (ROOT/'mod/common/scripted_effects').glob('*.txt')]
        self.assertFalse(any(e.key in ('add_radicals','add_loyalists','add_radicals_in_state','add_loyalists_in_state','add_war_exhaustion') for tree in trees for e in walk(tree)))

    def test_low_legitimacy_does_not_make_domestic_discussion_impossible(self):
        r=agenda();r.legitimacy=0
        self.assertTrue(r.check(r.definitions['td_can_legislate_trigger']))

    def test_stale_dialog_cannot_withdraw_or_charge_a_new_bill(self):
        r=agenda();r.next_event();old=deepcopy(r.windows[-1])
        r.execute(r.definitions['td_cancel_bill_effect'])
        r.variables.pop('td_bill_cooldown',None);r.expirations.pop('td_bill_cooldown',None)
        r.variables.update(td_target='B',td_bill=1,td_reason=7)
        r.execute(r.definitions['td_start_bill_effect']);r.next_event()
        before=deepcopy(r.variables)
        self.assertFalse(r.choose(old,'td.negotiate.withdraw'))
        self.assertFalse(r.choose(old,'td.negotiate.navy'))
        self.assertEqual(r.variables,before)
        self.assertEqual(r.gold_reserves,1000000)

    def test_reopening_invalid_target_cancels_without_additional_payment(self):
        r=agenda();r.next_event();r.choose(r.windows[-1],'td.negotiate.navy')
        r.states['A']['owner']='POR'
        r.execute(r.definitions['td_open_negotiation_effect'])
        self.assertNotIn('td_bill',r.variables)
        self.assertNotIn('td_navy_planning',r.modifiers)
        self.assertEqual(r.gold_reserves,990000)

    def test_survey_has_a_minimum_and_planning_counts_against_next_contract(self):
        r=agenda();r.states['A']['state_population']=1000;r.bureaucracy=15
        r.execute(r.definitions['td_sign_navy_pledge_effect'])
        self.assertEqual(r.gold_reserves,995000)
        r.execute(r.definitions['td_sign_railway_pledge_effect'])
        self.assertNotIn('td_pending_railway',r.variables)
        self.assertEqual(r.gold_reserves,995000)

    def test_delivered_commitment_cannot_repeat_its_reward(self):
        r=agenda(owned=True,kind=2);r.execute(r.definitions['td_sign_navy_pledge_effect']);resolve(r,3)
        r.states['A']['buildings']['naval_base']=3
        r.execute(r.definitions['td_pledges_monthly_effect'])
        expiry=deepcopy(r.modifier_expirations)
        r.day+=100;r.execute(r.definitions['td_pledges_monthly_effect'])
        self.assertEqual(r.modifier_expirations,expiry)
        self.assertNotIn('td_navy_planning',r.modifiers)

    def test_round_dialog_keeps_its_saved_target(self):
        r=agenda();r.next_event();old=deepcopy(r.windows[-1])
        r.variables['td_target']='B'
        self.assertEqual(old['saved']['td_negotiation_target'],'A')
        self.assertTrue(r.choose(old,'td.negotiate.navy'))
        self.assertEqual(r.variables['td_navy_region'],'REGION_A')

    def test_declaring_war_never_calls_an_extra_exhaustion_callback(self):
        callbacks=load(ROOT/'mod/common/on_actions/td_on_actions.txt')
        self.assertFalse(any(e.key in ('on_diplo_play_war_start','on_wargoal_added') for e in callbacks))

    def test_disabled_late_negotiation_cannot_charge_or_vote(self):
        r=agenda();r.next_event();window=deepcopy(r.windows[-1]);r.globals.clear()
        self.assertFalse(r.choose(window,'td.negotiate.continue'))
        self.assertFalse(r.choose(window,'td.negotiate.navy'))
        self.assertEqual(r.gold_reserves,1000000)
        self.assertEqual(r.variables['td_successes'],0)


if __name__=='__main__':unittest.main()
