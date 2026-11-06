"""Local paths for the isolated Pocket 18M experiment."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
local = ROOT/'pocket-development.json'
ASSETS = Path(json.loads(local.read_text())['assets_root']) if local.exists() else ROOT
VOICES = ROOT/'pocket_voices'
MODEL = 'english_18m_2026-10'
