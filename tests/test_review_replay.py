import sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'companion'))
import registry,service
from voice_catalog import normalize
from dialogue import Dialogue
class ReplayTests(unittest.TestCase):
    def test_reject_replay_and_lock_chosen_voice(self):
        catalog={k:normalize(k,dict(model='test.safetensors',gender='m')) for k in ('am_one','am_two')}
        with patch.object(registry,'VOICES',list(catalog)),patch.object(registry,'BLENDING_ENABLED',False):
            db=registry.Registry(':memory:',dict(service.DEFAULTS,voice_pool=list(catalog),voice_catalog=catalog))
            try:
                db.encounter('Halver');db.set_review_enabled(True)
                npc=db.review_candidate('halver');original=npc['voice'];line=Dialogue('Halver','Actual NPC line!',233)
                db.heard_for_review('Halver',npc['fingerprint'],line)
                self.assertEqual(db.review_replay('halver',npc['fingerprint']),line)
                self.assertEqual(db.review_replay('halver',npc['fingerprint'],True),line)
                trial=db.review_state()['review'];self.assertNotEqual(trial['voice'],original);self.assertEqual(trial['review_status'],'unreviewed')
                with self.assertRaises(ValueError):db.review_action('halver',trial['fingerprint'],'approve')
                with self.assertRaises(ValueError):db.review_replay('halver',npc['fingerprint'],True)
                db.heard_for_review('Halver',trial['fingerprint'],line)
                chosen=db.review_action('halver',trial['fingerprint'],'approve')
                self.assertEqual(chosen['voice'],trial['voice']);self.assertEqual(chosen['review_status'],'approved')
                self.assertIsNone(chosen['manual_voice']);self.assertIsNone(db.review_state()['review'])
                db.clear_reviews();self.assertEqual(db.voice_for('Halver'),trial['voice'])
            finally:db.close()
    def test_no_alternative_preserves_current_voice(self):
        catalog={'am_one':normalize('am_one',dict(model='test.safetensors',gender='m'))}
        with patch.object(registry,'VOICES',list(catalog)):
            db=registry.Registry(':memory:',dict(service.DEFAULTS,voice_pool=list(catalog),voice_catalog=catalog))
            try:
                db.encounter('Halver');db.set_review_enabled(True);npc=db.review_candidate('halver')
                db.heard_for_review('Halver',npc['fingerprint'],Dialogue('Halver','Hello'))
                with self.assertRaisesRegex(ValueError,'No other eligible'):db.review_replay('halver',npc['fingerprint'],True)
                self.assertEqual(db.review_state()['review']['voice'],'am_one')
                db.clear_reviews();self.assertEqual(db.review_lines,{})
            finally:db.close()
