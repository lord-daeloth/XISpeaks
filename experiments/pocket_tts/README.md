# Pocket TTS experiment

Open output/index.html after running the comparison to listen and inspect timings. This is a local experiment using Pocket TTS 4.0.1, four English model configurations, four sample stock voices per model, and three Piper stock voices.

## Reproduce on Windows

Create build/pocket-env with Python 3.12. Install CPU PyTorch from https://download.pytorch.org/whl/cpu, then install pocket-tts, scipy and psutil. Exact installed versions are recorded in output/sizes.json.

1. Run download.py with build/pocket-env/Scripts/python.exe to download model weights and all 27 built-in voice states into build/pocket-hf. The official library falls back to public stock-voice weights when cloning weights are unavailable.
2. Run sizes.py in that environment to inventory actual files and compress representative runtime/model archives.
3. Run compare.py in that environment. Piper workers use build/piper-train-env/Scripts/python.exe and the existing piper_voices directory.
4. Open output/index.html.

Comparison runs are sequential, with no downloads during timed inference. Samples are native engine output, without the addon’s per-voice calibration, NPC presets or effects. The report records cold-process initialization, first-call warm-up, steady-state synthesis time, first-chunk availability and real-time factor. Pocket uses fixed torch seed 42. Timings can vary with system load.

Completed model results are reused on rerun. To obtain a fresh measurement, move output to a separate dated folder before rerunning.

Package estimates include one model, all 27 named presets for that model, and the measured CPU Python runtime/dependencies. They exclude the broader voice-recording repository and cloning-capable weights. These are file-size estimates, not a tested Windows frozen companion. Voice licenses vary by source; review the upstream model cards before distributing them.

Sources:
- https://github.com/kyutai-labs/pocket-tts
- https://huggingface.co/kyutai/pocket-tts
- https://huggingface.co/kyutai/pocket-tts-without-voice-cloning
- https://huggingface.co/kyutai/tts-voices

## Volunteer likeness comparison

From the project root, run LOGIN-Pocket-TTS.cmd after accepting access at https://huggingface.co/kyutai/pocket-tts. Paste a Hugging Face read token into the local login prompt. The isolated Hugging Face credential/cache directory is build/pocket-hf, which is excluded from Git.

Run START-Pocket-Likeness.cmd to generate and open the local comparison. This uses the improved 93.6-second Halver reference in experiments/piper_training/output/new-reference.wav and the previously reviewed sentence boundaries. It compares 13.00-second and 26.35-second prompts for both models, using three fixed seeds per line. Two comparison sentences have actual recorded references outside the conditioning clips. Two other lines have baselines from the previous Piper 1,000-step test.

The script requires the official cloning-capable weights and refuses a silent fallback to stock voices. Voice conditioning and synthesis run locally. The input recording is retained. Generated audio, reports and model-specific voice states are under output/likeness and excluded from Git. Raw durations and initialization/conditioning costs are stored in results.json.
