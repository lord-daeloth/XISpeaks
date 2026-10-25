"""Persistent NPC voice assignments. SQLite transactions make UI edits atomic."""
import hashlib
from contextlib import closing
import math
from pathlib import Path
import sqlite3
import threading
import time
import unicodedata

# English voices supported by the pinned RealtimeTTS KokoroEngine.get_voices().
VOICES = sorted('''af_heart af_alloy af_aoede af_bella af_jessica af_kore af_nicole
af_nova af_river af_sarah af_sky am_adam am_echo am_eric am_fenrir am_liam
am_michael am_onyx am_puck am_santa bf_alice bf_emma bf_isabella bf_lily
bm_daniel bm_fable bm_george bm_lewis'''.split())
PRESETS = {'goblin': (1.15, 3.5), 'child': (1.03, 0.2), 'galka': (1.0, -1.0),
           'mithra': (1.0, 0.0), 'tarutaru': (1.03, 0.2)}
YOUNG_VOICES = ('af_sky', 'af_bella', 'bf_lily', 'am_puck')


def preset_effects(presets):
    if not isinstance(presets, dict) or any(k not in PRESETS or type(v) is not bool for k, v in presets.items()):
        raise ValueError('Invalid NPC presets')
    speed, pitch = 1.0, 0.0
    for key, enabled in presets.items():
        if enabled:
            speed *= PRESETS[key][0]
            pitch += PRESETS[key][1]
    return speed, pitch


def apply_presets(profile, presets):
    speed, pitch = preset_effects(presets)
    return dict(profile, speed=profile['speed'] * speed,
                pitch=max(-4.0, min(4.0, profile['pitch'] + pitch)))


PREFERENCES = ('unknown', 'masculine', 'feminine')


def number(value, low, high, label):
    if type(value) not in (float, int) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{label} must be between {low} and {high}')
    return float(value)


def choose_tuning(key):
    digest = hashlib.sha256(('XISpeaks-tuning-v1:' + key).encode('utf-8')).digest()
    bucket = int.from_bytes(digest[:2], 'big') % 100
    # 92% neutral; 3% pitch only, 3% speed only, 2% both. Stable per NPC.
    pitch = (-1.0, -0.5, 0.5, 1.0)[digest[2] % 4] if bucket < 3 or 6 <= bucket < 8 else 0.0
    speed = (0.95, 0.97, 1.03, 1.05)[digest[3] % 4] if 3 <= bucket < 8 else 1.0
    return speed, pitch


def name_key(name):
    if not isinstance(name, str) or not name.strip() or len(name) > 128:
        raise ValueError('NPC name must contain 1-128 characters')
    key = ' '.join(unicodedata.normalize('NFKC', name).split()).casefold()
    if len(key) > 128:
        raise ValueError('Normalized NPC name is too long')
    return key


def choose_voice(key, preference, pool):
    choices = sorted(v for v in pool if preference == 'unknown' or
                     v[1] == ('m' if preference == 'masculine' else 'f'))
    if not choices:
        raise ValueError('The enabled voice pool has no voices for that preference')
    digest = hashlib.sha256(('XISpeaks-v1:' + key).encode('utf-8')).digest()
    return choices[int.from_bytes(digest[:8], 'big') % len(choices)]


