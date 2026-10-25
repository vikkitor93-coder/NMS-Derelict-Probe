# Emulator placements to world transforms and containers (2026-10-20)

## Result
Input: emulator run B (`D:/Orca/NMS-Derelict-Probe-analysis/emu/assets_run_B/emu_placements.json`, 145 descriptors, asset-built source rows), CARGO_BUGS entrance origin (6,3,0), reused `nms_dungeon_instance_705.build_scene_instance_transforms` / `transform_authored_containers` (with the orientation-2 fix from `build_source_rows_from_assets`). Script: `tools/verify_positions_containers_705.py`. Run B's summary lacks `preset_index`, so `transform_writer_output_705.py` refuses it; the new script hard-codes index 7.

- **Instances: 145/145 match** the replay room components (`layout_x/y/z`) within 1e-4 (max error 1.35e-6; 124 bit-exact). Matched per (room, scene) by nearest position; 0 unmatched on either side.
  Per room 0..10: 15/15, 3/3, 10/10, 13/13, 2/2, 27/27, 3/3, 26/26, 4/4, 20/20, 22/22.
- **Containers: 23/23 match** the replay by (room, scene, node, kind), max error 4.2e-6; 17 salvage crates + 6 crew footlockers (replay: same). Per room: 0:7, 2:1, 4:1, 5:3, 7:4, 8:1, 9:3, 10:3.
- **The "grid multiples of 8" deltas are resolved.** The spike's base position (-32+(dx-6)*8, ...) omits the rotated source-row translation. A4720 translation = grid translation + `source_translation` (+ axes rotation for 110 of the 145). The 145 instances have 7 distinct source translations (0, 8 on x or z, (8,0,4), (8,0,16), (16,0,8) and 1-ulp variants). Adding them closes every gap.

## Caveats
- Model-to-capture fit, not a live A4720 observation: A4720 stays stubbed; its math is the offline port. Authored bounds and recursive REFERENCE activation remain Q4 assumptions (they fit this fixture).
- Container world positions are layout-space (`layout_local_xyz`); the replay's absolute `x/y/z` columns were not separately compared.
- Matching is by nearest position within (room, scene), so identical scenes in a room are order-agnostic. Per-instance instance_key identity was not checked.
- Only the fixture seed was verified.

## Files (`D:/Orca/NMS-Derelict-Probe-analysis/emu/positions/`)
`scene_transforms.json`, `containers.json`, `verification.json`; script `D:/Orca/NMS-Derelict-Probe/tools/verify_positions_containers_705.py`.
