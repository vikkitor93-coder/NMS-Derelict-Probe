# Derelict loot container types: briefcase and tall locker (milestone #20, 2026-10-20)

The user asked for all lootable containers per derelict, naming "the briefcase" and "the long tall one". They then
confirmed: "just the briefcase and the tall one is correct". These two are added as **extra columns**. The top-100
rank stays salvage crates + footlockers.

## Result

| container_kind | Prop scene (`.../SPACEBASE/PROPS/`) | Entity | Interaction | Reward table id | Size x*y*z (m) | Template refs |
|---|---|---|---|---|---|---|
| `salvage_crate` (existing) | `CRATEM` | `CRATEM/ENTITIES/CRATEM.ENTITY` | GenericReward | `R_ABAND_CRATE` | 1.27 x 0.90 x 1.07 | 54 in 45 scenes |
| `crew_footlocker` (existing) | `FOOT_LOCKER` | `FOOT_LOCKER/ENTITIES/FOOTLOCKER.ENTITY` | GenericReward | `R_ABAND_CRATE` | 1.58 x 0.90 x 0.99 | 34 in 28 scenes |
| **`briefcase`** (new) | `INTERACTIVE_CASE` | `INTERACTIVE_CASE/ENTITIES/SMALLCASE.ENTITY` | GenericReward, 3 m | **`R_ABAND_CASE`** | 0.91 x 0.27 x 0.64 | 79 in 56 scenes |
| **`tall_locker`** (new) | `LOCKER` | `LOCKER/ENTITIES/LOCKER.ENTITY` | GenericReward, 3 m | **`R_ABAND_LOCK`** | 1.04 x 3.04 x 1.13 | 74 in 22 scenes |

Across 1,454 generated derelicts, there are on average **22.9 briefcases** (range 8-55) and **27.3 tall lockers**
(range 4-118) per derelict. The current top-100 systems hold 3,508 briefcases and 3,643 tall lockers.

## Evidence

All of this was read from the exact 7.05 game files: HGPAKtool extraction, then MBINCompiler 7.04.1.3 conversion.
The extracted files are in the scratchpad (`agent-containers/ent`, `agent-containers/rt`).

1. **Scenes.** Every SPACEBASE prop referenced by the 319 generated-base template scenes is a direct `REFERENCE`
   child of an identity scene root. None needs hierarchy composition. The new kinds use exactly the same node shape as
   the validated crates (`RefBox*` / `RefLocker*` with `SCENEGRAPH` + `EMBEDGEOMETRY`, versus `RefCrateM*` /
   `RefFootLocker*`).
2. **Entities.**
   - Only CRATEM, FOOT_LOCKER, INTERACTIVE_CASE and LOCKER attach an entity with `GcSimpleInteractionComponentData`
     `SimpleInteractionType=GenericReward`, plus open/close animations. The interactive case plays the sound
     `INTERACTIVECASE_OPEN`.
   - Not lootable: `CRATE` (`CRATEL1.ENTITY`), `LARGE_CRATE` (`CRATE.ENTITY`), `FLOATING_CRATE`
     (`FLOATINGPHYSICS.ENTITY`), `CRATEM_LOOTED` and `CRATELID_LOOTED` (`SHAREDDATA/PHYSICS.ENTITY`). Their entities
     have only static physics / physics components: they are decoration. Following the user's decision, they are not
     added at all.
