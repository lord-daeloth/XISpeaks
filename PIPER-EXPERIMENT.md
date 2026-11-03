# Experimental Piper branch (Windows only)

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

All automatic NPC assignments use stock Piper voices: Ryan (US masculine),
Lessac (US feminine), Alan (UK masculine), and Cori (UK feminine). Their IDs are
`am_ryan`, `af_lessac`, `bm_alan`, `bf_cori`. Custom voices are manual overrides.
The exported Halver voice is already available locally as **`am_halver`**.

The initial registry imports the confirmed NPC race catalogue and bundled race,
preference, pitch and speed corrections. It replaces Kokoro voice choices and
clears old approval fingerprints. Existing experimental edits are preserved on
later launches. Elvaan still prefer British voices, Mithra feminine voices, and
race effects still apply. Kokoro blending is disabled because these independent
Piper models cannot use Kokoro voice-vector blends. Child has pitch/speed effects
but no special stock-voice subset yet. Contribution upload is disabled so these
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
| Piper Cori medium | 60.6 |
| Piper Lessac high | 108.6 |
| Piper Ryan high | 115.2 |
| Halver, trained for 1,000 batches, exported for playback | **60.6** |
| Halver generator-only training snapshot | 90.5 |
| Original full Ryan training checkpoint | 806.7 |

Kokoro shares one large model across small voice packs. Piper generally carries
a full model per voice. A multi-gigabyte English collection is not required:
install just the voices used. The four stock voices here total about 344.7 MiB;
adding Halver makes about 405.2 MiB. These figures exclude Python/runtime libraries.
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

Set `$assets` to the assets checkout first. Setup downloads only the four stock
models and their upstream model cards. Recordings, weights and databases are
ignored by Git. The stable release packager remains for Kokoro; do not use it to
publish a Piper release yet.

Model licensing is separate from the GPL app. In particular, the Ryan base model
card identifies a CC BY-NC-SA 4.0 dataset; this prototype does not establish that
a derived volunteer voice is unrestricted. Preserve the relevant base model
cards and resolve redistribution terms before publishing voice packs.
