"""Build auditable voice seeds from a pinned LandSandBoat checkout (PyYAML required)."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import subprocess
import sys
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'companion'))
from registry import VOICES, choose_voice, name_key

RACES = {1: ('hume','masculine'), 2: ('hume','feminine'),
         3: ('elvaan','masculine'), 4: ('elvaan','feminine'),
         5: ('tarutaru','masculine'), 6: ('tarutaru','feminine'),
         7: ('mithra','feminine'), 8: ('galka','masculine')}


def read_yaml(path):
    return yaml.load(path.read_text(encoding='utf-8'), Loader=yaml.CSafeLoader) or {}


def sql_rows(path, table):
    # Parse literals only; never execute upstream SQL.
    for line in path.read_text(encoding='utf-8').splitlines():
        match = re.match(r'INSERT INTO `' + table + r'` VALUES \((.*)\);$', line)
        if not match:
            continue
        fields = re.findall(r"'(?:\\.|''|[^'])*'|[^,]+", match[1])
        values = []
        for field in fields:
            field = field.strip()
            if field.startswith("'"):
                field = field[1:-1].replace("''", "'")
                field = re.sub(r'\\(.)', r'\1', field)
            elif field == 'NULL':
                field = None
            values.append(field)
        yield values


def decode_hex(value):
    raw = bytes.fromhex(value.removeprefix('0x'))
    kind = int.from_bytes(raw[:2], 'little')
    if kind == 1:
        return dict(type='equipped', race=raw[3], face=raw[2])
    return dict(type='standard' if kind == 0 else f'legacy_{kind}', model=int.from_bytes(raw[2:4], 'little'))


def classify(look, goblin_models):
    if look.get('type') == 'equipped' and look.get('race') in RACES:
        race, preference = RACES[look['race']]
        return dict(race=race, preference=preference,
                    presets=[race] if race in ('galka','mithra','tarutaru','elvaan') else [])
    if look.get('type') == 'standard' and look.get('model') in goblin_models:
        return dict(race='goblin', preference='unknown', presets=['goblin'])
    return None


def resolve(entries):
    known = {json.dumps(e['classification'], sort_keys=True) for e in entries if e['classification']}
    if len(known) > 1:
        return 'conflict', None
    if not known:
        return 'unknown', None
    profile = json.loads(next(iter(known)))
    # Unknown alternate looks may be disguises, objects, or different NPCs sharing a name.
    return ('confirmed' if all(e['classification'] for e in entries) else 'partial'), profile


def apply_reviewed_overrides(document, overrides):
    if overrides.get('schema') != 1:
        raise ValueError('Unsupported override schema')
    for key, override in overrides['associations'].items():
        if key != name_key(override['name']) or override['status'] != 'confirmed':
            raise ValueError('Invalid reviewed NPC override')
        previous = document['associations'].get(key, {})
        entry = dict(previous)
        if previous:
            entry['model_classification'] = dict(status=previous['status'], profile=previous['profile'])
        entry.update(override)
        entry.setdefault('entities', [])
        entry['suggested_voice'] = choose_voice(key, override['profile']['preference'], [v for v in VOICES if v.startswith('b')] if override['profile']['race']=='elvaan' else VOICES)
        document['associations'][key] = entry
    document['reviewed_sources'] = sorted(set(document.get('reviewed_sources', []) + overrides.get('sources', [overrides['source']])))
    document['statistics']['named_groups'] = len(document['associations'])
    document['statistics']['classifications'] = dict(Counter(v['status'] for v in document['associations'].values()))
    document['statistics']['reviewed_overrides'] = sum('evidence' in v for v in document['associations'].values())
    return document


def generate(source, output):
    revision = subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'], text=True).strip()
    ecosystems = read_yaml(source/'data/ecosystems.yaml')['ecosystems']
    species_families, ids = {}, {}
    for eco in ecosystems.values():
        for family, definition in eco.get('families', {}).items():
            for species, item in definition.get('species', {}).items():
                species_families[species] = family
                ids[str(item['id'])] = family
    model_families = defaultdict(set)
    model_sources = defaultdict(list)
    for path in sorted((source/'data/zones').glob('*/mobs.yaml')):
        for name, mob in read_yaml(path).get('templates', {}).items():
            look = mob.get('attributes', {}).get('render', {}).get('look', {})
            if look.get('type') == 'standard':
                model = look.get('model')
                family = species_families.get(mob.get('species'), 'unknown')
                model_families[model].add(family)
                model_sources[model].append(f'{path.relative_to(source).as_posix()}#{name}')
    for row in sql_rows(source/'sql/mob_pools.sql', 'mob_pools'):
        look = decode_hex(row[4])
        if look['type'] == 'standard':
            model_families[look['model']].add(ids.get(row[3], 'unknown'))
            model_sources[look['model']].append('sql/mob_pools.sql#' + row[0])
    goblin_models = {model for model, families in model_families.items() if families == {'goblin'} and model not in (0,50)}
    entities = {}
    for path in sorted((source/'data/zones').glob('*/npcs.yaml')):
        for identity, npc in read_yaml(path).get('npcs', {}).items():
            entities[int(identity)] = dict(id=int(identity), name=npc.get('display_name'),
                script=npc.get('script'), zone=path.parent.name, look=npc.get('render',{}).get('look',{}),
                source=path.relative_to(source).as_posix())
    for row in sql_rows(source/'sql/npc_list.sql', 'npc_list'):
        identity = int(row[0])
        entities.setdefault(identity, dict(id=identity, name=row[2], script=row[1],
            zone=f'zone_{(identity >> 12) & 0xFFF}', look=decode_hex(row[15]), source='sql/npc_list.sql'))
    groups = defaultdict(list)
    excluded = Counter()
    for entry in entities.values():
        name = entry['name']
        if not name or not any(c.isalpha() for c in name) or name.startswith(('_','#')) or 'debug' in name.casefold():
            excluded['unnamed_placeholder_or_debug'] += 1
            continue
        entry['classification'] = classify(entry['look'], goblin_models)
        groups[name_key(name)].append(entry)
    associations = {}
    counts = Counter()
    for key, entries in sorted(groups.items()):
        status, profile = resolve(entries)
        counts[status] += 1
        associations[key] = dict(name=entries[0]['name'], status=status, profile=profile,
                                 suggested_voice=choose_voice(key, profile['preference'] if profile else 'unknown', [v for v in VOICES if v.startswith('b')] if profile and profile['race'] == 'elvaan' else VOICES),
                                 entities=entries)
    document = dict(schema=1, source='https://github.com/LandSandBoat/server', revision=revision,
        rules='Only confirmed entries are eligible for import; partial/unknown/conflicting names require review.',
        statistics=dict(entities=len(entities), named_groups=len(groups), classifications=dict(counts), excluded=dict(excluded)),
        goblin_model_evidence={str(m):sorted(set(model_sources[m])) for m in sorted(goblin_models)},
        associations=associations)
    for filename in ('goblin_npc_overrides.json','wiki_race_overrides.json'):
        override_path = ROOT/'data'/filename
        if override_path.exists():
            apply_reviewed_overrides(document, json.loads(override_path.read_text(encoding='utf-8')))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(document['statistics'], indent=2))
    print('Goblin model IDs:', sorted(goblin_models))
    print(output)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT/'data/npc_associations.json')
    args=parser.parse_args()
    generate(args.source, args.output)
