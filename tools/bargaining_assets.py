"""Funded, target-bound bargaining and accountable building commitments."""
import json
from territorial_doctrine.model import RULES


def assets():
    n = RULES['negotiation']
    values = f'''td_pledge_survey_cost = {{
    value = var:td_bill_target.state_population
    multiply = {n['survey_cost_per_person']}
    min = 1000000000
    max = {n['minimum_survey_cost']}
    ceiling = yes
}}
'''
    for key in ('support_bonus', 'trust_weight', 'trust_cap', 'leader_adjustment', 'broken_support'):
        values += f'td_negotiation_{key} = {{ value = {n[key]} }}\n'
    modifiers = ''
    triggers = '''td_active_negotiation_trigger = {
    td_feature_enabled_trigger = yes
    has_variable = td_bill
    has_variable = td_waiting_round
    exists = var:td_bill_target
    scope:td_bill_run = var:td_bill_generation
    scope:td_round_run = var:td_round_epoch
}
'''
    effects = ''
    ratify = 'td_ratify_pledges_effect = {\n'
    release = 'td_release_unratified_pledges_effect = {\n'
    cleanup = 'td_release_all_pledges_effect = {\n'
    monthly = 'td_pledges_monthly_effect = {\n    if = { limit = { td_feature_enabled_trigger = yes }\n'
    journals = ''
    for kind, group, building in (('navy','armed_forces','naval_base'), ('railway','industrialists','railway')):
        extra = 'var:td_bill_target = { is_coastal = yes }' if kind == 'navy' else 'has_technology_researched = railways'
        modifiers += f'td_{kind}_planning = {{ country_bureaucracy_add = -{n["planning_bureaucracy"]} }}\n'
        triggers += f'''td_can_pledge_{kind}_trigger = {{
    td_can_legislate_trigger = yes
    td_allocation_slot_trigger = yes
    has_variable = td_bill
    var:td_bill < 3
    exists = var:td_bill_target
    NOT = {{ has_variable = td_bill_pledge_{kind} }}
    NOT = {{ has_variable = td_pending_{kind} }}
    gold_reserves >= td_pledge_survey_cost
    bureaucracy >= {n['planning_bureaucracy']}
    {extra}
    var:td_bill_target = {{
        is_treaty_port = no
        OR = {{ owner = root NOT = {{ state_region = {{ any_scope_state = {{ owner = root }} }} }} }}
    }}
}}
'''
        effects += f'''td_clear_{kind}_pledge_effect = {{
    if = {{ limit = {{ has_variable = td_bill has_variable = td_bill_pledge_{kind} var:td_{kind}_bill_generation = var:td_bill_generation }}
        remove_variable = td_bill_pledge_{kind}
        change_variable = {{ name = td_bill_allocation_count subtract = 1 }}
    }}
    remove_modifier = td_{kind}_planning
'''
        for suffix in ('target','region','baseline','deadline','acquisition_deadline','started','ratified','owned_at_sign','bill_generation','survey_paid'):
            effects += f'    remove_variable = td_{kind}_{suffix}\n'
        effects += f'    remove_variable = td_pending_{kind}\n}}\n'
        effects += f'''td_sign_{kind}_pledge_effect = {{
    if = {{ limit = {{ td_can_pledge_{kind}_trigger = yes }}
        set_variable = {{ name = td_target value = var:td_bill_target }}
        if = {{ limit = {{ td_bill_target_valid_trigger = yes }}
            set_variable = {{ name = td_{kind}_survey_paid value = td_pledge_survey_cost }}
            add_treasury = {{ value = var:td_{kind}_survey_paid multiply = -1 }}
            add_modifier = td_{kind}_planning
            set_variable = td_pending_{kind}
            set_variable = td_bill_pledge_{kind}
            change_variable = {{ name = td_bill_allocation_count add = 1 }}
            set_variable = {{ name = td_{kind}_bill_generation value = var:td_bill_generation }}
            set_variable = {{ name = td_{kind}_region value = var:td_bill_target.state_region }}
            if = {{ limit = {{ var:td_bill_target = {{ owner = root }} }}
                set_variable = td_{kind}_owned_at_sign
                set_variable = {{ name = td_{kind}_target value = var:td_bill_target }}
                set_variable = {{ name = td_{kind}_baseline value = var:td_bill_target.state_has_building_type_levels:bt:building_{building} }}
            }}
            td_calculate_politics_effect = yes
        }}
    }}
}}
'''
        ratify += f'''    if = {{ limit = {{ has_variable = td_bill_pledge_{kind} has_variable = td_pending_{kind} var:td_{kind}_bill_generation = var:td_bill_generation }}
        set_variable = td_{kind}_ratified
        if = {{ limit = {{ has_variable = td_{kind}_owned_at_sign }}
            set_variable = td_{kind}_started
            set_variable = {{ name = td_{kind}_deadline years = {n['delivery_years']} }}
        }}
        else = {{ set_variable = {{ name = td_{kind}_acquisition_deadline years = {n['acquisition_years']} }} }}
    }}
'''
        release += f'    if = {{ limit = {{ has_variable = td_pending_{kind} NOT = {{ has_variable = td_{kind}_ratified }} }} td_clear_{kind}_pledge_effect = yes }}\n'
        cleanup += f'    td_clear_{kind}_pledge_effect = yes\n'
        monthly += f'''        if = {{ limit = {{ has_variable = td_pending_{kind} has_variable = td_{kind}_ratified }}
            if = {{ limit = {{ NOT = {{ has_variable = td_{kind}_started }} }}
                if = {{ limit = {{ NOT = {{ has_variable = td_{kind}_acquisition_deadline }} }}
                    td_clear_{kind}_pledge_effect = yes
                }}
                else = {{
                    ordered_scope_state = {{
                        limit = {{ state_region = root.var:td_{kind}_region is_treaty_port = no }}
                        order_by = state_population
                        max = 1
                        root = {{
                            set_variable = {{ name = td_{kind}_target value = prev }}
                            set_variable = {{ name = td_{kind}_baseline value = prev.state_has_building_type_levels:bt:building_{building} }}
                            set_variable = td_{kind}_started
                            set_variable = {{ name = td_{kind}_deadline years = {n['delivery_years']} }}
                            remove_variable = td_{kind}_acquisition_deadline
                        }}
                    }}
                }}
            }}
            if = {{ limit = {{ has_variable = td_pending_{kind} has_variable = td_{kind}_started }}
                if = {{ limit = {{ NOT = {{ has_variable = td_{kind}_deadline }} }}
                    ig:ig_{group} = {{
                        remove_modifier = td_pledge_broken
                        add_modifier = {{ name = td_pledge_broken years = {n['broken_years']} }}
                        set_variable = {{ name = td_broken_pledge years = {n['broken_years']} }}
                    }}
                    td_clear_{kind}_pledge_effect = yes
                    trigger_event = td.18
                }}
                else_if = {{ limit = {{ exists = var:td_{kind}_target var:td_{kind}_target = {{
                    owner = root
                    is_treaty_port = no
                    state_has_building_type_levels:bt:building_{building} > root.var:td_{kind}_baseline
                }} }}
                    ig:ig_{group} = {{ remove_modifier = td_pledge_fulfilled add_modifier = {{ name = td_pledge_fulfilled years = {n['fulfilled_years']} }} }}
                    td_clear_{kind}_pledge_effect = yes
                    trigger_event = td.17
                }}
            }}
        }}
'''
        journals += f'''je_td_{kind}_contract = {{
    group = td_journal_group
    is_shown_when_inactive = {{ td_feature_enabled_trigger = yes has_variable = td_pending_{kind} has_variable = td_{kind}_started exists = var:td_{kind}_target }}
    possible = {{ td_feature_enabled_trigger = yes has_variable = td_pending_{kind} has_variable = td_{kind}_started exists = var:td_{kind}_target }}
    can_deactivate = yes
}}
je_td_{kind}_waiting = {{
    group = td_journal_group
    is_shown_when_inactive = {{ td_feature_enabled_trigger = yes has_variable = td_pending_{kind} has_variable = td_{kind}_ratified NOT = {{ has_variable = td_{kind}_started }} }}
    possible = {{ td_feature_enabled_trigger = yes has_variable = td_pending_{kind} has_variable = td_{kind}_ratified NOT = {{ has_variable = td_{kind}_started }} }}
    can_deactivate = yes
}}
'''
    effects += ratify+'}\n'+release+'}\n'+cleanup+'}\n'+monthly+'    }\n}\n'
    out = {'common/script_values/td_bargaining_values.txt':values,
           'common/scripted_triggers/td_bargaining_triggers.txt':triggers,
           'common/static_modifiers/td_bargaining_modifiers.txt':modifiers,
           'common/scripted_effects/td_bargaining.txt':effects,
           'common/journal_entries/td_contracts.txt':journals}
    for lang,label in (('english','en'),('simp_chinese','zh')):
        text = f'l_{lang}:\n'
        for kind,name in (('navy', '海军基地' if label=='zh' else 'Naval Base'),('railway','铁路' if label=='zh' else 'Railway')):
            scope = f"[ROOT.GetCountry.MakeScope.Var('td_{kind}_target').GetState.GetName]"
            entries = {
                'td_'+kind+'_planning':name+('承诺：行政预留' if label=='zh' else ' Commitment: Administrative Reserve'),
                'je_td_'+kind+'_contract':name+('交付：' if label=='zh' else ' Delivery: ')+scope,
                'je_td_'+kind+'_contract_reason':(('只检查此州的净新增一级建筑，三年内交付。建筑与维护费用由原版承担；失地、换原则或读档不重置基线与期限。' if label=='zh' else 'Add one net building level in this state within three years. Construction and upkeep use vanilla budgets. Transfers, doctrine changes and reloads never reset its baseline or deadline.')),
                'je_td_'+kind+'_waiting':name+('承诺等待取得主权' if label=='zh' else ' Commitment Awaiting Sovereignty'),
                'je_td_'+kind+'_waiting_reason':('批准后最多等待五年取得所约区域的普通州。行政预留持续，勘察支出不退还；到期仍未取得则关闭义务，不按未建成建筑惩罚。' if label=='zh' else 'Wait at most five years after ratification to acquire an ordinary state in the contracted region. Administration remains reserved; survey expenses are nonrefundable. If sovereignty is never acquired, the obligation closes without a construction breach.'),
            }
            for key,value in entries.items(): text += f' {key}:0 '+json.dumps(value,ensure_ascii=False)+'\n'
        out[f'localization/{lang}/td_bargaining_l_{lang}.yml']=text
    return out
