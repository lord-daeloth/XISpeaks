from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'companion'))
from audio_effects import process_pcm, EffectsQueue


class AudioEffectsTests(unittest.TestCase):
    def test_unity_is_bit_exact_and_silence_remains_silent(self):
        raw = np.array([-32768,-100,0,100,32767],dtype='<i2').tobytes()
        self.assertIs(process_pcm(raw), raw)
        self.assertEqual(process_pcm(raw,volume=0), bytes(len(raw)))
        self.assertEqual(process_pcm(b'',pitch=1), b'')

    def test_gain_boosts_quiet_audio_and_limits_peaks_without_wrap(self):
        raw = np.array([1000,-1000,30000,-30000],dtype='<i2').tobytes()
        result = np.frombuffer(process_pcm(raw,volume=3),dtype='<i2')
        self.assertAlmostEqual(int(result[0]),3000,delta=2)
        self.assertAlmostEqual(int(result[1]),-3000,delta=2)
        self.assertGreater(result[2],30000)
        self.assertLess(result[3],-30000)
        self.assertTrue(np.all(np.abs(result.astype(np.int32)) <= 32767))

    def test_pitch_changes_frequency_without_duration(self):
        time = np.arange(48000)/24000
        raw = (np.sin(2*np.pi*220*time)*6000).astype('<i2').tobytes()
        output = process_pcm(raw,pitch=1)
        self.assertEqual(len(output),len(raw))
        samples = np.frombuffer(output,dtype='<i2').astype(float)[6000:-6000]
        spectrum = np.abs(np.fft.rfft(samples*np.hanning(len(samples))))
        peak = np.fft.rfftfreq(len(samples),1/24000)[spectrum.argmax()]
        self.assertAlmostEqual(peak,220*2**(1/12),delta=2)

    def test_stop_during_processing_discards_output(self):
        queue = EffectsQueue()
        state = [False]
        queue.cancelled = lambda: state[0]
        def process(data,pitch,volume):
            state[0]=True
            return data
        with patch('audio_effects.process_pcm',side_effect=process):
            queue.put(b'\x00\x00')
        self.assertTrue(queue.empty())


if __name__ == '__main__':
    unittest.main()
