from pathlib import Path
import json
import sys
ROOT = Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[1]
local = ROOT / 'piper-development.json'
ASSETS = Path(json.loads(local.read_text(encoding='utf-8-sig'))['assets_root']) if local.exists() else ROOT
PYTHON = ASSETS / 'build/piper-train-env/Scripts/python.exe'
RUNS = ROOT / 'piper_trainer/output'
VOICES = ROOT / 'piper_voices'
