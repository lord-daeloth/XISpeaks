"""Bounded KVoiceWalk search starting from an Inno pack; local listening report."""
import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
UPSTREAM=ROOT/'.reference/kvoicewalk'
sys.path[:0]=[str(ROOT/'build/kvoicewalk-deps'),str(UPSTREAM)]
os.environ['HF_HUB_CACHE']=str(ROOT/'build/assets/models/hub')
os.environ['HF_HUB_OFFLINE']='1'
os.environ['HF_HUB_DISABLE_TELEMETRY']='1'

import librosa
import numpy as np
import soundfile as sf
import torch
from kokoro import KPipeline
from utilities.fitness_scorer import FitnessScorer
from utilities.kvoicewalk import KVoiceWalk
from utilities.voice_generator import VoiceGenerator

OTHER='The messenger arrived before dawn. Nobody expected the gates to be open so early.'
HELDOUT=[
    'Welcome, adventurer. There is much we have yet to discover beyond these walls.',
    'Are you certain? Then we must leave at once! I shall explain everything along the way.',
]


class StableScorer(FitnessScorer):
    def extract_features(self,audio,sr=24000):
        # Current librosa returns a one-element tempo array; upstream assumes a
        # scalar. This experiment is single-threaded; restore after extraction.
        original=librosa.beat.beat_track
        def compatible(*args,**kwargs):
            tempo,beats=original(*args,**kwargs)
            return float(np.asarray(tempo).reshape(-1)[0]),beats
        librosa.beat.beat_track=compatible
        try:return super().extract_features(audio,sr)
        finally:librosa.beat.beat_track=original

    def target_feature_penalty(self,features):
        # Upstream divides by zero for e.g. constant beat intervals. Protect both
        # zero and near-zero denominators; retain its relative-error scoring.
        return sum(abs(value-self.target_features[key])/max(abs(self.target_features[key]),1e-6)
                   for key,value in features.items())


class Generator:
    def __init__(self,lang,device):
        self.pipeline=KPipeline(lang_code=lang,repo_id='hexgrad/Kokoro-82M',device=device)

    def generate_audio(self,text,voice):
        chunks=[r.audio.detach().cpu().numpy() for r in self.pipeline(text,voice=voice.detach().cpu().float(),speed=1) if r.audio is not None]
        audio=np.concatenate(chunks)
        if not np.isfinite(audio).all() or len(audio)<2400:raise ValueError('Invalid generated audio')
        return audio


