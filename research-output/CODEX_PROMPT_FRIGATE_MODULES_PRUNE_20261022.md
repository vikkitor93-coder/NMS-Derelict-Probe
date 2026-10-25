You are taking over the NMS 7.05 derelict-freighter project as BOTH the scanner agent and the viewer agent.

**Projects (work only on D:):**
- Viewer/research: `D:/Orca/NMS-Derelict-Probe`
- Scanner app and fast generator: `D:/Orca/NMS-Derelict-Probe-fastgen`
- Published atlas clone: `D:/Orca/NMS-Derelict-Atlas`, public at github.com/vikkitor93-coder/nms-derelict-atlas

## Read first, in this order

1. `D:/Orca/NMS-COORDINATION.md` (rules plus the newest Log entries). Keep using it: add a NOTICE before changing any file format and a DONE when finished.
2. In `D:/Orca/NMS-Derelict-Probe/STATUS.md`, the section "NEXT AGENT START HERE".
3. `research-output/CRATE_LOOT_PREDICTION_20261021.md` and `CRATE_LOOT_PROGRESS_20261021.md`.
4. `research-output/END_REWARD_DATA_PROGRESS_20261021.md`. It describes how the end-reward backfill was built into the scanner (cache, resumable batches, publish every 500), so copy that pattern.
5. `TESTING.md` (regression suite: `python -I tools/regression_test_705.py`, plus `--full`).

## Hard rules

- Never launch or attach to No Man's Sky. The Python/pyMHF capture profiles stay quarantined.
- The atlas repo is the only thing you commit and push. Do it through the scanner's existing publish path and the repo lock (`atlas.repo_lock`). Don't commit the other repos unless the user asks.
- Never publish official game assets (meshes, textures, glyph PNGs).
- Before any destructive step (deleting files, rewriting published data), make a backup under `D:/Orca/NMS-Derelict-Probe-backups/` and get the user's explicit OK.
- Keep `STATUS.md` and `WORKSPACE_STATE.json` current after every result, so another agent can take over at any time. Never claim a test passed unless you ran it.

## Background (verified)

- The crate-loot predictor `tools/predict_crate_loot_705.py <ADDRESS16> [--room N] [--all] [--json]` predicts every salvage crate and crew footlocker, and the tall lockers too.
  - The seed is a hash of the container's world position, using the same position model as the end reward (`tools/predict_end_reward_705.py`, `end_reward_worker_705.py`).
  - Blind test, 2026-10-22: in `0000360006607CAA` all 5 crates matched in item and amount, including the one Salvaged Frigate Module. `0000FE0006607CAA` matched both crates.
  - About 7.5% of containers are AMBIGUOUS (near a rounding edge); the tool lists the alternatives.
  - Salvaged Frigate Module odds are 5/198 per crate or footlocker.
- The atlas has 60,190 systems in region CSVs (format 3, with end-reward columns), plus `index/systems.csv.gz` (format 4) and `views/top100.json.gz`. `tools/build_atlas_index.py` and `tools/build_top_bundle.py` rebuild them after each upload (`Scanner._derived_files`).
- The local top-100 bundle has container orientation that is not published yet; the next upload publishes it. Regression check e5 fails until then (expected).

## Task 1: Salvaged Frigate Modules in the scanner, then the backlog

1. Add a fast batch path for crate loot, modelled on `end_reward_batch_705.py` / `end_reward_worker_705.py`: persistent workers, a resumable cache CSV, and bounded chunks. The per-system result needs at least:
   - `frigate_modules`: the count of Salvaged Frigate Modules over crates and footlockers, plus tall lockers and briefcases if the table can give them; state which;
   - `frigate_modules_ambiguous`: the count of module predictions that are ambiguous, or the module alternatives;
   - `frigate_module_rooms`: a compact list of room numbers holding a module, so the viewer can show where.

   Optionally add a compact per-container loot list for the viewer's detail page, but keep the region and index files small, as the user demands.
2. Before running anything big, check it: batch == single tool on 200 random systems, and both `0000360006607CAA` and `0000FE0006607CAA` reproduce the confirmed items.
3. Build it into the scanner so new scans compute it, and add a visible backlog phase like the reward backfill. Bump the region/index formats; old rows mean "not computed yet", not zero. Post a NOTICE first.
4. Viewer, `D:/Orca/NMS-Derelict-Probe/viewer/static/`:
   - a "Frigate modules" column and filter/sort, with the column order kept stable and new columns appended;
   - on the system page, mark which crates hold modules, on the floor maps and in 3D.
5. Run the backlog over all 60,190 systems at BelowNormal priority, resumable, publishing every 500 rows via the existing publisher. Report the time per system first and the total ETA.
6. Run the regression tests (add checks for the new columns), `python -I tools/derelict_view.py --verify` and `python -I tools/extra_containers_705.py --check`, then report.

## Task 2: delete systems below a threshold and keep statistics about them (DESIGN FIRST, delete nothing until the user approves)

The user wants the scanner to drop systems below a quality threshold, so the published atlas only holds worthwhile derelicts, while keeping statistics about what was removed.

1. Propose the threshold rule and show its effect before changing anything. Examples:
   - total crates + footlockers < N;
   - or frigate_modules == 0;
   - or a combination.

   Show the numbers for a few candidate thresholds: how many systems stay, how many go, and the effect on file sizes. Make it configurable in the scanner. The top-100 ranking and maps must never lose a system that would rank in.
2. Statistics kept for the deleted systems: aggregated per region and globally, in a small published file (e.g. `stats/pruned.json.gz`, documented). For example:
   - count; median, mean and max crates, footlockers, briefcases and tall lockers;
   - the distribution of presets (derelict types) and the most common type;
   - the room-count distribution;
   - the end-reward distribution by item and class;
   - the total frigate modules lost;
   - the threshold used, and when.

   Make it deterministic (same input gives the same bytes) and updated by the scanner whenever it prunes. Propose any other useful stats.
3. Back up the region files under `D:/Orca/NMS-Derelict-Probe-backups/` before the first prune. Pruned systems must not be re-added by later scans, and the scanner should not waste time regenerating them: record the pruned glyphs compactly, or prune at scan time.
4. Viewer: show the pruned-system statistics, e.g. a "Pruned systems" panel per region and globally. The table counts must state that pruned systems are excluded.
5. Present the threshold numbers and the stats file format to the user, and wait for an explicit OK before the first real deletion and push.

## When done

Report a summary, the tests run with their real results, any blockers, and how the user reaches the viewer and scanner (`http://127.0.0.1:8765/` viewer, `:8790` scanner app). Update STATUS.md, WORKSPACE_STATE.json and the coordination Log.
