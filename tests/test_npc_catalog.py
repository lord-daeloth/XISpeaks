from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
sys.path.insert(0,str(ROOT/'companion'))
from build_npc_catalog import classify, decode_hex, resolve, apply_reviewed_overrides
from import_npc_catalog import import_catalog
from reconcile_wiki_races import reconcile, clean_title
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

    def test_wiki_reconciliation_preserves_gender_and_skips_conflicts(self):
        npc=lambda name,status,profile,entities:dict(name=name,status=status,profile=profile,entities=entities)
        female=dict(race='tarutaru',preference='feminine',presets=['tarutaru'])
        catalog=dict(associations={
            'shantotto':npc('Shantotto','partial',female,[dict(classification=female),dict(classification=None)]),
            'guard':npc('Guard','unknown',None,[]),
            'bob, i.m.':npc('Bob, I.M.','unknown',None,[])})
        pages=[dict(race='tarutaru',url='taru',members=[dict(title='Trust: Shantotto',url='s'),dict(title='Guard',url='g')]),
               dict(race='galka',url='galka',members=[dict(title='Guard',url='g'),dict(title='Bob I.M.',url='b')])]
        result,report=reconcile(catalog,pages)
        self.assertEqual(result['associations']['shantotto']['profile']['preference'],'feminine')
        self.assertIn('bob, i.m.',result['associations'])
        self.assertNotIn('guard',result['associations'])
        self.assertEqual(len(report['ambiguous']),1)
        self.assertEqual(clean_title('Trust: Apururu (UC)'),'Apururu')

    def test_race_only_import_preserves_manual_tuning_and_gender(self):
        registry=Registry(':memory:',dict(DEFAULTS,voices={}))
        try:
            registry.encounter('Zeid')
            registry.edit('zeid','profile',dict(voice='am_onyx',speed=.8,pitch=-1))
            registry.edit('zeid','preference','masculine')
            registry.edit('zeid','preset',dict(name='child',enabled=True))
            catalog=dict(schema=1,associations={'zeid':dict(name='Zeid',status='confirmed',profile=dict(race='galka',preference='unknown',presets=['galka']))})
            import_catalog(registry,catalog,race_only=True)
            row=registry.page()['rows'][0]
            self.assertEqual((row['manual_voice'],row['manual_speed'],row['manual_pitch']),('am_onyx',.8,-1))
            self.assertEqual(row['preference'],'masculine')
            self.assertTrue(row['presets']['galka'])
            self.assertTrue(row['presets']['child'])
            self.assertEqual(row['encounters'],1)
        finally:registry.close()

    def test_user_corrections_win_and_generic_names_stay_unresolved(self):
        import json
        overrides=json.loads((ROOT/'data/user_npc_overrides.json').read_text())
        document=dict(statistics={},associations={
            'bompupu':dict(name='Bompupu',status='confirmed',profile=dict(race='hume',preference='masculine',presets=[])),
            'delivery specialist':dict(name='Delivery Specialist',status='confirmed',profile=dict(race='hume',preference='masculine',presets=[]))})
        apply_reviewed_overrides(document,overrides)
        self.assertEqual(document['associations']['bompupu']['profile']['preference'],'feminine')
        self.assertEqual(document['associations']['oruga']['profile']['presets'],[])
        self.assertEqual(document['associations']['prince yahiko']['profile']['preference'],'masculine')
        self.assertEqual(document['associations']['delivery specialist']['status'],'conflict')
        self.assertIsNone(document['associations']['delivery specialist']['profile'])

    def test_explicit_gender_correction_preserves_tuning(self):
        registry=Registry(':memory:',dict(DEFAULTS,voices={}))
        try:
            registry.encounter('Bompupu')
            registry.edit('bompupu','preference','masculine')
            catalog=dict(schema=1,associations={'bompupu':dict(name='Bompupu',status='confirmed',profile=dict(race='tarutaru',preference='feminine',presets=['tarutaru']))})
            import_catalog(registry,catalog,race_only=True,correct_preferences=True)
            row=registry.page()['rows'][0]
            self.assertEqual(row['preference'],'feminine')
            self.assertTrue(row['presets']['tarutaru'])
            self.assertEqual(row['encounters'],1)
        finally:registry.close()

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
