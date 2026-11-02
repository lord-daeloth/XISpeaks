"""Lazy, single-owner speech worker for maintainer comparisons."""
import os
import queue
import threading

from review_contributions import ROOT
from dialogue import Dialogue
from service import DEFAULTS, KokoroBackend


def make_backend():
    # Reuse staged offline assets when available; otherwise use normal source setup.
    assets=ROOT/'build/assets'
    if (assets/'models/hub').is_dir():
        os.environ['HF_HUB_CACHE']=str(assets/'models/hub')
        os.environ['HF_HUB_OFFLINE']='1'
    if (assets/'nltk_data').is_dir():
        os.environ['NLTK_DATA']=str(assets/'nltk_data')
    import audio_effects
    if not audio_effects.RUBBERBAND.is_file():
        staged=assets/'tools/rubberband-4.0.0-gpl-executable-windows/rubberband.exe'
        if staged.is_file():audio_effects.RUBBERBAND=staged
    return KokoroBackend(DEFAULTS)


class VoicePreview:
    def __init__(self, notify, factory=make_backend):
        self.notify=notify;self.factory=factory
        self.jobs=queue.Queue();self.cancelled=threading.Event();self.closed=False
        self.thread=None

    def play(self, name, text, sound):
        self.cancelled.clear()
        self.jobs.put((name,text,dict(sound)))
        if self.thread is None:
            self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()

    def stop(self):
        self.cancelled.set()

    def close(self):
        self.closed=True;self.stop();self.jobs.put(None)

    def run(self):
        backend=None
        try:
            while True:
                job=self.jobs.get()
                if job is None or self.closed:return
                try:
                    if backend is None:backend=self.factory()
                    name,text,sound=job
                    if not self.cancelled.is_set():
                        backend.configure(sound['speed'],sound['pitch'],1.0,'rubberband')
                        backend.speak(Dialogue(name,text),sound['voice'],self.cancelled.is_set)
                    self.notify('preview_done','Stopped.' if self.cancelled.is_set() else 'Preview finished.')
                except Exception as error:
                    self.notify('preview_error',str(error))
        finally:
            if backend is not None:backend.close()
