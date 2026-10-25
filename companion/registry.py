"""Persistent NPC voice assignments. SQLite transactions make UI edits atomic."""
import hashlib
import sqlite3
import threading
import time
import unicodedata

# English voices supported by the pinned RealtimeTTS KokoroEngine.get_voices().
VOICES = sorted('''af_heart af_alloy af_aoede af_bella af_jessica af_kore af_nicole
af_nova af_river af_sarah af_sky am_adam am_echo am_eric am_fenrir am_liam
am_michael am_onyx am_puck am_santa bf_alice bf_emma bf_isabella bf_lily
bm_daniel bm_fable bm_george bm_lewis'''.split())
PREFERENCES = ('unknown', 'masculine', 'feminine')


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
        with self.db:
            self.db.execute('''CREATE TABLE IF NOT EXISTS npcs (
                key TEXT PRIMARY KEY, name TEXT NOT NULL, auto_voice TEXT NOT NULL,
                manual_voice TEXT, preference TEXT NOT NULL DEFAULT 'unknown',
                muted INTEGER NOT NULL DEFAULT 0, last_seen REAL NOT NULL DEFAULT 0,
                encounters INTEGER NOT NULL DEFAULT 0)''')
            self.db.execute('CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT)')
            if not self.db.execute("SELECT 1 FROM metadata WHERE key='legacy_imported'").fetchone():
                for name, voice in config['voices'].items():
                    # Preserve legacy choices, including user-supplied blended voices.
                    key = name_key(name)
                    self.db.execute('INSERT OR IGNORE INTO npcs (key,name,auto_voice,manual_voice) VALUES (?,?,?,?)',
                                    (key, name.strip(), choose_voice(key, 'unknown', self.pool), voice))
                self.db.execute("INSERT INTO metadata VALUES ('legacy_imported','1')")

    def encounter(self, name):
        key = name_key(name)
        with self.lock, self.db:
            self.db.execute('''INSERT INTO npcs (key,name,auto_voice,last_seen,encounters)
                VALUES (?,?,?,?,1) ON CONFLICT(key) DO UPDATE SET
                last_seen=excluded.last_seen, encounters=npcs.encounters+1''',
                (key, name.strip(), choose_voice(key, 'unknown', self.pool), time.time()))

    def voice_for(self, name):
        if not name:
            return self.default
        with self.lock:
            row = self.db.execute('SELECT * FROM npcs WHERE key=?', (name_key(name),)).fetchone()
            if not row:
                return self.default
            return None if row['muted'] else (row['manual_voice'] or row['auto_voice'])

    @staticmethod
    def public(row):
        result = dict(row)
        result['muted'] = bool(result['muted'])
        result['voice'] = result['manual_voice'] or result['auto_voice']
        result['source'] = 'manual' if result['manual_voice'] else 'automatic'
        return result

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
            elif action == 'reset':
                self.db.execute('UPDATE npcs SET manual_voice=NULL WHERE key=?', (key,))
            elif action == 'preference':
                if value not in PREFERENCES:
                    raise ValueError('Invalid voice preference')
                if value != row['preference']:
                    auto = choose_voice(key, value, self.pool)
                    self.db.execute('UPDATE npcs SET preference=?,auto_voice=? WHERE key=?', (value, auto, key))
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
            conditions.append('manual_voice IS NOT NULL')
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
