import json

from pathlib import Path

import sys

import tempfile

import threading

import unittest

from unittest.mock import patch

from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]

sys.path.insert(0,str(ROOT/'pocket_studio'))

import studio_engine as s



class StudioTests(unittest.TestCase):

    def test_multiple_regions_exclude_unwanted_audio_and_keep_order(self):
        import numpy as np
        import soundfile as sf
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            source=np.concatenate([np.full(48000,.1),np.full(48000,.8),np.full(48000,.3)])
            sf.write(root/'source.wav',source,24000,subtype='FLOAT')
            prepared,meta=s.prepare(root,0,6,'Off',False,regions=[(4,6),(0,2)])
            audio,rate=sf.read(prepared/'reference.wav')
            self.assertEqual(len(audio),96000)
            self.assertAlmostEqual(audio[24000],.1,places=4)
            self.assertAlmostEqual(audio[72000],.3,places=4)
            self.assertLess(audio.max(),.31)
            self.assertEqual(meta['regions'],[(0,2),(4,6)])
            self.assertEqual(meta['prepared']['seconds'],4)
            for regions in [[(0,2),(1,3)],[(0,1)],[(0,7)],[(float('nan'),2)]]:
                with self.assertRaises(ValueError):s.selection(root,0,6,regions)
            sf.write(root/'source.wav',np.ones(40*24000)*.1,24000)
            with self.assertRaisesRegex(ValueError,'combined'):s.selection(root,0,40,[(0,16),(20,36)])

    def test_pending_section_preview_allows_short_and_long_excerpts(self):
        import numpy as np
        import soundfile as sf
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            sf.write(root/'source.wav',np.concatenate([np.full(24000,.1),np.full(34*24000,.3)]),24000)
            path=s.preview_section(root,.25,.75)
            audio,rate=sf.read(path)
            self.assertEqual(len(audio),12000);self.assertAlmostEqual(audio.mean(),.1,places=4)
            path=s.preview_section(root,1,35)
            self.assertEqual(sf.info(path).frames,34*24000)
            with self.assertRaises(ValueError):s.preview_section(root,2,1)
            with self.assertRaises(s.Cancelled):s.preview_section(root,0,1,lambda:True)

    def test_audition_text_persists_and_defaults(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(s,'OUTPUT',Path(folder)):
            self.assertEqual(s.load_audition_text(),s.DEFAULT_AUDITION_TEXT)
            s.save_audition_text('Custom line\nAnother line')
            self.assertEqual(s.load_audition_text(),'Custom line\nAnother line')
            s.save_audition_text('');self.assertEqual(s.load_audition_text(),'')
            s.save_audition_text(s.DEFAULT_AUDITION_TEXT)
            self.assertEqual(s.load_audition_text(),s.DEFAULT_AUDITION_TEXT)

    def test_profile_automatic_assignment_flag(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'candidate.json').write_text(json.dumps(dict(model_revision='test',reference_sha256='test')))
            args=(root,'am_test','Test','m','a','Volunteer','Permission granted',{})
            self.assertFalse(s.profile(*args)['automatic'])
            self.assertTrue(s.profile(*args,automatic=True)['automatic'])

    def test_generated_id(self):

        self.assertEqual(s.stable_voice_id('Cloud-Steve-2','m','a'),'am_cloud_steve_2')

        self.assertEqual(s.stable_voice_id('  Élodie / Test! ','f','b'),'bf_elodie_test')



    def test_export_replacement_requires_opt_in_and_rolls_back(self):

        with tempfile.TemporaryDirectory() as folder,patch.object(s,'validate_state'):

            root=Path(folder);candidate=root/'candidate';candidate.mkdir();(candidate/'voice.safetensors').write_bytes(b'new')

            target=root/'xu_test.safetensors';target.write_bytes(b'old');meta=root/'xu_test.json';meta.write_text('old metadata')

            args=(candidate,'xu_test',dict(model=target.name),root)

            with self.assertRaisesRegex(ValueError,'Confirm replacement'):s.export(*args)

            self.assertEqual(target.read_bytes(),b'old')

            with patch.object(s,'atomic_json',side_effect=OSError('write failed')):

                with self.assertRaises(OSError):s.export(*args,overwrite=True)

            self.assertEqual(target.read_bytes(),b'old');self.assertEqual(meta.read_text(),'old metadata')

            s.export(*args,overwrite=True)

            self.assertEqual(target.read_bytes(),b'new');self.assertIn('xu_test',json.loads(meta.read_text()))



    def test_install_replacement_requires_opt_in_and_restores_old_state(self):

        class FakeStore:

            def __init__(self,path):self.path=Path(path);self.catalog={'xu_test':dict(model='xu_test.safetensors')};self.removed=set()

            def save(self,*args):raise ValueError('Catalog changed')

        with tempfile.TemporaryDirectory() as folder,patch.object(s,'Store',FakeStore),patch.object(s,'validate_state'):

            root=Path(folder);candidate=root/'candidate';candidate.mkdir();(candidate/'voice.safetensors').write_bytes(b'new')

            target=root/'xu_test.safetensors';target.write_bytes(b'old')

            args=(candidate,'xu_test',dict(model=target.name),root/'catalog.json')

            with self.assertRaisesRegex(ValueError,'Confirm replacement'):s.install(*args)

            with self.assertRaisesRegex(ValueError,'Catalog changed'):s.install(*args,overwrite=True)

            self.assertEqual(target.read_bytes(),b'old')

            with patch.object(FakeStore,'save') as save:

                s.install(*args,overwrite=True);save.assert_called_once()

            self.assertEqual(target.read_bytes(),b'new')



    def test_video_without_audio_reports_clear_error(self):

        with tempfile.TemporaryDirectory() as folder:

            media=Path(folder)/'video.mp4';media.write_bytes(b'fixture')

            with patch.object(s,'run_tool',return_value=b'{"streams":[]}'),patch.object(s,'tool',return_value='ffprobe'):

                with self.assertRaisesRegex(ValueError,'no audio track'):s.probe(media)



    def test_recorder_finishes_wav_and_releases_device(self):

        import wave

        stop=threading.Event();calls=[]

        class Stream:

            def read(self,n,**kwargs):

                calls.append('read')

                if calls.count('read')==3:stop.set()

                return b'\x10\x00'*n

            def close(self):calls.append('close')

        class Audio:

            def get_device_info_by_index(self,i):return {'defaultSampleRate':1000}

            def open(self,**kwargs):return Stream()

            def terminate(self):calls.append('terminate')

        with tempfile.TemporaryDirectory() as folder,patch.object(s,'OUTPUT',Path(folder)),patch.dict(sys.modules,pyaudio=SimpleNamespace(PyAudio=Audio,paInt16=8)):

            path=s.record(0,stop)

            with wave.open(str(path)) as wav:

                self.assertEqual(wav.getnframes(),3072);self.assertEqual(wav.getnchannels(),1)

        self.assertEqual(calls[-2:],['close','terminate'])



    def test_install_rollback_on_concurrent_catalog_edit(self):

        class FakeStore:

            def __init__(self,path):self.path=Path(path);self.catalog={};self.removed=set()

            def save(self,*args):raise ValueError('Catalog changed')

        with tempfile.TemporaryDirectory() as folder,patch.object(s,'Store',FakeStore),patch.object(s,'validate_state'):

            root=Path(folder);candidate=root/'candidate';candidate.mkdir();(candidate/'voice.safetensors').write_bytes(b'state')

            with self.assertRaisesRegex(ValueError,'Catalog changed'):s.install(candidate,'xu_test',dict(model='xu_test.safetensors'),root/'catalog.json')

            self.assertFalse((root/'xu_test.safetensors').exists())



if __name__=='__main__':unittest.main()
