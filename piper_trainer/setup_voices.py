"""Download only the four stock voices used by this experimental catalog."""
from pathlib import Path
import json
import shutil
import sys
from urllib.request import urlopen
from paths import ASSETS, ROOT, VOICES
STOCK = {'am_ryan':'en_US-ryan-high','af_lessac':'en_US-lessac-high','bm_alan':'en_GB-alan-medium','bf_cori':'en_GB-cori-medium'}

def main():
    from piper.download_voices import download_voice
    VOICES.mkdir(exist_ok=True)
    for key, name in STOCK.items():
        original=ASSETS/'build/piper-models'/f'{name}.onnx'
        for suffix in ('', '.json'):
            dest=VOICES/(name+'.onnx'+suffix)
            if not dest.exists() and Path(str(original)+suffix).exists():
                shutil.copyfile(str(original)+suffix,dest)
        download_voice(name,VOICES)
        lang,speaker,quality=name.split('-')
        with urlopen(f'https://huggingface.co/rhasspy/piper-voices/resolve/main/en/{lang}/{speaker}/{quality}/MODEL_CARD',timeout=60) as response:
            (VOICES/(name+'-MODEL_CARD')).write_bytes(response.read())
        print('Ready:',name,flush=True)
    catalog = {key:{'model':name+'.onnx','automatic':True} for key,name in STOCK.items()}
    path=VOICES/'catalog.json'
    if path.exists():
        catalog.update(json.loads(path.read_text()))
    if (VOICES/'am_halver.onnx').exists():
        catalog.setdefault('am_halver',{'model':'am_halver.onnx','automatic':False})
    path.write_text(json.dumps(catalog,indent=2))

if __name__=='__main__':main()
