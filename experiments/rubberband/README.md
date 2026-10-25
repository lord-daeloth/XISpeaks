# Standalone Rubber Band comparison

No app/addon code, settings, database, or dependencies are changed. Uses existing
unmodified smoke-af_heart.wav, smoke-am_michael.wav, and smoke-bf_emma.wav recordings.

Open output/index.html in a web browser to audition 30 players: originals plus
three algorithms at +3.5, -1, and +0.4 semitones. Comparison WAVs concatenate
original, current librosa, Rubber Band R3, and R3 with formant preservation,
with half-second pauses. Pitch only: speed and volume are unchanged.

Run from the XISpeaks folder:

```powershell
.\.venv\Scripts\python.exe experiments/rubberband/compare.py
```

Official utility source:
https://breakfastquay.com/files/releases/rubberband-4.0.0-gpl-executable-windows.zip
Extract into tools/ (retain the archive directory name). Its license and DLL are
kept alongside the executable. Downloaded tools and generated outputs are ignored
by Git. The experiment uses the existing Python environment with no pip installs.

Measured on this machine: warm librosa 9.7-14.0 ms, R3 44.0-71.8 ms,
R3 with formants 47.3-74.5 ms for recordings 2.71-2.94 seconds long.
Librosa initial warmup: 3.063 seconds. Raw measurements: output/timings.json.
Each reported time is a median of three runs following one initial run.
Rubber Band includes subprocess startup and file I/O, while librosa is in-memory
DSP. TTS synthesis, playback buffering, and browser playback are not timed.
These offline tests do not establish streaming latency or perceptual quality.
All processed files were checked for finite/non-silent samples, 24 kHz rate,
and duration within 50 ms of the source. Outputs use PCM16 for browser playback.
