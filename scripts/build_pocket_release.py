"""Stage or zip the standalone Pocket test, without any private cache or database."""
import argparse
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import shutil
import sys
import zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'companion'))
from pocket_paths import ASSETS,VOICES,MODEL

def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def refresh_voices(stage):
    target=stage/'companion/pocket_voices'
    shutil.copytree(VOICES,target,dirs_exist_ok=True,ignore=shutil.ignore_patterns('catalog-backups','*.tmp'))
    catalog=json.loads((target/'catalog.json').read_text())
    lines=['# Voice attribution and licensing','','Exported states are adaptations for Pocket English 18M playback. Source links credit the original recordings.','','| Profile | License | Source |','|---|---|---|']
    for key,item in catalog.items():lines.append(f"| {key} | {item.get('license','Project-author volunteer test recording')} | {item.get('source','Local Halver reference supplied by lord-daeloth')} |")
    (stage/'VOICE-LICENSES.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    for name in ('build_pocket_release.py','expand_pocket_voices.py','review_pocket_smoke.py'):
        shutil.copyfile(ROOT/'scripts'/name,stage/'source/scripts'/name)
    for name in ('POCKET-BUILDING.md','requirements-pocket-build.txt'):
        shutil.copyfile(ROOT/'packaging'/name,stage/'source/packaging'/name)
    shutil.copyfile(ROOT/'packaging/POCKET-README.txt',stage/'README.txt')
    shutil.copyfile(ROOT/'packaging/START-Pocket-Catalog.cmd',stage/'START-Voice-Catalog.cmd')
    shutil.copyfile(ROOT/'packaging/POCKET-README.txt',stage/'source/packaging/POCKET-README.txt')
    print('Updated voice pack:',len(catalog),'profiles',flush=True)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--zip-only',action='store_true');parser.add_argument('--refresh-voices',action='store_true');args=parser.parse_args()
    stage=ROOT/'build/pocket-release/XISpeaksPocket'
    if args.refresh_voices:
        refresh_voices(stage)
        return
    if not args.zip_only:
        if stage.exists():raise RuntimeError('Stage exists; use a new staging folder or --zip-only after verification')
        shutil.copytree(ROOT/'addon/XISpeaksPocket',stage)
        companion=stage/'companion'
        shutil.copytree(ROOT/'build/pocket-frozen/XISpeaks-Pocket-Companion',companion)
        shutil.copytree(VOICES,companion/'pocket_voices',ignore=shutil.ignore_patterns('catalog-backups','*.tmp'))
        data=companion/'data';data.mkdir()
        for name in ('npc_associations.json','release_npc_overrides.json','moogle_associations.json'):
            shutil.copyfile(ROOT/'data'/name,data/name)
        tool='rubberband-4.0.0-gpl-executable-windows'
        shutil.copytree(ASSETS/'tools'/tool,companion/'tools'/tool)
        import os
        os.environ['HF_HOME']=str(ASSETS/'build/pocket-hf')
        from huggingface_hub import hf_hub_download
        models=companion/'models';models.mkdir()
        for name,revision in [('model.safetensors','a7056f505a4a8ca72d8b5fb1440071d6f1a35739'),('tokenizer.model','08ffc58775e62aad9409511b9591c9af626270f3')]:
            source=hf_hub_download('kyutai/pocket-tts-without-voice-cloning',f'languages/{MODEL}/{name}',revision=revision,local_files_only=True)
            shutil.copyfile(source,models/name)
        for source,target in [('packaging/POCKET-README.txt','README.txt'),('LICENSE','LICENSE'),('packaging/START-XISpeaks-Pocket.cmd','START-XISpeaks-Pocket.cmd'),('packaging/POCKET-THIRD-PARTY.md','THIRD-PARTY.md')]:shutil.copyfile(ROOT/source,stage/target)
        licenses=stage/'licenses';licenses.mkdir()
        shutil.copyfile(Path(sys.base_prefix)/'LICENSE.txt',licenses/'Python.txt')
        shutil.copyfile(ROOT/'build/expanded-voices/UPSTREAM-VOICES.md',licenses/'UPSTREAM-VOICES.md')
        for file in (ROOT/'build/pocket-license-texts').iterdir():shutil.copyfile(file,licenses/file.name)
        packages=[]
        for package in metadata.distributions():
            pname=package.metadata['Name'];packages.append(dict(name=pname,version=package.version))
            for file in package.files or []:
                if '..' not in file.parts and any(s in file.name.lower() for s in ('license','licence','copying','notice','copyright')):
                    source=Path(package.locate_file(file))
                    if source.is_file():
                        dest=licenses/pname/file;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest)
        (licenses/'packages.json').write_text(json.dumps(packages,indent=2))
        source=stage/'source';source.mkdir()
        for folder in ('companion','scripts','packaging','piper_trainer','voice_editor'):
            shutil.copytree(ROOT/folder,source/folder,ignore=shutil.ignore_patterns('__pycache__','output','*.pyc'))
        shutil.copytree(ROOT/'addon/XISpeaksPocket',source/'addon/XISpeaksPocket')
        shutil.copyfile(ROOT/'LICENSE',source/'LICENSE')
        for name in ('rubberband-4.0.0.tar.bz2','libsndfile-1.2.2.zip'):
            shutil.copyfile(ROOT.parent/'XISpeaks-Piper/build/piper-source'/name,source/name)
        catalog=json.loads((companion/'pocket_voices/catalog.json').read_text())
        lines=['# Voice attribution and licensing','', 'Exported states are adaptations for Pocket English 18M playback. Source links credit the original recordings.','', '| Profile | License | Source |','|---|---|---|']
        for key,item in catalog.items():lines.append(f"| {key} | {item.get('license','Project-author volunteer test recording')} | {item.get('source','Local Halver reference supplied by lord-daeloth')} |")
        (stage/'VOICE-LICENSES.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
        print('Staged',stage,'voices',len(catalog),flush=True)
        return
    # Test artifacts/settings must not become release seeds.
    runtime=stage/'companion/pocket-runtime'
    files=[p for p in stage.rglob('*') if p.is_file() and not p.is_relative_to(runtime) and p!=stage/'SHA256SUMS.json']
    assert not any(p.name in ('token','pocket-development.json') or p.suffix in ('.sqlite3','.wav') for p in files)
    manifest={str(p.relative_to(stage)).replace('\\','/'):digest(p) for p in files}
    (stage/'SHA256SUMS.json').write_text(json.dumps(manifest,indent=2))
    files.append(stage/'SHA256SUMS.json')
    dist=ROOT/'dist';dist.mkdir(exist_ok=True)
    archive=dist/'XISpeaks-Pocket-windows-x64-test-all-voices.zip'
    with zipfile.ZipFile(archive.with_suffix('.partial'),'w',zipfile.ZIP_DEFLATED,compresslevel=4) as z:
        for path in files:z.write(path,path.relative_to(stage.parent))
    archive.with_suffix('.partial').replace(archive)
    archive.with_suffix('.zip.sha256').write_text(digest(archive)+'  '+archive.name+'\n')
    print('ZIP',archive,'bytes',archive.stat().st_size,'unpacked',sum(p.stat().st_size for p in files),flush=True)

if __name__=='__main__':main()