3. **Reward table.** The file is `metadata/reality/tables/rewardtable.mbin`, SHA-256 `A04483...6059`, the same as in
   `ghidra-static-20261015/REWARD_TABLE_PIPELINE_20261016.md`.
   - `R_ABAND_CASE` (TryFirst_ThenSelectAlways):
     - first try: TIMEDUST 10-30 (ChanceToUse 0.4);
     - then weighted: a procedural product (1), 20k-100k units (10), 20-50 nanites (40), 5k-10k units (40),
       50-200 nanites (10), AF_METAL 10-30 (40).
   - `R_ABAND_LOCK`:
     - first try: TIMEDUST 10-25 (0.6);
     - then weighted: GRENFUEL1 (10), 10 x procedural tech product (1 each), AMMO 100-600 (20), 5k-10k units (20),
       20-50 nanites (20), NIPNIPBUDS 1-3 (10), the curios WAR/EXP/TRA_CURIO1/2 (10 each), a system-specific product
       1-3 (70), AF_METAL 10-25 (20).
   - **Neither table contains FRIG_TOKEN** (salvaged frigate module). That item is only in `R_ABAND_CRATE`, which
     the crates and footlockers use. That is why the rank stays crates + footlockers.
4. **Live corroboration.**
   - Earlier live probe sessions recorded `R_ABAND_LOCK` reward calls in derelicts: 11 distinct seeds in one session
     (`LOADING_REGRESSION_TRACKER.md`), 5 in another.
   - One `R_ABAND_LOCK` call coincides with a Vy'keen Effigy pickup (`UNTITLED1_LOOT_ATTRIBUTION_REVIEW.md` #26).
     That is WAR_CURIO, which is in the LOCK table.
   - `R_ABAND_CASE` appears once (1 seed) in `20261017T162055Z_reward_seed_inventory.csv`.
   - So both kinds are opened in real derelicts. Their per-derelict counts and positions are **not** live-validated
     yet (see the open items).
5. **Images.** `research-output/container-types-20261020/`, from LOD0 geometry with the half-float positions read
   by `tools/build_piece_meshes_705.geometry`:
   - `interactive_case.png`: a flat case with a carry handle, so the "briefcase".
   - `locker.png`: about 3 m tall and 1 m wide, so the "tall one".
   - `foot_locker.png` and `cratem.png` are included for scale.
   - `lineup_front_same_scale.png` shows all four at one scale.
   - Small artefact: the locker's separate door stream is drawn in its joint's local frame (the small block at the
     floor). It is cosmetic only.
   - Renderer: scratchpad `agent-containers/render_props.py`, run with the Pillow venv.

## Where they appear

The new kinds come from the same template scenes as the crates. Totals over 1,454 layouts:
- Tall lockers: 82% are in BARRACKS scenes (for example `BARRACKS/ROOM_WALL7` has 15 and `ROOM_FLOOR0` has 10).
- Briefcases: spread over CARG (35%), END, MEDI and BARRACKS.

Average per derelict, by preset:

| preset | layouts | crates | footlockers | briefcases | tall lockers |
|---|---|---|---|---|---|
| CARGO_BUGS | 281 | 23.8 | 8.0 | 23.3 | 25.6 |
| CARGO_FLOATERS | 172 | 37.5 | 17.4 | 29.2 | 31.8 |
| CARGO_MAZE | 50 | 18.5 | 14.6 | 18.2 | 32.1 |
| CARGO_SLIME | 80 | 15.8 | 3.1 | 25.2 | 28.6 |
| CARGO_TURRETS | 197 | 28.9 | 15.8 | 25.1 | 32.0 |
| MEDI_BUGS | 277 | 6.2 | 6.9 | 23.5 | 21.9 |
| MEDI_FLOATERS | 89 | 12.5 | 11.1 | 17.2 | 26.2 |
| MEDI_MAZE | 43 | 8.2 | 12.4 | 13.9 | 28.7 |
| MEDI_SLIME | 61 | 4.3 | 1.8 | 30.0 | 23.4 |
| MEDI_TURRETS | 204 | 12.2 | 11.4 | 16.6 | 28.1 |

Examples of predicted counts:
- Live fixture `00003B0006606CAA`: 14 briefcases and 14 tall lockers, plus the validated 17 crates and 6 footlockers.
- `0002250006607CAA`: 42 briefcases and 35 tall lockers.

## Design decisions and formats

