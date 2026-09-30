# NMS Derelict Probe

Current stable package: **v0.3.31**.

## v0.3.31 — corrected logical-function analysis

The previous static analyzer treated the PE `.pdata` entry containing the root `Engine::AddResource` call (`0x0063505C..0x0063553E`) as if it were the entire logical C++ function. That was too strong: the fragment starts in the middle of live state-machine code and is entered from earlier code.

The caller window proves the real logical entry candidate is **`0x00634BC0`**: it is immediately preceded by four `INT3` bytes and begins with a normal MSVC x64 prologue. The older upstream scanner required at least six padding bytes, so it skipped this boundary and incorrectly selected the previous helper at `0x006345B0`.

v0.3.31 fixes both offline analyzers. **Extract upstream callers + upload** now targets `0x00634BC0`, and **Analyze seed function + upload** reports the root `.pdata` entry as a runtime fragment rather than claiming it is the logical function start. It also scans the known logical-entry-to-root prefix for descriptor/seed reads and direct writes.

No new NMS/derelict run is required.

## v0.3.30 — standalone Surveyor controller

Surveyor is now a separate Windows process instead of living inside the NMS/pyMHF GUI.

Normal workflow:

1. Double-click **Start-Surveyor.cmd** (or the backwards-compatible **Start-Derelict-Probe.cmd**).
2. The Surveyor window opens and stays open independently of No Man's Sky.
3. Click **Start NMS** when the game is needed.
4. Closing NMS leaves Surveyor running.
5. Research, GitHub upload, diagnostics, update checks and offline analysis remain usable while NMS is closed.

The standalone window includes:
- **Start NMS** with duplicate-instance protection;
- **Restart Surveyor**, which restarts only the controller and never closes NMS;
- live NMS/probe/recording status from `live-status.json`;
- loaded controller, downloaded/source and available update versions;
- GitHub setup/diagnostics/check/install controls;
- research + upload actions;
- live capture commands routed to the injected read-only probe through a small local command file;
- optional safe game overlay, **off by default**.

The injected `DerelictBaselineProbe` is now a headless backend (`@no_gui`). It continues the same read-only runtime capture and writes local evidence/status, while the standalone controller provides the user interface.

`Start-NMS.ps1` installs/syncs the probe and launches NMS through NMS.py without tying the Surveyor controller lifetime to the game process. It only installs the NMS.py runtime when the runtime is missing, avoiding a package update on every quick game launch.

### Updating

**Check for update** shows the exact source and available versions. **Install update** updates the extracted project and stages the probe backend when its MODS location is known. Then use **Restart Surveyor** to load a new controller version. NMS can remain open; backend probe code changes take effect the next time NMS is launched.

## Current research checkpoint

The latest upload exposed an analyzer interpretation bug rather than the seed formula. The `.pdata` range `0x0063505C..0x0063553E` is the **runtime fragment containing the root call**, not the logical function entry. The original caller bytes contain a stronger entry at `0x00634BC0`, preceded by four `CC` bytes and a full x64 prologue. Within the known entry-to-root prefix, the descriptor seed is read at `0x00634DBE` and the use-seed flag is checked at `0x00634E26`, both before the root `Engine::AddResource` call at `0x00635110`. No direct seed write has yet been demonstrated.

Next step: rerun **Extract upstream callers + upload** on v0.3.31 so the entire `NMS.exe` is scanned for references to the corrected entry `0x00634BC0`.