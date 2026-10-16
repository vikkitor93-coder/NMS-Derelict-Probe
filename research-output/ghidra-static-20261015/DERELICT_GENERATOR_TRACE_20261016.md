# Targeted abandoned-freighter generator trace — 2026-10-16

## Target identity and method

- Executable: `G:\SteamLibrary\steamapps\common\No Man's Sky\Binaries\NMS.exe`
- SHA-256: `13d5060d4efb9d2a6a6b1b349bc4257231056cc2a055df4bb15d816262cc3499` (verified locally this pass).
- Analysis used the existing Ghidra 12.1.4 `-noanalysis` project under `D:\Orca\Temp\nms-ghidra-targeted-20261016`; no game process or game files were changed.

RTTI at file offset `0x050FFA40` names `lambda_2` nested in `cGcAbandonedFreighterComponent::GenerateFreighterDungeon(cGcDungeonGenerationParams const&, cTkSeed const&, bool)`. Its lambda operator is at VA `0x14111B730`; it tests resource names `ABANDLIGHT` and `HIDEINABAND`, then updates resource state. This identifies a resource callback within the named method, not the room-graph algorithm.

## Preset selection path

- `FUN_14110A990` contains a RIP-relative reference to `METADATA/REALITY/TABLES/FREIGHTERDUNGEONSTABLE.MXML` (string VA `0x144AC9438`, reference instruction `0x14110A9BD`).
- `FUN_141100D40` selects a weighted record using component configuration at `this+0x8C8` and a seed input. It reads up to 32 entries with 0x18-byte stride and returns a record index.
- Component setup stores `global_table + index*0x90` at `this+0x48`. Worker `FUN_1411001D0` copies that record through `FUN_141100310`, which deep-copies three vector-like fields and scalar fields through offset `+0x78`.
- The cached XML at `%LOCALAPPDATA%\NMSDerelictSurveyor\asset-work-v1\extracted\metadata\reality\tables\freighterdungeonstable.MXML` confirms each `GcFreighterDungeonParams` record contains `DungeonParams: GcDungeonGenerationParams`. It has ten presets: eight with `Rooms=7` and two maze presets with `Rooms=4`. These values are config, not confirmed generated room counts. The table has no crate/loot fields.
- Worker registration: `FUN_1410FFE6F` references callback `FUN_1411001D0` at `0x141100018`, then calls `FUN_142C05640` with queue/lane argument `10`. The wrapper registers a fiber callback and passes exactly the stored context as RCX. Queue failure returns failure fields; it does not execute the callback inline. `10` is a scheduler lane/queue argument; it is not established as a delay.

## Important limitation

`FUN_1411001D0` constructs the copied params and a mixed seed, then calls `FUN_1411015C0`. The decompiled root plus chained funclets for `FUN_1411015C0` use RCX/component only; they enumerate resource handles, schedule callbacks, and update state flags. RDX/R8 are passed by the caller but not read in that body. Therefore this chain does **not** yet establish that the copied table params or mixed seed reach room placement. Do not label it as a verified generation call.

A second RTTI candidate is `cGcBaseBuildingGenerator::SpawnDecorations(...)`, whose nested lambda signature includes `cGcDungeonGenerationParams`, decoration-spawn vectors, and pruning options (RTTI around file offset `0x050CEA10`). Its connection to the abandoned-freighter path and whether it places crates remain under investigation.

## Validation evidence

The saved aggregate `research-uploads/20261013T201043Z-all-saved-evidence-01ac68b9/root-event-latest.json` has a matching root event for address `0000750006606CAB`, root `2A41B0E7EF42A1F7`, `UseSeedValue=true`; the older `2A41B0E7FE42A1F7` spelling is inconsistent with this raw event and appears to be a transcription error. The known 9-room / 18-salvage / 5-footlocker observation is user-reported and not independently tied to this latest event here. The current aggregate CSV did not include a row for that system.

## Still open

1. Trace the actual room-layout builder and establish where the selected parameter record is consumed.
2. Trace `cGcBaseBuildingGenerator::SpawnDecorations` and downstream room-scene placement.
3. Map the 0x90-byte table record to every `GcDungeonGenerationParams` field.
4. Revisit helper RVA `00639BE0` locally; prior workspace state requested a human Ghidra export because local execution had been unavailable, but the matching executable and Ghidra project are now accessible.
5. Find the cleanest manual room/crate observation before emulator validation; no verified loot/reward roll path has been identified.

