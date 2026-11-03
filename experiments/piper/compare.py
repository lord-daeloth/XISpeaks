"""CPU Piper/Kokoro timing and listening comparison in separate processes."""
import argparse
import html
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
import wave

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).parent/'output'
TEXTS=[
    "What do you want? Do you have something else to report? You are within the walls of Chateau d'Oraguille, home of royalty. Conduct yourself accordingly.",
    "Its layout and features resemble Zi'Tah, of that there can be no doubt. Yet the magic and warmth are gone, like we are in a different world entirely.",
    "Lion? Lion!? In the future from which I hail, the master faced many threats—not just that one—and came to be known as one of Vana'diel's most storied heroes.",
]
VOICES=[('piper','en_GB-alan-medium'),('piper','en_US-lessac-high'),('piper','en_US-ryan-high'),
        ('kokoro','bm_george'),('kokoro','af_heart')]


def worker(engine,name):
    import gc
    if engine=='piper':sys.path.insert(0,str(ROOT/'build/piper-deps'))
    os.environ['HF_HUB_CACHE']=str(ROOT/'build/assets/models/hub')
    os.environ['HF_HUB_OFFLINE']='1';os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
    import numpy as np
    started=time.perf_counter()
    if engine=='piper':
        from piper import PiperVoice
        voice=PiperVoice.load(ROOT/'build/piper-models'/f'{name}.onnx',use_cuda=False)
        def synth(text):
            for chunk in voice.synthesize(text):yield chunk.audio_int16_bytes,chunk.sample_rate
        thread_policy='ONNX Runtime default CPU session'
    else:
        import torch
        from kokoro import KPipeline
        torch.set_num_threads(4)
        pipeline=KPipeline(lang_code='b' if name.startswith('b') else 'a',repo_id='hexgrad/Kokoro-82M',device='cpu')
        pack=pipeline.load_voice(name)
        def synth(text):
            for result in pipeline(text,voice=pack,speed=1):
                if result.audio is not None:
                    audio=result.audio.detach().cpu().numpy()
                    yield np.rint(np.clip(audio,-1,1)*32767).astype('<i2').tobytes(),24000
        thread_policy='PyTorch CPU, 4 intra-op threads'
    load_seconds=time.perf_counter()-started
    started=time.perf_counter();list(synth('May your travels be safe, my friend.'))
    first_call=time.perf_counter()-started
    rows=[]
    for index,text in enumerate(TEXTS):
        timings=[]
        for repeat in range(3):
            chunks=[];first=None;started=time.perf_counter()
            for data,rate in synth(text):
                if first is None:first=time.perf_counter()-started
                chunks.append(data)
            elapsed=time.perf_counter()-started
            pcm=b''.join(chunks)
            if not pcm or first is None:raise ValueError('Empty synthesis')
            signal=np.frombuffer(pcm,dtype='<i2')
            if np.max(np.abs(signal.astype(np.int32)))<100:raise ValueError('Silent synthesis')
            duration=len(pcm)/2/rate
            timings.append(dict(first_chunk=first,total=elapsed,audio_seconds=duration,rtf=elapsed/duration))
            if repeat==0:
                file=f'{engine}-{name}-{index}.wav'
                with wave.open(str(OUT/file),'wb') as wav:
                    wav.setparams((1,2,rate,0,'NONE','not compressed'));wav.writeframes(pcm)
        rows.append(dict(text=text,file=file,measurements=timings,
            median={key:statistics.median(t[key] for t in timings) for key in timings[0]}))
    result=dict(engine=engine,voice=name,load_seconds=load_seconds,first_call_seconds=first_call,
        thread_policy=thread_policy,samples=rows)
    (OUT/f'{engine}-{name}.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(name,round(statistics.median(r['median']['rtf'] for r in rows),3),'RTF',flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--worker',nargs=2)
    args=parser.parse_args()
    if args.worker:worker(*args.worker);return
    OUT.mkdir(parents=True,exist_ok=False)
    for engine,name in VOICES:
        subprocess.run([sys.executable,str(Path(__file__).resolve()),'--worker',engine,name],check=True,cwd=ROOT)
    results=[json.loads((OUT/f'{engine}-{name}.json').read_text()) for engine,name in VOICES]
    (OUT/'results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    page='''<!doctype html><meta charset="utf-8"><title>Piper vs Kokoro</title>
<style>body{font:17px system-ui;max-width:1180px;margin:32px auto;padding:20px;background:#161c28;color:#edf2fa}p{line-height:1.5}section{background:#242e40;padding:20px;margin:20px 0;border-radius:12px}audio{width:100%}.voices{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:18px}table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:10px;border-bottom:1px solid #49536a}a{color:#9bd2ff}</style>
<h1>Piper vs Kokoro — CPU comparison</h1>
<p>Three stock Piper voices and two stock Kokoro voices. These are different speakers, not clones of the volunteer. Default voice speed; no pitch effects or XISpeaks-specific text/pause processing. Audio loudness and speaking pace can differ.</p>
<p>Timing is measured offline in separate processes on this machine. Each model is loaded and warmed before three sequential runs per passage. First chunk means synthesized audio becoming available, not actual sound-device latency. Engine chunk sizes differ. Total excludes WAV writing; imports/model initialization and first-call warm-up are separate. CPU only, ONNX Runtime default threads versus four PyTorch threads. No claim of universal performance parity.</p>
<table><tr><th>Voice</th><th>Load/init</th><th>First call</th><th>Warm first chunk*</th><th>Warm total*</th><th>RTF*</th></tr>'''
    for result in results:
        med={key:statistics.median(r['median'][key] for r in result['samples']) for key in ('first_chunk','total','rtf')}
        page+=f"<tr><td>{html.escape(result['engine']+' / '+result['voice'])}</td><td>{result['load_seconds']:.2f}s</td><td>{result['first_call_seconds']:.2f}s</td><td>{med['first_chunk']:.2f}s</td><td>{med['total']:.2f}s</td><td>{med['rtf']:.3f}</td></tr>"
    page+='</table><p>*Median of the three passage medians. RTF = synthesis time / audio duration; below 1 means faster than real time. Lower is faster.</p>'
    for index,text in enumerate(TEXTS):
        page+=f'<section><h2>Dialogue {index+1}</h2><p>{html.escape(text)}</p><div class="voices">'
        for result in results:
            row=result['samples'][index];med=row['median']
            page+=f"<div><h3>{html.escape(result['engine']+' / '+result['voice'])}</h3><audio controls preload=\"none\" src=\"{row['file']}\"></audio><p>First chunk {med['first_chunk']:.2f}s · total {med['total']:.2f}s · audio {med['audio_seconds']:.1f}s</p></div>"
        page+='</div></section>'
    page+='<p><a href="results.json">Full timing measurements</a></p><p>This experiment tests playback only. Custom Piper voice training requires a separate dataset and training checkpoint; a 20-second recording is not a validated training recipe.</p>'
    (OUT/'index.html').write_text(page,encoding='utf-8')
    print('REPORT',OUT/'index.html',flush=True)


if __name__=='__main__':main()
