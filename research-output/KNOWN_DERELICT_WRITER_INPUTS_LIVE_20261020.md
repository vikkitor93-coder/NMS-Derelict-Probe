# Known-derelict writer inputs, captured live (r3) — 2026-10-20

**Run:** CDB observer `0.3.55-cdb-r3-inputs`, run `5429652f8dc945b991a8e2b2e51401c3`, 2026-10-20 00:20:42 UTC, NMS PID 19136, NMS.exe SHA-256 `13D5060D…3499`. One writer call was captured at entry and CDB detached; NMS stayed alive. Raw evidence: `live-runtime/NMSDerelictSurveyor/layout-cdb-r3/5429652f8dc945b991a8e2b2e51401c3/` (`status.json`, `cdb.log`).

## Observed

- Breakpoint `00007FF709FEE5E0` = base `00007FF709C50000` + `0x39E5E0`.
- **Seed record (R8 `000000571A6FFB60`):** seed `7D7ED1B33E15365D`, "seed present" byte `01`.
- **Preset (R9 `000000571A6FFB70`, 0x10 after the seed record):** see the table below.
- Other args: RCX `00007FF70ECE2FF0` (the global `0x145092FF0` rebased), EDX `0x495153`, stack arg 5 `0`, stack arg 6 `000001A3384D4088` (heap output buffer).

| Preset offset | Raw | CARGO_BUGS static input |
|---|---|---|
| `+0x00` | ptr, count 2 | BranchRoomTypes (2) |
| `+0x10` | ptr, count 12 | GenerationRules (12) |
| `+0x20`, `+0x30` | ptr, count 6 each | MainRoomTypes (6), PruningRules (6) |
| `+0x40` | ptr, count 3 | Quests (3) |
| `+0x50 / +0x54 / +0x58` | 6 / 3 / 0 | EntranceX / Y / Z |
| `+0x5C` | 7 | Rooms |
| `+0x60 / +0x64 / +0x68` | 13 / 4 / 13 | SizeX / Y / Z |
| `+0x6C` | 1.25f | StraightMultiplier |
| `+0x70 / +0x74 / +0x78` | 1.0f / 0.5f / 1.0f | X / Y / Z Probability |

Static input source: `research-output/offline-layout-705-20261019/all_10_presets_static_inputs_corrected_20261019.json`, preset `CARGO_BUGS` (table index 7).

## Conclusions

- **Observed:** the address-derived seed `7D7ED1B33E15365D` reaches the writer unchanged, with its present flag set. This confirms the previously conditional seed link (STATUS Q1).
- **Observed:** the runtime preset is CARGO_BUGS. Every scalar and every array count match the static row (STATUS Q2).
- **Inference:** which `+0x20`/`+0x30` array is MainRoomTypes and which is PruningRules isn't resolved from counts alone; the pointed-to element data wasn't read.
- **Inference:** EDX `0x495153` decodes as slot `0x15153`, generation 9. That's a different slot from r2's `0x151E1`, consistent with a per-session runtime handle rather than a layout input (STATUS Q3).
- **Consequence:** the seed and preset inputs to the offline port are correct. Remaining mismatches with the replay are in generator logic or scene-reference handling (STATUS Q4).

## Not captured

The writer's return value, the output buffer contents, and the `RoomTemplates` table rows. The observer now has an optional `.catch`-guarded table read; see `tools/Run-Layout-Capture-0.3.55-cdb-README.md`.
