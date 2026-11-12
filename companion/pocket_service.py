"""Isolated XISpeaks Pocket 18M companion, localhost UDP 49152."""
import argparse
import hashlib
import json
import logging
from pathlib import Path
import sys
import threading
import time
from pocket_paths import ROOT, VOICES
import pocket_catalog
import registry

sys.path.insert(0,str(ROOT/'scripts'))


def create_registry(config,path):
    from import_npc_catalog import import_catalog
    from release_overrides import apply_overrides
    db=registry.Registry(path,config)
    db.contributions_enabled=False
    if not db.db.execute("SELECT 1 FROM metadata WHERE key='pocket_seed_v1'").fetchone():
        import_catalog(db,json.loads((ROOT/'data/npc_associations.json').read_text()))
        corrections=json.loads((ROOT/'data/release_npc_overrides.json').read_text())
        apply_overrides(db,corrections)
        from piper_service import migrate_pacing_and_moogles
        migrate_pacing_and_moogles(db,path)
        with db.db:
            db.db.execute("INSERT INTO metadata VALUES ('pocket_seed_v1','1')")
        db.set_globals(1,1,'rubberband')
    with db.db:
        db.db.execute("UPDATE npcs SET manual_voice=NULL,approval=NULL WHERE manual_voice IN ('am_halver_long','am_halver_short')")
    return db


class CatalogReload:
    def __init__(self,path,config,db):
        self.path=path
        self.config=config
        self.db=db
        self.stamp=path.stat().st_mtime_ns
        self.next_check=0
        self.db.catalog_revision=str(self.stamp)

    def __call__(self):
        if time.monotonic()<self.next_check:return
        self.next_check=time.monotonic()+1
        try:
            stamp=self.path.stat().st_mtime_ns
            if stamp==self.stamp:return
            catalog=pocket_catalog.load(self.path)
            from voice_catalog import Policy
            with self.db.lock,self.db.db:
                for key in set(self.db.voice_catalog)-set(catalog):
                    self.db.db.execute('UPDATE npcs SET manual_voice=NULL,approval=NULL WHERE manual_voice=?',(key,))
                self.config['voice_catalog']=catalog
                registry.VOICES[:]=sorted(catalog)
                self.db.voice_catalog=catalog
                self.db.voice_policy=Policy(catalog)
                self.db.pool=list(catalog)
                self.db.default=self.db.voice_policy.choose('__narrator__','unknown',{})
                self.db.review_queue.clear();self.db.review_heard.clear();self.db.review_deferred.clear()
                self.db.catalog_revision=str(stamp)
            self.stamp=stamp
        except Exception:
            logging.exception('Could not reload Pocket catalog')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=49152)
    parser.add_argument('--dry-run',action='store_true')
    args=parser.parse_args()
    if not 1024<=args.port<=65535:parser.error('Invalid port')
    path=VOICES/'catalog.json'
    catalog=pocket_catalog.load(path)
    registry.VOICES[:]=sorted(catalog)
    registry.BLENDING_ENABLED=False
    registry.YOUNG_VOICES=()
    import service
    from pocket_backend import PocketBackend
    config=dict(service.DEFAULTS,voice='bf_alba',voice_pool=list(catalog),voice_catalog=catalog)
    runtime=ROOT/'pocket-runtime';runtime.mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    db=create_registry(config,runtime/'npcs.sqlite3')
    speech=service.SpeechQueue(config,service.DryBackend if args.dry_run else PocketBackend,db)
    server=None
    try:
        server=service.Server(speech,args.port,db)
        server.catalog_reload=CatalogReload(path,config,db)
        server.run(threading.Event())
    except KeyboardInterrupt:pass
    finally:
        if server:server.close()
        speech.close()
        if not speech.worker.is_alive():db.close()

if __name__=='__main__':main()
