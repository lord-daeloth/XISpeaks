"""Lightweight streaming room effects. Delay state belongs to one utterance."""
import numpy as np
from scipy.signal import lfilter
PRESETS={'dry':(0,0,0),'small_room':(.11,.45,.40),'stone_hall':(.16,1.05,.55),'cave':(.19,1.65,.68),'ethereal':(.22,2.1,.35)}
ZONE_PRESETS={233:'stone_hall',142:'cave',143:'cave',150:'cave',172:'cave',173:'cave',174:'cave',176:'cave',193:'cave',196:'cave',208:'cave',212:'cave',270:'cave',271:'cave'}
class Reverb:
    def __init__(self,preset='dry',strength=1,rate=24000):
        if preset not in PRESETS:raise ValueError('Unknown environment effect')
        self.wet,self.tail,self.damp=PRESETS[preset];self.wet*=max(0,min(1,float(strength)))
        self.rate=rate;self.buffers=[];self.positions=[];self.filters=[];self.gains=[]
        for seconds in (.0297,.0371,.0411,.0437,.0531,.0617):
            delay=max(1,round(seconds*rate*(1.6 if preset=='cave' else 1)))
            self.buffers.append(np.zeros(delay,dtype=np.float32));self.positions.append(0);self.filters.append(np.zeros(1))
            self.gains.append(10**(-3*delay/rate/max(.1,self.tail)))
    def process(self,audio):
        audio=np.asarray(audio,dtype=np.float32)
        if not self.wet:return audio
        wet=np.zeros(len(audio),dtype=np.float32)
        for k,buffer in enumerate(self.buffers):
            pos=self.positions[k];offset=0
            while offset<len(audio):
                n=min(len(buffer)-pos,len(audio)-offset)
                delayed=buffer[pos:pos+n].copy()
                filtered,self.filters[k]=lfilter([1-self.damp],[1,-self.damp],delayed,zi=self.filters[k])
                buffer[pos:pos+n]=audio[offset:offset+n]+filtered*self.gains[k]
                wet[offset:offset+n]+=delayed
                offset+=n;pos=(pos+n)%len(buffer)
            self.positions[k]=pos
        return audio*(1-self.wet)+wet*(self.wet/len(self.buffers))
    def flush(self,cancelled=lambda:False):
        if not self.wet:return
        remaining=round(self.tail*self.rate)
        while remaining and not cancelled():
            n=min(1024,remaining);remaining-=n
            yield self.process(np.zeros(n,dtype=np.float32))
