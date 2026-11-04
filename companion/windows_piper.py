"""Portable Windows entry point for XISpeaks."""
import multiprocessing
import os
import sys
from pathlib import Path
from collections import OrderedDict
from paths import ROOT
from voice_install import prepare_voices


def main():
    os.environ['NUMBA_CACHE_DIR'] = str(ROOT / 'piper-runtime/cache')
    if '--self-test' in sys.argv:
        from piper_backend import PiperBackend
        from audio_effects import process_pcm
        from registry import choose_tuning
        backend = PiperBackend.__new__(PiperBackend)
        backend.cache = OrderedDict()
        backend.models = {'sample': dict(path=ROOT/'piper_voices/en_US-libritts-high.onnx', speaker_id=0)}
        backend.configure(1, 0, 1)
        pcm = b''.join(backend.pcm('Welcome, adventurer.', 'sample'))
        if len(pcm) < 24000 or not any(pcm):
            raise RuntimeError('No speech generated')
        for engine in ('rubberband', 'librosa'):
            audio = process_pcm(pcm, -2.5, 1, engine)
            if not any(audio):
                raise RuntimeError('Pitch effect produced silence')
        print('PASS: Piper speech and both pitch engines', flush=True)
        return
    prepare_voices(ROOT)
    from piper_service import main as serve
    serve()


if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()
