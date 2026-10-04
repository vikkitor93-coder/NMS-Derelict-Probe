# AI handoff — NMS Derelict Probe v0.3.41 candidate

## DUNGEON-C current follow-up — 2026-10-04

The newest shared Surveyor upload reviewed for this lane is `research-uploads/20261004T224430Z-all-saved-evidence-f138ff45/`. Its 0.3.37 root capture is for Angoto, universe address `0001BF0004E84EFD`, with candidate root seed `5B4AE67D9C2A8F61`. The root seed remains unverified. The event records owner+0x10 as zero; this does not expose the separate runtime caller target at `[RDX+0x10]`.

The user-confirmed layout/count run is separate from the historical 35-container baseline. For the fresh Angoto traversal, the modeled 11 main rooms and predicted 43 containers (30 Salvage + 13 Footlockers) matched the user's physical survey. The user attributes generation/replayability changes to the game update. This is a user-provided explanation; do not relabel the historical 35-container record or treat predicted counts as measurements in unrelated captures. The separate same-address post-update MEDI_FLOATERS model remains 8 main + 2 dead-end modeled rooms and 16 analyzer-predicted targets; its generation table still lists Rooms=7.

The latest user attachment `exact-root-caller-code-latest(2).json` (SHA-256 `207d8abc5d7d1e13fdb942315f8b7639d21ed30952a776638d6574ee22bfebb2`) contains the complete .pdata-bounded function at `00634930..00634E03` (1,235 bytes; target hook `00634BC0`; NMS.exe SHA-256 `671de22649274b49fa07f5a246bc7252c4e08bb9ab623d2e65722fbab4e497a4`). A linear x86-64 disassembly from the body start decoded 33 direct E8 call sites, independently recomputed all relative targets, and grouped them into seven unnamed targets. The inventory is published at `agent-patches/dungeon-decompile/CALLBACK_DIRECT_CALL_INVENTORY.json`. It validates call instruction boundaries from the bounded body, but the attachment contains no helper .pdata ranges or bodies; no helper identities are claimed.

The next DUNGEON-C step is to receive an export from the v0.3.39 helper-body extractor and validate each candidate against the call inventory and actual .pdata range before tracing data flow. The saved matching NMS.exe could not be transferred into this workspace. The full helper-export package is `NMS-Derelict-Probe-v0.3.50-DUNGEON-C-1.0.3-helper-export.zip` (SHA-256 `95d7ee614fa1d13bb342cb56949cddb5e4cbec0283ba871751d0ea614091f11f`). Run it from the complete extracted package, not the GitHub lane branch archive that lacks imported sibling modules. This is offline work: no NMS launch, fresh capture, or full traversal is needed. Exact steps and success condition are in `agent-patches/dungeon-decompile/STATUS.json`.


## Current handoff state

This is the current continuation point for the main integration worker. The candidate is based on the v0.3.40 Live Output package and is prepared on `integration/issue-8-ui-extensions`; it is not yet the installed `main` release.

- Issue #8 adds `AGENT_UI_EXTENSION_GUIDE.md`, a shared Surveyor UI API 1.0, a data-only JSON extension loader, and one DUNGEON-C sample panel.
- Extensions are downloaded into staging, checked against declared dependencies and SHA-256 hashes, checked for host/API compatibility, and activated without restarting Surveyor. Previous versions remain available for rollback.
- Extension panels can request only the eight stable `research.*` host action IDs. No agent-provided code, shell command, path, or process arguments are run. Preconditions are rechecked at click time.
- Evidence uploads initiated through a lane extension use a timestamped `<lane>-<action>` folder and run manifest. Local action records are also stored under `%LOCALAPPDATA%\NMSDerelictSurveyor\ui-extensions\<lane>\runs`.
- The DUNGEON-C sample panel launches the existing exact-root-caller offline extractor. It does not require NMS to run or a derelict traversal.
- Tests cover compatible install, hash/command rejection, failed-update preservation, live version activation, rollback, and evidence namespacing. Tk visual execution on Windows still needs a human machine.

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

## DUNGEON-C Surveyor extension — 2026-10-01

Lane `dungeon-decompile` has optional extension v1.0.1 on branch `agent/dungeon-decompile`, PR #18 targeting `integration/issue-8-ui-extensions`. It is data-only and uses API 1.0 action `research.analyze_generation`, request-only while this lane needs input, with preconditions `workflow.idle`, `nms.running`, `probe.connected`, empty parameters, and evidence namespace `dungeon-decompile`. Published v1.0.0 remains installed for rollback.

Checks on the Surveyor 0.3.41 candidate with the new lane files overlaid: lane tests 6/6; host extension/namespace tests 10/10; full suite 136/136; compileall passed; 46 JSON files parsed. No live game capture was produced by these tests.

