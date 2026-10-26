from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'companion'))
from portable import app_root, resource_root, initialize_database
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build_release import distributable


class PortableTests(unittest.TestCase):
    def test_package_excludes_personal_files_but_keeps_model_config(self):
        for name in ('companion/npcs.sqlite3', 'companion/npcs.sqlite3.bak', 'companion/config.json',
                     'companion/cache/numba/test', 'companion/self-test-rubberband.wav'):
            self.assertFalse(distributable(Path(name)), name)
        self.assertTrue(distributable(Path('companion/_internal/models/hub/snapshots/config.json')))
        self.assertTrue(distributable(Path('companion/XISpeaks-Companion.exe')))

    def test_frozen_paths_ignore_current_directory(self):
        with patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'executable', str(Path.cwd() / 'portable/app.exe')), patch.object(sys, '_MEIPASS', str(Path.cwd() / 'portable/_internal'), create=True):
            self.assertEqual(app_root(), Path(sys.executable).parent)
            self.assertEqual(resource_root(), Path(sys._MEIPASS))

    def test_seed_does_not_replace_customizations(self):
        with tempfile.TemporaryDirectory() as temp:
            seed, database = Path(temp) / 'seed', Path(temp) / 'database'
            seed.write_bytes(b'new defaults')
            initialize_database(database, seed)
            self.assertEqual(database.read_bytes(), b'new defaults')
            database.write_bytes(b'my custom choices')
            initialize_database(database, seed)
            self.assertEqual(database.read_bytes(), b'my custom choices')

    def test_failed_seed_does_not_leave_empty_database(self):
        with tempfile.TemporaryDirectory() as temp:
            database = Path(temp) / 'database'
            with self.assertRaises(FileNotFoundError):
                initialize_database(database, Path(temp) / 'missing')
            self.assertFalse(database.exists())
