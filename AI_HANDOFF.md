# AI handoff — NMS Derelict Probe v0.3.43 app package

## Runtime-dispatch extension 1.0.1 (2026-10-02)

The app package remains v0.3.43. This is a data-only extension refresh test: `runtime-dispatch` advances from 1.0.0 to 1.0.1; its panel payload and API 1.0 action contract are unchanged. The 1.0.0 files remain installed for rollback. Surveyor reads the extension feed from `agent-ui/extensions/index.json` on `main`, independently of the app package updater.

To install it now, open Surveyor v0.3.43 > **Check lane extensions** > update **RUNTIME-A · Live root dispatch** from 1.0.0 to 1.0.1. PR #30 is merged as `f3cfb4ad4bff9391ad3beba77ae3d8f1b7a8f708`. The lane still awaits its separate live `owner+0x10` capture; this extension update changes no probe or controller code.

Verification: the runtime-dispatch extension tests cover API/index compatibility, panel hash/action contract, rejected invalid content, exact preconditions, live refresh, rollback, and evidence namespacing. See `agent-patches/runtime-dispatch/RUNTIME_DISPATCH_EXTENSION_1.0.1.json` for exact results and hashes.

## 2026-10-01 Surveyor UI follow-up

- The main Surveyor window and in-game overlay now use the same live-status formatter. NMS/probe/capture, manual counts, caller scan, exact root caller, telemetry, automatic crates, room loot, trace, generation, last event, and hotkeys are surfaced across both views.
- The main window has a separate **Check lane extensions** action and extension update status. **Check app update** remains the controller release check. The extension feed is the published `agent-ui/extensions/index.json` on `main`; a lane-only update must be published there with its versioned panel and manifest before Surveyor can offer it. Agent B maps to **Seed-B · Seed lineage** (`seed-lineage`).
- Agent Console now shows all four lanes at once in a 2×2 card view. Each card shows its status, request, extension action buttons, and a disabled **Evidence upload confirmed** checkbox. The checkbox is checked only when that lane has a successful local action record containing the GitHub `research-uploads/<lane>-…` receipt. Prior successful receipts remain checked even if a later run fails. Request-only actions remain visible but disabled until the lane requests Surveyor input.
- The `Root dispatch +0x10 captured` Runtime-A event is still not emitted by the standard v0.3.41 live-status feed. It must not be represented as the ordinary exact-root-caller result; the Runtime-A live capture remains pending.
- Linux validation: `python -m unittest discover -s tests` (150 tests) and `python -m compileall -q tools overlay tests`. Tk visual rendering could not be checked in the headless workspace; verify card fit on Windows at the target display resolution.

## Current handoff state

The latest full Surveyor app package is v0.3.43. Its shared extension host reads `agent-ui/extensions/index.json` on `main`, independently of the app package updater. The runtime-dispatch extension is now v1.0.1; v1.0.0 remains available for rollback. The update changes only the extension version/catalog entry and associated tests/handoff; the panel payload, API 1.0 contract, controller, probe, and game behavior are unchanged.

The four-lane extension host remains data-only. It validates dependencies, API compatibility, and declared SHA-256 hashes before installation; extensions use only registered `research.*` actions, with preconditions rechecked before execution. The current runtime-dispatch action is `research.analyze_generation`, namespaced to `runtime-dispatch`, with empty parameters and preconditions `workflow.idle`, `nms.running`, and `probe.connected`.

The runtime-dispatch lane still needs a live `owner+0x10` slot value and target identity at the descriptor-correlated root event. The latest reviewed upload repeated root candidate `9256392A2F5A74AC` but omitted that slot value. No full traversal is required. The separate post-7.05 `MEDI_FLOATERS` layout remains an inference from its own capture and was not reproduced in the latest Runtime-A analysis session.

## Exact next action

**Extension refresh check:** open Surveyor v0.3.43 > click **Check lane extensions** > update **RUNTIME-A · Live root dispatch** to v1.0.1 > confirm the app reports the updated extension. No Surveyor app or NMS restart is required for this data-only extension update.

**Runtime research remains separate:** use the existing Runtime-A build from its lane manifest > fully exit NMS > start NMS from Surveyor > load the known derelict only until **Root dispatch +0x10 captured** appears > click **Analyze generation + upload** > return to Main and write `check`. Stop at the capture indicator; no full traversal is required.

