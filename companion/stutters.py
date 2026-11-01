"""Conservative stutter pronunciation and short, post-effect audio breaks."""
import re
import numpy as np

PATTERN = re.compile(r'(?<![\w-])((?:[A-Za-z]{1,2}-)+)([A-Za-z]+)(?![\w-])')
DIGRAPHS = {'wh', 'th', 'sh', 'ch', 'ph'}
CONSONANTS = set('bdfghjklmnprstvwzðθʃʒʧʤɹŋ')


def candidate(match):
    fragments = match[1].rstrip('-').lower().split('-')
    word = match[2].lower()
    return all((len(f) == 1 or f in DIGRAPHS) and len(f) < len(word)
               and word.startswith(f) for f in fragments)


def prepare(text, g2p):
    pronunciations = {}
    def replace(match):
        if not candidate(match):
            return match[0]
        word = match[2]
        sounds = g2p(word)[0].strip()
        onset = sounds.lstrip('ˈˌ')[:1]
        if onset not in CONSONANTS:
            return word[0].upper() + word[1:] if match[0][0].isupper() else word
        count = match[1].count('-')
        pronunciation = ' '.join([onset]*count + [sounds])
        pronunciations[pronunciation] = count
        return f'[{match[0]}](/{pronunciation}/)'
    return PATTERN.sub(replace, text), pronunciations


def boundaries(result, pronunciations):
    """Use Kokoro's own frame/leading-offset convention for sound boundaries."""
    if result.pred_dur is None or not result.tokens:
        return []
    durations = result.pred_dur.tolist()
    joined = ''.join((t.phonemes or '') + (' ' if t.whitespace else '') for t in result.tokens)
    if joined.strip() != result.phonemes:
        return []  # Never cut at a guessed position if token alignment changed.
    offset = -(len(joined) - len(joined.lstrip()))
    points = []
    for token in result.tokens:
        sounds = token.phonemes or ''
        for repeat in range(pronunciations.get(sounds, 0)):
            i = offset + repeat*2 + 1  # BOS occupies duration index zero.
            if 0 < i and i+1 < len(durations):
                frame = max(0, durations[0]-3) + sum(durations[1:i+1]) + durations[i+1]/2
                point = round(frame*600)
                if 0 < point < len(result.audio):
                    points.append(point)
        offset += len(sounds) + bool(token.whitespace)
    return sorted(set(points))


def insert_breaks(pcm, points, milliseconds=60):
    audio = np.frombuffer(pcm, dtype='<i2')
    points = sorted(set(p for p in points if 0 < p < len(audio)))
    if not points:
        return pcm
    pieces, cursor = [], 0
    for point in points + [len(audio)]:
        piece = audio[cursor:point].astype(np.float64)
        fade = min(72, len(piece)//2)
        if fade and cursor:
            piece[:fade] *= np.linspace(0, 1, fade)
        if fade and point != len(audio):
            piece[-fade:] *= np.linspace(1, 0, fade)
        pieces.append(piece.astype('<i2').tobytes())
        if point != len(audio):
            pieces.append(bytes(48*milliseconds))
        cursor = point
    return b''.join(pieces)


def install(engine, effects):
    """Adapt the installed RealtimeTTS engine without changing its dependencies."""
    get_pipeline, synthesize = engine._get_pipeline, engine.synthesize

    class Pipeline:
        def __init__(self, original):
            self.original = original

        def __getattr__(self, name):
            return getattr(self.original, name)

        def __call__(self, text, *args, **kwargs):
            prepared, pronunciations = prepare(text, self.original.g2p)
            for result in self.original(prepared, *args, **kwargs):
                effects.stutter_points = boundaries(result, pronunciations) if pronunciations else []
                yield result

    engine._get_pipeline = lambda lang: Pipeline(get_pipeline(lang))

    def speak(text, *args, **kwargs):
        trim = engine.trim_silence
        # Preserve the model timing origin, as in the accepted listening sample.
        if any(candidate(m) for m in PATTERN.finditer(text)):
            engine.trim_silence = False
        try:
            return synthesize(text, *args, **kwargs)
        finally:
            engine.trim_silence = trim
            effects.stutter_points = []
    engine.synthesize = speak
