XISpeaks - portable Windows x64 release

1. Extract the entire XISpeaks folder into your Ashita addons directory.
   Vanacore example: Vanacore\addons\ashita\XISpeaks
2. Double-click START-XISpeaks.cmd. Keep its console open while playing.
   The first start takes longer while the audio effects initialize.
3. In game: /addon load XISpeaks
   Voice editor: /xis voices

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
