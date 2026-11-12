## XISpeaks beta 3 — Pocket TTS

Windows x64 / Ashita. VanaCore and the CatsEyeXI Launcher are optional.

Download **all three ZIPs** (app + voices-1 + voices-2), then extract them into the same Ashita addons directory. Run `XISpeaks/START-XISpeaks.cmd`, then `/addon load XISpeaks` and `/xis test`. Public Pocket English 18M weights and all curated voice files are bundled; playback needs no Python, Hugging Face account, or model download.

- Switches the main engine from Piper to Pocket TTS.
- Curated catalog with custom voices and per-voice eligibility/calibration; unreferenced voice files excluded.
- NPC review, manual overrides, and two random-voice buttons (unrestricted or NPC-rule-aware).
- Catalog editor supports bulk removal and recovery from missing voice files.
- Source includes the separate cloning studio with media import, cleanup, multi-region selection, auditions and export.

Back up and replace the previous installation; do not overlay the old Piper folder. Pocket test users can migrate their closed companion's `pocket-runtime/npcs.sqlite3`, then use `/xis` rather than `/xispt`. See README for exact paths and upgrade instructions.

This is a beta despite being marked Latest so it is the default download. Check VOICE-LICENSES.md for voice-specific terms and attribution, including noncommercial profiles. Source and third-party notices are included. The player packages do not contain the cloning model, source recordings, studio projects or personal history.
