# XISpeaks Voice Studio (Windows)

An independent desktop app for creating candidate Kokoro voices from volunteer
recordings. It has its own launcher and UI, and does not import or modify the
maintainer app, live NPC database, or curated catalogue. It is excluded from
player release ZIPs. This first version is a source-checkout tool, not a bundled EXE.

## Launch

Run the repository `setup.ps1` if the Python environment has not been created.
Run `voice_studio/SETUP-Voice-Studio.cmd` once, then
`voice_studio/START-Voice-Studio.cmd`.
Setup installs Inno-Kokoro 0.2.0 and praat-parselmouth 0.4.7 into
`build/voice-studio-deps`; it reuses the checkout's existing speech libraries
without upgrading them. Python 3.12 and Kokoro 0.9.4 are the tested configuration.
First generation downloads Inno's weights to `build/voice-studio-model`.
First audition may download Kokoro/language assets if they aren't already cached.
Generation and synthesis run locally; recordings are not uploaded. Upstream
usage telemetry is disabled.

## Workflow

1. Enter the NPC name, volunteer credit, and a voice ID such as `bm_halver`.
   Prefixes: `af` American feminine, `am` American masculine, `bf` British feminine,
   `bm` British masculine. These label the pack; they do not transform the speaker's
   gender or guarantee an accent. Audition uses American/British text pronunciation
   according to the prefix.
2. Browse to a WAV or FLAC recording. Select a start offset and 3–30 second duration.
   At least five seconds of clear speech is recommended; stereo is mixed to mono.
   Use a single speaker, consistent performance, and no music or effects.
3. Click **Generate voice pack**. Each attempt creates a new folder; previous
   candidates are retained. The model remains loaded for subsequent attempts.
4. Enter dialogue not in the recording, then **Render audition** and **Play audition**.
   **Play reference** plays the exact selected clip. **Stop audio** stops playback.
   Rendering/generation runs in a background worker; wait for completion to close.
5. Use **Open existing pack** to revisit a `.pt` voice. Packs are loaded as tensors
   with `weights_only=True` and checked for expected shape and finite values.

Auditions use raw Kokoro at the selected speed, without XISpeaks pitch effects or
its special stutter/pause processing. This lets you judge the new pack itself.
Inno approximates the speaker; it does not promise exact likeness or uniqueness.

## Recording scripts and output

Paste verified NPC dialogue into the recording-script panel and export a text
script with instructions for the volunteer. Automatic DAT/dialogue extraction
is not included yet; confirm speaker attribution yourself.

`voice_studio/output/<voice-id>-<unique-suffix>/` contains:

- `<voice-id>.pt`: the Kokoro-compatible candidate voice tensor.
- `reference.wav`: the selected recording clip.
- `profile.json`: NPC, credit, tool version, clip offsets, checksum, and prosody weights.

Auditions are saved in separate `output/audition-*` folders with their text and
speed. Output, recordings, dependencies and model downloads are ignored by Git
and excluded from player ZIPs. **Reference clips remain in these local folders**;
review what you share and agree on synthesis/distribution permission and credit
with the volunteer before publishing a pack. Credit metadata is not a consent record.

Custom pack loading in the game companion and contribution catalogue is a later
integration step; this tool creates and auditions candidates without installing them.

## Upstream

[Inno-Kokoro](https://github.com/remsky/inno-kokoro) and its
[model card](https://huggingface.co/remsky/kokoro-inno-clone-tuner) describe the
limitations, benchmark results, and licenses. Its code/adapter are Apache-2.0;
the bundled speaker encoder has CC BY-SA 3.0 attribution/license requirements.
Kokoro is Apache-2.0. This repository's app code is GPL-3.0-or-later.
