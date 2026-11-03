"""Import confirmed catalog defaults once, backing up the registry before changes."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'companion'))
from registry import Registry, PRESETS, PREFERENCES, choose_voice, choose_tuning, name_key
from service import load_config


def import_catalog(registry, catalog, overwrite=False, race_only=False, correct_preferences=False):
    if catalog.get('schema') != 1 or not isinstance(catalog.get('associations'), dict):
        raise ValueError('Unsupported NPC catalog')
    rows = []
    for key, item in catalog['associations'].items():
        if item['status'] != 'confirmed':
            continue
        profile = item['profile']
        if key != name_key(item['name']) or profile['preference'] not in PREFERENCES:
            raise ValueError('Invalid catalog name/preference')
        if not isinstance(profile['presets'], list) or any(p not in PRESETS for p in profile['presets']):
            raise ValueError('Invalid catalog preset')
        # Respect the user's enabled voice pool; fail atomically if it cannot satisfy a preference.
        voice = registry.initial_voice(key, profile['preference'])
        speed, pitch = choose_tuning(key)
        rows.append((key,item['name'],profile,voice,speed,pitch))
    counts = dict(inserted=0, updated=0, preserved=0)
    with registry.lock, registry.db:
        for key,name,profile,voice,speed,pitch in rows:
            exists = registry.db.execute('SELECT 1 FROM npcs WHERE key=?',(key,)).fetchone()
            if exists and not overwrite and not race_only:
                counts['preserved'] += 1
                continue
            registry.db.execute('''INSERT INTO npcs (key,name,auto_voice,auto_speed,auto_pitch)
                VALUES (?,?,?,?,?) ON CONFLICT(key) DO NOTHING''', (key,name,voice,speed,pitch))
            if race_only:
                current = registry.db.execute('SELECT preference FROM npcs WHERE key=?', (key,)).fetchone()
                preference = current['preference'] if current['preference'] != 'unknown' and not correct_preferences else profile['preference']
                primary = registry.initial_voice(key, preference)
                registry.db.execute('''UPDATE npcs SET preference=?,auto_voice=?,
                    preset_goblin=?,preset_galka=?,preset_mithra=?,preset_tarutaru=?,preset_elvaan=? WHERE key=?''',
                    (preference,primary,*[int(p in profile['presets']) for p in ('goblin','galka','mithra','tarutaru','elvaan')],key))
                counts['updated' if exists else 'inserted'] += 1
                continue
            registry.db.execute('''UPDATE npcs SET preference=?,auto_voice=?,auto_speed=?,auto_pitch=?,
                manual_voice=NULL,manual_speed=NULL,manual_pitch=NULL,
                preset_goblin=?,preset_galka=?,preset_mithra=?,preset_tarutaru=?,preset_elvaan=? WHERE key=?''',
                (profile['preference'],voice,speed,pitch,
                 *[int(p in profile['presets']) for p in ('goblin','galka','mithra','tarutaru','elvaan')],key))
            # Child cannot be inferred from ordinary race codes. Preserve explicit Child/mute/history.
            counts['updated' if exists else 'inserted'] += 1
    return counts


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog',type=Path,default=ROOT/'data/npc_associations.json')
    parser.add_argument('--registry',type=Path,default=ROOT/'npcs.sqlite3')
    parser.add_argument('--config',type=Path,default=ROOT/'config.json')
    parser.add_argument('--overwrite',action='store_true',help='Replace existing confirmed voices/tuning/race flags; retain Child, mute, and history')
    parser.add_argument('--race-only',action='store_true',help='Update race flags and automatic selection; preserve manual voices, tuning, Child, and known preferences')
    parser.add_argument('--correct-preferences',action='store_true',help='With --race-only, apply reviewed gender corrections even when an old preference exists')
    args=parser.parse_args()
    if args.correct_preferences and not args.race_only:
        parser.error('--correct-preferences requires --race-only')
    raw=args.catalog.read_bytes()
    catalog=json.loads(raw)
    registry=Registry(args.registry,load_config(args.config))
    try:
        backup=Path(str(args.registry)+'.before-catalog-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.bak')
        with closing(sqlite3.connect(backup)) as target:
            registry.db.backup(target)
        result=import_catalog(registry,catalog,args.overwrite,args.race_only,args.correct_preferences)
        result.update(backup=str(backup),revision=catalog['revision'],catalog_sha256=hashlib.sha256(raw).hexdigest())
        print(json.dumps(result,indent=2))
    finally:
        registry.close()


if __name__ == '__main__':
    main()
