"""Standalone stutter listening experiment; production code/settings are untouched."""
from pathlib import Path
import html
import json
import os
import re
import sqlite3
import sys
import time
import wave

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / 'output'
LIVE = Path(r'D:\Games\CatsEyeXi\catseyexi-client\Vanacore\addons\ashita\XISpeaks\companion')
os.environ['HF_HUB_CACHE'] = str(LIVE / '_internal/models/hub')
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['NLTK_DATA'] = str(LIVE / '_internal/nltk_data')
sys.path.insert(0, str(ROOT / 'companion'))
from registry import Registry
from service import KokoroBackend, DEFAULTS
from dialogue import Dialogue
from audio_effects import process_pcm

EXAMPLES = ["Wh-what? What's going on?", "Y-yes, I understand.",
    "Th-that cannot be true!", "Th-think about what you are saying.",
    "N-n-no! We cannot leave him behind.", "W-wait! Please, listen to me."]
PATTERN = re.compile(r'\b((?:[A-Za-z]{1,3}-)+)([A-Za-z]+)\b')


def write_wav(path, pcm):
    with wave.open(str(path), 'wb') as output:
        output.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
        output.writeframes(pcm)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    registry = Registry(':memory:', DEFAULTS)
    with sqlite3.connect((LIVE / 'npcs.sqlite3').as_uri() + '?mode=ro', uri=True) as source:
        source.backup(registry.db)
    profile = registry.playback('Zeid')
    registry.close()
    print('Zeid:', profile, flush=True)
    backend = KokoroBackend(DEFAULTS)
    backend.configure(profile['speed'], profile['pitch'], profile['volume'], profile['pitch_engine'])
    backend.engine.set_voice(profile['voice'])
    pipeline = backend.engine._get_pipeline(backend.engine.current_lang)
    original_synthesize = backend.engine.synthesize
    original_play = backend.stream.play_async
    backend.stream.play_async = lambda **kwargs: original_play(muted=True, **kwargs)
    pcm = []
    backend.effects.put = lambda item, *args, **kwargs: pcm.append(process_pcm(
        item, profile['pitch'], profile['volume'], profile['pitch_engine']))
    results = []
    reels = {key: [] for key in ('original', 'phonetic', 'clean')}
    try:
        backend.speak(Dialogue('', 'May your travels be safe.'), profile['voice'], lambda: False)
        for index, text in enumerate(EXAMPLES, 1):
            for mode in reels:
                substitutions = []
                def transform(match):
                    fragments = match[1].rstrip('-').split('-')
                    word = match[2]
                    if not all(word.casefold().startswith(f.casefold()) for f in fragments):
                        return match[0]
                    if mode == 'clean':
                        return word[0].upper()+word[1:] if match[0][0].isupper() else word
                    sounds = pipeline.g2p(word)[0].strip()
                    onset = sounds.lstrip('ˈˌ')[0]
                    # Experimental consonant cases only; no claim of general spelling-to-sound alignment.
                    if onset not in 'wjðθn':
                        raise ValueError(f'Unexpected experimental onset: {word}: {sounds}')
                    pronunciation = ' '.join([onset] * len(fragments) + [sounds])
                    substitutions.append(dict(text=match[0], word_phonemes=sounds, onset=onset, pronunciation=pronunciation))
                    return f'[{match[0]}](/{pronunciation}/)'
                def synthesize(sentence, *args, **kwargs):
                    # Inject AFTER RealtimeTTS's link cleanup, directly before Kokoro G2P.
                    prepared = sentence if mode == 'original' else PATTERN.sub(transform, sentence)
                    return original_synthesize(prepared, *args, **kwargs)
                backend.engine.synthesize = synthesize
                pcm.clear()
                started = time.perf_counter()
                backend.speak(Dialogue('', text), profile['voice'], lambda: False)
                audio = b''.join(pcm)
                assert len(audio) > 24000 and any(audio)
                filename = f'{index:02d}-{mode}.wav'
                write_wav(OUT / filename, audio)
                reels[mode].extend([audio, bytes(24000)])  # Half-second gap between examples.
                result = dict(example=index, text=text, mode=mode, file=filename,
                    audio_seconds=len(audio)/48000, elapsed_seconds=time.perf_counter()-started,
                    substitutions=substitutions)
                results.append(result)
                print(json.dumps(result), flush=True)
    finally:
        backend.close()
    for mode, parts in reels.items():
        write_wav(OUT / f'all-{mode}.wav', b''.join(parts))
    (OUT / 'results.json').write_text(json.dumps(dict(profile=profile, results=results), indent=2), encoding='utf-8')
    labels = dict(original='A: Original spelling', phonetic='B: Pronunciation-based stutter', clean='C: Stutter removed')
    page = '''<!doctype html><meta charset="utf-8"><title>Zeid stutter comparison</title>
<style>body{font:17px system-ui;max-width:1150px;margin:40px auto;padding:20px;background:#151b25;color:#e4edf8}section{background:#222d3d;border-radius:12px;padding:20px;margin:20px 0}.row{display:flex;gap:20px;flex-wrap:wrap}.sample{flex:1;min-width:280px}audio{width:100%}p{line-height:1.5}summary{cursor:pointer}</style>
<h1>Zeid: stutter listening tests</h1><p>Six examples, three treatments. Same voice settings and sentence pauses throughout. App and addon unchanged.</p>'''
    page += '<p>Saved Zeid settings: '+html.escape(str(profile))+'</p><p>B derives the opening sound from the following word, so “that” and “think” get different TH sounds. This is an experiment on clear consonant cases, not a general stutter recognizer. Listen for skipped consonants, spelled letters, and awkward hesitations.</p>'
    page += '<section><h2>All six examples in order</h2><div class="row">'
    for mode, label in labels.items():
        page += f'<div class="sample"><h3>{label}</h3><audio controls preload="none" src="all-{mode}.wav"></audio></div>'
    page += '</div></section>'
    for index, text in enumerate(EXAMPLES, 1):
        page += f'<section><h2>{index}. {html.escape(text)}</h2><div class="row">'
        for row in (r for r in results if r['example'] == index):
            page += f'<div class="sample"><h3>{labels[row["mode"]]}</h3><audio controls preload="none" src="{row["file"]}"></audio></div>'
        page += '</div></section>'
    (OUT / 'index.html').write_text(page, encoding='utf-8')
    print(OUT / 'index.html', flush=True)


if __name__ == '__main__':
    main()
