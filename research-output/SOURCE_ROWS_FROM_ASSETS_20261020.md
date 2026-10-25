# Source rows from game assets (2026-10-20)

## Approach
Native emulation of `FUN_14039EC00` was rejected. Its row builder runs engine resource loading (`FUN_142d67410`, the scene manager at `DAT_146e8d708`, `FUN_141845a80` visitor and `FUN_14039FA50`), which is too engine-heavy for the timebox. Path (b) was taken instead: `tools/build_source_rows_from_assets.py` uses the Q4 reference-closure provider for the 0..0x25E map prefix and rebuilds the transform tail (+0x260..+0x29F) from the EC00 decompile.

Fixes found against the EC00 decompile (`dungeon_writer_methods.txt`, around lines 790-815):
- Orientation 2 offset is `x += (dimX-1)*8, z += (dimZ-1)*8`. The older port had X and Z swapped. This was the cause of the 4 door rows and R_OC_DIVIDER; the same dimension swap had made the oriented rows come out wrong.
- Tail layout: 3 axis rows `(ax, ay, az, 1.0)`, then a translation row `(tx, ty, tz, w)`.
- `w` lane: orientation 0 gives `-1 - min over CELL*/NOCELL* of sum(AABBMIN + node pos)` (clamped to 0). Orientation >0 gives `tx0 + tz0 + 2`, from the unrotated translation. Fit to the live data: 1,867 of 1,876 rows matched.
- `+0x2A0` is written as the descriptor index (table array 0, 0x50 stride). All 1,876 indices equal the live pointers' index.

## Byte comparison vs live `source-rows.bin` (pointer qword masked)
- Output: `D:/Orca/NMS-Derelict-Probe-analysis/emu/asset_source_rows.bin` (1,876 x 0x2B0). Comparison: `asset_rows_vs_live.json`.
- Prefix +0..0x25E (map + dims): **1,876 of 1,876 identical**. The old Q4 provider matched 1,871.
- Whole row except the pointer: 1,867 of 1,876 identical. The 9 mismatches are rows 0-7 (stairs_up/stairs_down, all 4 orientations) and row 852 (room_floor_ceilingturret, ori 0). They differ only in the tail translation or `w` lane by 1 ulp (about 4.77e-7, for example `-4.77e-7` vs `0`, or `6.9999995` vs `7.0`). The cause is an engine-side float rounding of the scene bound that is not recoverable from the MXML's 6-decimal AABB strings. None of these differences affect the writer: `FUN_1403A4720` is stubbed and the tail is not read by A2780/A3270.

## Emulator rerun (`tools/emulate_writer_705_assets.py`, new copy; `tools/emulate_writer_705.py` untouched)
- Run B (asset rows, no live inputs for the rows or descriptors; `--no-live-desc`; 236 s, `--max-insns 3000000000`, `emu/assets_run_B/`): ok, **11 rooms, 145 placements, scene multiset equal (empty diff both ways), per-room 15/3/10/13/2/27/3/26/4/20/22, no fault.** The fixture reproduces. The live descriptor qword overlay was therefore not needed for acceptance.
- Run A (`emu/assets_run_A/`, with the live descriptor overlay) is invalid: it gave 9 rooms and 120 placements because of an overlay indexing bug in the new copy. The overlay assumed live pointers (`(p-lo)//0x50`), but the asset rows hold indices. Ignore run A. Use `--no-live-desc` (the way run B ran).

## Remaining gaps
- The 9 rows with tail float noise are not byte-exact (scene bound rounding). An exact fix needs the real visitor bound computation, or a native emulation of EC00.
- The row builder does not model gating assumptions carried from Q4 (importer gates active); the live comparison supports them.
- The table (`generatedbasetemplatestable.mbin`) and preset still come from extracted MBINs. The extracted scene MXML and closure directories are required (they come from the PCBANKS extraction).
- Only the fixture seed and CARGO_BUGS were run. Exact A4720 positions and the crate and footlocker mapping are still open.

## Files
- `D:/Orca/NMS-Derelict-Probe/tools/build_source_rows_from_assets.py`
- `D:/Orca/NMS-Derelict-Probe/tools/emulate_writer_705_assets.py`
- `D:/Orca/NMS-Derelict-Probe-analysis/emu/asset_source_rows.bin`, `asset_rows_vs_live.json`, `assets_run_B/`, `assets_run_A/` (invalid), `assets_run_A.log`, `assets_run_B.log`
