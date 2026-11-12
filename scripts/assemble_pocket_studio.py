"""Complete the private local studio build; never bundle HF credentials or weights."""
import importlib.metadata as metadata
import json
from pathlib import Path
import shutil
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'companion'))
from pocket_paths import ASSETS

def main():
    target=ROOT/'dist/XISpeaks-Pocket-Studio'
    if not (target/'XISpeaks-Pocket-Studio.exe').is_file():raise RuntimeError('Build packaging/pocket-studio.spec first')
    tools=target/'tools/ffmpeg';tools.mkdir(parents=True,exist_ok=True)
    for name in ('ffmpeg.exe','ffprobe.exe'):shutil.copyfile(Path('C:/ffmpeg/bin')/name,tools/name)
    for name in ('LICENSE','README.txt'):shutil.copyfile(Path('C:/ffmpeg')/name,tools/name)
    (target/'START-Pocket-Studio.cmd').write_text('@echo off\nstart "" "%~dp0XISpeaks-Pocket-Studio.exe"\n')
    # Local developer configuration points to an already authorized cache. Do not
    # distribute this machine-specific file or the contents of that cache.
    (target/'pocket-development.json').write_text(json.dumps(dict(assets_root=str(ASSETS)),indent=2))
    shutil.copyfile(ROOT/'pocket_studio/README.md',target/'README.md');shutil.copyfile(ROOT/'LICENSE',target/'LICENSE')
    source=target/'source'
    for folder in ('pocket_studio','companion'):
        shutil.copytree(ROOT/folder,source/folder,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','output','*.pyc'))
    (source/'packaging').mkdir(parents=True,exist_ok=True)
    for name in ('pocket-studio.spec','requirements-pocket-build.txt'):shutil.copyfile(ROOT/'packaging'/name,source/'packaging'/name)
    licenses=target/'licenses';licenses.mkdir(exist_ok=True)
    shutil.copyfile(Path(sys.base_prefix)/'LICENSE.txt',licenses/'Python.txt')
    for package in metadata.distributions():
        for file in package.files or []:
            if '..' not in file.parts and any(s in file.name.lower() for s in ('license','licence','notice','copying','copyright')):
                src=Path(package.locate_file(file))
                if src.is_file():
                    dest=licenses/package.metadata['Name']/file;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest)
    print('Studio ready:',target)

if __name__=='__main__':main()
