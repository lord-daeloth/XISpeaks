"""Build the portable ZIP from a clean PyInstaller output and pinned voice assets."""
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import shutil
import sys
import tempfile
from urllib.request import urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'piper_trainer'))
from paths import ASSETS, VOICES

SOURCES = {
    'piper-1.8.0.zip':'https://codeload.github.com/OHF-Voice/piper1-gpl/zip/refs/tags/v1.8.0',
    'espeak-ng-724808c.zip':'https://codeload.github.com/espeak-ng/espeak-ng/zip/724808c',
    'rubberband-4.0.0.tar.bz2':'https://breakfastquay.com/files/releases/rubberband-4.0.0.tar.bz2',
    'libsndfile-1.2.2.zip':'https://codeload.github.com/libsndfile/libsndfile/zip/refs/tags/1.2.2',
}

def digest(file):
    with file.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()

def main():
    dist=ROOT/'dist'
    dist.mkdir(exist_ok=True)
    archive=dist/'XISpeaks-windows-x64-v1.0.0.zip'
    with tempfile.TemporaryDirectory(dir=ROOT/'build') as temp:
        stage=Path(temp)/'XISpeaks'
        shutil.copytree(ROOT/'addon/XISpeaks',stage)
        companion=stage/'companion'
        frozen=ROOT/'build/frozen/XISpeaks-Companion'
        shutil.copytree(frozen/'_internal',companion/'_internal')
        shutil.copyfile(frozen/'XISpeaks-Companion.exe',companion/'XISpeaks-Companion.exe')
        tool='rubberband-4.0.0-gpl-executable-windows'
        shutil.copytree(ASSETS/'tools'/tool,companion/'_internal/tools'/tool,dirs_exist_ok=True)
        data=companion/'data'
        shutil.copytree(ROOT/'data/piper-model-info',data/'piper-model-info')
        for name in ('piper-models.json','piper-catalog.json','npc_associations.json','moogle_associations.json','release_npc_overrides.json'):
            shutil.copyfile(ROOT/'data'/name,data/name)
        voices=companion/'piper_voices'
        voices.mkdir()
        name='en_US-libritts-high.onnx'
        model=VOICES/name
        pinned=next(m for m in json.loads((data/'piper-models.json').read_text()) if m['name']==name)
        if digest(model)!=pinned['sha256']:raise ValueError('Unexpected starter model')
        shutil.copyfile(model,voices/name)
        shutil.copyfile(data/'piper-model-info'/(name+'.json'),voices/(name+'.json'))
        for src,dst in [('README.md','README.txt'),('LICENSE','LICENSE'),('packaging/START-XISpeaks.cmd','START-XISpeaks.cmd'),('packaging/THIRD-PARTY.md','THIRD-PARTY.md')]:
            shutil.copyfile(ROOT/src,stage/dst)
        licenses=stage/'licenses'
        licenses.mkdir()
        shutil.copyfile(Path(sys.base_prefix)/'LICENSE.txt', licenses/'Python.txt')
        packages=[]
        for package in metadata.distributions():
            pname=package.metadata['Name']
            packages.append(dict(name=pname,version=package.version,license=package.metadata.get('License-Expression') or package.metadata.get('License')))
            for file in package.files or []:
                if any(s in file.name.lower() for s in ('license','licence','copying','notice','copyright')) and '..' not in file.parts:
                    source=Path(package.locate_file(file))
                    if source.is_file():
                        dest=licenses/pname/file
                        dest.parent.mkdir(parents=True,exist_ok=True)
                        shutil.copyfile(source,dest)
        (licenses/'packages.json').write_text(json.dumps(packages,indent=2),encoding='utf8')
        source=stage/'source'
        source.mkdir()
        for folder in ('companion','scripts','piper_trainer','packaging'):
            shutil.copytree(ROOT/folder,source/folder,ignore=shutil.ignore_patterns('__pycache__','output','*.pyc'))
        for name in ('requirements.txt','setup-rubberband.ps1','LICENSE'):
            shutil.copyfile(ROOT/name,source/name)
        cache=ROOT/'build/piper-source'
        cache.mkdir(exist_ok=True)
        for name,url in SOURCES.items():
            path=cache/name
            if not path.exists():
                with urlopen(url,timeout=120) as response,path.with_suffix('.download').open('wb') as target:
                    shutil.copyfileobj(response,target)
                path.with_suffix('.download').replace(path)
            shutil.copyfile(path,source/name)
        partial=archive.with_suffix('.partial')
        with zipfile.ZipFile(partial,'w',zipfile.ZIP_DEFLATED,compresslevel=4) as output:
            for path in stage.rglob('*'):
                if path.is_file():output.write(path,path.relative_to(stage.parent))
        partial.replace(archive)
    archive.with_suffix('.zip.sha256').write_text(digest(archive)+'  '+archive.name+'\n')
    print(archive,archive.stat().st_size,flush=True)

if __name__=='__main__':main()
