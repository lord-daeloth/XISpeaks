# Pocket Cloning Studio

A separate Windows app for enrolling volunteer voices into XISpeaks Pocket English 18M (2026-10). It does not train model weights. It exports a reusable voice state, which ordinary players can use with the public model without Hugging Face access.

## Workflow

1. Import WAV, FLAC, MP3, AAC/M4A, Ogg/Opus, or a common video file. For videos with multiple audio tracks, choose the volunteer track. FFmpeg decodes the selection to a local mono 24 kHz working WAV. The original is unchanged. Lossy input remains lossy in quality after conversion. DRM-protected files are not supported.
2. Alternatively, refresh microphones, select an input, and record. The input meter shows peak level; Stop recording ends the take. Recording stops automatically after three minutes.
3. Drag a waveform selection or enter exact start/end times. Use 3–30 seconds of one speaker with complete phrases. Denoising defaults off; Light/Moderate/Strong use FFmpeg FFT noise reduction. Preview original and prepared versions. Normalization targets a −3 dBFS peak with a +24 dB gain cap. Neither processing step repairs clipped audio or separates speakers/background music.
4. Name and create a candidate. Repeat with other excerpts or cleanup settings. Candidates retain their exact reference and processing metadata. Archive drafts removes them from the candidate list while preserving files under the project's archived folder.
5. Select candidates with Ctrl/Shift and audition on the same text and seeds. Up to six lines and four seeds are supported. Auditions use the exact public 18M model, with neutral tuning, and show duration, RMS, and generation warnings. Play an audition to see peak and clipping measurements too. Fixed seeds make comparison consistent; floating-point rounding may still differ slightly.
6. Select one keeper, fill in credit, permission/release notes, gender, accent, NPC eligibility, and a stable ID. Export writes `.safetensors` plus a JSON metadata sidecar. Install adds it to the selected Pocket catalog with the selected automatic-assignment setting. Existing IDs/files can be replaced after a confirmation popup. Assign it in `/xispt voices`, or enable automatic assignment in the catalog editor after review.

## Models and privacy

Model setup is the only step that needs the internet. Accept the terms at https://huggingface.co/kyutai/pocket-tts, then use a Hugging Face read token if not already signed in. The token is handled by Hugging Face's local credential manager, not stored in project/export metadata. Already-cached files are reused. This machine's existing authorized cache can be reused through the developer configuration.

The app uses a pinned gated cloning model and pinned public playback model/tokenizer. No recordings are uploaded. Cloning and auditions run locally on CPU once cached. Only use recordings with the speaker's permission; preserve their credit and agreed distribution conditions.

Projects and recordings are stored in `pocket_studio/output` beside the executable (or under the source checkout). Open `project.json` to resume. Exported profiles contain neither raw audio nor local source paths. Keep project folders private unless you intend to share their recordings. Model-specific states cannot be used with other Pocket models.

Cancel interrupts FFmpeg and streamed auditions. Model loading/encoding and an individual Hugging Face download finish their current stage before cancellation takes effect. Partial work can remain in the private project folder; completed candidates are only listed after their metadata is saved.

## Launch/build

Source: run `START-Pocket-Studio.cmd` in the Pocket checkout. Frozen app: `dist/XISpeaks-Pocket-Studio/START-Pocket-Studio.cmd`. This studio is separate from the player companion and catalog editor.

Build with the Pocket Python environment and `packaging/pocket-studio.spec`. FFmpeg/ffprobe are located in `tools/ffmpeg`, on PATH, or the existing local `C:/ffmpeg/bin` installation. The local standalone build copies these tools and their existing license/readme. It is not a published release ZIP; redistribution must also supply the applicable corresponding source and third-party notices. No gated weights or credentials are part of the application build.

Stable voice IDs are generated from display name, gender, and accent whenever those fields change (Cloud-Steve-2 + m + a becomes am_cloud_steve_2). You can edit the generated ID afterward. Export and catalog installation prompt before replacing an existing voice or metadata. Replacing a catalog voice keeps NPC assignments to that ID but installs the new metadata with the selected automatic-assignment setting.

### Keeping multiple clean sections
Drag a clean section on the waveform (or enter exact start/end times), then click **Add region**. Repeat for other clean sections. Select a row to adjust its times and click **Update selected**, or remove it with **Remove selected**. Regions are outlined in green and saved with the project. They are combined in recording order, excluding all gaps; the combined duration must be 3–30 seconds. Preview buttons and cloning use this combined reference. Very short edge fades reduce clicks at joins. Choose boundaries in natural pauses rather than cutting through words. **Clear regions** returns to the original single-selection workflow.

**Preview current section** plays only the current waveform/start-end selection, even when other regions have already been added. Use it before clicking Add region; short sections under 3 seconds can be previewed too. The combined original/prepared buttons still play the assembled reference.

Start another project with **New session: import…**, or record another clip. Each import creates a separate session folder; previous projects remain available through Open saved project. Audition text is saved automatically across sessions and app restarts. **Reset audition text to default** restores the five built-in lines.

In Export / install, enable **Available for automatic assignment** to include the voice in automatic choices for its checked NPC types. This flag is included in both exports and catalog installations. New sessions start at Candidate 1; reopened projects continue after their existing candidates.
