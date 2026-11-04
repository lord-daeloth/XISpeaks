# Piper development history and training notes

The addon has graduated to XISpeaks. For current installation, commands and release instructions, use [the README](README.md). The paths and commands below describe the isolated development build.


This checkout is **XISpeaks-Piper**, branch `codex/piper-transition`. The working
Kokoro checkout and installed addon remain separate. This is a source experiment,
not a replacement for the published Windows release.

## Start the trainer

Double-click **START-Piper-Trainer.cmd** in this folder.

1. Load a recording and click **Transcribe locally**, or load a reviewed manifest.
   The latest Halver recording/manifest is preloaded on this development machine.
2. Listen to clips and correct their words/times. Click **Apply clip edits**, then
   tick the transcript review checkbox. Fantasy names particularly need review.
   Save the manifest if you want to reuse it.
3. Select one or more starting checkpoints. **Ryan (US male)** is the default;
   **Alan (UK male)** is also available for comparison. Add other trusted local
   single-speaker medium Piper `.ckpt` files with their eSpeak pronunciation code.
4. Choose saved stages, e.g. `100,300,1000`. These are actual training batches,
   not epochs; each batch updates two optimizers. Each base starts a fresh
   fine-tune from the same recording, with the same seed and low learning rate.
5. Start training. The two bars show progress for the current checkpoint and all
   selected checkpoints. Logs show preparation, synthesis and errors. Cancel stops
   the child process; completed snapshot files remain in that run's directory.
6. In **Compare & export**, select a stage and passage. Play the candidate, the
   untrained base, and your recording. Include unseen dialogue when judging both
   likeness and clear pronunciation. The existing 1,000-batch Halver run is listed.
7. Give the keeper an ID such as `am_halver_new` and export it. Prefixes indicate
   American/British and masculine/feminine: `am_`, `af_`, `bm_`, `bf_`.

Export validates the ONNX graph and synthesizes test speech before registering
it. The model is added to the experimental companion's voice dropdown as a
manual-only choice. Restart that companion to load catalog changes. Existing
voice IDs cannot be overwritten accidentally.

Files are local: runs/manifests/snapshots under `piper_trainer/output/`; exported
voices under `piper_voices/`. The original recording is preserved. Training uses
a mono copy, resampled to 22,050 Hz with one fixed gain targeting -3 dBFS peak.
Automatic transcription is a draft, not a substitute for matching the recording.
There is no validation-loss ranking: the tool intentionally leaves keeper choice
to listening tests. Generator snapshots are not optimizer-resume checkpoints.

## Try the experimental addon

1. Copy **only** `addon/XISpeaksPiper` into the launcher's Ashita addons directory.
   Its folder name is distinct from `XISpeaks`.
2. Unload the regular addon while testing to avoid hearing two companions speak.
3. Run **START-XISpeaks-Piper.cmd** from this checkout. Keep its console open.
4. Load `XISpeaksPiper` in Ashita. Use **`/xisp voices`**, `/xisp test`,
   `/xisp status`, or `/xisp stop`. Long command: `/xispeakspiper`.
5. To return to the release, unload `XISpeaksPiper`, close its companion console,
   and load the normal `XISpeaks` addon/companion.

The Piper addon uses **UDP 49153** and **`piper-runtime/npcs.sqlite3`**. The regular
addon uses 49152 and its own database. No live addon files are deployed by the
trainer or launcher. Do not point the experiment at the regular NPC database.

All automatic NPC assignments use the full English stock catalog: **30 model
families, highest available quality per family, and 1,998 selectable speaker
entries**. Search the voice picker by family or speaker ID, then use Previous /
Next voices to browse 20 results at a time. Multi-speaker selections pass the
actual speaker ID to Piper and share a cached model session. Entries across
LibriTTS and LibriTTS-R can represent the same person; the count is not unique people.

Dataset gender metadata is used for LibriTTS and VCTK; model-card gender is used
where stated. Unclassified voices use `au_`, `bu_`, or `xu_` IDs and can be chosen
manually or assigned to NPCs with unknown gender. They do not enter masculine or
feminine automatic pools. Known VCTK accent groups use `a` (US/Canada), `b`
(UK/Ireland), or `x` (other); a model's language label alone is not proof of an
individual speaker's accent.

The experimental Halver export has been removed. Its source recording and training
runs are preserved. Existing overrides using the removed voice return to automatic
on restart. Other valid manual choices and valid approvals are retained; unapproved
automatic choices are redistributed over the larger pool. Database backups are
saved beside the registry before catalog migration. Cori was upgraded from medium
to high, so previous automatic Cori approvals are cleared.

