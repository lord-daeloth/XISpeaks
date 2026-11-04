"""Piper migration contracts without loading models or opening a sound device."""
from collections import OrderedDict
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import numpy as np
import scipy.signal
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'companion'),str(ROOT/'piper_trainer')]
from piper_backend import PiperBackend,speech_parts
import registry
from app import parse_stages

class PiperTests(unittest.TestCase):
    def test_stages_are_bounded_unique_and_ordered(self):
        self.assertEqual(parse_stages('100,300,1000'),[100,300,1000])
        for value in ('','0','5001','300,100','100,100'):
            with self.assertRaises(ValueError):parse_stages(value)

    def test_piper_registry_disallows_blends(self):
        with patch.object(registry,'BLENDING_ENABLED',False):
            self.assertEqual(registry.choose_blend('halver','am_echo',registry.VOICES),'am_echo')
            with self.assertRaises(ValueError):registry.validate_voice('0.70*am_echo + 0.30*am_onyx')

    def test_pause_lengths_speed_and_cancellation(self):
        backend=PiperBackend.__new__(PiperBackend)
        backend.models={'am_test':'unused'};backend.cache=OrderedDict();backend.configure(1.2,0,1)
        calls=[]
        pcm=np.full(2205,1000,dtype='<i2').tobytes()
        def synth(text,syn_config):
            calls.append((text,syn_config.length_scale))
            for _ in range(2):yield SimpleNamespace(audio_int16_bytes=pcm,sample_rate=22050)
        fake=SimpleNamespace(PiperVoice=SimpleNamespace(load=lambda *a,**k:SimpleNamespace(synthesize=synth)),SynthesisConfig=SimpleNamespace)
        with patch.dict(sys.modules,piper=fake):
            parts=list(backend.pcm('Hm? Look--over there!', 'am_test'))
            self.assertEqual([len(x) for x in parts],[4800,14400,4800,8640,4800,14400,4800,14400])
            self.assertEqual(calls[0][0],'Hmmmm? Look')
            self.assertAlmostEqual(calls[0][1],1/1.2)
            self.assertEqual(list(backend.pcm('Stop','am_test',lambda:True)),[])
            self.assertEqual(len(calls),2)

    def test_custom_voice_not_in_automatic_pool_and_catalog_path_is_bounded(self):
        from piper_service import configure_catalog
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder);(path/'voice.onnx').touch();(path/'voice.onnx.json').write_text('{}')
            catalog=path/'catalog.json';catalog.write_text(json.dumps({'am_custom':{'model':'voice.onnx','automatic':False}}))
            original=registry.VOICES[:]
            try:
                with patch.object(registry,'BLENDING_ENABLED',True),patch.object(registry,'YOUNG_VOICES',()):
                    result=configure_catalog(catalog)
                    self.assertFalse(result['am_custom']['automatic'])
                    catalog.write_text(json.dumps({'am_custom':{'model':'../outside.onnx'}}))
                    with self.assertRaises(ValueError):configure_catalog(catalog)
            finally:registry.VOICES[:]=original