## Scratch evidence

Working decomp/listing outputs are in `D:\Orca\Temp\nms-ghidra-targeted-20261016`, including `chained_method.txt`, `generator_caller.txt`, `params_builder.txt`, `next_methods.txt`, `component_region.txt`, `callback_scheduler.txt`, `task_dispatch.txt`, and `fiber_trampoline.txt`. They are scratch artifacts; this note records the durable conclusions and limitations.

## Follow-up evidence reconciliation — 2026-10-16

The exact-caller runtime event resolves the previously noted root spelling conflict. `research-uploads/20261013T201043Z-all-saved-evidence-01ac68b9/root-event-latest.json` records universe address `0000750006606CAB`, primary/effective root `2A41B0E7EF42A1F7`, `UseSeedValue=true`, event time `2026-10-13T20:10:33.777Z`, and exact-caller-correlated status. The older `2A41B0E7FE42A1F7` spelling is not supported by this event; treat it as a transcription error unless another raw capture is found.

The same upload's `generation-measurements.csv` has 11 records, none for address `0000750006606CAB` or root `2A41B0E7EF42A1F7`. They cover only `0001550006607CAC` and `00001A0004E84EFD`; the `room-crate-index.json` has 1,433 scene entries and none matched this address/root. Its `generation-baseline-latest.json` is instead for `0000760006606CAB`, with zero observed scenes/rooms/containers and status `needs-review`. Therefore these aggregate artifacts do not independently validate the user-reported 9-room derelict or its container totals against the 10/13 root capture.

The `FREIGHTERDUNGEONSTABLE.MXML` inspection showed ten preset records with configured `Rooms` values of 7 (eight records) or 4 (two maze records). The older empirical measurement CSV includes 9-room results for other systems and demonstrates that configured room budget and observed total room count differ; do not substitute table `Rooms` for observed room count.

New static evidence from parallel review strengthens the worker path but does not identify the layout routine: RTTI ties the `SpawnDecorations` closure to a base-building decoration-spawn function receiving dungeon params and decoration/pruning vectors. This is evidence of a decoration-placement candidate only; no loot/container semantics or abandoned-freighter call chain has been established. The currently confirmed abandoned-freighter worker still ends at a resource-enumeration/state-update method that does not visibly consume its params/seed.


A second pass compared all saved measurement CSVs and all root-event-latest snapshots. No CSV contains address `0000750006606CAB`; the 2026-10-13 journal independently records `2A41B0E7EF42A1F7` on line 967, with caller return RVA `0063AC25` and exact shared-entry caller return `02C0860A`. Multiple Oct 10 and Oct 13 root-event snapshots contain the same address/root; none of the searched root-event-latest snapshots contains the `…FE42…` variant. The journal has many `/DUNGEON/` resource preload/add records, but these are not placed-room or crate observations. No structured or manual observation tying the reported `9 / 18 / 5` counts to this exact root was located in saved evidence.

## Shipwright compatibility baseline — 2026-10-16

- Existing checkout: `C:\Users\Vikman\tools\NMS-Shipwright`, commit `f89691ed037edf437a7406c176aa6b96e654d314`, MIT License. Existing Windows venv: `.venv\Scripts\python.exe`. Cache: `C:\Users\Vikman\AppData\Local\NMS-Shipwright-derelict-test`.
- Local `NMS.exe` SHA-256: `13d5060d4efb9d2a6a6b1b349bc4257231056cc2a055df4bb15d816262cc3499`; file/product version `180836`; PE timestamp `0x6ABE9229`; size `88,560,712` bytes.
- `nms_procgen.exeaddr.resolve` completed successfully. Resolved `gen`, `info`, `planet_sentinels`, and `planet_info` signatures/addresses for this build.
- Smoke test `SystemGen.system(0x0000750006606CAB)` completed in Unicorn. The input decoded to a valid Euclid system-level address (system 117, galaxy address coordinates -853, 6, 1542); result reported valid region, 5 planets, 1 moon, Korvax, inhabited, and 50 generated ships.
- This verifies the existing emulator’s exact-build address resolution and one generator execution. It does not validate derelict generation, room counts, containers, or rewards. No Shipwright source, game files, or running game were changed. The command script is `C:\Users\Vikman\AppData\Local\NMS-Shipwright-derelict-test\smoke_systemgen.py`.

## Helper 00639BE0 descriptor-seed write trace — 2026-10-16

