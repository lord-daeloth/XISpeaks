from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'companion'), str(ROOT / 'scripts')]
from registry import Registry
from service import DEFAULTS, SpeechQueue
from dialogue import Dialogue
from test_companion import ControlledBackend, eventually
from release_overrides import export_overrides, apply_overrides


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'npcs.sqlite3'
        self.registry = Registry(self.path, DEFAULTS)
        self.registry.encounter('Halver')

    def tearDown(self):
        self.registry.close()
        self.temp.cleanup()

    def candidate(self):
        return self.registry.review_candidate('Halver')

    def test_persistence_staleness_global_volume_and_manual_review(self):
        r = self.registry
        self.assertFalse(r.review_enabled())
        r.set_review_enabled(True)
        fingerprint = self.candidate()['fingerprint']
        r.review_action('halver', fingerprint, 'approve')
        self.assertIsNone(self.candidate())
        r.set_globals(1.5, 2, 'librosa')
        self.assertIsNone(self.candidate())
        r.close()
        self.registry = r = Registry(self.path, DEFAULTS)
        self.assertTrue(r.review_enabled())
        self.assertIsNone(self.candidate())
        r.edit('halver', 'preset', dict(name='goblin', enabled=True))
        self.assertIsNotNone(self.candidate())
        with self.assertRaises(ValueError):
            r.review_action('halver', fingerprint, 'approve')
        r.edit('halver', 'voice', 'am_onyx')
        self.assertIsNone(self.candidate())
        r.edit('halver', 'reset')
        self.assertEqual(r.page(filter_name='unreviewed')['total'], 1)

    def test_queue_deduplication_later_and_changed_voice(self):
        r = self.registry
        r.set_review_enabled(True)
        fingerprint = self.candidate()['fingerprint']
        with patch('registry.time.monotonic', return_value=100):
            r.heard_for_review('Halver', fingerprint)
            r.heard_for_review('Halver', fingerprint)
            self.assertEqual(r.review_state()['review_count'], 1)
            r.review_action('halver', fingerprint, 'later')
        with patch('registry.time.monotonic', return_value=120):
            r.heard_for_review('Halver', fingerprint)
            self.assertEqual(r.review_state()['review_count'], 0)
        with patch('registry.time.monotonic', return_value=181):
            r.heard_for_review('Halver', fingerprint)
            self.assertEqual(r.review_state()['review_count'], 1)
        r.edit('halver', 'preset', dict(name='goblin', enabled=True))
        self.assertEqual(r.review_state()['review_count'], 0)
        r.heard_for_review('Halver', fingerprint)
        self.assertEqual(r.review_state()['review_count'], 0)
        r.set_review_enabled(False)
        self.assertIsNone(r.review_state()['review'])

    def test_prompt_only_after_completed_uncancelled_speech(self):
        r = self.registry
        r.set_review_enabled(True)
        backend = ControlledBackend(DEFAULTS)
        queue = SpeechQueue(DEFAULTS, lambda _: backend, r)
        try:
            eventually(lambda: queue.state == 'ready')
            queue.submit(Dialogue('Halver', 'Hello there.'))
            eventually(lambda: bool(backend.started))
            self.assertEqual(r.review_state()['review_count'], 0)
            queue.stop()
            eventually(lambda: bool(backend.cancelled))
            self.assertEqual(r.review_state()['review_count'], 0)
            backend.release.set()
            queue.submit(Dialogue('Halver', 'Try again.'))
            eventually(lambda: r.review_state()['review_count'] == 1)
        finally:
            queue.close()

    def test_approval_exports_without_review_toggle_or_history(self):
        r = self.registry
        r.set_review_enabled(True)
        r.review_action('halver', self.candidate()['fingerprint'], 'approve')
        seed = Registry(':memory:', DEFAULTS)
        try:
            exported = export_overrides(self.path, seed)
            self.assertEqual(len(exported['npcs']), 1)
            apply_overrides(seed, exported)
            row = seed.page()['rows'][0]
            self.assertEqual(row['review_status'], 'approved')
            self.assertIsNone(row['manual_voice'])
            self.assertEqual(row['encounters'], 0)
            self.assertFalse(seed.review_enabled())
        finally:
            seed.close()

    def test_failed_playback_and_previews_do_not_prompt(self):
        r = self.registry
        r.set_review_enabled(True)
        class Backend:
            fail = True
            def speak(self, *args):
                if self.fail:
                    raise RuntimeError('test synthesis failure')
            def close(self):
                pass
        backend = Backend()
        queue = SpeechQueue(DEFAULTS, lambda _: backend, r)
        try:
            eventually(lambda: queue.state == 'ready')
            queue.submit(Dialogue('Halver', 'Failed speech'))
            eventually(lambda: queue.last_error != '')
            self.assertEqual(r.review_state()['review_count'], 0)
            backend.fail = False
            queue.submit(Dialogue('Halver', 'Preview'), 'af_heart')
            eventually(lambda: queue.last_error == '')
            self.assertEqual(r.review_state()['review_count'], 0)
        finally:
            queue.close()