The crates and footlockers are live-validated, and several readers assume "not a crate = footlocker". This is true
in the scanner's `store.py`, `server.py` and `derelict_app.py` (where an unknown kind raises KeyError), in
`viewer/static/app.js` (`lockers = containers.length - crates`) and in `model.build`. So the new kinds are kept in
**separate** fields everywhere, and nothing existing changes meaning.

| Layer | Change |
|---|---|
| Catalog | `tools/extract_generatedbase_scene_assets.py --extra-only` (offline). It checks every member MBIN/MXML hash against the member manifest, then writes `research-output/exact705-generatedbase-scenes-20261019/authored_extra_container_transform_index.csv`: 153 rows, same columns as the main index. The main index files are byte-identical; the refactored writer reproduces `authored_container_transform_index.csv` exactly (SHA-256 `2FDACA...92E0`). |
| Placement | New `tools/extra_containers_705.py`, which uses the generator's own float32 `SceneInstanceTransform.transform_point`. `extra_containers(d)` needs only `d["instances"]`, so it works on every stored or old layout. `extra_counts(d)` returns `{"briefcase": n, "tall_locker": m}`. |
| derelict.json | `tools/generate_derelict_705.py main()`, which is also used by `fast_generate_705` and the scanner worker, adds `extra_containers` (same fields as `containers`) and `extra_container_kinds`. `containers`, `container_kinds` and `container_count` are unchanged. |
| View (model.js / derelict_view.py) | Optional key `"x"`, appended after `"i"`, only when `d.extra_containers` exists: `[kind codes, room, dx, dy, dz cm]`, same delta encoding as `"c"`. Kind codes: 0 salvage_crate, 1 crew_footlocker (in `"c"`), 2 briefcase, 3 tall_locker (in `"x"`). `VIEW_FORMAT` stays 3, because it is additive and old readers ignore `"x"`. `unpack` sets `d.extra_containers` and `d.extra_container_kinds` only when `"x"` exists. `build` returns `extras` (`null` = unknown) and per-room `briefcases` / `tallLockers`. The API also exports `KIND_CODES`, `KIND_NAMES` and `EXTRA_KINDS`. |
| Top-100 bundle | `build_top_bundle.build_bundle` always recomputes `extra_containers` from the pieces, so the scanner's stored layouts and fresh ones give the same bytes. Signature unchanged. Size: 123 KB -> 157-161 KB gzip. |
| Index | `build_atlas_index` format 3 appends `briefcases,tall_lockers` after `map`. The values are copied from region rows when the region file has those columns, otherwise left empty (unknown, not 0). Rank and `map` unchanged. |
| Region CSV | Scanner-owned: REQUEST posted (see Coordination). |

## Tests run (2026-10-20)

- `python -I tools/extra_containers_705.py --check`, over all 1,454 generated layouts.
  - Recomputing `containers` from the stored `instances` with the main index reproduces `d["containers"]` exactly
    for all 1,454. This proves the instance-to-container path that the extras use.
  - Extra totals: 33,296 briefcases and 39,644 tall lockers.
  - No duplicate positions, and no two extras closer than 0.6 m in one scene.
- Fast-generator regeneration to scratch of `00003B0006606CAA`, `0000010006607CAA` and `0002250006607CAA`.
  - Every key except timings, `fixture_check` and the two new keys is identical to the stored layouts, including
    `containers` and `container_kinds`.
  - The stored `extra_containers` equal the recomputation from the old layout.
  - A second run of `0002250006607CAA` is identical (stable).
- `python -I tools/derelict_view.py --verify`:
  - 1,454 layouts, 0 different (Python == JS);
  - 4 layouts with extras, 0 different.
  - The new Python pack equals the pre-change pack byte for byte for all 1,454 existing layouts (no extras -> no
    `"x"`).
  - JS pack -> unpack -> build round trip: kinds and rooms exact, positions within 0.005 m (cm rounding), per-room
    sums match.
- Top-100 bundle: my build from local layouts (83 generated into scratch) is **byte-identical** to the scanner's
  published `views/top100.json.gz`, which already carries `"x"` for all 100 systems. Two builds are identical.
