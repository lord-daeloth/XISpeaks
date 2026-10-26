"""Integration check for an extracted portable EXE (does not touch the live registry)."""
import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import tempfile
import time


def check(executable):
    with tempfile.TemporaryDirectory(prefix='XISpeaks portable test ') as directory:
        root = Path(directory)
        env = dict(os.environ, PATH=os.environ['SystemRoot'] + r'\System32',
                   HF_HOME=str(root / 'empty-hf'), PYTHONPATH='', PYTHONHOME='')
        database = root / 'npcs.sqlite3'
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.bind(('127.0.0.1', 0))
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as reservation:
                reservation.bind(('127.0.0.1', 0))
                port = reservation.getsockname()[1]
            client.settimeout(0.3)
            for attempt in range(2):
                with (root / f'run-{attempt}.log').open('w') as log:
                    process = subprocess.Popen([str(executable), '--dry-run', '--registry', str(database), '--port', str(port)],
                        cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
                    try:
                        deadline = time.monotonic() + 30
                        while True:
                            if process.poll() is not None or time.monotonic() > deadline:
                                raise RuntimeError((root / f'run-{attempt}.log').read_text())
                            client.sendto(b'XISUI\tsmoke\n{"action":"list","search":"Halver"}', ('127.0.0.1', port))
                            try:
                                reply = json.loads(client.recv(12000).split(b'\n', 1)[1])
                                assert reply['ok'], reply
                                assert reply['rows'][0]['name'] == 'Halver', reply
                                break
                            except (socket.timeout, ConnectionResetError):
                                time.sleep(0.05)
                        with closing(sqlite3.connect(database)) as db, db:
                            count = db.execute('SELECT COUNT(*) FROM npcs').fetchone()[0]
                            with closing(sqlite3.connect(executable.parent / '_internal/seed.sqlite3')) as seed:
                                assert count == seed.execute('SELECT COUNT(*) FROM npcs').fetchone()[0], count
                            if attempt == 0:
                                assert db.execute('SELECT SUM(encounters) FROM npcs').fetchone()[0] == 0
                                with closing(sqlite3.connect(executable.parent / '_internal/seed.sqlite3')) as seed:
                                    assert db.execute('SELECT key,manual_voice,manual_speed,manual_pitch FROM npcs ORDER BY key').fetchall() == seed.execute('SELECT key,manual_voice,manual_speed,manual_pitch FROM npcs ORDER BY key').fetchall()
                                db.execute("UPDATE npcs SET manual_voice='am_michael' WHERE key='halver'")
                            else:
                                assert db.execute("SELECT manual_voice FROM npcs WHERE key='halver'").fetchone()[0] == 'am_michael'
                    finally:
                        process.terminate()
                        process.wait(timeout=10)
        subprocess.run([str(executable), '--self-test'], cwd=root, env=env, check=True, timeout=240)
        print('PASS portable EXE: clean seed, UDP UI, preserved customization, isolated PATH and offline speech')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('executable', type=Path)
    check(parser.parse_args().executable.resolve())
