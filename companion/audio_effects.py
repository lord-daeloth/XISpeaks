"""Process Kokoro's 24 kHz mono PCM before it reaches playback or WAV output."""
from queue import Queue
from pathlib import Path
import os
import subprocess
import tempfile
import wave
import numpy as np
from portable import resource_root


RUBBERBAND = resource_root() / 'tools/rubberband-4.0.0-gpl-executable-windows/rubberband.exe'


def rubberband_pitch(data, pitch):
    if not RUBBERBAND.is_file():
        raise RuntimeError('Rubber Band is missing. Run setup-rubberband.ps1 or select Librosa in /xis voices.')
    with tempfile.TemporaryDirectory(prefix='xispeaks-pitch-') as directory:
        source, target = Path(directory) / 'input.wav', Path(directory) / 'output.wav'
        with wave.open(str(source), 'wb') as wav:
            wav.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
            wav.writeframes(data)
        subprocess.run([str(RUBBERBAND), '-q', '-3', '-p', str(pitch), str(source), str(target)],
                       check=True, capture_output=True, timeout=30,
                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        import soundfile as sf
        audio, rate = sf.read(target, dtype='float32')
        if rate != 24000 or audio.ndim != 1 or not np.isfinite(audio).all():
            raise RuntimeError('Invalid Rubber Band audio output')
        return audio


def process_pcm(data, pitch=0.0, volume=1.0, pitch_engine='librosa'):
    if pitch_engine not in ('librosa', 'rubberband'):
        raise ValueError('Unknown pitch engine')
    if pitch == 0 and volume == 1:
        return data
    audio = np.frombuffer(data, dtype='<i2').astype(np.float32) / 32768.0
    if not len(audio):
        return data
    if pitch:
        if pitch_engine == 'rubberband':
            audio = rubberband_pitch(data, pitch)
        else:
            import librosa
            audio = librosa.effects.pitch_shift(audio, sr=24000, n_steps=pitch)
    audio *= volume
    # Unity below the knee; compress peaks rather than wrap/clip boosted PCM.
    magnitude = np.abs(audio)
    over = magnitude > 0.8
    audio[over] = np.sign(audio[over]) * (0.8 + 0.2 * np.tanh((magnitude[over] - 0.8) / 0.2))
    return np.rint(np.clip(audio, -1, 1) * 32767).astype('<i2').tobytes()


def warm_pitch():
    # Pay librosa/Numba's first-use cost during startup, not an NPC's first line.
    process_pcm(np.zeros(4096, dtype='<i2').tobytes(), pitch=0.5)


class EffectsQueue(Queue):
    def __init__(self):
        super().__init__()
        self.pitch, self.volume = 0.0, 1.0
        self.pitch_engine = 'rubberband'
        self.cancelled = lambda: False
        self.error = None

    def put(self, item, block=True, timeout=None):
        if self.cancelled():
            return
        try:
            item = process_pcm(item, self.pitch, self.volume, self.pitch_engine)
        except Exception as exc:
            self.error = exc
            raise
        if not self.cancelled():
            super().put(item, block, timeout)
