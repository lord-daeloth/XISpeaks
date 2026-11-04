"""Run the XISpeaks Piper companion."""
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
    from voice_catalog import load
    catalog=load(path)
    registry.VOICES[:]=sorted(catalog)
    registry.YOUNG_VOICES=()
    registry.BLENDING_ENABLED=False
    return catalog

class CatalogRuntime:
    def __init__(self,db,config,path=VOICES/'catalog.json'):
        self.db,self.config,self.path=db,config,Path(path)
        self.stamp=self.path.stat().st_mtime_ns;self.next_check=0;self.db.catalog_revision=str(self.stamp)
    def reload(self):
        import time
        if time.monotonic()<self.next_check:return
        self.next_check=time.monotonic()+.5
        try:
            stamp=self.path.stat().st_mtime_ns
            if stamp==self.stamp:return
            from voice_catalog import load,Policy,playback_models
            catalog=load(self.path)
            with self.db.lock,self.db.db:
                removed=set(self.db.voice_catalog or {})-set(catalog)
                for key in removed:
                    self.db.db.execute('UPDATE npcs SET manual_voice=NULL,approval=NULL WHERE manual_voice=?',(key,))
                registry.VOICES[:]=sorted(catalog)
                self.db.voice_catalog=catalog;self.db.voice_policy=Policy(catalog);self.db.pool=list(catalog)
                self.db.default=self.db.voice_policy.choose('__narrator__','unknown',{})
                self.config['voice_catalog']=catalog;self.config['voice_pool']=list(catalog)
                self.config['piper_models']=playback_models(catalog,self.path.parent)
                self.db.review_queue.clear();self.db.review_heard.clear();self.db.review_deferred.clear()
                self.db.catalog_revision=str(stamp)
            self.stamp=stamp
            logging.info('Reloaded voice catalog: %d voices',len(catalog))
        except (OSError,ValueError,TypeError,KeyError):
            logging.exception('Unable to reload voice catalog; retaining last valid catalog')


def migrate_pacing_and_moogles(db,path):
    marker='piper_pacing_moogles_v1'
    if db.db.execute('SELECT 1 FROM metadata WHERE key=?',(marker,)).fetchone():return
    if str(path)!=':memory:':
        backup=Path(str(path)+'.before-moogles.bak')
        if not backup.exists():
            with closing(sqlite3.connect(str(backup))) as target:db.db.backup(target)
    catalog=json.loads((ROOT/'data/moogle_associations.json').read_text(encoding='utf-8'))
    with db.lock,db.db:
        for item in catalog['npcs']:
            key=registry.name_key(item['name']);speed,pitch=registry.choose_tuning(key)
            voice=db.initial_voice(key,'unknown')
            db.db.execute('INSERT OR IGNORE INTO npcs (key,name,auto_voice,auto_speed,auto_pitch) VALUES (?,?,?,?,?)',
                (key,item['name'],voice,speed,pitch))
            db.db.execute('UPDATE npcs SET preset_moogle=1,approval=NULL WHERE key=?',(key,))
        db.db.execute('INSERT INTO metadata VALUES (?,?)',(marker,'1'))


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
            item['manual_speed']=None;item['manual_pitch']=None
            item['approval']=None
        apply_overrides(db,corrections)
        with db.db:db.db.execute("INSERT INTO metadata VALUES ('piper_seed_v1','1')")
    migrate_pacing_and_moogles(db,path)
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
                voice=db.initial_voice(old['key'],old['preference'])
                db.db.execute('UPDATE npcs SET auto_voice=?,approval=NULL WHERE key=?',(voice,old['key']))
    with db.db:db.db.execute("INSERT OR REPLACE INTO metadata VALUES ('piper_pool_signature',?)",(signature,))
    return db


def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--dry-run',action='store_true')
    parser.add_argument('--port',type=int,default=49152)
    args=parser.parse_args()
    catalog=configure_catalog()
    import service
    from piper_backend import PiperBackend
    import audio_effects
    from portable import resource_root
    effects_root = resource_root() if getattr(sys,'frozen',False) else ASSETS
    audio_effects.RUBBERBAND=effects_root/'tools/rubberband-4.0.0-gpl-executable-windows/rubberband.exe'
    sys.path.insert(0,str(ROOT/'scripts'))
    runtime=ROOT/'piper-runtime';runtime.mkdir(exist_ok=True)
    from voice_catalog import playback_models
    pool=list(catalog)
    config=dict(service.DEFAULTS,voice='am_ryan' if 'am_ryan' in catalog else pool[0],voice_pool=pool,voice_catalog=catalog,piper_models=playback_models(catalog,VOICES))
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    db=create_registry(config,runtime/'npcs.sqlite3')
    speech=service.SpeechQueue(config,service.DryBackend if args.dry_run else PiperBackend,db)
    server=None
    try:
        server=service.Server(speech,args.port,db)
        server.catalog_reload=CatalogRuntime(db,config).reload
        server.run(threading.Event())
    except KeyboardInterrupt:pass
    finally:
        if server:server.close()
        speech.close()
        if not speech.worker.is_alive():db.close()

if __name__=='__main__':main()
