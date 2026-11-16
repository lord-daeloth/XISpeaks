"""Compare volunteer likeness with 7M and 18M Pocket models on local audio."""
import argparse
import html
import json
import math
import os
from pathlib import Path
import shutil
import statistics
import time
import wave

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent/'output/likeness'
REFERENCE = ROOT/'experiments/piper_training/output/new-reference.wav'
PIPER = ROOT/'experiments/piper_training/output-new-reference'
LANGUAGES = ['english_7m_2026-10', 'english_18m_2026-10']
SEEDS = [42, 123, 2026]
REVISION = 'db04f0e653473e5c7333c69686ac92b7460b0c1d'
os.environ['HF_HOME'] = str(ROOT/'build/pocket-hf')
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'


def write_audio(path, audio, rate=24000):
    import numpy as np
    with wave.open(str(path),'wb') as output:
        output.setparams((1,2,rate,0,'NONE','not compressed'))
        output.writeframes(np.rint(np.clip(audio,-1,1)*32767).astype('<i2').tobytes())


def prepare():
    import numpy as np
    from scipy.io import wavfile
    from scipy.signal import resample_poly
    metadata=json.loads((PIPER/'dataset.json').read_text())
    training=json.loads((PIPER/'results.json').read_text())
    rate,signal=wavfile.read(REFERENCE)
    original=signal.dtype
    if np.issubdtype(original,np.integer):
        signal=signal.astype(np.float64)/max(abs(np.iinfo(original).min),np.iinfo(original).max)
    else:signal=signal.astype(np.float64)
    if signal.ndim==2:signal=signal.mean(axis=1)
    if not np.isfinite(signal).all() or np.max(np.abs(signal))==0:
        raise ValueError('Reference audio is invalid or silent')
    gain=min(10**(metadata['gain_db']/20),10**(-3/20)/np.max(np.abs(signal)))
    signal*=gain
    signal=resample_poly(signal,24000//math.gcd(rate,24000),rate//math.gcd(rate,24000))
    OUT.mkdir(parents=True,exist_ok=True)
    prompts=[]
    # Full sentence boundaries, with short natural pauses at each end.
    for name,start,end,count in [('short',0.30,13.30,2),('long',0.30,26.65,4)]:
        filename=f'reference-{name}.wav'
        write_audio(OUT/filename,signal[round(start*24000):round(end*24000)])
        prompts.append(dict(name=name,file=filename,seconds=end-start,text=' '.join(s['text'] for s in metadata['segments'][:count])))
    texts=[]
    for index in (12,13):
        segment=metadata['segments'][index]
        filename=f'heldout-{index}.wav'
        write_audio(OUT/filename,signal[round((segment['start']-.12)*24000):round((segment['end']+.12)*24000)])
        texts.append(dict(text=segment['text'],reference=filename,kind='Recorded comparison; excluded from both Pocket prompts'))
    for index in (1,2):
        filename=f'piper-1000-{index}.wav'
        shutil.copyfile(PIPER/f'step-1000-{index}.wav',OUT/filename)
        texts.append(dict(text=training['audition_texts'][index],piper=filename,kind='New dialogue; also available from the previous Piper 1,000-step test'))
    info=dict(source=str(REFERENCE),gain_db=20*math.log10(gain),prompts=prompts,texts=texts,seeds=SEEDS)
    (OUT/'reference-details.json').write_text(json.dumps(info,indent=2),encoding='utf8')
    return info


def render(info, results):
    page="""<!doctype html><meta charset="utf-8"><title>Volunteer likeness: Pocket 7M vs 18M</title>
<style>body{font:17px system-ui;background:#111b2b;color:#edf4ff;max-width:1200px;margin:30px auto;padding:20px}a{color:#8bd6ff}section{padding:20px;background:#203047;margin:20px 0;border-radius:12px}audio{width:100%}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:20px}p{line-height:1.5}table{width:100%;border-collapse:collapse}td,th{text-align:left;border-bottom:1px solid #567;padding:8px}</style>
<h1>Your voice: Pocket 7M vs 18M</h1>
<p>Compare identity, accent, clarity, and emotional delivery. Both models receive the same local recording. Short and long prompts use complete sentences from the improved recording. The comparison lines are excluded from the Pocket prompts. Each generated line has three fixed-seed takes, making consistency audible.</p>
<p>Only fixed gain, mono conversion and 24 kHz resampling are applied to the reference. Outputs have native model volume, pace and pitch. This is reference-conditioned synthesis with no training. Audio and derived voice states stay in this local experiment.</p>
<h2>Voice prompts</h2><div class="grid">"""
    for prompt in info['prompts']:
        page+=f'<div><h3>{prompt["name"].title()} prompt ({prompt["seconds"]:.2f}s)</h3><audio controls src="{prompt["file"]}"></audio><p>{html.escape(prompt["text"])}</p></div>'
    page+='</div>'
    if not results:
        page+='<section><h2>Ready for model access</h2><p>Accept the model terms on Hugging Face, run LOGIN-Pocket-TTS.cmd, then START-Pocket-Likeness.cmd. Generated comparisons will appear here when complete.</p></section>'
    else:
        page+='<h2>Measured performance</h2><table><tr><th>Model / prompt</th><th>Prompt encoding</th><th>Voice state</th><th>First audio*</th><th>RTF*</th></tr>'
        for r in results:
            values=[take for sample in r['samples'] for take in sample['takes']]
            page+=f'<tr><td>{r["model"]} / {r["prompt"]}</td><td>{r["encoding_seconds"]:.2f}s</td><td>{r["state_bytes"]/1e6:.2f} MB</td><td>{statistics.median(v["first_chunk"] for v in values):.3f}s</td><td>{statistics.median(v["rtf"] for v in values):.3f}</td></tr>'
        page+='</table><p>*Warm CPU synthesis. RTF below 1 is faster than playback. Each model and prompt has one warm-up. State files are model-specific.</p>'
    for index,item in enumerate(info['texts']):
        page+=f'<section><h2>Line {index+1}</h2><p>{html.escape(item["text"])}</p><p>{item["kind"]}</p>'
        if 'reference' in item:
            page+=f'<h3>Your actual recording</h3><audio controls src="{item["reference"]}"></audio>'
        if 'piper' in item:
            page+=f'<h3>Previous Piper 1,000-step result</h3><audio controls src="{item["piper"]}"></audio>'
        page+='<div class="grid">'
        for r in results:
            page+=f'<div><h3>{r["model"]} / {r["prompt"]}</h3>'
            for take in r['samples'][index]['takes']:
                page+=f'<p>Seed {take["seed"]} · {take["seconds"]:.1f}s audio</p><audio controls preload="none" src="{take["file"]}"></audio>'
            page+='</div>'
        page+='</div></section>'
    page+='<p>Listen for your vowel sounds and consonants, rather than matching loudness alone. The Piper baselines used the entire recording for training; they are a prior-result comparison, not equal-data conditioning.</p><script>document.addEventListener("play",e=>{if(e.target.tagName==="AUDIO")document.querySelectorAll("audio").forEach(a=>{if(a!==e.target)a.pause()})},true)</script>'
    (OUT/'index.html').write_text(page,encoding='utf8')


def run(info):
    import numpy as np
    import torch
    from huggingface_hub import hf_hub_download
    from huggingface_hub.errors import GatedRepoError
    from pocket_tts import TTSModel, export_model_state
    # Fetch explicitly, so a gated model cannot silently fall back to stock voices.
    for language in LANGUAGES:
        try:
            hf_hub_download('kyutai/pocket-tts',f'languages/{language}/model.safetensors',revision=REVISION)
        except GatedRepoError:
            print('Access is required. Accept https://huggingface.co/kyutai/pocket-tts and run LOGIN-Pocket-TTS.cmd.',flush=True)
            return False
    results=[]
    for language in LANGUAGES:
        started=time.perf_counter()
        model=TTSModel.load_model(language=language)
        load_seconds=time.perf_counter()-started
        if not model.has_voice_cloning:raise RuntimeError('Cloning weights were not loaded')
        for prompt in info['prompts']:
            print('Preparing',language,prompt['name'],flush=True)
            started=time.perf_counter()
            state=model.get_state_for_audio_prompt(OUT/prompt['file'])
            encoding=time.perf_counter()-started
            state_file=OUT/f'{language}-{prompt["name"]}.safetensors'
            export_model_state(state,state_file)
            torch.manual_seed(42)
            list(model.generate_audio_stream(state,'May your travels be safe, my friend.'))
            samples=[]
            for index,item in enumerate(info['texts']):
                takes=[]
                for seed in SEEDS:
                    torch.manual_seed(seed)
                    started=time.perf_counter()
                    chunks=[];first=None
                    for chunk in model.generate_audio_stream(state,item['text']):
                        if first is None:first=time.perf_counter()-started
                        chunks.append(chunk.detach().cpu().numpy().reshape(-1))
                    elapsed=time.perf_counter()-started
                    audio=np.concatenate(chunks)
                    if not np.isfinite(audio).all() or max(abs(audio))<.001:raise RuntimeError('Invalid synthesized audio')
                    filename=f'{language}-{prompt["name"]}-{index}-{seed}.wav'
                    write_audio(OUT/filename,audio,model.sample_rate)
                    seconds=len(audio)/model.sample_rate
                    takes.append(dict(seed=seed,file=filename,first_chunk=first,total=elapsed,seconds=seconds,rtf=elapsed/seconds))
                samples.append(dict(text=item['text'],takes=takes))
                print(language,prompt['name'],'line',index+1,'complete',flush=True)
            results.append(dict(model=language,prompt=prompt['name'],load_seconds=load_seconds,encoding_seconds=encoding,state_bytes=state_file.stat().st_size,samples=samples))
            (OUT/'results.json').write_text(json.dumps(results,indent=2),encoding='utf8')
            render(info,results)
        del model
    return True


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--prepare-only',action='store_true')
    args=parser.parse_args()
    info=prepare()
    previous=OUT/'results.json'
    render(info,json.loads(previous.read_text()) if previous.exists() else [])
    if not args.prepare_only and not run(info):raise SystemExit(1)
    print('Report:',OUT/'index.html',flush=True)


if __name__=='__main__':main()
