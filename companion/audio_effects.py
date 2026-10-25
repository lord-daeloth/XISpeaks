"""Process Kokoro's 24 kHz mono PCM before it reaches playback or WAV output."""
from queue import Queue
import numpy as np


def process_pcm(data, pitch=0.0, volume=1.0):
    if pitch == 0 and volume == 1:
        return data
    audio = np.frombuffer(data, dtype='<i2').astype(np.float32) / 32768.0
    if not len(audio):
        return data
    if pitch:
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
        self.cancelled = lambda: False
        self.error = None

    def put(self, item, block=True, timeout=None):
        if self.cancelled():
            return
        try:
            item = process_pcm(item, self.pitch, self.volume)
        except Exception as exc:
            self.error = exc
            raise
        if not self.cancelled():
            super().put(item, block, timeout)
