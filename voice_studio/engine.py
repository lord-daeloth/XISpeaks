"""Local voice-pack creation; independent of the maintainer and live registry."""
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'voice_studio/output'
sys.path.insert(0,str(ROOT/'build/voice-studio-deps'))
os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
os.environ['DO_NOT_TRACK']='1'
if (ROOT/'build/assets/models/hub').is_dir():
    os.environ.setdefault('HF_HUB_CACHE',str(ROOT/'build/assets/models/hub'))


def voice_id(value):
    if not re.fullmatch(r'(?:af|am|bf|bm)_[a-z0-9][a-z0-9_]{0,59}',value):
        raise ValueError('Use af_, am_, bf_, or bm_ followed by lowercase letters, numbers and underscores (for example bm_halver).')
    return value


def recording_script(npc, dialogue):
    if not npc.strip() or not dialogue.strip():raise ValueError('Enter an NPC name and recording dialogue.')
    return f'''Recording script: {npc.strip()}

Record several separate 5–30 second takes in a quiet room, with one speaker,
no music or effects, and a consistent character voice. Leave natural pauses.
Save as WAV or FLAC. Only submit your own voice or recordings you have permission
to use for voice synthesis. Agree on credit and distribution permission before
publishing a resulting pack.

The dialogue below was supplied by the project organizer; verify the speaker.

{dialogue.strip()}

Keep some additional dialogue unrecorded for testing the generated voice.
'''


class Engine:
    def __init__(self):
        self.tuner=None;self.pipelines={}

    def generate(self, source, identifier, npc, credit, start=0, duration=30):
        import numpy as np
        import soundfile as sf
        import torch
        from inno_kokoro.enroll import Tuner, enroll, fetch_weights
        voice_id(identifier)
        start=float(start);duration=float(duration)
        if not np.isfinite([start,duration]).all() or start<0 or not 3<=duration<=30:
            raise ValueError('Start must be nonnegative and duration must be 3–30 seconds.')
        with sf.SoundFile(source) as f:
            sr=f.samplerate
            if start>=len(f)/sr:raise ValueError('Start is beyond the recording.')
            f.seek(int(start*sr));audio=f.read(int(duration*sr),dtype='float32',always_2d=True).mean(axis=1)
        if len(audio)/sr<3:raise ValueError('At least 3 seconds of recording are needed after the selected start.')
        if not np.isfinite(audio).all() or np.sqrt(np.mean(audio**2))<.0001:
            raise ValueError('Recording is silent or contains invalid samples.')
        if self.tuner is None:
            self.tuner=Tuner(fetch_weights(str(ROOT/'build/voice-studio-model')),device='cpu')
        pack,weights=enroll(torch.from_numpy(audio),sr,self.tuner)
        if tuple(pack.shape)!=(510,1,256) or not torch.isfinite(pack).all():raise ValueError('Invalid generated voice pack.')
        folder=OUTPUT/(identifier+'-'+uuid.uuid4().hex[:8]);folder.mkdir(parents=True)
        target=folder/(identifier+'.pt')
        torch.save(pack.cpu(),target)
        sf.write(folder/'reference.wav',audio,sr,subtype='PCM_16')
        metadata=dict(schema=1,voice_id=identifier,npc=npc,credit=credit,tool='inno-kokoro',version='0.2.0',
            reference_start=start,reference_seconds=len(audio)/sr,prosody_weights=weights,
            sha256=hashlib.sha256(target.read_bytes()).hexdigest(),status='candidate')
        (folder/'profile.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')
        return target

    def render(self, path, text, speed=1.0):
        import numpy as np
        import soundfile as sf
        import torch
        from kokoro import KPipeline
        path=Path(path)
        if not text.strip() or len(text)>2000:raise ValueError('Enter 1–2,000 characters of audition text.')
        speed=float(speed)
        if not np.isfinite(speed) or not .7<=speed<=1.3:raise ValueError('Speed must be 0.7–1.3.')
        pack=torch.load(path,map_location='cpu',weights_only=True)
        if not isinstance(pack,torch.Tensor) or tuple(pack.shape)!=(510,1,256) or not torch.isfinite(pack).all():
            raise ValueError('Expected a finite Kokoro voice tensor with shape [510, 1, 256].')
        lang='b' if path.stem.startswith('b') else 'a'
        if lang not in self.pipelines:self.pipelines[lang]=KPipeline(lang_code=lang,repo_id='hexgrad/Kokoro-82M')
        chunks=[result.audio.cpu().numpy() for result in self.pipelines[lang](text,voice=pack,speed=speed) if result.audio is not None]
        if not chunks:raise ValueError('No speech was generated.')
        folder=OUTPUT/('audition-'+uuid.uuid4().hex[:8]);folder.mkdir(parents=True)
        target=folder/'preview.wav'
        sf.write(target,np.concatenate(chunks),24000,subtype='PCM_16')
        (folder/'preview.json').write_text(json.dumps(dict(voice_file=str(path),text=text,speed=speed),indent=2),encoding='utf-8')
        return target
