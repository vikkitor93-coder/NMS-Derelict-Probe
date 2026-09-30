# AI handoff — NMS Derelict Probe v0.3.32

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

Verification target for this revision: standalone controller/source compile; full regression suite; JSON parse; full ZIP and delta integrity; delta apply against v0.3.29.

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

v0.3.31 corrects both static tools. Next action is **Extract upstream callers + upload** again; it will scan the full installed `NMS.exe` for direct references to corrected logical entry `0x00634BC0`. After that, inspect external xrefs or move to indirect/vtable entry tracing if none exist. Do not claim the `9256392A2F5A74AC` derivation formula is solved.


## v0.3.32 exact runtime caller correlation

The corrected v0.3.31 offline scan found 52 direct references to the verified logical entry `0x00634BC0`, proving the function is generic enough that static xrefs alone do not identify the derelict-specific path. v0.3.32 adds a narrow read-only signature hook at that entry. It records seeded descriptor calls only in a bounded in-memory ring, then correlates the exact descriptor pointer when `DUNGEON.SCENE.MBIN` reaches `Engine::AddResource`. The root event stores `logical_entry_matches`, `logical_entry_nearest_caller_return_offset_hex`, and a small code window.

Next live action: use a known derelict/address, wait only until standalone Surveyor shows **Root entry caller**, stop/save, then run **Analyze generation + upload** (or Measure + upload if a fresh measurement wrapper is desired) and tell ChatGPT `check`. Do not require a full room traversal.