XISpeaks - portable Windows x64 release

Windows x64 only. Linux is not currently supported; a Linux companion may be
explored later. Download updates from https://github.com/lord-daeloth/XISpeaks/releases
XISpeaks code: GPL-3.0-or-later (see LICENSE). Third-party licenses remain separate.

The companion MUST be running for speech to work. Loading the addon alone is
not enough: run START-XISpeaks.cmd and keep the companion open while playing.

1. Extract the entire XISpeaks folder into your Ashita addons directory.
   Vanacore example: Vanacore\addons\ashita\XISpeaks
2. Double-click START-XISpeaks.cmd. Keep its console open while playing.
   The first start takes longer while the audio effects initialize.
3. In game: /addon load XISpeaks
   Voice editor: /xis voices

Optional CatsEyeXI Launcher auto-start:
1. Open CatsEyeXI Launcher > Settings.
2. Scroll down to Companion Apps.
3. Add START-XISpeaks.cmd from your installed XISpeaks folder.
4. Check Auto-Start for that entry.
The companion will launch when you open the launcher. You must still load the
addon in game. Do not start a second companion manually if it is already running.

Voice review (optional, off by default): in /xis voices, enable "Review unapproved
voices". After a named NPC finishes speaking, a small window offers Approve,
Edit voice, or Later. Close the editor to see pending prompts. Approvals track
the NPC's current voice/blend, pitch and speed; changes to these require review
again. Saved manual voices/tuning count as reviewed. Global audio settings do not
invalidate approvals. Use the Unreviewed voices filter to browse outstanding NPCs.
Later/Edit suppress another prompt until that NPC has been silent for 60 seconds,
or you zone/restart. Interrupted, muted and failed speech does not request review.
During cutscenes XISpeaks temporarily reveals Ashita's ImGui layer while a prompt
or editor is open. Other ImGui windows may also appear; visibility is restored
when XISpeaks closes. No keyboard focus is automatically requested.

Want to contribute? We need voice approvals and manual corrections to improve
the catalogue. In /xis voices, click Contribute voices, review the summary, then
Open GitHub submission. Sign into GitHub and review the prefilled issue. If a JSON
file is selected in Explorer, drag it into the issue and wait for the upload.
Click Submit on GitHub to finish. Small contributions are embedded in the issue.
Only NPC voice settings are exported, not chat, history, player identity or global
audio settings. Submissions are public and reviewed before inclusion. Open export
folder lets you save/share the JSON manually. Git/API tokens are not required.

Python, Kokoro, all 28 English voices, Librosa and Rubber Band R3 are included.
No Python installation, API key, model download or internet connection is needed.
Keep the companion folder and its _internal directory together.
Close the companion with Ctrl+C. Run only one companion at a time.

Settings and NPC choices are saved in companion\npcs.sqlite3. Back up that file.
For optional advanced settings, copy companion\config.example.json to config.json
in the same directory. The defaults work without it.
Upgrades: close the companion, then extract over the existing addon. The archive
does not contain personal config.json or npcs.sqlite3 files, so they are retained.
The initial database contains reviewed NPC defaults and the author's saved voice,
blend, pitch/speed, gender and race corrections plus voice approvals, without personal history.
Existing databases are not replaced or automatically re-imported on upgrade.

Diagnostics: START-XISpeaks.cmd --self-test
This produces two test WAVs beside the EXE, without playing through speakers.
It checks offline model loading, blending, Rubber Band and Librosa.

Third-party license notices are in licenses, source/data, and companion/_internal.
Source and build scripts are in source. This is an unsigned Windows executable.
