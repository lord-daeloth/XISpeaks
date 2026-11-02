import queue
from pathlib import Path
import sys
import tempfile
import time
import tkinter as tk
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine import Engine, voice_id, recording_script
from studio import Studio


class StudioTests(unittest.TestCase):
    def test_names_and_script(self):
        self.assertEqual(voice_id('bm_halver'),'bm_halver')
        for value in ('../escape','bm_../test','CON','bm_a/b','bm_a\\b','am_'):
            with self.assertRaises(ValueError):voice_id(value)
        text=recording_script('Halver','Welcome, adventurer.')
        self.assertIn('Halver',text);self.assertIn('Welcome, adventurer.',text)
        with self.assertRaises(ValueError):recording_script('Halver',' ')

    def test_reject_silent_short_and_invalid_pack(self):
        import numpy as np
        import soundfile as sf
        import torch
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);source=folder/'silence.wav'
            sf.write(source,np.zeros(24000*5),24000)
            engine=Engine()
            for start,duration in ((0,30),(5,5),(0,2),(float('nan'),5)):
                with self.assertRaises(ValueError):engine.generate(source,'am_test','Test','',start,duration)
            pack=folder/'am_bad.pt';torch.save(torch.zeros(1),pack)
            with self.assertRaises(ValueError):engine.render(pack,'Hello.')
            self.assertIsNone(engine.tuner)

    def test_ui_worker_success_error_and_selection(self):
        root=tk.Tk();root.withdraw();ui=Studio(root)
        def wait():
            deadline=time.monotonic()+5
            while ui.busy and time.monotonic()<deadline:root.update();time.sleep(.01)
            self.assertFalse(ui.busy)
        try:
            with patch.object(ui.engine,'generate',return_value=Path('candidate/am_test.pt')) as generate:
                ui.source.set('volunteer.wav');ui.identifier.set('am_test');ui.generate();wait()
                self.assertEqual(ui.pack,Path('candidate/am_test.pt'))
                self.assertEqual(generate.call_args.args[0],'volunteer.wav')
            with patch.object(ui.engine,'render',return_value=Path('preview.wav')):
                ui.render();wait();self.assertEqual(ui.preview,Path('preview.wav'))
            with patch.object(ui.engine,'render',side_effect=ValueError('Bad pack')),patch('studio.messagebox.showerror') as error:
                ui.render();wait();error.assert_called_once()
            self.assertIn('Bad pack',ui.status.get())
        finally:ui.close()


if __name__=='__main__':unittest.main()
