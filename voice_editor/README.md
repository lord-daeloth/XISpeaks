# Piper Voice Catalog Editor

Launch **START-Voice-Catalog.cmd** from the XISpeaks checkout. This is a
separate Windows GUI from the trainer and maintainer tools. It uses the existing
Piper environment and edits `piper_voices/catalog.json`.

## Editing voices

Search by voice ID, label, or model name; use the gender filter to work through
unknown voices. Select a voice and change its label, model/speaker ID, gender,
accent group, automatic-assignment switch, eligible NPC types, volume or speed.
Changing gender does **not** rename the voice ID or invalidate manual references.

Edits remain drafts until **Save catalog**. Moving to another voice retains its
valid draft edits. Preview uses the selected voice's current unsaved settings.
Save creates a timestamped backup under `piper_voices/catalog-backups/`. If another
app changed the catalog since it was loaded, saving stops rather than replacing
those changes; reload and reapply the draft edits.

**Add voice** can reference an existing model/speaker or import an ONNX model with
its matching `.onnx.json` sidecar. New entries start with automatic assignment off.
**Remove selected** removes an entry on save; it does not delete the shared model.
Removed stock entries are recorded in `catalog-removed.json`, so running voice
setup again does not restore them. Voice-pack refreshes preserve catalog edits.
At least one catalog entry must remain; all entries may have automatic assignment
disabled if desired.

## Eligibility

Gender is stored as a property independent of the ID prefix:

* `m`: masculine NPCs, or NPCs with unknown gender.
* `f`: feminine NPCs, or NPCs with unknown gender.
* `a`: androgynous; eligible for masculine, feminine, and unknown NPCs.
* `u`: unclassified; eligible only for NPCs with unknown gender.

Each voice has flags for Child, Goblin, Moogle, Elvaan, Galka, Mithra, Tarutaru,
and **Other / no NPC preset**, which includes Hume NPCs. All active NPC presets
must be allowed: Child + Tarutaru requires both flags. With no active preset, the
Other flag applies. Accent is descriptive. An NPC's own gender preference applies consistently across all types.

These restrictions affect automatic assignment only. Manual overrides may use any
catalog entry. If nothing qualifies, the NPC remains silent and the addon shows
an explanation so you can adjust the catalog or choose an override.

## Preview and calibration

Enter a short passage and click **Preview voice**. The preview uses the companion's
Piper backend and audio processing: native Piper pace, the
voice's speed/volume corrections, global controls at 100%, and no NPC race effects.
**Stop** cancels synthesis between chunks or stops playback.

Volume accepts 0–300%; speed accepts 50–200%. Both multiply the normal NPC/global
settings in the companion. Existing gain limiting applies to boosted samples.
The displayed measurements are taken from the final generated PCM:

* **Peak dBFS** and percentage of digital full scale: maximum sample magnitude.
* **RMS dBFS**: average signal level, useful when voices have similar peaks.
* **Duration** in seconds and milliseconds, including the companion's sentence gaps.

These are digital measurements, independent of Windows/device output volume.
Use the same sample passage when comparing voices. Generated previews stay local
under `voice_editor/output/` and are ignored by Git.

## Companion integration

Restart the companion and reload XISpeaks once after installing this update.
After that, saved catalog edits reload automatically when the companion receives
an addon request/dialogue. A line already playing finishes with its original
settings. The addon picker displays edited labels/genders and voice calibration.
Removed manual voice references revert to automatic assignment. Changes to a
voice's audio settings invalidate old automatic-voice approval fingerprints.

The requested clean slate clears NPC manual voice, pitch, speed and approval
fields in the Piper database while retaining race presets, encounter history and
global settings. `scripts/reset_piper_profiles.py` performs this explicitly, with
a complete SQLite backup; it does not reset profiles on every startup. Fresh Piper
registries also skip the old bundled Kokoro manual tuning.

### Repeatable calibration previews

The preview defaults to **Fixed noise / seed**, with seed **42**. Keep the same sample text and seed while comparing voices or adjusting their volume and speed. **New seed** chooses another repeatable take; you can also enter a seed from 0 to 2147483647. The seed stays the same when switching voices during this editor session.

**Zero noise** sets both Piper noise controls to zero and disables the seed field. This removes random variation, but may sound different from normal gameplay. Different voice models still have different delivery even with the same seed.

These controls only affect editor previews, not saved voice profiles or the companion. Each preview reloads its model to reset the random state, so previews incur model-loading time. The measurement label records which mode/seed produced the sample. Repeatability applies to the same model, text, settings and installed runtime; it is not a guarantee across different hardware or runtime versions.
