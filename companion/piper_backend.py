"""Piper-only playback, with bounded model caching and shared audio effects."""
from collections import OrderedDict
from math import gcd
import re
import numpy as np


def speech_parts(text):
    text=re.sub(r'\bhm\b',lambda m:m[0][0]+'mmmm',text,flags=re.I)
    # Keep sentence context. Dash breaks are explicit, separate from sentence ends.
    return re.split(r'\s*(?:--+|\u2014)\s*',text)


BASE_SPEED = 0.9  # UI 100% means 90% of the native Piper pace.


class PiperBackend:
    def __init__(self,config):
        import pyaudio
        self.audio=pyaudio.PyAudio()
        self.stream=None
        self.device=config.get('output_device_index')
        self.models=config['piper_models']
        self.cache=OrderedDict()
        self.configure(1,0,1)

    def configure(self,speed,pitch,volume,pitch_engine='rubberband'):
        self.speed,self.pitch,self.volume,self.pitch_engine=speed,pitch,volume,pitch_engine

    def pcm(self,text,voice,cancelled=lambda:False):
        from piper import PiperVoice, SynthesisConfig
        from scipy.signal import resample_poly
        from audio_effects import process_pcm
        if voice not in self.models:raise ValueError('Unknown Piper voice: '+voice)
        entry=self.models[voice]
        path=entry['path'] if isinstance(entry,dict) else entry
        speaker=entry.get('speaker_id') if isinstance(entry,dict) else None
        cache_key=str(path)
        if cache_key not in self.cache:
            # Keep at most two sessions; hundreds of installed voices need not stay in RAM.
            if len(self.cache)>=2:self.cache.popitem(last=False)
            self.cache[cache_key]=PiperVoice.load(path,use_cuda=False)
        self.cache.move_to_end(cache_key)
        model=self.cache[cache_key]
        parts=speech_parts(text)
        for index,part in enumerate(parts):
            if cancelled():return
            if not part.strip():continue
            pending=None
            for chunk in model.synthesize(part,syn_config=SynthesisConfig(length_scale=1/(self.speed*BASE_SPEED),speaker_id=speaker)):
                if cancelled():return
                if pending is not None:
                    yield pending
                    yield b'\0\0'*7200
                pcm=np.frombuffer(chunk.audio_int16_bytes,dtype='<i2').astype(np.float32)/32768
                if chunk.sample_rate!=24000:
                    divisor=gcd(chunk.sample_rate,24000)
                    pcm=resample_poly(pcm,24000//divisor,chunk.sample_rate//divisor)
                data=np.rint(np.clip(pcm,-1,1)*32767).astype('<i2').tobytes()
                pending=process_pcm(data,self.pitch,self.volume,self.pitch_engine)
            if pending is not None:
                yield pending
                yield b'\0\0'*(4320 if index<len(parts)-1 else 7200)

    def speak(self,dialogue,voice,cancelled):
        import pyaudio
        if self.stream is None:
            self.stream=self.audio.open(format=pyaudio.paInt16,channels=1,rate=24000,output=True,output_device_index=self.device)
        for data in self.pcm(dialogue.text,voice,cancelled):
            for offset in range(0,len(data),2048):
                if cancelled():return
                self.stream.write(data[offset:offset+2048])

    def close(self):
        if self.stream is not None:self.stream.close()
        self.audio.terminate()
        self.cache.clear()
