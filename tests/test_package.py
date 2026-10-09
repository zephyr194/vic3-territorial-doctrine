from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from tools.package import install, package


class PackagingTests(unittest.TestCase):
    def test_archive_contains_game_payload_and_launcher(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'mod.zip'
            package(output)
            with ZipFile(output) as archive:
                self.assertIsNone(archive.testzip())
                names = archive.namelist()
                self.assertIn('territorial_doctrine/common/laws/td_laws.txt', names)
                self.assertIn('territorial_doctrine/.metadata/metadata.json', names)
                self.assertIn('territorial_doctrine.mod', names)
                self.assertIn('INSTALL.md', names)
                self.assertFalse(any(name.startswith('/') or '..' in Path(name).parts for name in names))

    def test_install_uses_absolute_path_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / 'user data/mod'
            install(directory)
            launcher = directory / 'territorial_doctrine.mod'
            original = launcher.read_bytes()
            self.assertIn((directory / 'territorial_doctrine').as_posix(), original.decode('utf-8'))
            with self.assertRaises(ValueError):
                install(directory)
            self.assertEqual(launcher.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
