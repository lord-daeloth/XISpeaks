from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'companion'))
from stutters import prepare, boundaries, insert_breaks


class StutterTests(unittest.TestCase):
    def test_word_pronunciation_controls_th_and_repetitions(self):
        sounds = {'that': 'ðæt', 'think': 'θɪŋk', 'no': 'nO'}
        text, mapping = prepare('Th-that, th-think, n-n-no!', lambda word: (sounds[word], []))
        self.assertIn('/ð ðæt/', text)
        self.assertIn('/θ θɪŋk/', text)
        self.assertIn('/n n nO/', text)
        self.assertEqual(mapping['n n nO'], 2)

    def test_regular_hyphens_unchanged_and_uncertain_onset_cleaned(self):
        text = 'well-known, co-operate, re-release, bye-bye, I-I, X-ray, th-other'
        self.assertEqual(prepare(text, lambda _: self.fail('Unexpected pronunciation lookup')), (text, {}))
        self.assertEqual(prepare('H-hour', lambda _: ('ˈaʊɹ', [])), ('Hour', {}))

    def test_alignment_handles_mid_sentence_and_multiple_breaks(self):
        tokens = [SimpleNamespace(phonemes='a', whitespace=True),
                  SimpleNamespace(phonemes='n n nO', whitespace=False)]
        result = SimpleNamespace(tokens=tokens, phonemes='a n n nO',
            pred_dur=np.array([3]+[1]*8+[3]), audio=np.zeros(20000))
        self.assertEqual(boundaries(result, {'n n nO': 2}), [2100, 3300])
        result.phonemes='mismatch'
        self.assertEqual(boundaries(result, {'n n nO': 2}), [])

    def test_breaks_are_exact_and_invalid_positions_ignored(self):
        audio = np.full(12000, 1000, dtype='<i2')
        output = np.frombuffer(insert_breaks(audio.tobytes(), [1000, 1000, 4000, -1, 99999]), dtype='<i2')
        self.assertEqual(len(output), len(audio)+2*1440)
        self.assertTrue(np.all(output[1000:2440] == 0))
        self.assertTrue(np.all(output[5440:6880] == 0))


if __name__ == '__main__':
    unittest.main()
