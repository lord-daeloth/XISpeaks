"""Paths shared by the source checkout and the portable Windows distribution."""
from pathlib import Path
import sys
import shutil


def app_root():
    return Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[1]


def resource_root():
    return Path(sys._MEIPASS) if getattr(sys, 'frozen', False) else app_root()


def initialize_database(database, seed):
    """Seed only a new registry; never truncate an existing user's data."""
    try:
        target = database.open('xb')
    except FileExistsError:
        return
    try:
        with target, seed.open('rb') as source:
            shutil.copyfileobj(source, target)
    except BaseException:
        database.unlink(missing_ok=True)
        raise
