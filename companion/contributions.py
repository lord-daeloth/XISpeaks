"""Portable voice contributions. No credentials, history, or network uploads."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import uuid
from urllib.parse import urlencode
import webbrowser

from registry import PRESETS, PREFERENCES, name_key, number, validate_voice

VERSION = '0.10.0'
RULESET = 'kokoro-en-v2-galka35'
MARKER = '<!-- xispeaks-contribution:v1 -->'
ISSUE_URL = 'https://github.com/lord-daeloth/XISpeaks/issues/new'
MAX_BYTES = 2 * 1024 * 1024
FIELDS = ('preference', 'manual_voice', 'manual_speed', 'manual_pitch') + tuple('preset_' + p for p in PRESETS)


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'))


def fingerprint(effective):
    return hashlib.sha256(json.dumps([effective['voice'], round(effective['speed'], 6),
        round(effective['pitch'], 6)]).encode()).hexdigest()[:32]


def digest(document):
    return hashlib.sha256(canonical({k: v for k, v in document.items() if k != 'id'}).encode()).hexdigest()


def export(registry, baseline=None):
    official = {}
    if baseline and Path(baseline).is_file():
        with closing(sqlite3.connect(Path(baseline).resolve().as_uri()+'?mode=ro', uri=True)) as db:
            db.row_factory = sqlite3.Row
            official = {r['key']: dict(r) for r in db.execute('SELECT * FROM npcs')}
    records = []
    with registry.lock:
        for row in registry.db.execute('SELECT * FROM npcs ORDER BY key'):
            current = registry.public(row)
            prior = official.get(row['key'])
            profile = {field: row[field] for field in FIELDS}
            changed = prior is not None and any(profile[f] != prior[f] for f in FIELDS)
            manual = current['review_status'] == 'manual' or changed
            approved = current['review_status'] == 'approved'
            if not manual and not approved:
                continue
            if prior is not None and not changed:
                prior_public = registry.public(prior)
                if manual or prior_public['review_status'] == 'approved':
                    continue  # Don't resubmit bundled assignments/approvals.
            effective = {key: current[key] for key in ('voice', 'speed', 'pitch')}
            records.append(dict(name=current['name'], kind='manual' if manual else 'approval',
                profile=profile, effective=effective, fingerprint=fingerprint(effective)))
    document = dict(format='xispeaks-contribution', schema=1, app_version=VERSION,
                    ruleset=RULESET, npcs=records)
    document['id'] = digest(document)
    validate(document)
    return document


def validate(document):
    if not isinstance(document, dict) or set(document) != {'format','schema','app_version','ruleset','npcs','id'}:
        raise ValueError('Invalid contribution document')
    if document['format'] != 'xispeaks-contribution' or type(document['schema']) is not int or document['schema'] != 1:
        raise ValueError('Unsupported contribution format')
    for key in ('app_version','ruleset'):
        if not isinstance(document[key], str) or not re.fullmatch(r'[A-Za-z0-9._-]{1,80}', document[key]):
            raise ValueError('Invalid contribution version')
    if not isinstance(document['npcs'], list) or len(document['npcs']) > 5000:
        raise ValueError('Too many NPCs')
    seen = set()
    for item in document['npcs']:
        if not isinstance(item, dict) or set(item) != {'name','kind','profile','effective','fingerprint'}:
            raise ValueError('Invalid NPC contribution')
        key = name_key(item['name'])
        if key in seen or any(ord(c)<32 for c in item['name']) or item['kind'] not in ('manual','approval'):
            raise ValueError('Duplicate or invalid NPC name/kind')
        seen.add(key)
        p, e = item['profile'], item['effective']
        if not isinstance(p, dict) or set(p) != set(FIELDS) or p['preference'] not in PREFERENCES:
            raise ValueError('Invalid voice profile')
        if p['manual_voice'] is not None:
            validate_voice(p['manual_voice'])
        for field, low, high in [('manual_speed',.7,1.3),('manual_pitch',-4,4)]:
            if p[field] is not None:
                number(p[field],low,high,field)
        for preset in PRESETS:
            if type(p['preset_'+preset]) is not int or p['preset_'+preset] not in (0,1):
                raise ValueError('Invalid NPC preset')
        if not isinstance(e,dict) or set(e) != {'voice','speed','pitch'}:
            raise ValueError('Invalid endorsed sound')
        validate_voice(e['voice'])
        number(e['speed'], .1, 10, 'NPC speed')
        number(e['pitch'], -4, 4, 'NPC pitch')
        if item['fingerprint'] != fingerprint(e):
            raise ValueError('Voice fingerprint mismatch')
        if item['kind']=='approval' and any(p[f] is not None for f in ('manual_voice','manual_speed','manual_pitch')):
            raise ValueError('An automatic approval cannot contain manual tuning')
    if document['id'] != digest(document) or len(canonical(document).encode()) > MAX_BYTES:
        raise ValueError('Contribution checksum mismatch or file too large')
    return document


def parse(text):
    if len(text.encode('utf-8')) > MAX_BYTES:
        raise ValueError('Contribution exceeds 2 MiB')
    if MARKER in text:
        blocks = re.findall(r'```json\s*\n(.*?)\n```', text.split(MARKER,1)[1], re.S)
        if len(blocks) != 1:
            raise ValueError('Download the attached JSON file and pass it to the merge tool')
        text = blocks[0]
    try:
        return validate(json.loads(text))
    except (TypeError, KeyError, json.JSONDecodeError) as exc:
        raise ValueError('Malformed contribution') from exc


def issue(document, filename):
    manual = sum(r['kind']=='manual' for r in document['npcs'])
    summary = (f"Voice contribution: {len(document['npcs'])} NPCs ({manual} manual corrections, "
               f"{len(document['npcs'])-manual} approvals).\nXISpeaks {VERSION}.\n\n")
    title = f"Voice contribution: {len(document['npcs'])} NPCs"
    body = summary + MARKER + '\n```json\n' + canonical(document) + '\n```\n'
    url = ISSUE_URL + '?' + urlencode(dict(title=title,body=body))
    attachment = len(url) > 1800  # Conservative Windows/browser URL bound.
    if attachment:
        body = summary + MARKER + f'\nPlease drag **{filename}** from the opened folder into this issue before submitting.\n\nContribution ID: `{document["id"]}`\n'
        url = ISSUE_URL + '?' + urlencode(dict(title=title,body=body))
    return dict(url=url, body=body, title=title, attachment=attachment)


class Contributions:
    def __init__(self, registry, folder, baseline=None):
        self.registry, self.folder, self.baseline = registry, Path(folder), baseline
        self.jobs = {}

    def prepare(self):
        document = export(self.registry, self.baseline)
        manual = sum(r['kind']=='manual' for r in document['npcs'])
        if not document['npcs']:
            return dict(count=0, manual=0, approvals=0)
        self.folder.mkdir(parents=True, exist_ok=True)
        filename = 'xispeaks-voices-' + document['id'][:16] + '.json'
        path = self.folder / filename
        # Deterministic export is safe to retry; atomic replace prevents partial files.
        temp = self.folder / (filename+'.'+uuid.uuid4().hex+'.tmp')
        temp.write_text(json.dumps(document,indent=2,ensure_ascii=True)+'\n',encoding='utf-8')
        temp.replace(path)
        token = uuid.uuid4().hex
        job = dict(issue(document,filename), path=path, opened=False)
        if len(self.jobs)>=16:
            self.jobs.pop(next(iter(self.jobs)))
        self.jobs[token] = job
        return dict(token=token,count=len(document['npcs']),manual=manual,
            approvals=len(document['npcs'])-manual,filename=filename,attachment=job['attachment'])

    def open(self, token, folder_only=False):
        if not isinstance(token,str) or token not in self.jobs:
            raise ValueError('Prepare the contribution again before opening it')
        job = self.jobs[token]
        if not folder_only and job['opened']:
            return 'Submission page already opened. Prepare again to reopen it.'
        if folder_only or job['attachment']:
            subprocess.Popen(['explorer.exe','/select,',str(job['path'])])
        if not folder_only:
            if not webbrowser.open(job['url']):
                raise ValueError('Unable to open browser. Export saved; open the folder to submit it manually.')
            job['opened'] = True
        return ('Folder opened.' if folder_only else 'GitHub opened. Review and submit the issue; attach the selected file if requested.')
