# Windows beta 4 build

Use 64-bit Python 3.12 and packaging/requirements-pocket-build.txt (CPU PyTorch from https://download.pytorch.org/whl/cpu). Player packages need no Python installation.

1. Build `python -m PyInstaller --noconfirm --distpath build/beta4-frozen packaging/companion.spec`.
2. Snapshot the curated catalog into data/pocket-catalog.json; retain referenced .safetensors in the chosen voice directory. The source tree tracks metadata, not model binaries or reference recordings.
3. Run `python scripts/package_release.py --voices PATH`. This stages only referenced states, the public model/tokenizer, frozen executables, notices, and corresponding source archives. It never includes the private HF cache, studio sessions, credentials, or personal runtime databases.
4. Run the staged companion with `--self-test` and `--dry-run` protocol checks. Run the test suite, then `python scripts/package_release.py --zip` to create the app and two voice ZIPs with checksums. Test a fresh extraction of all three.

The helper uses the local Pocket cache for pinned public weights, and build/release-assets for previously collected third-party license/source archives. Configure pocket-development.json with an assets_root only for local development; never distribute it. See packaging/POCKET-BUILDING.md for original asset preparation details.

Build the separate cloning studio into a temporary staging directory, then copy application files into its installed directory. Never rebuild directly over its directory: studio sessions live alongside it and must be preserved.
