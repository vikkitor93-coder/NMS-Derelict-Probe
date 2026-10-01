# AI handoff — NMS Derelict Probe v0.3.41 candidate

## Current handoff state

This is the current continuation point for the main integration worker. The candidate is based on the v0.3.40 Live Output package and is prepared on `integration/issue-8-ui-extensions`; it is not yet the installed `main` release.

- Issue #8 adds `AGENT_UI_EXTENSION_GUIDE.md`, a shared Surveyor UI API 1.0, a data-only JSON extension loader, and one DUNGEON-C sample panel.
- Extensions are downloaded into staging, checked against declared dependencies and SHA-256 hashes, checked for host/API compatibility, and activated without restarting Surveyor. Previous versions remain available for rollback.
- Extension panels can request only the eight stable `research.*` host action IDs. No agent-provided code, shell command, path, or process arguments are run. Preconditions are rechecked at click time.
- Evidence uploads initiated through a lane extension use a timestamped `<lane>-<action>` folder and run manifest. Local action records are also stored under `%LOCALAPPDATA%\NMSDerelictSurveyor\ui-extensions\<lane>\runs`.
- The DUNGEON-C sample panel launches the existing exact-root-caller offline extractor. It does not require NMS to run or a derelict traversal.
- Tests cover compatible install, hash/command rejection, failed-update preservation, live version activation, rollback, and evidence namespacing. Tk visual execution on Windows still needs a human machine.

## Runtime-dispatch UI extension candidate

- Assigned lane branch remains `agent/runtime-dispatch`; this API-host extension continuation is isolated on `agent/runtime-dispatch-ui` and targets `integration/issue-8-ui-extensions`.
- Adds request-only extension `runtime-dispatch` v1.0.0 for Surveyor UI API 1.0.
- It requests only `research.analyze_generation`, gated by `workflow.idle`, `nms.running`, and `probe.connected`; evidence stays namespaced to `runtime-dispatch`. The action uploads the Runtime-A dispatch file when the compatible probe has captured it.
- This is additive data and tests only. It does not alter Surveyor core, controller/probe protocols, or the standalone Runtime-A workflow.
- Post-7.05 capture analysis reports seed candidate `9256392A2F5A74AC`, high-confidence `MEDI_FLOATERS` preset inference, 10 modeled rooms (8 main + 2 dead-end), and 16 analyzer-predicted container targets. The seed capture remains unverified, 8 main rooms differ from table `Rooms=7`, and target counts are not verified physical counts. The pre-update `CARGO_FLOATERS` 8-room / 35-target observation is historical; cause and repeatability are unknown.
- Focused extension tests: 8 passed. Full suite after this addition: 138 passed. Windows visual refresh and a fresh live NMS dispatch capture remain unverified. PR #17 and #18 also edit the shared extension index; after combining all lane PRs, preserve the three entries listed in `agent-patches/runtime-dispatch/RUNTIME_UI_MANIFEST.json` under `integration_index_resolution`.

## Exact next action

The issue-8 UI extension host is implemented and its regression checks pass. PR #15 remains a draft; issue #8 remains open because the unified probe-capture requirement and Windows visual validation are still outstanding. Do not claim full issue acceptance or merge the candidate as the completed issue.

**Next human action (Windows; no full derelict traversal):** use the Runtime-A Surveyor build identified by `agent-patches/runtime-dispatch/RUNTIME_A_MANIFEST.json` > start Surveyor > click **Start NMS** > load the known derelict only until **Root dispatch +0x10 captured** appears > click **Analyze generation + upload** > return to Main and write `check`. Then review whether the capture hook is compatible with the other lane profiles before integration. Separately, visually verify the DUNGEON-C extension refresh and rollback in the Windows Surveyor UI.

**Verification completed in this continuation:** focused extension/console/workflow tests 17/17 passed; full suite 130/130 passed; `compileall` passed; 40 JSON files parsed; the 116-entry source ZIP passed integrity and SHA-256 checks. Windows/Tk visual behavior was not run in this Linux environment.

Issues #13 and #14 remain closed as not planned. Their benchmark branches were reset to `main`, removing the test-only help-button project; GitHub branch names remain because the connected API cannot delete refs. The delivered package contains no benchmark help button.

## Canonical source status

The last integrated canonical release is v0.3.38. The v0.3.41 candidate package must become authoritative only after its updated root `update-manifest.json` and full-package chunks are merged together.

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


## Runtime-dispatch UI extension (post-7.05)

**Post-7.05 capture analysis reports:** root-seed candidate `9256392A2F5A74AC`, high-confidence `MEDI_FLOATERS` preset inference, 10 modeled rooms (8 main + 2 dead-end), and 16 analyzer-predicted container targets. The root-seed capture remains unverified; 8 main rooms differ from table `Rooms=7`; predicted targets are not verified physical counts. The earlier `CARGO_FLOATERS`, 8-room, 35-target observation is historical.

**Inference:** one post-update sample is consistent with a layout change while the reported seed candidate stayed the same. It does not establish repeatability or changed seed derivation. **Hypothesis:** the cause is unknown.

**Runtime-A lane state:** the generation-layout change does not itself validate the live `owner+0x10` dispatch slot. RUNTIME-A still needs the value at that slot captured at the exact root event, along with the target/module/RVA (when applicable), bounded target bytes/thunk chain, and the descriptor at `owner+0x128`. No full derelict traversal is required. Do not hot-swap probe hooks; use a compatible probe build on a fresh NMS launch if a probe change is needed.

**Optional Surveyor panel:** `agent-ui/extensions/runtime-dispatch/1.0.0/` adds a data-only API 1.0 panel that requests only `research.analyze_generation`, gated by `workflow.idle`, `nms.running`, and `probe.connected`, with evidence namespace `runtime-dispatch`. The panel is `request_only` while this lane still needs live human validation. Existing standalone RUNTIME-A remains the fallback until the shared host candidate and this lane extension are integrated.