def metrics(result):
    return {key:float(result[key]) for key in ('score','target_similarity','self_similarity','feature_similarity') if key in result}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack',required=True,type=Path)
    parser.add_argument('--reference',required=True,type=Path)
    parser.add_argument('--transcript',required=True,type=Path)
    parser.add_argument('--steps',type=int,default=100)
    parser.add_argument('--seed',type=int,default=41)
    parser.add_argument('--output',type=Path,default=Path(__file__).parent/'output')
    parser.add_argument('--device',choices=['cpu','cuda'],default='cpu')
    args=parser.parse_args()
    if not 1<=args.steps<=10000:parser.error('Steps must be 1–10000')
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    random.seed(args.seed);np.random.seed(args.seed);torch.manual_seed(args.seed)
    torch.set_num_threads(4)
    text=args.transcript.read_text(encoding='utf-8-sig').strip()
    if not text:raise ValueError('Transcript is empty')
    original=torch.load(args.pack,map_location='cpu',weights_only=True)
    if tuple(original.shape)!=(510,1,256) or not torch.isfinite(original).all():raise ValueError('Invalid starting pack')
    reference,sr=sf.read(args.reference,dtype='float32',always_2d=True)
    reference=librosa.resample(reference.mean(axis=1),orig_sr=sr,target_sr=24000)
    sf.write(out/'reference.wav',reference,24000)
    generator=Generator('b' if args.pack.stem.startswith('b') else 'a',args.device)
    scorer=StableScorer(str(out/'reference.wav'),device=args.device)
    walk=KVoiceWalk.__new__(KVoiceWalk)
    walk.target_text=text;walk.other_text=OTHER;walk.speech_generator=generator;walk.fitness_scorer=scorer
    # Use the same mutation implementation as upstream, seeded with stock English
    # tensors plus Inno. No long interpolation search is performed in this pilot.
    voices=list((ROOT/'build/assets/models/hub/models--hexgrad--Kokoro-82M/snapshots').glob('*/voices/[ab][fm]_*.pt'))
    population=[torch.load(path,map_location='cpu',weights_only=True) for path in voices]
    mutation=VoiceGenerator(population+[original],None,device=args.device)
    best=original;initial=walk.score_voice(original);best_result=initial
    if not np.isfinite(initial['score']):raise ValueError('Nonfinite initial score')
    sf.write(out/'inno-training.wav',initial['audio'],24000)
    started=time.perf_counter();history=[]
    print('INITIAL',metrics(initial),flush=True)
    for step in range(1,args.steps+1):
        candidate=mutation.generate_voice(best,random.uniform(.01,.15),device=args.device)
        result=walk.score_voice(candidate,best_result['target_similarity']*.98)
        if np.isfinite(result['score']) and result['score']>best_result['score']:
            best=candidate;best_result=result
            history.append(dict(step=step,**metrics(result)))
            torch.save(best.detach().cpu(),out/'bm_optimized.pt')
            print('IMPROVED',history[-1],flush=True)
        if step%10==0:print('PROGRESS',step,'seconds',round(time.perf_counter()-started,1),flush=True)
    torch.save(best.detach().cpu(),out/'bm_optimized.pt')
    sf.write(out/'optimized-training.wav',best_result['audio'],24000)
    comparisons=[]
    for i,sentence in enumerate(HELDOUT):
        row=dict(text=sentence)
        for label,pack in [('inno',original),('optimized',best)]:
            audio=generator.generate_audio(sentence,pack)
            sf.write(out/f'{label}-{i}.wav',audio,24000)
            row[label+'_similarity']=float(scorer.target_similarity(audio))
        comparisons.append(row)
    summary=dict(steps=args.steps,seed=args.seed,device=args.device,seconds=time.perf_counter()-started,
        upstream_commit=subprocess.check_output(['git','-C',str(UPSTREAM),'rev-parse','HEAD'],text=True).strip(),
        source_pack_sha256=hashlib.sha256(args.pack.read_bytes()).hexdigest(),
        initial=metrics(initial),final=metrics(best_result),improvements=history,heldout=comparisons)
    (out/'results.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    page='''<!doctype html><meta charset="utf-8"><title>Halver: Inno vs KVoiceWalk</title>
<style>body{font:18px system-ui;background:#151b26;color:#ecf0f8;max-width:1000px;margin:40px auto;padding:20px}section{background:#242e3f;padding:20px;margin:18px 0;border-radius:12px}.pair{display:grid;grid-template-columns:1fr 1fr;gap:20px}audio{width:100%}p{line-height:1.5}a{color:#a4caff}</style>
<h1>Halver: Inno vs KVoiceWalk</h1><p>Local experiment using the selected 19.86-second recording. No pitch effects; equal synthesis speed. Listen for identity, naturalness, and consistency. Similarity scores are optimization metrics, not percentages of likeness.</p>
<h2>Volunteer reference</h2><audio controls src="reference.wav"></audio>'''
    page+=f'<p>{args.steps} search steps; {summary["seconds"]:.0f} seconds. Hybrid score: {initial["score"]:.2f} → {best_result["score"]:.2f}. This bounded pilot is not a fully converged search.</p>'
    scores=', '.join(f"{r['inno_similarity']:.3f} → {r['optimized_similarity']:.3f}" for r in comparisons)
    page+='<p>Held-out speaker similarity (A → B): '+scores+'. Improvement on the search dialogue alone does not demonstrate a better voice on new dialogue.</p>'
    for i,row in enumerate(comparisons):
        page+='<section><h2>Unseen dialogue '+str(i+1)+'</h2><p>'+html.escape(row['text'])+'</p><div class="pair">'
        for label,title in [('inno','A — Original Inno'),('optimized','B — Inno + KVoiceWalk')]:
            page+=f'<div><h3>{title}</h3><audio controls src="{label}-{i}.wav"></audio></div>'
        page+='</div></section>'
    page+='<details><summary>Search dialogue (used for optimization)</summary><p>'+html.escape(text)+'</p><p>A — Inno</p><audio controls src="inno-training.wav"></audio><p>B — Optimized</p><audio controls src="optimized-training.wav"></audio></details><p><a href="results.json">Metrics and reproducibility details</a></p>'
    (out/'index.html').write_text(page,encoding='utf-8')
    print('COMPLETE',out/'index.html',flush=True)


if __name__=='__main__':main()