The initial registry imports the confirmed NPC race catalogue and bundled race,
preference, pitch and speed corrections. It replaces Kokoro voice choices and
clears old approval fingerprints. Existing experimental edits are preserved on
later launches. The catalog flags determine which voices each NPC type can use. Race pitch and speed effects still apply. Kokoro blending is disabled because these independent
Piper models cannot use Kokoro voice-vector blends. Contribution upload is disabled so these
experimental profiles cannot enter the Kokoro catalogue by mistake.

Playback uses CPU ONNX, native speed control, 24 kHz resampling for the existing
Rubber Band/Librosa pitch effects, global volume, 300 ms sentence gaps, and 180 ms
dash gaps. `Hm` normalization is retained. Kokoro's phoneme-specific stutter
patch is not used; Piper pronunciation/pacing will need listening tests in game.
At most two voice models are cached in memory. Training and playback are separate.

## Model sizes on this machine

| Artifact | Size (MiB) |
| --- | ---: |
| Kokoro shared model | 312.1 |
| All 28 installed English Kokoro voice packs | 14.0 combined |
| Piper Alan medium | 60.3 |
| Piper Cori high | 108.9 |
| Piper Lessac high | 108.6 |
| Piper Ryan high | 115.2 |
| Previously exported Halver (1,000 batches) | **60.6** |
| Halver generator-only training snapshot | 90.5 |
| Original full Ryan training checkpoint | 806.7 |

Kokoro shares one large model across small voice packs. Piper generally carries
a full model per voice. A multi-gigabyte English collection is not required:
install just the voices used. The complete highest-quality English selection occupies about 2.26 GB (2.11 GiB). These figures exclude Python/runtime libraries.
Many bespoke NPC voices would therefore be better distributed as optional packs.
CUDA/PyTorch training dependencies are not needed for a future player-only build.

## Developer environment

This machine reuses the already-tested training environment and downloaded
assets read-only from the original checkout through ignored
`piper-development.json` (`{"assets_root":"C:/Projects/CatsEyeXi-Addons/XISpeaks"}`).
The new code, runs, registry and exported models live in this checkout. With no
local config, assets are expected under this checkout instead.

The native Windows training setup is documented in
[the training pilot](experiments/piper_training/README.md): Python 3.12,
PyTorch 2.7.1+cu128, Piper 1.8.0, Lightning 2.6.6, and Piper source revision
`10880972db9e0aca101fed350eadf8f49deefe9f` with its alignment extension compiled.
A CUDA GPU is required by this bounded trainer. It is not a standalone EXE yet.
Local transcription additionally uses the cached faster-whisper/base.en pilot.

Experimental extra packages (installed outside the stable Python environment):

```powershell
& "$assets/build/piper-train-env/Scripts/python.exe" -m pip install --target build/export-deps --no-deps onnx==1.17.0
& "$assets/build/piper-train-env/Scripts/python.exe" -m pip install --target build/playback-deps --no-deps PyAudio==0.2.14
& "$assets/build/piper-train-env/Scripts/python.exe" piper_trainer/setup_voices.py
```

Set `$assets` to the assets checkout first. Setup downloads the highest-quality English models and their upstream model cards.
Files are verified against revision-pinned repository hashes. Speaker counts/maps
come from the actual downloaded configurations: the upstream voices.json index
currently overstates LibriTTS-R speaker count. Recordings, weights and databases are
ignored by Git. The stable release packager remains for Kokoro; do not use it to
publish a Piper release yet.

Model licensing is separate from the GPL app. In particular, the Ryan base model
card identifies a CC BY-NC-SA 4.0 dataset; this prototype does not establish that
a derived volunteer voice is unrestricted. Preserve the relevant base model
cards and resolve redistribution terms before publishing voice packs.

## Piper pacing and Moogle presets

At 100% global speed, Piper uses the catalog speed multiplied by the NPC speed setting.

* Goblin: **+3.0 semitones**, **115%** relative speed.
* Child: **+1.0 semitone**, **100%** relative speed (no speed increase).
* Moogle: **+1.5 semitones**, **107.5%** relative speed.

The Moogle toggle is in `/xisp voices`. The companion imports
`data/moogle_associations.json` once, enabling it for 37 names using explicit
Moogle NPC names or consistent Moogle model appearances in the pinned
LandSandBoat catalog. This includes named Moogles such as Kupofried and Monsieur
Kupont. Placeholder models and object/event names are not treated as race evidence.
`scripts/build_moogle_catalog.py` reproduces this overlay. Manual voices and tuning
are retained, and later user changes to the toggle survive restarts. The database
is backed up as `.before-moogles.bak` before the overlay/settings migration.

## Voice catalog editor

Launch **START-Voice-Catalog.cmd** to add/remove voices, edit labels and gender
(including androgynous), control NPC-type eligibility, and calibrate per-voice
speed and volume. Text previews report peak/RMS digital level and exact duration.
See the [catalog editor guide](voice_editor/README.md) for save/reload behavior.
