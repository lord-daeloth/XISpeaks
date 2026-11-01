"""Compare exact pause lengths in the same phonetic-stutter synthesis."""
import html
import json
import sqlite3
import numpy as np
from compare import ROOT, LIVE, EXAMPLES, PATTERN, Registry, DEFAULTS, KokoroBackend, process_pcm, write_wav
from pathlib import Path
from nltk import sent_tokenize

OUT = Path(__file__).resolve().parent / 'output-pauses'


def insert_gaps(audio, boundaries, milliseconds):
    if not milliseconds:
        return audio.copy()
    pieces = []
    cursor = 0
    fade = 72  # 3 ms edge fades prevent clicks at the cuts.
    for point in boundaries + [len(audio)]:
        piece = audio[cursor:point].astype(np.float64)
        if cursor and len(piece) >= fade:
            piece[:fade] *= np.linspace(0, 1, fade)
        if point != len(audio) and len(piece) >= fade:
            piece[-fade:] *= np.linspace(1, 0, fade)
        pieces.append(piece.astype('<i2'))
        if point != len(audio):
            pieces.append(np.zeros(24 * milliseconds, dtype='<i2'))
        cursor = point
    return np.concatenate(pieces)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    registry = Registry(':memory:', DEFAULTS)
    with sqlite3.connect((LIVE / 'npcs.sqlite3').as_uri() + '?mode=ro', uri=True) as source:
        source.backup(registry.db)
    profile = registry.playback('Zeid')
    registry.close()
    backend = KokoroBackend(DEFAULTS)
    backend.engine.set_voice(profile['voice'])
    pipeline = backend.engine._get_pipeline(backend.engine.current_lang)
    voice = profile['voice']
    if '*' in voice:
        voice = backend.engine._parse_mixed_voice_formula(voice, pipeline)
    results = []
    reels = {gap: [] for gap in (0, 60, 100)}
    try:
        for index, text in enumerate(EXAMPLES, 1):
            base, boundaries = [], []
            offset = 0
            for sentence in sent_tokenize(text):
                changes = []
                def replace(match):
                    sounds = pipeline.g2p(match[2])[0].strip()
                    onset = sounds.lstrip('ˈˌ')[0]
                    count = len(match[1].rstrip('-').split('-'))
                    changes.append((onset, count))
                    return f'[{match[0]}](/' + ' '.join([onset]*count + [sounds]) + '/)'
                prepared = PATTERN.sub(replace, sentence)
                for result in pipeline(prepared, voice=voice, speed=profile['speed']):
                    raw = (result.audio.cpu().numpy()*32767).astype('<i2')
                    audio = np.frombuffer(process_pcm(raw.tobytes(), profile['pitch'], profile['volume'], profile['pitch_engine']), dtype='<i2')
                    if changes:
                        onset, count = changes.pop(0)
                        assert result.phonemes.startswith((onset+' ')*count), result.phonemes
                        durations = result.pred_dur.numpy()
                        # Kokoro's own timestamp convention: 600 samples/frame,
                        # with its three-frame leading offset and half-space boundary.
                        for repeat in range(count):
                            phoneme_index = repeat*2+1
                            frame = max(0, int(durations[0])-3) + durations[1:phoneme_index+1].sum() + durations[phoneme_index+1]/2
                            point = round(float(frame)*600*len(audio)/len(raw))
                            assert 0 < point < len(audio)
                            boundaries.append(offset+point)
                    base.append(audio)
                    offset += len(audio)
                assert not changes
                base.append(np.zeros(7200, dtype='<i2'))
                offset += 7200
            combined = np.concatenate(base)
            assert len(boundaries) == (2 if index == 5 else 1)
            for gap in reels:
                samples = insert_gaps(combined, boundaries, gap)
                assert len(samples) == len(combined)+len(boundaries)*24*gap
                filename = f'{index:02d}-gap-{gap}.wav'
                write_wav(OUT / filename, samples.tobytes())
                reels[gap].extend([samples.tobytes(), bytes(24000)])
                results.append(dict(example=index, text=text, gap_ms=gap, file=filename,
                    boundaries_seconds=[b/24000 for b in boundaries], seconds=len(samples)/24000))
            print(f'Generated example {index}: {text}', flush=True)
    finally:
        backend.close()
    for gap, parts in reels.items():
        write_wav(OUT / f'all-gap-{gap}.wav', b''.join(parts))
    (OUT / 'results.json').write_text(json.dumps(dict(profile=profile, results=results), indent=2))
    page = '''<!doctype html><meta charset="utf-8"><title>Stutter pause comparison</title><style>body{background:#151b25;color:#e4edf8;font:17px system-ui;max-width:1150px;margin:40px auto;padding:20px}section{background:#222d3d;padding:20px;margin:20px 0;border-radius:12px}.row{display:flex;gap:20px;flex-wrap:wrap}.sample{flex:1;min-width:280px}audio{width:100%}</style><h1>Stutters with tiny breaks</h1><p>Same phonetic-stutter recording in every column. 60 or 100 ms of silence inserted at Kokoro's estimated sound boundaries, with 3 ms fades to avoid clicks. These are approximate model timings; an awkward cut may need adjustment. No production changes.</p>'''
    page += '<p>Zeid settings: '+html.escape(str(profile))+'</p><section><h2>All six examples</h2><div class="row">'
    for gap in reels:
        page += f'<div class="sample"><h3>{gap} ms added break</h3><audio controls src="all-gap-{gap}.wav"></audio></div>'
    page += '</div></section>'
    for index, text in enumerate(EXAMPLES, 1):
        page += f'<section><h2>{index}. {html.escape(text)}</h2><div class="row">'
        for gap in reels:
            page += f'<div class="sample"><h3>{gap} ms added break</h3><audio controls preload="none" src="{index:02d}-gap-{gap}.wav"></audio></div>'
        page += '</div></section>'
    (OUT / 'index.html').write_text(page, encoding='utf-8')
    print(OUT / 'index.html', flush=True)


if __name__ == '__main__':
    main()
