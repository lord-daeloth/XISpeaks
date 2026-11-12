# Pocket test build

Windows x64, Python 3.12. Use an isolated environment with
`requirements-pocket-build.txt`; obtain the CPU PyTorch wheel from the official
PyTorch CPU index. This is a source-build workflow, not a player requirement.

1. Configure `pocket-development.json` with `assets_root` pointing to the local
   development assets (Pocket environment/cache, Rubber Band, original voice
   tests and Piper catalog metadata). Run `scripts/setup_pocket.py` to seed the
   stock states and two local Halver volunteer states.
2. Run `scripts/expand_pocket_voices.py`. This maintainer step needs access to
   the cloning model in the developer cache and network access to the pinned
   public voice reference collection. References are cached under build/;
   converted 18M states and provenance are under pocket_voices/.
3. Run PyInstaller with `packaging/pocket.spec`, `--distpath build/pocket-frozen`
   and `--workpath build/pocket-pyinstaller`.
4. Put the CC0-1.0, CC-BY-4.0, CC-BY-NC-4.0 license texts and the pinned public
   model card under build/pocket-license-texts/. The packaging script also
   includes the existing Rubber Band and libsndfile source archives from the
   sibling XISpeaks-Piper build/piper-source directory.
5. Run `scripts/build_pocket_release.py` to create the test staging directory.
   Run its EXE with `--self-test --all-voices`. If voices were still exporting
   when staged, use `--refresh-voices` before testing the full catalog.
6. Run `scripts/review_pocket_smoke.py` to record warnings and make flagged voices
   manual-only, then `scripts/build_pocket_release.py --refresh-voices`.
7. Run `scripts/build_pocket_release.py --zip-only`, extract the ZIP into a fresh
   directory, and test that extracted EXE and its localhost UDP protocol.

The packaged model and tokenizer come exclusively from the public model repo.
The frozen companion uses absolute local model paths and offline HF mode.
No credentials, private HF cache, source reference WAVs, or personal NPC database
are staged. Runtime test artifacts are excluded from the ZIP. Generated voice
files are model-specific: do not mix them with a different Pocket model/revision.

This is an all-voices test package, including separately licensed noncommercial
voice profiles. It is not yet a public GitHub release. Human listening review
and per-voice calibration are separate from the automated synthesis check.
