import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import soundfile as sf
import run


class PreparationTests(unittest.TestCase):
    def test_stereo_gain_and_source_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source.wav'
            tone=np.sin(np.arange(48000*2)*2*np.pi*220/48000)*.1
            sf.write(source,np.column_stack([tone,tone]),48000)
            original=source.read_bytes()
            segments=[dict(start=.1,end=1.8,text='Test recording.')]
            with patch.multiple(run,OUT=root/'out',SOURCE=source,SEGMENTS=segments,PEAK_DB=-3):
                info=run.prepare()
            audio,sr=sf.read(root/'out/reference.wav')
            self.assertEqual(audio.ndim,1)
            self.assertAlmostEqual(20*np.log10(np.max(np.abs(audio))),-3,places=2)
            self.assertEqual(source.read_bytes(),original)
            self.assertEqual(info['training_utterances'],1)
            _,rate=sf.read(root/'out/dataset/0.wav');self.assertEqual(rate,22050)

    def test_invalid_boundaries_do_not_create_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source.wav'
            sf.write(source,np.ones(24000)*.1,24000)
            with patch.multiple(run,OUT=root/'out',SOURCE=source,SEGMENTS=[dict(start=0,end=2,text='Too long.')],PEAK_DB=None):
                with self.assertRaises(ValueError):run.prepare()
            self.assertFalse((root/'out').exists())


if __name__=='__main__':unittest.main()
