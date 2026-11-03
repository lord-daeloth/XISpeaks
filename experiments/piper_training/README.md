# Piper volunteer likeness pilot

## Repeating with a new recording

The runner accepts a reviewed JSON manifest and a separate output directory:

```powershell
.\build\piper-train-env\Scripts\python.exe -u experiments/piper_training/run.py --manifest build/piper-training/new-manifest.json --output experiments/piper_training/output-new-reference
```

A manifest specifies `source` (absolute WAV path), `segments` (ordered,
nonoverlapping `start`/`end` seconds and exact `text`), `texts` (first audition is
training dialogue, remaining auditions are unseen), `stages` (ascending actual
batch counts), and optional `peak_db` (-20 to -1 dBFS). It validates boundaries
before writing output, averages stereo to mono, applies one fixed gain to the
whole recording, then resamples clips. It never overwrites the source or an
existing output directory. Preparation tests cover gain, stereo conversion,
source preservation, resampling and invalid boundaries.

The second run uses the supplied 93.6-second `new-reference.wav`, 14 reviewed
paragraph clips totaling 87.18 seconds, a -3 dBFS peak target (+9.81 dB gain), and
100/300/1,000-batch snapshots. It starts afresh from Ryan, not the first adapted
model. The merchant/watchtower passages from the recording instructions are
reserved for testing and are absent from training. Both data amount and levels
changed, so this does not isolate recording volume as the cause of any difference.
`dataset.json` records preprocessing and the actual segment transcripts/bounds.

The sections below describe the original short-recording pilot and environment.

Separate, local GPU fine-tuning experiment. It does not modify the companion,
addon, Studio, official NPC profiles, or original recording. It starts from
**Ryan medium (American male)**, not Alan/British, at the user's request.

## Dataset and limits

Input is the user-selected `voice_studio/output/bm_halver-e000cbe7/reference.wav`:
19.86 seconds containing four unique sentences read twice. The `bm_` filename
is an old Studio label; this experiment uses **en-us** phonemization.
The transcript was confirmed by the user in chat. Word boundaries came from
local Whisper alignment; the script uses sentence-level crops with silence
margins and resamples them to 22,050 Hz. The resulting eight WAV clips and exact
transcripts are saved under the ignored output folder.

No audio is held out: splitting repeated sentences into train/validation would
give misleading validation evidence. Instead the listening report includes one
training passage and two **unseen text** passages. This is not an independent
speaker-similarity benchmark or a validated production training recipe.

We train the official VITS generator and discriminator with fresh optimizers,
batch size 2, constant 1e-5 learning rates, FP32, seed 1234, for **300 actual
batches** (Lightning counts two optimizer steps per batch). Audio snapshots are
saved at 0, 25, 100, and 300 batches. These deliberately bounded settings probe
whether tiny-data adaptation changes identity; they do not establish convergence.
The original checkpoint is loaded strictly, preserving architecture and weights.

Generation uses the same inference seed (777), noise parameters and speed at
every snapshot, with 200 ms between synthesized sentences. It uses the actual
PyTorch generator, not an ONNX export. No pitch effects are applied. Compare
likeness, clarity, missing words, and consistency on unseen lines—not just on the
recorded passage. No improvement is asserted from training loss.

## Environment

Tested on native Windows with an RTX 4070 SUPER (12 GB), Python 3.12,
PyTorch 2.7.1+cu128, Piper Windows wheel 1.8.0, Lightning 2.6.6, and current
upstream Piper training source at `10880972db9e0aca101fed350eadf8f49deefe9f`.
All training dependencies live in `build/piper-train-env`, not `.venv`.

Prepare an isolated venv and install:

```powershell
.\.venv\Scripts\python.exe -m venv build/piper-train-env
.\build\piper-train-env\Scripts\python.exe -m pip install torch==2.7.1 --index-url https://download.pytorch.org/whl/cu128
.\build\piper-train-env\Scripts\python.exe -m pip install piper-tts==1.8.0 lightning==2.6.6 "jsonargparse[signatures]" cython librosa pysilero-vad tensorboard tensorboardX soundfile
```

Clone [Piper](https://github.com/OHF-Voice/piper1-gpl) into `.reference/piper`
and check out the revision above. Build the monotonic alignment extension with
the training venv's Python and installed Visual Studio C++ build tools:

1. Change to `.reference/piper/src/piper/train/vits/monotonic_align`.
2. Run `setup.py build_ext` with the training Python.
3. Copy the compiled `core*.pyd` under its `build` directory into a new child
   directory named `monotonic_align` (the upstream import location).

The runner imports upstream training/configuration code alongside the wheel's
native Windows phonemizer. This avoids changing/installing system-wide libraries.
The trusted upstream Linux checkpoint's PosixPath metadata is temporarily adapted
for Windows while loading; do not use this loader for untrusted submissions.

Download the official checkpoint
[`en/en_US/ryan/medium/epoch=4641-step=3104302.ckpt`](https://huggingface.co/datasets/rhasspy/piper-checkpoints/tree/main/en/en_US/ryan/medium)
to `build/piper-training/ryan.ckpt`, retaining its MODEL_CARD. Ryan's model card
lists CC BY-NC-SA 4.0 dataset licensing; this experiment does not distribute the
checkpoint or derived weights in Git/releases.

Run from the repository root:

```powershell
.\build\piper-train-env\Scripts\python.exe -u experiments/piper_training/run.py
```

The output directory must not already exist; rename an earlier run to retain it.
Open `experiments/piper_training/output/index.html` for the listening comparison.
Generator-only snapshots are saved for future experiments; they are **not**
resumable optimizer checkpoints or drop-in `.onnx` voices. `results.json` records
settings, stage timing and source/checkpoint SHA256 hashes. Recordings, models,
training caches and output are ignored by Git and remain local.
