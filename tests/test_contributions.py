import copy
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit,parse_qs

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'companion'))
from contributions import Contributions, export, parse, issue, validate, digest
from registry import Registry
from service import DEFAULTS


class ContributionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.registry=Registry(self.root/'npcs.sqlite3',dict(DEFAULTS,voices={}))

    def tearDown(self):
        self.registry.close()
        self.temp.cleanup()

    def approve(self,name):
        row=self.registry.encounter(name)
        npc=self.registry.page(search=name)['rows'][0]
        self.registry.review_action(npc['key'],npc['fingerprint'],'approve')

    def test_exports_only_valid_contributions_without_private_data(self):
        self.approve('Halver')
        self.registry.encounter('Unreviewed')
        self.registry.encounter('Maat')
        self.registry.edit('maat','profile',dict(voice='am_michael',speed=1,pitch=0))
        self.registry.set_globals(1.4,2)
        doc=export(self.registry)
        self.assertEqual({e['name'] for e in doc['npcs']},{'Halver','Maat'})
        encoded=json.dumps(doc)
        for field in ('last_seen','encounters','muted','volume','review_enabled'):
            self.assertNotIn(field,encoded)
        self.assertEqual(parse(encoded),doc)
        self.registry.edit('halver','preset',dict(name='galka',enabled=True))
        self.assertNotIn('Halver',[e['name'] for e in export(self.registry)['npcs']])

    def test_bundled_entries_are_not_resubmitted_but_new_edits_are(self):
        self.approve('Halver')
        baseline=self.root/'seed.sqlite3'
        with sqlite3.connect(baseline) as db: self.registry.db.backup(db)
        db.close()
        self.assertEqual(export(self.registry,baseline)['npcs'],[])
        self.registry.edit('halver','preset',dict(name='child',enabled=True))
        doc=export(self.registry,baseline)
        self.assertEqual(doc['npcs'][0]['kind'],'manual')

    def test_small_inline_large_attachment_and_retry_safe_open(self):
        self.approve('Halver')
        doc=export(self.registry)
        small=issue(doc,'voices.json')
        self.assertFalse(small['attachment'])
        self.assertEqual(parse(parse_qs(urlsplit(small['url']).query)['body'][0]),doc)
        for i in range(10): self.approve('Test NPC '+str(i))
        manager=Contributions(self.registry,self.root/'exports')
        summary=manager.prepare()
        self.assertTrue(summary['attachment'])
        path=self.root/'exports'/summary['filename']
        self.assertEqual(len(parse(path.read_text())['npcs']),11)
        with patch('contributions.webbrowser.open',return_value=True) as browser, patch('contributions.subprocess.Popen') as explorer:
            manager.open(summary['token'])
            manager.open(summary['token'])
            self.assertEqual(browser.call_count,1)
            self.assertEqual(explorer.call_count,1)
            self.assertEqual(explorer.call_args.args[0][-1],str(path))
        with self.assertRaises(ValueError): manager.open('../anything')

    def test_rejects_tampering_duplicates_and_unexpected_fields(self):
        self.approve('Halver')
        doc=export(self.registry)
        for mutate in [lambda d:d.update(secret='no'),
                       lambda d:d['npcs'].append(copy.deepcopy(d['npcs'][0])),
                       lambda d:d['npcs'][0]['effective'].update(pitch=999)]:
            bad=copy.deepcopy(doc);mutate(bad);bad['id']=digest(bad)
            with self.assertRaises(ValueError):validate(bad)
        bad=copy.deepcopy(doc);bad['id']='bad'
        with self.assertRaises(ValueError):validate(bad)


if __name__=='__main__': unittest.main()