Using a separate Ghidra 12.1.4 `-noanalysis` project on NMS.exe SHA-256 `13d5060d4efb9d2a6a6b1b349bc4257231056cc2a055df4bb15d816262cc3499`:

- Both required sites are direct calls to helper `00639BE0`: `006395D3` and `00639B99`.
- Helper body is RVA `00639BE0..00639FD1` (1,010 bytes), ending in `RET`. It allocates a `0x2A0`-byte owner and calls setup/constructor `00639610`.
- In `00639610`, instruction `006396B3` loads source argument `param_5` from `[RSP+0x80]`; `006396BB` sets `RCX=owner+0x128`; call at `006396C2` invokes `FUN_140227A40`.
- `FUN_140227A40` copies the source bytes at `param_2+0x10..0x2F` to destination `param_1+0x10..0x2F`, which lands at owner `+0x138..+0x157`. Thus the seed-bearing descriptor subobject location read later at owner `+0x138` is populated from caller-supplied `param_5` data. This confirms a write path into the descriptor seed field, but does not yet explain the semantic origin/meaning of all four copied qwords or prove a layout seed formula.
- Scratch decompilation/listing is in `D:\Orca\Temp\nms-ghidra-helper-20261016\helper-constructor.txt` and `seed-subobject-constructor.txt`; the isolated process closed after the trace.

## SpawnDecorations callback trace — 2026-10-16

An isolated Ghidra `-noanalysis` project traced the inferred owner VA `0x1403A4A0B` and closure. Its body iterates resource/template data, computes transformed coordinates, calls helpers `FUN_141843E60` and `FUN_142BE4970`, then schedules a callback through `FUN_141845A80`. RTTI identifies the owner as `cGcBaseBuildingGenerator::SpawnDecorations` with parameters including `DecorationSpawn`, `cGcDungeonGenerationParams const&`, `PruningOption`, and bool. A vtable thunk at `0x1403A8EA0` reaches lambda body `0x1403A4FB0`; that callback resolves a resource handle to a name, uppercases names shorter than 17 characters, checks a captured list, and appends a `0x30`-byte record to a captured vector on match. This is a resource-filter/record-collection callback in a decoration-related path. It is not direct evidence of creating loot or crate objects, and no abandoned-freighter caller was established.

Full scratch traces: `D:\\Orca\\Temp\\nms-ghidra-targeted-20261016\\basebuilding_isolated_trace.txt` and `basebuilding_lambda_trace.txt`. The isolated Ghidra process exited cleanly.

## Chained funclet listing and helper callsite inputs — 2026-10-16

- Local matching-build listing: `D:\\Orca\\Temp\\nms-ghidra-helper-20261016\\listing_0063B130_0063BEEC.txt`; file SHA-256 `57614d0c8494d05ea840ea7cf051ab3a7367606a859abbb47950019fe74a1503`; executable SHA-256 is the matching `13d5060d...cc3499` build. A local contiguous-byte audit counted 811 instruction/data rows and 3,517 bytes, covering VA `0x14063B130..0x14063BEEC` inclusive with no gaps. Ghidra `.pdata` reports the actual function interval as RVA `0063B130..0063BEEC` end-exclusive (3,516 bytes); the requested inclusive endpoint byte `0063BEEC` is the adjacent boundary byte (`INT3`).
- The file includes the requested reference section for `0063BEBC`; Ghidra resolved zero xrefs to that exact address in this `-noanalysis` pass. The bytes are present in the listing; do not interpret zero xrefs as proof of no indirect/data references outside this program database.
- Both `006395D3` and `00639B99` call `00639BE0` directly. In both caller frames, helper stack `param_5` is loaded from the caller's fifth incoming argument (`[RSP+0xF0]`). This shows where setup data comes from at the ABI level; its upstream semantic source and exact equality to any runtime-captured root seed remain unproven.
- Ghidra process exited cleanly after export.

A byte-identical persistent project copy is saved as `research-output/ghidra-static-20261015/LISTING_0063B130_0063BEEC_20261016.txt` (SHA-256 `57614d0c8494d05ea840ea7cf051ab3a7367606a859abbb47950019fe74a1503`).

The `SpawnDecorations` owner’s nearby helper call uses the exact ASCII literal `Decoration` at VA `0x144A58220` (RVA `0x04A58220`, file offset `0x04A57620`). That helper hashes the literal with a per-item seed and traverses/updates connected scene references. This narrows the role to decoration/resource traversal and filtering; it does not support interpreting the path as room-graph or loot/container generation.
