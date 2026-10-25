# LandSandBoat NPC voice catalog

Source revision: `81a13ab0febcace751017044529ec77773180ad1`

Generated from the upstream LandSandBoat NPC definitions; this is a starting catalog, not a complete list of speaking characters or CatsEye-specific content.

## Coverage

- 37,870 entity records inspected (YAML plus remaining legacy SQL).
- 6,817 normalized display-name groups retained, including unclassified objects.
- 3,128 confirmed names eligible for import; 113 partial, 72 conflicting, and 3,504 unknown groups retained for review.
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
- goblin: 17
- hume: 930
- mithra: 362
- tarutaru: 614

## Attribution

Derived from https://github.com/LandSandBoat/server at the pinned revision above. Upstream copyright and GPL terms are retained in `LandSandBoat-LICENSE`. Per-entity source paths and Goblin-model evidence are included in the JSON.
