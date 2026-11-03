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
    def render(self,key,entry,folder,text,path,cancelled):
        from voice_catalog import playback_models
        self.backend.models=playback_models({key:entry},folder)
        data=b''.join(self.backend.pcm(text,key,cancelled))
        if cancelled():return None
        if not data:raise ValueError('No speech generated')
        with wave.open(str(path),'wb') as output:
            output.setparams((1,2,24000,0,'NONE','not compressed'));output.writeframes(data)
        return measure(data)