Focused extension/refresh/rollback/precondition/namespacing verification passed 18/18. The tests do not replace the outstanding Windows visual check or live NMS capture.

## Canonical source status

The full app package remains v0.3.43 and is served through `update-manifest.json`. Runtime-dispatch extension v1.0.1 is published through the shared `main` extension index; it can update independently of the app package. The complete source snapshot for this lane update is `NMS-Derelict-Probe-v0.3.43-runtime-dispatch-extension-1.0.1-source.zip`.

---

## Prior Agent Console implementation record

The v0.3.39 standalone Surveyor opened a compact read-only Agent Console beside the main UI. The current v0.3.41 candidate retains it and adds the extension panel described above. It still cannot read private chats; agents must publish STATUS.json updates for new requests to appear.

No probe, game overlay, or controller-command protocol was changed. The Agent Console is a separate Tkinter `Toplevel` and has no access to NMS memory.

Current published lane picture at the v0.3.39 source snapshot:

- Runtime-A needs one short live capture of the exact `owner+0x10` dispatch slot. No full derelict traversal is required.
- Seed-B has published system-seed anchors; it requires no Surveyor action.
- DUNGEON-C uploaded its offline NMS.exe scan (38 candidates; no multi-anchor matches; generator consumer unidentified); agent work can continue offline.
- Metadata-D is free at the last sync.

The remaining human action is Runtime-A. Exact recipe: extract and run `NMS-Derelict-Probe-v0.3.38-RUNTIME-A.zip` > start NMS from Surveyor > load the same known derelict only until **Root dispatch +0x10** is captured > click **Analyze generation + upload** > return to this Main chat and write `check`. No full traversal is required. The Agent Console can copy these steps.

## Agent status data contract

`schema/agent-status-v1.schema.json` defines the additive lane status format. Agents commit `agent-patches/<lane>/STATUS.json` on their own branch when work starts, changes state, or needs a human. Required fields are schema version, lane, UTC update time, state, and summary; human requests carry exact steps, success condition, evidence to return, and full-traversal requirement. Main updates the integrated `WORKSPACE_STATE.json`. The console falls back to current lane manifests when no STATUS.json exists yet.

## Run and verify

- Normal launch: extract the complete project ZIP and double-click `Start-Surveyor.cmd`. The main Surveyor and Agent Console open independently from NMS.
- Runtime: existing Python 3.12/3.13 plus Tkinter; the Agent Console adds no installed dependency and sends only public read-only GET requests to this GitHub repository.
- Regression tests: `python -m unittest discover -s tests`.
- Syntax check: `python -m compileall -q tools mod overlay tests`.
- This v0.3.39 ZIP is an integration candidate. The in-app updater serves it only after the matching PR's `update-manifest.json` and package chunks reach `main`; until then, install from the complete ZIP.

## v0.3.39 verification and limits

Agent Console data logic: 6 focused tests pass. Full regression suite: 119/119 pass. `compileall` passes; 37 packaged JSON files parse. The Tkinter window has not been visually exercised on Windows in this environment. Agent updates remain invisible until their status/manifest changes are committed to GitHub; the console cannot inspect chat state.

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

Historical v0.3.34 action; superseded by the v0.3.38 exact caller capture and the current Runtime-A dispatch-slot validation described above.

## v0.3.32 exact runtime caller correlation

The corrected v0.3.31 offline scan found 52 direct references to the verified logical entry `0x00634BC0`, proving the function is generic enough that static xrefs alone do not identify the derelict-specific path. v0.3.32 adds a narrow read-only signature hook at that entry. It records seeded descriptor calls only in a bounded in-memory ring, then correlates the exact descriptor pointer when `DUNGEON.SCENE.MBIN` reaches `Engine::AddResource`. The root event stores `logical_entry_matches`, `logical_entry_nearest_caller_return_offset_hex`, and a small code window.

Historical v0.3.32 action; superseded by the current Runtime-A capture request above. Do not ask the user to repeat older exact-caller work.
### v0.3.34 launcher repair
- Standalone Surveyor Start NMS now uses the repaired `Start-NMS.ps1`.
- Do not restore the old `import nmspy, pymhf 2>$null` hard gate; it hid the actual Python traceback and could loop on a package that pip reported as already installed.
- The launcher tests/repairs the selected runtime, may fall back to Python 3.12, writes pyMHF local config, and starts via `python -m pymhf run nmspy`.
- Runtime failure evidence: `%LOCALAPPDATA%\NMSDerelictSurveyor\runtime-repair-latest.log`.


