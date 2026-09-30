# AI handoff — NMS Derelict Probe v0.3.38

## Product architecture

The user clarified that Surveyor itself must run independently of NMS. v0.3.30 moves the primary UI out of the injected pyMHF process into `tools/surveyor_controller.py`.

- `Start-Surveyor.cmd` / `Start-Surveyor.ps1` starts the standalone controller only.
- Backwards-compatible `Start-Derelict-Probe.cmd` now starts Surveyor, not NMS.
- The controller survives NMS exit and has a **Start NMS** button.
- `Start-NMS.ps1` detects/persists NMS.exe, syncs the probe to `GAMEDATA\MODS`, and starts `pymhf run nmspy` in a separate process.
- **Restart Surveyor** restarts only `surveyor_controller.py`; it never closes or restarts NMS.
- Game overlay is optional and defaults OFF.
- The injected `DerelictBaselineProbe` is `@no_gui` and acts as a read-only backend.
- Standalone live-capture controls write `%LOCALAPPDATA%\NMSDerelictSurveyor\controller-command.json`; the probe polls it and acknowledges in `controller-command-ack.json`.
- Existing live status, logs, evidence, GitHub uploads and offline research actions are preserved.

Updater details:
- Controller shows loaded controller, downloaded/source and available versions.
- GitHub helper bug fixed: `_stage_installed_mod` now uses `ROOT / "installed-mod-file.txt"` (v0.3.29 referenced an undefined `SURVEYOR_ROOT`).
- After install, restart only Surveyor to load new controller code. Backend probe changes apply on the next NMS launch unless separately live-reloaded by pyMHF tooling.

Verification for v0.3.34: 106/106 regression tests, compileall, packaged JSON parse, full ZIP integrity, delta integrity, and delta-apply equality against v0.3.32.

## Research state

Latest uploaded `analyze-seed-function` evidence (`20260930T005951Z`) revealed an analyzer-boundary mistake:
- `.pdata` entry containing root call: `0x0063505C .. 0x0063553E`
- this range starts mid-flow (no real prologue, live nonvolatile registers already in use) and is **not** the logical C++ function entry
- original caller window has the unique current-build prologue at `0x00634BC0`, immediately after four `CC` bytes
- v0.3.26 required >=6 padding bytes and therefore skipped `0x00634BC0`, wrongly choosing previous helper `0x006345B0`
- true function at `0x00634BC0` copies second argument to `RSI` at `0x00634BE1`
- primary seed read `movups xmm0,[rsi+0x138]` at `0x00634DBE`, **before** root AddResource
- use-seed flag check `[rsi+0x140]` at `0x00634E26`, **before** root AddResource
- descriptor pointer is `RSI+0x128`; root AddResource is `0x00635110`
- no direct seed write has yet been proven

v0.3.31 corrected both static tools and the corrected scan found 52 direct references. v0.3.34 now observes all 52 through one shared-entry hook and carries the original external caller through recursive invocations using a per-thread stack. Do not claim the `9256392A2F5A74AC` derivation formula is solved until the exact caller is captured and its upstream seed construction is demonstrated.


## v0.3.34 all-callers-at-once correlation

The user explicitly asked to test all 52 static caller references at once rather than batching them. v0.3.34 makes that behavior explicit. One hook at the verified shared entry `0x00634BC0` observes every invocation and records caller return RVA + exact embedded descriptor pointer for seeded descriptors. The verified self-recursive return RVA is `0x00634C63`; it is retained as evidence but excluded when choosing the external root-path caller.

When the exact `DUNGEON.SCENE.MBIN` descriptor reaches `Engine::AddResource`, the probe now records `logical_entry_exact_external_caller_return_offset_hex` plus a larger small code window and immediately writes `asset-work-v1/exact-root-caller-latest.json`. The dedicated file includes the exact external caller, descriptor pointer, root seed, observed caller hit counts, and the static candidate count. `Analyze generation + upload` uploads that file alongside `generation-baseline-latest.json` when available.

Next live action: update to v0.3.34, launch NMS from standalone Surveyor, load a known derelict only until **Exact root caller** changes from `Not captured`, then stop/save and run **Analyze generation + upload**. No full traversal is required.

## v0.3.32 exact runtime caller correlation

The corrected v0.3.31 offline scan found 52 direct references to the verified logical entry `0x00634BC0`, proving the function is generic enough that static xrefs alone do not identify the derelict-specific path. v0.3.32 adds a narrow read-only signature hook at that entry. It records seeded descriptor calls only in a bounded in-memory ring, then correlates the exact descriptor pointer when `DUNGEON.SCENE.MBIN` reaches `Engine::AddResource`. The root event stores `logical_entry_matches`, `logical_entry_nearest_caller_return_offset_hex`, and a small code window.

Next live action: use a known derelict/address, wait only until standalone Surveyor shows **Root entry caller**, stop/save, then run **Analyze generation + upload** (or Measure + upload if a fresh measurement wrapper is desired) and tell ChatGPT `check`. Do not require a full room traversal.
### v0.3.34 launcher repair
- Standalone Surveyor Start NMS now uses the repaired `Start-NMS.ps1`.
- Do not restore the old `import nmspy, pymhf 2>$null` hard gate; it hid the actual Python traceback and could loop on a package that pip reported as already installed.
- The launcher tests/repairs the selected runtime, may fall back to Python 3.12, writes pyMHF local config, and starts via `python -m pymhf run nmspy`.
- Runtime failure evidence: `%LOCALAPPDATA%\NMSDerelictSurveyor\runtime-repair-latest.log`.


