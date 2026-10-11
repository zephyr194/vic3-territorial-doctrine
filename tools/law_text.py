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
    group_effects = ', '.join(
        RULES['group_politics'][group][label] + ' ' + signed(value, percent=True)
        for group, value in info['political_strength'].items())
    country_effects = ', '.join(
        COUNTRY_EFFECTS[key][0 if label == 'zh' else 1] + ' ' + signed(value, percent=COUNTRY_EFFECTS[key][2])
        for key, value in info['country_modifiers'].items())
    industry_effects = ', '.join(
        INDUSTRY_EFFECTS[key][0 if label == 'zh' else 1] + ' ' + signed(value, percent=True)
        for key, value in info['industry_modifiers'].items())
    territory_effects = ', '.join(
        TERRITORY_EFFECTS[key][0 if label == 'zh' else 1] + ' ' + signed(value, percent=True)
        for key, value in info['territory_modifiers'].items())
    if label == 'zh':
        focus = (f'重点区域上限{info["focus_limit"]}；每区域预留行政力{info["bureaucracy"]}、权威力{info["authority"]}，'
                 f'等待{info["wait_months"]}个月成熟。' if info['focus_limit'] else '不设扩张重点区域。')
        details = [f'集团政治力量：{group_effects}。', f'国家效果：{country_effects}。',
                   f'产业吞吐量：{industry_effects}。吞吐量同时增加投入需求与产出。',
                   f'拥有的新领土与非文化家园州：{territory_effects}；遵循原版迁移法律。',
                   f'宣称资格：{info["eligibility"][label]}',
                   f'基础立场：{baseline_positions(doctrine, label)}。殖民政策与人文科技会调整立场。',
                   focus + f'新宣称基础额外恶名{info["infamy"]}，另计本法律恶名倍率；逐州整合基础成本×{info["cost_multiplier"]}。接纳修正案通过后，为该州支付项目成本并整合一年。']
    else:
        focus = (f'Focus limit {info["focus_limit"]}; reserve {info["bureaucracy"]} bureaucracy and '
                 f'{info["authority"]} authority per region; maturity after {info["wait_months"]} months.'
                 if info['focus_limit'] else 'No expansion focus regions.')
        details = [f'Interest-group political strength: {group_effects}.', f'National effects: {country_effects}.',
                   f'Industry throughput: {industry_effects}. Throughput increases both input demand and output.',
                   f'Owned newly acquired and non-homeland states: {territory_effects}; vanilla migration laws apply.',
                   f'Claim eligibility: {info["eligibility"][label]}',
                   f'Base positions: {baseline_positions(doctrine, label)}. Colonial policy and humanitarian research adjust positions.',
                   focus + f' Base additional new-claim infamy {info["infamy"]}, adjusted by this law’s infamy factor; individual integration base cost x{info["cost_multiplier"]}. Ratified admission amendments give their funded state a one-year integration project.']
    return info['description'][label] + '\n\n' + '\n'.join(details)


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
