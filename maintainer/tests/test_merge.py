from pathlib import Path
import sys
import unittest
sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parents[2]/'companion')]
from review_contributions import review,merge
from contributions import export,digest
from registry import Registry
from service import DEFAULTS


class MergeTests(unittest.TestCase):
    def test_review_conflict_and_selected_merge(self):
        official=Registry(':memory:',dict(DEFAULTS,voices={}))
        submitted=Registry(':memory:',dict(DEFAULTS,voices={}))
        try:
            official.encounter('Halver');submitted.encounter('Halver')
            submitted.edit('halver','profile',dict(voice='am_michael',speed=1,pitch=0))
            doc=export(submitted)
            curated=dict(schema=1,npcs=[])
            report=review(doc,official,curated)
            self.assertEqual(report[0]['status'],'new')
            changed=merge(doc,report,curated,['Halver'])
            self.assertEqual(changed['npcs'][0]['manual_voice'],'am_michael')
            official.edit('halver','profile',dict(voice='am_michael',speed=1,pitch=0))
            official.edit('halver','preference','masculine')
            same_sound=review(doc,official,changed)
            self.assertEqual(same_sound[0]['status'],'conflict')
            official.edit('halver','profile',dict(voice='af_heart',speed=1,pitch=0))
            report=review(doc,official,changed)
            self.assertEqual(report[0]['status'],'conflict')
            with self.assertRaises(ValueError):merge(doc,report,changed,['Halver'])
            self.assertEqual(merge(doc,report,changed,['Halver'],True),changed)
            doc['ruleset']='older';doc['id']=digest(doc)
            report=review(doc,official,changed)
            self.assertEqual(report[0]['status'],'outdated_or_custom_rules')
            with self.assertRaises(ValueError):merge(doc,report,changed,['Halver'],True)
        finally:
            official.close();submitted.close()

    def test_approval_matching_and_duplicate_import(self):
        from release_overrides import apply_overrides
        official=Registry(':memory:',dict(DEFAULTS,voices={}))
        submitted=Registry(':memory:',dict(DEFAULTS,voices={}))
        try:
            official.encounter('Halver');submitted.encounter('Halver')
            row=submitted.page()['rows'][0]
            submitted.review_action('halver',row['fingerprint'],'approve')
            doc=export(submitted);curated=dict(schema=1,npcs=[])
            report=review(doc,official,curated)
            self.assertEqual(report[0]['status'],'new_approval')
            changed=merge(doc,report,curated,['Halver'])
            apply_overrides(official,changed)
            report=review(doc,official,changed)
            self.assertEqual(report[0]['status'],'matching')
            self.assertEqual(merge(doc,report,changed,['Halver']),changed)
        finally:
            official.close();submitted.close()


if __name__=='__main__':unittest.main()
