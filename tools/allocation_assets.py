"""Target-bound, paid distribution contracts; no fictional property/pop rewards."""
import json
from territorial_doctrine.model import RULES

CONTRACTS = {
    'religious_schools': {'zh':'宗教办学扩展','en':'Religious Education Expansion','groups':{'devout':10},'opposition':{'intelligentsia':-5},'institution':'schools','law':'religious_schools'},
    'public_schools': {'zh':'公共教育扩展','en':'Public Education Expansion','groups':{'intelligentsia':10},'opposition':{'devout':-5},'institution':'schools','law':'public_schools'},
    'health_services': {'zh':'医疗服务扩展','en':'Health Service Expansion','groups':{'trade_unions':10},'opposition':{},'institution':'health_system'},
    'land_settlement': {'zh':'维持现有地主土地制度','en':'Maintain the Existing Landlord Regime','groups':{'landowners':10},'opposition':{'rural_folk':-5},'hold':True},
    'low_tax': {'zh':'一年低税保障','en':'One-Year Low-Tax Guarantee','groups':{'rural_folk':10,'petty_bourgeoisie':10},'opposition':{},'hold':True},
}


def assets():
    n=RULES['negotiation'];a=RULES['allocation']
    triggers=f'''td_allocation_slot_trigger = {{
    has_variable = td_bill_allocation_count
    var:td_bill_allocation_count < {a['slots_per_bill']}
}}
'''
    effects='';modifiers='';journals='';decisions='';options=''
    ratify='td_ratify_allocations_effect = {\n'
    release='td_release_unratified_allocations_effect = {\n'
    cleanup='td_release_all_allocations_effect = {\n'
    validate='td_validate_unratified_allocations_effect = {\n'
    monthly='td_allocations_monthly_effect = {\n    if = { limit = { td_feature_enabled_trigger = yes }\n'
    scores='td_allocation_scores_effect = {\n    every_interest_group = { set_variable = { name = td_component_allocation value = 0 } }\n'
    for kind,c in CONTRACTS.items():
        hold=c.get('hold',False);inst=c.get('institution');law=c.get('law')
        continuation=[]
        if law:continuation.append(f'has_law = law_type:law_{law}')
        if kind=='religious_schools':continuation.append(f'religion = var:td_{kind}_faith')
        if inst:continuation.append(f'has_institution = institution_{inst}')
        if kind=='land_settlement':
            continuation.append(f'''OR = {{ AND = {{ var:td_{kind}_land_law = 1 has_law = law_type:law_serfdom }} AND = {{ var:td_{kind}_land_law = 2 has_law = law_type:law_tenant_farmers }} }}''')
        if kind=='low_tax':continuation.append('OR = { tax_level = very_low tax_level = low }')
        triggers+=f'td_{kind}_conditions_trigger = {{\n    '+ '\n    '.join(continuation)+'\n}\n'
        eligibility=[]
        if inst:
            eligibility.extend([f'has_institution = institution_{inst}',f'institution_investment_level:institution_{inst} < institution:institution_{inst}.investment_max'])
        if law:eligibility.append(f'has_law = law_type:law_{law}')
        if kind in ('religious_schools','public_schools'):
            other='public_schools' if kind=='religious_schools' else 'religious_schools'
            eligibility.append(f'NOT = {{ has_variable = td_pending_{other} }}')
        if kind=='land_settlement':eligibility.append('OR = { has_law = law_type:law_serfdom has_law = law_type:law_tenant_farmers }')
        if kind=='low_tax':eligibility.extend(['has_global_variable = td_fiscal_enabled','OR = { tax_level = very_low tax_level = low }','net_total_income >= 0'])
        triggers+=f'''td_can_allocate_{kind}_trigger = {{
    td_can_legislate_trigger = yes
    td_allocation_slot_trigger = yes
    has_variable = td_bill
    var:td_bill < 3
    exists = var:td_bill_target
    NOT = {{ has_variable = td_pending_{kind} }}
    gold_reserves >= td_pledge_survey_cost
    bureaucracy >= {n['planning_bureaucracy']}
    var:td_bill_target = {{ is_treaty_port = no OR = {{ owner = root NOT = {{ state_region = {{ any_scope_state = {{ owner = root }} }} }} }} }}
    '''+'\n    '.join(eligibility)+'\n}\n'
        modifiers+=f'td_{kind}_planning = {{ country_bureaucracy_add = -{n["planning_bureaucracy"]} }}\n'
        effects+=f'''td_clear_{kind}_allocation_effect = {{
    if = {{ limit = {{ has_variable = td_bill has_variable = td_bill_{kind} var:td_{kind}_bill_generation = var:td_bill_generation }}
        remove_variable = td_bill_{kind}
        change_variable = {{ name = td_bill_allocation_count subtract = 1 }}
    }}
    remove_modifier = td_{kind}_planning
'''
        suffixes=['region','target','bill_generation','ratified','started','deadline','acquisition_deadline','survey_paid']
        if inst:suffixes.append('baseline')
        if kind=='religious_schools':suffixes.append('faith')
        if kind=='land_settlement':suffixes.append('land_law')
        if hold:suffixes.append('holding')
        for suffix in suffixes:
            effects+=f'    remove_variable = td_{kind}_{suffix}\n'
        effects+=f'    remove_variable = td_pending_{kind}\n}}\n'
        baseline=(f'set_variable = {{ name = td_{kind}_baseline value = institution_investment_level:institution_{inst} }}' if inst else '')
        effects+=f'''td_sign_{kind}_allocation_effect = {{
    if = {{ limit = {{ td_can_allocate_{kind}_trigger = yes }}
        set_variable = {{ name = td_target value = var:td_bill_target }}
        if = {{ limit = {{ td_bill_target_valid_trigger = yes }}
            set_variable = {{ name = td_{kind}_survey_paid value = td_pledge_survey_cost }}
            add_treasury = {{ value = var:td_{kind}_survey_paid multiply = -1 }}
            add_modifier = td_{kind}_planning
            set_variable = td_pending_{kind}
            set_variable = td_bill_{kind}
            change_variable = {{ name = td_bill_allocation_count add = 1 }}
            set_variable = {{ name = td_{kind}_bill_generation value = var:td_bill_generation }}
            set_variable = {{ name = td_{kind}_region value = var:td_bill_target.state_region }}
            {baseline}
'''
        if kind=='religious_schools':effects+=f'            set_variable = {{ name = td_{kind}_faith value = religion }}\n'
        if kind=='land_settlement':
            effects+=f'''            set_variable = {{ name = td_{kind}_land_law value = 0 }}
            if = {{ limit = {{ has_law = law_type:law_serfdom }} set_variable = {{ name = td_{kind}_land_law value = 1 }} }}
            if = {{ limit = {{ has_law = law_type:law_tenant_farmers }} set_variable = {{ name = td_{kind}_land_law value = 2 }} }}
'''
        effects+=f'''            if = {{ limit = {{ var:td_bill_target = {{ owner = root }} }} set_variable = {{ name = td_{kind}_target value = var:td_bill_target }} }}
            td_calculate_politics_effect = yes
        }}
    }}
}}
'''
        start=f'''set_variable = td_{kind}_started
            set_variable = {{ name = td_{kind}_deadline years = {a['maintenance_delivery_years'] if hold else n['delivery_years']} }}'''
        if hold:start+=f'\n            set_variable = {{ name = td_{kind}_holding years = {a["maintenance_years"]} }}'
        ratify+=f'''    if = {{ limit = {{ has_variable = td_bill_{kind} has_variable = td_pending_{kind} var:td_{kind}_bill_generation = var:td_bill_generation }}
        set_variable = td_{kind}_ratified
        if = {{ limit = {{ exists = var:td_{kind}_target }} {start} }}
        else = {{ set_variable = {{ name = td_{kind}_acquisition_deadline years = {n['acquisition_years']} }} }}
    }}
'''
        release+=f'    if = {{ limit = {{ has_variable = td_pending_{kind} NOT = {{ has_variable = td_{kind}_ratified }} }} td_clear_{kind}_allocation_effect = yes }}\n'
        cleanup+=f'    td_clear_{kind}_allocation_effect = yes\n'
        validate+=f'    if = {{ limit = {{ has_variable = td_pending_{kind} NOT = {{ has_variable = td_{kind}_ratified }} NOT = {{ td_{kind}_conditions_trigger = yes }} }} td_clear_{kind}_allocation_effect = yes }}\n'
        broken='';fulfilled=''
        for group in c['groups']:
            broken+=f'ig:ig_{group} = {{ remove_modifier = td_pledge_broken add_modifier = {{ name = td_pledge_broken years = {n["broken_years"]} }} set_variable = {{ name = td_broken_pledge years = {n["broken_years"]} }} }}\n'
            fulfilled+=f'ig:ig_{group} = {{ remove_modifier = td_pledge_fulfilled add_modifier = {{ name = td_pledge_fulfilled years = {n["fulfilled_years"]} }} }}\n'
        effects+=f'td_breach_{kind}_allocation_effect = {{\n    {broken}    td_clear_{kind}_allocation_effect = yes\n    trigger_event = td.18\n}}\n'
        monthly+=f'''        if = {{ limit = {{ has_variable = td_pending_{kind} has_variable = td_{kind}_ratified }}
            if = {{ limit = {{ NOT = {{ td_{kind}_conditions_trigger = yes }} }} td_breach_{kind}_allocation_effect = yes }}
            else = {{
                if = {{ limit = {{ NOT = {{ has_variable = td_{kind}_started }} }}
                    if = {{ limit = {{ NOT = {{ has_variable = td_{kind}_acquisition_deadline }} }} td_clear_{kind}_allocation_effect = yes }}
                    else = {{ ordered_scope_state = {{
                        limit = {{ state_region = root.var:td_{kind}_region is_treaty_port = no }}
                        order_by = state_population
                        max = 1
                        root = {{
                            set_variable = {{ name = td_{kind}_target value = prev }}
                            {start}
                            remove_variable = td_{kind}_acquisition_deadline
                        }}
                    }} }}
                }}
                if = {{ limit = {{ has_variable = td_pending_{kind} has_variable = td_{kind}_started }}
                    if = {{ limit = {{ NOT = {{ has_variable = td_{kind}_deadline }} }} td_breach_{kind}_allocation_effect = yes }}
                    else_if = {{ limit = {{ exists = var:td_{kind}_target var:td_{kind}_target = {{ owner = root is_treaty_port = no'''
        if inst:monthly+=' is_incorporated = yes'
        monthly+=' } '
        if hold:monthly+=f'NOT = {{ has_variable = td_{kind}_holding }}'
        else:monthly+=f'institution_investment_level:institution_{inst} > var:td_{kind}_baseline'
        monthly+=f''' }}
                        {fulfilled}td_clear_{kind}_allocation_effect = yes
                        trigger_event = td.17
                    }}
                }}
            }}
        }}
'''
        scores+=f'''    if = {{ limit = {{ has_variable = td_bill_{kind} has_variable = td_pending_{kind} var:td_{kind}_bill_generation = var:td_bill_generation }}
'''
        for group,amount in {**c['groups'],**c['opposition']}.items():
            score=n['support_bonus'] if amount>0 else -a['opportunity_score']
            scores+=f'        ig:ig_{group} = {{ change_variable = {{ name = td_component_allocation add = {score} }} }}\n'
        scores+='    }\n'
        decisions+=f'''td_allocate_{kind} = {{
    is_shown = {{ td_feature_enabled_trigger = yes has_variable = td_bill var:td_bill < 3 }}
    possible = {{ td_can_allocate_{kind}_trigger = yes }}
    when_taken = {{ td_sign_{kind}_allocation_effect = yes }}
    ai_chance = {{ value = 0 }}
}}
'''
        options+=f'    option = {{ name = td.allocate.{kind} trigger = {{ td_active_negotiation_trigger = yes td_can_allocate_{kind}_trigger = yes }} td_sign_{kind}_allocation_effect = yes trigger_event = td.32 }}\n'
        journals+=f'''je_td_{kind}_allocation = {{
    group = td_journal_group
    is_shown_when_inactive = {{ td_feature_enabled_trigger = yes has_variable = td_pending_{kind} has_variable = td_{kind}_started exists = var:td_{kind}_target }}
    possible = {{ td_feature_enabled_trigger = yes has_variable = td_pending_{kind} has_variable = td_{kind}_started exists = var:td_{kind}_target }}
    can_deactivate = yes
}}
je_td_{kind}_allocation_waiting = {{
    group = td_journal_group
    is_shown_when_inactive = {{ td_feature_enabled_trigger = yes has_variable = td_pending_{kind} has_variable = td_{kind}_ratified NOT = {{ has_variable = td_{kind}_started }} }}
    possible = {{ td_feature_enabled_trigger = yes has_variable = td_pending_{kind} has_variable = td_{kind}_ratified NOT = {{ has_variable = td_{kind}_started }} }}
    can_deactivate = yes
}}
je_td_{kind}_allocation_proposed = {{
    group = td_journal_group
    is_shown_when_inactive = {{ td_feature_enabled_trigger = yes has_variable = td_pending_{kind} NOT = {{ has_variable = td_{kind}_ratified }} has_variable = td_bill exists = var:td_bill_target }}
    possible = {{ td_feature_enabled_trigger = yes has_variable = td_pending_{kind} NOT = {{ has_variable = td_{kind}_ratified }} has_variable = td_bill exists = var:td_bill_target }}
    can_deactivate = yes
}}
'''
    scores+='    every_interest_group = { change_variable = { name = td_score add = var:td_component_allocation } }\n}\n'
    effects+=ratify+'}\n'+release+'}\n'+cleanup+'}\n'+validate+'}\n'+monthly+'    }\n}\n'+scores
    values=''.join(f'td_allocation_{key} = {{ value = {a[key]} }}\n' for key in ('opportunity_score','religion_majority_threshold','market_access_threshold'))
    out={'common/script_values/td_allocation_values.txt':values,
         'common/scripted_triggers/td_allocation_triggers.txt':triggers,
         'common/scripted_effects/td_allocations.txt':effects,
         'common/static_modifiers/td_allocation_modifiers.txt':modifiers,
         'common/decisions/td_allocation_decisions.txt':decisions,
         'common/journal_entries/td_allocations.txt':journals}
    for lang in ('english','simp_chinese'):
        zh=lang=='simp_chinese';label='zh' if zh else 'en';loc='l_'+lang+':\n'
        for kind,c in CONTRACTS.items():
            name=c[label]
            detail=('实际支付与建设合同同额的准备费并持续预留10行政力。每法案共两项分配槽位；未批准取消费用不退。机构条款须提高实际机构投入一级并让绑定州正式整合；保障条款须维持已记录制度/低税至少一年。外国目标最多等五年取得，再开始履约；国家制度变更会取消未批准条款或追责已批准义务。支持是预期机会，不是已经扩权、获利或居民改宗。' if zh else 'Pay the same preparation fee as a construction commitment and reserve 10 bureaucracy. Two allocation slots per bill. Unratified cancellation gives no refund. Institutional clauses require one actual investment level and incorporation of the bound state; guarantees hold the recorded regime/low tax for at least one year. Foreign targets wait at most five years before delivery. Changing prerequisites cancels unratified clauses or breaches ratified ones. Support reflects opportunities, not realized political power, profit or conversion.')
            entries={'td_allocate_'+kind:name,'td_allocate_'+kind+'_desc':detail,'td.allocate.'+kind:name,
                     'td_'+kind+'_planning':name+('：规划预留' if zh else ': Planning Reserve'),
                     'je_td_'+kind+'_allocation':name+('：' if zh else ': ')+f"[ROOT.GetCountry.MakeScope.Var('td_{kind}_target').GetState.GetName]",
                     'je_td_'+kind+'_allocation_waiting':name+('：等待取得主权' if zh else ': Awaiting Sovereignty'),
                     'je_td_'+kind+'_allocation_waiting_reason':detail,
                     'je_td_'+kind+'_allocation_proposed':name+('：审议中，' if zh else ': Proposed, ')+"[ROOT.GetCountry.MakeScope.Var('td_bill_target').GetState.GetName]",
                     'je_td_'+kind+'_allocation_proposed_reason':detail,
                     'je_td_'+kind+'_allocation_reason':detail}
            for key,value in entries.items():loc+=f' {key}:0 '+json.dumps(value,ensure_ascii=False)+'\n'
        out[f'localization/{lang}/td_allocations_l_{lang}.yml']=loc
    return out,options
