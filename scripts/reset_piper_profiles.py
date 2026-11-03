"""Explicitly reset Piper NPC voice/tuning overrides and approvals, with a SQLite backup."""
import argparse
from contextlib import closing
from pathlib import Path
import sqlite3
import time
ROOT=Path(__file__).resolve().parents[1]

def reset(path):
    path=Path(path).resolve()
    if not path.is_file():raise ValueError('NPC database does not exist')
    backup=Path(str(path)+f'.before-clean-slate-{time.time_ns()}.bak')
    with closing(sqlite3.connect(str(path),timeout=10)) as db:
        with closing(sqlite3.connect(str(backup))) as target:db.backup(target)
        overrides=db.execute('SELECT COUNT(*) FROM npcs WHERE manual_voice IS NOT NULL OR manual_speed IS NOT NULL OR manual_pitch IS NOT NULL').fetchone()[0]
        approvals=db.execute('SELECT COUNT(*) FROM npcs WHERE approval IS NOT NULL').fetchone()[0]
        with db:db.execute('UPDATE npcs SET manual_voice=NULL,manual_speed=NULL,manual_pitch=NULL,approval=NULL')
    return dict(overrides=overrides,approvals=approvals,backup=str(backup))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--database',type=Path,default=ROOT/'piper-runtime/npcs.sqlite3')
    print(reset(parser.parse_args().database))
