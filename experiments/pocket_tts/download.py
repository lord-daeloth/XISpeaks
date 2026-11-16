import os,json,time
from pathlib import Path
root=Path(__file__).resolve().parents[2]
os.environ['HF_HOME']=str(root/'build/pocket-hf')
os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
from pocket_tts import TTSModel
from pocket_tts.utils.utils import _ORIGINS_OF_PREDEFINED_VOICES
out=Path(__file__).parent/'output'
results=[]
for language in ['english','english_18m_2026-10','english_7m_2026-10','english_2m_2026-10']:
    start=time.perf_counter()
    model=TTSModel.load_model(language=language)
    voices=[]
    for name in _ORIGINS_OF_PREDEFINED_VOICES:
        model.get_state_for_audio_prompt(name)
        voices.append(name)
    results.append(dict(language=language,voices=voices,seconds=time.perf_counter()-start))
    print(language,len(voices),'voices ready',flush=True)
    del model
(out/'download.json').write_text(json.dumps(results,indent=2))
