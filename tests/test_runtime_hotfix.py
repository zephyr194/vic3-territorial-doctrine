"""Regressions for the 1.13.11 report; these do not execute the game engine."""
from copy import deepcopy
from pathlib import Path
import shutil
import tempfile
import unittest

from native_runner import EventRunner
from test_plan_delivery import GeographyRunner, roundtrip
from territorial_doctrine.script import load, walk
from tools.validate import validate

ROOT = Path(__file__).resolve().parents[1]


def field(entries, key):
    return next(e.value for e in entries if e.key == key)


class StrictGeographyRunner(GeographyRunner):
    def context(self):
        context = super().context()
        # The old fixture used var:td_bill=0 even when no bill existed, masking
        # the actual engine's unset-variable error on the pre-bill menu path.
        for key in list(context):
            if key.startswith('var:') and '.' not in key and key[4:] not in self.storage():
                del context[key]
        return context


class RuntimeHotfixTests(unittest.TestCase):
    def test_no_bill_journals_and_unadmitted_states_do_not_read_unset_variables(self):
        r = StrictGeographyRunner()
        for state in r.states.values():
            state['owner'] = r.country
        for name in ('je_td_bill', 'je_td_admission_amendment', 'je_td_integration'):
            for key in ('is_shown_when_inactive', 'possible'):
                self.assertFalse(r.check(field(r.definitions[name], key)))
        self.assertFalse(r.check(field(r.definitions['td_select_integration'], 'is_shown')))
        self.assertFalse(r.check(field(r.definitions['td_refresh_integration'], 'is_shown')))
        r.states['A']['variables']['td_admitted_owner'] = r.country
        self.assertTrue(r.check(field(r.definitions['td_select_integration'], 'is_shown')))
        self.assertTrue(r.check(field(r.definitions['td_refresh_integration'], 'is_shown')))
        r.variables.update(td_bill=2, td_bill_target='A')
        self.assertTrue(r.check(field(r.definitions['je_td_admission_amendment'], 'possible')))

    def test_first_owned_state_menu_to_named_review_without_a_bill(self):
        r = StrictGeographyRunner()
        r.states['A']['owner'] = r.country
        r.variables.pop('td_target')
        r.execute(field(r.definitions['td_select_owned'], 'when_taken'))
        window = r.windows[-1]
        self.assertEqual(window['name'], 'td.20')
        self.assertEqual(window['saved']['td_menu_target'], 'A')
        # Check every option; even the irrelevant arguments must be safe to draw.
        for option in (e.value for e in r.definitions['td.20'] if e.key == 'option'):
            r.check(next((e.value for e in option if e.key == 'trigger'), []))
        self.assertTrue(r.choose(window, 'td.reason.civil_administration'))
        self.assertEqual(r.windows[-1]['name'], 'td.30')
        self.assertNotIn('td_bill', r.variables)
        self.assertGreater(r.variables['td_preview_fast_cost'], 0)

    def test_foreign_claim_menu_checks_arguments_without_bill_or_pending_defaults(self):
        r = StrictGeographyRunner()
        r.execute(field(r.definitions['td_select_claim'], 'when_taken'))
        self.assertEqual(r.notifications[-1], 'td.20')
        for option in (e.value for e in r.definitions['td.20'] if e.key == 'option'):
            r.check(next((e.value for e in option if e.key == 'trigger'), []))
        self.assertTrue(r.choose(r.windows[-1], 'td.reason.regional_interest'))
        self.assertEqual(r.notifications[-1], 'td.21')
        self.assertNotIn('td_bill', r.variables)

    def test_stale_menu_cannot_change_or_cancel_another_states_menu(self):
        r = StrictGeographyRunner()
        for state in r.states.values():
            state['owner'] = r.country
        r.fire('td.31')
        old_notice = r.windows[-1]
        r.execute(field(r.definitions['td_select_owned'], 'when_taken'))
        old = r.windows[-1]
        self.assertTrue(r.choose(old, 'td.next_state'))
        current = r.windows[-1]
        self.assertEqual(r.variables['td_target'], 'B')
        self.assertFalse(r.choose(old, 'td.reason.civil_administration'))
        r.choose(old, 'td.cancel_menu')
        self.assertEqual(r.variables['td_pending_bill'], 2)
        r.choose(old_notice, 'td.close')
        self.assertEqual(r.variables['td_pending_bill'], 2)
        self.assertTrue(r.choose(current, 'td.reason.civil_administration'))

    def test_disappeared_state_blocks_old_menu_actions(self):
        r = StrictGeographyRunner()
        r.states['A']['owner'] = r.country
        r.execute(field(r.definitions['td_select_owned'], 'when_taken'))
        window = r.windows[-1]
        del r.states['A']
        self.assertFalse(r.choose(window, 'td.reason.civil_administration'))
        r.execute(r.definitions['td_open_target_menu_effect'])
        self.assertEqual(r.notifications[-1], 'td.31')

    def test_acknowledgement_closes_notice_and_survives_persisted_state(self):
        r = EventRunner(country='POR')
        self.assertTrue(r.check(field(r.definitions['td_mod_status'], 'is_shown')))
        r.execute(field(r.definitions['td_mod_status'], 'when_taken'))
        self.assertEqual(r.windows[-1]['name'], 'td.23')
        before = deepcopy((r.states, r.globals, r.gold_reserves, r.bureaucracy))
        self.assertTrue(r.choose(r.windows[-1], 'td.close'))
        self.assertFalse(r.check(field(r.definitions['td_mod_status'], 'is_shown')))
        self.assertEqual((r.states, r.globals, r.gold_reserves, r.bureaucracy), before)
        restored = roundtrip(r)
        self.assertFalse(restored.check(field(restored.definitions['td_mod_status'], 'is_shown')))
        self.assertEqual(r.owner_updates, 0)

    def test_status_actions_have_no_world_iteration(self):
        r = EventRunner()
        for name in ('td_mod_status', 'td_enable_system_effect', 'td.23'):
            self.assertFalse(any(e.key in ('every_country', 'every_state')
                                 for e in walk(r.definitions[name])))
        self.assertNotIn('td_enable_doctrine', r.definitions)
        for lang in ('english', 'simp_chinese'):
            loc = (ROOT/f'mod/localization/{lang}/td_gameplay_l_{lang}.yml').read_text(encoding='utf-8-sig')
            self.assertIn('[ROOT.GetCountry.GetName]', loc)
            self.assertNotIn('system starts disabled', loc)

    def test_law_group_visibility_has_no_runtime_switch(self):
        group = load(ROOT/'mod/common/law_groups/td_law_group.txt')[0].value
        self.assertNotIn('enable', [e.key for e in group])

    def test_selection_effects_are_hidden_from_tooltip_evaluation(self):
        r = EventRunner()
        for name in ('td_select_owned', 'td_select_claim', 'td_renounce_lost', 'td_select_integration', 'td_claim_al_rif'):
            self.assertEqual([e.key for e in field(r.definitions[name], 'when_taken')], ['hidden_effect'])
        self.assertNotIn('every_scope_pop', [e.key for e in walk(r.definitions['td_refresh_target_effect'])])

    def test_every_visible_event_has_a_bundled_image(self):
        for path in (ROOT/'mod/events').glob('*.txt'):
            for event in load(path):
                if not isinstance(event.value, list) or any(e.key == 'hidden' and e.value == 'yes' for e in event.value):
                    continue
                asset = field(field(event.value, 'event_image'), 'texture').strip('"')
                data = (ROOT/'mod'/asset).read_bytes()
                self.assertEqual(data[:4], b'DDS ')
                self.assertGreater(len(data), 128)

    def test_validator_rejects_missing_event_art(self):
        with tempfile.TemporaryDirectory() as tmp:
            mod = Path(tmp)/'mod'
            shutil.copytree(ROOT/'mod', mod)
            (mod/'gfx/event_pictures/td_territorial_deliberation.dds').unlink()
            self.assertTrue(any('missing texture' in error for error in validate(mod)))


if __name__ == '__main__':
    unittest.main()
