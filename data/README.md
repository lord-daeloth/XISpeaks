# LandSandBoat NPC voice catalog

Source revision: `81a13ab0febcace751017044529ec77773180ad1`

Generated from the upstream LandSandBoat NPC definitions; this is a starting catalog, not a complete list of speaking characters or CatsEye-specific content.

## Coverage

- 37,870 entity records inspected (YAML plus remaining legacy SQL).
- 6,829 normalized display-name groups retained, including unclassified objects.
- 3,658 confirmed names eligible for import; 67 partial, 66 conflicting, and 3,038 unknown groups retained for review.
- No gender/age guessed from names. No inference of adulthood from race. Child flags are not generated.

## Sources and rules

- `data/zones/*/npcs.yaml`: display names, IDs, model type, equipped race, and model ID. YAML takes precedence over duplicate legacy SQL IDs.
- `sql/npc_list.sql`: legacy NPC records still in upstream. SQL literals are parsed, never executed.
- `scripts/enum/race.lua`: equipped race codes 1-8 identify Hume/Elvaan/Tarutaru masculine/feminine, Mithra, and Galka.
- `src/common/mmo.h`: look layout (16-bit model type followed by face/race or fixed model ID); legacy data decoded little endian.
- `data/ecosystems.yaml`, zone mob templates, and `sql/mob_pools.sql`: fixed models associated exclusively with the Goblin family. Ambiguous models and placeholder model 50 are excluded.
- Fixed NPC models without those mappings, including many important story NPCs and child models, remain unknown. Codes 29-31 are deliberately not interpreted without a verified definition.
- A name is confirmed only if every retained appearance has a matching known classification. Different known races/genders produce a conflict; unknown alternate models produce partial status.
- Generic names with conflicting appearances need zone-aware runtime matching. Current XISpeaks identifies speakers by normalized display name only.

## Import behavior

`suggested_voice` is a deterministic starter voice from the stock pool. Import recomputes it using the user-configured pool and the confirmed gender preference.
Only confirmed names are imported. Existing manual voice/tuning and race flags can be replaced with `--overwrite`; Child, mute, encounters, and last-heard timestamps remain intact. Global audio settings remain intact. Unheard entries have zero encounters and do not appear in Recent.
A timestamped SQLite backup is made before every import. Import is explicit and does not run on startup, so subsequent user edits remain in control.

```powershell
.\.venv\Scripts\python.exe scripts/build_npc_catalog.py .reference/landsandboat
.\.venv\Scripts\python.exe scripts/import_npc_catalog.py
# Add --overwrite only to replace existing confirmed assignments.
```

The generator requires PyYAML (already available in this development environment). The importer uses the existing companion dependencies only.

## Confirmed coverage by race

- elvaan: 922
- galka: 283
- goblin: 90
- hume: 930
- mithra: 362
- tarutaru: 614

## Attribution

Derived from https://github.com/LandSandBoat/server at the pinned revision above. Upstream copyright and GPL terms are retained in `LandSandBoat-LICENSE`. Per-entity source paths and Goblin-model evidence are included in the JSON.

## Reviewed Goblin supplement

The FFXIclopedia [Goblin NPC category](https://ffxiclopedia.fandom.com/wiki/Category:Goblin_NPCs), reviewed October 25, 2026, supplies explicit race evidence for 79 speaker names in `goblin_npc_overrides.json`. The category contains 80 pages: `Trust: Fablinix` duplicates Fablinix, and `Goblin Grenadier (NPC)` is normalized to its spoken name. Category membership does not establish gender, so preference remains unknown.

The generator applies these exact-name overrides after model classification and preserves the previous model result and source records. It does not classify additional NPCs solely because they share model 85. This raises confirmed coverage by 73 names (six were already confirmed), to 3,201, including 90 Goblins. Twelve wiki names are absent from the pinned LandSandBoat catalog but are still useful name-based seeds.

To apply only this supplement, without resetting unrelated NPC choices:

```powershell
.\.venv\Scripts\python.exe scripts/import_npc_catalog.py --catalog data/goblin_npc_overrides.json --overwrite
```

This makes a fresh database backup and replaces the listed NPCs' voice/tuning defaults and race presets, retaining Child, mute, and encounter history. No addon changes or restart are needed; refresh the voice editor.

## Elvaan assignments

Confirmed Elvaan profiles now include the Elvaan preset and a British suggested
primary voice. Runtime automatic assignment gives them a 75% chance of a blend
with a same-gender partner of either accent, retaining 60-80% British primary.
The targeted rollout enabled this flag for 922 existing confirmed Elvaan entries
without replacing manual overrides or other saved fields.

## Four-race wiki reconciliation (October 25, 2026)

All 15 supplied category pages were read in-browser: 387 Galka, 748 Tarutaru,
1,024 Elvaan and 454 Mithra page entries. The 2,613 raw entries include Trust and
(A)/(S)/(UC) variants. Exact and unique punctuation-normalized matches resolved
451 additional catalog names: 78 Galka, 101 Tarutaru, 177 Elvaan and 95 Mithra.
1,797 unique names already matched confirmed records. No fuzzy suggestions were
applied; 17 conflicting names and 111 unmatched page entries remain for review.

The registry import added 428 entries and updated 23, preserving manual voice,
manual/base tuning, known preferences, Child flags, mute and encounter history.
A timestamped SQLite backup precedes the import. Race defaults can change the
effective sound, but the saved tuning is retained. No addon reload is required.

See [the readable review](wiki_race_review.md), `wiki_race_review.json`,
`wiki_race_overrides.json`, and `wiki_race_pages.json` for decisions and sources.
The generator now reapplies this supplement on regeneration. To import just race
information without resetting custom settings, use `--race-only` with the supplement.
The original coverage numbers above describe earlier passes where noted; current
combined coverage is 3,652 confirmed names out of 6,829 named groups.

## User-reviewed conflict resolution

`user_npc_overrides.json` is applied after model and wiki sources. It records the
11 user-confirmed voice policies and six generic identities that must remain
unresolved. See the updated [review](wiki_race_review.md). Combined catalog coverage
is now 3,658 confirmed voice policies. `mixed` race profiles intentionally express
a shared gendered voice without race presets until zone-aware identity is available.
