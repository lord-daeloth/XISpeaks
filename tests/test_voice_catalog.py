import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'companion'),str(ROOT/'voice_editor'),str(ROOT/'piper_trainer'),str(ROOT/'scripts')]
from voice_catalog import normalize,Policy,Store,merge_stock
import registry
from preview import measure

class CatalogTests(unittest.TestCase):
    def catalog(self):
        return {key:normalize(key,dict(model='test.onnx',gender=gender)) for key,gender in [('am_one','m'),('af_two','f'),('au_both','a')]}
    def test_random_eligible_uses_policy_and_keeps_tuning(self):
        import service
        data=self.catalog();data['am_one']['automatic']=False
        with patch.object(registry,'VOICES',list(data)),patch.object(registry,'BLENDING_ENABLED',False):
            db=registry.Registry(':memory:',dict(service.DEFAULTS,voice='am_one',voice_pool=list(data),voice_catalog=data))
            try:
                db.encounter('Npc');db.edit('npc','preference','masculine')
                db.edit('npc','profile',dict(voice='af_two',speed=.9,pitch=-1))
                result=db.edit('npc','random_eligible')
                self.assertEqual(result['voice'],'au_both')
                self.assertEqual(result['base_speed'],.9);self.assertEqual(result['base_pitch'],-1)
                data['au_both']['npc_types']['goblin']=False
                db.edit('npc','preset',dict(name='goblin',enabled=True))
                with self.assertRaisesRegex(ValueError,'No eligible'):db.edit('npc','random_eligible')
                self.assertEqual(db.voice_for('Npc'),'au_both')
            finally:db.close()

    def test_androgynous_metadata_and_intersection(self):
        data=self.catalog();data['au_both']['npc_types']['goblin']=False
        policy=Policy(data)
        self.assertIn('am_one',policy.candidates('masculine',{'elvaan':True}))
        self.assertIn('am_one',policy.candidates('unknown',{'mithra':True}))
        self.assertNotIn('am_one',policy.candidates('feminine',{'mithra':True}))
        self.assertIn('au_both',policy.candidates('masculine',{'child':True}))
        self.assertIn('au_both',policy.candidates('feminine',{'child':True}))
        self.assertIn('au_both',policy.candidates('unknown',{}))
        self.assertNotIn('au_both',policy.candidates('unknown',{'child':True,'goblin':True}))
        data['af_two']['npc_types']['child']=False
        self.assertEqual(Policy(data).candidates('feminine',{'child':True,'goblin':True}),[])
        self.assertEqual(Policy(data).choose('foo','feminine',{'child':True,'goblin':True}),'')
    def test_registry_eligibility_manual_override_and_tuning_approval(self):
        import service
        data=self.catalog()
        for entry in data.values():entry['npc_types']['moogle']=False
        with patch.object(registry,'VOICES',list(data)),patch.object(registry,'BLENDING_ENABLED',False):
            db=registry.Registry(':memory:',dict(service.DEFAULTS,voice='am_one',voice_pool=list(data),voice_catalog=data))
            try:
                db.encounter('Moogle');db.edit('moogle','preset',dict(name='moogle',enabled=True))
                self.assertIsNone(db.playback('Moogle')['voice'])
                self.assertIn('No eligible',db.page(search='Moogle')['rows'][0]['assignment_error'])
                db.edit('moogle','voice','am_one');self.assertEqual(db.playback('Moogle')['voice'],'am_one')
                first=db.page(search='Moogle')['rows'][0]['fingerprint']
                data['am_one']['volume']=.7
                self.assertNotEqual(first,db.page(search='Moogle')['rows'][0]['fingerprint'])
            finally:db.close()
    def test_save_backup_conflict_and_stock_refresh(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'test.onnx').touch();(root/'test.onnx.json').write_text('{}')
            path=root/'catalog.json';path.write_text(json.dumps(self.catalog()))
            store=Store(path);other=Store(path);updated=copy.deepcopy(store.catalog)
            updated['am_one'].update(volume=.75,speed=.8,gender='a')
            del updated['af_two'];store.save(updated,{'af_two'})
            self.assertEqual(len(list((root/'catalog-backups').glob('*.json'))),1)
            self.assertTrue(store.catalog['am_one']['sound_revision'])
            with self.assertRaises(ValueError):other.save(other.catalog)
            generated=self.catalog()
            for entry in generated.values():entry['stock']=True
            merged=merge_stock(generated,store.catalog,store.removed)
            self.assertNotIn('af_two',merged)
            self.assertEqual(merged['am_one']['volume'],.75)
            self.assertEqual(merged['am_one']['gender'],'a')
    def test_measurement_uses_final_pcm_and_duration(self):
        pcm=np.full(24000,16384,dtype='<i2').tobytes();stats=measure(pcm)
        self.assertEqual(stats['milliseconds'],1000);self.assertEqual(stats['peak'],.5)
        self.assertAlmostEqual(stats['peak_dbfs'],-6.0205999)
        self.assertAlmostEqual(stats['rms_dbfs'],stats['peak_dbfs'])
        self.assertIsNone(measure(bytes(100))['peak_dbfs'])

    def test_live_reload_removes_override_and_updates_playback_tuning(self):
        from piper_service import CatalogRuntime
        import service
        with tempfile.TemporaryDirectory() as folder,patch.object(registry,'VOICES',list(self.catalog())),patch.object(registry,'BLENDING_ENABLED',False):
            root=Path(folder);(root/'test.onnx').touch();(root/'test.onnx.json').write_text('{}')
            path=root/'catalog.json';path.write_text(json.dumps(self.catalog()))
            store=Store(path);config=dict(service.DEFAULTS,voice='am_one',voice_pool=list(store.catalog),voice_catalog=store.catalog)
            db=registry.Registry(':memory:',config)
            try:
                db.encounter('Npc');db.edit('npc','voice','am_one')
                runtime=CatalogRuntime(db,config,path)
                changed={'af_two':copy.deepcopy(store.catalog['af_two'])};changed['af_two'].update(volume=.6,speed=.8)
                store.save(changed,{'am_one','au_both'});runtime.reload()
                self.assertEqual(db.voice_for('Npc'),'af_two')
                self.assertIsNone(db.db.execute("SELECT manual_voice FROM npcs WHERE key='npc'").fetchone()[0])
                self.assertEqual(config['piper_models']['af_two']['volume'],.6)
                self.assertEqual(config['piper_models']['af_two']['speed'],.8)
                self.assertEqual(db.voice_catalog['af_two']['gender'],'f')
            finally:db.close()

    def test_preview_resets_session_seed_and_zero_noise(self):
        from preview import Renderer
        from types import SimpleNamespace
        events=[]
        renderer=Renderer()
        renderer.backend=SimpleNamespace(config={},model=SimpleNamespace(temp=.3),rate=24000,configure=lambda *args:None)
        def pcm(*args):
            events.append(renderer.backend.model.temp)
            return [np.full(240,1000,dtype='<i2').tobytes()]
        renderer.backend.pcm=pcm
        entry=dict(model='test.safetensors',speaker_id=None,speed=1,volume=1)
        with tempfile.TemporaryDirectory() as folder,patch.dict(sys.modules,torch=SimpleNamespace(manual_seed=lambda value:events.append(value))):
            (Path(folder)/entry['model']).write_bytes(b'fixture')
            path=Path(folder)/'sample.wav'
            renderer.render('am_test',entry,folder,'Hello',path,lambda:False,'fixed',123)
            renderer.render('am_test',entry,folder,'Hello',path,lambda:False,'zero',999)
            self.assertEqual(events,[123,.3,42,0])
            self.assertEqual(renderer.backend.model.temp,.3)
            with self.assertRaises(ValueError):renderer.render('am_test',entry,folder,'Hello',path,lambda:False,'fixed',-1)

    def test_calibration_multiplies_global_speed_and_gain(self):
        import scipy.signal
        from collections import OrderedDict
        from types import SimpleNamespace
        from piper_backend import PiperBackend
        backend=PiperBackend.__new__(PiperBackend);backend.cache=OrderedDict();backend.configure(1.2,0,2)
        backend.models={'am_test':dict(path='shared',speaker_id=2,speed=.8,volume=.25)}
        scales=[]
        def synth(text,syn_config):
            scales.append(syn_config.length_scale)
            yield SimpleNamespace(audio_int16_bytes=np.full(2400,4000,dtype='<i2').tobytes(),sample_rate=24000)
        fake=SimpleNamespace(PiperVoice=SimpleNamespace(load=lambda *a,**k:SimpleNamespace(synthesize=synth)),SynthesisConfig=SimpleNamespace)
        with patch.dict(sys.modules,piper=fake):parts=list(backend.pcm('Hello','am_test'))
        self.assertAlmostEqual(scales[0],1/(1.2*.8))
        self.assertAlmostEqual(int(np.frombuffer(parts[0],dtype='<i2')[0]),2000,delta=1)

if __name__=='__main__':unittest.main()
