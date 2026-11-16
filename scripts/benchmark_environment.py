"""Measure post-processing alone, including reset, chunking, and tail generation."""
import sys,time,json,statistics,argparse
from pathlib import Path
import numpy as np
import soundfile as sf
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'companion'))
from environment_effects import Reverb,PRESETS
p=argparse.ArgumentParser();p.add_argument('--sample',type=Path);args=p.parse_args()
out=ROOT/'build/effects';out.mkdir(parents=True,exist_ok=True)
audio=np.random.default_rng(42).normal(0,.06,6*24000).astype(np.float32)
results={}
for preset in PRESETS:
    times=[]
    for repeat in range(31):
        start=time.perf_counter();fx=Reverb(preset)
        for i in range(0,len(audio),1024):fx.process(audio[i:i+1024])
        list(fx.flush())
        if repeat:times.append((time.perf_counter()-start)*1000)
    results[preset]=dict(median_ms=round(statistics.median(times),3),p95_ms=round(sorted(times)[28],3),audio_seconds=6,tail_seconds=PRESETS[preset][1],cpu_percent_of_audio=round(statistics.median(times)/60,3))
if args.sample:
    source,rate=sf.read(args.sample,dtype='float32');assert rate==24000
    for preset in PRESETS:
        fx=Reverb(preset);parts=[fx.process(source)]+list(fx.flush());sf.write(out/(preset+'.wav'),np.clip(np.concatenate(parts),-1,1),rate)
(out/'benchmark.json').write_text(json.dumps(results,indent=2));print(json.dumps(results,indent=2))
