"""Launch the isolated Piper companion. No Kokoro synthesis or stable database access."""
import json
import hashlib
import sqlite3
from contextlib import closing
import logging
from pathlib import Path
import re
import sys
import threading
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'piper_trainer'))
from paths import ROOT,ASSETS,VOICES
sys.path.insert(0,str(ROOT/'build/playback-deps'))
import registry


def configure_catalog(path=VOICES/'catalog.json'):
    catalog=json.loads(path.read_text(encoding='utf-8-sig'))
    if not catalog:raise ValueError('Empty Piper catalog; run setup_voices.py')
    configs={}
    for key,item in catalog.items():
        if not re.fullmatch('[abx][fmu]_[a-z0-9_]+',key):raise ValueError('Invalid voice ID: '+key)
        model=(path.parent/item['model']).resolve()
        if not model.is_relative_to(path.parent.resolve()) or not model.is_file() or not Path(str(model)+'.json').is_file():
            raise ValueError('Missing/invalid model: '+str(model))
        if model not in configs:configs[model]=json.loads(Path(str(model)+'.json').read_text(encoding='utf-8'))
        config=configs[model]
        speaker=item.get('speaker_id')
        count=config.get('num_speakers',1)
        if (count>1 and speaker is None) or (speaker is not None and (type(speaker) is not int or not 0<=speaker<count)):
            raise ValueError('Invalid speaker ID: '+key)
    registry.VOICES[:]=sorted(catalog)
    registry.YOUNG_VOICES=()
    registry.BLENDING_ENABLED=False
    return catalog


def create_registry(config,path):
    from import_npc_catalog import import_catalog
    from release_overrides import apply_overrides
    db=registry.Registry(path,config)
    db.contributions_enabled=False
    if not db.db.execute("SELECT 1 FROM metadata WHERE key='piper_seed_v1'").fetchone():
        import_catalog(db,json.loads((ROOT/'data/npc_associations.json').read_text(encoding='utf-8')))
        corrections=json.loads((ROOT/'data/release_npc_overrides.json').read_text(encoding='utf-8'))
        for item in corrections['npcs']:
            item['manual_voice']=None
            item['approval']=None
        apply_overrides(db,corrections)
        with db.db:db.db.execute("INSERT INTO metadata VALUES ('piper_seed_v1','1')")
    signature=hashlib.sha256(json.dumps(config['voice_pool'],sort_keys=True).encode()).hexdigest()
    previous=db.db.execute("SELECT value FROM metadata WHERE key='piper_pool_signature'").fetchone()
    if previous and previous[0]==signature:return db
    if str(path)!=':memory:':
        backup=Path(str(path)+'.catalog-'+signature[:12]+'.bak')
        if not backup.exists():
            with closing(sqlite3.connect(str(backup))) as target:db.db.backup(target)
    if not previous:
        with db.db:db.db.execute("UPDATE npcs SET approval=NULL WHERE auto_voice='bf_cori'")
    # Expand unapproved automatic choices; preserve explicit choices and valid approvals.
    with db.lock,db.db:
        for row in db.db.execute('SELECT * FROM npcs').fetchall():
            old=dict(row)
            if old['manual_voice'] and old['manual_voice'] not in registry.VOICES:
                db.db.execute('UPDATE npcs SET manual_voice=NULL,approval=NULL WHERE key=?',(old['key'],))
                old['manual_voice']=None;old['approval']=None
            if old['approval'] and db.public(old)['fingerprint']!=old['approval']:
                old['approval']=None
                db.db.execute('UPDATE npcs SET approval=NULL WHERE key=?',(old['key'],))
            if old['auto_voice'] not in config['voice_pool'] or (not old['manual_voice'] and not old['approval']):
                voice=registry.choose_voice(old['key'],old['preference'],config['voice_pool'])
                db.db.execute('UPDATE npcs SET auto_voice=?,approval=NULL WHERE key=?',(voice,old['key']))
    with db.db:db.db.execute("INSERT OR REPLACE INTO metadata VALUES ('piper_pool_signature',?)",(signature,))
    return db


def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--dry-run',action='store_true')
    args=parser.parse_args()
    catalog=configure_catalog()
    import service
    from piper_backend import PiperBackend
    import audio_effects
    audio_effects.RUBBERBAND=ASSETS/'tools/rubberband-4.0.0-gpl-executable-windows/rubberband.exe'
    sys.path.insert(0,str(ROOT/'scripts'))
    runtime=ROOT/'piper-runtime';runtime.mkdir(exist_ok=True)
    pool=[key for key,item in catalog.items() if item.get('automatic',True)]
    config=dict(service.DEFAULTS,voice='am_ryan',voice_pool=pool,piper_models={key:dict(path=VOICES/item['model'],speaker_id=item.get('speaker_id')) for key,item in catalog.items()})
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    db=create_registry(config,runtime/'npcs.sqlite3')
    speech=service.SpeechQueue(config,service.DryBackend if args.dry_run else PiperBackend,db)
    server=None
    try:
        server=service.Server(speech,49153,db)
        server.run(threading.Event())
    except KeyboardInterrupt:pass
    finally:
        if server:server.close()
        speech.close()
        if not speech.worker.is_alive():db.close()

if __name__=='__main__':main()
