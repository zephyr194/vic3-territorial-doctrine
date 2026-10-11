from copy import deepcopy
from dataclasses import asdict
from itertools import product
from pathlib import Path
import tempfile
import unittest

from native_runner import EventRunner, WarRunner, policy_context
from territorial_doctrine.model import (RULES, WarGoal, WarMandate, colonial_tendencies,
    colonial_admission_multiplier, doctrine_scores, group_scores, integration_cost, political_weight)
from territorial_doctrine.script import Entry, formula, load, walk
from tools.generate import outputs
from tools.validate import validate

ROOT = Path(__file__).resolve().parents[1]


class ColonialTests(unittest.TestCase):
    def test_exploitation_reverses_with_humanitarian_research(self):
        self.assertEqual(colonial_tendencies('exploitation', 0), (20, -20))
        self.assertEqual(colonial_tendencies('exploitation', 1), (5, -5))
        self.assertEqual(colonial_tendencies('exploitation', 2), (-10, 10))
        with self.assertRaises(ValueError):
            colonial_tendencies('exploitation', 3)

    def test_land_and_resident_bills_have_opposite_incentives(self):
        early_claim = group_scores('imperial_expansion', colonial_target=True, colonial_policy='exploitation')
        late_claim = group_scores('imperial_expansion', colonial_target=True, colonial_policy='exploitation', humanitarian_stage=2)
        early_admit = group_scores('imperial_expansion', admission=True, colonial_target=True, colonial_policy='exploitation')
        late_admit = group_scores('imperial_expansion', admission=True, colonial_target=True, colonial_policy='exploitation', humanitarian_stage=2)
        for g in RULES['groups']:
            self.assertLess(late_claim[g], early_claim[g])
            self.assertGreater(late_admit[g], early_admit[g])

    def test_humanitarian_rights_cost_more_despite_greater_support(self):
        early = integration_cost(1_000_000, 'strategic_frontiers', fast=False,
            colonial_target=True, colonial_policy='exploitation')
        late = integration_cost(1_000_000, 'strategic_frontiers', fast=False,
            colonial_target=True, colonial_policy='exploitation', humanitarian_stage=2)
        self.assertEqual((early, late), (63, 75))

    def test_colonial_policy_shapes_national_doctrine_opinions(self):
        for group in RULES['groups']:
            self.assertLess(doctrine_scores('imperial_expansion', 'exploitation', 2)[group],
                            doctrine_scores('imperial_expansion', 'exploitation', 0)[group])
            self.assertGreater(doctrine_scores('status_quo', 'exploitation', 2)[group],
                               doctrine_scores('status_quo', 'exploitation', 0)[group])

    def test_renunciation_and_non_colonial_targets_keep_original_scores(self):
        original = group_scores('historical_rights', renunciation=True)
        self.assertEqual(original, group_scores('historical_rights', renunciation=True,
            colonial_target=True, colonial_policy='exploitation', humanitarian_stage=2))
        self.assertEqual(group_scores('imperial_expansion'),
            group_scores('imperial_expansion', colonial_policy='exploitation', humanitarian_stage=2))

    def test_native_values_and_costs_match_all_policy_stages(self):
        definitions = {e.key:e.value for p in (ROOT/'mod/common/script_values').glob('*.txt') for e in load(p)}
        for policy, stage in product(RULES['colonial']['policies'], range(3)):
            ctx = policy_context()
            info = RULES['colonial']['policies'][policy]
            if 'law' in info:
                ctx['has_law:law_type:'+info['law']] = True
            for i, tech in enumerate(RULES['colonial']['humanitarian_technologies']):
                ctx['has_technology_researched:'+tech] = i < stage
            expected = colonial_tendencies(policy, stage)
            self.assertEqual(formula('td_colonial_expansion_pull',ctx,definitions),expected[0])
            self.assertEqual(formula('td_colonial_admission_pull',ctx,definitions),expected[1])
            self.assertAlmostEqual(formula('td_colonial_admission_multiplier',ctx,definitions),
                                   colonial_admission_multiplier(policy,stage))
            ctx.update({'var:td_target.state_population':1_000_001, 'var:td_target.turmoil':.3,
                'var:td_target.devastation':.1,'var:td_accepted_share':.4,
                'var:td_target.var:td_source_administration':1,
                'var:td_target.td_colonial_target_trigger':True})
            for fast in (False,True):
                self.assertEqual(formula('td_fast_project_cost' if fast else 'td_regular_project_cost',ctx,definitions),
                    integration_cost(1_000_001,'strategic_frontiers',fast=fast,turmoil=.3,devastation=.1,
                                     accepted_share=.4,colonial_target=True,colonial_policy=policy,humanitarian_stage=stage))

    def test_float_noise_does_not_add_a_bureaucracy_point(self):
        self.assertEqual(integration_cost(1_000_000,'strategic_frontiers',fast=False,actor_power='autocracy'),55)
        self.assertEqual(integration_cost(3_000_000,'strategic_frontiers',fast=False,colonial_target=True,
            colonial_policy='resettlement',humanitarian_stage=1),121)

    def test_actual_bill_score_effects_match_policy_weights(self):
        for policy, stage, kind in product(RULES['colonial']['policies'],range(3),(1,2)):
            r=EventRunner();r.policy.update(policy_context(doctrine='imperial_expansion'))
            r.variables['td_bill']=kind
            info=RULES['colonial']['policies'][policy]
            if 'law' in info:r.policy['has_law:law_type:'+info['law']]=True
            for i,t in enumerate(RULES['colonial']['humanitarian_technologies']):
                r.policy['has_technology_researched:'+t]=i<stage
            r.policy['var:td_target.td_colonial_target_trigger']=True
            r.execute(r.definitions['td_base_scores_effect'])
            r.execute(r.definitions['td_colonial_bill_scores_effect'])
            pull=colonial_tendencies(policy,stage)[kind-1]
            for group in RULES['groups']:
                expected=RULES['groups'][group][3]*10+pull*RULES['colonial']['weights'][group]
                self.assertEqual(r.groups['ig:ig_'+group]['variables']['td_score'],expected)

    def test_generated_profiles_match_model_and_preserve_vanilla_ideologies(self):
        runner = EventRunner()
        for group in runner.groups.values():
            group['ideologies'].add('ideology_liberal')
        for policy, stage in product(RULES['colonial']['policies'], range(3)):
            for p in RULES['colonial']['policies'].values():
                if 'law' in p:
                    runner.policy['has_law:law_type:'+p['law']] = p == RULES['colonial']['policies'][policy]
            for i, tech in enumerate(RULES['colonial']['humanitarian_technologies']):
                runner.policy['has_technology_researched:'+tech] = i < stage
            runner.execute(runner.definitions['td_refresh_colonial_profile_effect'])
            profile = RULES['colonial']['policies'][policy]['id']*3+stage
            for g in RULES['groups']:
                key=f'ideology_td_p{profile//3}_h{profile%3}_{g}'
                self.assertEqual(runner.groups['ig:ig_'+g]['ideologies'], {'ideology_liberal',key})
                law_block=next(e.value for e in runner.definitions[key] if e.key=='lawgroup_territorial_doctrine')
                opinions={e.key:e.value for e in law_block}
                for d in RULES['doctrines']:
                    level=int(political_weight(doctrine_scores(d,policy,stage)[g])*2)
                    expected={-2:'strongly_disapprove',-1:'disapprove',0:'neutral',1:'approve',2:'strongly_approve'}[level]
                    self.assertEqual(opinions['law_td_'+d],expected)
            before=deepcopy(runner.groups)
            runner.execute(runner.definitions['td_refresh_colonial_profile_effect'])
            self.assertEqual(runner.groups,before)


