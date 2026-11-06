"""Validate Pocket 18M voice states and reuse the catalog eligibility policy."""
import hashlib
import json
from pathlib import Path
from voice_catalog import normalize
from pocket_paths import MODEL


def load(path):
    path = Path(path)
    document = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(document,dict) or not document:
        raise ValueError('Pocket catalog must contain voices')
    catalog = {}
    for key, value in document.items():
        entry = normalize(key,value)
        state = (path.parent/entry['model']).resolve()
        if state.parent != path.parent.resolve() or state.suffix != '.safetensors' or not state.is_file():
            raise ValueError('Missing or invalid Pocket voice state: '+key)
        if entry.get('engine_model') != MODEL:
            raise ValueError('Voice state must be exported for '+MODEL)
        entry['sound_revision'] = hashlib.sha256(state.read_bytes()).hexdigest()[:16]
        catalog[key] = entry
    return catalog