class Registry:
    def __init__(self, path, config):
        self.pool = config.get('voice_pool', VOICES)
        if not isinstance(self.pool, list) or not self.pool or any(v not in VOICES for v in self.pool):
            raise ValueError('voice_pool must be a nonempty list of supported English voice IDs')
        self.default = config['voice']
        self.lock = threading.RLock()
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        old_columns = {row[1] for row in self.db.execute('PRAGMA table_info(npcs)')}
        if old_columns and 'auto_speed' not in old_columns and str(path) != ':memory:':
            backup = Path(str(path) + '.v030.bak')
            if not backup.exists():
                with closing(sqlite3.connect(str(backup))) as target:
                    self.db.backup(target)
        if old_columns and 'preset_goblin' not in old_columns and str(path) != ':memory:':
            backup = Path(str(path) + '.v040.bak')
            if not backup.exists():
                with closing(sqlite3.connect(str(backup))) as target:
                    self.db.backup(target)
        with self.db:
            self.db.execute('''CREATE TABLE IF NOT EXISTS npcs (
                key TEXT PRIMARY KEY, name TEXT NOT NULL, auto_voice TEXT NOT NULL,
                manual_voice TEXT, preference TEXT NOT NULL DEFAULT 'unknown',
                muted INTEGER NOT NULL DEFAULT 0, last_seen REAL NOT NULL DEFAULT 0,
                encounters INTEGER NOT NULL DEFAULT 0)''')
            self.db.execute('CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT)')
            columns = {row[1] for row in self.db.execute('PRAGMA table_info(npcs)')}
            for column in ('auto_speed', 'auto_pitch', 'manual_speed', 'manual_pitch'):
                if column not in columns:
                    self.db.execute(f'ALTER TABLE npcs ADD COLUMN {column} REAL')
            for preset in PRESETS:
                if 'preset_' + preset not in columns:
                    self.db.execute(f'ALTER TABLE npcs ADD COLUMN preset_{preset} INTEGER NOT NULL DEFAULT 0')
            self.db.execute('CREATE TABLE IF NOT EXISTS audio_settings (id INTEGER PRIMARY KEY CHECK(id=1), speed REAL, volume REAL)')
            self.db.execute('INSERT OR IGNORE INTO audio_settings VALUES (1,?,?)', (config['speed'], config.get('volume', 1.0)))
            if not self.db.execute("SELECT 1 FROM metadata WHERE key='legacy_imported'").fetchone():
                for name, voice in config['voices'].items():
                    # Preserve legacy choices, including user-supplied blended voices.
                    key = name_key(name)
                    self.db.execute('INSERT OR IGNORE INTO npcs (key,name,auto_voice,manual_voice) VALUES (?,?,?,?)',
                                    (key, name.strip(), choose_voice(key, 'unknown', self.pool), voice))
                self.db.execute("INSERT INTO metadata VALUES ('legacy_imported','1')")
            for row in self.db.execute('SELECT key FROM npcs WHERE auto_speed IS NULL OR auto_pitch IS NULL').fetchall():
                speed, pitch = choose_tuning(row['key'])
                self.db.execute('UPDATE npcs SET auto_speed=?,auto_pitch=? WHERE key=?', (speed, pitch, row['key']))

    def encounter(self, name):
        key = name_key(name)
        with self.lock, self.db:
            speed, pitch = choose_tuning(key)
            self.db.execute('''INSERT INTO npcs (key,name,auto_voice,last_seen,encounters,auto_speed,auto_pitch)
                VALUES (?,?,?,?,1,?,?) ON CONFLICT(key) DO UPDATE SET
                last_seen=excluded.last_seen, encounters=npcs.encounters+1''',
                (key, name.strip(), choose_voice(key, 'unknown', self.pool), time.time(), speed, pitch))

    def globals(self):
        with self.lock:
            row = self.db.execute('SELECT speed,volume FROM audio_settings WHERE id=1').fetchone()
            return dict(row)

    def set_globals(self, speed, volume):
        speed = number(speed, 0.5, 2, 'Global speed')
        volume = number(volume, 0, 3, 'Volume')
        with self.lock, self.db:
            self.db.execute('UPDATE audio_settings SET speed=?,volume=? WHERE id=1', (speed, volume))
            return self.globals()

    def playback(self, name, override=None):
        with self.lock:
            settings = self.globals()
            voice, speed, pitch = self.default, 1.0, 0.0
            if override is not None:
                if isinstance(override, str):
                    voice = override
                else:
                    voice, speed, pitch = override['voice'], override['speed'], override['pitch']
            elif name:
                row = self.db.execute('SELECT * FROM npcs WHERE key=?', (name_key(name),)).fetchone()
                if row:
                    npc = self.public(row)
                    voice, speed, pitch = npc['voice'], npc['speed'], npc['pitch']
                    if npc['muted']:
                        voice = None
            return dict(voice=voice, speed=max(0.5, min(2.0, settings['speed'] * speed)),
                        pitch=pitch, volume=settings['volume'])

    def voice_for(self, name):
        if not name:
            return self.default
        with self.lock:
            row = self.db.execute('SELECT * FROM npcs WHERE key=?', (name_key(name),)).fetchone()
            if not row:
                return self.default
            return None if row['muted'] else self.public(row)['voice']

    def public(self, row):
        result = dict(row)
        result['muted'] = bool(result['muted'])
        result['voice'] = result['manual_voice'] or result['auto_voice']
        result['source'] = 'manual' if result['manual_voice'] else 'automatic'
        result['speed'] = result['manual_speed'] if result['manual_speed'] is not None else result['auto_speed']
        result['pitch'] = result['manual_pitch'] if result['manual_pitch'] is not None else result['auto_pitch']
        result['tuning_source'] = 'manual' if result['manual_speed'] is not None or result['manual_pitch'] is not None else 'automatic'
        result['base_speed'], result['base_pitch'] = result['speed'], result['pitch']
        presets = {key: bool(result.pop('preset_' + key)) for key in PRESETS}
        result['presets'] = presets
        result['preset_speed'], result['preset_pitch'] = preset_effects(presets)
        if not result['manual_voice'] and any(presets.values()):
            preference = 'feminine' if presets['mithra'] else result['preference']
            pool = self.pool
            if presets['child'] or presets['tarutaru']:
                young = [v for v in pool if v in YOUNG_VOICES and
                         (preference == 'unknown' or v[1] == ('f' if preference == 'feminine' else 'm'))]
                if young:
                    pool = young
            if presets['mithra'] or presets['child'] or presets['tarutaru']:
                result['voice'] = choose_voice(result['key'], preference, pool)
        return apply_presets(result, presets)

    def edit(self, key, action, value=None):
        if not isinstance(key, str) or len(key) > 128:
            raise ValueError('Invalid NPC key')
        with self.lock, self.db:
            row = self.db.execute('SELECT * FROM npcs WHERE key=?', (key,)).fetchone()
            if row is None:
                raise ValueError('NPC no longer exists; refresh the list')
            if action == 'voice':
                if value not in VOICES:
                    raise ValueError('Choose a supported English voice')
                self.db.execute('UPDATE npcs SET manual_voice=? WHERE key=?', (value, key))
            elif action == 'profile':
                if not isinstance(value, dict) or value.get('voice') not in VOICES:
                    raise ValueError('Choose a supported English voice')
                speed = number(value.get('speed'), 0.7, 1.3, 'NPC speed')
                pitch = number(value.get('pitch'), -4, 4, 'Pitch')
                self.db.execute('UPDATE npcs SET manual_voice=?,manual_speed=?,manual_pitch=? WHERE key=?',
                                (value['voice'], speed, pitch, key))
            elif action == 'reset':
                self.db.execute('UPDATE npcs SET manual_voice=NULL,manual_speed=NULL,manual_pitch=NULL WHERE key=?', (key,))
            elif action == 'reset_tuning':
                self.db.execute('UPDATE npcs SET manual_speed=NULL,manual_pitch=NULL WHERE key=?', (key,))
            elif action == 'preference':
                if value not in PREFERENCES:
                    raise ValueError('Invalid voice preference')
                if value != row['preference']:
                    auto = choose_voice(key, value, self.pool)
                    self.db.execute('UPDATE npcs SET preference=?,auto_voice=? WHERE key=?', (value, auto, key))
            elif action == 'preset':
                if not isinstance(value, dict) or value.get('name') not in PRESETS or type(value.get('enabled')) is not bool:
                    raise ValueError('Invalid NPC preset')
                # Validate the resulting pool before committing the toggle.
                candidate = dict(row)
                candidate['preset_' + value['name']] = int(value['enabled'])
                self.public(candidate)
                self.db.execute(f"UPDATE npcs SET preset_{value['name']}=? WHERE key=?", (int(value['enabled']), key))
            elif action == 'mute':
                if type(value) is not bool:
                    raise ValueError('Mute must be true or false')
                self.db.execute('UPDATE npcs SET muted=? WHERE key=?', (int(value), key))
            else:
                raise ValueError('Unknown edit')
            return self.public(self.db.execute('SELECT * FROM npcs WHERE key=?', (key,)).fetchone())

    def page(self, search='', filter_name='all', page=0):
        if not isinstance(search, str) or len(search) > 128 or filter_name not in ('all', 'recent', 'manual'):
            raise ValueError('Invalid list filter')
        if type(page) is not int or not 0 <= page <= 100000:
            raise ValueError('Invalid page')
        # instr is a literal substring match: player-supplied %/_ are not wildcards.
        conditions, args = ['instr(key,?) > 0'], [unicodedata.normalize('NFKC', search).casefold()]
        if filter_name == 'manual':
            conditions.append('(manual_voice IS NOT NULL OR manual_speed IS NOT NULL OR manual_pitch IS NOT NULL OR ' +
                              ' OR '.join('preset_' + key + '=1' for key in PRESETS) + ')')
        if filter_name == 'recent':
            conditions.append('last_seen >= ?')
            args.append(time.time() - 86400)
        where = ' AND '.join(conditions)
        with self.lock:
            total = self.db.execute('SELECT count(*) FROM npcs WHERE ' + where, args).fetchone()[0]
            page = min(page, max(0, (total - 1) // 12))
            rows = self.db.execute('SELECT * FROM npcs WHERE ' + where +
                                   ' ORDER BY last_seen DESC,key LIMIT 12 OFFSET ?', args + [page * 12]).fetchall()
            return dict(rows=[self.public(row) for row in rows], total=total, page=page)

    def close(self):
        with self.lock:
            self.db.close()
