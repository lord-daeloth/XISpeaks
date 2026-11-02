"""Review GitHub/file contributions; explicitly merge selected NPCs into release JSON."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'companion'), str(ROOT/'scripts')]
from contributions import FIELDS, MAX_BYTES, RULESET, parse
from registry import Registry, name_key
from service import DEFAULTS
from import_npc_catalog import import_catalog
from release_overrides import apply_overrides


def load_official(path, catalog):
    registry = Registry(':memory:', dict(DEFAULTS, voices={}))
    import_catalog(registry, json.loads(catalog.read_text(encoding='utf-8')))
    document = json.loads(path.read_text(encoding='utf-8'))
    apply_overrides(registry, document)
    return registry, document


def review(document, official, curated):
    known = {name_key(r['name']) for r in curated['npcs']}
    result = []
    candidate = Registry(':memory:', dict(DEFAULTS, voices={}))
    try:
        for entry in document['npcs']:
            key = name_key(entry['name'])
            old = official.db.execute('SELECT * FROM npcs WHERE key=?',(key,)).fetchone()
            before = official.public(old) if old else None
            official.db.backup(candidate.db)
            candidate.encounter(entry['name'])
            candidate.edit(key,'preference',entry['profile']['preference'])
            with candidate.db:
                candidate.db.execute('UPDATE npcs SET '+','.join(f'{f}=?' for f in FIELDS)+' WHERE key=?',
                    (*[entry['profile'][f] for f in FIELDS],key))
            proposed = candidate.public(candidate.db.execute('SELECT * FROM npcs WHERE key=?',(key,)).fetchone())
            status = 'new'
            if document['ruleset'] != RULESET or proposed['fingerprint'] != entry['fingerprint']:
                status = 'outdated_or_custom_rules'
            elif before and before['fingerprint'] == entry['fingerprint'] and (
                    entry['kind']=='approval' or all(old[f]==entry['profile'][f] for f in FIELDS)):
                if entry['kind']=='approval' and before['review_status']=='unreviewed':
                    status = 'new_approval'
                else:
                    status = 'matching'
            elif before and (key in known or entry['kind']=='approval'):
                status = 'conflict'
            result.append(dict(key=key, name=entry['name'], status=status,
                official_profile=None if old is None else {f:old[f] for f in FIELDS},
                official=None if before is None else {f:before[f] for f in ('voice','speed','pitch')},
                proposed=entry['effective'], entry=entry))
    finally:
        candidate.close()
    return result


def merge(document, report, curated, selected, allow_conflicts=False):
    rows = {name_key(r['name']):dict(r) for r in curated['npcs']}
    selected = {name_key(k) for k in selected}
    missing = selected - {r['key'] for r in report}
    if missing:
        raise ValueError('Names absent from submission: '+', '.join(sorted(missing)))
    for item in report:
        if item['key'] not in selected:
            continue
        if item['status']=='outdated_or_custom_rules':
            raise ValueError('Manually resolve older/custom assignment rules before merging: '+item['name'])
        if item['status']=='conflict' and not allow_conflicts:
            raise ValueError('Use --allow-conflicts only after reviewing: '+item['name'])
        if item['status']=='matching':
            continue
        entry = item['entry']
        profile = item['official_profile'] if item['status']=='new_approval' else entry['profile']
        rows[item['key']] = dict(name=entry['name'], **profile,
            approval=entry['fingerprint'] if entry['kind']=='approval' else None)
    return dict(schema=1,npcs=[rows[k] for k in sorted(rows)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--file',type=Path,help='Export JSON or saved issue body')
    source.add_argument('--issue',type=int,help='Read a public XISpeaks issue (inline data only)')
    parser.add_argument('--official',type=Path,default=ROOT/'data/release_npc_overrides.json')
    parser.add_argument('--catalog',type=Path,default=ROOT/'data/npc_associations.json')
    parser.add_argument('--accept',action='append',default=[],help='NPC name to accept; repeat for multiple NPCs')
    parser.add_argument('--allow-conflicts',action='store_true')
    parser.add_argument('--write',action='store_true',help='Save explicitly selected changes; default is review only')
    args = parser.parse_args()
    if args.issue:
        if args.issue < 1:
            raise ValueError('Invalid issue number')
        request = urllib.request.Request(f'https://api.github.com/repos/lord-daeloth/XISpeaks/issues/{args.issue}',
            headers={'User-Agent':'XISpeaks-maintainer','Accept':'application/vnd.github+json'})
        with urllib.request.urlopen(request,timeout=30) as response:
            data=response.read(MAX_BYTES+1)
        if len(data)>MAX_BYTES:
            raise ValueError('Issue too large')
        text=json.loads(data)['body']
    else:
        if args.file.stat().st_size>MAX_BYTES:
            raise ValueError('File too large')
        text=args.file.read_text(encoding='utf-8')
    document=parse(text)
    original=args.official.read_bytes()
    official, curated=load_official(args.official,args.catalog)
    try:
        report=review(document,official,curated)
    finally:
        official.close()
    for row in report:
        print(json.dumps({k:row[k] for k in ('name','status','official','proposed')},ensure_ascii=True))
    updated=merge(document,report,curated,args.accept,args.allow_conflicts)
    if args.write:
        if not args.accept:
            raise ValueError('--write requires one or more --accept names')
        if updated == curated:
            print('Already represented; no changes written.')
            return
        if args.official.read_bytes()!=original:
            raise ValueError('Official data changed during review; rerun')
        backup=ROOT/'build/merge-backups'/ (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]+'.json')
        backup.parent.mkdir(parents=True,exist_ok=True)
        backup.write_bytes(original)
        temp=args.official.with_name(args.official.name+'.'+uuid.uuid4().hex+'.tmp')
        temp.write_text(json.dumps(updated,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        temp.replace(args.official)
        print('Saved selected NPCs. Backup:',backup)
    else:
        print('Review only. Use --accept NAME (repeat as needed) and --write to save.')


if __name__=='__main__':
    main()
