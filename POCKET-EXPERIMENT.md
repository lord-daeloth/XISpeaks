# XISpeaks Pocket 18M test build

This separate source checkout is on codex/pocket-18m. It uses only english_18m_2026-10, with a separate NPC database, voice catalog, addon name and UDP port.

## Start

1. Run START-XISpeaks-Pocket.cmd and wait for "Speech engine ready".
2. Unload any active XISpeaks/XISpeaksPiper addon so each NPC line is sent once.
3. Run /addon load XISpeaksPocket.
4. Use /xispt test, /xispt status and /xispt voices. Stop speech with /xispt stop.

The installed test addon lives under Vanacore/addons/ashita/XISpeaksPocket. It uses Ashita and does not require VanaCore. Commands /xispeakspocket and /xispocket are also accepted. UDP is localhost port 49154.

## Voices and settings

The catalog contains 21 English stock voice states and two volunteer Halver variants. Halver initially uses the 26-second reference. Both volunteer states are available manually and excluded from general automatic assignment. The usual NPC race/gender data, automatic eligibility flags, manual overrides, voice review, global volume/speed, NPC pitch/speed and cutscene UI remain available.

Profiles are stored in pocket-runtime/npcs.sqlite3. Eligibility, labels, gender, accent and per-voice calibration live in pocket_voices/catalog.json. The companion reloads valid catalog edits automatically. The existing standalone Piper catalog editor validates ONNX models and should not be used on this catalog. For this initial test, catalog changes can be made in JSON. The in-game NPC editor works normally.

Neutral speech streams immediately. Changing speed or pitch requires rendering the whole NPC line before processing it with Rubber Band R3 (default) or Librosa. This avoids per-chunk effect discontinuities but adds a wait before adjusted speech begins. Generation and effects can be interrupted. Native Pocket phrasing is retained for initial listening tests.

## Local developer setup

pocket-development.json points at the existing XISpeaks checkout containing build/pocket-env, build/pocket-hf and tools. This private file and the volunteer states are excluded from Git. The environment needs pocket-tts==4.0.1, CPU torch==2.15.0+cpu, PyAudio==0.2.14, librosa==1.0.0 and scipy. This source test uses the already-authorized/cached 18M cloning weights. Initialization fails explicitly if cloning weights are unavailable.

scripts/setup_pocket.py imports cached stock states and the likeness-test volunteer states into this checkout. It preserves existing catalog edits. scripts/check_pocket.py performs local synthesis, effects and cancellation checks without playing its WAV output. This is an experimental source build; it has not been packaged as an EXE.
