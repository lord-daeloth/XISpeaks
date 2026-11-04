# Windows x64 release build

Use Python 3.12 on Windows x64. Create a dedicated virtual environment in build/release-env, then install packaging/requirements-build.txt into it. Run setup-rubberband.ps1 and use companion/voice_install.py to populate the pinned local stock voices. The starter model checksum is verified during packaging.

From the project root run the following commands in PowerShell.

```powershell
& ./build/release-env/Scripts/python.exe -m PyInstaller --noconfirm --distpath build/frozen --workpath build/freeze packaging/companion.spec
& ./build/release-env/Scripts/python.exe scripts/build_release.py
```

The packager collects the upstream source archives, third-party notices, catalog, model cards, model manifests, addon and prebuilt companion into dist/XISpeaks-windows-x64-v1.0.0.zip. Extract the ZIP to a fresh directory. Run START-XISpeaks.cmd --self-test to check offline synthesis and both pitch engines, then run the companion and test /xis status and /xis test.

The checked-in data/piper-catalog.json is the release snapshot. To publish future catalog edits, validate the working piper_voices/catalog.json against the installed models, copy it into data/piper-catalog.json and review the diff before building.
