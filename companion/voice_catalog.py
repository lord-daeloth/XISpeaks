"""Piper catalog validation, editing, eligibility and playback metadata."""
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import time

NPC_TYPES=('child','goblin','moogle','elvaan','galka','mithra','tarutaru','other')
GENDERS={'m','f','u','a'}
EDITABLE=('label','gender','accent','automatic','npc_types','volume','speed','sound_revision')

def normalize(key,item):
    if not re.fullmatch(r'[abx][fmua]_[a-z0-9_]{1,90}',key):raise ValueError('Voice IDs must start am_, af_, au_, aa_, bm_, bf_, bu_, ba_, or x equivalents')
    result=copy.deepcopy(item)
    result.setdefault('gender',key[1]);result.setdefault('accent',key[0])
    result.setdefault('label',key);result.setdefault('automatic',True)
    result.setdefault('speed',1.0);result.setdefault('volume',1.0)
    result.setdefault('speaker_id',None)
    flags=result.setdefault('npc_types',{})
    if not isinstance(flags,dict) or set(flags)-set(NPC_TYPES) or any(type(v)is not bool for v in flags.values()):raise ValueError('Invalid NPC eligibility flags')
    result['npc_types']={kind:flags.get(kind,True) for kind in NPC_TYPES}
    if result['gender'] not in GENDERS or result['accent'] not in ('a','b','x'):raise ValueError('Invalid gender or accent')
    if type(result['automatic']) is not bool:raise ValueError('Automatic assignment must be on or off')
    if not isinstance(result['label'],str) or not result['label'].strip() or len(result['label'])>100:raise ValueError('Label must contain 1–100 characters')
    for field,low,high in [('volume',0,3),('speed',.5,2)]:
        value=result[field]
        if type(value) not in (int,float) or not math.isfinite(value) or not low<=value<=high:raise ValueError(f'{field.title()} must be {low*100:g}–{high*100:g}%')
    return result

def validate(document,folder):
    if not isinstance(document,dict) or not document:raise ValueError('Keep at least one voice in the catalog; automatic assignment may be disabled')
    folder=Path(folder).resolve();configs={};result={}
    for key,item in document.items():
        if not isinstance(item,dict):raise ValueError('Invalid voice entry')
        entry=normalize(key,item)
        model=entry.get('model')
        if not isinstance(model,str):raise ValueError('Select an ONNX model')
        path=(folder/model).resolve()
        if path.parent!=folder or path.suffix.lower()!='.onnx' or not path.is_file():raise ValueError('Model must exist directly in the voice folder: '+model)
        if path not in configs:
            configs[path]=json.loads(Path(str(path)+'.json').read_text(encoding='utf-8-sig'))
        count=configs[path].get('num_speakers',1);speaker=entry['speaker_id']
        if type(count)is not int or count<1:raise ValueError('Invalid model speaker count')
        if count>1 and speaker is None:raise ValueError('Select a speaker for '+key)
        if speaker is not None and (type(speaker)is not int or not 0<=speaker<count):raise ValueError('Speaker ID out of range: '+key)
        result[key]=entry
    return result

def load(path):
    path=Path(path)
    return validate(json.loads(path.read_text(encoding='utf-8-sig')),path.parent)

def playback_models(catalog,folder):
    return {key:dict(path=Path(folder)/item['model'],speaker_id=item['speaker_id'],speed=item['speed'],volume=item['volume']) for key,item in catalog.items()}

def sound_fields(entry):
    return [entry['model'],entry.get('speaker_id'),entry.get('speed',1),entry.get('volume',1)]

class Policy:
    def __init__(self,catalog):self.catalog=catalog;self.cache={}
    def candidates(self,preference,presets):
        if presets.get('mithra'):preference='feminine'
        types=tuple(k for k in NPC_TYPES if k!='other' and presets.get(k)) or ('other',)
        signature=(preference,types)
        if signature not in self.cache:
            wanted='m' if preference=='masculine' else 'f'
            self.cache[signature]=sorted(key for key,item in self.catalog.items()
                if item['automatic'] and (preference=='unknown' or item['gender'] in (wanted,'a'))
                and all(item['npc_types'][kind] for kind in types)
                and ('elvaan' not in types or item['accent']=='b'))
        return self.cache[signature]
    def choose(self,key,preference,presets,preferred=None):
        candidates=self.candidates(preference,presets)
        if preferred in candidates:return preferred
        if not candidates:return ''
        digest=hashlib.sha256(('XISpeaks-v1:'+key).encode()).digest()
        return candidates[int.from_bytes(digest[:8],'big')%len(candidates)]

class Store:
    def __init__(self,path):self.path=Path(path);self.reload()
    def reload(self):
        self.catalog=load(self.path);self.digest=hashlib.sha256(self.path.read_bytes()).hexdigest()
        removed=self.path.with_name('catalog-removed.json')
        self.removed=set(json.loads(removed.read_text()) if removed.exists() else [])
    def save(self,catalog,removed=None):
        catalog=validate(catalog,self.path.parent)
        if hashlib.sha256(self.path.read_bytes()).hexdigest()!=self.digest:raise ValueError('Catalog changed in another app. Reload before saving; your draft has not overwritten it.')
        for key,entry in catalog.items():
            old=self.catalog.get(key)
            if old:
                changed=[field for field in (*EDITABLE,'model','speaker_id') if old.get(field)!=entry.get(field)]
                entry['overrides']=sorted(set(entry.get('overrides',[]))|set(changed))
            if old and sound_fields(old)!=sound_fields(entry):entry['sound_revision']=hashlib.sha256(json.dumps(sound_fields(entry)).encode()).hexdigest()[:16]
        backups=self.path.parent/'catalog-backups';backups.mkdir(exist_ok=True)
        shutil.copyfile(self.path,backups/f'{time.time_ns()}.json')
        if removed is not None:
            removal=self.path.with_name('catalog-removed.json');temp=removal.with_suffix('.tmp')
            temp.write_text(json.dumps(sorted(set(removed)-set(catalog)),indent=2));temp.replace(removal)
        temp=self.path.with_suffix('.tmp');temp.write_text(json.dumps(catalog,indent=2)+'\n',encoding='utf-8');temp.replace(self.path)
        self.reload()


def merge_stock(generated,existing,removed):
    result=copy.deepcopy(generated)
    for key,item in existing.items():
        if key in result:
            fields=set(EDITABLE)|set(item.get('overrides',[]))|{'overrides'}
            for field in fields:
                if field in item:result[key][field]=copy.deepcopy(item[field])
        elif not item.get('stock'):result[key]=copy.deepcopy(item)
    for key in removed:result.pop(key,None)
    return result
