import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'companion'))
import pocket_catalog as c

class MissingTests(unittest.TestCase):
    def test_cleanup_backup_and_empty_catalog(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(c,'validate_state'):
            root=Path(folder);path=root/'catalog.json'
            entries={k:dict(model=k+'.safetensors',engine_model=c.MODEL) for k in ('am_kept','am_missing')}
            (root/'am_kept.safetensors').write_bytes(b'voice')
            path.write_text(json.dumps(entries));original=path.read_bytes()
            store=c.Store(path,prune_missing=True)
            self.assertEqual(store.missing_removed,['am_missing'])
            self.assertEqual(set(store.catalog),{'am_kept'})
            self.assertEqual(next((root/'catalog-backups').iterdir()).read_bytes(),original)
            (root/'am_kept.safetensors').unlink();store.reload()
            self.assertEqual(store.catalog,{})
            store.reload();self.assertEqual(store.catalog,{})

    def test_invalid_survivor_does_not_modify_catalog(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(c,'validate_state',side_effect=ValueError('corrupt')):
            root=Path(folder);path=root/'catalog.json'
            (root/'am_bad.safetensors').write_bytes(b'bad')
            path.write_text(json.dumps({k:dict(model=k+'.safetensors',engine_model=c.MODEL) for k in ('am_missing','am_bad')}))
            original=path.read_bytes()
            with self.assertRaises(ValueError):c.Store(path,prune_missing=True)
            self.assertEqual(path.read_bytes(),original)
