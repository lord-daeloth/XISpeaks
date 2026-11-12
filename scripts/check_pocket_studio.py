"""Integration checks using a consenting volunteer reference; never installs into the live catalog."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import uuid
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'pocket_studio'),str(ROOT/'companion')]
import studio_engine as s

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--reference',type=Path,required=True);args=parser.parse_args()
    import numpy as np
    import soundfile as sf
    out=ROOT/'build'/('studio-check-'+uuid.uuid4().hex[:8]);out.mkdir()
    s.OUTPUT=out/'projects';s.OUTPUT.mkdir()
    original_hash=s.hashlib.sha256(args.reference.read_bytes()).hexdigest()
    info=s.probe(args.reference);project,data=s.import_media(info,info['tracks'][0]['index'])
    assert data['summary']['seconds']>26.65
    # Real codecs and a video with two audio tracks.
    s.run_tool([s.tool('ffmpeg'),'-v','error','-y','-i',str(args.reference),'-t','6',str(out/'short.wav')])
    for extension in ('flac','mp3','m4a','ogg'):
        file=out/('reference.'+extension)
        s.run_tool([s.tool('ffmpeg'),'-v','error','-y','-i',str(out/'short.wav'),str(file)])
        probe=s.probe(file);p,d=s.import_media(probe,probe['tracks'][0]['index'])
        assert 5.9<d['summary']['seconds']<6.5
        print('Imported',extension,flush=True)
    video=out/'two-tracks.mp4'
    s.run_tool([s.tool('ffmpeg'),'-v','error','-y','-f','lavfi','-i','color=c=black:s=160x90:r=5','-i',str(out/'short.wav'),'-f','lavfi','-i','sine=frequency=1000:sample_rate=24000','-map','0:v','-map','1:a','-map','2:a','-t','6','-c:v','mpeg4','-c:a','aac',str(video)])
    probe=s.probe(video);assert len(probe['tracks'])==2
    p,d=s.import_media(probe,probe['tracks'][1]['index']);audio,rate=sf.read(p/'source.wav')
    dominant=np.fft.rfftfreq(len(audio),1/rate)[np.argmax(np.abs(np.fft.rfft(audio)))]
    assert abs(dominant-1000)<3
    print('Video extraction selected the correct audio track',flush=True)
    for start,end in ((-1,5),(0,31),(5,4),(0,float('nan'))):
        try:s.selection(project,start,end)
        except ValueError:pass
        else:raise AssertionError('Invalid selection accepted')
    try:s.import_media(info,info['tracks'][0]['index'],lambda:True)
    except s.Cancelled:pass
    else:raise AssertionError('Cancellation ignored')
    raw,_=s.prepare(project,.3,26.65,'Off',True)
    clean,meta=s.prepare(project,.3,26.65,'Light',True)
    assert (raw/'reference.wav').read_bytes()!=(clean/'reference.wav').read_bytes()
    assert meta['prepared']['peak_dbfs']<=-2.99
    worker=s.Engine();candidate,cmeta=worker.clone(project,clean,'Integration check')
    results=worker.audition([candidate],['Welcome, adventurer. Your time will come, my friend.'],[42,42])
    assert results[0]['metrics']['seconds']>1
    a=sf.read(results[0]['file'])[0];b=sf.read(results[1]['file'])[0]
    assert a.shape==b.shape and np.max(np.abs(a-b))<=2/32768
    try:worker.audition([candidate],['Hello there.'],[42],lambda:True)
    except s.Cancelled:pass
    else:raise AssertionError('Audition cancellation ignored')
    entry=s.profile(candidate,'xu_studio_test','Studio test','u','x','Volunteer test','Local test only',{})
    dest=out/'export';s.export(candidate,'xu_studio_test',entry,dest)
    assert not list(dest.glob('*.wav'))
    assert str(args.reference) not in (dest/'xu_studio_test.json').read_text()
    catalog=out/'catalog';catalog.mkdir();shutil.copyfile(ROOT/'pocket_voices/alba.safetensors',catalog/'alba.safetensors')
    (catalog/'catalog.json').write_text(json.dumps({'bf_alba':dict(model='alba.safetensors',engine_model=s.MODEL)}))
    s.install(candidate,'xu_studio_test',entry,catalog/'catalog.json')
    assert not s.Store(catalog/'catalog.json').catalog['xu_studio_test']['automatic']
    try:s.install(candidate,'xu_studio_test',entry,catalog/'catalog.json')
    except ValueError:pass
    else:raise AssertionError('Existing voice overwritten')
    assert s.hashlib.sha256(args.reference.read_bytes()).hexdigest()==original_hash
    (out/'results.json').write_text(json.dumps(dict(candidate=str(candidate),auditions=results,checks='audio/video import, track selection, denoise, normalization, clone, public playback, fixed seed, cancellation, export privacy, catalog install/conflict'),indent=2))
    print('PASS Pocket Studio integration:',out,flush=True)

if __name__=='__main__':main()
