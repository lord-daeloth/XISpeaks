"""Prepare the upstream voice collection for offline 18M playback (maintainer only)."""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'companion'))
from pocket_paths import ASSETS, MODEL, VOICES
from voice_catalog import normalize

def fetch(url):
    with urllib.request.urlopen(url, timeout=120) as response:
        return response.read()

def main():
    os.environ['HF_HOME'] = str(ASSETS/'build/pocket-hf')
    os.environ['HF_HUB_OFFLINE'] = '1'
    import torch
    from pocket_tts import TTSModel, export_model_state
    from pocket_tts.utils.utils import _ORIGINS_OF_PREDEFINED_VOICES
    torch.set_num_threads(1)
    cache=ROOT/'build/expanded-voices';cache.mkdir(parents=True,exist_ok=True)
    pin=cache/'inventory.json'
    if not pin.exists():
        revision='323332d33f997de8394f24a193e1a76df720e01a'
        # This repository currently fits in one 1000-entry WAV listing only after paging.
        url=f'https://huggingface.co/api/models/kyutai/tts-voices/tree/{revision}?recursive=true&limit=1000'
        rows=[]
        while url:
            with urllib.request.urlopen(url,timeout=120) as response:
                rows.extend(json.load(response))
                link=response.headers.get('Link','')
                url=next((part.split('>')[0].strip().lstrip('<') for part in link.split(',') if 'rel="next"' in part),None)
        pin.write_text(json.dumps(dict(revision=revision,files=rows),indent=2))
    inventory=json.loads(pin.read_text());revision=inventory['revision']
    readme=fetch(f'https://huggingface.co/kyutai/tts-voices/raw/{revision}/README.md')
    (cache/'UPSTREAM-VOICES.md').write_bytes(readme)
    files={x['path']:x for x in inventory['files'] if x['path'].endswith('.wav')}
    selected=[p for p in sorted(files) if not p.endswith('_enhanced.wav') and p!='unmute-prod-website/degaulle-2.wav']
    selected=[p[:-4]+'_enhanced.wav' if p[:-4]+'_enhanced.wav' in files else p for p in selected]
    def download(p):
        dest=cache/'references'/p
        if not dest.exists():
            dest.parent.mkdir(parents=True,exist_ok=True)
            data=fetch(f'https://huggingface.co/kyutai/tts-voices/resolve/{revision}/{p}')
            if len(data)!=files[p]['size']:raise ValueError('Incomplete download '+p)
            dest.write_bytes(data)
        return p
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for i,p in enumerate(pool.map(download,selected),1):
            if i%25==0:print('Downloaded',i,'/',len(selected),flush=True)
    catalog=json.loads((VOICES/'catalog.json').read_text())
    piper=json.loads((ASSETS/'piper_voices/catalog.json').read_text())
    def canonical(p):return p.replace('_enhanced.wav','.wav')
    aliases={canonical(v.split('kyutai/tts-voices/')[-1]):k for k,v in _ORIGINS_OF_PREDEFINED_VOICES.items() if 'kyutai/tts-voices/' in v and '@' not in v}
    licenses={'voice-donations':'CC0-1.0','vctk':'CC-BY-4.0','alba-mackenna':'CC-BY-4.0','voice-zero':'CC0-1.0','ears':'CC-BY-NC-4.0','expresso':'CC-BY-NC-4.0','cml-tts':'CC-BY-4.0'}
    model=TTSModel.load_model(language=MODEL)
    if not model.has_voice_cloning:raise RuntimeError('Maintainer export requires cloning weights')
    manifest=[];failures=[]
    for i,p in enumerate(selected,1):
        group=p.split('/')[0]
        license=licenses.get(group,'CC0-1.0')
        if p.endswith('ex04_narration_longform_00001.wav'):license='CC-BY-NC-4.0'
        if p.endswith('p329_022.wav'):license='CC-BY-4.0'
        alias=aliases.get(canonical(p))
        key=next((k for k,v in catalog.items() if alias and v['model']==alias+'.safetensors'),None)
        gender,accent='u','x'
        if group=='vctk':
            speaker=Path(p).stem.split('_')[0]
            metadata=next((v for k,v in piper.items() if k.endswith('_vctk_'+speaker)),{})
            gender,accent=metadata.get('gender','u'),metadata.get('accent','x')
        if group=='alba-mackenna':gender,accent='f','b'
        if accent not in ('a','b','x'):accent='x'
        key=key or accent+gender+'_'+re.sub('[^a-z0-9_]+','_',canonical(p)[:-4].lower()).strip('_')[:85]
        dest=VOICES/(key+'.safetensors') if key not in catalog else VOICES/catalog[key]['model']
        try:
            if not dest.exists():
                state=model.get_state_for_audio_prompt(cache/'references'/p)
                export_model_state(state,dest)
            entry=catalog.get(key) or normalize(key,dict(model=dest.name,engine_model=MODEL,label=(group+' / '+Path(p).stem.replace('_enhanced',''))[:100],gender=gender,accent=accent,automatic=group not in ('cml-tts','unmute-prod-website')))
            entry.update(source=f'https://huggingface.co/kyutai/tts-voices/blob/{revision}/{p}',license=license,source_group=group)
            catalog[key]=entry
            manifest.append(dict(key=key,**entry,bytes=dest.stat().st_size,sha256=hashlib.sha256(dest.read_bytes()).hexdigest()))
        except Exception as error:
            failures.append(dict(source=p,error=str(error)))
        if i%20==0:print('Exported',i,'/',len(selected),'failures',len(failures),flush=True)
    (VOICES/'catalog.json').write_text(json.dumps(catalog,indent=2)+'\n')
    (VOICES/'sources.json').write_text(json.dumps(dict(repository='kyutai/tts-voices',revision=revision,voices=manifest,failures=failures),indent=2))
    print('CATALOG',len(catalog),'EXPORTED',len(manifest),'FAILURES',failures,flush=True)
    if failures:raise RuntimeError('Some exports failed; inspect sources.json')

if __name__=='__main__':main()