class ActivationTests(unittest.TestCase):
    def test_loaded_disabled_world_has_no_country_or_state_initialization(self):
        runner=EventRunner();runner.globals.clear()
        # A fresh disabled save has no enacted territorial doctrine to clean up.
        for doctrine in RULES['doctrines']:
            runner.policy['has_law:law_type:law_td_' + doctrine] = False
        original=deepcopy(runner.variables)
        runner.execute(next(e.value for e in runner.definitions['td_initialize_world'] if e.key=='effect'))
        self.assertEqual(runner.globals,{'td_mod_present':1})
        self.assertEqual(runner.variables,original)
        self.assertEqual(runner.owner_updates,0)
        self.assertTrue(all(not g['ideologies'] for g in runner.groups.values()))

    def test_enabled_decision_initializes_once_and_cannot_be_repeated(self):
        runner=EventRunner();runner.globals.clear()
        runner.execute(runner.definitions['td_enable_system_effect'])
        self.assertIn('td_system_enabled',runner.globals)
        self.assertIn('td_initialized_v4',runner.variables)
        self.assertEqual(runner.owner_updates,2)
        state=deepcopy((runner.variables,runner.groups,runner.notifications))
        runner.execute(runner.definitions['td_enable_system_effect'])
        self.assertEqual((runner.variables,runner.groups,runner.notifications),state)
        self.assertEqual(runner.owner_updates,2)

    def test_disabled_late_bill_and_project_events_are_inert(self):
        runner=EventRunner();runner.globals.clear()
        runner.variables.update(td_bill=1,td_fast=1,td_generation=1,td_valid_months=11)
        runner.saved['td_project_run']=1
        original=deepcopy(runner.variables)
        runner.fire('td.1');runner.fire('td.2')
        self.assertEqual(runner.variables,original)
        self.assertFalse(runner.queue)
        self.assertFalse(runner.claims)
        self.assertFalse(runner.incorporated)

    def test_admission_stays_locked_until_funded_project(self):
        runner=EventRunner((.1,.1,.1))
        runner.variables.update(td_bill=2,td_reason=4)
        runner.execute(runner.definitions['td_start_bill_effect'])
        for _ in range(3):runner.next_event()
        self.assertIn('td_requires_admission',runner.states['A']['modifiers'])
        runner.execute(runner.definitions['td_start_regular_effect'])
        self.assertNotIn('td_requires_admission',runner.states['A']['modifiers'])
        self.assertIn('td_requires_admission',runner.states['B']['modifiers'])
        self.assertEqual(runner.modifiers['td_project_cost'],50)

    def test_confirming_existing_claim_costs_no_extra_infamy(self):
        runner=EventRunner((.1,.1,.1));runner.claims.add('A')
        runner.variables['td_bill']=1
        runner.execute(runner.definitions['td_start_bill_effect'])
        for _ in range(3):runner.next_event()
        self.assertEqual(runner.variables['infamy'],0)
        self.assertEqual(runner.lists['td_approved_claim_regions'],{'A'})


