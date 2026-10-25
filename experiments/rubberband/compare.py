"""Standalone listening comparison; never edits or starts the companion/addon."""
from pathlib import Path
import html
import json
import statistics
import subprocess
import sys
import time
import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = HERE / 'output'
EXE = HERE / 'tools/rubberband-4.0.0-gpl-executable-windows/rubberband.exe'
sys.path.insert(0, str(ROOT / 'companion'))
from audio_effects import process_pcm, warm_pitch


def main():
    OUT.mkdir(exist_ok=True)
    if not EXE.exists():
        raise SystemExit('Extract the official Rubber Band 4.0 Windows utility into tools first.')
    start = time.perf_counter()
    warm_pitch()
    warmup = time.perf_counter() - start
    results, sections = [], []
    for voice in ('af_heart', 'am_michael', 'bf_emma'):
        source = ROOT / f'smoke-{voice}.wav'
        audio, rate = sf.read(source, dtype='int16')
        assert rate == 24000 and audio.ndim == 1
        original = OUT / f'{voice}-original.wav'
        sf.write(original, audio, rate, subtype='PCM_16')
        duration = len(audio) / rate
        sections.append(f'<h2>{voice} — {duration:.2f}s source</h2><p>Original</p><audio controls src="{original.name}"></audio>')
        for pitch, label in ((3.5, 'Goblin'), (-1, 'Galka'), (.4, 'Child + Tarutaru')):
            sections.append(f'<h3>{label}: {pitch:+g} semitones</h3><div class="row">')
            reel = [audio.astype(np.float32) / 32768, np.zeros(rate // 2)]
            for method in ('Current librosa', 'Rubber Band R3', 'Rubber Band R3 + formants'):
                slug = {'Current librosa':'librosa', 'Rubber Band R3':'r3', 'Rubber Band R3 + formants':'r3-formants'}[method]
                target = OUT / f'{voice}-{pitch:+g}-{slug}.wav'
                times = []
                for _ in range(4):
                    start = time.perf_counter()
                    if slug == 'librosa':
                        processed = process_pcm(audio.tobytes(), pitch, 1)
                    else:
                        command = [str(EXE), '-q', '-3', '-p', str(pitch)]
                        if slug == 'r3-formants': command.append('-F')
                        subprocess.run(command + [str(source), str(target)], check=True, capture_output=True)
                    times.append(time.perf_counter() - start)
                if slug == 'librosa':
                    sf.write(target, np.frombuffer(processed, dtype='<i2'), rate, subtype='PCM_16')
                samples, sr = sf.read(target, dtype='float32')
                assert sr == rate and np.isfinite(samples).all() and np.max(np.abs(samples)) > .001
                assert abs(len(samples) - len(audio)) <= rate * .05
                # Standardize utility output to browser-friendly PCM16, outside timings.
                sf.write(target, samples, rate, subtype='PCM_16')
                median = statistics.median(times[1:]) * 1000
                result = dict(voice=voice, pitch=pitch, method=method, input_seconds=duration,
                              first_ms=times[0]*1000, median_ms=median, output_seconds=len(samples)/rate)
                results.append(result)
                sections.append(f'<div><b>{method}</b><p>{median:.1f} ms ({median/duration:.1f} ms/audio second)</p><audio controls src="{target.name}"></audio></div>')
                reel += [samples, np.zeros(rate // 2)]
            sections.append('</div>')
            sf.write(OUT / f'{voice}-{pitch:+g}-comparison.wav', np.concatenate(reel), rate, subtype='PCM_16')
    (OUT / 'timings.json').write_text(json.dumps(dict(librosa_warmup_seconds=warmup, results=results), indent=2))
    page = '''<!doctype html><meta charset="utf-8"><title>XISpeaks pitch comparison</title>
<style>body{background:#151922;color:#e8edf6;font:16px system-ui;max-width:1120px;margin:36px auto;padding:24px}h1,h2{color:#9bd6f9}h2{margin-top:48px}.row{display:flex;gap:16px;flex-wrap:wrap}.row>div{background:#242b39;padding:18px;border-radius:10px}audio{width:300px}p{color:#b7c3d5}</style>
<h1>XISpeaks: Rubber Band listening test</h1>
<p>App and addon unchanged. Same source recording, pitch only; speed and volume stay unchanged. Compare warbling on sustained vowels, naturalness, and consonant clarity.</p>
<p>Each row compares the existing algorithm with Rubber Band 4.0 R3, then R3 with formant preservation. Formants preserve vocal character but may not be the best artistic choice for Goblins.</p>
<p>Timings are medians of 3 runs after a first run. Rubber Band includes process launch and WAV file I/O; librosa measures in-memory DSP after warmup. These are offline utility timings, not live playback latency or TTS generation time. No loudness normalization applied.</p>
''' + '\n'.join(sections)
    (OUT / 'index.html').write_text(page, encoding='utf-8')
    print(f'Librosa startup warmup: {warmup:.3f}s')
    for method in ('Current librosa', 'Rubber Band R3', 'Rubber Band R3 + formants'):
        values = [r['median_ms'] for r in results if r['method'] == method]
        print(f'{method}: {min(values):.1f}-{max(values):.1f}ms across samples')
    print(OUT / 'index.html')


if __name__ == '__main__':
    main()
