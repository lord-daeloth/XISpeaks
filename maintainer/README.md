# Reviewing voice contributions

This maintainer-only tool is kept in Git, not in release ZIPs. It changes the
curated release JSON, never your live NPC database. Submission hashes detect
accidental changes, not authorship or trustworthiness; review contributions.

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
