# XISpeaks

An Ashita v4 addon that sends NPC dialogue to a local RealtimeTTS/Kokoro companion.
Version 0.3.0 adds a persistent NPC registry, stable automatic voice assignments,
and an in-game voice editor. Restart the companion and `/addon reload XISpeaks`,
then use `/xis voices`. Dialogue capture still supports Halver's mode 142 and
Faurie's mode 150; tracing remains available.

Initial validation: 13 Python/LuaJIT tests passed, and Kokoro generated a 2.71-second
non-silent WAV through RealtimeTTS. The project `.venv` is installed in this checkout;
you can go straight to `install-addon.ps1` and `run.cmd`.
`setup.ps1` remains available for fresh installs.

## Design

`FFXI text_in -> Ashita addon -> localhost UDP -> Python queue -> Kokoro -> speakers`

The game only filters channels and sends bytes. Python handles text cleanup, voice
selection, model inference and audio playback. No API key or cloud speech service
is needed. First model/voice initialization can download assets; cached inference
is local. Dialogue is not sent to a remote speech provider.

This follows Esper's RealtimeTTS/Kokoro architecture and default `af_heart` voice.
Balloon's channel and encoding handling informed the parser: channel 150 is NPC
dialogue; 151 includes system narration. Named mode 142 dialogue was added based
on an actual capture. Unlike Balloon, XISpeaks does not inspect
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
| `voices` / `ui` / no arguments | Toggle the NPC voice editor |
| `help` | Print the command list |
| `on` / `off` | Enable or disable capture; off also stops current/queued speech |
| `stop` | Stop current speech and clear the queue; capture stays enabled |
| `status` | Display capture settings and request companion health |
| `test` | Send a test line even when capture is off |
| `system on` / `system off` | Include/exclude all channel 151 messages; default off |
| `port 49152` | Set local UDP port; match companion `--port` |
| `trace on` / `trace off` | Start/save a bounded local diagnostic capture of all text events |
| `trace Halver` | Capture only text containing Halver (case-insensitive) plus packet metadata |

Zone-in/out clears speech. Finishing an NPC interaction does not clear speech, so
the final line can finish. Rapidly advancing dialogue queues it in order; at most
12 waiting lines are retained, and waiting lines older than 30 seconds are skipped.
Stop is requested immediately, but Kokoro may take time to finish an active
inference operation before cancellation returns. Model startup is not interruptible
by the in-game stop command; queued lines are still discarded.

## Voices

Open `/xis voices`. Talk to NPCs while capture is enabled and the companion is
running; they appear with their latest encounter first. All NPCs, Recent (last
24 hours), Manual overrides, search, and pagination keep the list manageable.
Old conversations are not imported from chat logs; entries accumulate from now on.

Select an NPC to:

- Choose a voice and **Preview voice** without saving. Preview uses a fixed sample,
  replaces current/queued speech, and does not create a new NPC entry.
- **Save override** to persist the selected voice. The UI confirms after the
  companion commits it; failures/timeouts are shown. On timeout, Refresh to check
  whether an edit was saved before the acknowledgement was lost.
- **Reset to automatic** to remove the manual override and restore the saved
  automatic voice. It is not a reroll.
- Choose **Unknown / mixed pool**, **Masculine**, or **Feminine** automatic voice
  preference. Changing preference recalculates the automatic voice using that
  pool, but keeps any manual override until Reset. No gender is inferred from names.
- **Mute this NPC** without losing the chosen voice.

Edits apply to subsequent playback, including waiting lines. An already playing
line finishes; `/xis stop` stops it immediately. The preview dropdown labels voices
by US/UK accent and masculine/feminine category. First use can download voice assets.
One failed voice playback is logged without disabling every subsequent NPC.

The default pool contains the 28 English voices exposed by the pinned Kokoro engine.
On first encounter, a SHA-256 hash of the normalized NPC name picks an automatic
voice, and the result is saved. Pool changes do not reshuffle existing assignments.
Names are Unicode-normalized, whitespace-normalized, and case-insensitive for
identity; NPCs with the same name share an assignment across zones/characters.
Unnamed narration uses `config.json`'s `voice` and does not enter the registry.

Assignments, preferences, mute state and last-seen times live in **npcs.sqlite3**
beside `config.json`. Back up that file with the companion stopped. SQLite commits
each edit/encounter atomically. Do not delete it unless you want to reset the registry.
Use `--registry 'C:\path\to\npcs.sqlite3'` to keep separate profiles. Use a separate
port per simultaneous companion, as before.

Existing `config.json` `voices` entries are imported **once**, on registry creation,
as manual overrides (including the Maat/Shantotto examples, if still configured).
After that the editor/database is authoritative; editing that old mapping does not
overwrite UI choices or undo resets. Legacy custom/blended voice values are
preserved for playback, but the editor currently selects/previews English stock
voices only. An unknown saved voice can be replaced using the dropdown.

