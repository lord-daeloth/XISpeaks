"""Package curated Pocket beta 3; never copy unreferenced voices or runtime data."""
import argparse,hashlib,json,shutil,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'companion'))
from pocket_paths import ASSETS,MODEL
from pocket_catalog import validate
VERSION='v1.0.0-beta.3'
STAGE=ROOT/'build/beta3-release/XISpeaks'
def digest(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--voices',type=Path);parser.add_argument('--zip',action='store_true');args=parser.parse_args()
    if not args.zip:
        if STAGE.exists():raise RuntimeError('Stage already exists; use a fresh staging folder')
        if args.voices is None:parser.error('--voices is required for staging')
        catalog=json.loads((ROOT/'data/pocket-catalog.json').read_text(encoding='utf-8'))
        validate(catalog,args.voices)
        shutil.copytree(ROOT/'addon/XISpeaks',STAGE)
        companion=STAGE/'companion';shutil.copytree(ROOT/'build/beta3-frozen/XISpeaks-Companion',companion)
        voices=companion/'pocket_voices';voices.mkdir()
        shutil.copyfile(ROOT/'data/pocket-catalog.json',voices/'catalog.json')
        for name in sorted({v['model'] for v in catalog.values()}):shutil.copyfile(args.voices/name,voices/name)
        old=ROOT/'build/pocket-release/XISpeaksPocket'
        shutil.copytree(old/'licenses',STAGE/'licenses')
        shutil.copytree(old/'companion/models',companion/'models')
        shutil.copytree(old/'companion/tools',companion/'tools')
        data=companion/'data';data.mkdir()
        for name in ('npc_associations.json','release_npc_overrides.json','moogle_associations.json'):shutil.copyfile(ROOT/'data'/name,data/name)
        for src,dst in [('README.md','README.txt'),('LICENSE','LICENSE'),('packaging/THIRD-PARTY.md','THIRD-PARTY.md'),('packaging/START-XISpeaks.cmd','START-XISpeaks.cmd'),('packaging/START-Voice-Catalog.cmd','START-Voice-Catalog.cmd')]:shutil.copyfile(ROOT/src,STAGE/dst)
        lines=['# Voice attribution and recorded terms','','Custom profiles preserve their supplied permission notes; these notes are not a new license grant.','','| Profile | Credit / source | License or supplied permission notes |','|---|---|---|']
        for key,v in catalog.items():
            clean=lambda x:str(x).replace('|','/').replace('\n',' ')
            lines.append('| '+key+' | '+clean(v.get('source') or v.get('credit','Unspecified'))+' | '+clean(v.get('license') or v.get('permission_notes','Unspecified'))+' |')
        (STAGE/'VOICE-LICENSES.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
        source=STAGE/'source';source.mkdir()
        for folder in ('addon/XISpeaks','companion','scripts','packaging','voice_editor'):
            shutil.copytree(ROOT/folder,source/folder,ignore=shutil.ignore_patterns('__pycache__','output','*.pyc'))
        shutil.copyfile(ROOT/'LICENSE',source/'LICENSE')
        for name in ('rubberband-4.0.0.tar.bz2','libsndfile-1.2.2.zip'):shutil.copyfile(old/'source'/name,source/name)
        print('STAGED',len(catalog),'voices',flush=True);return
    # Runtime self-tests may exist under staging; never ship them.
    files=sorted(p for p in STAGE.rglob('*') if p.is_file() and 'pocket-runtime' not in p.relative_to(STAGE).parts and p.name!='SHA256SUMS.json')
    assert not any(p.name in ('token','pocket-development.json') or p.suffix in ('.sqlite3','.wav') for p in files)
    catalog=json.loads((STAGE/'companion/pocket_voices/catalog.json').read_text())
    states=[p for p in files if p.parent==STAGE/'companion/pocket_voices' and p.suffix=='.safetensors']
    assert {p.name for p in states}=={v['model'] for v in catalog.values()}
    manifest={p.relative_to(STAGE).as_posix():digest(p) for p in files}
    (STAGE/'SHA256SUMS.json').write_text(json.dumps(manifest,indent=2))
    app=[p for p in files if p not in states]+[STAGE/'SHA256SUMS.json']
    # Balance source bytes to comfortably stay under GitHub's 2 GiB per asset limit.
    groups=[[],[]];sizes=[0,0]
    for p in sorted(states,key=lambda p:p.stat().st_size,reverse=True):
        i=sizes.index(min(sizes));groups[i].append(p);sizes[i]+=p.stat().st_size
    out=ROOT/'dist/beta3';out.mkdir(parents=True,exist_ok=True)
    hashes=[]
    for label,group in [('app',app),('voices-1',groups[0]),('voices-2',groups[1])]:
        archive=out/f'XISpeaks-{VERSION}-windows-x64-{label}.zip'
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=4) as z:
            for p in group:z.write(p,'XISpeaks/'+p.relative_to(STAGE).as_posix())
        assert archive.stat().st_size<2*1024**3
        hashes.append(digest(archive)+'  '+archive.name)
        print(archive.name,archive.stat().st_size,flush=True)
    (out/'SHA256SUMS.txt').write_text('\n'.join(hashes)+'\n')
if __name__=='__main__':main()
