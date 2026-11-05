# XISpeaks

XISpeaks reads Final Fantasy XI NPC dialogue aloud with local Piper voices. The Ashita addon captures NPC lines and sends them to a companion on your PC. The Piper server beta supports **Windows x64 only**.

## Install and play

1. Download the Windows ZIP from [the Piper beta release](https://github.com/lord-daeloth/XISpeaks/releases/tag/v1.0.0-beta.2). Close the previous companion and unload the previous addon. When upgrading from Kokoro, move the old XISpeaks folder to a backup location before extracting.
2. Extract the entire **XISpeaks** folder into the Ashita addons directory. For CatsEyeXI with Vanacore, use `Vanacore\addons\ashita\XISpeaks`.
3. Run **START-XISpeaks.cmd** and keep the companion open while playing. The ZIP includes the Windows executable, Python runtime, speech and pitch engines, and a starter voice model. On first launch it downloads the remaining English weights directly from the pinned upstream collection (about 2 GB). Re-run the launcher after an interrupted download. Speech runs locally after setup.
4. In game, enter `/addon load XISpeaks`, then `/xis test`. Use `/xis voices` for recent NPCs, search, voice overrides, pitch, speed, volume and review prompts. Use `/xis stop` to interrupt speech or `/xis status` to check the companion. The default local UDP port is 49152.

**CatsEyeXI Launcher auto-start.** Open **Settings**, scroll down to **Companion Apps**, add the installed **START-XISpeaks.cmd**, and check **Auto-Start**.

## Voices and profiles

The release carries the curated English voice catalog, including separate speakers from multi-speaker models. Catalog settings govern eligibility, gender, speed and volume. NPC presets can also apply pitch and speed effects. The companion stores your history, manual choices and approvals in `companion/piper-runtime/npcs.sqlite3`. Kokoro voice IDs and blends belong to the previous engine. The Kokoro release remains available under tag v0.10.0.

When moving from the Piper test build, close both companions, unload XISpeaksPiper and copy your test build's `piper-runtime` and `piper_voices` folders into the new `companion` folder to retain personal settings and reuse existing downloads. Use the new addon name **XISpeaks**.

## Contributing and building

Voice catalog maintainers can edit metadata, filter and group-edit voices, and preview calibrated samples with [the catalog editor](voice_editor/README.md). The [Piper trainer notes](PIPER-EXPERIMENT.md) cover experimental training workflows. For corrections to the public catalog, open a GitHub issue with the NPC or voice ID and the proposed change. The Piper addon currently has no submission upload.

For source setup, use 64-bit Python 3.12 and run `setup.ps1`, then `run.cmd`. See [the Windows build guide](packaging/BUILDING.md) for release packaging.

XISpeaks is licensed under **GPL-3.0-or-later**. Third-party software and voices have their own terms. See [LICENSE](LICENSE) and [third-party notices](packaging/THIRD-PARTY.md).
