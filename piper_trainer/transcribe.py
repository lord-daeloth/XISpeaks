"""Local timestamped transcription for the trainer's editable clip list."""
import argparse
import json
import sys
from math import gcd
from pathlib import Path
from paths import ASSETS
sys.path.insert(0,str(ASSETS/'build/voice-transcribe-deps'))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('audio',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args()
    import soundfile as sf
    from scipy.signal import resample_poly
    from faster_whisper import WhisperModel
    audio,rate=sf.read(args.audio,dtype='float32',always_2d=True);audio=audio.mean(axis=1)
    divisor=gcd(rate,16000);audio=resample_poly(audio,16000//divisor,rate//divisor)
    model=WhisperModel('base.en',device='cpu',compute_type='int8',download_root=str(ASSETS/'build/voice-transcribe-models'),local_files_only=True)
    segments,_=model.transcribe(audio,language='en',beam_size=5,word_timestamps=True)
    rows=[]
    for s in segments:
        # Whisper sentence segments are editable; do not silently replace fantasy names.
        rows.append(dict(start=round(s.start,3),end=round(min(s.end,len(audio)/16000),3),text=s.text.strip()))
        print('TRANSCRIBE',round(min(100,s.end/(len(audio)/16000)*100)),flush=True)
    if not rows:raise ValueError('No speech detected')
    args.output.write_text(json.dumps(dict(source=str(args.audio.resolve()),segments=rows,peak_db=-3,
        stages=[100,300,1000],texts=[rows[0]['text'],
        'The merchant counted seven silver coins, closed the wooden chest, and quietly asked us to leave.',
        'Why has the watchtower gone silent? Send a messenger immediately, but keep the remaining soldiers here.']),indent=2),encoding='utf-8')

if __name__=='__main__':main()
