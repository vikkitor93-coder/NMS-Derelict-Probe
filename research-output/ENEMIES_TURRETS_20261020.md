# Enemies and turrets in generated derelicts (milestones #21 / #22), 2026-10-20

Tool: `python -I tools/derelict_hazards_705.py <ADDRESS16 | folder | derelict.json> [--text] [--json OUT]`
and `python -I tools/derelict_hazards_705.py --summary [GENERATED_DIR] [--csv OUT] [--json OUT]`.
It is read-only: it reads `derelict.json` and the decompiled scenes in `D:/Orca/NMS-Derelict-Probe-analysis/meshcache/raw/`.
It reuses `scene()`, `trs()` and `matmul()` from `tools/build_piece_meshes_705.py`. It does not touch the shared generator.

## 1. What spawns enemies, and where it comes from

All game files are from NMS 7.05 PCBANKS, decompiled with MBINCompiler 7.04.1-pre3. Scratch extracts are in
`D:/Orca/Temp/claude/D--Orca-NMS-Derelict-Probe/3bcdb12b-7aa1-4b9d-a671-cd2211d292d8/scratchpad/agent-hazards/ext/`.

### Layout pieces (decoration templates, `metadata/reality/tables/generatedbasetemplatestable.mbin`)

| Template id | Placed piece scene | Hazard node inside (piece-local) | Probability / MaxPerRoom | Excluded rooms |
|---|---|---|---|---|
| `SPWN_H_FLOATERS` | `DUNGEON/SPAWNERS/FLOATER` | `SPACEBASE/SPAWNERS/FLOATER_HOSTILE_SPAWNER` at (0, 2, 0) | 0.04 / 100 | room index 0 |
| `SPWN_H_F_FLOATS` | `DUNGEON/SPAWNERS/FASTFLOATER` | `.../FLOATER_FAST_SPAWNER` at (0, 2, 0) | 0.10 / 100 | room index 0 |
| `SPWN_H_DRONE` | `DUNGEON/SPAWNERS/DRONE` | `.../DRONE_HOSTILE_SPAWNER` at (0, 2, 0) | 0.15 / 2 | room index 0 |
| `SPWN_N_BUG` | `DUNGEON/SPAWNERS/BUG` | (not placed: probability 0) | 0.00 | |
| `COM_F_TURRET` | `DUNGEON/COMM/ROOM_FLOOR_CEILINGTURRET` | `SPACEBASE/TURRET` at (0, 4, 8), rotated 180° about Z, so it hangs from the ceiling | 0.25 / 3 | |
| `R_*POD*` (12 ids: `R_C_CARGPOD0/1`, `R_F_CARGPOD0`, `R_W_CARGPOD0`, BARR and MEDI variants) | `DUNGEON/{CARG,BARRACKS,MEDI}/PODS/*` | `SPACEBASE/INFESTATION/MEDIUMHANGSLIME` (hanging sac) and/or `LARGEPILLARSLIME` (pillar sac), plus slime | 1.0 | |
| `R_*SLI*` | `DUNGEON/*/SLIME/*` | slime only (`MEDIUM90/MEDIUMFLAT/LARGECORNER` slime) | 1.0 | |
| `DOOR_SLIME`, `DOOR_SLIME_B` | `DUNGEON/INFESTATION/DOOR_*_SLIME` | `SPACEBASE/DOOR_SLIME` (an animated door with slime; it has no destructible entity of its own) | 1.0 | |
| several room pieces | e.g. `CARG/CORNER00` | `SPACEBASE/EXPLODINGBARREL` (destructible, area damage `BARRELEXPLODE`) | | |

### How the preset theme selects them

There are two steps, and both are data:
1. `freighterdungeonstable.mbin` gives each preset its room types: `*_BUGS` uses `R_BUG_*` / `R_S_BUG_*` / `B_BUG_*` rooms, `*_FLOATERS` uses `R_FLO_*`, `*_SLIME` uses `R_SLI_*`, and `*_TURRETS` / `*_MAZE` use the plain `R_BARR` / `R_CARG` / `R_MEDI` / `R_HANG`.
2. `generatedbasetemplatestable.mbin` RoomTemplates gives each room type its decoration themes. The hazard themes are:

| Room types | Hazard themes |
|---|---|
| `R_BARR`, `R_CARG`, `R_MEDI` | FLOATERS, DRONES, plus TURRET in CARG and MEDI |
| `R_S_CARG`, `R_S_MEDI` (also the entrance room, room 0, in every preset) | TURRET, FLOATERS |
| `R_FLO_*`, `R_S_FLO_*`, `B_FLO_*` | FAST_FLOATERS, FLOATERS |
| `R_BUG_*`, `R_S_BUG_*` | DOOR_SLIME, INFESTED_{CARGO,BARR,MEDI} (the sac pieces), FLOATERS in `R_BUG_BARR` only |
| `R_SLI_*`, `R_S_SLI_*` | DOOR_SLIME, SLIME, SLIME_{CARGO,BARR,MEDI}, TURRET, DRONES |
| `R_END`, `R_HANG` | FLOATERS |

