"""CPU listening comparison. Run main using the isolated pocket-env interpreter."""
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

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent/'output'
TEXTS = [
    "Welcome, adventurer. There is much we have yet to discover beyond these walls.",
    "What do you want? Do you have something else to report? You are within the walls of Chateau d'Oraguille, home of royalty. Conduct yourself accordingly.",
    "Its layout and features resemble Zi'Tah, of that there can be no doubt. Yet the magic and warmth are gone, like we are in a different world entirely.",
    "Lion? Lion!? Wh-what? What's going on? Hm... In the future from which I hail, the master faced many threats--not just that one--and came to be known as one of Vana'diel's most storied heroes.",
]
MODELS = ['english','english_18m_2026-10','english_7m_2026-10','english_2m_2026-10']
VOICES = ['alba','marius','charles','cosette']


def worker(engine, name):
    os.environ['HF_HOME'] = str(ROOT/'build/pocket-hf')
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
    import numpy as np
    started = time.perf_counter()
    if engine == 'pocket':
        import torch
        from pocket_tts import TTSModel
        model = TTSModel.load_model(language=name)
        rate = model.sample_rate
        voices = VOICES
        def prepare(voice):
            state = model.get_state_for_audio_prompt(voice)
            def synth(text):
                torch.manual_seed(42)
                for chunk in model.generate_audio_stream(state,text):
                    yield np.rint(np.clip(chunk.detach().cpu().numpy().reshape(-1),-1,1)*32767).astype('<i2').tobytes()
            return synth
        policy = f'CPU PyTorch {torch.__version__}, {torch.get_num_threads()} intra-op thread(s); library streaming'
    else:
        from piper import PiperVoice, SynthesisConfig
        model = PiperVoice.load(ROOT/'piper_voices'/f'{name}.onnx',use_cuda=False)
        rate = model.config.sample_rate
        voices = [name]
        def prepare(voice):
            def synth(text):
                for chunk in model.synthesize(text,syn_config=SynthesisConfig()):
                    yield chunk.audio_int16_bytes
            return synth
        policy = 'CPU ONNX Runtime default threads; native voice speed and noise'
    load = time.perf_counter()-started
    results = []
    for voice in voices:
        start = time.perf_counter()
        synth = prepare(voice)
        prepare_time = time.perf_counter()-start
        start = time.perf_counter()
        list(synth('May your travels be safe, my friend.'))
        first_call = time.perf_counter()-start
        rows = []
        for index,text in enumerate(TEXTS):
            runs = []
            file = f'{engine}-{name}-{voice}-{index}.wav'
            for repeat in range(3):
                start = time.perf_counter()
                first = None
                data = []
                chunks = []
                for pcm in synth(text):
                    now = time.perf_counter()-start
                    if first is None:first=now
                    data.append(pcm)
                    chunks.append((now,len(pcm)/2/rate))
                elapsed = time.perf_counter()-start
                pcm = b''.join(data)
                signal = np.frombuffer(pcm,dtype='<i2').astype(np.float64)/32768
                if signal.size == 0 or max(abs(signal))<.001:raise ValueError('Empty/silent audio')
                duration = signal.size/rate
                # Minimum starting buffer needed to avoid gaps in real-time playback.
                played = 0
                buffer = 0
                for arrived,length in chunks:
                    buffer=max(buffer,arrived-played)
                    played+=length
                runs.append(dict(first_chunk=first,total=elapsed,audio_seconds=duration,rtf=elapsed/duration,buffer_seconds=buffer,peak_dbfs=float(20*np.log10(max(abs(signal)))),rms_dbfs=float(20*np.log10(np.sqrt(np.mean(signal**2))))))
                if repeat==0:
                    with wave.open(str(OUT/file),'wb') as output:
                        output.setparams((1,2,rate,0,'NONE','not compressed'))
                        output.writeframes(pcm)
            rows.append(dict(text=text,file=file,runs=runs,median={k:statistics.median(r[k] for r in runs) for k in runs[0]}))
        results.append(dict(engine=engine,model=name,voice=voice,load_seconds=load,voice_prepare_seconds=prepare_time,first_call_seconds=first_call,policy=policy,samples=rows))
        print(engine,name,voice,'RTF',statistics.median(r['median']['rtf'] for r in rows),flush=True)
    (OUT/f'{engine}-{name}.json').write_text(json.dumps(results,indent=2),encoding='utf8')


