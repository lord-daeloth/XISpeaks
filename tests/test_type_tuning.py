import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'companion'))
import registry,service
class TypeTuningTests(unittest.TestCase):
    def test_neutral_existing_hash_offsets_and_manual_tuning_preserved(self):
        db=registry.Registry(':memory:',dict(service.DEFAULTS,random_tuning=False))
        try:
            db.encounter('Test');db.db.execute("UPDATE npcs SET auto_speed=1.05,auto_pitch=1 WHERE key='test'")
            npc=db.page()['rows'][0];self.assertEqual(npc['base_speed'],1);self.assertEqual(npc['base_pitch'],0)
            db.edit('test','preset',dict(name='galka',enabled=True))
            npc=db.page()['rows'][0];self.assertEqual(npc['speed'],.9);self.assertEqual(npc['pitch'],-2.5)
            db.edit('test','profile',dict(voice=registry.VOICES[0],speed=1.1,pitch=.2))
            npc=db.page()['rows'][0];self.assertAlmostEqual(npc['speed'],.99);self.assertAlmostEqual(npc['pitch'],-2.3)
        finally:db.close()
    def test_settings_persist_stack_and_reset(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'test.sqlite3';db=registry.Registry(path,dict(service.DEFAULTS,random_tuning=False))
            db.set_preset_settings('galka',.85,-1.2);db.close()
            db=registry.Registry(path,dict(service.DEFAULTS,random_tuning=False))
            try:
                settings=db.preset_settings();self.assertEqual(settings['galka'],[.85,-1.2])
                speed,pitch=registry.preset_effects({'galka':True,'child':True},settings)
                self.assertEqual(speed,.85);self.assertAlmostEqual(pitch,-.2)
                with self.assertRaises(ValueError):db.set_preset_settings('galka',float('nan'),0)
                self.assertEqual(db.set_preset_settings('galka',reset=True)['galka'],registry.PRESETS['galka'])
            finally:db.close()
