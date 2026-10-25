# Q4: why the offline port emits 59,606 placements instead of 145

Build: NMS 7.05, NMS.exe SHA-256 `13D5060D…3499`. Fixture `00003B0006606CAA`, preset `CARGO_BUGS`, writer seed `7D7ED1B33E15365D`. Nothing here launched or attached to NMS.

## 1. Root cause (observed)

- **Reproduced.** `reconstruct_cargo_bugs_candidate_705.py` gives 59,606, accepted on selection attempt 71. This is the same as `CARGO_BUGS_ZERO_OVERRIDE_LAYOUT_REPLAY_20261019.json`.
- **59,601 of the 59,606 placements use rows with dimensions (0,0,0) and an all-zero 600-byte map.** In the direct-MXML catalog, 1,068 of the 1,292 rows are empty in this way.
- **Every placed template has `MaxPerRoom` = 100.** Most have `Probability` 1.0. For example, R_W3 shows 700 placements, which is 100 in each of 7 rooms.
- **Native A2780 explains the count when maps are empty.** In `D:/Orca/Temp/nms-ghidra-targeted-20261019/dungeon_writer_methods.txt`:
  - The only cap is the per-group check `count < row+0x44` (MaxPerRoom), tested once per group and origin (line 3165).
  - Each of the 16 slots then calls A3270 (line 3195), then A5480 and `count++` (lines 3248–3249), with no break (line 3257).
  - An empty map passes A3270 at every origin, and A5480 occupies no cells, so each group fills to about 100.
  - The port follows this control flow faithfully, so the inflation comes from the input rows, not from the A2780 logic.
- **Why the rows are empty.** The provider (`scene_callback_matrix_705._scene_nodes`, `nms_dungeon_offline.load_scene_map_nodes`) walks only the root MXML.
  - `extract_reference_closure_q4_705.py` read the exact `NMSARC.EntitySceneMBIN.pak` (hash-checked) and extracted the reference closure: 161 targets, none missing.
  - 243 of the 319 templates have no direct callback tags, and **all 243** gain tags through `REFERENCE` scenes. Example: `ROOM_WALL_3` → `EMPTY/ROOM_WALL` (7 tags).
  - Every reference edge that leads to a tag has identity rotation, translation and scale. Composing them is trivial, so the fix carries no matrix ambiguity.
- **Native does not drop empty rows either.** The row builder appends a 0x2B0 row (line 863), zeroes 600 bytes (line 895), then runs the callback visitor `FUN_141845A80` (line 915). There is no filter on dimensions.

**Inference (strong): recursive reference import is active in the writer context.** In-game, R_W3 (MaxPerRoom 100, probability 1.0) appears 10 times across the 11 rooms, not about 700. With empty native maps it would saturate exactly as the port does. So the native R_W3 map is non-empty, and its tags exist only in referenced scenes. This settles the open "are recursive references active?" question indirectly. The gate bytes (`+0x14448`, `+0x2C1`) themselves remain unobserved.

## 2. Fix and result

- **The fix is in the map provider; the writer and search code are unchanged.**
  - `nms_dungeon_reference_closure_q4_705.py` walks `SCENEGRAPH` references recursively, in manager preorder.
  - `Q4SourceCatalog` uses that recursive node list for both CELL\*C row expansion and the materialized maps. Row indices shift; for example, quest row 950 becomes 1390.
- **Replay from the identical first-A2780 state** (`q4_a2780_snapshot_diag_705.py` → `Q4_A2780_SNAPSHOT_DIAG_20261020.json`). Pre-A2780 stages never read map rows, so the state is the same for both providers.

  | Provider | Placements | Empty-row placements | Outcome |
  |---|---:|---:|---|
  | Original | 59,606 | 59,601 | Accepted |
  | Q4 | 7 | 0 | Fails: required quest `R_W_CAPT` (row 1390, 3×1×3) in room 2 |
  | Q4, quest tags zeroed | 8 | – | Accepted |

- **The full Q4 driver run** (`reconstruct_cargo_bugs_candidate_705_q4.py`) is not accepted within the native retry limits. The A2780 quest failure recurs 16 times.
- **So the fix removes the inflation but does not reach 145.** It exposes a second, independent gap: populated maps almost never pass A3270 on the post-A1DA0 grid.
  - A scratch probe over every candidate and origin in rooms 0, 2 and 6 found 0–5 fits per room.
  - The rejections are dominated by two checks: the out-of-grid opcode rule (`nms_dungeon_fit_705.py` line 205) and the required-piece-flag check (line 290).
  - Before this fix, the A3270/A5480 path had never been exercised with non-empty maps.

## 3. Unknowns and what would settle them

- **Exact map content per row.** Callback order, the AABB low bound (still the authored-MXML candidate) and CELL\*C order inside referenced scenes are unconfirmed. The 0.3.55 row capture (`FUN_14039EC00` raw 0x2B0 rows) would settle all three. Row R_W3 alone would confirm the referenced tags directly.
- **The A3270 rejection gap.** Possible causes are the grid byte0/byte4 state written by the topology helpers, the fit-bound arguments, or the out-of-grid rule. A capture of the post-A1DA0 grid plus one A3270 call's inputs and output would decide it.
- **The gate values `+0x14448` / `+0x2C1`.** These are only needed for proof; the indirect inference above already covers the behaviour.

## Files (all new)

- `extract_reference_closure_q4_705.py`; `q4-reference-closure-20261020/` (161 members as MBIN and MXML, plus `reference_closure_manifest.json`)
- `nms_dungeon_reference_closure_q4_705.py`
- `reconstruct_cargo_bugs_candidate_705_q4.py` → `CARGO_BUGS_ZERO_OVERRIDE_LAYOUT_Q4_20261020.json`
- `q4_a2780_snapshot_diag_705.py` → `Q4_A2780_SNAPSHOT_DIAG_20261020.json`

Run each script with `python -I -c "import sys,runpy; sys.path.insert(0,<dir>); runpy.run_path(<script>, run_name='__main__')"`. The scripts import their siblings, so `-I` alone breaks those imports.
