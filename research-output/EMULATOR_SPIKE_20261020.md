# Emulator spike: real writer FUN_14039E5E0 under Unicorn (2026-10-20)

## Result

**Success.** The native layout writer, run unmodified in Unicorn on the fixture seed `7D7ED1B33E15365D` and preset CARGO_BUGS, returns **11 rooms** and emits **145 placement descriptors**. These match the known-derelict replay (`research-output/known-derelict-replay-20261019/`) on every check made. Roughly 40 tool calls were used.

| Check | Emulator | Replay | Match |
|---|---|---|---|
| Writer return value (rax = room count, `ok` = reached sentinel) | 11 | 11 rooms | yes |
| Placement descriptors captured at the A4720 call | 145 | 145 instances | yes |
| Multiset of scene resources (descriptor to source row to template MXML Filename) | equal | | yes, empty diff both ways |
| Instances per room 0..10 | 15,3,10,13,2,27,3,26,4,20,22 | identical | yes |
| Room families from the 0x40-byte room records | CARG, BARR, CARG, CARG, BARR, BARR, BARR, CARG, BARR, CARG, END | same dominant families | yes |
| Positions | not fully verified (see below) | | partial |

Notes on the table:
- Room records at the out buffer, byte `+0x20` = room-type index, `+0x28` = name: R_S_CARG, B_BUG_BARR, R_S_BUG_CARG, R_S_BUG_CARG, B_BUG_BARR, R_BUG_BARR, B_BUG_BARR, R_BUG_CARG, B_BUG_BARR, R_BUG_CARG, R_END. The replay labels rooms 4 and 6 `main_room`; the writer says branch rooms. That is only a replay labelling difference, since the families agree.
- Position check: I computed the base position `-32+(dx-6)*8, -16+(dy-3)*8, -32+(dz)*8` from the descriptors and compared it with the replay `layout_x/y/z`. Per instance the delta is a small grid-aligned constant (0/8/16/24 in x and z, 0 in y; 10 distinct deltas). That is what the rotated source-row translation should add. A4720's exact matrix was not run, because A4720 is stubbed.
- The reward/crate counts (17 crates + 6 footlockers) were not tested. They come from authored scene references, downstream of A4720.

## Run effort
About 4.0 min and 2.45 M A3270 calls. The writer's retry loops (200 x 500 x 1000) rejected 4,618 candidate layouts before accepting the one at A2780 (3 calls). That is roughly 1.5 billion emulated instructions at about 12 M instr/s. Native speed is far faster, but a Python-driven "any seed" loop would cost minutes per seed. A faster path is native-code stubs or fewer Python hooks (the current hooks are cheap already; the time is the Unicorn core).

## How to run
```
%USERPROFILE%/tools/NMS-Shipwright/.venv/Scripts/python.exe -I D:/Orca/NMS-Derelict-Probe/tools/emulate_writer_705.py --max-insns 3000000000
```
Outputs in `D:/Orca/NMS-Derelict-Probe-analysis/emu/`:
- `last_run_summary.json`: result, entry counts of writer stages, stub calls, and `compare_to_replay`.
- `outbuf.bin`: first 64 x 0x40-byte room records (11 valid).
- `a2780_placements.bin`: the 145 x 20-byte placement descriptors.
- `emu_placements.json`: decoded placements (source row, descriptor, template id, scene, room, grid xy/z).
- Helpers: `disasm_va.py` (capstone disassembler for the exe; capstone installed to `pylib/`), `cmp_rows.py`, `cmp_desc.py`.

The 300 M default instruction budget stops before acceptance; pass at least `--max-insns 3000000000`.

## Observed (works)
- Harness is a trimmed copy of Shipwright `emu.py` (MIT, attributed in the file header): no exeaddr, no globals, no pak extraction, no gamepath; loads only the read-only analysis copy `D:/Orca/NMS-Derelict-Probe-analysis/rea/NMS-13D5060D.exe` (SHA 13D5060D...).
- Global `0x145092FF0` built as `+0x00` templates table, `+0x24` = 1876, `+0x28` = source rows. Nothing else in that global was needed.
- Templates table: `D:/Orca/Temp/generatedbase-table-705-mbc707/generatedbasetemplatestable.mbin` via `load_mbin`. Its 38 RoomTemplates rows match the live-captured rows (run `ec256227...`) qword for qword, ignoring pointers: 0 diffs.
- Preset: element 7 (stride 0x90, array data at MBIN file offset 0x30) of `freighterdungeonstable.mbin` = CARGO_BUGS, directly usable as R9 (same layout as the live header).
- Source rows: live `source-rows.bin`; each row's `+0x2A0` descriptor pointer is remapped to the matching element of the table's first array (319 elements, stride 0x50). The live descriptors are exactly elements of that array, 319 distinct, so the "descriptor" is the first-array element and the 0x80-byte dump spans the next element too.
- Two MBIN-vs-runtime differences handled: (1) GenerationRules entries are polymorphic `{rel offset u64, type hash u32, 0xEEEEEE01}`; `load_mbin` needed an extra fixup turning rel into an absolute pointer (stock Shipwright code leaves them dangling, which faulted at `0x14039E7F2` reading `0x168`). (2) The runtime fills descriptor qword `+0x18` and rewrites array flag words; I overlay the live-dumped plain-data qwords (first 0x50 bytes) onto the 319 descriptors. Whether the `+0x18` overlay is required for acceptance was not isolated.
- Stubs (hook records args, then returns): `FUN_142C1FE30` (returns fake allocator object), `func_142C20E80` (bump alloc), `FUN_1403A4400`, `FUN_1403A4720` (captures the placement array), `FUN_1403A51B0`, `FUN_142BFF9A0`, `FUN_142C090F0`, `func_142BFA8F0` (free), `FUN_142C22170`. Imports `_aligned_malloc` / `_aligned_free` only. No other engine call was reached.
- EDX `0x4951E1` is irrelevant (A4400 stubbed).

## Inferred
- Placement array record = 20 bytes (count at `array+4`, data pointer at `array+8`), per `PLACEMENT_RECORD_AND_INSTANCE_CHAIN_20261019.md`; the matching counts support this.
- Descriptor index order equals the MXML `DecorationTemplates` order (used for scene names); the scene multiset match supports this.

## Unknown / not done
- Exact world positions and rotations (A4720 transform chain not emulated); the 23 containers (authored scene references).
- Whether descriptor `+0x18` and the source-row contents are static per derelict (STATUS assumption: capture a second derelict).
- Seeds other than the fixture were not run. The source rows (1876 x 0x2B0) were captured live, not generated; generating them (the row builder `FUN_14039EC00` or the scene-map callback path) is the remaining piece for a no-game "any seed" tool. Table/preset parts come from MBINs, so this is the only live-captured input left.
- Not isolated: whether `FUN_142C1FE30` / `142C22170` allocator-scope semantics matter (the stub is trivial and the result is correct).

## Next steps
1. Run a second seed, using the same rows (assumed static), against another captured derelict to verify.
2. Emulate or hook A4720's transform to get positions and compare with `layout_x/y/z` exactly.
3. Emulate the row builder `FUN_14039EC00` so the 1876 source rows need no live capture.
4. Make the long retry loop faster (smaller `count` granularity, or detect the first accept) if many seeds are wanted.
