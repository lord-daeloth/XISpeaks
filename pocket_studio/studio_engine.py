"""Local media preparation, Pocket 18M enrollment, and public-model auditions."""
import contextlib
import hashlib
import json
import logging
import math
import os
import re
import unicodedata
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import wave

ROOT=Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'companion'))
from pocket_paths import ASSETS, MODEL
from pocket_catalog import Store, validate_state
from voice_catalog import normalize

OUTPUT=ROOT/'pocket_studio/output'
CACHE=ASSETS/'build/pocket-hf'
FULL_REV='db04f0e653473e5c7333c69686ac92b7460b0c1d'
PUBLIC_REV='a7056f505a4a8ca72d8b5fb1440071d6f1a35739'
TOKEN_REV='08ffc58775e62aad9409511b9591c9af626270f3'
DENoise={'Off':None,'Light':6,'Moderate':12,'Strong':18}
os.environ['HF_HOME']=str(CACHE)
os.environ['HF_HUB_DISABLE_TELEMETRY']='1'

DEFAULT_AUDITION_TEXT = """Welcome to Vana'diel. There is much we have yet to discover beyond these walls.
What do you want? Do you have something else to report?
Your time will come in due course, my friend. Until then, be well.
I am extremely dark and broody...
I want you to suffer for your mistakes!"""


def load_audition_text():
    try:
        text=json.loads((OUTPUT/'studio-settings.json').read_text(encoding='utf-8')).get('audition_text')
        return text if isinstance(text,str) else DEFAULT_AUDITION_TEXT
    except (OSError,ValueError,AttributeError):return DEFAULT_AUDITION_TEXT


def save_audition_text(text):
    OUTPUT.mkdir(parents=True,exist_ok=True)
    atomic_json(OUTPUT/'studio-settings.json',{'audition_text':text})


class Cancelled(Exception):pass

def check(cancel):
    if cancel():raise Cancelled('Cancelled')

def atomic_json(path,data):
    path=Path(path);temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(data,indent=2)+'\n',encoding='utf8');temp.replace(path)

def tool(name):
    for p in (ROOT/'tools/ffmpeg'/f'{name}.exe',Path('C:/ffmpeg/bin')/f'{name}.exe'):
        if p.is_file():return str(p)
    found=shutil.which(name)
    if not found:raise ValueError('FFmpeg/ffprobe is missing. Put both EXEs in tools/ffmpeg.')
    return found

def run_tool(args,cancel=lambda:False,progress=lambda *a:None,duration=None):
    OUTPUT.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=OUTPUT) as folder:
        out=Path(folder)/'stdout';err=Path(folder)/'stderr'
        with out.open('wb') as stdout,err.open('wb') as stderr:
            p=subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            try:
                while p.poll() is None:
                    check(cancel)
                    if duration:
                        with out.open('rb') as f:
                            f.seek(max(0,out.stat().st_size-4096));lines=f.read().decode(errors='replace').splitlines()
                        stamps=[s.split('=',1)[1] for s in lines if s.startswith('out_time_us=')]
                        if stamps:
                            with contextlib.suppress(ValueError):progress('Converting media',min(99,float(stamps[-1])/1e6/duration*100))
                    time.sleep(.1)
                if p.returncode:raise ValueError(err.read_text(errors='replace')[-1800:])
            finally:
                if p.poll() is None:
                    p.terminate()
                    try:p.wait(timeout=3)
                    except subprocess.TimeoutExpired:p.kill();p.wait()
        check(cancel)
        return out.read_bytes()

def probe(path,cancel=lambda:False):
    path=Path(path).resolve()
    if not path.is_file():raise ValueError('Choose a local audio or video file.')
    data=json.loads(run_tool([tool('ffprobe'),'-v','error','-protocol_whitelist','file,pipe','-show_streams','-show_format','-of','json',str(path)],cancel))
    streams=[s for s in data.get('streams',[]) if s.get('codec_type')=='audio']
    if not streams:raise ValueError('This file has no audio track.')
    return dict(path=str(path),tracks=[dict(index=s['index'],codec=s.get('codec_name','?'),channels=s.get('channels',0),language=s.get('tags',{}).get('language',''),title=s.get('tags',{}).get('title','')) for s in streams],duration=float(data.get('format',{}).get('duration',0) or 0))

