# Reviewing voice contributions

This maintainer-only tool is kept in Git, not in release ZIPs. It changes the
curated release JSON, never your live NPC database. Submission hashes detect
accidental changes, not authorship or trustworthiness; review contributions.

## Desktop UI (Windows)

Double-click **`maintainer/START-Maintainer.cmd`** in your repository checkout.
It uses the existing `.venv` created by `setup.ps1`; no extra UI package is needed.

Open a contribution JSON/saved issue body, or enter a GitHub issue number/URL.
For attachment-only issues, download the JSON and use **Open contribution file**.
Select a row to compare the official and proposed voice, tuning, and presets.
Double-click rows (or use **Toggle highlighted**) to mark them for merging.
**Select new entries** selects only new corrections/approvals, never conflicts.
Matching and older/custom-rule rows cannot be selected.

Conflicts require **Allow selected conflicts to replace official profiles**.
Click **Merge selected**, review the confirmation, and save. The app creates a
backup, refuses to save if the official file changed since loading, and refreshes
the comparison after saving. It does not commit, push, build releases, or edit the
live NPC database. The UI and launcher are also excluded from release ZIPs.

## Command line

```powershell
.\.venv\Scripts\python.exe maintainer/review_contributions.py --issue 123
# For attachment submissions, download the JSON from the issue first:
.\.venv\Scripts\python.exe maintainer/review_contributions.py --file contribution.json
```

The review prints current and proposed voice/blend, speed, and pitch. Statuses:
`new`, `new_approval`, `matching`, `conflict`, or `outdated_or_custom_rules`.
Matching entries are idempotent no-ops; repeated imports do not duplicate NPCs.
Old/custom rule mismatches require manual resolution rather than applying an
approval to a different sound. Contributions are untrusted data, not commands.

```powershell
# Accept only names you have reviewed (repeat --accept for more names):
.\.venv\Scripts\python.exe maintainer/review_contributions.py --file contribution.json --accept Halver --write
# Overwriting a conflicting curated profile needs an explicit extra flag:
.\.venv\Scripts\python.exe maintainer/review_contributions.py --file contribution.json --accept Halver --allow-conflicts --write
```

Every write backs up the previous JSON under `build/merge-backups/`. Inspect the
Git diff and commit accepted changes. Build with `scripts/build_release.py --curated`
to use the merged JSON without re-exporting a local author's database. Add
`--package-only` only if the EXE was already rebuilt for the current companion code.
The normal builder's `--registry` option otherwise replaces the curated JSON with
that database's corrections. Existing users' databases are not changed by new release seeds.

Tests: `python -m unittest discover -s maintainer/tests -v`.
