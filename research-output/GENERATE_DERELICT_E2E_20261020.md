# End-to-end derelict generator (2026-10-20)

Tool: `tools/generate_derelict_705.py` (new). Composes `derelict_seed_preset_705.derelict_seed_preset`, `emulate_writer_705_assets.py` (subprocess, `--no-live-desc`, `--seed/--preset-index`), `transform_writer_output_705` (+ `build_source_rows_from_assets`) for scene transforms and authored containers. No existing file was edited.

## Run
    python tools/generate_derelict_705.py <ADDRESS16> [--override 0] [--max-insns 3000000000] [--fixture-check] [--reuse-run] [--out DIR]
Output `D:\Orca\NMS-Derelict-Probe-analysis\emu\generated\<ADDRESS>\derelict.json` (seed, preset, rooms, instances = scene + translation/axes/grid origin in layout space, containers with local/layout positions) plus raw emulator files and `emulator_stdout.log`. The emulator runs with the Shipwright venv python (`%USERPROFILE%/tools/NMS-Shipwright/.venv`, has unicorn; override with env `EMU_PYTHON`). Exit 2 if the writer does not complete.

## Results
| Address | Seed | Preset | Outcome |
|---|---|---|---|
| 00003B0006606CAA (fixture) | 7D7ED1B33E15365D | CARGO_BUGS (7) | 11 rooms, 145 instances, per-room 15/3/10/13/2/27/3/26/4/20/22, 23 containers (17 crates, 6 footlockers). `--fixture-check` vs replay CSVs: all 145 instances and 23 containers matched, max error 1.3e-6 / 4.2e-6. 234 s. PASS |
| 0000750006606CAB | A4391301293DA029 | CARGO_BUGS (7) | 9 rooms, 121 instances (14/5/13/13/9/25/2/21/19), 23 containers (18 crates, 5 footlockers), families EMPTY/BARRACKS/INFESTATION/CARG/COMM/END/SPAWNERS. 70 s, no fault. Matches earlier run. |
| 0000320006606CAA | 1907F3194383C5C4 | CARGO_FLOATERS (6) | NOT completed. No fault, but the writer never returned within 3G, 6G (earlier attempt) or 15G instructions (1656 s). At 15G: A2780 entered 10 times (1 at 3G), A3270 8.7M calls, A1DA0 28k; still retrying. |

## Gaps
- FLOATERS: unresolved whether the writer would eventually succeed (needs more instructions) or loops forever because an emulator input differs for preset 6 (asset-built source rows, preset struct for index 6, or a stub). Next: trace which A2780/A3270 constraint fails for preset 6, or capture a live FLOATERS derelict.
- No ground truth for non-fixture addresses; seed/preset assume weights = MXML and override 0.
- Room records are emitted with name + raw u16s (field meaning not decoded).
- Transforms keep the qualified assumptions of the offline model (authored bounds, callback order).
