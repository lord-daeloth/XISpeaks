"""Export stock 18M states and the selected volunteer states into the test catalog."""
import json
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'companion'))
from pocket_paths import ROOT, ASSETS, VOICES, MODEL

def main():
    import os
    os.environ['HF_HOME']=str(ASSETS/'build/pocket-hf')
    from huggingface_hub import hf_hub_download
    from pocket_tts.utils.utils import _ORIGINS_OF_PREDEFINED_VOICES
    from voice_catalog import normalize
    VOICES.mkdir(exist_ok=True)
    path=VOICES/'catalog.json'
    catalog=json.loads(path.read_text()) if path.exists() else {}
    piper=json.loads((ASSETS/'piper_voices/catalog.json').read_text())
    known={'alba':('f','b'),'marius':('m','u'),'javert':('m','u'),'cosette':('f','u'),'jean':('m','u')}
    for name,origin in _ORIGINS_OF_PREDEFINED_VOICES.items():
        if name in ('giovanni','lola','juergen','rafael','daan','estelle'):continue
        gender,accent=known.get(name,('u','u'))
        if '/vctk/' in origin:
            speaker=origin.split('/vctk/')[1].split('_')[0]
            found=next((v for k,v in piper.items() if k.endswith('_vctk_'+speaker)),None)
            if found:gender,accent=found['gender'],found['accent']
        accent='x' if accent=='u' else accent
        key=accent+gender+'_'+name
        source=hf_hub_download('kyutai/pocket-tts-without-voice-cloning',f'languages/{MODEL}/embeddings/{name}.safetensors',revision='a7056f505a4a8ca72d8b5fb1440071d6f1a35739',local_files_only=True)
        target=VOICES/(name+'.safetensors')
        if not target.exists():shutil.copyfile(source,target)
        catalog.setdefault(key,normalize(key,dict(model=target.name,engine_model=MODEL,label=name.title(),gender=gender,accent=accent)))
    for variant in ('long','short'):
        source=ASSETS/f'experiments/pocket_tts/output/likeness/{MODEL}-{variant}.safetensors'
        target=VOICES/f'halver-{variant}.safetensors'
        if not source.is_file():raise FileNotFoundError('Run the likeness comparison first: '+str(source))
        if not target.exists():shutil.copyfile(source,target)
        key='am_halver_'+variant
        catalog.setdefault(key,normalize(key,dict(model=target.name,engine_model=MODEL,label='Halver volunteer ('+variant+' reference)',automatic=False)))
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(catalog,indent=2)+'\n')
    temp.replace(path)
    print('Pocket catalog ready:',len(catalog),'voices')
if __name__=='__main__':main()
