# AI handoff — NMS Derelict Probe v0.3.30

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

Latest uploaded `analyze-seed-function` evidence (`20260930T005951Z`) corrected the containing runtime function using authoritative PE `.pdata` metadata:
- function: `0x0063505C .. 0x0063553E` (1250 bytes)
- root `Engine::AddResource` call: `0x00635110`
- previous padding candidate `0x006345B0` was not the authoritative unwind-function start
- descriptor references: `+0x128` at `0x006350B0` / `0x006350D4`
- primary seed read: `+0x138` at `0x0063523F`
- no conservative direct descriptor/seed writes found in the function
- no direct references to the function found
- `.rdata` references seen were unwind metadata, no validated MSVC RTTI candidate

Interpretation: the root descriptor seed is already populated when this runtime function consumes it. The producer is likely upstream/indirect (virtual/function pointer/object population), not yet identified. Do not claim the `9256392A2F5A74AC` derivation formula is solved.