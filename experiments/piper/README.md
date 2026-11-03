# Piper vs Kokoro: local CPU pilot

This is a playback experiment, not a switch to Piper or a trained volunteer voice.
It compares three existing Piper voices against two Kokoro voices using identical
NPC dialogue. Outputs and models remain local; the addon, companion, and Studio
are unchanged.

## Reproduce (Windows source checkout)

Use the existing project `.venv`. Dependencies are isolated in a target folder:

```powershell
.\.venv\Scripts\python.exe -m pip install --target build/piper-deps piper-tts==1.8.0 onnxruntime==1.31.1 numpy==2.5.4
.\.venv\Scripts\python.exe experiments/piper/download.py
.\.venv\Scripts\python.exe experiments/piper/compare.py
```

Kokoro's existing model/English voices must be staged under
`build/assets/models/hub`. The comparison creates `experiments/piper/output` and
refuses to overwrite an existing run. Rename a previous output before rerunning.
Open `output/index.html` for listening and `output/results.json` for measurements.

Each voice runs in a separate process. CPU only; ONNX Runtime default thread
policy for Piper, four PyTorch intra-op threads for Kokoro. Load/init timing
includes engine imports after NumPy, model loading and voice loading, but excludes
process startup. First-call time uses a short warm-up sentence. Each actual passage
has three warmed sequential measurements. WAV writing is outside measured time.
First chunk is availability of generated PCM, not sound-device playback latency;
the engines' chunk boundaries differ. Median RTF is synthesis time divided by
generated audio duration. These are practical configurations, not a controlled
equal-thread benchmark or an end-to-end companion measurement.

No Rubber Band, stutter corrections, or custom pause insertion are used. Different
voices have different pacing and loudness. Audio is saved at each engine's native
sample rate (22,050 Hz Piper, 24,000 Hz Kokoro). All audio chunks are retained.

## Custom voice training implications

Piper has an official [training workflow](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/TRAINING.md)
for recordings paired with exact transcripts, fine-tuning an existing checkpoint,
and exporting an ONNX voice for playback. Training uses a PyTorch environment
separate from this inference experiment; WSL/Linux is a likely setup to evaluate.
An exported `.onnx` inference file is not the training `.ckpt` checkpoint.

The published small-dataset examples are around 0.9–4 hours. Those examples are
not a minimum requirement, but they do not establish that twenty seconds, or even
a few minutes, will preserve an arbitrary volunteer's identity. A deliberately
small-data training test would need held-out dialogue and explicit failure
criteria before collecting more recordings or integrating a new engine.

## Model provenance

The downloader saves each upstream MODEL_CARD alongside its model in
`build/piper-models`. The models are from
[rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices):

- `en_GB-alan-medium`: UK English, medium; model card links dataset license.
- `en_US-lessac-high`: US English, high; model card links Lessac dataset terms.
- `en_US-ryan-high`: US English, high; model card lists CC BY-NC-SA 4.0.

These are local evaluation downloads, not bundled release assets. Engine licensing
does not replace individual model/dataset licensing. Code uses the official
[Piper Python API](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/API_PYTHON.md).
