"""Real PowerShell filesystem transactions; native Windows or optional pwsh."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = (os.environ.get('VTD_POWERSHELL_EXE') or
              (str(Path(os.environ.get('SystemRoot', 'C:/Windows')) /
                   'System32/WindowsPowerShell/v1.0/powershell.exe') if sys.platform == 'win32'
               else shutil.which('pwsh')))


@unittest.skipUnless(POWERSHELL, 'requires Windows PowerShell or optional VTD_POWERSHELL_EXE/pwsh')
class PowerShellInstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='VTD tests ')
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.source = self.base / 'checkout 中文'
        self.destination = self.base / 'user data 中文/mod'
        self.script = self.source / 'tools/install-windows.ps1'
        self.script.parent.mkdir(parents=True)
        shutil.copy2(ROOT / 'tools/install-windows.ps1', self.script)
        for name in ('LICENSE', 'mod/.metadata/metadata.json',
                     'mod/common/law_groups/td_law_group.txt',
                     'mod/localization/english/td_laws_l_english.yml'):
            target = self.source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
        (self.source / 'mod/obsolete.txt').write_text('old')
        self.folder = self.destination / 'territorial_doctrine'
        self.launcher = self.destination / 'territorial_doctrine.mod'
        self.log = self.base / 'install.log'

    def cli(self, *arguments, code=0, input_text=None, script=None):
        result = subprocess.run(
            [POWERSHELL, '-NoLogo', '-NoProfile', '-ExecutionPolicy', 'Bypass',
             '-File', str(script or self.script), *map(str, arguments)],
            input=input_text, capture_output=True, encoding='utf-8', errors='replace',
            cwd=self.base, timeout=30,
            env={**os.environ, 'VTD_MOD_DIR': str(self.destination),
                 'VTD_LOG_FILE': str(self.log),
                 'XDG_CACHE_HOME': str(self.base / 'cache'),
                 'XDG_CONFIG_HOME': str(self.base / 'config'),
                 'XDG_DATA_HOME': str(self.base / 'data')})
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return result

    def backups(self):
        return list((self.destination.parent / 'vtd-backups').iterdir())

    def test_lifecycle_cleans_old_files_and_backs_up_local_edits_without_touching_saves(self):
        self.destination.mkdir(parents=True)
        (self.destination / 'other.mod').write_text('other')
        saves = self.destination.parent / 'save games'
        saves.mkdir(); (saves / 'test.v3').write_bytes(b'save')
        self.cli('install')
        self.assertIn(self.folder.as_posix(), self.launcher.read_text(encoding='utf-8-sig'))
        self.assertTrue((self.folder / '.metadata/metadata.json').is_file())
        self.assertTrue((self.folder / '.vtd-install.json').is_file())
        (self.folder / 'local edit').write_text('keep')
        (self.source / 'mod/obsolete.txt').unlink()
        (self.source / 'mod/new.txt').write_text('new')
        result = self.cli('update')
        self.assertIn('Backing up', result.stdout)
        self.assertFalse((self.folder / 'obsolete.txt').exists())
        self.assertFalse((self.folder / 'local edit').exists())
        self.assertEqual((self.backups()[0] / 'territorial_doctrine/local edit').read_text(), 'keep')
        self.cli('remove'); self.cli('remove')
        self.assertFalse(self.folder.exists()); self.assertFalse(self.launcher.exists())
        self.assertEqual((saves / 'test.v3').read_bytes(), b'save')
        self.assertEqual((self.destination / 'other.mod').read_text(), 'other')
        self.assertEqual(len(self.backups()), 2)
        self.assertFalse((self.destination / '.vtd-install.lock').exists())
        self.assertFalse(list(self.destination.glob('.vtd-stage-*')))
        self.assertIn('VTD exit code: 0', self.log.read_text(encoding='utf-8-sig'))

    def test_preview_status_and_menu_create_no_game_directories(self):
        self.cli('install', '--dry-run')
        result = self.cli('--menu', input_text='4\n')
        self.assertIn('1 Install', result.stdout)
        self.assertIn('VTD: not installed', result.stdout)
        self.cli('--mod-dir', self.destination, 'remove', '--dry-run')
        self.assertFalse(self.destination.exists())

    def test_wrong_identity_and_descriptor_path_are_preserved(self):
        self.folder.mkdir(parents=True)
        (self.folder / 'private.txt').write_text('keep')
        for action in ('install', 'update', 'remove'):
            self.cli(action, code=1)
        self.assertEqual((self.folder / 'private.txt').read_text(), 'keep')
        shutil.rmtree(self.folder)
        self.cli('install')
        original = self.launcher.read_text(encoding='utf-8-sig')
        self.launcher.write_text(original.replace(self.folder.as_posix(), (self.base / 'elsewhere').as_posix()), encoding='utf-8')
        self.cli('update', code=1); self.cli('remove', code=1)
        self.assertTrue(self.folder.exists())

    def test_existing_install_lock_and_missing_install_errors(self):
        self.cli('update', code=1)
        self.cli('install')
        self.cli('install', code=1)
        lock = self.destination / '.vtd-install.lock'
        lock.write_text('busy')
        self.cli('remove', code=1)
        self.assertEqual(lock.read_text(), 'busy')
        self.assertTrue(self.folder.exists())

    def test_legacy_relative_descriptor_and_partial_install_repair(self):
        self.destination.mkdir(parents=True)
        shutil.copytree(self.source / 'mod', self.folder)
        self.launcher.write_text('name="Territorial Doctrine"\npath="mod/territorial_doctrine"\n')
        self.cli('update')
        self.launcher.unlink()
        self.assertIn('partial', self.cli('status').stdout)
        self.cli('update')
        self.assertTrue(self.launcher.is_file())
        shutil.rmtree(self.folder)
        self.cli('remove')
        self.assertFalse(self.launcher.exists())

    def test_invalid_source_or_failed_backup_leaves_installation_untouched(self):
        self.cli('install')
        before = self.launcher.read_bytes()
        source_law = self.source / 'mod/common/law_groups/td_law_group.txt'
        source_law.unlink()
        self.cli('update', code=1)
        source_law.write_text('restored')
        backup_root = self.destination.parent / 'vtd-backups'
        backup_root.write_text('not a directory')
        self.cli('remove', code=1)
        self.assertEqual(before, self.launcher.read_bytes())
        self.assertTrue(self.folder.exists())
        self.assertFalse((self.destination / '.vtd-install.lock').exists())

    def test_failed_descriptor_commit_rolls_back_payload_and_descriptor(self):
        self.cli('install')
        before = self.launcher.read_bytes()
        (self.folder / 'local edit').write_text('keep')
        script = self.script.read_text(encoding='utf-8-sig')
        needle = 'Move-Item -LiteralPath $nextLauncher -Destination $launcher'
        self.assertIn(needle, script)
        self.script.write_text(script.replace(needle, "throw 'injected commit failure'"), encoding='utf-8-sig')
        self.cli('update', code=1)
        self.assertEqual(before, self.launcher.read_bytes())
        self.assertEqual((self.folder / 'local edit').read_text(), 'keep')
        self.assertEqual(len(self.backups()), 1)
        self.assertFalse(list(self.destination.glob('.vtd-stage-*')))

    def test_arguments_source_checkout_guard_and_generate_error(self):
        for arguments in (('install', '--mod-dir', self.source), ('install', '--generate'),
                          ('status', '--mod-dir'), ('--unknown',), ('install', 'remove')):
            self.cli(*arguments, code=1)
        self.assertFalse(self.destination.exists())
        self.assertIn('vtd.cmd', self.cli('--help').stdout)

    def test_symlink_source_and_payload_are_refused(self):
        external = self.base / 'external'
        external.mkdir(); (external / 'keep').write_text('safe')
        try:
            (self.source / 'mod/linked').symlink_to(external, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest('symlinks unavailable')
        self.cli('install', code=1)
        (self.source / 'mod/linked').unlink()
        self.destination.mkdir(parents=True)
        self.folder.symlink_to(external, target_is_directory=True)
        self.cli('remove', code=1)
        self.assertEqual((external / 'keep').read_text(), 'safe')
        self.folder.unlink()
        self.folder.symlink_to(self.base / 'missing target', target_is_directory=True)
        self.cli('install', code=1)
        self.assertTrue(self.folder.is_symlink())

    def test_real_checkout_install_update_remove_without_python(self):
        script = ROOT / 'tools/install-windows.ps1'
        for action in ('install', 'status', 'update', 'remove'):
            self.cli(action, script=script)
            if action == 'install':
                expected = len([p for p in (ROOT / 'mod').rglob('*') if p.is_file()]) + 2
                self.assertEqual(len([p for p in self.folder.rglob('*') if p.is_file()]), expected)
                self.assertTrue((self.folder / '.metadata/metadata.json').exists())
        self.assertFalse(self.folder.exists())


if __name__ == '__main__':
    unittest.main()
