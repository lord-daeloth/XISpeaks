XISpeaks Pocket 18M - Windows x64 test release

This experimental build uses Ashita. VanaCore and the CatsEyeXI Launcher are
optional. It is separate from the released Piper XISpeaks addon.

INSTALL
Extract the complete XISpeaksPocket folder into your Ashita addons directory.
For the current CatsEyeXI VanaCore layout this is:
D:\Games\CatsEyeXi\catseyexi-client\Vanacore\addons\ashita\XISpeaksPocket
For standalone Ashita, use <your Ashita folder>\addons\XISpeaksPocket.
Do not place it inside an additional XISpeaksPocket subfolder.

Run START-XISpeaks-Pocket.cmd and wait for "Speech engine ready".
Close any existing Pocket test companion first; both use localhost port 49154.
Unload XISpeaks/XISpeaksPiper before loading this test, to prevent duplicate speech.
In game: /addon load XISpeaksPocket
Commands: /xispt voices, /xispt test, /xispt status, /xispt stop, /xispt on/off.
The companion must remain running. No Python install, Hugging Face account,
model downloads, or internet connection is needed for playback.

Optional launcher startup: CatsEyeXI Launcher > Settings > Companion Apps;
add START-XISpeaks-Pocket.cmd and check Auto-Start.

VOICES
Run START-Voice-Catalog.cmd to edit the catalog and preview voices.
The catalog includes stock voices, exported Kyutai collection references,
expressive variants, and character styles. These are
profiles, not all distinct speakers. Cleaned references replace raw duplicates.
Non-English CML and website references are available manually, not automatically.
Unknown genders remain unknown rather than being guessed. New profiles have
not undergone human listening/calibration; adjust NPC assignments in /xispt voices.
Profiles that produced model warnings in the packaged smoke test are manual-only.
See VOICE-TEST-REPORT.txt and VOICE-TEST-RESULTS.json for those results.
Some references have NONCOMMERCIAL licenses. See VOICE-LICENSES.md and
companion/pocket_voices/sources.json before redistributing or using commercially.

This uses the public English 18M playback model. New recordings must be enrolled
separately with the cloning model; that model is not bundled.

DATA / UNINSTALL
Assignments and approvals live in companion/pocket-runtime/npcs.sqlite3.
Voice metadata is companion/pocket_voices/catalog.json.
No personal NPC database is shipped. Halver uses automatic assignment.
To uninstall: /addon unload XISpeaksPocket, close the companion, remove the folder
and any launcher auto-start entry. Back up the runtime folder to preserve settings.

TEST
Run companion\XISpeaks-Pocket-Companion.exe --self-test for a local synthesis test.
Add --all-voices to synthesize every profile. Results go under pocket-runtime.
Self-tests generate files but do not play audio.

CREDITS
XISpeaks by lord-daeloth, developed with OpenAI Codex assistance; GPL-3.0-or-later.
Pocket TTS by Kyutai; voices credited individually in the bundled provenance file.
Rubber Band by Breakfast Quay. See licenses and THIRD-PARTY.md.
Source: https://github.com/lord-daeloth/XISpeaks
This experimental build's matching source is also included in source/.
