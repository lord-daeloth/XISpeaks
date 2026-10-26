import json
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'companion'))
from registry import Registry, VOICES, choose_voice, name_key, choose_tuning, choose_blend, validate_voice
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
    def test_elvaan_blends_are_more_frequent_and_keep_primary_dominant(self):
        values=[choose_blend(f'elvaan-{i}','bm_george',VOICES,True) for i in range(10000)]
        self.assertTrue(7300 < sum('*' in v for v in values) < 7700)
        self.assertTrue(any(v.split('*')[-1].startswith('am_') for v in values if '*' in v))
        for value in values:
            validate_voice(value)
            if '*' in value:
                self.assertGreaterEqual(float(value.split('*')[0]),.6)
                self.assertTrue(value.split('*')[-1][1]=='m')

    def test_elvaan_toggle_british_primary_manual_override_and_restore(self):
        self.registry.encounter('Halver')
        self.registry.edit('halver','preference','masculine')
        original=self.registry.voice_for('Halver')
        npc=self.registry.edit('halver','preset',dict(name='elvaan',enabled=True))
        primary=npc['voice'].split('*')[1].split()[0] if '*' in npc['voice'] else npc['voice']
        self.assertTrue(primary.startswith('bm_'))
        self.registry.edit('halver','voice','am_michael')
        self.assertEqual(self.registry.voice_for('Halver'),'am_michael')
        self.registry.edit('halver','reset')
        self.registry.edit('halver','preset',dict(name='elvaan',enabled=False))
        self.assertEqual(self.registry.voice_for('Halver'),original)
        self.registry.edit('halver','preference','feminine')
        npc=self.registry.edit('halver','preset',dict(name='elvaan',enabled=True))
        primary=npc['voice'].split('*')[1].split()[0] if '*' in npc['voice'] else npc['voice']
        self.assertTrue(primary.startswith('bf_'))
        self.registry.close()
        self.registry=Registry(self.path,self.config)
        self.assertEqual(self.registry.voice_for('Halver'),npc['voice'])

    def test_automatic_blend_distribution_and_compatibility(self):
        values=[choose_blend(f'blend-{i}', 'am_michael', VOICES) for i in range(10000)]
        self.assertTrue(2300 < sum('*' in v for v in values) < 2700)
        for voice in values:
            validate_voice(voice)
            if '*' in voice:
                self.assertIn('*am_michael + ',voice)
                self.assertTrue(voice.split('*')[-1].startswith('am_'))
        self.assertEqual(choose_blend('x','af_heart',['af_heart']), 'af_heart')
        self.assertEqual(choose_blend('x','af_heart',VOICES),choose_blend('x','af_heart',list(reversed(VOICES))))

    def test_manual_blend_save_reset_and_restart(self):
        key=next(f'blend-{i}' for i in range(100) if '*' in choose_blend(f'blend-{i}', 'am_michael', VOICES))
        self.registry.encounter(key)
        self.registry.db.execute('UPDATE npcs SET auto_voice=? WHERE key=?',('am_michael',key))
        self.registry.db.commit()
        automatic=self.registry.voice_for(key)
        self.assertIn('*',automatic)
        blend='0.70*af_heart + 0.30*af_bella'
        self.registry.edit(key,'profile',dict(voice=blend,speed=1,pitch=0))
        self.registry.close()
        self.registry=Registry(self.path,self.config)
        self.assertEqual(self.registry.voice_for(key),blend)
        self.registry.edit(key,'voice','am_michael')
        self.assertEqual(self.registry.voice_for(key),'am_michael')
        self.assertEqual(self.registry.edit(key,'reset')['voice'],automatic)
        for bad in ('0.70*af_heart + 0.70*af_bella','0.70*af_heart + 0.30*af_heart', '1*af_heart + nan*af_bella'):
            with self.assertRaises(ValueError): self.registry.edit(key,'voice',bad)

    def test_pitch_engine_migration_preserves_global_settings(self):
        self.registry.set_globals(1.2, 1.8)
        self.registry.db.execute('ALTER TABLE audio_settings DROP COLUMN pitch_engine')
        self.registry.db.commit()
        self.registry.close()
        self.registry = Registry(self.path, self.config)
        self.assertEqual(self.registry.globals(), dict(speed=1.2, volume=1.8, pitch_engine='rubberband'))
        self.assertEqual(self.registry.voice_for('Maat'), 'am_michael')

    def test_pitch_engine_persistence_and_validation(self):
        self.assertEqual(self.registry.globals()['pitch_engine'], 'rubberband')
        self.registry.set_globals(1.2, 1.8, 'librosa')
        self.registry.close()
        self.registry = Registry(self.path, self.config)
        self.assertEqual(self.registry.playback('Maat')['pitch_engine'], 'librosa')
        self.registry.set_globals(1, 1)
        self.assertEqual(self.registry.globals()['pitch_engine'], 'librosa')
        with self.assertRaises(ValueError):
            self.registry.set_globals(1.5, 2, 'invalid')
        self.assertEqual(self.registry.globals(), dict(speed=1, volume=1, pitch_engine='librosa'))

    def test_updated_race_presets_and_tarutaru_voice_pool(self):
        self.registry.encounter('Halver')
        before = self.registry.page(search='halver')['rows'][0]
        npc = self.registry.edit('halver', 'preset', dict(name='tarutaru', enabled=True))
        self.assertEqual(npc['voice'], before['voice'])
        self.assertAlmostEqual(npc['speed'], before['speed'] * 1.1)
        self.assertAlmostEqual(npc['pitch'], before['pitch'] + 1)
        self.registry.edit('maat', 'profile', dict(voice='am_michael', speed=1, pitch=0))
        npc = self.registry.edit('maat', 'preset', dict(name='galka', enabled=True))
        self.assertEqual(npc['speed'], .9)
        self.assertEqual(npc['pitch'], -4)

    def test_presets_stack_restore_and_persist(self):
        self.registry.encounter('Halver')
        original = self.registry.playback('Halver')
        self.registry.edit('halver', 'preset', dict(name='child', enabled=True))
        npc = self.registry.edit('halver', 'preset', dict(name='tarutaru', enabled=True))
        self.assertIn(npc['voice'], ('af_sky', 'af_bella', 'bf_lily', 'am_puck'))
        self.assertAlmostEqual(npc['speed'], npc['base_speed'] * 1.03 * 1.1)
        self.assertAlmostEqual(npc['pitch'], npc['base_pitch'] + 2.0)
        self.registry.close()
        self.registry = Registry(self.path, self.config)
        self.assertTrue(self.registry.page(search='halver')['rows'][0]['presets']['child'])
        for name in ('child', 'tarutaru'):
            self.registry.edit('halver', 'preset', dict(name=name, enabled=False))
        self.assertEqual(self.registry.playback('Halver'), original)

    def test_presets_manual_precedence_and_limits(self):
        self.registry.edit('maat', 'preset', dict(name='mithra', enabled=True))
        self.assertEqual(self.registry.voice_for('Maat'), 'am_michael')
        npc = self.registry.edit('maat', 'reset')
        self.assertEqual(npc['voice'][1], 'f')
        self.registry.edit('maat', 'profile', dict(voice='am_puck', speed=1.2, pitch=1))
        npc = self.registry.edit('maat', 'preset', dict(name='goblin', enabled=True))
        self.assertEqual(npc['voice'], 'am_puck')
        self.assertEqual(npc['pitch'], 4)
        self.assertAlmostEqual(npc['speed'], 1.38)
        npc = self.registry.edit('maat', 'preset', dict(name='galka', enabled=True))
        self.assertEqual(npc['pitch'], .5)
        self.registry.set_globals(2, 2)
        self.assertEqual(self.registry.playback('Maat')['speed'], 2)
        for value in (dict(name='bad', enabled=True), dict(name='child', enabled=1)):
            with self.assertRaises(ValueError):
                self.registry.edit('maat', 'preset', value)
        self.assertFalse(self.registry.page(search='maat')['rows'][0]['presets']['child'])

    def test_v040_migration_preserves_assignments(self):
        self.registry.close()
        import sqlite3
        with sqlite3.connect(self.path) as db:
            for key in ('goblin', 'child', 'galka', 'mithra', 'tarutaru'):
                db.execute('ALTER TABLE npcs DROP COLUMN preset_' + key)
        db.close()
        self.registry = Registry(self.path, self.config)
        self.assertTrue(Path(str(self.path) + '.v040.bak').exists())
        self.assertEqual(self.registry.voice_for('Maat'), 'am_michael')
        self.assertFalse(any(self.registry.page()['rows'][0]['presets'].values()))

    def test_rare_hash_variations_and_determinism(self):
        values = [choose_tuning(f'npc-{i}') for i in range(10000)]
        changed = sum(v != (1,0) for v in values)
        self.assertTrue(650 < changed < 950)
        self.assertTrue(all(.95 <= speed <= 1.05 and abs(pitch) <= 1 for speed,pitch in values))
        self.assertEqual(choose_tuning('halver'),choose_tuning('halver'))

    def test_tuning_global_composition_reset_and_restart(self):
        self.registry.encounter('Halver')
        original = self.registry.page(search='halver')['rows'][0]
        self.registry.edit('halver','profile',dict(voice='am_michael',speed=1.1,pitch=-1.5))
        self.registry.set_globals(1.2,2)
        profile = self.registry.playback('Halver')
        self.assertAlmostEqual(profile['speed'],1.32)
        self.assertEqual(profile['volume'],2)
        self.assertEqual(profile['pitch'],-1.5)
        self.assertEqual(self.registry.playback('')['speed'],1.2)
        self.registry.close()
        self.registry = Registry(self.path,self.config)
        self.assertEqual(self.registry.playback('Halver'),profile)
        reset = self.registry.edit('halver','reset_tuning')
        self.assertEqual(reset['voice'],'am_michael')
        self.assertEqual((reset['speed'],reset['pitch']),(original['auto_speed'],original['auto_pitch']))
        self.registry.edit('halver','reset')
        self.assertEqual(self.registry.voice_for('Halver'),original['auto_voice'])

    def test_invalid_tuning_is_atomic_and_effective_speed_is_clamped(self):
        for speed,volume in [(float('nan'),1),(1,float('inf')),(True,1),(1,4)]:
            with self.assertRaises(ValueError): self.registry.set_globals(speed,volume)
        for pitch in [float('nan'),5,False]:
            with self.assertRaises(ValueError):
                self.registry.edit('maat','profile',dict(voice='af_heart',speed=1,pitch=pitch))
        self.assertEqual(self.registry.voice_for('maat'),'am_michael')
        self.registry.edit('maat','profile',dict(voice='am_michael',speed=1.3,pitch=0))
        self.registry.set_globals(2,1)
        self.assertEqual(self.registry.playback('maat')['speed'],2)

    def test_old_database_migration_keeps_voice_and_mute(self):
        import sqlite3
        path = Path(self.temp.name)/'old.sqlite3'
        with sqlite3.connect(path) as db:
            db.execute('''CREATE TABLE npcs (key TEXT PRIMARY KEY,name TEXT NOT NULL,auto_voice TEXT NOT NULL,
                manual_voice TEXT,preference TEXT NOT NULL DEFAULT 'unknown',muted INTEGER NOT NULL DEFAULT 0,
                last_seen REAL NOT NULL DEFAULT 0,encounters INTEGER NOT NULL DEFAULT 0)''')
            db.execute("INSERT INTO npcs (key,name,auto_voice,manual_voice,muted) VALUES ('halver','Halver','am_adam','bm_george',1)")
        db.close()
        registry = Registry(path,self.config)
        try:
            row = registry.page(search='halver')['rows'][0]
            self.assertEqual(row['voice'],'bm_george')
            self.assertTrue(row['muted'])
            self.assertIsNotNone(row['auto_speed'])
            self.assertTrue(Path(str(path)+'.v030.bak').exists())
        finally:
            registry.close()
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

    def test_blend_preview_reaches_backend(self):
        blend='0.70*am_michael + 0.30*am_fenrir'
        self.assertTrue(self.request(dict(action='preview',voice=blend))['ok'])
        eventually(lambda: bool(self.backend.started))
        self.assertEqual(self.backend.started[0][1],blend)
        self.assertFalse(self.request(dict(action='preview',voice='0.70*bad + 0.30*am_fenrir'))['ok'])

    def test_preset_preview_matches_playback(self):
        parameters = []
        self.backend.configure = lambda **kwargs: parameters.append(kwargs)
        self.registry.edit('maat', 'profile', dict(voice='am_puck', speed=1.1, pitch=.5))
        self.registry.edit('maat', 'preset', dict(name='goblin', enabled=True))
        self.registry.set_globals(1.2, 1.8)
        result = self.request(dict(action='preview', voice='am_puck', speed=1.1, pitch=.5,
                                   presets=dict(goblin=True)))
        self.assertTrue(result['ok'])
        eventually(lambda: bool(self.backend.started))
        expected = self.registry.playback('Maat')
        expected.pop('voice')
        self.assertEqual(parameters[0], expected)
        self.assertFalse(self.request(dict(action='preview', voice='am_puck', presets=dict(child=1)))['ok'])

    def test_preview_uses_global_speed_volume_and_requested_tuning(self):
        parameters = []
        self.backend.configure = lambda **kwargs: parameters.append(kwargs)
        result = self.request(dict(action='globals',speed=1.2,volume=1.8))
        self.assertEqual(result['globals'],dict(speed=1.2,volume=1.8,pitch_engine='rubberband'))
        self.request(dict(action='preview',voice='af_heart',speed=1.05,pitch=-.5))
        eventually(lambda: bool(self.backend.started))
        self.assertAlmostEqual(parameters[0]['speed'],1.26)
        self.assertEqual(parameters[0]['volume'],1.8)
        self.assertEqual(parameters[0]['pitch'],-.5)


if __name__ == '__main__':
    unittest.main()
