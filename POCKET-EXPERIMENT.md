# Historical Pocket test setup

Pocket is now the main beta 3 engine. See README.md for current release installation. The instructions below describe the isolated test addon.

# XISpeaks Pocket 18M test build

This separate source checkout is on codex/pocket-18m. It uses only english_18m_2026-10, with a separate NPC database, voice catalog, addon name and UDP port.

## Start

1. Run START-XISpeaks-Pocket.cmd and wait for "Speech engine ready".
2. Unload any active XISpeaks/XISpeaksPiper addon so each NPC line is sent once.
3. Run /addon load XISpeaksPocket.
4. Use /xispt test, /xispt status and /xispt voices. Stop speech with /xispt stop.

The installed test addon lives under Vanacore/addons/ashita/XISpeaksPocket. It uses Ashita and does not require VanaCore. Commands /xispeakspocket and /xispocket are also accepted. UDP is localhost port 49154.

## Voices and settings

The expanded catalog contains 638 profiles. Both Halver volunteer test states have been retired; Halver uses normal automatic assignment. The usual NPC race/gender data, automatic eligibility flags, manual overrides, voice review, global volume/speed, NPC pitch/speed and cutscene UI remain available.

Profiles are stored in pocket-runtime/npcs.sqlite3. Eligibility, labels, gender, accent and per-voice calibration live in pocket_voices/catalog.json. The companion reloads valid catalog edits automatically. Use START-Voice-Catalog.cmd for the Pocket catalog editor, including previews and bulk edits. The in-game NPC editor also works normally.

Neutral speech streams immediately. Changing speed or pitch requires rendering the whole NPC line before processing it with Rubber Band R3 (default) or Librosa. This avoids per-chunk effect discontinuities but adds a wait before adjusted speech begins. Generation and effects can be interrupted. Native Pocket phrasing is retained for initial listening tests.

## Local developer setup

pocket-development.json points at the existing XISpeaks checkout containing build/pocket-env, build/pocket-hf and tools. This private file and the volunteer states are excluded from Git. The environment needs pocket-tts==4.0.1, CPU torch==2.15.0+cpu, PyAudio==0.2.14, librosa==1.0.0 and scipy. Playback uses only public 18M weights and tokenizer, pinned in companion/pocket-public-18m.yaml. Stock and prepared volunteer states need no Hugging Face account or gated-model approval. This source test requires the public files cached locally and runs offline. Future distributions should bundle these assets with licenses and attribution. Creating new states from recordings is reserved for the future cloning app; the companion does not load gated weights.

scripts/setup_pocket.py imports cached stock states  into this checkout. It preserves existing catalog edits. scripts/check_pocket.py performs local synthesis, effects and cancellation checks without playing its WAV output. This is an experimental source build; it has not been packaged as an EXE.

## Portable all-voices test

The Windows test packaging workflow is documented in packaging/POCKET-BUILDING.md. The portable companion bundles the public model/tokenizer and exported voice states; it does not need a Hugging Face account or Python installation. Expanded profiles include expressive variants and separately licensed noncommercial voices, with attribution in VOICE-LICENSES.md and per-profile source URLs. The portable addon retains the XISpeaksPocket name and /xispt commands to avoid replacing the released Piper addon.
