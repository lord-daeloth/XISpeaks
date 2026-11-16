import json,sys,zipfile
from pathlib import Path
import importlib.metadata
root=Path(__file__).resolve().parents[2]
out=Path(__file__).parent/'output'
env=root/'build/pocket-env'
runtime=[]
for path in env.rglob('*'):
    if path.is_file() and '__pycache__' not in path.parts and path.suffix!='.pyc':
        runtime.append(path)
base=Path(sys.base_prefix)
for folder in ['DLLs','Lib']:
    for path in (base/folder).rglob('*'):
        if path.is_file() and not {'site-packages','__pycache__','test','tests','tkinter','idlelib'}.intersection(path.parts) and path.suffix!='.pyc':
            runtime.append(path)
runtime.extend(p for p in base.glob('*.dll'))
runtime.extend(p for p in base.glob('python*.exe'))
archive=root/'build/pocket-runtime-sizing.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=4) as z:
    for i,p in enumerate(runtime):z.write(p,f'{i}/{p.name}')
sizes=dict(runtime_uncompressed=sum(p.stat().st_size for p in runtime),runtime_zip=archive.stat().st_size,method='Conservative runtime archive including installed dependencies and Python standard library; excludes bytecode caches/tests from base Python. Not a frozen EXE measurement.',models=[])
snapshots=root/'build/pocket-hf/hub/models--kyutai--pocket-tts-without-voice-cloning/snapshots'
for language in ['english','english_18m_2026-10','english_7m_2026-10','english_2m_2026-10']:
    paths={}
    for folder in snapshots.glob('*/languages/'+language):
        for p in folder.rglob('*'):
            if p.is_file():paths[p.relative_to(folder).as_posix()]=p
    if not paths:continue
    archive=root/'build'/f'pocket-{language}-sizing.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=4) as z:
        for name,p in paths.items():z.write(p,name)
    voices=[p for name,p in paths.items() if name.startswith('embeddings/')]
    sizes['models'].append(dict(language=language,weights=sum(p.stat().st_size for n,p in paths.items() if n.endswith('model.safetensors')),voices=len(voices),voices_bytes=sum(p.stat().st_size for p in voices),assets_bytes=sum(p.stat().st_size for p in paths.values()),assets_zip=archive.stat().st_size,files=list(paths)))
sizes['versions']={d.metadata['Name']:d.version for d in importlib.metadata.distributions()}
(out/'sizes.json').write_text(json.dumps(sizes,indent=2))
print(json.dumps({k:v for k,v in sizes.items() if k!='versions'},indent=2))
