# Game-update resilience for the derelict generator, scanner and atlas (2026-10-22)

User request: "ok, do all steps now" (5 steps: scanner guard, version tag, auto-relocate, old-vs-new comparison,
golden in-game cases). NMS was never launched or attached; exe files were only read from disk. Nothing was committed
or pushed; the atlas was not republished (the scanner's next upload picks up the new index tag). Every edited file has
a `*.pre-update-guard-20261022` backup.

**Untested on a real different build.** The only NMS.exe on this PC are the installed game and the pinned copy, and
both are 7.05 (`13D5060D...3499`). Everything below was tested on 7.05, on a byte-perturbed copy, on a relocated
(code-shifted) copy of the 7.05 exe, and on a perturbed data profile.

## Why it matters

The generator, end-reward and crate-loot predictors make **7.05** results whatever is installed. They read a pinned
copy of the 7.05 exe plus 7.05 tables extracted earlier. One step was not pinned: the space-POI position (Shipwright)
read the **installed** NMS.exe and its globals. So after a Steam update, new atlas rows would have silently mixed
7.05 layouts with POI positions from the new build.

## Step 1: scanner guard (`tools/update_guard_705.py` + small hook in `app/scanner.py`, `app/atlas.py`)

- `check("publish")` takes milliseconds once the exe hash is cached (first call about 0.4-0.7 s, then 20 ms in the
  hook test). It compares the installed NMS.exe SHA-256 (settings / Steam, **never the running process**) with the
  generator's pinned copy, plus the PAK names and sizes with `minimap/build_baseline.json`.
- `check("start")` takes about 1-1.5 s (4 s while the comparison runs loaded the CPU). It adds raw-byte fingerprints
  of the 9 game tables / scene sets the chain reads, and the 54 pure-Python golden seed checks.
- Hook: on Scan start, every 60 s in the main loop, and before every `Atlas.claim / publish / publish_batch /
  _commit_push`. When the game changed it raises `UpdateBlocked`. That class is deliberately not a RuntimeError, so the
  scanner's GitHub-retry wrapper `_net` cannot swallow it. The scanner goes to state `error` with the message
  **"NMS was updated: generator data is 7.05; run the update check (tools/Check-After-NMS-Update.cmd, then
  research-output/GAME_UPDATE_RESILIENCE_20261022.md). Scanning and publishing are paused."** This message shows in
  the phone page and the desktop app (both show `s.error`). `snapshot()["update_check"]` carries the last result.
  Computed rows stay in the local store and caches (nothing is lost). No game install found = warning only.
- A build that the comparison found equivalent can be accepted: `python -I tools/update_guard_705.py --accept --report
  <compare json>`. This records `builds/accepted-builds.json`, and the guard then passes for that exe + PAK set.
- Testable without an update: `NMS_UPDATE_GUARD=off`, `NMS_UPDATE_GUARD_EXE=<file>|none`, `NMS_UPDATE_GUARD_BASELINE`,
  `NMS_UPDATE_GUARD_PINNED`, `NMS_UPDATE_GUARD_ACCEPTED`.
- **The running scanner keeps its old code until its next restart** (it was not stopped or restarted). One exception:
  `tools/build_atlas_index.py` is reloaded at every publish, so step 2's index tag is live at the next upload.
- Limit: rows computed in the up to 60 s between a Steam update and the next guard check stay in the local store. If
  the comparison says "rescan needed", regenerate those too. In the desktop app's Atlas tab, a manual publish raises
  the same error (that is the intent).

## Step 2: game_build tag (file-level, no per-row cost)

- Region files already name their build in the header (`# generator ...; NMS.exe 7.05 SHA-256 <sha>`). `app/atlas.py`
  now writes that from one constant, `GAME_BUILD = "7.05"`, so the text is unchanged.
- `tools/build_atlas_index.py` reads each region's build. When all match, the index's first `#` line ends with
  `; game_build 7.05 13D5060D`: about 30 bytes, no column, INDEX_FORMAT stays 5. If builds are ever mixed, the index
  gets a per-row `game_build` column and the header says `index format 6` and `game_build mixed (...)`. Tested on an
  atlas copy: uniform gives a byte-identical body plus the tag; mixed gives format 6 with 531/86,733 rows tagged.
- **Rows without a tag are 7.05 implicitly** (every row published so far). The viewer, `build_atlas_index` and the
  docs treat a missing tag as `7.05 13D5060D`.
