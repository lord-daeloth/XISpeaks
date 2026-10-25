"""Optional real-model test: writes a short WAV without playing through speakers."""
from array import array
from pathlib import Path
import sys
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'companion'))
from service import KokoroBackend, DEFAULTS


def main():
    output = Path(__file__).resolve().parents[1] / 'smoke-test.wav'
    backend = KokoroBackend(DEFAULTS)
    try:
        backend.stream.feed("Welcome to Vana'diel. Your voice companion is ready.").play(
            muted=True, output_wavfile=str(output))
    finally:
        backend.close()
    with wave.open(str(output), 'rb') as audio:
        samples = array('h', audio.readframes(audio.getnframes()))
        assert audio.getsampwidth() == 2, 'Expected 16-bit PCM'
        assert audio.getnframes() > audio.getframerate(), 'Expected at least one second of speech'
        assert max(map(abs, samples)) > 100, 'Audio is silent'
        print(f'PASS: {audio.getnframes()/audio.getframerate():.2f}s of non-silent audio: {output}')


if __name__ == '__main__':
    main()
