"""Listening tests only: humming and laughter; live settings are read-only."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'stutters'))
from compare import LIVE, Registry, DEFAULTS, KokoroBackend, Dialogue, process_pcm, write_wav
import html
import json
import sqlite3
import time

OUT = Path(__file__).resolve().parent / 'output'
LABELS = ['Original', 'Normalized spelling', 'Explicit sounds', 'Alternate sounds / rhythm']
CASES = [
    ('Hm. I see.', [
        ('Hm. I see.', {}),
        ('Hmm. I see.', {}),
        ('Xishum. I see.', {'Xishum': '[Hmm](/mː/)'}),
        ('Xishum. I see.', {'Xishum': '[Hmm](/hmː/)'})]),
    ('Hmmmm... Something is wrong.', [
        ('Hmmmm... Something is wrong.', {}),
        ('Hmm... Something is wrong.', {}),
        ('Xishum... Something is wrong.', {'Xishum': '[Hmm](/mː/)'}),
        ('Xishum... Something is wrong.', {'Xishum': '[Hmm](/hmː/)'})]),
    ('Ha ha ha ha! That was a good one.', [
        ('Ha ha ha ha! That was a good one.', {}),
        ('Ha, ha, ha, ha! That was a good one.', {}),
        ('Xislaughter! That was a good one.', {'Xislaughter': '[Ha ha ha ha](/hˈɑ hˈɑ hˈɑ hˈɑ/)'}),
        ('Xisha [xis_laugh] Xisha [xis_laugh] Xisha [xis_laugh] Xisha! That was a good one.',
            {'Xisha': '[Ha](/hˈɑ/)'})]),
]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    registry = Registry(':memory:', DEFAULTS)
    with sqlite3.connect((LIVE/'npcs.sqlite3').as_uri()+'?mode=ro', uri=True) as source:
        source.backup(registry.db)
    profile = registry.playback('Zeid')
    registry.close()
    backend = KokoroBackend(DEFAULTS)
    backend.configure(profile['speed'], profile['pitch'], profile['volume'], profile['pitch_engine'])
    backend.engine.set_voice(profile['voice'])
    pipeline = backend.engine._get_pipeline(backend.engine.current_lang)
    backend.stream.add_pause('xis_laugh', .08)
    play = backend.stream.play_async
    backend.stream.play_async = lambda **kwargs: play(muted=True, **kwargs)
    synthesize = backend.engine.synthesize
    pcm = []
    backend.effects.put = lambda item, *args, **kwargs: pcm.append(process_pcm(
        item, profile['pitch'], profile['volume'], profile['pitch_engine']))
    results, reels = [], {i: [] for i in range(4)}
    diagnostics = {s: pipeline.g2p(s)[0] for s in ['Hm', 'Hmm', 'Hmmmm', 'ha ha ha ha', 'Ha, ha, ha, ha!']}
    try:
        backend.speak(Dialogue('', 'May your travels be safe.'), profile['voice'], lambda: False)
        for index, (original, variants) in enumerate(CASES, 1):
            for number, (text, replacements) in enumerate(variants):
                synthesized = []
                def render(sentence, *args, **kwargs):
                    for marker, markup in replacements.items():
                        sentence = sentence.replace(marker, markup)
                    synthesized.append(dict(text=sentence, phonemes=pipeline.g2p(sentence)[0]))
                    return synthesize(sentence, *args, **kwargs)
                backend.engine.synthesize = render
                pcm.clear()
                start = time.perf_counter()
                backend.speak(Dialogue('', text), profile['voice'], lambda: False)
                data = b''.join(pcm)
                assert len(data)>24000 and any(data)
                filename = f'{index:02d}-{number}.wav'
                write_wav(OUT/filename, data)
                reels[number].extend([data, bytes(24000)])
                results.append(dict(example=index, variant=number, file=filename, text=original,
                    synthesized=synthesized, audio_seconds=len(data)/48000, elapsed_seconds=time.perf_counter()-start))
                print(f'Generated {index}, {LABELS[number]}', flush=True)
    finally:
        backend.close()
    for number, parts in reels.items():
        write_wav(OUT/f'all-{number}.wav', b''.join(parts))
    (OUT/'results.json').write_text(json.dumps(dict(profile=profile, diagnostics=diagnostics, results=results), indent=2), encoding='utf-8')
    page = '''<!doctype html><meta charset="utf-8"><title>Hums and laughter</title><style>body{background:#151b25;color:#e4edf8;font:17px system-ui;max-width:1350px;margin:40px auto;padding:20px}section{background:#222d3d;padding:20px;margin:20px 0;border-radius:12px}.row{display:flex;gap:18px;flex-wrap:wrap}.sample{flex:1;min-width:260px}audio{width:100%}</style><h1>Hums and laughter: listening tests</h1><p>Same saved Zeid voice and tuning throughout. No changes to the app or addon. Laughter may still sound spoken; these tests compare pronunciation and timing, not an expressive laughter model.</p>'''
    page += '<p>'+html.escape(str(profile))+'</p><p>For humming: C uses a sustained M sound; D adds an H onset. For laughter: C uses explicit “hah” sounds together; D synthesizes each “hah” separately with 80 ms breaks.</p><section><h2>All three examples</h2><div class="row">'
    for number, label in enumerate(LABELS):
        page += f'<div class="sample"><h3>{chr(65+number)}: {label}</h3><audio controls src="all-{number}.wav"></audio></div>'
    page += '</div></section>'
    for index, (text, _) in enumerate(CASES, 1):
        page += f'<section><h2>{html.escape(text)}</h2><div class="row">'
        for number, label in enumerate(LABELS):
            page += f'<div class="sample"><h3>{chr(65+number)}: {label}</h3><audio controls preload="none" src="{index:02d}-{number}.wav"></audio></div>'
        page += '</div></section>'
    (OUT/'index.html').write_text(page, encoding='utf-8')
    print(OUT/'index.html', flush=True)


if __name__ == '__main__':
    main()
