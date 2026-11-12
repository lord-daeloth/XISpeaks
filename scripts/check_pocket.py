import json,sys,time,wave
from pathlib import Path
from unittest.mock import patch
root=Path.cwd()
sys.path[:0]=[str(root/'companion'),str(root/'scripts')]
import pocket_catalog,registry
from pocket_paths import VOICES
from pocket_backend import PocketBackend
from pocket_service import create_registry
import service
catalog=pocket_catalog.load(VOICES/'catalog.json')
registry.VOICES[:]=sorted(catalog);registry.BLENDING_ENABLED=False
config=dict(service.DEFAULTS,voice='bf_alba',voice_pool=list(catalog),voice_catalog=catalog)
db=create_registry(config,':memory:')
assert db.voice_for('Halver') in catalog
assert db.db.execute('select count(*) from npcs').fetchone()[0]>=3700
backend=PocketBackend(config)
assert not backend.model.has_voice_cloning
out=root/'build/pocket-smoke';out.mkdir(parents=True,exist_ok=True)
text='Welcome, adventurer. There is much we have yet to discover beyond these walls.'
lengths=[]
for name,voice,speed,pitch in [('neutral','bf_alba',1,0),('volunteer','bf_alba',1,0),('galka','bf_alba',.9,-2.5)]:
    backend.configure(speed,pitch,1)
    start=time.perf_counter();data=b''.join(backend.pcm(text,voice))
    assert len(data)>24000 and any(data)
    with wave.open(str(out/(name+'.wav')),'wb') as wav:
        wav.setparams((1,2,24000,0,'NONE','not compressed'));wav.writeframes(data)
    print(name,'seconds',len(data)/48000,'synthesis',time.perf_counter()-start,flush=True)
# Interrupt a streaming utterance, then confirm the same model is usable again.
cancelled=False
stream=backend.pcm(text,'bf_alba',lambda:cancelled)
backend.configure(1,0,1)
next(stream);cancelled=True
assert list(stream)==[]
assert any(b''.join(backend.pcm('Hello again.','bf_alba')))
backend.close();db.close()
print('Real Pocket stock/custom/effects/cancellation checks passed',flush=True)
