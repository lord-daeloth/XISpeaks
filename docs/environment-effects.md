# Environment and NPC effects (beta 4)

In `/xis voices`, use **Enable room / NPC effects**, **Effects strength (%)**, and **Environment effect**, then **Apply effects**. Automatic by map selects Stone Hall in Chateau d’Oraguille and Cave in mapped caves/mines; unmapped zones are dry. An explicit environment choice applies everywhere.

Each NPC has an **NPC effect** dropdown, saved immediately. Use map effect inherits the environment, Dry suppresses it for that NPC, and an explicit preset replaces the environment. Preview voice includes the chosen effect and current map. The global off switch disables both map and NPC effects.

Presets: Dry, Small Room, Stone Hall, Cave, Ethereal. Defaults are deliberately subtle; 100% strength means the preset's intended wet/dry mix, not 100% wet audio. Effect processing comes after pitch/speed changes and before voice volume/peak limiting. It streams in 1024-sample chunks (42.7 ms at 24 kHz), without adding a whole-utterance buffering requirement. Each utterance has fresh effect state; stop and zone transitions discard the remainder. Decay tails add up to 0.45 / 1.05 / 1.65 / 2.1 seconds of audible decay, separate from CPU processing cost.

Zone mappings are in `companion/environment_effects.py`, using zone IDs from the local LandSandBoat-derived TravelPlanner catalog. Entire zones share a preset; there is no room geometry detection. NPC overrides and global settings are stored in the existing SQLite metadata table. This first version provides reverberation only; chorus, distortion, and other treatments are future additions.

Benchmark: `python scripts/benchmark_environment.py`. Measures 30 warmed repetitions of six seconds of 24 kHz mono audio, processed in 1024-sample chunks including tail generation. It excludes TTS generation, device buffering and first import cost. The tool can also write comparison WAVs with `--sample PATH`.

## Reviewing voices
The review popup includes Play Again (replays the actual spoken line with fresh synthesis), Reject (tries a different eligible voice and replays that same line), Approve, Edit voice, and Later. Reject choices are temporary until approved; approval waits until the trial has finished playing. If only one eligible voice exists, Reject explains that and keeps the current voice. Replays use the original line and zone, stored only in memory. Stop/zone transitions clear the review session. Existing manual corrections still use the normal edit workflow.

## NPC type tuning
Pocket no longer applies random hash-based pitch or speed offsets. Existing saved automatic offsets are ignored; manual tuning remains intact. Expand **NPC type pitch / speed** in the addon, choose a type, adjust its speed (50–150%) and pitch (−4 to +4 semitones), then **Save type settings**. **Reset type defaults** resets only the selected type. These settings persist in the local companion database and apply to all NPCs with that type enabled, including previews. Multiple types still stack; manual NPC tuning is added on top. Catalog voice calibration and global speed/volume remain unchanged.
