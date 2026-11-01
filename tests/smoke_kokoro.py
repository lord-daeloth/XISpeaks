"""Optional real-model test: writes a short WAV without playing through speakers."""
from array import array
import argparse
import hashlib
from pathlib import Path
import sys
import wave
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'companion'))
from service import KokoroBackend, DEFAULTS
from dialogue import Dialogue
from registry import validate_voice


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--voices', nargs='+', default=['af_heart'])
    parser.add_argument('--speed', type=float, default=1.0)
    parser.add_argument('--pitch', type=float, default=0.0)
    parser.add_argument('--volume', type=float, default=1.0)
    args = parser.parse_args()
    backend = KokoroBackend(DEFAULTS)
    try:
        play_async = backend.stream.play_async
        for voice in args.voices:
            backend.configure(args.speed, args.pitch, args.volume)
            validate_voice(voice)
            filename = voice if voice.replace('_', '').isalnum() else 'blend-' + hashlib.sha256(voice.encode()).hexdigest()[:12]
            suffix = f'-s{args.speed}-p{args.pitch}-v{args.volume}' if (args.speed,args.pitch,args.volume) != (1,0,1) else ''
            output = Path(__file__).resolve().parents[1] / f'smoke-{filename}{suffix}.wav'
            with patch.object(backend.stream, 'play_async', side_effect=lambda **kwargs: play_async(muted=True, output_wavfile=str(output), **kwargs)):
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
