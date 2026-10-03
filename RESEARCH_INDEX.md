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


## Seed-lineage static follow-up (2026-10-02)

Measured from the uploaded offline reports (20261002T221217Z-extract-upstream, 20261002T221235Z-analyze-seed-function): NMS.exe SHA-256 671de22649274b49fa07f5a246bc7252c4e08bb9ab623d2e65722fbab4e497a4; address 00001A0004E84EFD; root seed 9256392A2F5A74AC; candidate logical entry 006388A0 after four CC bytes; root-call .pdata fragment 00638D3C..0063921E. The analyzed function reads the primary seed at second-argument +0x138, which is descriptor +0x10, and tests use-seed at second-argument +0x140, descriptor +0x18. No possible descriptor-field writes were identified in the known prefix. There are 52 direct rel32 references to the entry candidate, 51 outside the known prefix.

Measured from captured caller bytes: call sites 006377B6 and 00637D86 pass RCX=RSI, RDX=RBX; in each path, RBX is the return value from a call to 00637DB0 immediately before the root-handler call.

Inference: seed construction/assignment occurs upstream of the analyzed root handler. The repeated 00637DB0 call is a useful next static target. The available capture does not establish the helper's type or seed logic. The earlier padding-boundary error did not reproduce with this upload, and its local cause is unknown. The system-seed-to-root-seed formula remains unresolved.
