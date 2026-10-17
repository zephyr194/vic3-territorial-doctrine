"""Filesystem lifecycle, ownership and rollback tests for the local installer."""
from contextlib import redirect_stdout, redirect_stderr
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools import install as installer
from tools.package import descriptor

ROOT = Path(__file__).resolve().parents[1]


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.destination = self.base / 'profile with spaces 中文' / 'mod'
        self.source = self.base / 'checkout'
        (self.source / 'mod/.metadata').mkdir(parents=True)
        (self.source / 'mod/.metadata/metadata.json').write_text(json.dumps({
            'id':installer.NAME, 'game_id':'victoria3', 'version':'test-old'}),encoding='utf-8')
        (self.source / 'mod/old-file.txt').write_text('old')
        (self.source / 'LICENSE').write_text('license')
        self.addCleanup(patch.stopall)
        self.real_validate_source=installer.validate_source
        patch.object(installer,'ROOT',self.source).start()
        # Most tests isolate filesystem transactions. PackagingTests and the CLI
        # test below exercise real generated-asset validation against the repo.
        patch.object(installer,'validate_source').start()

    @property
    def folder(self):return self.destination / installer.NAME

    @property
    def launcher(self):return self.destination / (installer.NAME+'.mod')

    def run_action(self, action, **kwargs):
        with redirect_stdout(io.StringIO()):return installer.manage(action,self.destination,**kwargs)

    def test_install_update_and_remove_keep_saves_other_mods_and_backups(self):
        self.destination.mkdir(parents=True)
        saves=self.destination.parent/'save games';saves.mkdir();(saves/'test.v3').write_bytes(b'save')
        (self.destination/'other.mod').write_bytes(b'other')
        self.run_action('install')
        self.assertIn(self.folder.as_posix(),self.launcher.read_text())
        self.assertTrue((self.folder/installer.MARKER).is_file())
        (self.folder/'local edit.txt').write_text('keep in backup')
        (self.source/'mod/old-file.txt').unlink();(self.source/'mod/new-file.txt').write_text('new')
        metadata=self.source/'mod/.metadata/metadata.json'
        data=json.loads(metadata.read_text());data['version']='test-new';metadata.write_text(json.dumps(data))
        backup=self.run_action('update')
        self.assertFalse((self.folder/'old-file.txt').exists())
        self.assertEqual((self.folder/'new-file.txt').read_text(),'new')
        self.assertEqual((backup/installer.NAME/'local edit.txt').read_text(),'keep in backup')
        self.assertEqual((backup/installer.NAME/'old-file.txt').read_text(),'old')
        self.assertEqual(json.loads((self.folder/installer.MARKER).read_text())['version'],'test-new')
        removal=self.run_action('remove')
        self.assertFalse(self.folder.exists());self.assertFalse(self.launcher.exists())
        self.assertEqual((removal/installer.NAME/'new-file.txt').read_text(),'new')
        self.assertEqual((saves/'test.v3').read_bytes(),b'save')
        self.assertEqual((self.destination/'other.mod').read_bytes(),b'other')
        self.run_action('remove');self.run_action('install')
        self.assertFalse((self.destination/'.vtd-install.lock').exists())
        self.assertFalse(list(self.destination.glob('.vtd-stage-*')))

    def test_existing_install_is_not_silently_overwritten(self):
        self.run_action('install');before=self.launcher.read_bytes()
        with self.assertRaises(ValueError):self.run_action('install')
        self.assertEqual(self.launcher.read_bytes(),before)

    def test_update_requires_an_installation_and_remove_absent_creates_nothing(self):
        with self.assertRaises(ValueError):self.run_action('update')
        self.run_action('remove');self.assertFalse(self.destination.exists())

    def test_dry_runs_never_create_directories_or_mutate_source(self):
        self.run_action('install',dry_run=True,generate=True)
        self.assertFalse(self.destination.exists());installer.validate_source.assert_not_called()
        self.run_action('install')
        before=self.launcher.read_bytes()
        self.run_action('update',dry_run=True);self.run_action('remove',dry_run=True)
        self.assertEqual(self.launcher.read_bytes(),before)
        self.assertFalse((self.destination.parent/'vtd-backups').exists())

    def test_unrecognized_folder_is_never_removed_or_replaced(self):
        self.folder.mkdir(parents=True);(self.folder/'my-file.txt').write_text('private')
        for action in ('install','update','remove'):
            with self.assertRaises(ValueError):self.run_action(action)
        self.assertEqual((self.folder/'my-file.txt').read_text(),'private')

    def test_wrong_metadata_and_descriptor_target_are_rejected(self):
        self.run_action('install')
        metadata=self.folder/'.metadata/metadata.json';data=json.loads(metadata.read_text());data['id']='another_mod';metadata.write_text(json.dumps(data))
        with self.assertRaises(ValueError):self.run_action('remove')
        data['id']=installer.NAME;metadata.write_text(json.dumps(data))
        self.launcher.write_text(descriptor((self.base/'another-mod').as_posix()))
        with self.assertRaises(ValueError):self.run_action('update')
        self.assertTrue(self.folder.exists())

    def test_old_zip_install_with_relative_descriptor_can_be_updated(self):
        self.destination.mkdir(parents=True);shutil.copytree(self.source/'mod',self.folder)
        self.launcher.write_text(descriptor('mod/'+installer.NAME))
        backup=self.run_action('update')
        self.assertTrue(backup.is_dir());self.assertTrue((self.folder/installer.MARKER).exists())
        self.assertEqual(installer.inspect_installation(self.destination)['version'],'test-old')

    def test_partial_install_with_missing_descriptor_is_repaired(self):
        self.run_action('install');self.launcher.unlink()
        self.assertTrue(installer.inspect_installation(self.destination)['partial'])
        self.run_action('update');self.assertTrue(self.launcher.exists())

    def test_orphan_descriptor_can_be_repaired_or_removed(self):
        self.destination.mkdir(parents=True);self.launcher.write_text(descriptor(self.folder.as_posix()))
        self.run_action('update');shutil.rmtree(self.folder)
        self.run_action('remove');self.assertFalse(self.launcher.exists())

    def test_unrelated_orphan_descriptor_is_preserved(self):
        self.destination.mkdir(parents=True)
        self.launcher.write_text('name="Another Mod"\npath="mod/territorial_doctrine"\n')
        with self.assertRaises(ValueError):self.run_action('remove')
        self.assertTrue(self.launcher.exists())

    def test_locked_operation_does_not_touch_the_install(self):
        self.run_action('install');lock=self.destination/'.vtd-install.lock';lock.write_text('busy')
        with self.assertRaises(ValueError):self.run_action('remove')
        self.assertEqual(lock.read_text(),'busy');self.assertTrue(self.folder.exists())

    def test_failed_descriptor_commit_restores_both_old_files(self):
        self.run_action('install');old=self.launcher.read_bytes();(self.folder/'local.txt').write_text('old')
        with patch.object(installer.os,'replace',side_effect=OSError('injected write failure')):
            with self.assertRaises(OSError):self.run_action('update')
        self.assertEqual(self.launcher.read_bytes(),old)
        self.assertEqual((self.folder/'local.txt').read_text(),'old')
        self.assertFalse((self.destination/'.vtd-install.lock').exists())
        self.assertEqual(len(list((self.destination.parent/'vtd-backups').iterdir())),1)

    def test_failed_payload_commit_restores_the_old_install(self):
        self.run_action('install');rename=Path.rename
        def fail_new(path,target):
            if path.name=='next_payload':raise OSError('injected rename failure')
            return rename(path,target)
        with patch.object(Path,'rename',fail_new):
            with self.assertRaises(OSError):self.run_action('update')
        self.assertEqual((self.folder/'old-file.txt').read_text(),'old');self.assertTrue(self.launcher.exists())

    def test_failed_backup_or_source_validation_never_moves_the_old_install(self):
        self.run_action('install')
        with patch.object(installer,'backup_installation',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):self.run_action('remove')
        installer.validate_source.side_effect=ValueError('invalid source')
        with self.assertRaises(ValueError):self.run_action('update')
        self.run_action('remove')  # Removal still works with broken source validation.
        self.assertFalse(self.folder.exists())

    def test_source_checkout_is_never_an_install_destination(self):
        for destination in (self.source,self.source/'nested'):
            with self.assertRaises(ValueError):installer.validate_destination(destination)
        with patch.object(installer,'ROOT',self.base/installer.NAME):
            with self.assertRaises(ValueError):installer.validate_destination(self.base)

    def test_symlink_payload_and_backup_paths_are_not_traversed(self):
        external=self.base/'external';external.mkdir();(external/'keep').write_text('safe')
        self.destination.mkdir(parents=True)
        try:self.folder.symlink_to(external,target_is_directory=True)
        except (OSError,NotImplementedError):self.skipTest('symlinks unavailable')
        with self.assertRaises(ValueError):self.run_action('remove')
        self.folder.unlink();self.run_action('install')
        (self.destination.parent/'vtd-backups').symlink_to(external,target_is_directory=True)
        with self.assertRaises(ValueError):self.run_action('update')
        self.assertEqual((external/'keep').read_text(),'safe');self.assertTrue(self.folder.exists())
        (self.source/'mod/linked-file').symlink_to(external/'keep')
        with patch.object(installer.subprocess,'run') as regenerate:
            with self.assertRaises(ValueError):self.real_validate_source(generate=True)
            regenerate.assert_not_called()
        self.assertEqual((external/'keep').read_text(),'safe')

    def test_argument_options_work_before_or_after_subcommand(self):
        for argv in (['--mod-dir',str(self.destination),'--dry-run','install'],['install','--mod-dir',str(self.destination),'--dry-run']):
            with redirect_stdout(io.StringIO()):self.assertEqual(installer.main(argv),0)
        self.assertFalse(self.destination.exists())

    def test_cli_reports_conflicts_without_a_traceback(self):
        self.folder.mkdir(parents=True);errors=io.StringIO()
        with redirect_stderr(errors):code=installer.main(['remove','--mod-dir',str(self.destination)])
        self.assertEqual(code,1);self.assertNotIn('Traceback',errors.getvalue())


