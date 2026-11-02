import unittest
from unittest.mock import patch
import numpy as np
from compare import StableScorer, metrics


class CompatibilityTests(unittest.TestCase):
    def test_zero_feature_values_stay_finite(self):
        scorer=StableScorer.__new__(StableScorer)
        scorer.target_features={'zero':0.,'negative':-2.,'tiny':1e-20}
        penalty=scorer.target_feature_penalty({'zero':0.,'negative':-1.,'tiny':0.})
        self.assertTrue(np.isfinite(penalty))
        self.assertAlmostEqual(penalty,.5)

    def test_metrics_excludes_waveform(self):
        value=dict(score=np.float32(1),target_similarity=.5,audio=np.ones(10))
        self.assertEqual(metrics(value),dict(score=1.,target_similarity=.5))


if __name__=='__main__':unittest.main()
