"""Portable Pocket playback entry point; never enrolls or downloads voices."""
import multiprocessing
import os
from pathlib import Path
import sys
from pocket_paths import ROOT, VOICES

def main():
    os.environ['NUMBA_CACHE_DIR'] = str(ROOT/'pocket-runtime/cache')
    if '--self-test' in sys.argv:
        import json
        import logging
        import time
        import torch
        import wave
        import pocket_catalog
        import registry
        from pocket_backend import PocketBackend
        from pocket_service import create_registry
        import service
        catalog=pocket_catalog.load(VOICES/'catalog.json')
        registry.VOICES[:]=sorted(catalog)
        registry.BLENDING_ENABLED=False
        config=dict(service.DEFAULTS,voice='bf_alba',voice_pool=list(catalog),voice_catalog=catalog)
        db=create_registry(config,':memory:')
        backend=PocketBackend(config)
        results=[]
        warnings=[]
        class CaptureWarnings(logging.Handler):
            def emit(self, record):
                if record.levelno>=logging.WARNING:
                    warnings.append(record.getMessage())
        capture=CaptureWarnings()
        model_log=logging.getLogger('pocket_tts.models.tts_model')
        model_log.addHandler(capture)
        output=ROOT/'pocket-runtime/self-test';output.mkdir(parents=True,exist_ok=True)
        keys=list(catalog) if '--all-voices' in sys.argv else list(catalog)[:3]
        try:
            for i,key in enumerate(keys):
                warnings.clear()
                torch.manual_seed(42)
                started=time.perf_counter()
                data=b''.join(backend.pcm('Welcome, adventurer.',key))
                if len(data)<4800 or not any(data):raise RuntimeError('Invalid speech: '+key)
                results.append(dict(voice=key,audio_seconds=len(data)/48000,generation_seconds=time.perf_counter()-started,warnings=list(warnings)))
                if i<3:
                    with wave.open(str(output/(key+'.wav')),'wb') as wav:
                        wav.setparams((1,2,24000,0,'NONE','not compressed'));wav.writeframes(data)
                if (i+1)%25==0:print('Validated',i+1,'/',len(keys),flush=True)
            for effect in ('rubberband','librosa'):
                backend.configure(.9,-2.5,1,effect)
                if not any(b''.join(backend.pcm('Safe travels, my friend.',next(iter(catalog))))):raise RuntimeError('Silent effect '+effect)
        finally:
            model_log.removeHandler(capture)
            backend.close();db.close()
        (output/'results.json').write_text(json.dumps(results,indent=2))
        print('PASS: offline public model,',len(keys),'voices, NPC seed and both pitch engines',flush=True)
        return
    from pocket_service import main as serve
    serve()

if __name__=='__main__':
    multiprocessing.freeze_support()
    main()