class FocusTests(unittest.TestCase):
    def prepare(self, runner):
        runner.variables.update(td_pending_bill=1,td_reason=1)

    def test_individual_focus_cost_waiting_and_duplicate_guard(self):
        r=EventRunner();self.prepare(r)
        r.execute(r.definitions['td_designate_focus_effect'])
        self.assertEqual(r.variables['td_focus_count'],1)
        self.assertEqual(r.modifiers['td_focus_strategic_frontiers'],1)
        self.assertEqual(r.lists['td_focus_regions'],{'R1'})
        self.assertNotIn('td_ready_focus_regions',r.lists)
        self.assertEqual(r.queue[0][0],180)
        r.execute(r.definitions['td_designate_focus_effect'])
        self.assertEqual(r.variables['td_focus_count'],1)
        self.assertEqual(len(r.queue),1)
        r.next_event()
        self.assertEqual(r.lists['td_ready_focus_regions'],{'R1'})

    def test_wait_event_keeps_original_region_after_browsing(self):
        r=EventRunner();self.prepare(r)
        r.execute(r.definitions['td_designate_focus_effect'])
        r.variables['td_target']='B'
        r.execute(r.definitions['td_designate_focus_effect'])
        self.assertEqual(r.variables['td_focus_count'],2)
        self.assertEqual(r.modifiers['td_focus_strategic_frontiers'],2)
        r.states['A']['region']='R3';r.variables['td_target']='A'
        r.execute(r.definitions['td_designate_focus_effect'])
        self.assertEqual(r.variables['td_focus_count'],2)
        r.next_event();r.next_event()
        self.assertEqual(r.lists['td_ready_focus_regions'],{'R1','R2'})

    def test_withdrawal_invalidates_old_wait_timer(self):
        r=EventRunner();self.prepare(r)
        r.execute(r.definitions['td_designate_focus_effect'])
        r.execute(r.definitions['td_remove_focus_effect'])
        self.assertEqual(r.variables['td_focus_count'],0)
        self.assertNotIn('td_focus_strategic_frontiers',r.modifiers)
        r.next_event()
        self.assertNotIn('td_ready_focus_regions',r.lists)

    def test_empire_waits_twelve_months_and_disabled_cannot_designate(self):
        r=EventRunner();self.prepare(r)
        r.policy.update(policy_context(doctrine='imperial_expansion'))
        r.execute(r.definitions['td_designate_focus_effect'])
        self.assertEqual(r.queue[0][0],360)
        r=EventRunner();self.prepare(r);r.globals.clear()
        r.execute(r.definitions['td_designate_focus_effect'])
        self.assertFalse(r.queue)
        self.assertFalse(r.lists)


