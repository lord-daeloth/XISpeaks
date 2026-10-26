"""Frozen entry point. Configure offline assets before importing the TTS stack."""
import multiprocessing
import os
import sys

from portable import app_root, resource_root


def prepare():
    root = app_root()
    os.environ['HF_HUB_CACHE'] = str(resource_root() / 'models/hub')
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
    os.environ['NUMBA_CACHE_DIR'] = str(root / 'cache/numba')
    os.environ['NLTK_DATA'] = str(resource_root() / 'nltk_data')


def self_test():
    """Exercise real offline synthesis, both accents, blending and both effects."""
    import socket
    def no_network(*args, **kwargs):
        raise RuntimeError('Self-test forbids network connections')
    socket.socket.connect = no_network
    socket.socket.connect_ex = no_network
    from array import array
    import wave
    from service import KokoroBackend, DEFAULTS
    from dialogue import Dialogue
    from registry import VOICES
    from huggingface_hub import hf_hub_download
    import nltk
    # The verification must not silently fall back to the developer's cache.
    nltk.data.path[:] = [os.environ['NLTK_DATA']]
    for voice in VOICES:
        hf_hub_download('hexgrad/Kokoro-82M', f'voices/{voice}.pt', local_files_only=True)
    backend = KokoroBackend(DEFAULTS)
    try:
        play = backend.stream.play_async
        for engine, voice in [('rubberband', '0.70*bm_george + 0.30*am_michael'), ('librosa', 'af_heart')]:
            output = app_root() / f'self-test-{engine}.wav'
            backend.configure(1.1, 1, 1.5, engine)
            backend.stream.play_async = lambda: play(muted=True, output_wavfile=str(output))
            backend.speak(Dialogue('', "Welcome to Vana'diel. Your voice companion is ready."), voice, lambda: False)
            if any(pipeline.g2p.fallback is None for pipeline in backend.engine.pipelines.values()):
                raise RuntimeError('The bundled eSpeak pronunciation fallback did not load')
            with wave.open(str(output)) as audio:
                samples = array('h', audio.readframes(audio.getnframes()))
                if audio.getsampwidth() != 2 or audio.getnframes() <= audio.getframerate() or max(map(abs, samples), default=0) < 100:
                    raise RuntimeError(f'Invalid audio: {output}')
            print(f'PASS offline {engine}: {output}', flush=True)
    finally:
        backend.close()


if __name__ == '__main__':
    multiprocessing.freeze_support()
    prepare()
    if '--self-test' in sys.argv:
        self_test()
    else:
        from service import main
        main()
