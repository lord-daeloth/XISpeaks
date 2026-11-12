"""Render previews through the companion's exact Piper tuning path."""
from collections import OrderedDict
import math
from pathlib import Path
import wave
import numpy as np


def measure(pcm,rate=24000):
    samples=np.frombuffer(pcm,dtype='<i2').astype(np.float64)/32768
    peak=float(np.max(np.abs(samples))) if samples.size else 0
    rms=float(np.sqrt(np.mean(samples*samples))) if samples.size else 0
    return dict(peak=peak,peak_dbfs=20*math.log10(peak) if peak else None,
        rms_dbfs=20*math.log10(rms) if rms else None,seconds=len(samples)/rate,milliseconds=round(len(samples)*1000/rate))

class Renderer:
    def __init__(self):
        self.backend=None
    def render(self,key,entry,folder,text,path,cancelled,mode="fixed",seed=42):
        import hashlib
        import torch
        from pocket_backend import PocketBackend
        if mode not in ('fixed','zero'):raise ValueError('Unknown preview noise mode')
        if type(seed) is not int or not 0<=seed<=2147483647:raise ValueError('Invalid seed')
        entry=dict(entry,sound_revision=hashlib.sha256((Path(folder)/entry['model']).read_bytes()).hexdigest())
        if self.backend is None:self.backend=PocketBackend({'voice_catalog':{}},voice_folder=folder)
        self.backend.voice_folder=Path(folder)
        self.backend.config['voice_catalog']={key:entry}
        self.backend.configure(1,0,1)
        torch.manual_seed(seed if mode=='fixed' else 42)
        normal_temp=self.backend.model.temp
        try:
            if mode=='zero':self.backend.model.temp=0
            data=b''.join(self.backend.pcm(text,key,cancelled))
        finally:self.backend.model.temp=normal_temp
        if cancelled():return None
        if not data:raise ValueError('No speech generated')
        with wave.open(str(path),'wb') as output:
            output.setparams((1,2,self.backend.rate,0,'NONE','not compressed'));output.writeframes(data)
        return measure(data,self.backend.rate)
