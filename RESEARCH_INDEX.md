# NMS Derelict Probe — Research Index

Last updated: 2026-10-01. This file is the short shared truth table for humans and parallel AI agents.

## Agent D static abandoned-freighter map (2026-10-07)

- **Measured from installed game assets:** `DungeonRootScene` points to a scene with one `GeneratedBaseRoot` locator, whose attachment entity has gravity-volume and static-physics components. Neither the scene nor its direct attachment names a dungeon room scene. Ten preset main/branch room ID lists are recorded in `agent-patches/metadata/STATIC_ROOT_SCENE_TRACE_20261007.json`; mapping those IDs to actual runtime room scenes remains open.

- **Measured from installed game assets:** the active `MODELS/SPACE/POI/PARTS/DUNGEON_ENTRANCE/ENTITIES/DUNGEONENTRANCE.ENTITY.MBIN` has `GcAbandonedFreighterComponentData`, ten weighted `DungeonOptions`, and `GcOutpostComponentData.AbandonedFreighter=true`. Its SHA-256 is `7ae4acec4521f5e8347b9d61514cf59dae7a24e722a7058a1126beb999b243e8`.
- **Measured from installed game assets:** all ten option names match the ten current `FREIGHTERDUNGEONSTABLE.MBIN` presets. Each MEDI and CARGO set has TURRETS 0.66, FLOATERS 0.33, BUGS 1.00, SLIME 0.25, and MAZE 0.15. MAZE presets specify four rooms; the other eight specify seven. See `agent-patches/metadata/CURRENT_DUNGEON_OPTIONS_20261007.json`.
- **Measured from installed game assets:** the component's `DungeonRootScene.Filename` is `MODELS/PLANETS/BIOMES/COMMON/BUILDINGS/PARTS/BUILDABLEPARTS/SPACEBASE/GENERATEDBASEROOT.SCENE.MBIN`. The similarly named spacecraft entrance entity has an empty options list and `AbandonedFreighter=false`.
- **Unproven:** runtime choice probabilities, normalization, seed input, selection frequency, and whether this static root field resolves to the observed runtime `MODELS/SPACE/POI/DUNGEON.SCENE.MBIN` through intervening calls.

## Seed-lineage capture consistency (2026-10-01)

- **Measured:** caller and upstream evidence both show universe `00001A0004E84EFD`, root seed `9256392A2F5A74AC`, and call RVA `00635110`.
- **Measured:** caller session `20260930T030805Z_00001A0004E84EFD` and upstream session `20260929T203022Z_00001A0004E84EFD` differ. Caller NMS.exe hash is `671de22649274b49fa07f5a246bc7252c4e08bb9ab623d2e65722fbab4e497a4`; upstream hash is `b7913f268dfc62386b6b68f524bfc8ade4a44a9f4fbad39085b7bf51be3680cb`. Caller evidence says `baseline_window_matches_exe: false`.
- **Measured:** rerunning the current boundary detector against the attached caller evidence raises `No compiler-padding function boundary found before the call`.
- **Inference:** the upstream candidate `00634BC0` is not validated for this caller window; do not use it as a current boundary.
- **Hypothesis:** evidence was captured across a running-process/executable change or otherwise mixed across states. A fresh post-relaunch capture is needed to verify.
- **Next:** relaunch NMS from the installed executable, capture one root resource event at the known system, run **Extract caller code + upload**, and verify `baseline_window_matches_exe` before rerunning upstream analysis. No full traversal is required.

## Confirmed runtime facts

- Known baseline universe address: `00001A0004E84EFD` (reality index 0; system index 26; voxel `-259, 4, -380`).
- Root resource: `MODELS/SPACE/POI/DUNGEON.SCENE.MBIN`.
- Root descriptor seed: `9256392A2F5A74AC`.
- Logical shared entry: `NMS.exe + 00634BC0`.
- Exact external root-path return RVA: `02BFCC1A`.
- Call instruction: `02BFCC17: FF 52 10` -> `call qword ptr [RDX+0x10]`.
- Runtime owner pointer in the baseline capture: `0000017475826C00`.
- Runtime descriptor pointer: `0000017475826D28` = owner + `0x128`.
- Primary/secondary captured seeds: `9256392A2F5A74AC` / `FFFFFFFFFFFFFFFF`.
- Offline static resolver found no coherent conventional static vtable candidate for `00634BC0`.

## Confirmed public structure/algorithm facts

- `cTkResourceDescriptor`: descriptors vector at `+0x0`, primary seed at `+0x10`, secondary seed at `+0x20` in current NMS.py definitions.
- `cGcAbandonedFreighterComponentData`: `DungeonRootScene` + weighted `DungeonOptions`.
- `cGcFreighterDungeonChoice`: preset `Name` + `Weighting`.
- `cGcDungeonGenerationParams`: map size, entrance, room count, directional probabilities, straight multiplier, main/branch room types, quests, generation/pruning rules.
- The project already parses current `FREIGHTERDUNGEONSTABLE.MBIN` data; reuse it.
- A public disassembly-derived address->system-seed implementation produces system seed `B006BAB6` for the baseline address. Relation to the derelict root seed remains unproven.

## Hypotheses / open links

1. Classify the unknown runtime owner/dispatch object and resolve `[owner+0x10]` live.
2. Identify the weighted `DungeonOptions` selection boundary and the RNG/seed input used there.
3. Locate the runtime function that consumes `GcDungeonGenerationParams`.
4. Trace system/POI state to root descriptor seed `9256392A2F5A74AC`.
5. Once the generator entry is safe and understood, adapt the Pi pattern to call it repeatedly without gameplay.

## Explicitly disproven / downgraded

- Do not call the `owner+0x10` structure a proven static C++ vtable. Static vtable search returned no coherent candidate.
- Do not identify `owner` as a normal `cTkResource`; public/current `cTkResource` layout places its embedded descriptor elsewhere than `owner+0x128`.
- Do not treat ReNMS general WFC/freighter-base `cGcMap` as the abandoned-derelict generator without direct evidence.
- Do not claim the system-seed -> derelict-root-seed formula is solved.

## Evidence rule

Every conclusion must be tagged mentally as **measured**, **public-structure confirmed**, **inferred**, or **hypothesis**. Never promote an inference to measured fact merely because it fits the current model.
