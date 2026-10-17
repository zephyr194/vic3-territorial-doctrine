"""Exercise visible console output and persistent logs across startup failures."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class LauncherTests(unittest.TestCase):
    def test_forced_menu_with_redirected_input_is_visible_and_logged(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            log = base / 'diagnostic 中文.log'
            result = subprocess.run(
                [sys.executable, str(ROOT / 'vtd.py'), '--menu', '--mod-dir', str(base / 'mod')],
                input='4\n', capture_output=True, encoding='utf-8', cwd=base,
                env={**os.environ, 'VTD_LOG_FILE': str(log), 'PYTHONIOENCODING': 'utf-8'})
            self.assertEqual(result.returncode, 0, result.stderr)
            for message in ('1 Install', 'Choose /', 'VTD: not installed', 'VTD exit code: 0'):
                self.assertIn(message, result.stdout)
                self.assertIn(message, log.read_text(encoding='utf-8'))
            self.assertFalse((base / 'mod').exists())

    def test_bad_arguments_and_install_errors_are_logged_with_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            log = base / 'errors.log'
            for arguments, code, message in (
                (['--unknown'], 2, 'unrecognized arguments'),
                (['update', '--mod-dir', str(base / 'mod')], 1, 'Run install first'),
            ):
                result = subprocess.run([sys.executable, str(ROOT / 'vtd.py'), *arguments],
                                        capture_output=True, encoding='utf-8',
                                        env={**os.environ, 'VTD_LOG_FILE': str(log), 'PYTHONIOENCODING': 'utf-8'})
                self.assertEqual(result.returncode, code)
                self.assertIn(message, result.stderr)
                self.assertIn(message, log.read_text(encoding='utf-8'))
                self.assertIn('VTD exit code: {}'.format(code), log.read_text(encoding='utf-8'))

    def test_import_failure_is_logged_before_installer_starts(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            shutil.copy2(ROOT / 'vtd.py', base / 'vtd.py')
            (base / 'tools').mkdir()
            (base / 'tools/__init__.py').touch()
            (base / 'tools/install.py').write_text("raise RuntimeError('broken installer import')\n")
            log = base / 'startup.log'
            result = subprocess.run([sys.executable, str(base / 'vtd.py'), 'status'], cwd=base,
                                    capture_output=True, encoding='utf-8',
                                    env={**os.environ, 'VTD_LOG_FILE': str(log), 'PYTHONIOENCODING': 'utf-8'})
            self.assertEqual(result.returncode, 1)
            self.assertIn('broken installer import', result.stderr)
            self.assertIn('Traceback', log.read_text(encoding='utf-8'))
            self.assertIn('VTD exit code: 1', log.read_text(encoding='utf-8'))


@unittest.skipUnless(sys.platform == 'win32', 'requires native Windows cmd.exe')
class WindowsLauncherTests(unittest.TestCase):
    def test_batch_command_and_double_click_menu_route(self):
        with tempfile.TemporaryDirectory(prefix='VTD test ') as tmp:
            base = Path(tmp)
            # A checkout path containing spaces, as is common under Documents.
            shutil.copy2(ROOT / 'vtd.cmd', base / 'vtd.cmd')
            (base / 'tools').mkdir()
            shutil.copy2(ROOT / 'tools/install-windows.ps1', base / 'tools/install-windows.ps1')
            for arguments, input_text in (('status --mod-dir "{}"'.format(base / 'mod'), ''),
                                          ('--vtd-console', '4\n')):
                result = subprocess.run(
                    '"{}" {}'.format(base / 'vtd.cmd', arguments), shell=True,
                    input=input_text, capture_output=True, encoding='utf-8', errors='replace',
                    env={**os.environ, 'VTD_MOD_DIR': str(base / 'mod'), 'PYTHONIOENCODING': 'utf-8'},
                    timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('VTD: not installed', result.stdout)
                self.assertIn('VTD finished with exit code 0', result.stdout)
                if input_text:
                    self.assertIn('1 Install', result.stdout)

    def test_batch_works_when_no_python_is_available(self):
        with tempfile.TemporaryDirectory(prefix='VTD test ') as tmp:
            base = Path(tmp)
            for name in ('py.cmd', 'python.cmd'):
                (base / name).write_bytes(b'@echo ERROR Python must not be called\r\n@exit /b 87\r\n')
            for action in ('install', 'update', 'remove', 'status'):
                result = subprocess.run(
                    '"{}" {} --mod-dir "{}"'.format(ROOT / 'vtd.cmd', action, base / 'mod'), shell=True,
                    capture_output=True, encoding='utf-8', errors='replace', cwd=base,
                    env={**os.environ, 'PATH': str(base)}, timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('VTD exit code: 0', result.stdout)
                self.assertNotIn('ERROR Python must not be called', result.stdout)
            self.assertIn('VTD: not installed', result.stdout)


if __name__ == '__main__':
    unittest.main()