## v0.3.36 launcher correction
The standalone controller remains the primary UI, but Start NMS must not import pyMHF inside the controller's hidden/captured PowerShell process. pyMHF creates questionary/prompt_toolkit console objects at import time and fails there with `NoConsoleScreenBufferError`. Start-NMS.ps1 now checks package metadata without importing pyMHF, prepares the probe/config/optional overlay, then spawns a fresh visible cmd.exe which runs the proven `pymhf.exe run nmspy` command. Do not reintroduce a hidden pyMHF import preflight or Python downgrade workaround for this console error. The all-52 exact-caller correlation remains unchanged.

## v0.3.38 exact root caller result / next action
Baseline B short capture on 2026-09-30 correlated the exact dungeon descriptor pointer `0000017475826D28` / root seed `9256392A2F5A74AC` to external caller return RVA `02BFCC1A` with recursion depth 0 and age 0.74 ms at the root add. This RVA was **not** among the 52 direct E8/E9 static references to logical entry `00634BC0`, so the derelict path is likely indirect (function pointer/thunk/other non-rel32 transfer) rather than one of the 52 direct xrefs. Do not infer a symbol yet.

v0.3.38 added `tools/extract_exact_root_caller_code.py`, `Extract-Exact-Root-Caller-Code.cmd`, a standalone UI button **Extract exact root caller + upload**, and GitHub action `extract-exact-root-caller`. It reads `%LOCALAPPDATA%\NMSDerelictSurveyor\asset-work-v1\exact-root-caller-latest.json`, maps the exact RVA into installed `NMS.exe`, captures a bounded code window, and conservatively recognizes direct `E8 rel32` and indirect `FF /2` calls. Output: `exact-root-caller-code-latest.json`. This historical action is complete; the current Runtime-A request is to inspect the exact dispatch slot live.


### v0.3.38 next research step
The exact external call at `02BFCC17` decoded as `FF 52 10`, targeting the verified logical function `00634BC0`. Static resolution found no coherent conventional vtable candidate. The current follow-up is Runtime-A's live capture of the value at `owner+0x10`; do not call it a proven C++ vtable slot or class.


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

## 2026-10-01 Agent Console layout update

- The Agent Console now shows all four lanes side by side in one row. Each lane's status, summary, Surveyor request, upload receipt, and extension details sit in an independently scrollable information area.
- The header's **Check extensions** action refreshes the published extension index for all lanes in one request.
- Task actions, Copy full steps, and per-lane extension update controls stay in a fixed bottom strip. Each lane update button reflects that lane's state; **Update all** installs every currently available extension update after one confirmation.
- Agent status refresh and copy-summary controls are also anchored below the lane cards. Action-button availability continues to follow the active extension's preconditions and each lane's human-request state.
- Validation: `python -m compileall -q tools overlay tests`; `python -m unittest discover -s tests` (150 tests passed).
- Windows visual rendering was not exercised in this Linux workspace; review the four-column width on the target display after launching the updated Surveyor.


## v0.3.43 Agent Console update

- Lane panels show extension status/version and upload confirmation first.
- Mouse-wheel events are routed to the nearest scroll canvas under the pointer; the main Surveyor page and each lane panel scroll without targeting the scrollbar. Tk Text output retains native wheel behavior.
- Upload all confirms once, then runs currently eligible lane extension actions sequentially. Request-only actions require an active lane request; preconditions are rechecked before each action. Skipped actions are logged, and final UI directs the user to inspect each lane upload receipt.
- Verification: `python -m unittest discover -s tests` (151 passed), `python -m compileall -q tools overlay tests`. Tk visual QA remains pending on Windows.
- Next action: install Surveyor 0.3.43, verify wheel scrolling over the main page and lane cards, and exercise Upload all with only the intended lane requests enabled.

## Seed-lineage extension 1.0.2

Published a version-only refresh of the seed-lineage Surveyor extension for update testing. The panel contents and host action are unchanged from 1.0.1: `research.extract_caller_code`, precondition `workflow.idle`, empty API 1.0 parameters, evidence namespace `seed-lineage`, and `request_only: true`. Extension 1.0.1 remains installed for rollback.
