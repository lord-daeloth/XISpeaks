"""Install the highest quality of every English Piper model and expose all speakers."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import shutil
import tarfile
from urllib.request import urlopen
from paths import ROOT, VOICES
BASE='https://huggingface.co/rhasspy/piper-voices/resolve/main/'
QUALITY={'x_low':0,'low':1,'medium':2,'high':3}
# Verified existing voices and explicitly gendered dataset names. Unknowns stay unknown.
GENDERS={'alan':'m','cori':'f','lessac':'f','ryan':'m','hfc_female':'f','hfc_male':'m',
         'northern_english_male':'m','southern_english_female':'f','ljspeech':'f'}

def best_english(index):
    selected={}
    for key,item in index.items():
        if not key.startswith('en_'):continue
        family=key.rsplit('-',1)[0]
        if family not in selected or QUALITY[item['quality']]>QUALITY[selected[family][1]['quality']]:selected[family]=(key,item)
    return sorted(selected.values())

def valid(path,info):
    if not path.is_file() or path.stat().st_size!=info['size']:return False
    data=path.read_bytes()
    if 'lfs' in info:return hashlib.sha256(data).hexdigest()==info['lfs']['oid']
    return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==info['oid']

def download(entry):
    key,item=entry
    directory=str(Path(next(iter(item['files']))).parent).replace('\\','/')
    with urlopen('https://huggingface.co/api/models/rhasspy/piper-voices/tree/'+REVISION+'/'+directory,timeout=60) as response:
        files=[f for f in json.load(response) if f['type']=='file']
    for info in files:
        remote=info['path'];filename=Path(remote).name
        if filename not in (key+'.onnx',key+'.onnx.json','MODEL_CARD'):continue
        path=VOICES/(key+'-MODEL_CARD' if filename=='MODEL_CARD' else filename)
        if valid(path,info):continue
        temporary=path.with_suffix(path.suffix+'.download')
        if not valid(temporary,info):
            with urlopen(BASE+remote,timeout=120) as response,temporary.open('wb') as target:shutil.copyfileobj(response,target)
        if not valid(temporary,info):raise ValueError('Download checksum mismatch: '+remote)
        temporary.replace(path)
    config=json.loads((VOICES/(key+'.onnx.json')).read_text(encoding='utf-8'))
    item.update(num_speakers=config['num_speakers'],speaker_id_map=config.get('speaker_id_map',{}),verified_files=files)
    print('Verified:',key,config['num_speakers'],'speakers',flush=True)
    return entry

def speaker_genders():
    cache=VOICES/'librispeech-speakers.txt'
    if not cache.exists():
        # Dataset metadata precedes audio in this archive. Never unpack audio.
        with urlopen('https://www.openslr.org/resources/12/dev-clean.tar.gz',timeout=60) as response:
            with tarfile.open(fileobj=response,mode='r|gz') as archive:
                for member in archive:
                    if member.offset>15000000:raise ValueError('Speaker metadata not found at archive start')
                    if member.name.endswith('SPEAKERS.TXT'):
                        cache.write_bytes(archive.extractfile(member).read());break
    genders={}
    for line in cache.read_text(encoding='utf-8').splitlines():
        fields=[x.strip() for x in line.split('|')]
        if len(fields)>1 and fields[0].isdigit() and fields[1] in ('M','F'):genders[fields[0]]=fields[1].lower()
    return genders

def vctk_metadata():
    cache=VOICES/'vctk-speaker-info.txt'
    url='https://datashare.ed.ac.uk/server/api/core/bitstreams/ab3c7d2f-98b2-4271-b7e4-40a6ffb40d1d/content'
    if not cache.exists():
        with urlopen(url,timeout=60) as response:cache.write_bytes(response.read())
    metadata={}
    for line in cache.read_text(encoding='utf-8').splitlines():
        fields=line.split()
        if len(fields)>=4 and fields[0].isdigit() and fields[2] in ('M','F'):
            accent=fields[3]
            group='a' if accent in ('American','Canadian') else 'b' if accent in ('English','Scottish','Welsh','Irish','NorthernIrish') else 'x'
            metadata['p'+fields[0]]=dict(gender=fields[2].lower(),accent=group,description=accent)
    return metadata

def make_catalog(entries,genders,vctk=None):
    vctk=vctk or {}
    catalog={}
    for key,item in entries:
        lang,name,quality=key.split('-');accent='a' if lang=='en_US' else 'b'
        speakers=item.get('speaker_id_map',{}) if item['num_speakers']>1 else {'':None}
        if len(speakers)!=item['num_speakers']:raise ValueError('Incomplete speaker map: '+key)
        for speaker,sid in speakers.items():
            gender=genders.get(speaker.removeprefix('p'),'u') if name in ('libritts','libritts_r') else GENDERS.get(name,'u')
            speaker_accent=accent
            if name=='vctk':
                gender=vctk.get(speaker,{}).get('gender','u');speaker_accent=vctk.get(speaker,{}).get('accent','x')
            card=VOICES/(key+'-MODEL_CARD')
            if gender=='u' and not speaker and card.exists():
                description=card.read_text(encoding='utf-8').lower()
                if 'english female voice' in description:gender='f'
                elif 'english male voice' in description:gender='m'
            suffix='_'+re.sub('[^a-z0-9_]','_',speaker.lower()) if speaker else ''
            identity=f'{speaker_accent}{gender}_{name}{suffix}'
            if identity in catalog:raise ValueError('Duplicate speaker key: '+identity)
            catalog[identity]=dict(model=key+'.onnx',speaker_id=sid,automatic=True,stock=True,
                label=f'{name} / {speaker}' if speaker else name,gender=gender,quality=quality,language=lang)
    return catalog

def main():
    global BASE,REVISION
    with urlopen('https://huggingface.co/api/models/rhasspy/piper-voices',timeout=60) as response:REVISION=json.load(response)['sha']
    BASE='https://huggingface.co/rhasspy/piper-voices/resolve/'+REVISION+'/'
    VOICES.mkdir(exist_ok=True)
    with urlopen(BASE+'voices.json',timeout=60) as response:index=json.load(response)
    entries=best_english(index)
    with ThreadPoolExecutor(max_workers=3) as workers:list(workers.map(download,entries))
    catalog=make_catalog(entries,speaker_genders(),vctk_metadata())
    path=VOICES/'catalog.json'
    import sys
    sys.path.insert(0,str(ROOT/'companion'))
    from voice_catalog import merge_stock
    old=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    if path.exists():shutil.copyfile(path,VOICES/'catalog.before-all-english.json')
    removed=VOICES/'catalog-removed.json'
    catalog=merge_stock(catalog,old,json.loads(removed.read_text()) if removed.exists() else [])
    temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(catalog,indent=2),encoding='utf-8');temporary.replace(path)
    (VOICES/'english-models.json').write_text(json.dumps(dict(revision=REVISION,entries=entries,total_speakers=len(catalog)),indent=2),encoding='utf-8')
    print(f'Catalog ready: {len(entries)} models, {len(catalog)} selectable speakers',flush=True)

if __name__=='__main__':main()
