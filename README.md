# XISpeaks

An Ashita v4 addon that sends NPC dialogue to a local RealtimeTTS/Kokoro companion.
Version 0.1.0 is an initial implementation; actual Vanacore event compatibility and
dialogue coverage need an in-game smoke test.

Local validation: 13 Python/LuaJIT tests passed, and Kokoro generated a 2.71-second
non-silent WAV through RealtimeTTS. The project `.venv` is installed in this checkout;
you can go straight to `install-addon.ps1` and `run.cmd`. The addon has not yet been
copied into the game installation. `setup.ps1` remains available for fresh installs.

## Design

`FFXI text_in -> Ashita addon -> localhost UDP -> Python queue -> Kokoro -> speakers`

The game only filters channels and sends bytes. Python handles text cleanup, voice
selection, model inference and audio playback. No API key or cloud speech service
is needed. First model/voice initialization can download assets; cached inference
is local. Dialogue is not sent to a remote speech provider.

This follows Esper's RealtimeTTS/Kokoro architecture and default `af_heart` voice.
Balloon's channel and encoding handling informed the parser: channel 150 is NPC
dialogue; 151 includes system narration. Unlike Balloon, XISpeaks does not inspect
game memory, hide text, advance dialogue, or change the camera. It reads original
`e.message`, so Balloon's changes to `e.message_modified` should coexist.

Running neural inference inside a Lua addon would require a compatible native
inference runtime, model assets and background execution. That is not implemented
here. A companion avoids putting model latency and Python dependencies in the game
process. This is a practical architecture choice, not proof that in-process TTS is
impossible.

## Setup (Windows)

Use 64-bit Python 3.10–3.12; 3.12 is the default for the setup script.
From this folder in PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
# Or: .\setup.ps1 -Python 'C:\path\to\python.exe'
powershell -ExecutionPolicy Bypass -File .\install-addon.ps1
.\run.cmd
```

The addon installer copies only the Lua addon to:
`D:\Games\CatsEyeXi\catseyexi-client\Vanacore\addons\ashita\XISpeaks`.
For another Ashita installation, pass `-AddonRoot 'C:\path\to\addons'`.
The Python companion stays in this project directory. Nothing launches at Windows
startup, and no game addon is automatically loaded.

Then in game:

```text
/addon load XISpeaks
/xispeaks status
/xispeaks test
```

Wait for `Speech engine ready` in the companion console. First startup can take
longer while models download. An error is reported in that console and through
`status`; the service does not silently substitute a different voice engine.
Close the console or press Ctrl+C to stop the companion.

For capture diagnostics without loading Kokoro:

```powershell
.\run.cmd --dry-run
# Also works without speech packages using any suitable Python:
python .\companion\service.py --dry-run
```

## Commands

`/xis` is an alias for `/xispeaks`.

| Command | Effect |
| --- | --- |
| `on` / `off` | Enable or disable capture; off also stops current/queued speech |
| `stop` | Stop current speech and clear the queue; capture stays enabled |
| `status` | Display capture settings and request companion health |
| `test` | Send a test line even when capture is off |
| `system on` / `system off` | Include/exclude all channel 151 messages; default off |
| `port 49152` | Set local UDP port; match companion `--port` |

Zone-in/out clears speech. Finishing an NPC interaction does not clear speech, so
the final line can finish. Rapidly advancing dialogue queues it in order; at most
12 waiting lines are retained, and waiting lines older than 30 seconds are skipped.
Stop is requested immediately, but Kokoro may take time to finish an active
inference operation before cancellation returns. Model startup is not interruptible
by the in-game stop command; queued lines are still discarded.

## Voices

Setup copies `config.example.json` to `config.json` if it does not exist. Edit
`config.json`, then restart the companion. NPC names are exact, case-sensitive
matches. Unassigned or unnamed dialogue uses `voice`. The Shantotto and Maat entries
are examples, not inferred character identities. No gender/race guessing is used.

`speed` accepts 0.5–2.0. `output_device_index` is a PyAudio device index, or `null`
for the default output. `duplicate_seconds` suppresses immediately repeated,
identical speaker/text within the chosen interval; set it to 0 to disable this.
Unknown config fields fail validation to catch typos.

## Scope and limitations

- Channel 150 is a useful filter, not a guarantee that every line is spoken by an
  NPC. Unnamed channel 150 text is read in the default voice. Player say, party,
  linkshell, combat messages and injected addon messages are excluded.
- Channel 151 is opt-in because it also contains Home Point and other notices.
  Cutscene-only narration detection is not implemented. Some server-specific
  dialogue modes may need additions after real capture testing.
- Input is assumed to be original FFXI Shift-JIS/CP932 bytes, as in Balloon.
  Prompt/color codes and known custom glyphs are cleaned before decoding. English
  voices are the default; Japanese text is preserved but needs an appropriate
  Kokoro voice/language setup to sound correct.
- UDP is nonblocking and best effort: no retries or replay after the companion
  starts. `status` confirms reachability; a successful send alone does not.
- One game client per companion/port is supported. Multiple clients sharing a
  port would share the queue and stop controls. Use separate ports for multiboxing.
- The listener binds only to `127.0.0.1`. Other local programs can send speech or
  stop commands; it is not an authenticated local service.
- RealtimeTTS may log internal synthesis/audio errors without raising exceptions.
  A `ready` status confirms engine initialization, not audible output. Check the
  console and `/xispeaks test` for audio device/model issues.

## Validation

```powershell
python -m unittest discover -s tests -v
```

Tests cover raw FFXI text cleanup, protocol rejection, voice mapping, queue order,
duplicates, overflow, expiry, cancellation and actual loopback UDP traffic with
a controlled speech backend. They do not require Kokoro or launch the game.
Install the optional developer package `lupa` to include LuaJIT event-handler
tests; otherwise those two tests are skipped. Run `python tests/smoke_kokoro.py`
for a real-model test that writes `smoke-test.wav` without playing it aloud.

In-game checklist: run dry mode; speak to an NPC; verify speaker and text; send
player chat and verify silence; test with Balloon loaded; change zones while speech
is queued; verify `/xis off`; then restart without dry mode and check audible output.

## References

- [Esper](https://github.com/lord-daeloth/esper), inspected at
  `cfd93079a64a092aa06502a1fb0d06f863ea7718` (`desktop/esper_tts.py`).
- [Balloon for Ashita v4](https://github.com/onimitch/ffxi-balloon-ashitav4), local
  version 4.3.2 (`Balloon.lua`, `defines.lua`), for channel and glyph behavior.
- [RealtimeTTS](https://github.com/KoljaB/RealtimeTTS) and
  [Kokoro](https://github.com/hexgrad/kokoro).

The integration is newly written; Esper/Balloon source is not bundled in the addon.
The ignored `.reference` directory, if present in this development checkout, is
research material only and should not be distributed.