- Viewer: the atlas header line shows "game build NMS 7.05 (exe 13D5060D)" (`viewer/static/app.js`, live on refresh;
  until the scanner's next upload it shows the implicit 7.05). `views/top100.json.gz` was not changed: its systems
  are a subset of the index.
- Regression e2 ("rebuilt index == published index") fails until the scanner's next upload. That is expected: only the
  header comment differs.

## Step 3: auto-relocate (`tools/relocate_generator_705.py`, `tools/extract_build_data_705.py`, `tools/build_profile_705.py`)

All 52 hard-coded NMS.exe addresses are enumerated in `build_profile_705.ADDRESSES_705`:
- native (11): the writer `0x14039E5E0`, the 9 patched engine functions, and the global `G = 0x145092FF0`;
- diag (15): Unicorn counters only;
- logic (19 incl. 3 data/constants): seed/preset, end-reward and crate-loot functions the Python ports re-implement;
- site (6): instructions inside them;
- poi (5): the Shipwright system generator, which finds these itself by signature.

Also listed are the writer's immediate `0x4951E1` and the struct offsets that no tool can relocate (POI table, row
layout, preset layout, live-reader offsets).

Method: the exe's .pdata gives exact function bounds; a small x64 length decoder wildcards rel32, RIP-relative and
in-image imm64 operands. The tool then uses a 64-byte prefix signature and compares the whole masked body ("body
identical" = same code modulo relocation). It also follows the call graph from the writer (n-th call maps to n-th
call), and finds data through the same instruction in a relocated function. That includes the writer's caller, whose
chained-unwind fragment loads G. Confidence: high / medium / low (body changed) / none.

Self-test (`--self-test`, about 18 s):
- 7.05 vs 7.05: **52/52 exactly** (51 high, 1 medium = G, found through one reference);
- byte-perturbed writer: found, `body_identical=False`, similarity 0.995, verdict "native writer NOT ready";
- code shifted +0x1040 (.pdata and chain records moved with it): **52/52 at 7.05 + 0x1040**.

The live-reader finder (`nms_find_addresses_705`) runs too (0x6E8D6D0 / +0x38).

Output: `builds/<label or sha8>/address_map.json` + `build.json`. It refuses to write the 7.05 folder; the 7.05
profile is built in.

Re-extraction (`--extract`, or `extract_build_data_705.py <game> <out>`) writes the same relative layout as the 7.05
workspace into the build folder: dungeon inputs + provenance, the generated-base table, the 319 scenes + container
indexes (the existing extractor, run unchanged with its hash pins replaced in memory), the writer table, rebuilt
`asset_source_rows.bin`, the space-POI table, a Shipwright globals/metadata snapshot, fingerprints, and
`derived_checks.json`. The derived checks cover PRESETS weights, RefDungeonEntrance, and which tables changed vs 7.05.
**Test:** a 7.05 re-extraction (`--reproduce-705`, same compiler versions as the originals) reproduced **653/653
files byte-identically** in 190 s, including `asset_source_rows.bin` and both container indexes.

