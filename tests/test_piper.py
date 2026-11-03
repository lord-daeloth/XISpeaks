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

if __name__=='__main__':unittest.main()
