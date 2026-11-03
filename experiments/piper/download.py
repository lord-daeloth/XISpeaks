"""Download the comparison models and model cards; no volunteer audio involved."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'build/piper-deps'))
from piper.download_voices import download_voice


def download(name):
    folder=ROOT/'build/piper-models';folder.mkdir(parents=True,exist_ok=True)
    download_voice(name,folder)
    lang,speaker,quality=name.split('-')
    url=f'https://huggingface.co/rhasspy/piper-voices/resolve/main/en/{lang}/{speaker}/{quality}/MODEL_CARD'
    with urlopen(url,timeout=60) as response:
        (folder/(name+'-MODEL_CARD')).write_bytes(response.read())
    print(name,'ready',flush=True)


if __name__=='__main__':
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(download,['en_GB-alan-medium','en_US-lessac-high','en_US-ryan-high']))
