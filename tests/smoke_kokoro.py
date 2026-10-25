"""Optional real-model test: writes a short WAV without playing through speakers."""
from array import array
import argparse
from pathlib import Path
import sys
import wave
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'companion'))
from service import KokoroBackend, DEFAULTS
from dialogue import Dialogue


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--voices', nargs='+', default=['af_heart'])
    args = parser.parse_args()
    backend = KokoroBackend(DEFAULTS)
    try:
        play_async = backend.stream.play_async
        for voice in args.voices:
            if not voice.replace('_', '').isalnum():
                raise ValueError('Expected a simple voice ID')
            output = Path(__file__).resolve().parents[1] / f'smoke-{voice}.wav'
            with patch.object(backend.stream, 'play_async', side_effect=lambda: play_async(muted=True, output_wavfile=str(output))):
                backend.speak(Dialogue('', "Welcome to Vana'diel. Your voice companion is ready."), voice, lambda: False)
            with wave.open(str(output), 'rb') as audio:
                samples = array('h', audio.readframes(audio.getnframes()))
                assert audio.getsampwidth() == 2, 'Expected 16-bit PCM'
                assert audio.getnframes() > audio.getframerate(), 'Expected at least one second of speech'
                assert max(map(abs, samples)) > 100, 'Audio is silent'
                print(f'PASS {voice}: {audio.getnframes()/audio.getframerate():.2f}s of non-silent audio: {output}', flush=True)
    finally:
        backend.close()


if __name__ == '__main__':
    main()