Not automatic (reported, manual): a changed writer 2nd argument; changed struct offsets; a changed rewardtable or
gameplay globals (the loot/reward tables are Python constants and must be re-derived into the profile's `overrides`);
a scene count other than 319; DUNGEON_D (measured in game).

`build_profile_705.apply_profile()` runs the **unchanged** 7.05 code as another build by patching module globals and
defaults in memory only: exe, addresses, G, data root, catalog cache, fingerprints, POI pin and predictor overrides.
The shared fast generator files were not edited. A 7.05 snapshot of Shipwright's game data is in `builds/7.05/shipwright/`, so the
old side never reads the installed game.

## Step 4: comparison harness (`tools/compare_builds_705.py` + `tools/compare_builds_worker_705.py`)

RESULTS_PLACEHOLDER

## Step 5: golden in-game cases (`tools/golden_ingame_705.json` + `tools/golden_ingame_705.py`)

One file with only observed facts; unobserved values are left out, never filled with predictions:
- 3 live-census layouts: 003B BUGS 11/17/6/145 instances, 0075 BUGS 9/18/5/121, 0320 FLOATERS 9/29/18;
- 3 end rewards: 0002250006607CAA Fuel Unit B, 00002F0006607CAA (glyphs 502F06607CAA) A-Class Reactor,
  0000FE0006607CAA Salvaged Fleet Beacon C;
- 7 crates: FE room 2 Photon Cannon C x1 and room 3 Larval Core; 0036 rooms 1/4/6/7/8 Frigate Module x1, Tainted
  Metal x30, Hadal Core x2, Larval Core x2, Hadal Core x2;
- 54 seed checks: the 47-seed 0320 recording (44 observed seeds + 3 combined-toast sums; seeds 24, 44 and 45 were not
  visible in the video), the 5/5 tall lockers, and the 2 captured FE crate seeds.

**Result on 7.05: 67/67 pass** (54 seed checks + 13 full-chain checks, 20 s). Hooked into `minimap/check_update.py`
(step 9; `--quick` runs the 54 seed checks), into `update_guard_705.py` start mode (seed checks), and into the
comparison harness (new and old side).

## After an NMS update: runbook (commands in order)

Run from `D:/Orca/NMS-Derelict-Probe`. All steps are read-only on the game folder. EMU python =
`%USERPROFILE%/tools/NMS-Shipwright/.venv/Scripts/python.exe` (the tools start it themselves).

1. The scanner stops by itself with "NMS was updated ...". Leave it stopped.
2. `python -I minimap/check_update.py`: the overview. It shows what changed (exe, PAKs, tables) and whether the 7.05
   generator still passes the golden facts.
3. `python -I tools/relocate_generator_705.py "G:/SteamLibrary/steamapps/common/No Man's Sky/Binaries/NMS.exe" --label <version> --extract`
   This writes `D:/Orca/NMS-Derelict-Probe-analysis/builds/<version>/`. Read the VERDICT and
   `data/derived_checks.json`. If the native writer is NOT ready, or the logic or tables changed, the new build needs
   manual porting. Stop here and keep the atlas at 7.05.
4. (Automatic in step 3: the tool copies the new exe read-only to `builds/<version>/NMS-<sha8>.exe`, and the
   profile uses that copy, so a later Steam update cannot change it underneath.)
5. `python -I tools/golden_ingame_705.py --profile <version> --full-profile`: the 7.05 in-game facts on the new
   build. A failure here is either a real game change or a relocation error. In-game re-checks decide which.
6. `python -I tools/compare_builds_705.py --old 7.05 --new <version> --n 1000 --workers 4` (about 10 min).
7. If the decision is **"atlas valid for new build"**: `python -I tools/update_guard_705.py --accept --report
   research-output/compare-builds/compare_7.05_vs_<version>_1000.json`. Then restart the scanner. It keeps
   publishing 7.05-identical data (the tag stays 7.05: the data is identical).
   If **"rescan needed: loot/rewards only"**: the layouts are valid; the end-reward and frigate-module backfills must
   be recomputed with the new build (scanner owner).
   If **"rescan needed: layouts"**: switching the generator itself to the new build is a scanner/shared-generator
   change. Make a REQUEST in the coordination file: the pinned exe path, `GAME_BUILD`/`EXE_SHA`/`INPUT_FILES` in
   `app/atlas.py`, and a rescan of the affected presets.
8. `python -I minimap/check_update.py --save-baseline` once the generator is adopted for the new build.

## Files

New (all ours, in `tools/`): `build_profile_705.py`, `update_guard_705.py`, `relocate_generator_705.py`,
`extract_build_data_705.py`, `compare_builds_705.py`, `compare_builds_worker_705.py`, `golden_ingame_705.py`,
`golden_ingame_705.json`, `test_scanner_update_guard.py`. New data: `D:/Orca/NMS-Derelict-Probe-analysis/builds/`
(`7.05/` reference + Shipwright snapshot, `_reextract-705/` test re-extraction, `_perturbed-test/` test profile).

Changed, with backups `*.pre-update-guard-20261022`:
- `D:/Orca/NMS-Derelict-Probe-fastgen/app/scanner.py` (hook), `app/atlas.py` (GAME_BUILD + guard callback);
- `tools/build_atlas_index.py` (tag), `viewer/static/app.js` (label), `minimap/check_update.py` (steps 8 and 9),
  `minimap/README.md`;
- `STATUS.md`, `WORKSPACE_STATE.json`, `D:/Orca/NMS-COORDINATION.md` (NOTICE/DONE).
