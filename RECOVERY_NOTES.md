# Recovery notes (branch `recovered-20261025`)

On 2026-10-24/25 the drive that held the working copy of this project was lost. This branch is the recovered
state, pushed as a NEW BRANCH for safekeeping. `main` is untouched and nothing here has been published or
deployed. The live site and the atlas are not affected.

## How the tree was rebuilt
1. Files that still existed elsewhere (this repo, earlier snapshots, other copies) were taken as they were.
2. Files that were only ever shown or written inside tool sessions were replayed from the session logs
   (full `cat` / `sed -n` reads, `Write` calls and later edit patches, newest observation wins).
3. What the logs do not contain was reconstructed as new code (stage G1/G2), by static reading of the
   game executable and the logged call sites, and marked in the file.

## Verbatim recovered (logs, complete, compile OK)
`tools/end_reward_batch_705.py`, `end_reward_worker_705.py`, `crate_loot_batch_705.py`, `crate_loot_worker_705.py`,
`derelict_seed_preset_705.py`, `transform_writer_output_705.py`, `emulate_writer_705_assets.py`,
`extract_generatedbase_scene_assets.py`, `extract_r_w3_scene_references_705.py`, `scan_worker_705.py`,
`test_scanner_update_guard.py`; under `research-output/offline-layout-705-20261019/`:
`nms_universe_address_705.py`, `nms_dungeon_a2780_search_705.py`, `nms_dungeon_fit_705.py`,
`reconstruct_cargo_bugs_candidate_705.py`, `scene_callback_matrix_705.py` (G1, completed from logs),
`nms_dungeon_reference_closure_q4_705.py` (final logged version). Also several reports under `research-output/`.
Promoted from earlier staging versions (not reconstructed, but the staging variant, not necessarily the last edit):
`scan_cache_705.py`, `nms_paths_705.py` (partial, 8 of 19 lines logged), `publish_end_reward_cache_705.py`
(first 25 lines logged, the rest from the later staged copy).

## Reconstructed or partly reconstructed (headers inside each file say which lines)
- `research-output/offline-generator-assessment-20261019/row_tag_codec.py`: ALL NEW CODE, ported from a static
  disassembly of the 7.05 executable (function FUN_14039FA50); no line of the original survives.
- `nms_dungeon_source_catalog_705.py`: lines 1-25 and 140-410 logged, 26-139 reconstructed.
- `nms_dungeon_offline.py`: lines 1-219 and the tail reconstructed, 220-360 logged.
- `nms_dungeon_variable_placement_705.py`, `nms_dungeon_topology_705.py`, `nms_dungeon_piece_selector_705.py`,
  `nms_dungeon_pregraph_705.py`, `nms_dungeon_instance_705.py` (G2): logged fragments plus reconstructed bodies
  (docstrings list the reconstructed parts).
- Minimap, mod, ondemand server and `system_names_705`/regression harness come from agent-written replays and
  staging copies (A2/A4 stage); `ondemand/tests/stub_generator.py` is a stub (see `STUB_NOTE.txt`).
- `STATUS.md` was rewritten after the loss and carries the recovery log; network names and addresses in it were
  redacted for this public branch.

## Verified (comparisons actually run)
- Game data re-extracted from the installed 7.05 game: `asset_source_rows.bin` sha256
  `39c87c6855deb985b2d9e0febba0f66656b97ed46b5e73191cb77a94abd2328b` (1876 rows) equals the value logged
  for 7.05; `--check-against-705` 653/653; presets and entrance reference match.
- Atlas check of the rebuilt generator: 20 of 20 sampled addresses pass (all geometry and room-detail columns
  and the row check hash). Caveat: the atlas stores empty `briefcases`/`tall_lockers` on some old rows; the
  harness blanks our two counts there (7 of 20 rows blanked, 13 compared directly).
- Rewards, loot and frigate columns: 164 of 164 addresses match the atlas in every column.
- Scanner smoke run: 240 systems of one region, 0 differences against the atlas (scanner app itself is NOT
  in this repo).

## Still missing or failing
- Regression suite: 11 pass, 2 fail, 7 skip (needs the replay fixture, the `glyphs_to_address` edit and
  name vectors).
- Not recovered: minimap `core.py` (partial, 120 of 246 lines) and `layoutmodel.py`; traffic-logger and relay
  scripts; capture scripts (`run_layout_capture_0_3_55*.ps1` etc.); about 43 research notes and 67 files that
  only existed on the lost drive; several P3 reports listed as "none" in the miner coverage table.
- On-demand server and scanner server tests with the real generator have not been run.
- Not published here on purpose: game data and extracted `.mbin`/`.MXML` files, executable copies, derived
  container meshes, stale nested duplicate folders, `*.pre-*` backup copies, local minimap settings.
