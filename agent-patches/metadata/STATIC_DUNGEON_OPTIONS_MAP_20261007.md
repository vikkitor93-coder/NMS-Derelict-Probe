# Direct abandoned-freighter DungeonOptions map — 2026-10-07

## Sources and method

The installed game's PAK index identifies `MODELS/SPACE/POI/PARTS/DUNGEON_ENTRANCE/ENTITIES/DUNGEONENTRANCE.ENTITY.MBIN`. Its decompiled component is `GcAbandonedFreighterComponentData`, and the same entity's `GcOutpostComponentData.AbandonedFreighter` is `true`. The component contains `DungeonRootScene` and ten `GcFreighterDungeonChoice` entries under `DungeonOptions`.

The component MBIN SHA-256 is `7ae4acec4521f5e8347b9d61514cf59dae7a24e722a7058a1126beb999b243e8`. The current `METADATA/REALITY/TABLES/FREIGHTERDUNGEONSTABLE.MBIN` SHA-256 is `f5afb96f49560bf39a0ec6ffc295540ed4c38165e4458df2c7785fe391e1a82a`. MBINCompiler v7.4.1.3 converted both to MXML. `map_current_dungeon_options.py` reads those two MXML files, hashes their MBIN sources, rejects duplicate or unmatched names, and writes `CURRENT_DUNGEON_OPTIONS_20261007.json`. All ten component names match the ten table presets.

The component's `DungeonRootScene.Filename` is `MODELS/PLANETS/BIOMES/COMMON/BUILDINGS/PARTS/BUILDABLEPARTS/SPACEBASE/GENERATEDBASEROOT.SCENE.MBIN`. This static field should not be equated with the separately observed runtime `MODELS/SPACE/POI/DUNGEON.SCENE.MBIN` resource without tracing the intervening calls.

| Dungeon option | Weighting | Table Rooms |
|---|---:|---:|
| MEDI_TURRETS | 0.66 | 7 |
| MEDI_FLOATERS | 0.33 | 7 |
| MEDI_BUGS | 1.00 | 7 |
| MEDI_SLIME | 0.25 | 7 |
| MEDI_MAZE | 0.15 | 4 |
| CARGO_TURRETS | 0.66 | 7 |
| CARGO_FLOATERS | 0.33 | 7 |
| CARGO_BUGS | 1.00 | 7 |
| CARGO_SLIME | 0.25 | 7 |
| CARGO_MAZE | 0.15 | 4 |

The similarly named `MODELS/COMMON/SPACECRAFT/COMMONPARTS/ABANDONEDPARTS/DUNGEONENTRANCE/ENTITIES/DUNGEONENTRANCE.ENTITY.MBIN` contains an empty `DungeonOptions` list and marks `GcOutpostComponentData.AbandonedFreighter` as `false`. The mapper rejected this alternate source; it must not be substituted for the active entrance component.

## Verification and limit

The mapper succeeded on the active entity and failed on the alternate entity with `Entity is not marked as an abandoned freighter`. It found ten unique choices and ten unique table entries with exact name agreement. The JSON output contains source hashes, exact weights, table room counts, and sizes. The listed weights are measured static values in the installed game assets. Their runtime selection semantics, normalization, seed input, and actual selection frequencies have not been established.
