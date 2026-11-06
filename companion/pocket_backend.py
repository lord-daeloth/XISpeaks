"""CPU Pocket 18M playback and whole-line pitch/tempo effects."""
from collections import OrderedDict
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import wave
import numpy as np
from pocket_paths import ASSETS, MODEL, VOICES


class PocketBackend:
    def __init__(self, config):
        os.environ['HF_HOME'] = str(ASSETS/'build/pocket-hf')
        os.environ['HF_HUB_OFFLINE'] = '1'
        os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
        from pocket_tts import TTSModel
        import pyaudio
        self.model = TTSModel.load_model(language=MODEL)
        if not self.model.has_voice_cloning:
            raise RuntimeError('Pocket 18M cloning weights are required for the volunteer voice.')
        self.config = config
        self.states = OrderedDict()
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.rate = self.model.sample_rate
        self.configure(1, 0, 1)

    def configure(self, speed, pitch, volume, pitch_engine='rubberband'):
        self.speed = speed
        self.pitch = pitch
        self.volume = volume
        self.pitch_engine = pitch_engine

    def generate(self, text, voice, cancelled=lambda:False):
        entry = self.config['voice_catalog'][voice]
        signature = (entry['model'], entry['sound_revision'])
        if signature not in self.states:
            state = self.model.get_state_for_audio_prompt(VOICES/entry['model'])
            self.states[signature] = state
            if len(self.states)>8:
                self.states.popitem(last=False)
        self.states.move_to_end(signature)
        stop = threading.Event()
        stream = self.model.generate_audio_stream(self.states[signature],text,stop=stop)
        try:
            for chunk in stream:
                if cancelled():
                    break
                yield chunk.detach().cpu().numpy().reshape(-1)
        finally:
            stop.set()
            stream.close()

    def transform(self, audio, speed, pitch, engine, cancelled):
        if cancelled():return np.empty(0,dtype=np.float32)
        if engine == 'librosa':
            import librosa
            if speed != 1:audio=librosa.effects.time_stretch(audio,rate=speed)
            if pitch:audio=librosa.effects.pitch_shift(audio,sr=self.rate,n_steps=pitch)
            return audio
        executable=ASSETS/'tools/rubberband-4.0.0-gpl-executable-windows/rubberband.exe'
        with tempfile.TemporaryDirectory(prefix='xispeaks-pocket-') as folder:
            source=Path(folder)/'in.wav';target=Path(folder)/'out.wav'
            with wave.open(str(source),'wb') as wav:
                wav.setparams((1,2,self.rate,0,'NONE','not compressed'))
                wav.writeframes(np.rint(np.clip(audio,-1,1)*32767).astype('<i2').tobytes())
            with tempfile.TemporaryFile() as errors:
                process=subprocess.Popen([str(executable),'-q','-3','-T',str(speed),'-p',str(pitch),str(source),str(target)],
                    stdout=subprocess.DEVNULL,stderr=errors,creationflags=subprocess.CREATE_NO_WINDOW)
                try:
                    while True:
                        if cancelled():
                            process.terminate();process.wait()
                            return np.empty(0,dtype=np.float32)
                        try:
                            code=process.wait(timeout=.05)
                            break
                        except subprocess.TimeoutExpired:pass
                    if code:
                        errors.seek(0)
                        raise RuntimeError(errors.read().decode(errors='replace')[-300:])
                finally:
                    if process.poll() is None:process.kill();process.wait()
            with wave.open(str(target)) as wav:
                if wav.getframerate()!=self.rate or wav.getnchannels()!=1 or wav.getsampwidth()!=2:
                    raise RuntimeError('Unexpected Rubber Band audio format')
                return np.frombuffer(wav.readframes(wav.getnframes()),dtype='<i2').astype(np.float32)/32768

    def pcm(self,text,voice,cancelled=lambda:False):
        from audio_effects import process_pcm
        entry=self.config['voice_catalog'][voice]
        speed=self.speed*entry['speed']
        volume=self.volume*entry['volume']
        if speed != 1 or self.pitch:
            chunks=list(self.generate(text,voice,cancelled))
            if cancelled() or not chunks:return
            audio=self.transform(np.concatenate(chunks),speed,self.pitch,self.pitch_engine,cancelled)
            chunks=(audio,)
        else:
            chunks=self.generate(text,voice,cancelled)
        try:
            for audio in chunks:
                if cancelled():return
                data=np.rint(np.clip(audio,-1,1)*32767).astype('<i2').tobytes()
                yield process_pcm(data,volume=volume)
        finally:
            if hasattr(chunks,'close'):chunks.close()

    def speak(self,dialogue,voice,cancelled):
        import pyaudio
        if self.stream is None:
            self.stream=self.audio.open(format=pyaudio.paInt16,channels=1,rate=self.rate,output=True,
                output_device_index=self.config.get('output_device_index'))
        for data in self.pcm(dialogue.text,voice,cancelled):
            for offset in range(0,len(data),2048):
                if cancelled():return
                self.stream.write(data[offset:offset+2048])

    def close(self):
        if self.stream is not None:self.stream.close()
        self.audio.terminate()
        self.states.clear()