class WarTests(unittest.TestCase):
    def test_both_doctrine_and_every_target_bill_are_required(self):
        goals=(WarGoal('conquer_state',('A',)),WarGoal('conquer_state',('B',)))
        for doctrine in RULES['doctrines']:
            for approved in (set(),{'A'},{'A','B'}):
                mandate=WarMandate(doctrine,goals,approved)
                self.assertEqual(mandate.unauthorized,
                    doctrine not in RULES['war']['expansion_doctrines'] or approved != {'A','B'})

    def test_annexation_requires_every_state_not_just_one_claim(self):
        self.assertTrue(WarMandate('imperial_expansion',(WarGoal('annex_country',('A','B')),),{'A'}).unauthorized)
        self.assertTrue(WarMandate('imperial_expansion',(WarGoal('annex_country'),),{'A','B'}).unauthorized)

    def test_defense_return_state_and_nonterritorial_wars_are_exempt(self):
        for kind in ('return_state','war_reparations','humiliation'):
            m=WarMandate('status_quo',(WarGoal(kind,('A',)),),set())
            self.assertFalse(m.unauthorized);self.assertEqual(m.tick(),0)
        m=WarMandate('status_quo',(WarGoal('conquer_state',('A',)),),set(),attacker=False)
        self.assertFalse(m.unauthorized)
        self.assertEqual(m.tick(),0)

    def test_disabled_system_adds_no_exhaustion(self):
        m=WarMandate('status_quo',(WarGoal('conquer_state',('A',)),),set(),enabled=False)
        self.assertEqual(m.tick(),0)
        m=WarMandate('status_quo',(WarGoal('conquer_state',('A',)),),set())
        self.assertEqual(m.tick(enabled=False),0)

    def test_cap_peace_and_saved_state(self):
        m=WarMandate('status_quo',(WarGoal('conquer_state',('A',)),),set())
        for _ in range(6):self.assertEqual(m.tick(),2)
        saved=asdict(m)
        restored=deepcopy(m)
        self.assertEqual(asdict(restored),saved)
        self.assertEqual(restored.tick(at_war=False),0)
        self.assertEqual(sum(restored.tick() for _ in range(20)),8)
        self.assertEqual(restored.cumulative_exhaustion,20)

    def test_late_approval_cannot_erase_start_snapshot(self):
        approved=set()
        m=WarMandate('imperial_expansion',(WarGoal('conquer_state',('A',)),),approved)
        approved.add('A');m.doctrine='strategic_frontiers'
        self.assertTrue(m.unauthorized)
        self.assertEqual(m.tick(),2)
        m=WarMandate('imperial_expansion',(WarGoal('conquer_state',('A',)),),{'A'},renounced_regions={'A'})
        self.assertTrue(m.unauthorized)


