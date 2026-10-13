"""Compatibility cleanup: no unconditional legitimacy or population rewards."""
from territorial_doctrine.model import RULES


def assets():
    names = ['td_success_'+d for d in RULES['doctrines'] if d != 'status_quo'] + ['td_success_admission']
    modifiers = ''.join(f'{name} = {{}}\n' for name in names)
    cleanup = 'td_clear_success_modifiers_effect = {\n'
    cleanup += ''.join(f'    remove_modifier = {name}\n' for name in names)
    cleanup += '    remove_variable = td_success_window\n    remove_variable = td_success_state\n}\n'
    effects = cleanup + """td_register_original_territory_effect = {
    if = { limit = { NOT = { has_variable = td_original_owner } }
        set_variable = { name = td_original_owner value = owner }
    }
}
td_revoke_success_on_prev_state_effect = { td_clear_success_modifiers_effect = yes }
td_refresh_success_credit_effect = { td_clear_success_modifiers_effect = yes }
td_award_acquisition_success_effect = {}
td_award_admission_success_effect = {}
td_process_acquisition_effect = {}
td_admission_reaction_effect = {}
"""
    return {'common/static_modifiers/td_success_modifiers.txt': modifiers,
            'common/scripted_effects/td_success.txt': effects}
