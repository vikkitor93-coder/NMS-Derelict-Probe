# Address -> (writer seed, preset) -- 2026-10-20

Code: `tools/derelict_seed_preset_705.py` (`derelict_seed_preset(address, override=0)` -> `(seed, preset, index)`). Pure Python, no numpy.

## Native evidence (decompiles in D:\Orca\Temp\nms-ghidra-targeted-20261016\component_region.txt, next_methods.txt)
Both the component init `FUN_1410FED60` and the worker `FUN_1411001D0` compute the identical seed:
1. `a = FUN_140583A90(_DAT_146e8d708 + 0xb940)` (current galaxy address, packed; port in `research-output/offline-layout-705-20261019/nms_universe_address_705.py`).
2. If `_DAT_14526D4F0 != 0`, `a` = that override.
3. `a = (a>>33 ^ a) * 0x64DD81482CBD31D7; a = (a>>33 ^ a) * -0x1C955A39EC9ED669; seed = a>>33 ^ a`.
The worker hands `seed` to `FUN_1411015C0` -> writer `FUN_14039E5E0`. `FUN_1410FED60` passes the same seed (record {seed, byte 1}) to the chooser `FUN_141100D40`, then sets component+0x48 = table_base + idx*0x90 (the 0x90-stride freighterdungeonstable rows).

## Chooser `FUN_141100D40`
Weight list at cfg+0x58 (0x18-byte entries, float weight at +0x10, count cfg+0x60, max 32); total = float32 sum.
With lo=u32(seed), hi=seed>>32: n = lo+(lo==0); u = rotl16(lo)^hi^lo; r = (float)((double)u32(n*0x5A76F899 + u) * D) with D = double at 0x144B282D8 = bytes `00 00 10 00 00 00 F0 3D` (about 2^-32); thr = f32(r*total).
cum = w[0]; idx = 0; while cum < thr and k < count: cum += w[k+1]; idx++; k++. The chosen entry's 16-byte key is then matched to the table row key (+0x80, stride 0x90) and that row index returned. Entries are in source order (MEDI_TURRETS .. CARGO_MAZE, weights .66 .33 1 .25 .15 x2), so idx == table index (confirmed by the fixture: 7).
(The same LCG `n*0x5A76F899` appears in the writer; r is a [0,1) uniform.)

## Results
| Address | seed | preset |
|---|---|---|
| 00003B0006606CAA (fixture) | 7D7ED1B33E15365D | CARGO_BUGS (7) -- matches live seed and live preset |
| 0000320006606CAA | 1907F3194383C5C4 | CARGO_FLOATERS (6) (seed equals AI_HANDOFF's prior candidate) |
| 0000750006606CAB | A4391301293DA029 | CARGO_BUGS (7) |

## Cross-checks
- 7.05-era sessions 20261017 (...CAB, ...CAA): family evidence only. CAB scenes include DUNGEON/CARG + INFESTATION (bugs hazard), consistent with CARGO_BUGS; CAA has CARG, SPAWNERS and no INFESTATION, consistent with a non-BUGS CARGO preset (floaters vs turrets/slime not separable from family dirs). Weak, not proof.
- Old Sep/Oct measurements (user-data ...asset-work-v1/generation-measurements) infer CARGO_FLOATERS for 0001550006607CAC / 00001A0004E84EFD but the same address yields CARGO_FLOATERS on 09-29 and MEDI_FLOATERS on 09-30, and the port predicts MEDI_BUGS for both. These are pre-7.05 probe runs on an unknown build with heuristic scene-count inference, and the same address changed preset between runs, so they do not contradict the 7.05 chain (maybe a different exe or a nonzero override). Not used.

## Gaps
- Weights assumed equal to the MXML values (float32); not read from the live cfg+0x58 array. Fixture passing is consistent with it, but one more live preset hit at a non-CARGO_BUGS address would pin it.
- Zero-override path assumed (`_DAT_14526D4F0` never observed nonzero); native edge case (cum runs past the count reading uninitialised stack) clamped.
- REA snapshot not tried; existing decompiles were sufficient.
