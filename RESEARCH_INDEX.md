# NMS Derelict Probe — Research Index

Last updated: 2026-09-30. This file is the short shared truth table for humans and parallel AI agents.

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
