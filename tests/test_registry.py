import json
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'companion'))
from registry import Registry, VOICES, choose_voice, name_key
from service import DEFAULTS, Server, SpeechQueue
from dialogue import Dialogue
from test_companion import ControlledBackend, eventually


class RegistryFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'npcs.sqlite3'
        self.config = dict(DEFAULTS, voices={'Maat': 'am_michael'})
        self.registry = Registry(self.path, self.config)

    def tearDown(self):
        self.registry.close()
        self.temp.cleanup()


class RegistryTests(RegistryFixture):
    def test_hash_is_stable_and_saved_across_pool_changes(self):
        self.registry.encounter('Halver')
        voice = self.registry.voice_for('Halver')
        self.assertEqual(voice, choose_voice('halver', 'unknown', list(reversed(VOICES))))
        self.registry.close()
        self.registry = Registry(self.path, dict(self.config, voice_pool=['af_heart']))
        self.registry.encounter(' HALVER ')
        self.assertEqual(self.registry.voice_for('Halver'), voice)
        self.registry.encounter('Faurie')
        self.assertEqual(self.registry.voice_for('Faurie'), 'af_heart')
        self.assertEqual(self.registry.page(search='halver')['total'], 1)

    def test_legacy_import_once_override_reset_preference_mute(self):
        self.assertEqual(self.registry.voice_for('maat'), 'am_michael')
        self.registry.edit('maat', 'preference', 'feminine')
        self.assertEqual(self.registry.voice_for('maat'), 'am_michael')
        automatic = self.registry.edit('maat', 'reset')['voice']
        self.assertEqual(automatic[1], 'f')
        self.registry.edit('maat', 'mute', True)
        self.assertIsNone(self.registry.voice_for('Maat'))
        self.registry.close()
        self.registry = Registry(self.path, self.config)
        self.assertIsNone(self.registry.voice_for('Maat'))
        self.registry.edit('maat', 'mute', False)
        self.assertEqual(self.registry.voice_for('Maat'), automatic)
        self.assertEqual(self.registry.page(filter_name='manual')['total'], 0)
        self.registry.edit('maat', 'voice', 'bm_george')
        self.assertEqual(self.registry.voice_for('Maat'), 'bm_george')

    def test_search_literal_pagination_and_recent(self):
        for i in range(30):
            self.registry.encounter(f'Guard {i:02}')
        self.assertEqual(self.registry.page(search='Guard')['total'], 30)
        first = self.registry.page(search='Guard')['rows']
        self.assertEqual(len(first), 12)
        self.assertEqual(first[0]['name'], 'Guard 29')
        self.assertEqual(len(self.registry.page(search='Guard', page=2)['rows']), 6)
        self.assertEqual(self.registry.page(search='%')['total'], 0)
        self.assertEqual(self.registry.page(filter_name='recent')['total'], 30)
        self.assertEqual(self.registry.page(filter_name='manual')['total'], 1)
        self.assertEqual(self.registry.page(page=100)['page'], 2)

    def test_rejected_edits_leave_existing_assignment_intact(self):
        for action, value in [('voice', 'invalid'), ('preference', 'guessed'), ('mute', 'yes'), ('other', None)]:
            with self.subTest(action=action), self.assertRaises(ValueError):
                self.registry.edit('maat', action, value)
        self.assertEqual(self.registry.voice_for('Maat'), 'am_michael')
        self.registry.pool = ['af_heart']
        with self.assertRaises(ValueError):
            self.registry.edit('maat', 'preference', 'masculine')
        self.assertEqual(self.registry.page()['rows'][0]['preference'], 'unknown')

    def test_utf8_names_and_no_blank_npcs(self):
        self.registry.encounter('Élodie')
        self.registry.encounter('ÉLODIE')
        self.assertEqual(self.registry.page(search='élodie')['total'], 1)
        with self.assertRaises(ValueError):
            self.registry.encounter(' ')


class EditorIntegrationTests(RegistryFixture):
    def setUp(self):
        super().setUp()
        self.backend = ControlledBackend({})
        self.speech = SpeechQueue(self.config, lambda _: self.backend, self.registry)
        eventually(lambda: self.speech.state == 'ready')
        self.server = Server(self.speech, 0, self.registry)
        self.client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.client.bind(('127.0.0.1', 0))
        self.client.settimeout(1)
        self.address = self.client.getsockname()
        self.serial = 0

    def tearDown(self):
        self.speech.close()
        self.server.close()
        self.client.close()
        super().tearDown()

    def request(self, request, identity=None):
        self.serial += 1
        identity = identity or str(self.serial)
        frame = b'XISUI\t' + identity.encode() + b'\n' + json.dumps(request).encode()
        self.server.handle(frame, self.address)
        reply = self.client.recv(12000)
        self.assertTrue(reply.startswith(b'XISUI\t' + identity.encode() + b'\n'))
        return json.loads(reply.partition(b'\n')[2])

    def test_encounter_list_edit_and_duplicate_ack(self):
        self.server.handle(b'XIS1\tspeak\tnpc1\t142\nHalver : Hello.', self.address)
        eventually(lambda: bool(self.backend.started))
        reply = self.request(dict(action='list', search='Halver'))
        self.assertTrue(reply['ok'])
        self.assertEqual(reply['rows'][0]['name'], 'Halver')
        request = dict(action='edit', key='halver', edit='voice', value='am_michael')
        first = self.request(request, 'repeat')
        with patch.object(self.registry, 'edit', side_effect=AssertionError('Must not repeat edit')):
            self.assertEqual(self.request(request, 'repeat'), first)
        self.assertEqual(self.registry.voice_for('Halver'), 'am_michael')

    def test_preview_is_not_registered_and_retries_do_not_repeat(self):
        result = self.request(dict(action='preview', voice='bf_emma'), 'preview')
        self.assertTrue(result['ok'])
        eventually(lambda: bool(self.backend.started))
        self.assertEqual(self.backend.started[0][1], 'bf_emma')
        with patch.object(self.speech, 'submit', side_effect=AssertionError('Must not replay preview')):
            self.assertEqual(self.request(dict(action='preview', voice='bf_emma'), 'preview'), result)
        self.assertEqual(self.registry.page()['total'], 1)

    def test_queued_line_uses_live_override_and_mute(self):
        self.registry.encounter('Halver')
        self.speech.submit(Dialogue('', 'blocking'))
        eventually(lambda: bool(self.backend.started))
        self.speech.submit(Dialogue('Halver', 'next'))
        self.registry.edit('halver', 'voice', 'bm_george')
        self.backend.release.set()
        eventually(lambda: len(self.backend.started) == 2)
        self.assertEqual(self.backend.started[1], ('next', 'bm_george'))
        self.registry.edit('halver', 'mute', True)
        self.speech.submit(Dialogue('Halver', 'muted'))
        eventually(lambda: not self.speech.pending and self.speech.state == 'ready')
        self.assertEqual(len(self.backend.started), 2)

    def test_bad_requests_are_errors_not_service_crashes(self):
        for request in [[], {'action':'list', 'page':-1}, {'action':'list', 'search':{}},
                        {'action':'edit', 'key':[]}, {'action':'preview', 'voice':'nope'}]:
            self.assertFalse(self.request(request)['ok'])
        self.assertTrue(self.request({'action':'list'})['ok'])


if __name__ == '__main__':
    unittest.main()
