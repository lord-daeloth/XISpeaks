from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
sys.path.insert(0,str(ROOT/'companion'))
from build_npc_catalog import classify, decode_hex, resolve, apply_reviewed_overrides
from import_npc_catalog import import_catalog
from registry import Registry
from service import DEFAULTS


class CatalogTests(unittest.TestCase):
    def test_reviewed_overrides_are_exact_names_and_keep_model_evidence(self):
        import json
        reviewed=json.loads((ROOT/'data/goblin_npc_overrides.json').read_text(encoding='utf-8'))
        self.assertEqual(len(reviewed['associations']),79)
        self.assertNotIn('trust: fablinix',reviewed['associations'])
        self.assertIn('goblin grenadier',reviewed['associations'])
        document=dict(statistics={},associations={
            'mystrix':dict(name='Mystrix',status='unknown',profile=None,entities=[dict(id=1)]),
            'other':dict(name='Other',status='unknown',profile=None,entities=[])})
        apply_reviewed_overrides(document,reviewed)
        self.assertEqual(document['associations']['mystrix']['profile']['presets'],['goblin'])
        self.assertEqual(document['associations']['mystrix']['model_classification']['status'],'unknown')
        self.assertEqual(document['associations']['mystrix']['entities'],[dict(id=1)])
        self.assertEqual(document['associations']['other']['status'],'unknown')

    def test_race_bytes_and_unknown_models(self):
        look=decode_hex('0x0100060600101320133013401350006000700000')
        self.assertEqual(classify(look,set())['preference'],'feminine')
        self.assertEqual(classify(look,set())['presets'],['tarutaru'])
        self.assertIsNone(classify(dict(type='equipped',race=31),set()))
        self.assertIsNone(classify(dict(type='standard',model=50),{484}))
        self.assertEqual(classify(dict(type='standard',model=484),{484})['presets'],['goblin'])

    def test_name_conflicts_and_partial_matches_are_not_confirmed(self):
        male=classify(dict(type='equipped',race=1),set())
        female=classify(dict(type='equipped',race=2),set())
        self.assertEqual(resolve([dict(classification=male),dict(classification=female)])[0],'conflict')
        self.assertEqual(resolve([dict(classification=male),dict(classification=None)])[0],'partial')
        self.assertEqual(resolve([dict(classification=male)] )[0],'confirmed')

    def test_import_overrides_only_confirmed_and_preserves_history(self):
        registry=Registry(':memory:',dict(DEFAULTS,voices={}))
        try:
            registry.encounter('Halver')
            registry.edit('halver','profile',dict(voice='af_heart',speed=1.2,pitch=2))
            registry.edit('halver','mute',True)
            registry.edit('halver','preset',dict(name='child',enabled=True))
            profile=classify(dict(type='equipped',race=3),set())
            catalog=dict(schema=1,associations={
                'halver':dict(name='Halver',status='confirmed',profile=profile),
                'unknown':dict(name='Unknown',status='partial',profile=profile)})
            self.assertEqual(import_catalog(registry,catalog)['preserved'],1)
            self.assertEqual(import_catalog(registry,catalog,True)['updated'],1)
            row=registry.page()['rows'][0]
            self.assertIsNone(row['manual_voice'])
            self.assertEqual(row['preference'],'masculine')
            self.assertTrue(row['presets']['child'])
            self.assertTrue(row['muted'])
            self.assertEqual(row['encounters'],1)
            self.assertEqual(registry.page()['total'],1)
        finally:
            registry.close()


if __name__ == '__main__': unittest.main()