## v0.3.36 launcher correction
The standalone controller remains the primary UI, but Start NMS must not import pyMHF inside the controller's hidden/captured PowerShell process. pyMHF creates questionary/prompt_toolkit console objects at import time and fails there with `NoConsoleScreenBufferError`. Start-NMS.ps1 now checks package metadata without importing pyMHF, prepares the probe/config/optional overlay, then spawns a fresh visible cmd.exe which runs the proven `pymhf.exe run nmspy` command. Do not reintroduce a hidden pyMHF import preflight or Python downgrade workaround for this console error. The all-52 exact-caller correlation remains unchanged.

## v0.3.38 exact root caller result / next action
Baseline B short capture on 2026-09-30 correlated the exact dungeon descriptor pointer `0000017475826D28` / root seed `9256392A2F5A74AC` to external caller return RVA `02BFCC1A` with recursion depth 0 and age 0.74 ms at the root add. This RVA was **not** among the 52 direct E8/E9 static references to logical entry `00634BC0`, so the derelict path is likely indirect (function pointer/thunk/other non-rel32 transfer) rather than one of the 52 direct xrefs. Do not infer a symbol yet.

v0.3.38 adds `tools/extract_exact_root_caller_code.py`, `Extract-Exact-Root-Caller-Code.cmd`, a standalone UI button **Extract exact root caller + upload**, and GitHub action `extract-exact-root-caller`. It reads `%LOCALAPPDATA%\NMSDerelictSurveyor\asset-work-v1\exact-root-caller-latest.json`, maps the exact RVA into installed `NMS.exe`, captures a bounded code window, and conservatively recognizes direct `E8 rel32` and indirect `FF /2` calls. Output: `exact-root-caller-code-latest.json`. No NMS run is needed. Next user workflow: update/restart Surveyor, click **Extract exact root caller + upload**, then say `check`.


### v0.3.38 next research step
The exact external call at `02BFCC17` decoded as `FF 52 10`: load vtable from the object and call virtual slot `+0x10`. The runtime target was the verified logical function `00634BC0`. Use **Resolve root vtable + upload** to identify vtable candidate(s), RTTI/class metadata and constructor/reference sites offline. Do not launch NMS for this step.


## v0.3.37–v0.3.38 research/tool state

- v0.3.37 added offline extraction/decoding of the exact runtime-correlated external caller. The known baseline captured `02BFCC17: FF 52 10` (`call qword ptr [rdx+0x10]`) with return RVA `02BFCC1A`.
- The same runtime event correlated owner pointer `0000017475826C00`, descriptor pointer `0000017475826D28` (`owner + 0x128`), primary seed `9256392A2F5A74AC`, and secondary seed `FFFFFFFFFFFFFFFF`.
- v0.3.38 added an offline attempt to resolve the `+0x10` dispatch slot. It found zero coherent static vtable candidates for the verified `00634BC0` target. Treat `owner` as an unknown runtime dispatch/owner structure; do **not** claim a conventional C++ vtable/class until live evidence proves it.
- Next live runtime target: at the exact root event capture `owner`, slot address `owner+0x10`, value at that slot, its module/RVA when applicable, a bounded target byte window/thunk chain, and re-confirm the descriptor at `owner+0x128`. No full derelict traversal is needed.

## External research incorporated 2026-09-30 (not yet runtime-proven)

- Public reverse-engineering provides a disassembly-derived universal-address -> system-seed implementation. For the known baseline universe address `00001A0004E84EFD`, the derived 32-bit system seed is `B006BAB6`. This is an upstream anchor, not yet a proven direct parent of the derelict root seed.
- Current/public metadata definitions confirm `cTkResourceDescriptor`: descriptor vector `+0x0`, primary `cTkSeed` `+0x10`, secondary `cTkSeed` `+0x20`. This independently supports the probe's descriptor interpretation.
- `cGcAbandonedFreighterComponentData` contains `DungeonRootScene` and weighted `DungeonOptions`; each `cGcFreighterDungeonChoice` contains a preset `Name` and `Weighting`.
- `cGcFreighterDungeonsTable` contains `cGcFreighterDungeonParams`, whose `GcDungeonGenerationParams` includes Size/Entrance/Rooms, X/Y/Z probabilities, StraightMultiplier, main/branch room types, quests, generation rules and pruning rules. The project already has a current-Cosmos dungeon-table parser; do not duplicate it.
- Pi / Every Item Procedural demonstrates the desired long-term technique: retain a live NMS manager and call real game generation repeatedly across seeds. The long-term goal is the analogous direct derelict/dungeon generator call, but this is not yet located.
- ReNMS general WFC/freighter-base `cGcMap` structures are useful reference material but are **not proven** to be the abandoned-derelict dungeon generator. Keep that lead separate.

## Multi-agent workflow

- `main` is integration-only. Research agents work on isolated branches/worktrees and never push experimental runtime changes directly to `main`.
- Shared contract: current canonical package + `AI_HANDOFF.md` + `RESEARCH_INDEX.md` + `AGENT_WORKFLOW.md`. Agents should read only their lane's files/evidence unless broader context is required.
- Lanes: `agent/runtime-dispatch`, `agent/seed-lineage`, `agent/dungeon-decompile`, `agent/metadata`; integration is the only lane that combines proven changes.
- Every experimental Surveyor must visibly identify its lane/build (for example `Surveyor · RUNTIME-A`) and write evidence under a lane-specific namespace so simultaneous variants cannot be confused.
- Agents publish a PR containing source changes, tests, evidence schema changes, and a concise handoff. Main integration accepts only reproducible/proven findings.
