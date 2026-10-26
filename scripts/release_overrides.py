"""Export NPC sound corrections without copying player history or global settings."""
from contextlib import closing
import json
import re
from pathlib import Path
import sqlite3

from registry import PRESETS, PREFERENCES, name_key, number, validate_voice

FIELDS = ('preference', 'manual_voice', 'manual_speed', 'manual_pitch', 'approval') + tuple('preset_' + p for p in PRESETS)


def profile(row):
    return {field: row[field] if field in row.keys() else None for field in FIELDS}


def empty_profile():
    return dict(preference='unknown', manual_voice=None, manual_speed=None, manual_pitch=None, approval=None,
                **{'preset_' + p: 0 for p in PRESETS})


def export_overrides(source, baseline):
    records = []
    # Read-only connection also sees committed WAL changes from a running companion.
    with closing(sqlite3.connect(Path(source).resolve().as_uri() + '?mode=ro', uri=True)) as db:
        db.row_factory = sqlite3.Row
        for row in db.execute('SELECT * FROM npcs ORDER BY key'):
            original = baseline.db.execute('SELECT * FROM npcs WHERE key=?', (row['key'],)).fetchone()
            current = profile(row)
            if current != (profile(original) if original else empty_profile()):
                records.append(dict(name=row['name'], **current))
    return dict(schema=1, npcs=records)


def apply_overrides(registry, document):
    if document.get('schema') != 1 or not isinstance(document.get('npcs'), list):
        raise ValueError('Invalid release NPC overrides')
    seen = set()
    document = dict(document, npcs=[dict(item, approval=item.get('approval')) for item in document['npcs']])
    for item in document['npcs']:
        if set(item) != {'name', *FIELDS} or not isinstance(item['name'], str) or not item['name'].strip():
            raise ValueError('Invalid release NPC profile')
        key = name_key(item['name'])
        if key in seen or item['preference'] not in PREFERENCES:
            raise ValueError('Duplicate NPC or invalid preference')
        seen.add(key)
        if item['approval'] is not None and (not isinstance(item['approval'], str) or not re.fullmatch('[0-9a-f]{32}', item['approval'])):
            raise ValueError('Invalid approval fingerprint')
        if item['manual_voice'] is not None:
            validate_voice(item['manual_voice'])
        for field, low, high in [('manual_speed', 0.7, 1.3), ('manual_pitch', -4, 4)]:
            if item[field] is not None:
                number(item[field], low, high, field)
        for preset in PRESETS:
            if type(item['preset_' + preset]) is not int or item['preset_' + preset] not in (0, 1):
                raise ValueError('Invalid preset')
    for item in document['npcs']:
        key = name_key(item['name'])
        registry.encounter(item['name'])
        registry.edit(key, 'preference', item['preference'])
        with registry.db:
            registry.db.execute('UPDATE npcs SET ' + ','.join(f'{field}=?' for field in FIELDS) +
                                ',last_seen=0,encounters=0 WHERE key=?', (*[item[f] for f in FIELDS], key))
    return len(document['npcs'])
