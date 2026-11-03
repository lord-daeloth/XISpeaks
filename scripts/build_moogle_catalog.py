"""Build conservative Moogle assignments from the pinned NPC catalog's model evidence."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MODELS={82,981,1418,2361,2364,2365,2401,2405,2406,2419,2452}
EXCLUDE={'dmat','event master','master1','master2','master3','master4'}

def build(catalog):
    assignments=[]
    for key,item in catalog['associations'].items():
        named=key=='moogle' or key.endswith(' moogle')
        modeled=bool(item['entities']) and all(e['look'].get('type')=='standard' and e['look'].get('model') in MODELS for e in item['entities'])
        if key in EXCLUDE or not (named or modeled):continue
        assignments.append(dict(name=item['name'],evidence='explicit Moogle NPC name' if named else 'all recorded appearances use a Moogle model',
            models=sorted({e['look'].get('model') for e in item['entities'] if e['look'].get('model') is not None})))
    return dict(schema=1,source=catalog['source'],revision=catalog['revision'],
        notes='Models 50 and 52 are placeholders; 2290 and 2326 are objects/effects. Never infer Moogles from those models. Named Moogle records may include these placeholder looks.',
        moogle_models=sorted(MODELS),npcs=assignments)

if __name__=='__main__':
    data=build(json.loads((ROOT/'data/npc_associations.json').read_text(encoding='utf-8')))
    (ROOT/'data/moogle_associations.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    print(len(data['npcs']),[n['name'] for n in data['npcs']])
