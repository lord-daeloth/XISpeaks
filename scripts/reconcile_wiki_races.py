"""Reconcile captured wiki category membership with NPC display names conservatively."""
from collections import Counter, defaultdict
import difflib
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'companion'))
from registry import name_key


def clean_title(title):
    title=re.sub(r'^Trust:\s*','',title)
    return re.sub(r'\s+\((?:A|S|UC|NPC)\)$','',title).strip()


def punctuation_key(title):
    return ''.join(c for c in name_key(title) if c.isalnum())


def reconcile(catalog, pages):
    associations=catalog['associations']
    index=defaultdict(set)
    for key in associations:index[punctuation_key(key)].add(key)
    matches=defaultdict(list)
    report=dict(pages=len(pages),category_entries=sum(len(p['members']) for p in pages),unmatched=[],ambiguous=[],unchanged=[],updates=[])
    for page in pages:
        for member in page['members']:
            title=member['title'];name=clean_title(title)
            evidence=dict(title=title,url=member['url'],category=page['url'],race=page['race'])
            # Category membership can include guild/location/user pages, not just speakers.
            if ':' in name or 'Guild' in name or re.search(r'\([^()]+\)$',name):
                report['unmatched'].append(dict(evidence,reason='Non-speaker or unresolved disambiguation'))
                continue
            key=name_key(name)
            candidates={key} if key in associations else index.get(punctuation_key(name),set())
            if len(candidates)!=1:
                report['unmatched'].append(dict(evidence,reason='No unique display-name match',
                    suggestions=difflib.get_close_matches(key,list(associations),n=3,cutoff=.85)))
                continue
            key=next(iter(candidates))
            matches[key].append(dict(evidence,match='exact' if key==name_key(name) else 'unique punctuation normalization'))
    updates={}
    for key,evidence in sorted(matches.items()):
        races={e['race'] for e in evidence}
        existing=associations[key]
        # Recover original classifications when rerunning against an augmented catalog.
        original=existing.get('model_classification',existing)
        model_races={e['classification']['race'] for e in existing.get('entities',[]) if e.get('classification')}
        if len(races)!=1 or model_races-races:
            report['ambiguous'].append(dict(key=key,name=existing['name'],wiki_races=sorted(races),model_races=sorted(model_races),evidence=evidence))
            continue
        race=next(iter(races))
        if original['status']=='confirmed' and original.get('profile',{}).get('race')==race:
            report['unchanged'].append(key)
            continue
        genders={e['classification']['preference'] for e in existing.get('entities',[]) if e.get('classification') and e['classification']['race']==race and e['classification']['preference']!='unknown'}
        preference=next(iter(genders)) if len(genders)==1 else 'unknown'
        # Voice defaults established by XISpeaks' existing race policy, not age/sex inference.
        if preference=='unknown' and race=='galka':preference='masculine'
        updates[key]=dict(name=existing['name'],status='confirmed',profile=dict(race=race,preference=preference,presets=[race]),
            evidence=dict(method='Reviewed category membership; exact or unique punctuation match',sources=evidence),
            previous_status=original['status'])
        report['updates'].append(dict(key=key,race=race,previous_status=original['status'],preference=preference))
    report['counts']=dict(updates=len(updates),unchanged=len(report['unchanged']),ambiguous=len(report['ambiguous']),unmatched_pages=len(report['unmatched']),by_race=dict(Counter(v['profile']['race'] for v in updates.values())))
    overrides=dict(schema=1,revision='wiki-races-2026-10-25',source='https://ffxiclopedia.fandom.com/',sources=[p['url'] for p in pages],associations=updates)
    return overrides,report


if __name__=='__main__':
    catalog=json.loads((ROOT/'data/npc_associations.json').read_text(encoding='utf-8'))
    pages=json.loads((ROOT/'data/wiki_race_pages.json').read_text(encoding='utf-8'))
    overrides,report=reconcile(catalog,pages)
    for filename,value in [('wiki_race_overrides.json',overrides),('wiki_race_review.json',report)]:
        (ROOT/'data'/filename).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report['counts'],indent=2))
