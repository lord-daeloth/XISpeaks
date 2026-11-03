"""Tiny-data Piper fine-tune: native Windows/CUDA, separate from the companion."""
import hashlib
import html
import inspect
import json
import os
from pathlib import Path
import random
import time

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).parent/'output'
SOURCE=ROOT/'voice_studio/output/bm_halver-e000cbe7/reference.wav'
BASE=ROOT/'build/piper-training/ryan.ckpt'
STAGES=(25,100,300)
TEXTS=[
    'What do you want? Do you have something else to report?',
    'Welcome, adventurer. There is much we have yet to discover beyond these walls.',
    'Are you certain? Then we must leave at once! I shall explain everything along the way.',
]
LINES=[
    'What do you want?', 'Do you have something else to report?',
    "You are within the walls of Chateau d'Oraguille, home of royalty.",
    'Conduct yourself accordingly.',
]
BOUNDS=[(.35,1.85),(2.05,3.70),(4.30,8.20),(8.28,9.75),
        (10.85,12.0),(12.20,13.75),(14.25,17.67),(17.68,19.25)]


def setup_imports():
    import importlib.util
    import sys
    import piper
    spec=importlib.util.spec_from_file_location('piper.config',ROOT/'.reference/piper/src/piper/config.py')
    config=importlib.util.module_from_spec(spec)
    sys.modules['piper.config']=config;spec.loader.exec_module(config)
    piper.config=config
    import piper.train
    # Use current upstream training fixes with the installed Windows phonemizer.
    piper.train.__path__.insert(0,str(ROOT/'.reference/piper/src/piper/train'))


