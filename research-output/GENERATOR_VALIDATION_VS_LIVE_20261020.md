# Generator validation against live derelicts (2026-10-20)

Tool: `python tools/generate_derelict_705.py <ADDRESS16>`. It computes address → seed → preset (`tools/derelict_seed_preset_705.py`, override assumed 0) and then the native writer `FUN_14039E5E0` under Unicorn, using source rows built from assets.

Ground truth: `research-output/SYSTEM_CRATE_CENSUS.csv` / `SYSTEM_CRATE_CENSUS_20261018.md`. These are Probe proximity-overlay counts from live game sessions, which the user confirmed accurate on 2026-10-18. They were captured before the emulator existed, so they are independent of it.

| Address | Predicted preset | Live rooms / crates / footlockers | Generated rooms / crates / footlockers | Result |
| --- | --- | --- | --- | --- |
| `00003B0006606CAA` (fixture) | CARGO_BUGS (7) | 11 / 17 / 6 | 11 / 17 / 6, plus 145/145 positions | exact |
| `0000750006606CAB` | CARGO_BUGS (7) | 9 / 18 / 5 | 9 / 18 / 5 | exact |
| `0000320006606CAA` | CARGO_FLOATERS (6) | 9 / 29 / 18 | 9 / 29 / 18 | exact |

`0000320006606CAA` session `20261017T203551Z` also has hand-placed markers: 29 `blue_crate` and 18 `footlocker`. These agree with the census.

## Secondary agreement: the old Probe asset analyzer

Earlier Probe versions ran an asset-derived analyzer from the game's live dungeon root seed, a different input from our address-derived writer seed. Its predictions are not physical counts, but they are independent of the emulator.

| Address | Analyzer (session/run) | Analyzer scenes / targets | Generator preset, rooms, instances, containers | Result |
| --- | --- | --- | --- | --- |
| `0001BF0004E84EFD` | CARGO_FLOATERS, run `20261008T140207Z-d8e24197` | 164 / 43 (30 + 13) | CARGO_FLOATERS, 11 rooms, 164, 43 (30 + 13) | exact |
| `0000790006606CAB` | CARGO_FLOATERS, session `20261009T230838Z` | 134 / 32, 10 chunks | CARGO_FLOATERS, 10 rooms, 134, 32 (25 + 7) | exact. The user's markers there are 7 `room` + 3 `room_zero` = 10 |
| `0001550006607CAC` | MEDI_FLOATERS, run `20261008T195817Z-1b73e442` | 146 / 14 (7 + 7) | **MEDI_BUGS**, 10 rooms, 146, 14 (7 + 7) | counts exact, preset name differs |

On `0001550006607CAC`, the generated layout contains 7 INFESTATION (bugs-hazard) scenes, which supports BUGS. The old analyzer inferred the preset name heuristically and gave this address different presets on different days (`SEED_PRESET_SELECTION_20261020.md`), so its name is weaker evidence than its counts.

Other batch outputs, with no ground truth available:
- `0000760006606CAB`: CARGO_BUGS, 12 rooms, 157 instances, 29 + 8.
- `00001A0004E84EFD`: MEDI_BUGS, 10 rooms, 150 instances, 11 + 5.
- `0001680006607CAC`: MEDI_TURRETS, 10 rooms, 145 instances, 13 + 1.
- `00006D0006606CAB`: MEDI_FLOATERS, 9 rooms, 130 instances, 12 + 9.

All six ran without faults, taking 27–338 s of emulator time. Outputs are in `D:/Orca/NMS-Derelict-Probe-analysis/emu/generated/<address>/` (sequential re-run, logs `emu/gen2-<address>.log`). The first parallel batch shared one output folder because of a shell-quoting bug (now `emu/generated-batch1-INVALID-shared-output-dir/`). Its printed summaries equal the clean re-run's.

## What this establishes

- The address → seed mix and the preset chooser are right for two different presets. That includes the MXML chooser weights and the zero override at these addresses.
- The emulated writer reproduces room and container counts for three live derelicts. Positions are verified only for the fixture.
- The earlier CARGO_FLOATERS non-completion was a too-low instruction cap. The native search is long (A3270 entered 18.0M times) but finite.

## Not yet established

- Per-room and per-position agreement for the two non-fixture derelicts. Their census has totals only.
- Presets other than CARGO_BUGS and CARGO_FLOATERS.
- Room-record fields beyond the template name.

## Speed

Unicorn's `count=` instruction cap installs a per-instruction hook. The generator now defaults to `--max-insns 0` (uncapped) and no entry counters (`--counters` re-enables them). Outputs are byte-identical (outbuf.bin, a2780_placements.bin) for `0000750006606CAB` and `0000320006606CAA`, and the fixture check still passes.

| Address | Before | After |
| --- | --- | --- |
| `0000750006606CAB` | 70 s (emulator) | 11 s (emulator), 46 s (whole tool) |
| `0000320006606CAA` | 55 min | 7 min 40 s |
| `00003B0006606CAA` fixture check | 234 s | 57 s |

Backups: `tools/emulate_writer_705_assets.py.pre-nocount-20261020.bak` and `tools/generate_derelict_705.py.pre-nocount-20261020.bak`.

## Independent implementation cross-check

Codex wrote a separate address → seed → preset implementation during the same day (`research-output/offline-layout-705-20261019/nms_dungeon_preset_705.py`, `select_dungeon_preset_for_address`). It was compared with `tools/derelict_seed_preset_705.py` on 2,010 addresses: the 10 real ones above plus 2,000 random ones. There were 0 mismatches in mixed seed, preset name or table index, and all 10 presets occur. Codex's `SECOND_ADDRESS_NATIVE_WRITER_RUN_20261020.md` (`0000750006606CAB`: 9 rooms, 121 placements, 18 + 5) and `A4720_TRANSFORM_CONTAINER_FIT_20261020.md` (fixture 145/145, 23/23) agree with this report.
