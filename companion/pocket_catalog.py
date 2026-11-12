"""Validate Pocket 18M voice states and reuse the catalog eligibility policy."""
import hashlib
import json
import time
from pathlib import Path
from voice_catalog import normalize, Store as BaseStore
from pocket_paths import MODEL


def load(path):
    path = Path(path)
    document = json.loads(path.read_text(encoding='utf-8-sig'))
    catalog=validate(document,path.parent)
    for entry in catalog.values():
        state=path.parent/entry['model']
        entry['sound_revision'] = hashlib.sha256(state.read_bytes()).hexdigest()[:16]
    return catalog


def validate_state(path):
    from safetensors import safe_open
    expected=set()
    with safe_open(path,framework='numpy') as state:
        for layer in range(8):
            base=f'transformer.layers.{layer}.self_attn/'
            for field in ('cache','offset','pad'):
                key=base+field;expected.add(key)
                shape=state.get_slice(key).get_shape()
                if field=='cache':
                    if len(shape)!=5 or shape[:2]!=[2,1] or shape[2]<1 or shape[3:]!=[8,64]:raise ValueError('Not a compatible Pocket 18M voice state')
                elif shape!=[1]:raise ValueError('Invalid Pocket voice state')
        if set(state.keys())!=expected:raise ValueError('Not a compatible Pocket 18M voice state')


def validate(document,folder):
    folder=Path(folder)
    if not isinstance(document,dict) or not document:
        raise ValueError('Pocket catalog must contain voices')
    catalog = {}
    for key, value in document.items():
        entry = normalize(key,value)
        state = (folder/entry['model']).resolve()
        if state.parent != folder.resolve() or state.suffix != '.safetensors' or not state.is_file():
            raise ValueError('Missing or invalid Pocket voice state: '+key)
        if entry.get('engine_model') != MODEL:
            raise ValueError('Voice state must be exported for '+MODEL)
        if entry.get('speaker_id') is not None:raise ValueError('Pocket states contain one voice; no speaker ID is used')
        validate_state(state)
        catalog[key] = entry
    return catalog


class Store(BaseStore):
    validate=staticmethod(validate)

    def __init__(self,path,prune_missing=False):
        self.prune_missing=prune_missing;self.missing_removed=[]
        if prune_missing:self.validate=lambda document,folder: {} if document=={} else validate(document,folder)
        super().__init__(path)

    def reload(self):
        self.missing_removed=[]
        if self.prune_missing:
            original=self.path.read_bytes()
            document=json.loads(original.decode('utf-8-sig'))
            if not isinstance(document,dict):raise ValueError('Pocket catalog must be an object')
            remaining={};missing=[]
            for key,value in document.items():
                entry=normalize(key,value);state=(self.path.parent/entry['model']).resolve()
                # Invalid paths and corrupt files remain errors, not silent deletions.
                if state.parent==self.path.parent.resolve() and state.suffix=='.safetensors' and not state.exists():missing.append(key)
                else:remaining[key]=value
            if missing:
                self.validate(remaining,self.path.parent)
                if self.path.read_bytes()!=original:raise ValueError('Catalog changed while checking missing voices. Retry opening it.')
                backups=self.path.parent/'catalog-backups';backups.mkdir(exist_ok=True)
                (backups/f'{time.time_ns()}-missing-voices.json').write_bytes(original)
                temp=self.path.with_name(self.path.name+'.repair.tmp')
                temp.write_text(json.dumps(remaining,indent=2)+'\n',encoding='utf-8');temp.replace(self.path)
                self.missing_removed=missing
        super().reload()
