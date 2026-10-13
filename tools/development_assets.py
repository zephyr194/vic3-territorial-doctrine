"""Remove legacy packages; investment uses vanilla buildings."""
from territorial_doctrine.model import RULES


def assets():
    names = ['td_territory_' + d for d in RULES['doctrines']]
    modifiers = '# Compatibility names carry no economic/population modifiers.\n'
    modifiers += ''.join(f'{name} = {{}}\n' for name in names)
    cleanup = 'td_clear_state_development_effect = {\n'
    cleanup += ''.join(f'    remove_modifier = {name}\n' for name in names)
    cleanup += '    remove_variable = td_development_profile\n    remove_variable = td_development_owner\n}\n'
    return {'common/static_modifiers/td_territory_modifiers.txt': modifiers,
            'common/scripted_effects/td_development.txt': cleanup +
            'td_refresh_state_development_effect = { td_clear_state_development_effect = yes }\n'}
