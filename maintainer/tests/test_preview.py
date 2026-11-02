import sys
from pathlib import Path
import queue
import threading
import unittest
from unittest.mock import Mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from voice_preview import VoicePreview


class PreviewTests(unittest.TestCase):
    def test_settings_reuse_stop_and_cleanup(self):
        events=queue.Queue();backend=Mock();started=threading.Event()
        def speak(dialogue,voice,cancelled):
            self.assertEqual(dialogue.text,'Sample!')
            started.set()
            if voice=='am_michael':
                self.assertTrue(worker.cancelled.wait(3))
                self.assertTrue(cancelled())
        backend.speak.side_effect=speak
        factory=Mock(return_value=backend)
        worker=VoicePreview(lambda *event:events.put(event),factory)
        try:
            worker.play('Zeid','Sample!',dict(voice='am_michael',speed=.9,pitch=-3.5))
            self.assertTrue(started.wait(3));worker.stop()
            self.assertEqual(events.get(timeout=3),('preview_done','Stopped.'))
            backend.configure.assert_called_with(.9,-3.5,1.0,'rubberband')
            worker.play('Zeid','Sample!',dict(voice='bm_george',speed=1,pitch=0))
            self.assertEqual(events.get(timeout=3)[0],'preview_done')
            factory.assert_called_once()
        finally:
            worker.close();worker.thread.join(3)
        backend.close.assert_called_once()

    def test_initialization_error_is_reported_and_retryable(self):
        events=queue.Queue();backend=Mock()
        worker=VoicePreview(lambda *event:events.put(event),Mock(side_effect=[RuntimeError('Missing model'),backend]))
        try:
            sound=dict(voice='af_heart',speed=1,pitch=0)
            worker.play('Test','Hello.',sound)
            self.assertEqual(events.get(timeout=3),('preview_error','Missing model'))
            worker.play('Test','Hello.',sound)
            self.assertEqual(events.get(timeout=3)[0],'preview_done')
        finally:
            worker.close();worker.thread.join(3)
