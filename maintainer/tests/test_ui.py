import json
from pathlib import Path
import sys
import tempfile
import time
import tkinter as tk
import unittest
from unittest.mock import patch

sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parents[2]/'companion')]
from maintainer_ui import MaintainerUI
from review_contributions import save_review
from registry import Registry
from service import DEFAULTS
from contributions import export


class MaintainerUITests(unittest.TestCase):
    def test_load_select_merge_and_refresh_in_real_tk(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            official=folder/'official.json';official.write_text('{"schema":1,"npcs":[]}')
            catalog=folder/'catalog.json';catalog.write_text('{"schema":1,"associations":{}}')
            registry=Registry(':memory:',dict(DEFAULTS,voices={}))
            try:
                registry.encounter('Test NPC')
                registry.edit('test npc','profile',dict(voice='am_michael',speed=1,pitch=0))
                doc=export(registry)
            finally:registry.close()
            source=folder/'submission.json';source.write_text(json.dumps(doc))
            root=tk.Tk();root.withdraw()
            ui=MaintainerUI(root,official,catalog,folder/'backups')
            def wait():
                deadline=time.monotonic()+5
                while ui.busy and time.monotonic()<deadline:
                    root.update();time.sleep(.01)
                self.assertFalse(ui.busy)
            try:
                with patch('maintainer_ui.messagebox.showerror') as error:
                    ui.start_load(file=source);wait()
                    error.assert_not_called()
                self.assertEqual(len(ui.rows),1)
                self.assertFalse(ui.selected)
                ui.tree.selection_set('0');ui.show_details()
                self.assertIn('am_michael',ui.details[1].get('1.0','end'))
                ui.select_new();self.assertEqual(ui.selected,{'test npc'})
                with patch('maintainer_ui.messagebox.askyesno',return_value=True),patch('maintainer_ui.messagebox.showinfo'),patch('maintainer_ui.messagebox.showerror') as error:
                    ui.merge_selected();wait();error.assert_not_called()
                self.assertEqual(json.loads(official.read_text())['npcs'][0]['manual_voice'],'am_michael')
                self.assertEqual(len(list((folder/'backups').glob('*.json'))),1)
                self.assertEqual(ui.rows['0']['status'],'matching')
                ui.select_new();self.assertFalse(ui.selected)
            finally:ui.close()

    def test_stale_review_is_rejected_and_backup_is_exact(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);path=folder/'official.json'
            old=dict(schema=1,npcs=[]);original=json.dumps(old).encode()
            path.write_bytes(original)
            updated=dict(schema=1,npcs=[dict(name='Test')])
            path.write_bytes(original+b' ')
            with self.assertRaises(ValueError):save_review(path,original,old,updated,folder/'backups')
            self.assertFalse((folder/'backups').exists())
            path.write_bytes(original)
            backup=save_review(path,original,old,updated,folder/'backups')
            self.assertEqual(backup.read_bytes(),original)
            self.assertEqual(json.loads(path.read_text()),updated)


if __name__=='__main__':unittest.main()
