import json,unittest
from pathlib import Path
class BlankReleaseTests(unittest.TestCase):
    def test_seed_contains_no_manual_voice_tuning_or_approvals(self):
        root=Path(__file__).resolve().parents[1]
        data=json.loads((root/'data/release_npc_overrides.json').read_text())
        for npc in data['npcs']:
            for field in ('manual_voice','manual_speed','manual_pitch','approval'):
                self.assertIsNone(npc[field],npc['name']+' '+field)
