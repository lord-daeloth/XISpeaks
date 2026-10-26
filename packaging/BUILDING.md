# Portable Windows release

Extract `dist/XISpeaks-windows-x64.zip` into your Ashita addons directory, then
double-click `XISpeaks/START-XISpeaks.cmd`. Load with `/addon load XISpeaks`.
The companion EXE, Python runtime, Kokoro model, 28 English voices, tokenizer,
Librosa, and Rubber Band R3 are included. Keep the entire folder together.

The release seeds 3,658 reviewed NPC defaults on first start. Choices are saved
in `companion/npcs.sqlite3`. Updates preserve that file and optional config.json.
When migrating from the development setup, close the old companion and copy
your existing npcs.sqlite3 and config.json beside the new EXE. Never run both
companions at once.

## Build

Use Windows x64 Python 3.12 in a virtual environment:

```
python -m pip install -r packaging/requirements-build.txt
powershell -ExecutionPolicy Bypass -File setup-rubberband.ps1
python scripts/build_release.py
```

The builder fetches pinned Kokoro assets and tokenizer data, creates a fresh
seed database, freezes the app with PyInstaller, and produces a ZIP and SHA-256
checksum in dist. No personal registry or config is used. Source, upstream
source archives, model attribution and third-party notices accompany the release.

Run `START-XISpeaks.cmd --self-test` to test offline synthesis, blending, and
both pitch engines without audible playback. It writes two WAVs beside the EXE.
The build is unsigned and targets Windows x64. Validate on a clean Windows
machine before describing a release as tested on machines without Python.
