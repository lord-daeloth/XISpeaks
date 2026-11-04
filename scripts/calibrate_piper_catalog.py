"""Calibrate the local Piper catalog against the editor's zero-noise reference."""
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'companion'), str(ROOT / 'voice_editor')]
from audio_effects import process_pcm
from preview import Renderer, measure
from voice_catalog import Store, playback_models

TEXT = 'Welcome, adventurer. There is much we have yet to discover beyond these walls.'


def calibrate(backend, key, entry, folder):
    model = playback_models({key: entry}, folder)[key]
    backend.models = {key: model}
    speed, volume = model['speed'], model['volume']
    model['volume'] = 1
    fraction = int.from_bytes(hashlib.sha256(key.encode()).digest()[:4], 'big') / (2**32 - 1)
    duration_goal = 5.25 + 0.5 * fraction
    level_goal = -15.6 + 1.2 * fraction
    for attempt in range(5):
        model['speed'] = speed
        samples = b''.join(backend.pcm(TEXT, key))
        seconds = len(samples) / 48000
        if 5 <= seconds <= 6 or attempt == 4:
            break
        # The two sentence pauses total 0.6 s regardless of speed.
        updated = round(max(0.5, min(2, speed * (seconds - 0.6) / (duration_goal - 0.6))), 3)
        if updated == speed:
            break
        speed = updated
    for attempt in range(8):
        level = measure(process_pcm(samples, volume=volume))['rms_dbfs']
        if level is None and not any(samples):
            raise ValueError(f'{key} produced silence')
        if level is not None and -16 <= level <= -14 or attempt == 7:
            break
        updated = round(min(3, volume * 10**((level_goal - level)/20)), 4) if level is not None else 1
        if updated == volume:
            break
        volume = updated
    return dict(speed=speed, volume=volume, seconds=seconds, rms_dbfs=level)


def main():
    import onnxruntime
    onnxruntime.set_seed(42)
    store = Store(ROOT / 'piper_voices/catalog.json')
    output = ROOT / 'voice_editor/output'
    output.mkdir(exist_ok=True)
    checkpoint = output / ('calibration-' + store.digest + '.jsonl')
    results = {}
    if checkpoint.exists():
        for line in checkpoint.read_text().splitlines():
            key, result = json.loads(line)
            results[key] = result
    backend = Renderer().backend
    backend.synthesis_options = {'noise_scale': 0., 'noise_w_scale': 0.}
    catalog = copy.deepcopy(store.catalog)
    with checkpoint.open('a') as log:
        for key in sorted(catalog, key=lambda k: catalog[k]['model']):
            if key not in results:
                results[key] = calibrate(backend, key, catalog[key], store.path.parent)
                print(json.dumps([key, results[key]]), file=log, flush=True)
                if len(results) <= 3 or len(results) % 100 == 0:
                    print(len(results), '/', len(catalog), key, results[key], flush=True)
            for field in ('speed', 'volume'):
                catalog[key][field] = results[key][field]
    changed = sum(catalog[k] != store.catalog[k] for k in catalog)
    if changed:
        store.save(catalog)
    exceptions = [k for k,r in results.items() if not 5 <= r['seconds'] <= 6 or r['rms_dbfs'] is None or not -16 <= r['rms_dbfs'] <= -14]
    print(f'Saved {changed} changes; {len(exceptions)} outside target: {exceptions}', flush=True)


if __name__ == '__main__':
    main()
