from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'companion'), str(ROOT / 'scripts')]
from registry import Registry
from service import DEFAULTS
from release_overrides import export_overrides, apply_overrides


class ReleaseOverrideTests(unittest.TestCase):
    def test_corrections_survive_without_history_mutes_or_globals(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'live.sqlite3'
            live, seed = Registry(path, DEFAULTS), Registry(':memory:', DEFAULTS)
            try:
                live.encounter('Shadow Lord')
                live.edit('shadow lord', 'profile', dict(voice='0.70*am_onyx + 0.30*am_fenrir', speed=0.8888888889, pitch=-1))
                live.edit('shadow lord', 'preset', dict(name='galka', enabled=True))
                live.edit('shadow lord', 'mute', True)
                live.set_globals(1.2, 2.5, 'librosa')
                live.encounter('Uncorrected NPC')
                live.encounter('Race Only')
                live.edit('race only', 'preset', dict(name='elvaan', enabled=True))
                exported = export_overrides(path, seed)
                self.assertEqual(len(exported['npcs']), 2)
                self.assertEqual(apply_overrides(seed, exported), 2)
                row = seed.db.execute("SELECT * FROM npcs WHERE key='shadow lord'").fetchone()
                self.assertEqual(row['manual_voice'], '0.70*am_onyx + 0.30*am_fenrir')
                self.assertEqual(row['preset_galka'], 1)
                self.assertAlmostEqual(row['manual_speed'], 0.8888888889)
                self.assertEqual((row['muted'], row['encounters'], row['last_seen']), (0, 0, 0))
                self.assertEqual(seed.globals()['volume'], 1)
                self.assertEqual(export_overrides(path, seed)['npcs'], [])
            finally:
                live.close()
                seed.close()
