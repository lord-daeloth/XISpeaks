# XISpeaks

Local NPC text-to-speech for **Final Fantasy XI**, using an **Ashita v4 addon** and a **Kokoro voice companion**.

**Windows x64 only.** The current release, setup scripts, and bundled companion target Windows. There is no supported Linux build. A Linux companion may be explored later; game/addon compatibility and audio dependencies would need separate validation.

[Download the latest Windows release](https://github.com/lord-daeloth/XISpeaks/releases/latest) · [Release history](https://github.com/lord-daeloth/XISpeaks/releases) · [Build instructions](packaging/BUILDING.md)

## Install the portable release

1. Download the **XISpeaks-windows-x64-v0.9.0.zip** release asset. GitHub's automatic **Source code** archives do not contain the executable, models, or bundled dependencies.
2. Extract the entire `XISpeaks` folder into your Ashita addons directory. For Vanacore, use `Vanacore/addons/ashita/XISpeaks`.
3. Double-click `XISpeaks/START-XISpeaks.cmd`. Keep its console open and wait for the speech engine to become ready.
4. In game, run:

   ```text
   /addon load XISpeaks
   /xis voices
   ```

The ZIP includes Python, Kokoro, all 28 English voices, Librosa, Rubber Band R3, and the required model/tokenizer assets. **No separate Python installation, API key, model download, or internet connection is needed to use the portable release.** Keep the `companion` folder and its `_internal` directory together.

Run only one companion at a time. Close it with Ctrl+C when finished. Nothing starts automatically with Windows. The executable is unsigned.

XISpeaks has been used with Ashita through the CatsEyeXI Vanacore launcher. It is an Ashita addon, not a native Vanacore or Windower addon. Other setups have not been comprehensively tested.

## Features

- Captures NPC dialogue, including named mode-142 dialogue and regular mode-150 NPC dialogue, while filtering player chat.
- Deterministic automatic voice assignments, optional two-voice blends, and per-NPC manual overrides.
- An in-game editor with search, recent conversations, presets, previews, pitch, speed, and mute controls.
- Global speed and volume controls; Rubber Band R3 for higher-quality pitch shifting or Librosa for faster processing.
- Optional voice approval prompts that can appear during cutscenes.
- A starter NPC catalog plus curated voice corrections and approvals.
- Complete-sentence synthesis, 300 ms sentence pauses, 180 ms double-dash pauses, and pronunciation-based stutters with 60 ms breaks for supported cases.
- Standalone `Hm` normalized to `Hmmmm`; laughter remains Kokoro's original rendering.

Speech runs locally. The addon sends dialogue to the companion over localhost UDP (default port `49152`); no dialogue is sent to a cloud speech provider. Inference runs outside the game process.

## Edit and approve voices

Open `/xis voices`, talk to an NPC, and select **Recent NPCs** to find the latest encounters. Approved and manually assigned voices remain editable. Search and the All, Recent, Manual, and Unreviewed filters offer other ways to find entries.

Choose a voice or blend, adjust pitch/speed, and use **Preview voice** before **Save override**. Race/Child preset toggles save immediately. Manual voice choices take precedence over automatic selection.

Enable **Review unapproved voices** to get an Approve / Edit voice / Later prompt after a new voice finishes speaking. Close the main editor to see pending prompts. Approvals track the NPC's voice, pitch, and speed; changing those can require review again. Saved manual voice/tuning overrides count as reviewed. Global audio settings do not invalidate approvals.

During cutscenes, XISpeaks temporarily reveals Ashita's ImGui layer when its editor or review prompt is open. Other ImGui windows may also become visible. It does not advance dialogue or alter the camera.

### NPC presets

| Preset | Automatic voice preference | Speed multiplier | Pitch offset |
| --- | --- | --- | --- |
| Goblin | Existing preference | 115% | +3.5 semitones |
| Child | Small youthful voice pool | 103% | +1 semitone |
| Galka | Existing preference | 90% | -4 semitones |
| Mithra | Feminine voices | 100% | None |
| Tarutaru | Full configured pool | 110% | +1 semitone |
| Elvaan | British primary, more frequent blending | 100% | None |

Presets stack. Effective speed combines global speed, NPC tuning, and presets (clamped to 50–200%); pitch is clamped to -4 through +4 semitones. Automatic Elvaan blends retain at least 60% of the British primary voice. Voice gender is based on catalog data or preferences, not guesses from fantasy names.

## Commands

`/xis` and `/xispeaks` are equivalent prefixes.

| Command | Action |
| --- | --- |
| `/xis voices` | Open/close the voice editor |
| `/xis on` / `/xis off` | Enable/disable capture |
| `/xis stop` | Stop speech and clear the queue |
| `/xis status` | Check settings and companion connectivity |
| `/xis test` | Speak a test line |
| `/xis system on` / `/xis system off` | Include/exclude mode-151 narration (off by default) |
| `/xis port 49152` | Change the addon port; match the companion's port |
| `/xis trace on` / `/xis trace off` | Start/save a bounded diagnostic capture |
| `/xis trace Halver` | Limit trace text to a name or phrase |

Zoning clears speech. Fast dialogue advancement queues lines; the queue drops old waiting lines rather than falling indefinitely behind. Cancellation may wait for active model inference to return.

## Saved data and upgrades

Your active settings live in **`XISpeaks/companion/npcs.sqlite3`**. Close the companion before making a simple file backup. Optional advanced settings can be set by copying `companion/config.example.json` to `companion/config.json`.

New installs start from **`companion/_internal/seed.sqlite3`**, which includes the starter catalog and the author's current curated corrections and approvals. The readable correction list is [data/release_npc_overrides.json](data/release_npc_overrides.json), also included under `source/data` in the ZIP. Encounter history, personal mute choices, global volume/speed, and the review-mode toggle are not distributed.

To upgrade, close the companion and extract the new release over the existing addon folder. Release archives do not contain an active `npcs.sqlite3` or personal `config.json`, so your saved choices remain intact. **New seed defaults do not overwrite an existing user's database.** Reload the addon with `/addon reload XISpeaks` when Lua files change, then launch the new companion.

NPC identity currently uses the normalized display name. Different NPCs sharing a name share an assignment; zone-specific identities are not implemented. The catalog contains incomplete and conflicting classifications, so manual corrections remain useful. See [catalog provenance and coverage](data/README.md).

## Troubleshooting

- **No speech:** wait for the companion to finish startup, then run `/xis status` and `/xis test`. Check the companion console for errors.
- **Only one instance allowed:** close any existing XISpeaks companion console before launching another copy.
- **NPC missing from the editor:** click **Recent NPCs**, which clears the search/filter and returns to recent encounters.
- **Quiet voices:** raise Voice volume in the editor and click **Apply global audio**. Boosted peaks are limited.
- **Unnatural names or vocalizations:** Kokoro can struggle with fantasy names, laughter, and some stutters. Report a short example with the assigned voice and tuning.
- **Missed dialogue:** use a short `/xis trace` capture. Traces may contain player chat, so inspect them before sharing.

`START-XISpeaks.cmd --self-test` checks offline speech, blending, pitch engines, and stutter handling without audible playback. It writes test WAVs beside the EXE.

## Develop from source (Windows)

Use 64-bit Python 3.10–3.12; the portable build uses Python 3.12. From the repository folder:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
powershell -ExecutionPolicy Bypass -File .\install-addon.ps1 -AddonRoot 'C:\path\to\Ashita\addons'
.\run.cmd
```

Source setup downloads dependencies and model assets as needed. The development companion stays in the checkout; do not also run the portable companion on the same port. The installer defaults to the author's Vanacore directory, so supply `-AddonRoot` for your installation.

```powershell
# Optional LuaJIT test dependency:
.\.venv\Scripts\python.exe -m pip install lupa
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

See [portable build instructions](packaging/BUILDING.md) to build an EXE/ZIP and include a chosen database's overrides and approvals. Listening experiments are under `experiments/`; they contain author-specific paths and are development aids, not installation steps.

## License and acknowledgments

XISpeaks code is licensed under **GPL-3.0-or-later**. See [LICENSE](LICENSE). Copyright (c) 2026 lord-daeloth.

Third-party code, models, and data retain their respective licenses. The release includes license notices, model attribution, XISpeaks source, and upstream source archives under `licenses/` and `source/`; model assets also retain their bundled notices.

NPC catalog provenance is documented in [data/README.md](data/README.md), including LandSandBoat and FFXIclopedia sources. RealtimeTTS and Kokoro provide speech synthesis; Rubber Band and Librosa provide pitch processing. The companion architecture follows [Esper](https://github.com/lord-daeloth/esper), and Balloon's dialogue handling informed the initial capture approach.
