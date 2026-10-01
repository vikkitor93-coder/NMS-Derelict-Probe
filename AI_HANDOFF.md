# AI handoff — NMS Derelict Probe v0.3.38

## Read this first

This file is the **current technical handoff**, not a chronological log. Historical implementation details and old next-actions belong in Git history / `CHANGELOG.md` and must not override the current registry.

New agents should read in this order:

1. `AGENT_START_HERE.md`
2. `WORKSPACE_STATE.json`
3. `RESEARCH_INDEX.md`
4. `PROJECT_PROFILE.md` for stable project context and constraints
5. this file for current technical state and next action
6. `AGENT_WORKFLOW.md`
7. the assigned lane manifest and only relevant changed files/evidence

The repository is the continuity layer between normal ChatGPT, Work, Codex, and other AI agents. Do not rely on hidden chat context.

## Shared mission

Reverse engineer No Man's Sky abandoned/derelict freighter procedural generation far enough to identify and safely invoke the real dungeon generator directly.

Long-term target:

`seed -> invoke real NMS derelict/dungeon generator -> capture selected preset/layout/rooms/resources -> next seed`

The unresolved chain all agents are contributing toward is:

`universe address/system -> system seed -> POI/derelict seed derivation -> weighted DungeonOptions choice -> GcDungeonGenerationParams consumer -> room/layout/resource generation`

The project is no longer starting from zero: both runtime and static/public anchors exist on multiple points of this chain.

## Product architecture

Surveyor runs independently of NMS.

- `tools/surveyor_controller.py` is the standalone primary UI.
- `Start-Surveyor.cmd` / `.ps1` starts Surveyor only.
- `Start-NMS.ps1` detects/persists NMS.exe, syncs the pyMHF probe to `GAMEDATA\MODS`, prepares config, then launches the proven visible `pymhf.exe run nmspy` path.
- Surveyor survives NMS exit and can restart without restarting NMS.
- The injected `DerelictBaselineProbe` is `@no_gui` and acts as a read-only backend.
- Controller/probe commands use `%LOCALAPPDATA%\NMSDerelictSurveyor\controller-command.json` plus the acknowledgement file.
- Game overlay is optional and defaults off.
- Evidence/local analysis state lives under `%LOCALAPPDATA%\NMSDerelictSurveyor\asset-work-v1`.

Do not reintroduce the old hidden pyMHF import preflight; pyMHF console initialization can fail in hidden/captured PowerShell. Stable launcher behavior is considered working and must be preserved unless a dedicated launcher task says otherwise.

## Canonical source / artifact policy

Canonical baseline version: **v0.3.38**.

Verified complete baseline ZIP:

`/NMS-Derelict-Probe/Canonical/NMS-Derelict-Probe-v0.3.38-canonical.zip`

Recorded SHA-256:

`7ac2ce0c9cf7188839e03dca984b457b649716d4298bcb779ce178a64293a9e7`

Canonical verification before parallelization:

- 113/113 tests passed;
- compileall passed;
- 35 JSON files parsed;
- runtime logic unchanged by canonicalization.

Complete experimental ZIPs are stored in ChatGPT Library. GitHub carries source-state summaries, manifests, reproducible patches, evidence, branches, PRs, and integration state.

## Confirmed runtime baseline

Known baseline universe address:

`00001A0004E84EFD`

Known root resource:

`MODELS/SPACE/POI/DUNGEON.SCENE.MBIN`

Captured root descriptor seed:

`9256392A2F5A74AC`

Verified logical shared entry:

`NMS.exe + 00634BC0`

Exact runtime-correlated external root-path return RVA:

`02BFCC1A`

Exact external call instruction:

`02BFCC17: FF 52 10` -> `call qword ptr [RDX+0x10]`

Same root event correlated:

- owner: `0000017475826C00`
- descriptor: `0000017475826D28`
- descriptor = owner + `0x128`
- primary seed: `9256392A2F5A74AC`
- secondary seed: `FFFFFFFFFFFFFFFF`
- recursion depth: 0
- age at root AddResource: ~0.74 ms

A prior static scan found 52 direct rel32 references to `00634BC0`, but this actual derelict root caller was indirect and was not one of those 52 direct references.

## Critical interpretation cautions

Do **not** call `owner+0x10` a proven normal C++ vtable slot. The offline static resolver found no coherent conventional static vtable candidate for target `00634BC0`.

Do **not** identify `owner` as a normal `cTkResource`; current public `cTkResource` layout places its embedded descriptor elsewhere than `owner+0x128`.

Use neutral terms such as `owner`, `dispatch object`, `dispatch slot`, or `runtime structure` until live evidence proves more.

## Public/static research incorporated

Current public NMS.py definitions independently support the probe's `cTkResourceDescriptor` interpretation:

- descriptor vector at `+0x0`;
- primary `cTkSeed` at `+0x10`;
- secondary `cTkSeed` at `+0x20`.

Public/current metadata establishes an explicit abandoned-freighter configuration chain:

- `GcAbandonedFreighterComponentData`
  - `DungeonRootScene`
  - weighted `DungeonOptions[]`
- `GcFreighterDungeonChoice`
  - `Name`
  - `Weighting`
- `GcFreighterDungeonsTable`
  - `GcFreighterDungeonParams`
  - `GcDungeonGenerationParams`

Known `GcDungeonGenerationParams` inputs include:

