"""Player-facing doctrine text derived from the enacted balance rules."""
from territorial_doctrine.model import RULES, DOCTRINES, doctrine_scores, political_weight


OPINIONS = {
    'zh': {-2: '强烈反对', -1: '反对', 0: '中立', 1: '支持', 2: '强烈支持'},
    'en': {-2: 'Strongly oppose', -1: 'Oppose', 0: 'Neutral', 1: 'Support', 2: 'Strongly support'},
}
COUNTRY_EFFECTS = {
    'country_bureaucracy_mult': ('行政力', 'Bureaucracy', True),
    'country_prestige_mult': ('威望', 'Prestige', True),
    'country_authority_add': ('权威力', 'Authority', False),
    'country_diplomatic_play_maneuvers_add': ('外交博弈机动点', 'Diplomatic play maneuvers', False),
    'country_military_goods_cost_mult': ('军事物资花费', 'Military goods cost', True),
    'country_infamy_generation_mult': ('恶名产生', 'Infamy generation', True),
    'country_infamy_decay_mult': ('恶名衰减', 'Infamy decay', True),
    'country_legitimacy_base_add': ('基础合法性', 'Base legitimacy', False),
}
INDUSTRY_EFFECTS = {
    'building_paper_mill_throughput_mult': ('造纸厂', 'Paper Mills'),
    'building_food_industry_throughput_mult': ('食品工业', 'Food Industries'),
    'building_textile_mill_throughput_mult': ('纺织厂', 'Textile Mills'),
    'building_group_bg_agriculture_throughput_mult': ('农业', 'Agriculture'),
    'building_group_bg_logging_throughput_mult': ('林业', 'Logging'),
    'building_coal_mine_throughput_mult': ('煤矿', 'Coal Mines'),
    'building_iron_mine_throughput_mult': ('铁矿', 'Iron Mines'),
    'building_lead_mine_throughput_mult': ('铅矿', 'Lead Mines'),
    'building_sulfur_mine_throughput_mult': ('硫矿', 'Sulfur Mines'),
    'building_steel_mill_throughput_mult': ('炼钢厂', 'Steel Mills'),
    'building_tooling_workshop_throughput_mult': ('工具工坊', 'Tooling Workshops'),
    'building_chemical_plant_throughput_mult': ('化工厂', 'Chemical Plants'),
    'building_motor_industry_throughput_mult': ('动力机械工业', 'Motor Industries'),
    'building_arms_industry_throughput_mult': ('武器厂', 'Arms Industries'),
    'building_munition_plant_throughput_mult': ('弹药厂', 'Munition Plants'),
    'building_war_machine_industry_throughput_mult': ('战争机器工业', 'War Machine Industries'),
    'building_shipyard_throughput_mult': ('造船厂', 'Shipyards'),
}
TERRITORY_EFFECTS = {
    'state_construction_mult': ('建设效率', 'Construction efficiency'),
    'state_migration_pull_mult': ('移民吸引力', 'Migration attraction'),
    'state_radicals_from_discrimination_mult': ('歧视产生的激进派', 'Radicals from discrimination'),
    'state_radicals_from_sol_change_mult': ('生活水平下降产生的激进派', 'Radicals from falling living standards'),
    'state_loyalists_from_sol_change_mult': ('生活水平上升产生的效忠派', 'Loyalists from rising living standards'),
}


def signed(value, *, percent=False):
    return f'{value * 100 if percent else value:+g}' + ('%' if percent else '')


def baseline_positions(doctrine, label):
    index = DOCTRINES.index(doctrine)
    parts = []
    for stance in (2, 1, 0, -1, -2):
        names = [RULES['group_politics'][group][label] for group, scores in RULES['groups'].items()
                 if scores[index] == stance]
        if names:
            parts.append(f'{OPINIONS[label][stance]}: ' + ', '.join(names))
    return '; '.join(parts)


def doctrine_description(doctrine, label):
    info = RULES['doctrines'][doctrine]
    if label == 'zh':
        details = '实际支持另计理由、殖民政策、人文科技、集团对政府的认可、领袖立场、付费承诺与违约。无免费产业、建设、移民、人口或国家属性修正；不额外增加恶名或厌战。每90天一轮国内谈判，三成通过、三败否决。接纳仍逐州审核、付款后整合一年。'
        return info['description'][label] + '\n\n宣称资格：' + info['eligibility'][label] + '\n初始偏好：' + baseline_positions(doctrine,label) + '。' + details
    details = 'Actual support also reflects arguments, colonial policy, humanitarian research, government approval, leader ideology, funded commitments and breaches. No free industrial, construction, migration, population or national attribute modifiers; no extra infamy or exhaustion. Negotiation occurs every 90 days: three successes pass, three failures reject. Admission still reviews and funds one state for a one-year incorporation project.'
    return info['description'][label] + '\n\nClaim eligibility: ' + info['eligibility'][label] + '\nInitial preferences: ' + baseline_positions(doctrine,label) + '. ' + details


def group_description(group, label, policy=None, stage=0):
    info = RULES['group_politics'][group]
    if policy is None:
        levels = RULES['groups'][group]
    else:
        levels = [int(political_weight(doctrine_scores(d, policy, stage)[group]) * 2) for d in DOCTRINES]
    positions = '; '.join(f'{RULES["doctrines"][d][label]}: {OPINIONS[label][level]}'
                          for d, level in zip(DOCTRINES, levels))
    if label == 'zh':
        context = '基础立场' if policy is None else f'当前殖民与人文阶段{stage}/2的立场'
        return info['rationale'][label] + '\n' + context + '：' + positions + '。具体法案另计目标条件与承诺。'
    context = 'Base positions' if policy is None else f'Current colonial positions at humanitarian stage {stage}/2'
    return info['rationale'][label] + '\n' + context + ': ' + positions + '. Individual bills also account for targets and pledges.'