def prepare():
    import numpy as np
    import soundfile as sf
    from scipy.signal import resample_poly
    from math import gcd
    OUT.mkdir(parents=True,exist_ok=False)
    data=OUT/'dataset';data.mkdir()
    audio,sr=sf.read(SOURCE,dtype='float32')
    if audio.ndim!=1:raise ValueError('Expected mono reference')
    if len(audio)/sr<BOUNDS[-1][1]:raise ValueError('Reference is shorter than the reviewed clip boundaries')
    sf.write(OUT/'reference.wav',audio,sr)
    rows=[]
    for i,(start,end) in enumerate(BOUNDS):
        clip=audio[int(start*sr):int(end*sr)]
        g=gcd(sr,22050);clip=resample_poly(clip,22050//g,sr//g)
        if not np.isfinite(clip).all():raise ValueError('Invalid audio')
        sf.write(data/f'{i}.wav',clip,22050)
        rows.append(f'{i}.wav|{LINES[i%4]}')
    (data/'metadata.csv').write_text('\n'.join(rows)+'\n',encoding='utf-8')


def main():
    setup_imports()
    import pathlib
    import numpy as np
    import soundfile as sf
    import torch
    import lightning as L
    from piper.train.vits.lightning import VitsModel
    from piper.train.vits.dataset import VitsDataModule
    from piper.phonemize_espeak import EspeakPhonemizer
    from piper.phoneme_ids import phonemes_to_ids
    if not torch.cuda.is_available():raise RuntimeError('CUDA is required for this bounded training pilot')
    prepare();L.seed_everything(1234,workers=True);torch.set_num_threads(4)
    # Official Linux checkpoint contains PosixPath metadata. Resolve it only
    # while reading this known upstream file; never use this for submitted files.
    old_path=pathlib.PosixPath
    try:
        if os.name=='nt':pathlib.PosixPath=pathlib.WindowsPath
        checkpoint=torch.load(BASE,map_location='cpu',weights_only=False)
    finally:pathlib.PosixPath=old_path
    allowed=set(inspect.signature(VitsModel.__init__).parameters)-{'self','kwargs','dataset'}
    params={k:v for k,v in checkpoint['hyper_parameters'].items() if k in allowed}
    params.update(batch_size=2,learning_rate=1e-5,learning_rate_d=1e-5,lr_decay=1.,lr_decay_d=1.,
                  mos_metric=None,warmstart_ckpt=None,grad_clip=1.)
    model=VitsModel(**params)
    model.load_state_dict(checkpoint['state_dict'],strict=True)
    del checkpoint
    phonemizer=EspeakPhonemizer()
    inputs=[]
    for text in TEXTS:
        sentences=phonemizer.phonemize('en-us',text)
        inputs.append([phonemes_to_ids(p) for p in sentences])
    records=[];started=time.perf_counter()

    def render(module,step):
        was_training=module.training;module.eval()
        with torch.no_grad(),torch.random.fork_rng(devices=[0]):
            torch.manual_seed(777)
            for i,sentences in enumerate(inputs):
                chunks=[]
                for ids in sentences:
                    x=torch.LongTensor(ids).unsqueeze(0).to(module.device)
                    audio=module(x,torch.LongTensor([len(ids)]).to(module.device),[.667,1.,.8]).flatten().cpu().numpy()
                    if not np.isfinite(audio).all() or len(audio)==0:raise RuntimeError('Invalid inference output')
                    chunks.append(audio);chunks.append(np.zeros(int(.2*22050),dtype=np.float32))
                sf.write(OUT/f'step-{step}-{i}.wav',np.concatenate(chunks),22050,subtype='PCM_16')
        if was_training:module.train()
        records.append(dict(batches=step,seconds=time.perf_counter()-started))
        (OUT/'progress.json').write_text(json.dumps(records,indent=2))
        print('RENDERED',step,'batches',flush=True)

    class Samples(L.Callback):
        def __init__(self):self.batches=0
        def on_train_start(self,trainer,module):render(module,0)
        def on_train_batch_end(self,trainer,module,outputs,batch,batch_idx):
            self.batches+=1
            if self.batches%25==0:print('BATCH',self.batches,'seconds',round(time.perf_counter()-started,1),flush=True)
            if self.batches in STAGES:
                render(module,self.batches)
                # Generator-only weights, not a resumable optimizer checkpoint.
                torch.save(dict(model_g={k:v.detach().cpu() for k,v in module.model_g.state_dict().items()},parameters=params),OUT/f'generator-{self.batches}.pt')
            if self.batches>=STAGES[-1]:trainer.should_stop=True
    data=VitsDataModule(csv_path=OUT/'dataset/metadata.csv',audio_dir=OUT/'dataset',cache_dir=OUT/'cache',
        config_path=OUT/'voice-config.json',voice_name='volunteer_test',espeak_voice='en-us',batch_size=2,
        validation_split=0.,num_test_examples=0,num_workers=0,trim_silence=False)
    trainer=L.Trainer(accelerator='gpu',devices=1,precision='32-true',max_epochs=100,
        limit_val_batches=0,num_sanity_val_steps=0,logger=False,enable_checkpointing=False,
        enable_progress_bar=False,callbacks=[Samples()],default_root_dir=OUT)
    trainer.fit(model,datamodule=data)
    summary=dict(base='en_US-ryan-medium',seed=1234,recording_seconds=19.86,unique_sentences=4,
        training_utterances=8,learning_rate=1e-5,batch_size=2,stages=records,
        source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),checkpoint_sha256=hashlib.sha256(BASE.read_bytes()).hexdigest())
    (OUT/'results.json').write_text(json.dumps(summary,indent=2))
    page='''<!doctype html><meta charset="utf-8"><title>Piper volunteer fine-tuning</title>
<style>body{font:18px system-ui;max-width:1150px;margin:35px auto;padding:20px;background:#161c28;color:#eef3fa}section{background:#242e40;padding:20px;margin:20px 0;border-radius:12px}.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:20px}audio{width:100%}p{line-height:1.5}</style>
<h1>Piper likeness experiment</h1><p>American male Ryan medium checkpoint, fine-tuned on the selected 19.86-second reference. Eight clips contain only four unique sentences, each repeated. This is an extremely small-data feasibility test, not a production voice.</p>
<p>Compare identity AND intelligibility on unseen dialogue. No independent recorded validation set exists; no validation-loss claim is made. Identical synthesis settings, random seed and 200 ms sentence gaps across snapshots. No pitch effects.</p><h2>Your reference</h2><audio controls src="reference.wav"></audio>'''
    for i,text in enumerate(TEXTS):
        page+=f'<section><h2>{"Training dialogue" if i==0 else "Unseen dialogue "+str(i)}</h2><p>{html.escape(text)}</p><div class="grid">'
        for step in (0,*STAGES):
            label='Original Ryan' if step==0 else f'After {step} training batches'
            page+=f'<div><h3>{label}</h3><audio controls src="step-{step}-{i}.wav"></audio></div>'
        page+='</div></section>'
    (OUT/'index.html').write_text(page,encoding='utf-8')
    print('COMPLETE',OUT/'index.html',flush=True)


if __name__=='__main__':main()