Setup copies `config.example.json` to `config.json` if missing. Engine settings still
live there and require restarting the companion. An optional `voice_pool` list
restricts automatic assignments, for example `["af_heart", "am_michael", "bf_emma",
"bm_george"]`. Include at least one voice of each category if using both preferences;
an empty category produces an error instead of silently choosing the wrong pool.
Manual assignments can use any of the 28 stock voices regardless of this pool.

`speed` accepts 0.5–2.0. `output_device_index` is a PyAudio device index, or `null`
for the default output. `duplicate_seconds` suppresses immediately repeated,
identical speaker/text within the chosen interval; set it to 0 to disable this.
Unknown config fields fail validation to catch typos.

## Investigating missed dialogue

Install the updated Lua file with `install-addon.ps1`, then `/addon reload XISpeaks`.
The companion does not need restarting for tracing. For a focused comparison:

1. `/xis trace Halver`, speak to Halver, then `/xis trace off`.
2. `/xis trace Faurie`, speak to Faurie, then `/xis trace off`.

Each capture prints its path and creates a separate `trace-*.tsv` file in the
installed XISpeaks addon folder. `/xis trace on` records all text instead, including
player conversations; use named captures when you only need those NPCs. Logs stay
local and are not sent to the companion. Captures are not enabled automatically.

The trace includes full and low-byte modes, modified mode, injected/blocked flags,
the speech filter's decision, and original/modified text as hex (to preserve game
encoding and control bytes). `speech` means the line passed the addon filter, not
confirmation of UDP delivery or audible playback. Selected incoming chat/dialogue/
zone packet IDs and times are recorded for correlation; packet payloads are not.
Metadata packet records are included even with a name filter and are not proof of
a particular speaker. Text flags reflect what this callback sees, not necessarily
the final state after all other addons have processed the event.

Readable inspection from this project folder:

```powershell
.\.venv\Scripts\python.exe companion\inspect_trace.py 'D:\path\to\trace-file.tsv'
# For an all-chat capture, optionally filter the report:
.\.venv\Scripts\python.exe companion\inspect_trace.py 'D:\path\to\trace-file.tsv' --contains Halver
```

Compare Halver's low mode and decision with Faurie's. A different mode calls for
examining that channel before adding it; an injected line calls for checking the
addon producing it. Original/modified text and injected copies can explain replayed
log entries without assuming the server sent duplicates. If Halver is entirely
absent, the trace cannot establish why: check the name filter and consider testing
with chat-formatting addons temporarily unloaded to isolate event delivery/order.

The first comparison found Halver at full mode 654 (low byte 142), not injected or
blocked. Faurie's originals were full mode 662 (low byte 150), followed by two
timestamped copies per line at full mode 66200 (low byte 152). Those copies were
blocked but **not** flagged injected, so checking the injection flag alone would
not exclude them. Mode 152 remains excluded. The trace does not identify which
component generated the copies. Halver's line also arrived after packet 0x052;
an interaction-active-only filter could therefore miss this closing dialogue.

Captures stop at 120 seconds or 1,000 records. Each text field is limited to 1,024
bytes; original lengths are retained to identify truncation. The in-memory buffer
holds at most 64 records and flushes on presentation every half second; overflow
is counted in the completion message. Logs are buffered, so an abrupt game exit can
lose the final buffer. Tracing makes no changes to speech-channel acceptance.

## Scope and limitations

- Channel 150 is a useful filter, not a guarantee that every line is spoken by an
  NPC. Unnamed channel 150 text is read in the default voice. Player say, party,
  linkshell, combat messages and injected addon messages are excluded.
- Channel 142 is accepted only when it has a nonempty `Speaker : dialogue` prefix
  (up to 48 speaker bytes in the addon). Unnamed notices remain excluded. Both the
  addon and companion enforce this restriction. This is a text-format heuristic,
  not a lookup proving the named speaker is an NPC. Other dialogue modes may still
  require future traces; this does not claim exhaustive NPC coverage.
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
  stop commands and edit voice assignments; it is not an authenticated local service.
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
tests; otherwise those tests are skipped. Version 0.3.0 passes 35 tests, including
the observed Halver/Faurie modes, exclusion of unnamed mode 142 notices and mode
152 duplicates, raw capture, name filtering, timeout, buffer limits and write errors.
Registry/editor tests additionally cover stable hashing across restarts/pool changes,
one-time migration, preferences, overrides/reset/mute, literal search/pagination,
live queued-line changes, UI acknowledgements and retry deduplication.
Run `python tests/smoke_kokoro.py --voices af_heart am_michael bf_emma`
for real-model switching tests that write `smoke-<voice>.wav` without playing aloud.
Lua UI tests use mocked ImGui calls; actual in-game layout and interaction require
a smoke test after reload.

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