class DiscoveryTests(unittest.TestCase):
    def test_explicit_and_environment_paths_take_precedence(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp)
            self.assertEqual(installer.find_mod_dir(home/'explicit',environ={'VTD_MOD_DIR':str(home/'env')}),home/'explicit')
            self.assertEqual(installer.find_mod_dir(environ={'VTD_MOD_DIR':str(home/'env')}),home/'env')

    def test_linux_xdg_and_macos_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);suffix=Path('Paradox Interactive/Victoria 3/mod')
            self.assertEqual(installer.find_mod_dir(platform='linux',home=home,environ={}),home/'.local/share'/suffix)
            self.assertEqual(installer.find_mod_dir(platform='linux',home=home,environ={'XDG_DATA_HOME':str(home/'custom')}),home/'custom'/suffix)
            self.assertEqual(installer.find_mod_dir(platform='darwin',home=home,environ={}),home/'Documents'/suffix)

    def test_windows_redirected_documents_and_onedrive_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);suffix=Path('Paradox Interactive/Victoria 3/mod')
            with patch.object(installer,'windows_documents',return_value=home/'redirected'):
                self.assertEqual(installer.find_mod_dir(platform='win32',home=home,environ={}),home/'redirected'/suffix)
            target=home/'OneDrive/Documents'/suffix;target.parent.mkdir(parents=True)
            with patch.object(installer,'windows_documents',return_value=None):
                self.assertEqual(installer.find_mod_dir(platform='win32',home=home,environ={'OneDrive':str(home/'OneDrive')}),target)
                (home/'Documents'/suffix).parent.mkdir(parents=True)
                with self.assertRaises(ValueError):installer.find_mod_dir(platform='win32',home=home,environ={'OneDrive':str(home/'OneDrive')})

    def test_real_cli_lifecycle_from_another_working_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp);destination=directory/'user data 中文/mod'
            for action in ('install','status','update','remove','remove'):
                command=[sys.executable,str(ROOT/'vtd.py'),action,'--mod-dir',str(destination)]
                if action=='update':command.append('--generate')
                log=directory/(action+'.log')
                result=subprocess.run(command,cwd=directory,capture_output=True,text=True,
                                      env={**os.environ,'VTD_LOG_FILE':str(log)})
                self.assertEqual(result.returncode,0,result.stderr)
                recorded=log.read_text(encoding='utf-8')
                self.assertIn('VTD exit code: 0',recorded)
                if action=='install':self.assertIn('Staging mod files',recorded)
                if action=='update':
                    self.assertIn('Regenerating source assets',recorded)
                    self.assertIn('Backing up the previous installation',recorded)
            self.assertFalse((destination/installer.NAME).exists())


if __name__=='__main__':unittest.main()
