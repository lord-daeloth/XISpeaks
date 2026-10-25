"""Measure warm DSP cost on an existing smoke WAV; does not play audio."""
from pathlib import Path
import statistics
import sys
import time
import wave

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'companion'))
from audio_effects import process_pcm, warm_pitch

if __name__ == '__main__':
    path = Path(__file__).resolve().parents[1]/'smoke-af_heart.wav'
    started = time.perf_counter()
    warm_pitch()
    print(f'Pitch warmup: {time.perf_counter()-started:.3f}s')
    with wave.open(str(path),'rb') as wav:
        duration = wav.getnframes()/wav.getframerate()
        raw = wav.readframes(wav.getnframes())
    print(f'Input: {duration:.2f}s of recorded Kokoro speech')
    for pitch,volume in [(0,1),(0,2),(1,2),(-1,2)]:
        durations=[]
        for _ in range(8):
            started=time.perf_counter()
            result=process_pcm(raw,pitch,volume)
            durations.append(time.perf_counter()-started)
            assert len(result)==len(raw)
        print(f'Pitch {pitch:+g}, volume {volume:g}: median {statistics.median(durations)*1000:.2f}ms')