- SizeX/Y/Z;
- EntranceX/Y/Z;
- Rooms;
- X/Y/Z probabilities;
- StraightMultiplier;
- MainRoomTypes / BranchRoomTypes;
- quests;
- generation rules;
- pruning rules.

The project already has a current Cosmos `FREIGHTERDUNGEONSTABLE` parser. Do not duplicate it unless your task is specifically improving that parser.

Pi / Every Item Procedural demonstrates the desired end-state technique for other NMS generators: retain a live manager and invoke real game procedural functions repeatedly across seeds. It does **not** already provide the abandoned-derelict interior generator.

ReNMS general WFC/freighter-base `cGcMap` structures are reference material only; they are not proven to be the abandoned-derelict dungeon generator.

## Seed research state

A public disassembly-derived universal-address -> system-seed implementation has been incorporated by the Seed-B lane.

Known anchors now include:

- `00001A0004E84EFD -> B006BAB6 -> initial generator state 3E342BADCF79F176`
- `0001550006607CAC -> 9E1A7905 -> initial generator state 37DEC848947D131C`

Known corresponding captured derelict root seeds:

- baseline 35: `9256392A2F5A74AC`
- baseline 51: `00C9E8DF0327789E`

Direct equality was not found. The system-seed -> derelict-root-seed relationship remains **unknown and unclaimed**.

## Current parallel lanes

The authoritative claim/state registry is `WORKSPACE_STATE.json`.

### Runtime-A — `agent/runtime-dispatch`

Purpose: capture the live value of the exact root event's `owner+0x10` dispatch slot, classify its target/module/RVA, collect nearby qwords and bounded target/thunk bytes, and reconfirm descriptor correlation at `owner+0x128`.

Status: **build ready; awaiting short live validation**.

Manifest:

`agent-patches/runtime-dispatch/RUNTIME_A_MANIFEST.json`

Complete build:

`/NMS-Derelict-Probe/Agent-Builds/runtime-dispatch/NMS-Derelict-Probe-v0.3.38-RUNTIME-A.zip`

No full derelict traversal should be required.

### Seed-B — `agent/seed-lineage`

Purpose: create deterministic system-seed anchors and constrain the unknown derivation into the derelict root seed without inventing a formula.

Status: **first agent output published; do not duplicate**.

Manifest:

`agent-patches/seed-lineage/SEED_B_MANIFEST.json`

The current result is useful upstream anchoring, not a solved derivation.

### DUNGEON-C — `agent/dungeon-decompile`

Purpose: scan the installed current `NMS.exe` offline for dungeon/derelict metadata anchors, xrefs, runtime-function ranges, and bounded code windows to narrow the real `GcDungeonGenerationParams` consumer/generator path.

Status: **tool/output published; waiting for local offline NMS.exe scan**.

Manifest:

`agent-patches/dungeon-decompile/DUNGEON_C_MANIFEST.json`

Game runtime is not required for this scan.

### Metadata-D — `agent/metadata`

Purpose: map abandoned-freighter component `DungeonOptions`/weights, `DungeonRootScene`, dungeon-table presets, and static asset relationships; identify evidence that helps locate the weighted preset-selection boundary without duplicating the runtime/seed/decompile lanes.

Status: see `WORKSPACE_STATE.json`; at the last integration sync this was the free predefined lane.

## Shared open research questions

1. What exactly is the runtime `owner`/dispatch object and what does its live `+0x10` target resolve to?
2. What state/seed feeds the abandoned-freighter `DungeonOptions` weighted choice?
3. Which current NMS function consumes `GcDungeonGenerationParams` to build the derelict layout?
4. How is the captured root descriptor seed derived from system/POI/derelict state?
5. Once the generator boundary is understood, can the Pi direct-call pattern be adapted safely for high-volume offline/in-process derelict generation?

These are one shared problem, not five unrelated projects.

## Evidence discipline

Every conclusion must remain clearly in one of these categories:

- **measured runtime fact**;
- **public/static structure or algorithm confirmed**;
- **inference**;
- **hypothesis**.

Do not upgrade inference to fact because it fits the model. Preserve contradictory evidence.

## User workflow / human intervention preference

The user wants minimal, literal intervention instructions with no interpretive overhead.

When intervention is required, give one step-by-step chain such as:

`Open NMS/Surveyor build > perform exact action > wait for exact visible success condition > click exact upload action > tell Main AI "check"`

Explicitly say whether a full derelict traversal is required. Default is no traversal.

When the user says `check`, inspect only new evidence/commits since the last reviewed state. Avoid rereading unchanged files unless needed for correctness.

## Agent operating rules

- You are one agent among several; do not assume exclusive ownership of the project.
- Work only in your assigned or newly claimed non-overlapping lane.
- Continue autonomously until complete, genuinely blocked, or human intervention is required.
- Keep your Surveyor variant visibly lane-labeled.
- Keep experimental evidence lane-specific.
- Preserve stable behavior and protocols; make changes modular/backwards-compatible.
- Default to read-only NMS instrumentation.
- Run targeted regression tests and report exact results truthfully.
- Publish a lane manifest + reproducible patch/evidence before yielding.
- Never push experimental research changes directly to `main`.
- Integration accepts only the smallest reproducible/proven subset.

For the exact startup prompt and branch/output contract, read `AGENT_START_HERE.md` and `AGENT_WORKFLOW.md`.