Check: every one of the 28,272 hazard decorations (spawners, turrets, sac pieces, slime doors) in the 1,457 local layouts sits in a room whose template lists the matching theme. There were 0 exceptions (`scratchpad/agent-hazards/theme_check.py`). The `InvalidRoomIndexes = 0` rule also holds: no spawner is ever in room 0, while turrets are (789 of them in room 0).

### What each spawner releases (`metadata/simulation/scene/experiencespawntable.mbin`)

Each spawner entity (`.../ENTITIES/*SPAWNER.ENTITY.MBIN`) is a sketch graph, `OnSpawned -> RaiseEvent("PE_SPAWN", <id>)`.
The id is taken from the node that `OnSpawned` connects to. The unconnected "BUG" node in the floater and drone graphs is a leftover and is not raised.
`CreatureSpawnTable` maps each id to an archetype and a count. Counts are MinNum..MaxNum, given for each of 4 difficulty columns, Off / Slow / Normal / Fast.

| Event id (who raises it) | Archetype -> CreatureType | Count (Off, Slow, Normal, Fast) | Spawn type |
|---|---|---|---|
| `FLOATER` (floater spawner) | FLOATER -> Floater (scale 0.9) | 1-2 in all four columns | Freighter |
| `FAST_FLOATER` (fast floater spawner) | FAST_FLOATER -> Floater (scale 0.5) | 1-2 in all four columns | Freighter |
| `MINIDRONE` (drone spawner) | MINIDRONE -> MiniDrone | 2-3 in all four columns | Freighter |
| `FIEND_DROP` (sac's `_DESTROYED` scene, `OnSpawned -> RaiseEvent PE_SPAWN FIEND_DROP`, at locator SPAWNPOS, anim VENTDROP) | BUG -> **Scuttler** (the "biological horror") | 1-3, 3-5, **6-8**, 6-10 | Freighter |
| `BUG` (bug_neutral_spawner, not placed in derelicts) | BUG -> Scuttler | 3-5 | Freighter |
| `FIEND_EGG` (egg hatch; no fiend eggs are placed in derelicts) | BUG -> Scuttler | 1 | Freighter |

Turret (`SPACEBASE/TURRET/ENTITIES/TURRET.ENTITY.MBIN`): it has `GcTurretComponentData` (laser `BASE_TURRET_L`, projectile `TURRETINT`, missile `BASE_TURRET_M`) and a `GcBaseDefenceComponentData` trigger (perception `LASER`).
Its sketch toggles Deployed/Retracted, and destroying it gives `R_ABAND_TURRET`.

Bug sacs (`MEDIUMHANGSLIME`, `LARGEPILLARSLIME`) carry `GcAlienPodComponentData`. The agro values are: AgroMovement 11 within 8.5 m, AgroTorch within 10 m, AgroThreshold 15, GunfireAgro range 20.
They are also destructible (health 600, FiendCrime `EggDestroyed`, reward `DE_FATSLIME`). Their destroyed model raises `FIEND_DROP`.
Plain slime (`MEDIUM90`, `MEDIUMFLAT`, `LARGECORNER`, `LARGE90`) is destructible (700-800 health, `EggDestroyed`, `DE_FATSLIME`). It spawns nothing directly.

## 2. Output of the tool

For each layout: `totals` (count per kind), `turrets`, `enemy_spawners`, `bug_sacs`, and `expected_creatures_normal` (summed min-max per archetype in the Normal column).
For each room: `rooms[]` with `room_index`, `template`, `counts`, and `hazards[]`. Each hazard has:
`kind, category, symbol, x, y, z` (layout metres), `u, v, level` (viewer grid), `yaw_deg` (local +Z in layout), `mount` (turrets),
`spawn {event, creature, archetype, count_normal, count_by_difficulty}`, `trigger`, `template_id`, `piece`, `scene_node`.
`missing_scenes` lists any piece MXML not in the cache. It was empty for all layouts.

Positions: hazard node matrices are composed down the REFERENCE chain (including InstanceTransforms, `R = Rz*Ry*Rx`). The piece-local point maps to layout space as p·A + t, the same mapping that reproduces the generator's `containers[].layout_local_xyz`.
`level = floor((y + 1) / 8) + Ey` is the deck the hazard stands on or hangs from. A ceiling turret is 4 m above its deck, and plain `round(y/8)` would put a turret at y = -4 on the deck above.

## 3. Results over all local layouts (1,453 of 1,457 readable; 5 min 43 s)

Mean count per layout. The per-layout CSV and JSON are in `scratchpad/agent-hazards/hazards_per_layout.csv` and `hazards_summary.json`.

| Preset | n | Floater sp. | Fast-floater sp. | Drone sp. | Turrets | Hanging sacs | Pillar sacs | Slime | Slime doors | Barrels | Creatures (Normal, min-max) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| CARGO_BUGS | 281 | 1.92 | 0 | 0 | 0.90 | 6.34 | 9.90 | 120.2 | 7.6 | 4.5 | 99-134 |
| MEDI_BUGS | 277 | 1.89 | 0 | 0 | 0.44 | 11.02 | 7.08 | 147.0 | 7.5 | 0.9 | 111-149 |
| CARGO_FLOATERS | 171 | 4.20 | 10.03 | 0 | 0 | 0 | 0 | 0 | 0 | 10.7 | 14-29 |
| MEDI_FLOATERS | 89 | 2.78 | 6.27 | 0 | 0 | 0 | 0 | 0 | 0 | 2.8 | 9-18 |
| CARGO_TURRETS | 197 | 4.68 | 0 | 5.22 | 4.99 | 0 | 0 | 0 | 0 | 8.2 | 15-25 |
| MEDI_TURRETS | 204 | 3.91 | 0 | 4.78 | 1.98 | 0 | 0 | 0 | 0 | 2.5 | 14-22 |
| CARGO_SLIME | 80 | 1.43 | 0 | 7.50 | 9.05 | 0 | 0 | 139.4 | 9.0 | 9.4 | 16-25 |
| MEDI_SLIME | 61 | 1.97 | 0 | 6.56 | 10.20 | 0 | 0 | 205.7 | 8.9 | 0.5 | 15-24 |
| CARGO_MAZE | 50 | 2.30 | 0 | 4.60 | 3.48 | 0 | 0 | 0 | 0 | 5.4 | 12-18 |
| MEDI_MAZE | 43 | 2.28 | 0 | 3.86 | 1.44 | 0 | 0 | 0 | 0 | 2.0 | 10-16 |

Is this plausible?
- Each preset has its own signature hazard. BUGS layouts always have sacs (at least 2 pillar sacs, or at least 2 hanging sacs) and never drones or fast floaters. FLOATERS layouts always have fast floaters (at least 1) and never turrets, drones or sacs.
- TURRETS layouts have turrets in 194 of 197 (CARGO) and 186 of 204 (MEDI). The highest turret counts are not in TURRETS presets but in SLIME presets: every SLIME layout has 4-16 turrets. TURRETS, SLIME and MAZE all have drones.
- BUGS layouts can still have 1-4 turrets. These are mostly in the entrance room `R_S_CARG` / `R_S_MEDI`, which is shared by all presets.
- Pieces with a hazard in the room-0 entrance: turrets only, never spawners. This matches the table's `InvalidRoomIndexes`.

## 4. Proven, inferred, and decided at run time

**From data and the layout (deterministic, reproduced by the generator):** which hazard pieces exist, their room and their position.
Spawner and turret pieces are ordinary decoration placements of the native writer. The writer's probability rolls are part of the seeded generation, the same as crates.
The fixture `00003B0006606CAA` matches live data for all 145 instances (`GENERATOR_VALIDATION_VS_LIVE_20261020.md`), and that fixture has 17 sacs, 0 spawners and 0 turrets. Other presets are verified only by totals, or not at all (see the blind-test plan).

**Decided at run time (not in the layout), with evidence:**
- *How many creatures* a spawner releases: random in MinNum..MaxNum (table above). The column comes from a 4-value difficulty option named Off/Slow/Normal/Fast. I'm *assuming* this is the custom-difficulty combat setting; I have not verified which one it is.
- *When* they spawn: the spawner graph fires on the entity's `OnSpawned`, that is, when the spawner node is instantiated or streamed in. The spawner LodDistances are 0/50/80/150/500. `GcCreatureGlobals` has `FreighterSpawnDist 30` and `FreighterDespawnDist 50`. Inferred: creatures appear when the player comes within about 30 m and despawn beyond 50 m. Not verified whether spawners re-fire after a despawn.
- *Bugs* exist only through the sacs. A sac bursts when its alien-pod agro passes its threshold (movement, torch, gunfire) or when it is destroyed. The destroyed model then drops 6-8 Scuttlers (Normal). The agro-to-burst link and "one burst per sac" are **inferred**.
- `GcCreatureGlobals` has `MaxFiendsToSpawn 6` / `MaxFiendsToSpawnCarnage 10`. That may cap bugs alive at the same time, so the tool's "BUG 99-134" is an upper bound on bugs *over the whole visit*, not bugs at one moment. **Inferred**: the cap might apply only to the Fiend type.
- Shooting plain slime raises FiendCrime `EggDestroyed`. Whether that spawns anything in a freighter is not established, so the tool spawns nothing for it.
- Turrets deploy from "Retracted" on base-defence perception. Their facing is dynamic; the tool reports only the mount (all ceiling) and the mount yaw.

**Open item (generator vs data):** `COM_F_TURRET` has `MaxPerRoom = 3`, but 62 layouts have 4-5 turrets in one room, in 5 presets. For example, `0000770007607CAA` room 5 `R_CARG` has 5, and `00001C0006607CAA` room 7 has 4. In contrast, `SPWN_H_DRONE` `MaxPerRoom = 2` is never exceeded across 1,457 layouts.
Either the turret cap is counted differently in the writer (for example per layer or pass), or the generator diverges here. An in-game check of one such room settles it (see section 6).

## 5. Viewer integration spec (for the viewer agent; I have not changed any viewer files)

Data: the tool's JSON per layout. The viewer needs only `rooms[].hazards[]` with `kind, x, y, z, u, v, level, yaw_deg, mount, spawn.count_normal` and `totals`.
For the compact bundle, the proposed per-room form is `"hz": [[kindCode, x_cm, y_cm, z_cm], ...]`, delta-encoded like the containers, with kind codes:

| Code | Kind | Map symbol (suggested) | Colour | Tooltip |
|---|---|---|---|---|
| F | floater_spawner | jellyfish / "F" in a circle | violet | "Floater spawner: 1-2 floaters" |
| f | fast_floater_spawner | small "f" in a circle | light violet | "Fast floater spawner: 1-2 small fast floaters" |
| D | drone_spawner | diamond "D" | orange | "Drone spawner: 2-3 mini drones" |
| T | turret | triangle pointing down (ceiling mount) | red | "Ceiling turret (deploys when it detects you)" |
| S | hanging_sac | teardrop | green | "Hanging sac: bursts into 6-8 biological horrors (Normal)" |
| P | pillar_sac | tall capsule | dark green | "Pillar sac: 6-8 biological horrors (Normal)" |
| X | explosive_barrel | small "X" | yellow | "Explosive barrel" |
| = | slime_door | hatched door marker | green outline | "Slime-covered door" |
| ~ | slime | (off by default, about 120-200 per BUGS/SLIME layout) | faint green | "Slime (destructible)" |

Toggles: "Enemies" (F f D S P), "Turrets" (T), "Hazards" (X, =, ~). Room list badge: "T3 D2 F1 S4". Layout summary line, for example: "Turrets 5, spawners 10, sacs 0; creatures (Normal) 15-25".
Atlas index columns, if wanted: `turrets, spawners, bug_sacs, creatures_min, creatures_max`. Those would go to `build_atlas_index.py`, which is owned by the viewer agent and the scanner. They need a NOTICE in `D:/Orca/NMS-COORDINATION.md` first, because the scanner reads that file.

## 6. What the user should check in-game (I did not launch the game)

1. Fixture `00003B0006606CAA` (CARGO_BUGS, already visited): there should be **no floaters, drones or turrets**. Bugs should come only from the 17 sacs (rooms 2, 3, 5, 7, 9: 9 hanging + 8 pillar). Check whether a sac bursts when you approach it or only when you shoot it, and roughly how many bugs drop (expected 6-8 on Normal).
2. A TURRETS derelict, e.g. `0000770007607CAA` (CARGO_TURRETS): room 5 (`R_CARG`, one deck below the entrance) should have **5** ceiling turrets at x = -16 (z = 56, 64, 72, 80) and at (-8, 80), plus 2 drone spawners. This decides the MaxPerRoom-3 open item.
3. A FLOATERS derelict, e.g. `003C04607CAC` or `00F906608CAA` (CARGO_FLOATERS, visited earlier): **no turrets** at all. Count the floaters that appear at one spawner (expected 1-2).
4. Drone spawner: expected 2-3 mini drones each. Check whether they reappear after you leave (more than 50 m) and come back.
5. Note your difficulty setting and whether it is custom. The counts above use the "Normal" column.

## Files

- `tools/derelict_hazards_705.py` (new)
- `research-output/ENEMIES_TURRETS_20261020.md` (this file)
- Scratch: `D:/Orca/Temp/claude/D--Orca-NMS-Derelict-Probe/3bcdb12b-7aa1-4b9d-a671-cd2211d292d8/scratchpad/agent-hazards/` (pak extracts in `ext/`, `hazards_per_layout.csv`, `hazards_summary.json`, `theme_check.py`, `per_room_max.py`, MXML dumps `est.txt`, `gbt.txt`, `fdt.txt`)
