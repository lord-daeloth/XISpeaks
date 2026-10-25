import json
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'companion'))
from dialogue import Dialogue, clean_dialogue, parse_frame
from service import DEFAULTS, Server, SpeechQueue, load_config


def eventually(predicate, timeout=2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError('Timed out waiting for worker')


class DialogueTests(unittest.TestCase):
    def test_colors_prompts_and_speaker(self):
        self.assertEqual(clean_dialogue(b'\x1e\x01Maat : Take\x07this \x1e\x02item\x1e\x01.\x7f1'),
                         Dialogue('Maat', 'Take this item.'))

    def test_auto_prompt_only_is_not_speech(self):
        self.assertIsNone(clean_dialogue(b'\x7f4\x01'))
        self.assertEqual(clean_dialogue(b'Wait.\x7f4\x06'), Dialogue('', 'Wait.'))

    def test_japanese_and_custom_glyphs(self):
        self.assertEqual(clean_dialogue('こんにちは。'.encode('cp932')).text, 'こんにちは。')
        self.assertEqual(clean_dialogue(b'Use \xef\x1f and \xef\x24.').text, 'Use Fire and Water .')
        self.assertEqual(clean_dialogue(b'R\x88\x69sum\x88\x69').text, 'Résumé')

    def test_colon_in_body_is_preserved(self):
        self.assertEqual(clean_dialogue(b'Maat : Listen: this matters.'), Dialogue('Maat', 'Listen: this matters.'))

    def test_protocol_rejects_player_chat_and_malformed_frames(self):
        for frame in [b'XIS1\tspeak\tid\t9\nPlayer : Hi', b'{}',
                      b'XIS1\tstop\tid\t0\npayload', b'XIS1\tspeak\tid\t150\n' + b'a'*12000]:
            with self.subTest(frame=frame[:50]), self.assertRaises(ValueError):
                parse_frame(frame)
        self.assertEqual(parse_frame(b'XIS1\tspeak\tid\t150\nMaat : Hello').mode, 150)

    def test_config_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            self.assertEqual(load_config(path)['voice'], 'af_heart')
            for data in [{'speed': 'fast'}, {'queue_limit': 1.5}, {'voices': []}, {'unknown': True}]:
                path.write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    load_config(path)


class ControlledBackend:
    def __init__(self, config):
        self.started = []
        self.cancelled = []
        self.release = threading.Event()
        self.closed = False

    def speak(self, dialogue, voice, cancelled):
        self.started.append((dialogue.text, voice))
        while not self.release.wait(0.01):
            if cancelled():
                self.cancelled.append(dialogue.text)
                return

    def close(self):
        self.closed = True


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.backend = ControlledBackend({})
        self.config = dict(DEFAULTS, queue_limit=2, voices={'Maat': 'am_michael'})
        self.queue = SpeechQueue(self.config, lambda _: self.backend)
        eventually(lambda: self.queue.status().startswith('ready'))

    def tearDown(self):
        self.queue.close()

    def test_order_duplicate_voice_and_overflow(self):
        first = Dialogue('Maat', 'first')
        self.assertTrue(self.queue.submit(first))
        eventually(lambda: len(self.backend.started) == 1)
        self.assertFalse(self.queue.submit(first))
        for text in ('second', 'third', 'fourth'):
            self.queue.submit(Dialogue('', text))
        self.backend.release.set()
        eventually(lambda: len(self.backend.started) == 3)
        self.assertEqual(self.backend.started, [('first', 'am_michael'), ('third', 'af_heart'), ('fourth', 'af_heart')])

    def test_stop_cancels_current_and_clears_waiting(self):
        self.queue.submit(Dialogue('', 'current'))
        eventually(lambda: bool(self.backend.started))
        self.queue.submit(Dialogue('', 'waiting'))
        self.queue.stop()
        eventually(lambda: bool(self.backend.cancelled))
        self.backend.release.set()
        self.queue.submit(Dialogue('', 'new'))
        eventually(lambda: len(self.backend.started) == 2)
        self.assertEqual([x[0] for x in self.backend.started], ['current', 'new'])

    def test_expired_waiting_line_is_dropped(self):
        self.queue.submit(Dialogue('', 'current'))
        eventually(lambda: bool(self.backend.started))
        self.queue.submit(Dialogue('', 'stale'))
        with self.queue.condition:
            generation, _, dialogue, voice = self.queue.pending[0]
            self.queue.pending[0] = (generation, time.monotonic() - 60, dialogue, voice)
        self.backend.release.set()
        eventually(lambda: not self.queue.pending and self.queue.state == 'ready')
        self.assertEqual(len(self.backend.started), 1)

    def test_real_udp_status_filtering_and_stop(self):
        server = Server(self.queue, 0)
        stopped = threading.Event()
        thread = threading.Thread(target=server.run, args=(stopped,))
        thread.start()
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
                client.settimeout(2)
                destination = server.socket.getsockname()
                client.sendto(b'XIS1\tping\t1\t0\n', destination)
                self.assertTrue(client.recv(1024).startswith(b'XIS1\tOK\tready'))
                client.sendto(b'XIS1\tspeak\t2\t9\nPlayer : ignored', destination)
                frame = b'XIS1\tspeak\t3\t150\nMaat : Hello\x7f1'
                client.sendto(frame, destination)
                client.sendto(frame, destination)
                eventually(lambda: len(self.backend.started) == 1)
                client.sendto(b'XIS1\tstop\t4\t0\n', destination)
                eventually(lambda: len(self.backend.cancelled) == 1)
                self.assertEqual(self.backend.started, [('Hello', 'am_michael')])
        finally:
            stopped.set()
            thread.join(2)
            server.close()

    def test_mode_142_named_dialogue_only(self):
        server = Server(self.queue, 0)
        try:
            server.handle(b'XIS1\tspeak\t1\t142\nAn unnamed system notice.', ('127.0.0.1', 12345))
            server.handle(b'XIS1\tspeak\t2\t142\nHalver : Be well.\x7f1', ('127.0.0.1', 12345))
            server.handle(b'XIS1\tspeak\t3\t152\n[10:05pm] Faurie : Goodbye.', ('127.0.0.1', 12345))
            eventually(lambda: bool(self.backend.started))
            self.assertEqual(self.backend.started, [('Be well.', 'af_heart')])
            self.assertFalse(self.queue.pending)
        finally:
            server.close()


class StartupTests(unittest.TestCase):
    def test_failed_voice_does_not_disable_next_line(self):
        class Backend(ControlledBackend):
            def speak(self, dialogue, voice, cancelled):
                if dialogue.text == 'bad':
                    raise RuntimeError('Voice asset unavailable')
                self.started.append((dialogue.text, voice))
        backend = Backend({})
        queue = SpeechQueue(dict(DEFAULTS), lambda _: backend)
        try:
            with self.assertLogs('XISpeaks', level='ERROR'):
                queue.submit(Dialogue('', 'bad'))
                eventually(lambda: bool(queue.last_error))
            queue.submit(Dialogue('', 'good'))
            eventually(lambda: len(backend.started) == 1)
            self.assertEqual(queue.state, 'ready')
            self.assertEqual(queue.last_error, '')
        finally:
            queue.close()

    def test_stop_during_model_load_does_not_replay_old_lines(self):
        loaded = threading.Event()
        backend = ControlledBackend({})
        backend.release.set()
        def factory(config):
            loaded.wait(2)
            return backend
        queue = SpeechQueue(dict(DEFAULTS), factory)
        try:
            queue.submit(Dialogue('', 'old'))
            queue.stop()
            loaded.set()
            queue.submit(Dialogue('', 'new'))
            eventually(lambda: len(backend.started) == 1)
            self.assertEqual(backend.started[0][0], 'new')
        finally:
            loaded.set()
            queue.close()


if __name__ == '__main__':
    unittest.main()
