"""Offline A/B using actual playback defaults; live settings are read only."""
from pathlib import Path
import html
import json
import os
import sqlite3
import sys
import time
import wave

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / 'output'
LIVE = Path(r'D:\Games\CatsEyeXi\catseyexi-client\Vanacore\addons\ashita\XISpeaks\companion')
TEXT = "Its layout and features resemble Zi'Tah, of that there can be no doubt. Yet the magic and warmth are gone, like we are in a different world entirely."
os.environ['HF_HUB_CACHE'] = str(LIVE / '_internal/models/hub')
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['NLTK_DATA'] = str(LIVE / '_internal/nltk_data')
sys.path.insert(0, str(ROOT / 'companion'))
from registry import Registry
from service import KokoroBackend, DEFAULTS


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    registry = Registry(':memory:', DEFAULTS)
    with sqlite3.connect((LIVE / 'npcs.sqlite3').as_uri() + '?mode=ro', uri=True) as source:
        source.backup(registry.db)
    profile = registry.playback('Zeid')
    registry.close()
    print('Zeid:', profile, flush=True)
    backend = KokoroBackend(DEFAULTS)
    backend.engine.set_voice(profile['voice'])
    backend.configure(profile['speed'], profile['pitch'], profile['volume'], profile['pitch_engine'])
    # Warm model and effects equally before either measured sample.
    backend.stream.feed('May your travels be safe.').play(muted=True)
    original = backend.engine.synthesize
    results = []
    try:
        for slug, title, options in [
            ('current', 'A: Current fast fragments', {}),
            ('sentences', 'B: Complete sentences', dict(fast_sentence_fragment=False,
                fast_sentence_fragment_allsentences=False,
                fast_sentence_fragment_allsentences_multiple=False,
                force_first_fragment_after_words=100000)),
        ]:
            chunks = []
            pcm = []
            def capture(item, *args, **kwargs):
                from audio_effects import process_pcm
                pcm.append(process_pcm(item, profile['pitch'], profile['volume'], profile['pitch_engine']))
            # Capture the processed PCM directly, avoiding output-device resampling.
            backend.effects.put = capture
            def measured(text, *args, **kwargs):
                start = time.perf_counter()
                result = original(text, *args, **kwargs)
                chunks.append(dict(text=text, seconds=time.perf_counter()-start))
                return result
            backend.engine.synthesize = measured
            target = OUT / (slug + '.wav')
            started = time.perf_counter()
            backend.stream.feed(TEXT).play_async(muted=True, **options)
            while backend.stream.is_playing():
                time.sleep(.02)
            if backend.effects.error or getattr(backend.stream, 'error_flag', False):
                raise RuntimeError('Synthesis failed')
            with wave.open(str(target), 'wb') as audio:
                audio.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
                audio.writeframes(b''.join(pcm))
            with wave.open(str(target)) as audio:
                duration = audio.getnframes()/audio.getframerate()
                assert duration > 1
            row = dict(title=title, file=target.name, chunks=chunks,
                processing_seconds=sum(c['seconds'] for c in chunks),
                elapsed_seconds=time.perf_counter()-started, audio_seconds=duration)
            results.append(row)
            print(json.dumps(row), flush=True)
    finally:
        backend.close()
    (OUT / 'results.json').write_text(json.dumps(dict(text=TEXT, profile=profile, results=results), indent=2))
    page = '<!doctype html><meta charset="utf-8"><title>Zeid pacing comparison</title><style>body{font:18px system-ui;max-width:850px;margin:40px auto;background:#161c26;color:#e7edf5}section{padding:20px;background:#242e3d;margin:20px 0;border-radius:12px}audio{width:100%}li{margin:12px 0}</style><h1>Zeid: speech pacing comparison</h1>'
    page += '<p>' + html.escape(TEXT) + '</p><p>Same live Zeid settings in both: ' + html.escape(str(profile)) + '</p><p>Only sentence fragmentation changes. Warmed model; one run per version. Processing times include pitch effects, exclude model startup, and are not live playback latency. WAVs do not reproduce possible playback buffer stalls.</p>'
    for r in results:
        page += f'<section><h2>{r["title"]}</h2><audio controls src="{r["file"]}"></audio><p>Processing: {r["processing_seconds"]:.2f}s; audio: {r["audio_seconds"]:.2f}s</p><p>Text sent to Kokoro in each call:</p><ol>'
        page += ''.join('<li>'+html.escape(c['text'])+'</li>' for c in r['chunks']) + '</ol></section>'
    (OUT / 'index.html').write_text(page, encoding='utf-8')


if __name__ == '__main__':
    main()
