# Portable Windows release

**Windows x64 only.** There is currently no supported Linux build.
Download packaged releases from https://github.com/lord-daeloth/XISpeaks/releases.

Extract `dist/XISpeaks-windows-x64.zip` into your Ashita addons directory, then
double-click `XISpeaks/START-XISpeaks.cmd`. Load with `/addon load XISpeaks`.
The companion EXE, Python runtime, Kokoro model, 28 English voices, tokenizer,
Librosa, and Rubber Band R3 are included. Keep the entire folder together.

The release seeds reviewed NPC defaults plus saved author corrections on first start. Choices are saved
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

To include the current overrides and approvals from an installed companion:

```powershell
python scripts/build_release.py --registry 'C:\path\to\XISpeaks\companion\npcs.sqlite3' --output dist/XISpeaks-windows-x64-v0.9.0.zip
```

Use `--package-only` with an already rebuilt, tested EXE when only documentation
or the curated seed changed. The ZIP includes the project LICENSE, third-party
notices and source; generated binaries/models remain out of Git.

The builder fetches pinned Kokoro assets and tokenizer data, creates a fresh
seed database, freezes the app with PyInstaller, and produces a ZIP and SHA-256
checksum in dist. Each build reads NPC corrections from the project's npcs.sqlite3
and exports them to data/release_npc_overrides.json. This includes manual voices,
blends, pitch/speed overrides, gender preferences, race/Child toggles and approval
fingerprints. Approval fingerprints remain valid only for the same NPC sound. It excludes
encounter history, mute choices, and global audio settings. If the local database
is absent, the saved JSON is used, so source releases retain the corrections.
Use --registry PATH to read a different live database, or --catalog-only to omit
corrections. --package-only refreshes the seed without rebuilding the EXE.
Existing users' databases remain untouched; these defaults apply to new installs.
The optional review-mode toggle is personal and is never exported.
Source, upstream
source archives, model attribution and third-party notices accompany the release.

Run `START-XISpeaks.cmd --self-test` to test offline synthesis, blending, and
both pitch engines without audible playback. It writes two WAVs beside the EXE.
The build is unsigned and targets Windows x64. Validate on a clean Windows
machine before describing a release as tested on machines without Python.