The post-7.05 capture records root seed candidate `9256392A2F5A74AC`, high-confidence inferred preset `MEDI_FLOATERS`, 10 observed rooms, and 16 predicted target containers. The earlier `CARGO_FLOATERS` / 8-room / 35-container result remains historical. Root-seed validity and repeatability are unproven; room count versus table value 7 needs review.

Other open lane PRs also update the shared extension index. Before integration, retain their entries and replace only the DUNGEON-C v1.0.0 row with v1.0.1. PR #18 includes the exact combined index for current companion PRs #16, #17, and #19. Human next action remains the Runtime-A live capture recipe in the DUNGEON-C manifest; no full traversal is required.

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

## DUNGEON-C extension refresh — 2026-10-02

Extension v1.0.2 is prepared as a version-only refresh of v1.0.1. The app reads its shared extension index from `main`, so the lane push is accompanied by a narrow integration PR; Surveyor can offer the refresh after that PR merges. Focused extension suite 6/6 and source suite 151/151 passed. Rollback remains v1.0.1.


## 2026-10-04 extractor launcher correction

The first delivered launcher produced the Windows path-syntax error on the user's machine. The corrected launcher uses `pushd`, validates and de-quotes Surveyor's saved interpreter path, falls back through `py -3` and `python.exe`, and reports a specific folder/runtime error. The updated complete source ZIP is `NMS-Derelict-Probe-v0.3.50-DUNGEON-C-1.0.3-launcher-fix-source.zip` (SHA-256 `bee57a5f135f34a16879f3ba047c5831b4974d77176cd830d2641a9e9b74f568`). Regression suite remains 175/175; compileall passes. Next: user reruns the corrected command and reports the output; if successful, upload all saved evidence for offline decompilation. No NMS launch or traversal is needed.


## Fresh target-body analysis (2026-10-04)

- Direct attachment `exact-root-caller-code-latest(2).json`, SHA-256 `207d8abc5d7d1e13fdb942315f8b7639d21ed30952a776638d6574ee22bfebb2`, probe 0.3.37: seed `5B4AE67D9C2A8F61`, descriptor `00000254AAE08D28`, exact external return `02C0497A` after `FF 52 10` at `02C04977`. Owner+0x10 is zero at logical entry and root add; target identity remains null/low-address. This artifact was attached directly; it is not claimed to be in the shared upload folder.
- NMS.exe SHA-256 `671de22649274b49fa07f5a246bc7252c4e08bb9ab623d2e65722fbab4e497a4`. Extracted body hash `902813092d71c46ae1068923f0aa198e897ab219b3fe29fca1de52bd15b779d5`; .pdata function is `00634930..00634E03` (1,235 bytes). Hook RVA `00634BC0` is interior offset `0x290`, not the function start.
- Disassembly around the hook shows four values conditionally stored at RSI+0x50/+0x54/+0x58/+0x5C with corresponding availability bits in RSI+0x1ED (bits 1/3/2/4; bit 0 always set). A boolean indicates all four nonzero while an input flag is clear. Repeated helper chains consume each present value and update RSI+0x48. This suggests a four-field record/metadata aggregation path; exact helper meanings and class identity remain unknown.
- The owner-relative zero is not the raw qword at the vtable pointer used by `FF 52 10`; the actual indirect target remains unverified. Next: add conservative direct-call helper extraction/analysis from the bounded body and retain candidate labels until instruction boundaries and target ranges are confirmed.
- Launcher run succeeded using Python on PATH after rejecting the BOM-prefixed saved interpreter path. The launcher now suppresses that nonfatal warning and includes it only if all interpreter fallbacks fail.

## Callback return correlation (2026-10-04)

- Caller-return correlation: the bounded function returns the four-field completion boolean in EAX; the external caller compares against 1, then unlinks and frees its 0x58-byte record. This supports a completion-check/record-processing callback interpretation; class/subsystem identity and raw dispatch target remain unknown.


## DUNGEON-C tool 0.3.39

The offline target exporter now scans for raw `E8` bytes and includes helper bodies only when the resulting candidate target maps to an executable section and `.pdata` function. Results are capped (128 call candidates, 12 bodies, 512 KiB total) and marked heuristic because instruction boundaries are not decoded. The fresh 2026-10-04 capture ties the callback's all-four-fields boolean return to caller-side record removal; exact class and indirect slot destination remain unknown. Focused tests: 8/8; full suite: 177/177; compileall passed.

Next: user runs the updated extractor and shares the regenerated supported caller-code evidence. No NMS launch or traversal is needed.