class ExpandedCatalogTests(unittest.TestCase):
    def test_highest_quality_per_family(self):
        from setup_voices import best_english,make_catalog
        index={name:dict(quality=quality,num_speakers=1) for name,quality in
            [('en_US-demo-low','low'),('en_US-demo-high','high'),('en_GB-demo-medium','medium'),('de_DE-demo-high','high')]}
        self.assertEqual([key for key,_ in best_english(index)],['en_GB-demo-medium','en_US-demo-high'])
        catalog=make_catalog([('en_US-libritts-high',dict(num_speakers=2,speaker_id_map={'p1':1,'p2':0}))],{'1':'f','2':'m'})
        self.assertEqual(catalog['af_libritts_p1']['speaker_id'],1)
        self.assertEqual(catalog['am_libritts_p2']['speaker_id'],0)

    def test_speakers_share_model_session(self):
        backend=PiperBackend.__new__(PiperBackend);backend.cache=OrderedDict();backend.configure(1,0,1)
        backend.models={name:dict(path='shared.onnx',speaker_id=sid) for name,sid in [('af_one',5),('am_two',8)]}
        loaded=[];speakers=[]
        def synth(text,syn_config):
            speakers.append(syn_config.speaker_id)
            yield SimpleNamespace(audio_int16_bytes=np.full(2400,1000,dtype='<i2').tobytes(),sample_rate=24000)
        def load(path,**kwargs):loaded.append(path);return SimpleNamespace(synthesize=synth)
        fake=SimpleNamespace(PiperVoice=SimpleNamespace(load=load),SynthesisConfig=SimpleNamespace)
        with patch.dict(sys.modules,piper=fake):
            list(backend.pcm('Hello','af_one'));list(backend.pcm('Hello','am_two'))
        self.assertEqual(loaded,['shared.onnx']);self.assertEqual(speakers,[5,8])

    def test_catalog_migration_preserves_choices_and_retires_halver(self):
        import service
        sys.path.insert(0,str(ROOT/'scripts'))
        from piper_service import create_registry
        pool=['am_ryan','af_lessac','bm_alan','bf_cori','am_new']
        with tempfile.TemporaryDirectory() as folder,patch.object(registry,'VOICES',pool+['am_halver']),patch.object(registry,'BLENDING_ENABLED',False):
            path=Path(folder)/'npcs.sqlite3'
            config=dict(service.DEFAULTS,voice='am_ryan',voice_pool=pool)
            db=registry.Registry(path,config)
            db.encounter('Halver');db.edit('halver','voice','am_halver')
            db.encounter('Manual');db.edit('manual','voice','am_ryan')
            db.encounter('Approved')
            with db.db:
                db.db.execute("UPDATE npcs SET auto_voice='am_ryan' WHERE key='approved'")
                row=db.db.execute("SELECT * FROM npcs WHERE key='approved'").fetchone()
                db.db.execute("UPDATE npcs SET approval=? WHERE key='approved'",(db.public(row)['fingerprint'],))
                db.db.execute("INSERT INTO metadata VALUES ('piper_seed_v1','1')")
            db.close()
            with patch.object(registry,'VOICES',pool):
                db=create_registry(config,path)
                self.assertIn(db.voice_for('Halver'),pool)
                self.assertIsNone(db.db.execute("SELECT manual_voice FROM npcs WHERE key='halver'").fetchone()[0])
                self.assertEqual(db.voice_for('Manual'),'am_ryan')
                self.assertEqual(db.voice_for('Approved'),'am_ryan')
                self.assertTrue(db.db.execute("SELECT approval FROM npcs WHERE key='approved'").fetchone()[0])
                db.close()
            self.assertEqual(len(list(Path(folder).glob('*.bak'))),2)

    def test_voice_search_fits_udp_and_supports_last_page(self):
        import service
        responses=[]
        server=service.Server.__new__(service.Server);server.ui_replies={}
        server.registry=SimpleNamespace(contributions_enabled=False)
        server.speech=SimpleNamespace(status=lambda:'ready',last_error='')
        server.socket=SimpleNamespace(sendto=lambda data,address:responses.append(data))
        with patch.object(service,'VOICES',[f'au_speaker_{i:04}' for i in range(1998)]):
            for i,request in enumerate([dict(action='voice_list',page=49),dict(action='voice_list',search='1997')]):
                server.handle_ui(b'XISUI\t'+str(i).encode()+b'\n'+json.dumps(request).encode(),('127.0.0.1',1234))
        self.assertTrue(all(len(r)<12000 for r in responses))
        last=json.loads(responses[-1].partition(b'\n')[2]);self.assertEqual(last['voices'],['au_speaker_1997'])
        self.assertEqual(json.loads(responses[0].partition(b'\n')[2])['voice_total'],1998)

class MooglePacingTests(unittest.TestCase):
    def test_preset_values_and_child_stacking(self):
        self.assertEqual(registry.preset_effects({'goblin':True}),(1.15,3.0))
        self.assertEqual(registry.preset_effects({'child':True}),(1.0,1.0))
        self.assertEqual(registry.preset_effects({'moogle':True}),(1.075,1.5))
        self.assertEqual(registry.preset_effects({'child':True,'tarutaru':True}),(1.1,2.0))

    def test_moogle_migration_is_once_only_and_preserves_manual_profile(self):
        import service
        from piper_service import migrate_pacing_and_moogles
        db=registry.Registry(':memory:',dict(service.DEFAULTS))
        try:
            db.encounter('Moogle');db.edit('moogle','voice','am_echo');db.set_globals(.9,1.4)
            migrate_pacing_and_moogles(db,':memory:')
            self.assertEqual(db.globals()['speed'],.9)
            self.assertEqual(db.globals()['volume'],1.4)
            row=db.db.execute("SELECT * FROM npcs WHERE key='moogle'").fetchone()
            self.assertEqual(row['manual_voice'],'am_echo')
            self.assertEqual(row['encounters'],1)
            self.assertTrue(db.public(row)['presets']['moogle'])
            self.assertEqual(db.db.execute('SELECT COUNT(*) FROM npcs WHERE preset_moogle=1').fetchone()[0],37)
            db.edit('moogle','preset',dict(name='moogle',enabled=False));db.set_globals(.9,1.4)
            migrate_pacing_and_moogles(db,':memory:')
            self.assertEqual(db.globals()['speed'],.9)
            self.assertEqual(db.db.execute("SELECT preset_moogle FROM npcs WHERE key='moogle'").fetchone()[0],0)
        finally:db.close()

    def test_catalog_excludes_objects_and_includes_named_moogles(self):
        data=json.loads((ROOT/'data/moogle_associations.json').read_text(encoding='utf-8'))
        names={n['name'] for n in data['npcs']}
        self.assertTrue({'Moogle','Kupofried','Monsieur Kupont','Nomad Moogle'}<=names)
        self.assertFalse({"Moogle's Letter",'Moogle Meeting','Magian Mooglehood','Apollyon Operator'} & names)

if __name__=='__main__':unittest.main()
