"""Permanent, opt-in fiscal, recruitment and public-service accounting.

Budget figures are engine observations, not predicted yields or extra charges.
The score mapping is an explicit gameplay proxy for distributional bargaining.
"""
import json
from territorial_doctrine.model import RULES

MODULES = ('fiscal', 'recruitment', 'services')
INSTITUTIONS = {'education': 'institution_schools', 'health': 'institution_health_system'}
TAX_BEARERS = {
    'land_based_taxation': ('landowners', 'rural_folk'),
    'per_capita_based_taxation': ('trade_unions', 'rural_folk', 'petty_bourgeoisie'),
    'consumption_based_taxation': ('trade_unions', 'rural_folk', 'petty_bourgeoisie'),
    'proportional_taxation': ('landowners', 'industrialists', 'trade_unions', 'petty_bourgeoisie'),
    'graduated_taxation': ('landowners', 'industrialists'),
}


def assets():
    rules = RULES['civic_accounting']
    values = 'td_tax_rank = {\n    value = 0\n'
    for rank, level in enumerate(('very_low', 'low', 'medium', 'high', 'very_high'), 1):
        values += f'    if = {{ limit = {{ tax_level = {level} }} value = {rank} }}\n'
    values += '}\n'
    for name, key in INSTITUTIONS.items():
        values += f'''td_{name}_level = {{
    value = 0
    if = {{ limit = {{ has_institution = {key} }} value = institution_investment_level:{key} }}
}}
'''
    for name in ('tax_step_score', 'service_step_score', 'bureaucracy_pressure_score', 'component_cap'):
        values += f'td_civic_{name} = {{ value = {rules[name]} }}\n'
    values += '''td_civic_tax_delta = { value = td_tax_rank subtract = var:td_bill_tax_baseline }
td_civic_tax_pressure = { value = td_civic_tax_delta max = 0 multiply = td_civic_tax_step_score min = td_civic_component_cap }
td_civic_education_cuts = { value = var:td_bill_education_baseline subtract = td_education_level max = 0 }
td_civic_health_cuts = { value = var:td_bill_health_baseline subtract = td_health_level max = 0 }
td_mobilization_magnitude = { value = legitimacy subtract = 50 divide = 50 }
'''
    triggers = '''td_civic_any_enabled_trigger = {
    td_feature_enabled_trigger = yes
    OR = { has_global_variable = td_fiscal_enabled has_global_variable = td_recruitment_enabled has_global_variable = td_services_enabled }
}
td_civic_expansion_phase_trigger = {
    td_expansion_doctrine_trigger = yes
    OR = { has_variable = td_expansion_program AND = { has_variable = td_bill var:td_bill = 1 } }
}
td_conscription_active_trigger = {
    td_feature_enabled_trigger = yes
    has_global_variable = td_recruitment_enabled
    has_variable = td_expansion_program
    td_expansion_doctrine_trigger = yes
    is_at_war = yes
    any_scope_war = { attacker_warleader = prev }
}
td_can_raise_budget_tax_trigger = {
    td_feature_enabled_trigger = yes
    has_global_variable = td_fiscal_enabled
    NOT = { has_variable = td_tax_adjustment_wait }
    NOT = { tax_level = very_high }
    net_total_income < 0
    NOT = { has_modifier = country_bankruptcy }
}
td_can_lower_budget_tax_trigger = {
    td_feature_enabled_trigger = yes
    has_global_variable = td_fiscal_enabled
    NOT = { has_variable = td_tax_adjustment_wait }
    NOT = { tax_level = very_low }
    net_total_income > 0
    gold_reserves > 0
    NOT = { has_modifier = country_bankruptcy }
}
'''
    # Tax levels are enumerated explicitly: no guessed integer setter/rank.
    effects = '''td_snapshot_civic_bill_effect = {
    set_variable = { name = td_bill_tax_baseline value = td_tax_rank }
    set_variable = { name = td_bill_education_baseline value = td_education_level }
    set_variable = { name = td_bill_health_baseline value = td_health_level }
}
td_refresh_civic_accounts_effect = {
    if = { limit = { td_civic_any_enabled_trigger = yes }
        if = { limit = { NOT = { has_variable = td_service_reference_education } }
            set_variable = { name = td_service_reference_education value = td_education_level }
            set_variable = { name = td_service_reference_health value = td_health_level }
        }
        set_variable = { name = td_civic_phase value = 0 }
        if = { limit = { td_civic_expansion_phase_trigger = yes } set_variable = { name = td_civic_phase value = 1 } }
        set_variable = { name = td_account_fiscal_enabled value = 0 }
        set_variable = { name = td_account_recruitment_enabled value = 0 }
        set_variable = { name = td_account_services_enabled value = 0 }
        if = { limit = { has_global_variable = td_fiscal_enabled } set_variable = { name = td_account_fiscal_enabled value = 1 } }
        if = { limit = { has_global_variable = td_recruitment_enabled } set_variable = { name = td_account_recruitment_enabled value = 1 } }
        if = { limit = { has_global_variable = td_services_enabled } set_variable = { name = td_account_services_enabled value = 1 } }
        set_variable = { name = td_weekly_balance value = net_total_income }
        set_variable = { name = td_weekly_expenses value = total_expenses }
        set_variable = { name = td_weekly_funding_gap value = { value = net_total_income multiply = -1 max = 0 } }
        set_variable = { name = td_budget_tax_rank value = td_tax_rank }
        set_variable = { name = td_budget_tax_law value = 0 }
'''
    for index, law in enumerate(TAX_BEARERS, 1):
        effects += f'        if = {{ limit = {{ has_law = law_type:law_{law} }} set_variable = {{ name = td_budget_tax_law value = {index} }} }}\n'
    effects += '''        set_variable = { name = td_service_education value = td_education_level }
        set_variable = { name = td_service_health value = td_health_level }
        set_variable = { name = td_service_education_gap value = { value = var:td_service_reference_education subtract = td_education_level max = 0 } }
        set_variable = { name = td_service_health_gap value = { value = var:td_service_reference_health subtract = td_health_level max = 0 } }
        set_variable = { name = td_bureaucracy_balance value = bureaucracy }
        set_variable = { name = td_bureaucracy_gap value = { value = bureaucracy multiply = -1 max = 0 } }
        set_variable = { name = td_service_pressure_percent value = { value = var:td_bureaucracy_gap divide = { value = bureaucracy_usage max = 1 } multiply = 100 min = 100 } }
        set_variable = { name = td_recruitment_active value = 0 }
        set_variable = { name = td_recruitment_percent value = 0 }
        if = { limit = { td_conscription_active_trigger = yes }
            set_variable = { name = td_recruitment_active value = 1 }
            set_variable = { name = td_recruitment_percent value = { value = td_mobilization_magnitude min = 1 max = -1 multiply = '''+str(rules['conscription_max_multiplier']*100)+''' } }
        }
    }
}
td_clear_conscription_state_effect = {
    remove_modifier = td_conscription_high_trust
    remove_modifier = td_conscription_low_trust
}
td_maybe_clear_conscription_state_effect = {
    if = { limit = { OR = { NOT = { has_variable = td_recorded_owner } NOT = { var:td_recorded_owner = owner } } } td_clear_conscription_state_effect = yes }
}
td_refresh_country_civic_effect = {
    every_scope_state = { td_clear_conscription_state_effect = yes }
    if = { limit = { td_civic_any_enabled_trigger = yes }
        td_refresh_civic_accounts_effect = yes
        if = { limit = { td_conscription_active_trigger = yes }
            if = { limit = { legitimacy > 50 }
                set_variable = { name = td_mobilization_scale value = { value = td_mobilization_magnitude min = 1 max = 0 } }
                every_scope_state = { if = { limit = { is_treaty_port = no } add_modifier = { name = td_conscription_high_trust multiplier = owner.var:td_mobilization_scale } } }
            }
            else_if = { limit = { legitimacy < 50 }
                set_variable = { name = td_mobilization_scale value = { value = td_mobilization_magnitude multiply = -1 min = 1 max = 0 } }
                every_scope_state = { if = { limit = { is_treaty_port = no } add_modifier = { name = td_conscription_low_trust multiplier = owner.var:td_mobilization_scale } } }
            }
        }
    }
}
td_civic_bill_scores_effect = {
    every_interest_group = {
        set_variable = { name = td_component_fiscal value = 0 }
        set_variable = { name = td_component_services value = 0 }
    }
    if = { limit = { td_civic_any_enabled_trigger = yes }
        td_refresh_civic_accounts_effect = yes
        if = { limit = { has_variable = td_bill_tax_baseline has_global_variable = td_fiscal_enabled }
            set_variable = { name = td_bill_tax_pressure value = td_civic_tax_pressure }
'''
    for index, (law, groups) in enumerate(TAX_BEARERS.items(), 1):
        effects += f'            if = {{ limit = {{ var:td_budget_tax_law = {index} }}\n'
        for group in groups:
            effects += f'                ig:ig_{group} = {{ set_variable = {{ name = td_component_fiscal value = {{ value = owner.var:td_bill_tax_pressure multiply = -1 }} }} }}\n'
        effects += '            }\n'
    effects += '''        }
        if = { limit = { has_variable = td_bill_education_baseline has_global_variable = td_services_enabled }
            set_variable = { name = td_bill_education_cuts value = td_civic_education_cuts }
            set_variable = { name = td_bill_health_cuts value = td_civic_health_cuts }
            ig:ig_intelligentsia = { set_variable = { name = td_component_services value = { value = owner.var:td_bill_education_cuts multiply = td_civic_service_step_score multiply = -1 } } }
            ig:ig_trade_unions = { set_variable = { name = td_component_services value = { value = owner.var:td_bill_health_cuts multiply = td_civic_service_step_score multiply = -1 } } }
            if = { limit = { bureaucracy < 0 }
                ig:ig_intelligentsia = { change_variable = { name = td_component_services subtract = td_civic_bureaucracy_pressure_score } }
                ig:ig_trade_unions = { change_variable = { name = td_component_services subtract = td_civic_bureaucracy_pressure_score } }
                ig:ig_petty_bourgeoisie = { change_variable = { name = td_component_services subtract = td_civic_bureaucracy_pressure_score } }
            }
        }
    }
    every_interest_group = {
        set_variable = { name = td_component_services value = { value = var:td_component_services max = { value = td_civic_component_cap multiply = -1 } } }
        change_variable = { name = td_score add = var:td_component_fiscal add = var:td_component_services }
    }
}
'''
    for direction, trigger, levels in (
        ('raise', 'td_can_raise_budget_tax_trigger', ('very_low', 'low', 'medium', 'high', 'very_high')),
        ('lower', 'td_can_lower_budget_tax_trigger', ('very_high', 'high', 'medium', 'low', 'very_low'))):
        effects += f'td_{direction}_budget_tax_effect = {{\n    if = {{ limit = {{ {trigger} = yes }}\n'
        for current, target in zip(levels, levels[1:]):
            branch = 'if' if current == levels[0] else 'else_if'
            effects += f'        {branch} = {{ limit = {{ tax_level = {current} }} set_tax_level = {target} }}\n'
        effects += f'''        set_variable = {{ name = td_tax_adjustment_wait days = {rules['tax_adjustment_days']} }}
        td_refresh_country_civic_effect = yes
        if = {{ limit = {{ has_variable = td_bill exists = var:td_bill_target }} td_calculate_politics_effect = yes }}
    }}
}}
'''
    effects += '''td_return_peace_budget_effect = {
    if = { limit = { td_civic_any_enabled_trigger = yes has_variable = td_expansion_program NOT = { AND = { has_variable = td_bill var:td_bill = 1 } } }
        remove_variable = td_expansion_program
        td_refresh_country_civic_effect = yes
    }
}
'''
    decisions = ''
    for module in MODULES:
        decisions += f'''td_enable_{module}_accounting = {{
    is_shown = {{ is_player = yes td_feature_enabled_trigger = yes NOT = {{ has_global_variable = td_{module}_enabled }} }}
    possible = {{ td_feature_enabled_trigger = yes NOT = {{ has_global_variable = td_{module}_enabled }} }}
    when_taken = {{
        if = {{ limit = {{ td_feature_enabled_trigger = yes NOT = {{ has_global_variable = td_{module}_enabled }} }}
            set_global_variable = td_{module}_enabled
            every_country = {{ td_refresh_country_civic_effect = yes }}
        }}
    }}
    ai_chance = {{ value = 0 }}
}}
'''
    decisions += '''td_civic_accounts = {
    is_shown = { is_player = yes td_civic_any_enabled_trigger = yes }
    when_taken = { td_refresh_country_civic_effect = yes trigger_event = td.40 }
    ai_chance = { value = 0 }
}
'''
    for direction in ('raise', 'lower'):
        decisions += f'''td_{direction}_budget_tax = {{
    is_shown = {{ is_player = yes td_feature_enabled_trigger = yes has_global_variable = td_fiscal_enabled }}
    possible = {{ td_can_{direction}_budget_tax_trigger = yes }}
    when_taken = {{ td_{direction}_budget_tax_effect = yes }}
    ai_chance = {{ value = 0 }}
}}
'''
    decisions += '''td_return_peace_budget = {
    is_shown = { is_player = yes td_civic_any_enabled_trigger = yes has_variable = td_expansion_program }
    possible = { NOT = { AND = { has_variable = td_bill var:td_bill = 1 } } }
    when_taken = { td_return_peace_budget_effect = yes }
    ai_chance = { value = 0 }
}
'''
    events = '''td.40 = {
    type = country_event
    title = td.40.t
    desc = td.40.d
    flavor = td.flavor
    immediate = { if = { limit = { td_civic_any_enabled_trigger = yes } td_refresh_civic_accounts_effect = yes } }
    option = { name = td.close ai_chance = { base = 0 } }
}
'''
    modifiers = f'''td_conscription_high_trust = {{ state_conscription_rate_mult = {rules['conscription_max_multiplier']} }}
td_conscription_low_trust = {{ state_conscription_rate_mult = {-rules['conscription_max_multiplier']} }}
'''
    out = {
        'common/script_values/td_civic_values.txt': values,
        'common/scripted_triggers/td_civic_triggers.txt': triggers,
        'common/scripted_effects/td_civic.txt': effects,
        'common/static_modifiers/td_civic_modifiers.txt': modifiers,
        'common/decisions/td_civic_decisions.txt': decisions,
        'events/td_civic_events.txt': events,
    }
    for lang, zh in (('english', False), ('simp_chinese', True)):
        entries = {}
        for module, cn, en in (('fiscal', '领土财政核算', 'Territorial Fiscal Accounting'), ('recruitment', '征募政治响应', 'Political Recruitment Response'), ('services', '公共服务责任核算', 'Public-Service Responsibility Accounting')):
            entries['td_enable_'+module+'_accounting'] = ('永久启用' if zh else 'Permanently Enable ')+(cn if zh else en)
            entries['td_enable_'+module+'_accounting_desc'] = ('为整个存档所有国家永久开启此模块；必须先启用国家领土原则。没有关闭入口。扩张计划与和平阶段可变化，原有合同和债务继续承担。' if zh else 'Permanently enable this module for all countries in this save, after activating Territorial Doctrine. No disable action. Expansion programs and peaceful budgeting can change; existing contracts and debts persist.')
        module_tips = {
            'fiscal': ('读取实际税制与周预算缺口，可按收支条件调整原版税档；当前法案中的实际加税会影响承担负担集团的支持。', 'Read the actual tax law and weekly funding gap; adjust vanilla tax settings under budget conditions. Actual tax increases affect burden-bearing groups in the current bill.'),
            'recruitment': ('已批准扩张计划、扩张原则且作为进攻方战争领袖时，根据合法性相对调整征募潜力，最多±10%；和平与防御不产生此项修正。', 'With an approved expansion program, an expansion doctrine and offensive war leadership, legitimacy adjusts relative conscription potential by at most +/-10%. No modifier in peace or on defense.'),
            'services': ('读取原版教育/医疗投入及行政缺口，实际投入减少或行政不足进入集团谈判；和平仍显示恢复缺口。机构投入由实际政策决定。', 'Read vanilla education/health investment and bureaucracy shortfalls. Actual cuts or administrative shortages enter group deliberation; peaceful budgeting still reports restoration gaps. Actual policy sets institution investment.'),
        }
        for module, tips in module_tips.items():
            entries['td_enable_'+module+'_accounting_desc'] += ' ' + tips[0 if zh else 1]
        entries.update({
            'td_civic_accounts': '查看领土财政、征募与服务账目' if zh else 'View Territorial Fiscal, Recruitment and Service Accounts',
            'td_civic_accounts_desc': '查看永久模块状态与实际原版预算、税制、行政余额和机构投入。数字是当前观测，不是未来税收预测。未开启模块不产生额外效果。' if zh else 'Review module flags and observed vanilla budget, tax law, administration and institutions. Figures are current observations, not revenue forecasts. Disabled modules produce no additional effect.',
            'td_raise_budget_tax': '赤字预算：提高一档原版税负' if zh else 'Deficit Budget: Raise Vanilla Tax One Step',
            'td_raise_budget_tax_desc': '财政模块开启且实际周预算为负时，可真实提高一档原版税负。30天内不重复调整。税制法律保持，实际税收与生活影响由原版计算；当前法案读取真实增加的负担。' if zh else 'With fiscal accounting and a negative observed weekly balance, raise the actual vanilla tax setting one step. A 30-day adjustment cooldown applies. Vanilla computes revenue and living costs; the current bill reads the increased burden under its tax law.',
            'td_lower_budget_tax': '盈余预算：降低一档原版税负' if zh else 'Surplus Budget: Lower Vanilla Tax One Step',
            'td_lower_budget_tax_desc': '周预算为正且有黄金储备时，可真实降低一档税负；30天内不重复调整。盈余不是保证降税后仍有盈余，须观察下一次原版预算。不会制造额外支持或退款。' if zh else 'With a positive observed weekly balance and gold reserves, lower the actual vanilla tax setting one step with a 30-day cooldown. A current surplus does not guarantee a surplus after the cut; check the next vanilla budget. No free support or refund.',
            'td_return_peace_budget': '结束扩张计划，转入和平预算' if zh else 'End Expansion Program and Return to Peaceful Budgeting',
            'td_return_peace_budget_desc': '结束临时扩张计划及其征募修正；正在审议的扩张法案须先处理。永久模块、债务、年度接纳和已批准建设合同保留。新扩张计划须重新通过目标法案，不能免费恢复旧动员修正。' if zh else 'End the temporary expansion program and its recruitment modifier; resolve any active claim bill first. Module flags, debts, annual admission and ratified building contracts persist. Another program requires another approved target bill.',
            'td_conscription_high_trust': '扩张动员：高合法性征募' if zh else 'Expansion Mobilization: Higher-Legitimacy Recruitment',
            'td_conscription_low_trust': '扩张动员：低合法性征募' if zh else 'Expansion Mobilization: Lower-Legitimacy Recruitment',
            'td_conscription_high_trust_desc': '批准扩张计划且作为进攻方战争领袖时，征募潜力最多相对增加10%；具体数值依合法性计算，不自动征兵，军事制度和人口继续限制实际兵力。' if zh else 'An approved expansion program led in an offensive war can add at most 10% relative conscription potential, scaled by legitimacy. No units are automatically raised; military institutions and population still constrain forces.',
            'td_conscription_low_trust_desc': '相同动员条件下，低合法性最多相对减少10%征募潜力；和平、防御方与没有批准计划时无此修正。' if zh else 'Under the same mobilization conditions, low legitimacy reduces relative conscription potential by at most 10%. No modifier in peace, on defense or without an approved program.',
            'td.40.t': '领土政策账目' if zh else 'Territorial Policy Accounts',
        })
        def v(name): return "[ROOT.GetCountry.MakeScope.Var('"+name+"').GetValue]"
        if zh:
            entries['td.40.d'] = f"永久模块（1开启/0关闭）：财政{v('td_account_fiscal_enabled')}，征募{v('td_account_recruitment_enabled')}，服务{v('td_account_services_enabled')}。阶段（1扩张/0和平）：{v('td_civic_phase')}。\n\n原版周余额：{v('td_weekly_balance')}；周支出：{v('td_weekly_expenses')}；周缺口：{v('td_weekly_funding_gap')}。税档（1最低至5最高）：{v('td_budget_tax_rank')}；税制（0未知/1土地/2人头/3消费/4比例/5累进）：{v('td_budget_tax_law')}。\n\n可用行政：{v('td_bureaucracy_balance')}；行政缺口：{v('td_bureaucracy_gap')}；缺口占使用量：{v('td_service_pressure_percent')}%。教育/医疗投入：{v('td_service_education')}/{v('td_service_health')}级；相较首次核算缺口：{v('td_service_education_gap')}/{v('td_service_health_gap')}级。该比例是预算压力指标，不是机构效率或居民服务覆盖率。\n\n征募修正实际开启：{v('td_recruitment_active')}；相对征募潜力变化：{v('td_recruitment_percent')}%。原版军队费用与服务机构费用只记账，不重复收取。具体国家、人口税负与未来项目收益尚未估算。"
        else:
            entries['td.40.d'] = f"Permanent modules (1 enabled/0 disabled): fiscal {v('td_account_fiscal_enabled')}, recruitment {v('td_account_recruitment_enabled')}, services {v('td_account_services_enabled')}. Phase (1 expansion/0 peace): {v('td_civic_phase')}.\n\nVanilla weekly balance: {v('td_weekly_balance')}; expenses: {v('td_weekly_expenses')}; funding gap: {v('td_weekly_funding_gap')}. Tax rank (1 lowest to 5 highest): {v('td_budget_tax_rank')}; law (0 unknown/1 land/2 per-capita/3 consumption/4 proportional/5 graduated): {v('td_budget_tax_law')}.\n\nAvailable bureaucracy: {v('td_bureaucracy_balance')}; shortfall: {v('td_bureaucracy_gap')}; shortfall/usage: {v('td_service_pressure_percent')}%. Education/health investment: {v('td_service_education')}/{v('td_service_health')}; gaps against first accounting: {v('td_service_education_gap')}/{v('td_service_health_gap')}. This ratio is budget pressure, not institution efficiency or population coverage.\n\nRecruitment modifier active: {v('td_recruitment_active')}; relative conscription potential change: {v('td_recruitment_percent')}%. Vanilla military and institutional expenses are recorded, never charged twice. Population-specific tax burdens and future project returns are unassessed."
        loc = 'l_'+lang+':\n'
        for key, value in entries.items(): loc += f' {key}:0 '+json.dumps(value,ensure_ascii=False)+'\n'
        out[f'localization/{lang}/td_civic_l_{lang}.yml'] = loc
    return out
