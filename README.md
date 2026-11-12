# XISpeaks

<p align="center"><img src="assets/branding/xispeaks-logo.png" alt="XISpeaks logo" width="280"></p>

XISpeaks reads Final Fantasy XI NPC dialogue aloud using local **Pocket TTS English 18M** voices. The Ashita addon sends NPC dialogue to a companion running on your PC. **Beta 3 is Windows x64 only.** Works with Ashita, including through VanaCore; neither VanaCore nor the CatsEyeXI Launcher is required.

## Install beta 3

1. Download the **app ZIP and both voice ZIPs** from [the latest release](https://github.com/lord-daeloth/XISpeaks/releases/latest). Extract all three into the same Ashita addons directory. They combine into one **XISpeaks** folder. With CatsEyeXI/VanaCore, the usual path is `D:\Games\CatsEyeXi\catseyexi-client\Vanacore\addons\ashita\XISpeaks`; standalone Ashita users should use their own `addons\XISpeaks` directory.
2. Run **START-XISpeaks.cmd** inside that folder and keep the companion running. The package includes the EXE, runtime, public model, tokenizer, and curated voices. No Python installation, Hugging Face account, model access agreement, or first-run voice download is needed for playback.
3. In game: `/addon load XISpeaks`, then `/xis test`. Use `/xis voices` to edit NPC voices, `/xis stop` to interrupt speech, and `/xis status` to check the connection. The default local UDP port is 49152.

**CatsEyeXI Launcher auto-start:** Settings → Companion Apps → add **START-XISpeaks.cmd** → check **Auto-Start**. The companion then starts when the launcher opens.

**Upgrading:** Close the old companion and unload its addon. Back up the old XISpeaks folder, then extract into a fresh folder; do not overlay a Piper installation. Piper voice assignments cannot be reused with Pocket. From the Pocket test build, unload XISpeaksPocket and copy only `companion/pocket-runtime/npcs.sqlite3` (with the companion closed) into the new `companion/pocket-runtime` directory if you want your personal history/overrides. Do not copy the old voice folder over the curated beta catalog. The addon is now named XISpeaks and uses `/xis` instead of `/xispt`.

**Uninstall:** `/addon unload XISpeaks`, close the companion, remove its launcher auto-start entry if configured, and delete the XISpeaks folder. Back up `companion/pocket-runtime` first if keeping personal settings.

## Want to contribute?

We need voice approvals, NPC corrections, and volunteer voices to improve the catalog. Enable voice review in `/xis voices`; approve suitable automatic voices or make manual corrections. Keep your `companion/pocket-runtime/npcs.sqlite3` backed up. The old Kokoro submission uploader is not enabled for Pocket; for now, [open an issue](https://github.com/lord-daeloth/XISpeaks/issues) with the NPC/voice IDs and proposed correction. Do not attach your entire runtime database publicly.

For custom voices, use the separate [Pocket Cloning Studio](pocket_studio/README.md). Export the voice and metadata together, with accurate source/credit and permission notes. Creating clones needs access to the gated cloning model; playing exported voices uses only the bundled public model. The studio and maintainer tools are source workflows, not included in the player ZIPs.

## Voices and controls

Beta 3 ships the curated catalog, including custom profiles, calibrations, NPC overrides and approvals. Only voice files referenced by that catalog are packaged. Gender, automatic-assignment eligibility, and NPC-type flags control automatic choices. The addon includes unrestricted and NPC-rule-aware random voice buttons; both save a manual override. Pitch, speed, volume, NPC presets and cutscene review remain available.

Run **START-Voice-Catalog.cmd** to edit voices, preview them, and change eligibility/calibration. The editor backs up the catalog before removing entries with missing files. Multi-select removal keeps files on disk; saving applies the catalog edit.

Playback is local. Some included voices carry noncommercial licenses; others have separate attribution or permission notes. **Public availability alone is not a redistribution license.** See the release's **VOICE-LICENSES.md**, catalog metadata and [third-party notices](packaging/THIRD-PARTY.md) for the recorded terms; custom reference rights remain separate from the program license.

## Source and building

See [the Windows build guide](packaging/BUILDING.md). The project is GPL-3.0-or-later; dependencies, models and voices have their own licenses. The previous Piper release remains available as v1.0.0-beta.2. Historical engine/training tools remain in the source tree for reference and are excluded from the player package.
