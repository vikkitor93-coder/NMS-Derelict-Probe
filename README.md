# NMS Derelict Probe

Current stable package: **v0.3.30**.

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

Latest uploaded seed-function analysis validated the containing function with PE unwind metadata as `0x0063505C..0x0063553E`. The function reads the embedded descriptor/primary seed but contains no conservative direct write to the descriptor seed fields, has no external direct rel32 references, and yielded no validated MSVC RTTI candidate. The deterministic seed producer therefore remains upstream/indirect and is not yet identified.