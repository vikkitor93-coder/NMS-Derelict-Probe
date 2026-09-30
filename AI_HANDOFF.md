# AI handoff — NMS Derelict Probe v0.3.27

Read-only NMS.py/pyMHF derelict research project. Goal: derive deterministic universe-address/system coordinates -> dungeon descriptor seed -> room layout -> target-container count offline.

## Research state
- Known address: `00001A0004E84EFD`; root descriptor seed: `9256392A2F5A74AC`.
- Root `Engine::AddResource` call RVA: `0x00635110`; return `0x00635115`; target `0x01831A10`.
- The containing function starts at candidate RVA `0x00634BC0`, immediately after compiler INT3 padding.
- Function prologue copies its second argument into RSI. Descriptor address is `RSI + 0x128`.
- Primary seed is read at `RSI + 0x138`; use-seed flag checked at `RSI + 0x140`, before the root AddResource call. Therefore the root seed is created upstream of this function.
- Current public NMS.py did not provide a reliable named signature for `0x00634BC0`; do not invent a symbol name.
- v0.3.26 added offline `Extract upstream callers + upload` to scan installed NMS.exe for direct E8/E9 references to `0x00634BC0`.

## v0.3.27 restart convenience
Added GUI **Restart Surveyor**. The callback saves any active research session, starts a detached `Restart-Surveyor.ps1`, and passes the current NMS PID plus the recorded launch mode. The helper uses `Process.CloseMainWindow()` for a clean close, waits up to 30 seconds, and relaunches only after the old PID is gone. It deliberately refuses to force-kill NMS.

Both `Install-and-Start.ps1` and `Install-and-Start-NoOverlay.ps1` now write `%LOCALAPPDATA%\NMSDerelictSurveyor\launch-mode.txt` as `overlay` or `no-overlay`. Restart selects `Start-Derelict-Probe.cmd` or `Start-Derelict-Probe-NoOverlay.cmd` accordingly. Diagnostics: `%LOCALAPPDATA%\NMSDerelictSurveyor\gui-actions\restart-latest.log`.

## Stable workflow
GitHub CLI auth/update/upload works. GUI research actions run in explicit background steps and persistent diagnostics remain under `%LOCALAPPDATA%\NMSDerelictSurveyor\gui-actions`. The external live overlay remains separate and opaque/non-layered. Never reintroduce alpha/layered rendering by default.

## Safety
Runtime probe remains observational only. Do not add setters, inventory/reward/save mutation, or online hooks. Do not call the dungeon-root descriptor seed the actual room-selection RNG state until causality is proven. Restart is clean-close-only; do not replace it with forced process termination without explicit user request.

## Verification
91/91 unit tests pass. Python compileall passes. All packaged JSON files parse. PowerShell/NMS restart behavior cannot be executed in the Linux build environment and needs one Windows smoke test.

## Exact next action
Update/install v0.3.27 and use **Restart Surveyor** whenever a restart is needed. For the research path, click **Extract upstream callers + upload**, then tell ChatGPT `check`. No derelict run is needed.