class NativeWarTests(unittest.TestCase):
    def snapshot(self, runner, war='W1'):
        runner.saved['td_mandate_war']=war
        runner.execute(runner.definitions['td_snapshot_war_mandate_effect'])

    def test_passed_target_does_not_cover_another_target(self):
        r=WarRunner();r.lists['td_approved_claim_regions']={'A'}
        self.snapshot(r)
        self.assertIn('td_unauthorized_war',r.wars['W1']['variables'])
        r.execute(r.definitions['td_war_monthly_effect'])
        self.assertEqual(r.wars['W1']['engine_exhaustion'],2)
        self.assertEqual(r.wars['W2']['engine_exhaustion'],0)

    def test_all_approved_targets_and_expansion_doctrine_are_exempt(self):
        r=WarRunner();r.lists['td_approved_claim_regions']={'A','B'}
        self.snapshot(r)
        self.assertNotIn('td_unauthorized_war',r.wars['W1']['variables'])
        r.execute(r.definitions['td_war_monthly_effect'])
        self.assertEqual(r.wars['W1']['engine_exhaustion'],0)

    def test_missing_doctrine_and_renounced_claim_are_not_authorized(self):
        for missing_doctrine in (False,True):
            r=WarRunner();r.lists['td_approved_claim_regions']={'A','B'}
            if missing_doctrine:
                r.policy.update(policy_context(doctrine='status_quo'))
            else:
                r.lists['td_renounced_regions']={'B'}
            self.snapshot(r)
            self.assertIn('td_unauthorized_war',r.wars['W1']['variables'])

    def test_cap_is_per_war_and_snapshot_is_not_reset(self):
        r=WarRunner()
        self.snapshot(r,'W1');self.snapshot(r,'W2')
        for _ in range(6):r.execute(r.definitions['td_war_monthly_effect'])
        self.assertEqual(r.wars['W1']['engine_exhaustion'],12)
        self.assertEqual(r.wars['W2']['engine_exhaustion'],12)
        r.lists['td_approved_claim_regions']={'A','B'}
        self.snapshot(r,'W1')  # Added war goal rechecks cannot erase bad start.
        self.assertEqual(r.wars['W1']['variables']['td_extra_exhaustion'],12)
        restored=deepcopy(r)
        for _ in range(20):restored.execute(restored.definitions['td_war_monthly_effect'])
        self.assertEqual(restored.wars['W1']['engine_exhaustion'],20)
        self.assertEqual(restored.wars['W2']['engine_exhaustion'],20)

    def test_disabled_and_pre_activation_wars_are_untouched(self):
        r=WarRunner();r.globals.clear()
        self.snapshot(r)
        r.execute(r.definitions['td_war_monthly_effect'])
        self.assertFalse(r.wars['W1']['variables'])
        r.globals['td_system_enabled']=1
        r.execute(r.definitions['td_war_monthly_effect'])
        self.assertEqual(r.wars['W1']['engine_exhaustion'],0)

    def test_another_warleader_cannot_overwrite_original_policy_country(self):
        r=WarRunner()
        r.wars['W1']['variables'].update(td_policy_checked=1,td_policy_country='OTHER',td_extra_exhaustion=6)
        self.snapshot(r)
        self.assertNotIn('td_unauthorized_war',r.wars['W1']['variables'])
        self.assertEqual(r.wars['W1']['variables']['td_policy_country'],'OTHER')
        self.assertEqual(r.wars['W1']['variables']['td_extra_exhaustion'],6)

    def test_nonterritorial_goal_fixtures_create_no_penalty(self):
        r=WarRunner();r.targets['W1'].clear()
        self.snapshot(r)
        r.execute(r.definitions['td_war_monthly_effect'])
        self.assertEqual(r.wars['W1']['engine_exhaustion'],0)


class LocalizationTests(unittest.TestCase):
    def test_every_catalog_has_identical_keys_and_fallback_text(self):
        generated=outputs()
        english={p.name:b.decode('utf-8-sig') for p,b in generated.items() if p.parent.name=='english' and p.suffix=='.yml'}
        for p in (ROOT/'mod/localization/english').glob('*.yml'):
            english.setdefault(p.name,p.read_text(encoding='utf-8-sig'))
        for lang in RULES['localization']['languages']:
            if lang in RULES['localization']['translated']:continue
            for filename,source in english.items():
                p=ROOT/'mod/localization'/lang/filename.replace('_l_english','_l_'+lang)
                self.assertEqual(p.read_text(encoding='utf-8-sig'),source.replace('l_english:',f'l_{lang}:',1))
        self.assertEqual(RULES['localization']['default'],'english')

    def test_missing_fallback_key_is_reported(self):
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            mod=Path(tmp)/'mod';shutil.copytree(ROOT/'mod',mod)
            p=mod/'localization/french/td_gameplay_l_french.yml'
            lines=p.read_text(encoding='utf-8-sig').splitlines()
            p.write_text('\n'.join(l for l in lines if ' td_enable_doctrine:' not in l)+'\n',encoding='utf-8-sig')
            self.assertTrue(any('English/french localization keys differ' in e for e in validate(mod)))


if __name__=='__main__':unittest.main()