def measurements(audio,rate=24000):
    import numpy as np
    audio=np.asarray(audio,dtype=np.float64)
    peak=float(np.max(np.abs(audio))) if audio.size else 0
    rms=float(np.sqrt(np.mean(audio*audio))) if audio.size else 0
    return dict(seconds=len(audio)/rate,peak_dbfs=20*math.log10(peak) if peak else None,rms_dbfs=20*math.log10(rms) if rms else None,clipped_percent=float(np.mean(np.abs(audio)>=.999))*100 if audio.size else 0)

def inspect_wav(path,cancel=lambda:False):
    import numpy as np
    import soundfile as sf
    points=[];count=0;energy=0.;peak=0.;clipped=0
    with sf.SoundFile(path) as f:
        rate=f.samplerate;duration=len(f)/rate
        block=max(1024,math.ceil(len(f)/1500))
        for audio in f.blocks(blocksize=block,dtype='float32',always_2d=True):
            check(cancel);x=audio[:,0]
            if not np.isfinite(x).all():raise ValueError('Audio contains invalid samples.')
            points.append([float(x.min()),float(x.max())]);count+=len(x);energy+=float(np.sum(x.astype('float64')**2));peak=max(peak,float(np.max(np.abs(x))));clipped+=int(np.count_nonzero(np.abs(x)>=.999))
    if not count:raise ValueError('Audio is empty.')
    rms=math.sqrt(energy/count)
    return dict(seconds=duration,peak_dbfs=20*math.log10(peak) if peak else None,rms_dbfs=20*math.log10(rms) if rms else None,clipped_percent=clipped/count*100,points=points)

def import_media(info,track,cancel=lambda:False,progress=lambda *a:None):
    if track not in [t['index'] for t in info['tracks']]:raise ValueError('Choose one of the file’s audio tracks.')
    project=OUTPUT/('session-'+uuid.uuid4().hex[:12]);project.mkdir(parents=True)
    wav=project/'source.wav'
    run_tool([tool('ffmpeg'),'-nostdin','-hide_banner','-loglevel','error','-y','-protocol_whitelist','file,pipe','-i',info['path'],'-map',f'0:{track}','-vn','-ac','1','-ar','24000','-c:a','pcm_f32le','-progress','pipe:1',str(wav)],cancel,progress,info['duration'])
    summary=inspect_wav(wav,cancel)
    data=dict(version=1,source=info,track=track,summary=summary)
    atomic_json(project/'project.json',data)
    progress('Imported; select 3–30 seconds',100)
    return project,data

def clean_regions(regions,duration):
    result=sorted((float(a),float(b)) for a,b in regions)
    if not result:raise ValueError('Add at least one region.')
    for i,(a,b) in enumerate(result):
        if not math.isfinite(a) or not math.isfinite(b) or a<0 or b<=a or b>duration+.001:
            raise ValueError('Each region must have a valid start and end within the recording.')
        if i and a<result[i-1][1]:raise ValueError('Regions must not overlap.')
    return result


def preview_section(project,start,end,cancel=lambda:False):
    """Audition only the pending selection, without cloning duration limits."""
    import soundfile as sf
    target=Path(project)/'selection-preview.wav'
    with sf.SoundFile(Path(project)/'source.wav') as source:
        clean_regions([(start,end)],len(source)/source.samplerate)
        first=round(start*source.samplerate);last=min(len(source),round(end*source.samplerate))
        if last<=first:raise ValueError('Select a longer section to preview.')
        source.seek(first)
        with sf.SoundFile(target,'w',samplerate=source.samplerate,channels=source.channels,subtype='PCM_16') as output:
            remaining=last-first
            while remaining:
                check(cancel);audio=source.read(min(65536,remaining),dtype='float32')
                output.write(audio);remaining-=len(audio)
    return target


