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
        from piper_backend import PiperBackend
        self.backend=PiperBackend.__new__(PiperBackend)
        self.backend.cache=OrderedDict();self.backend.models={};self.backend.configure(1,0,1)
    def render(self,key,entry,folder,text,path,cancelled,mode="fixed",seed=42):
        from voice_catalog import playback_models
        import onnxruntime
        if mode not in ('fixed','zero'):raise ValueError('Unknown preview noise mode')
        if not isinstance(seed,int) or not 0<=seed<=2147483647:
            raise ValueError('Seed must be an integer from 0 to 2147483647')
        # Random operators own session-local state. Reset the seed BEFORE creating
        # a fresh session; reusing a cached session would advance its random stream.
        self.backend.cache.clear()
        onnxruntime.set_seed(seed if mode=='fixed' else 42)
        self.backend.synthesis_options={'noise_scale':0.0,'noise_w_scale':0.0} if mode=='zero' else {}
        self.backend.models=playback_models({key:entry},folder)
        data=b''.join(self.backend.pcm(text,key,cancelled))
        if cancelled():return None
        if not data:raise ValueError('No speech generated')
        with wave.open(str(path),'wb') as output:
            output.setparams((1,2,24000,0,'NONE','not compressed'));output.writeframes(data)
        return measure(data)