def report(results):
    page="""<!doctype html><html><meta charset="utf-8"><title>Pocket TTS vs Piper</title>
<style>body{font:16px system-ui;background:#111b2b;color:#eef4ff;max-width:1400px;margin:32px auto;padding:20px}a{color:#8bd9ff}table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:10px;border-bottom:1px solid #354761}section{background:#1d2b41;padding:20px;margin:20px 0;border-radius:12px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:18px}audio{width:100%}p{line-height:1.5}select{padding:8px} .card{border:1px solid #41516b;padding:12px;border-radius:8px}</style>
<h1>Pocket TTS vs Piper</h1>
<p>CPU-only samples on your AMD Ryzen 7 9800X3D, Windows x64. English stock voices. Raw engine output at native pace, without XISpeaks catalog tuning or pitch effects. The voices are different speakers. Piper Alba and Pocket Alba share the Alba donor, but use different synthesis methods.</p>
<p>Each process loads one model, warms up each voice, then runs each passage three times sequentially. Warm timing excludes file writing and downloads. Load includes imports and cached model initialization. First chunk is software availability, not speaker latency. Buffer time estimates the minimum initial wait to play the measured chunk stream continuously. The model cache is already on disk, so this is not a cold disk benchmark.</p>
<p>Pocket uses its default CPU threading (one PyTorch intra-op thread, plus streaming work), fixed seed 42 and default temperature. Piper uses ONNX Runtime's default CPU threading and normal noise. Library defaults reflect their practical CPU setup rather than identical CPU budgets. RTF = synthesis time/audio length; below 1 is faster than playback. Actual game load will affect results.</p>
<table><tr><th>Model / voice</th><th>Load</th><th>Voice state</th><th>First call</th><th>First chunk*</th><th>Total*</th><th>RTF*</th></tr>"""
    for result in results:
        med={k:statistics.median(s['median'][k] for s in result['samples']) for k in ('first_chunk','total','rtf')}
        title=html.escape(result['model']+' / '+result['voice'])
        page+=f"<tr><td>{title}</td><td>{result['load_seconds']:.2f}s</td><td>{result['voice_prepare_seconds']:.3f}s</td><td>{result['first_call_seconds']:.2f}s</td><td>{med['first_chunk']:.3f}s</td><td>{med['total']:.2f}s</td><td>{med['rtf']:.3f}</td></tr>"
    page+='</table><p>*Median of passage medians. Repeated load values belong to the same model process.</p>'
    sizes=json.loads((OUT/'sizes.json').read_text())
    mb=lambda value:f'{value/1_000_000:,.1f} MB'
    page+='<h2>Package size estimate</h2><p>Measured files from Pocket TTS 4.0.1 and CPU-only PyTorch 2.15.0. These are compressed dependency/model archives, not a built companion EXE. Include one English model plus its 27 built-in voice states. The figures exclude integration code and pitch effects, and include a conservative Python dependency set. Models with different configurations require their own voice states.</p>'
    page+=f'<p>Shared runtime: {mb(sizes["runtime_uncompressed"])} unpacked / {mb(sizes["runtime_zip"])} ZIP. The stock-voice weights were used; cloning-capable model download requires Hugging Face access approval.</p>'
    page+='<table><tr><th>Model</th><th>Weights</th><th>27 voice states</th><th>Total installed estimate</th><th>Total ZIP estimate</th></tr>'
    for model in sizes['models']:
        page+=f'<tr><td>{model["language"]}</td><td>{mb(model["weights"])}</td><td>{mb(model["voices_bytes"])}</td><td>{mb(sizes["runtime_uncompressed"]+model["assets_bytes"])}</td><td>{mb(sizes["runtime_zip"]+model["assets_zip"])}</td></tr>'
    page+='</table><p>These 27 presets are the named stock voices supported by the package, including voices originating in other languages. The broader Kyutai voice-recording collection offers additional prompts for cloning, with mixed licenses; it is not included in these totals. Current XISpeaks Piper has 1,998 speaker entries across 30 models occupying about 2.26 GB of model weights.</p>'

    page+='<label>Show samples for <select id="model-filter"><option value="">All models</option>'
    for model in dict.fromkeys(r['model'] for r in results):
        page+=f'<option value="{html.escape(model)}">{html.escape(model)}</option>'
    page+='</select></label>'
    for i,text in enumerate(TEXTS):
        page+=f'<section><h2>Dialogue {i+1}</h2><p>{html.escape(text)}</p><div class="grid">'
        for result in results:
            row=result['samples'][i];m=row['median']
            page+=f'<div class="card" data-model="{result["model"]}"><b>{html.escape(result["model"]+" / "+result["voice"])}</b><audio controls preload="none" src="{row["file"]}"></audio><p>{m["audio_seconds"]:.1f}s audio · {m["first_chunk"]:.3f}s first chunk · {m["total"]:.2f}s synthesis · {m["buffer_seconds"]:.3f}s buffer<br>RMS {m["rms_dbfs"]:.1f} dBFS</p></div>'
        page+='</div></section>'
    page+='<p><a href="results.json">All runs</a> · <a href="sizes.json">Measured package sizes</a></p><script>document.addEventListener("play",e=>{if(e.target.tagName==="AUDIO")document.querySelectorAll("audio").forEach(a=>{if(a!==e.target)a.pause()})},true)document.getElementById("model-filter").addEventListener("change",e=>document.querySelectorAll(".card").forEach(c=>c.hidden=!!e.target.value&&c.dataset.model!==e.target.value));</script></html>'
    (OUT/'index.html').write_text(page,encoding='utf8')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--worker',nargs=2)
    args=parser.parse_args()
    if args.worker:return worker(*args.worker)
    OUT.mkdir(exist_ok=True)
    configurations=[('piper',v) for v in ['en_US-ryan-high','en_US-lessac-high','en_GB-alba-medium']]+[('pocket',m) for m in MODELS]
    for engine,name in configurations:
        python=ROOT/('build/pocket-env/Scripts/python.exe' if engine=='pocket' else 'build/piper-train-env/Scripts/python.exe')
        destination=OUT/f'{engine}-{name}.json'
        if not destination.exists():
            subprocess.run([python,__file__,'--worker',engine,name],check=True,cwd=ROOT)
    results=sum([json.loads((OUT/f'{e}-{n}.json').read_text()) for e,n in configurations],[])
    (OUT/'results.json').write_text(json.dumps(results,indent=2),encoding='utf8')
    report(results)
    print('Report:',OUT/'index.html',flush=True)


if __name__=='__main__':main()