def selection(project,start,end,regions=None):
    import numpy as np
    import soundfile as sf
    with sf.SoundFile(Path(project)/'source.wav') as f:
        spans=clean_regions(regions if regions is not None else [(start,end)],len(f)/f.samplerate)
        total=sum(b-a for a,b in spans)
        if not 3<=total<=30:raise ValueError('The combined reference must be between 3 and 30 seconds.')
        parts=[]
        for a,b in spans:
            first=round(a*f.samplerate);f.seek(first)
            part=f.read(round(b*f.samplerate)-first,dtype='float32')
            # Short edge fades avoid clicks at joins without blending words together.
            if len(spans)>1:
                fade=min(round(.005*f.samplerate),len(part)//2)
                if fade:
                    part[:fade]*=np.linspace(0,1,fade);part[-fade:]*=np.linspace(1,0,fade)
            parts.append(part)
    audio=np.concatenate(parts)
    if measurements(audio)['rms_dbfs'] is None:raise ValueError('Selected reference is silent.')
    return audio


def prepare(project,start,end,denoise='Off',normalize_gain=True,cancel=lambda:False,regions=None):
    import numpy as np
    import soundfile as sf
    if denoise not in DENoise:raise ValueError('Unknown denoise setting')
    audio=selection(project,start,end,regions);check(cancel)
    folder=Path(project)/('prepared-'+uuid.uuid4().hex[:10]);folder.mkdir()
    sf.write(folder/'original.wav',audio,24000,subtype='PCM_16')
    processed=audio
    if DENoise[denoise]:
        sf.write(folder/'input.wav',audio,24000,subtype='FLOAT')
        run_tool([tool('ffmpeg'),'-nostdin','-v','error','-y','-i',str(folder/'input.wav'),'-af',f'afftdn=nr={DENoise[denoise]}:nf=-45:tn=1','-c:a','pcm_f32le',str(folder/'denoised.wav')],cancel)
        processed,_=sf.read(folder/'denoised.wav',dtype='float32')
    peak=float(np.max(np.abs(processed)));gain=1.
    if peak<=1e-7:raise ValueError('Prepared reference is silent.')
    if normalize_gain:gain=min(10**(24/20),10**(-3/20)/peak)
    processed=np.clip(processed*gain,-1,1)
    sf.write(folder/'reference.wav',processed,24000,subtype='PCM_16')
    meta=dict(start=start,end=end,regions=sorted(regions if regions is not None else [(start,end)]),denoise=denoise,normalize=normalize_gain,gain_db=20*math.log10(gain),original=measurements(audio),prepared=measurements(processed))
    atomic_json(folder/'processing.json',meta);check(cancel)
    return folder,meta

def cached_models():
    from huggingface_hub import hf_hub_download
    specs={'cloning':('kyutai/pocket-tts','model.safetensors',FULL_REV),'public':('kyutai/pocket-tts-without-voice-cloning','model.safetensors',PUBLIC_REV),'tokenizer':('kyutai/pocket-tts-without-voice-cloning','tokenizer.model',TOKEN_REV)}
    found={}
    for key,(repo,name,revision) in specs.items():
        try:found[key]=Path(hf_hub_download(repo,f'languages/{MODEL}/{name}',revision=revision,cache_dir=CACHE/'hub',local_files_only=True))
        except Exception:found[key]=None
    return found,specs

def setup_models(token='',cancel=lambda:False,progress=lambda *a:None):
    from huggingface_hub import constants,hf_hub_download,login
    old=constants.HF_HUB_OFFLINE;constants.HF_HUB_OFFLINE=False
    try:
        if token.strip():login(token=token.strip(),add_to_git_credential=False)
        found,specs=cached_models()
        for i,(key,(repo,name,revision)) in enumerate(specs.items()):
            check(cancel);progress('Preparing '+key+' model (download can take a few minutes)',i/3*100)
            if found[key] is None:hf_hub_download(repo,f'languages/{MODEL}/{name}',revision=revision,cache_dir=CACHE/'hub')
        check(cancel);progress('Models ready; cloning and playback are now offline',100)
    finally:constants.HF_HUB_OFFLINE=old

class Engine:
    def __init__(self):self.cloner=None;self.player=None
    def model(self,cloning,progress=lambda *a:None):
        name='cloner' if cloning else 'player'
        if getattr(self,name) is None:
            found,_=cached_models();key='cloning' if cloning else 'public'
            if not found[key] or not found['tokenizer']:raise ValueError('Model files are missing. Open Model setup and download them first.')
            progress('Loading '+('cloning' if cloning else 'public playback')+' model',None)
            import pocket_tts
            import torch
            import yaml
            torch.set_num_threads(1)
            config=yaml.safe_load((Path(pocket_tts.__file__).parent/'config'/f'{MODEL}.yaml').read_text(encoding='utf8'))
            config['weights_path']=str(found[key]);config['weights_path_without_voice_cloning']=str(found[key])
            config['flow_lm']['lookup_table']['tokenizer_path']=str(found['tokenizer'])
            OUTPUT.mkdir(parents=True,exist_ok=True)
            path=OUTPUT/(name+'-config.yaml');path.write_text(yaml.safe_dump(config),encoding='utf8')
            model=pocket_tts.TTSModel.load_model(config=path)
            if cloning and not model.has_voice_cloning:raise ValueError('Cloning weights were not loaded')
            model.has_voice_cloning=cloning;setattr(self,name,model)
        return getattr(self,name)
    def clone(self,project,prepared,label,cancel=lambda:False,progress=lambda *a:None):
        label=label.strip()
        if not label or len(label)>100:raise ValueError('Give the candidate a name (1–100 characters).')
        check(cancel);model=self.model(True,progress);check(cancel)
        progress('Encoding reference; cancellation takes effect after this stage',None)
        from pocket_tts import export_model_state
        state=model.get_state_for_audio_prompt(Path(prepared)/'reference.wav');check(cancel)
        candidate=Path(project)/('candidate-'+uuid.uuid4().hex[:12]);candidate.mkdir()
        export_model_state(state,candidate/'voice.safetensors');validate_state(candidate/'voice.safetensors')
        for name in ('original.wav','reference.wav','processing.json'):shutil.copyfile(Path(prepared)/name,candidate/name)
        meta=dict(label=label,engine_model=MODEL,model_revision=FULL_REV,public_revision=PUBLIC_REV,created=time.time(),reference_sha256=hashlib.sha256((candidate/'reference.wav').read_bytes()).hexdigest(),processing=json.loads((candidate/'processing.json').read_text()))
        atomic_json(candidate/'candidate.json',meta);progress('Candidate created',100)
        return candidate,meta
    def audition(self,candidates,texts,seeds,cancel=lambda:False,progress=lambda *a:None):
        import torch
        import numpy as np
        import soundfile as sf
        if not texts or len(texts)>6 or any(not t.strip() or len(t)>1200 for t in texts):raise ValueError('Enter 1–6 nonempty test lines, up to 1200 characters each.')
        if not seeds or len(seeds)>4 or any(type(s) is not int or not 0<=s<=2147483647 for s in seeds):raise ValueError('Use 1–4 seeds between 0 and 2147483647.')
        model=self.model(False,progress);results=[];total=len(candidates)*len(texts)*len(seeds)
        warnings=[]
        class Capture(logging.Handler):
            def emit(self,record):
                if record.levelno>=logging.WARNING:warnings.append(record.getMessage())
        logger=logging.getLogger('pocket_tts.models.tts_model');capture=Capture();logger.addHandler(capture)
        try:
            for folder in candidates:
                folder=Path(folder);state=model.get_state_for_audio_prompt(folder/'voice.safetensors')
                label=json.loads((folder/'candidate.json').read_text())['label']
                for text in texts:
                    for seed in seeds:
                        check(cancel);warnings.clear();torch.manual_seed(seed)
                        progress('Auditioning '+label,len(results)/total*100)
                        stop=threading.Event();chunks=[];start=time.perf_counter()
                        stream=model.generate_audio_stream(state,text,stop=stop)
                        try:
                            for chunk in stream:
                                check(cancel);chunks.append(chunk.detach().cpu().numpy().reshape(-1))
                        finally:stop.set();stream.close()
                        check(cancel)
                        if not chunks:raise ValueError('No speech was generated.')
                        audio=np.concatenate(chunks);dest=folder/('preview-'+uuid.uuid4().hex[:10]+'.wav');sf.write(dest,audio,24000,subtype='PCM_16')
                        result=dict(candidate=str(folder),label=label,text=text,seed=seed,file=str(dest),metrics=measurements(audio),generation_seconds=time.perf_counter()-start,warnings=list(warnings))
                        atomic_json(dest.with_suffix('.json'),result);results.append(result)
            progress('Auditions ready',100);return results
        finally:logger.removeHandler(capture)

def profile(candidate,key,label,gender,accent,credit,permission,flags,npc='',automatic=False):
    meta=json.loads((Path(candidate)/'candidate.json').read_text())
    if not credit.strip() or not permission.strip():raise ValueError('Enter speaker credit and permission/release notes before exporting.')
    return normalize(key,dict(model=key+'.safetensors',engine_model=MODEL,label=label.strip(),gender=gender,accent=accent,automatic=bool(automatic),npc_types=flags,credit=credit.strip(),permission_notes=permission.strip(),intended_npc=npc.strip(),model_revision=meta['model_revision'],reference_sha256=meta['reference_sha256'],stock=False))

def stable_voice_id(label,gender,accent):
    name=unicodedata.normalize('NFKD',label).encode('ascii','ignore').decode().lower()
    name=re.sub(r'[^a-z0-9]+','_',name).strip('_') or 'new_voice'
    return accent+gender+'_'+name


def install(candidate,key,entry,catalog_path,overwrite=False):
    store=Store(catalog_path)
    target=store.path.parent/entry['model']
    if target.parent.resolve()!=store.path.parent.resolve():raise ValueError('Invalid voice file path.')
    if (key in store.catalog or target.exists()) and not overwrite:raise ValueError('That voice ID or file already exists. Confirm replacement first.')
    if any(k!=key and v['model']==entry['model'] for k,v in store.catalog.items()):
        raise ValueError('This voice file is shared by another catalog entry. Choose a different ID.')
    validate_state(Path(candidate)/'voice.safetensors')
    previous=target.read_bytes() if target.exists() else None
    try:
        shutil.copyfile(Path(candidate)/'voice.safetensors',target)
        catalog=dict(store.catalog);catalog[key]=entry
        store.save(catalog,store.removed-{key})
    except Exception:
        if previous is None:target.unlink(missing_ok=True)
        else:target.write_bytes(previous)
        raise
    return target


def export(candidate,key,entry,folder,overwrite=False):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    state=folder/entry['model'];metadata=folder/(key+'.json')
    if state.parent.resolve()!=folder.resolve() or metadata.parent.resolve()!=folder.resolve():raise ValueError('Invalid export path.')
    if (state.exists() or metadata.exists()) and not overwrite:raise ValueError('Export files already exist. Confirm replacement first.')
    validate_state(Path(candidate)/'voice.safetensors')
    previous={p:p.read_bytes() if p.exists() else None for p in (state,metadata)}
    try:
        shutil.copyfile(Path(candidate)/'voice.safetensors',state)
        atomic_json(metadata,{key:entry})
    except Exception:
        for path,data in previous.items():
            if data is None:path.unlink(missing_ok=True)
            else:path.write_bytes(data)
        raise
    return state


def microphones():
    import pyaudio
    pa=pyaudio.PyAudio()
    try:return [(i,pa.get_device_info_by_index(i)['name']) for i in range(pa.get_device_count()) if pa.get_device_info_by_index(i)['maxInputChannels']>0]
    finally:pa.terminate()

def record(device,stop,cancel=lambda:False,progress=lambda *a:None):
    import numpy as np
    import pyaudio
    OUTPUT.mkdir(parents=True,exist_ok=True)
    path=OUTPUT/('recording-'+uuid.uuid4().hex[:12]+'.wav')
    pa=pyaudio.PyAudio();stream=None
    try:
        info=pa.get_device_info_by_index(device);rate=int(info['defaultSampleRate'])
        stream=pa.open(format=pyaudio.paInt16,channels=1,rate=rate,input=True,input_device_index=device,frames_per_buffer=1024)
        with wave.open(str(path),'wb') as f:
            f.setparams((1,2,rate,0,'NONE','not compressed'));frames=0
            while not stop.is_set() and frames<rate*180:
                check(cancel);data=stream.read(1024,exception_on_overflow=False);f.writeframesraw(data);frames+=len(data)//2
                peak=float(np.max(np.abs(np.frombuffer(data,dtype='<i2').astype(float))))/32768
                progress(f'Recording {frames/rate:.1f}s — peak {20*math.log10(max(peak,1e-9)):.1f} dBFS',min(100,peak*100))
        check(cancel)
        if frames/rate<3:raise ValueError('Record at least three seconds of speech.')
        return path
    finally:
        if stream:stream.close()
        pa.terminate()