- Index: tested on a scratch copy of `regions/`.
  - Two builds are byte-identical.
  - The first 10 columns are identical to format 2 for all 55,871 rows.
  - The new columns are empty for today's region files.
  - A simulated region file with `briefcases,tall_lockers` fills all 537 rows.
  - The top-100 (`map`) set is unchanged.
- `python -I tools/regression_test_705.py` (fast mode): **19 PASS, 1 FAIL, 1 SKIP** (`--full` only).
  - The one FAIL is **e2 "rebuilt index == published index"**, and it is expected. The published index is still
    format 2, because the scanner has not published since the format 3 builder went in.
  - Checked directly: the format-2 builder reproduces the published index byte for byte, and the format-3 rows minus
    the two appended columns equal the published rows.
  - e2 passes again after the scanner's next publish, which rewrites the index in format 3.
  - e5 (bundle == published) passes.

## Coordination

- `D:/Orca/NMS-COORDINATION.md`, entry 2026-10-20 19:55: NOTICE (derelict.json keys, view `"x"`, bundle, index
  format 3) and REQUEST to the scanner (region CSV/store columns `briefcases`, `tall_lockers`). No reply yet.
- Because the scanner reloads these tools on every publish, the change went live during the edits.
  - Atlas commit `a370fb7` (20:03) has `"x"` on 8 of 100 views. It was built between the `derelict_view.py` edit
    and the `build_top_bundle.py` edit.
  - `754db23` (20:07) and later have all 100 views with `"x"`.
  - This is harmless: old viewers ignore `"x"`, and later commits supersede it.

## What the viewer agent must add (app.js / app.css / index.html; not touched here)

- **Index table columns:**
  - key `briefcases`, label "Briefcases"; key `tall_lockers`, label "Tall lockers";
  - both read by header name from `index/systems.csv.gz`, numeric;
  - an empty cell means "not known yet", so show "-" and leave the row out of numeric filters on these columns,
    rather than treating it as 0;
  - not part of `total` or of the rank;
  - optional filters "Min briefcases" and "Min tall lockers".
- **Derelict page:**
  - Cards "Briefcases" and "Tall lockers" from `d.extra_container_kinds`, or from counting `build().extras`. When
    `extras` is `null`, the layout predates the feature, so show "-".
  - Per-room table: add `r.briefcases` and `r.tallLockers` next to crates and footlockers. Keep `lockers` as the
    footlockers: `lockers = containers.length - crates` stays correct, because `containers` holds only crates and
    footlockers.
- **Map symbols:**
  - Existing: crate orange, footlocker blue.
  - Suggested briefcase: a small flat purple rectangle (for example `#8e5bd0`), drawn smaller than a crate.
  - Suggested tall locker: a tall narrow teal/green rectangle (for example `#1a9e8a`).
  - Give both a legend entry and tooltips: "Briefcase (R_ABAND_CASE: units, nanites, salvage, no frigate module)"
    and "Tall locker (R_ABAND_LOCK: curios, ammo, tech, no frigate module)".
  - The heights come from `layout_local_xyz` like the crates; use `build().extras[i].g` for grid u, v and level.
  - Consider a toggle "show briefcases / tall lockers", because they double the marker count. BARRACKS rooms carry
    up to 15 lockers along a wall.

## Open items

1. **The user should confirm in-game.**
   - Do the briefcase and tall-locker counts match one known derelict? Easiest: `00003B0006606CAA`, predicted
     14 + 14, or `0002250006607CAA`, predicted 42 + 35.
   - Do opened ones give the items listed above?
   - The positions use the same validated transform path as the crates, but they are not live-checked.
2. **Scanner:** region CSV/store columns (REQUEST); back-filling published regions needs regeneration.
3. **Viewer agent:** the UI items above.
4. **Index:** published `index/systems.csv.gz` stays format 2 until the scanner's next publish; until then regression
   check e2 is expected to fail.
