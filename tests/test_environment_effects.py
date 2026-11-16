import unittest,sys, tempfile
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'companion'))
from environment_effects import Reverb
from dialogue import parse_frame
import registry,service
class EnvironmentTests(unittest.TestCase):
    def test_streaming_matches_whole_and_tail_is_bounded(self):
        audio=np.random.default_rng(42).normal(0,.08,24000).astype(np.float32)
        whole=Reverb('cave');expected=whole.process(audio)
        streaming=Reverb('cave');actual=np.concatenate([streaming.process(audio[i:i+511]) for i in range(0,len(audio),511)])
        np.testing.assert_allclose(actual,expected,atol=1e-6)
        tail=np.concatenate(list(streaming.flush()));self.assertEqual(len(tail),39600);self.assertTrue(np.any(tail));self.assertTrue(np.isfinite(tail).all())
        self.assertEqual(list(streaming.flush(lambda:True)),[])
        np.testing.assert_array_equal(Reverb('dry').process(audio),audio)
        np.testing.assert_array_equal(Reverb('cave',0).process(audio),audio)
    def test_zone_wire_backwards_compatible(self):
        self.assertEqual(parse_frame(b'XIS1\tspeak\tx\t150\nA : Hello').zone,0)
        self.assertEqual(parse_frame(b'XIS1\tspeak\tx\t150\t233\nA : Hello').zone,233)
        with self.assertRaises(ValueError):parse_frame(b'XIS1\tspeak\tx\t150\t-1\nA : Hello')
    def test_settings_and_npc_override_persist(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'npcs.sqlite3';db=registry.Registry(path,service.DEFAULTS)
            db.encounter('Halver');self.assertEqual(db.effect_profile('Halver',233)['preset'],'stone_hall')
            db.edit('halver','effect','ethereal');self.assertEqual(db.effect_profile('Halver',233)['preset'],'ethereal')
            db.set_effects(False,.5,'auto');self.assertEqual(db.effect_profile('Halver',233)['preset'],'dry');db.close()
            db=registry.Registry(path,service.DEFAULTS)
            self.assertEqual(db.effects()['strength'],.5);self.assertEqual(db.public(db.db.execute("SELECT * FROM npcs WHERE key='halver'").fetchone())['effect'],'ethereal');db.close()

    def test_backend_tail_cancellation_and_fresh_utterance(self):
        from pocket_backend import PocketBackend
        backend=PocketBackend.__new__(PocketBackend);backend.rate=24000
        backend.config={'voice_catalog':{'test':{'speed':1,'volume':1}}};backend.configure(1,0,1)
        backend.configure_environment('cave',1)
        audio=np.ones(2400,dtype=np.float32)*.1
        backend.generate=lambda *a:iter([audio])
        first=list(backend.pcm('test','test'))
        self.assertEqual(sum(map(len,first)),(2400+39600)*2)
        self.assertEqual(first,list(backend.pcm('test','test')))
        cancelled=False;stream=backend.pcm('test','test',lambda:cancelled)
        next(stream);cancelled=True;self.assertEqual(list(stream),[])
