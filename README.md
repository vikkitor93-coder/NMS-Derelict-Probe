# NMS Derelict Probe

> **v0.3.36 launch fix:** Standalone Surveyor remains independent, but **Start NMS** now hands off to the same console-backed `pymhf.exe run nmspy` launch style used by the older working UI. The hidden `import pymhf` preflight and Python downgrade/reinstall loop were removed.


Current Surveyor package: **v0.3.41**.

## v0.3.41 — shared lane UI extensions

The Agent Console can load versioned, hash-checked JSON panels for each research lane without restarting Surveyor. Panel buttons request stable Surveyor action IDs; extensions cannot run supplied shell commands or code. Updates activate live, previous versions remain available for rollback, and lane-triggered uploads use timestamped lane/action folders. See `AGENT_UI_EXTENSION_GUIDE.md` for the contract and reusable agent prompt.

## v0.3.40 — live research output

Surveyor shows the current research command, step, progress, latest output line, and exit status as it runs. The main window and output history can be scrolled, and the full workflow log remains available for copying or diagnosis. Fast output is batched for the display so the window stays responsive.

## v0.3.39 — Agent Console

Standalone Surveyor opens a compact **Agent Console** alongside its main window. It shows the latest published state of Runtime-A, Seed-B, DUNGEON-C, and Metadata-D, highlights lanes needing Surveyor input, and gives the exact steps, success condition, evidence to return, and full-traversal requirement.

The console reads `WORKSPACE_STATE.json` from the repository's `main` branch and reads `agent-patches/<lane>/STATUS.json` plus each lane manifest from the corresponding agent branch. It refreshes every 60 seconds and can also refresh on demand. If the main registry is older than 30 minutes, it displays a stale-state warning; if a refresh fails, it keeps the last successful view. The console does not read private chat messages. Agent requests appear only after they are published to GitHub.

Select a lane and click **Copy Surveyor steps** to copy its literal user recipe. After completing the recipe and its upload step, return to the Main chat and write `check`. **Copy status summary** copies the visible lane states and pending human action for chat handoff.

To publish a lane's current request, commit `agent-patches/<lane>/STATUS.json` on that lane's branch using `schema/agent-status-v1.schema.json`. Include exact steps and say whether a full derelict traversal is required.

## v0.3.34 — all 52 callers at once

v0.3.34 makes the runtime caller test explicit and self-contained. The single verified hook at `0x00634BC0` observes every caller that reaches the shared function, so all 52 static direct references are covered in one run rather than being tested in batches.

When the derelict root `DUNGEON.SCENE.MBIN` reaches `Engine::AddResource`, Surveyor matches the exact descriptor pointer, excludes the verified self-recursive edge (`return RVA 0x00634C63`), and records the nearest external caller as the exact root-path candidate. The result is written immediately to `%LOCALAPPDATA%\NMSDerelictSurveyor\asset-work-v1\exact-root-caller-latest.json` so the evidence survives even if NMS is closed right after capture.

The standalone UI now shows **Caller scan** and **Exact root caller** separately. `Analyze generation + upload` uploads both the normal baseline and the dedicated exact-caller evidence when present.

## v0.3.32 — exact runtime caller correlation

The corrected v0.3.31 full-executable scan found **52** direct `CALL/JMP rel32` references to the generic logical entry at `0x00634BC0`. That is too many static candidates to identify the derelict-specific path safely. v0.3.32 therefore adds one narrow read-only runtime correlation hook using the verified entry signature.

The hook remembers only seeded descriptor invocations in memory. When `MODELS/SPACE/POI/DUNGEON.SCENE.MBIN` later reaches `Engine::AddResource`, Surveyor matches the exact descriptor pointer and records the nearest `0x00634BC0` caller plus a tiny code window. It does not write game memory and does not hook global RNG.

The standalone Surveyor status now includes **Root entry caller**. Once that value appears, a short capture is enough; a full derelict traversal is unnecessary.

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

The corrected v0.3.31 scan found 52 direct references. v0.3.34 now observes all of them at once at runtime and selects the exact external caller by descriptor identity; no batch-by-batch caller testing is required.
## v0.3.34 Start NMS runtime repair

`Start-NMS.ps1` now self-repairs the NMSpy/pyMHF runtime instead of treating a hidden import failure as a generic missing-package error. It tests the actual interpreter, force-repairs the pinned runtime only when needed, falls back to Python 3.12 when necessary, writes the local pyMHF NMS/MODS config, and launches with `python -m pymhf run nmspy`. A full import traceback is retained in `%LOCALAPPDATA%\NMSDerelictSurveyor\runtime-repair-latest.log` if startup still fails. `Start-NMS-With-Overlay.cmd` is the manual overlay launcher; `Start-NMS.cmd` records without the overlay.


### Exact root caller follow-up (v0.3.38)
After `Analyze generation + upload` has captured an exact root caller, use **Extract exact root caller + upload** in the standalone Surveyor. This is offline/read-only: it opens the installed `NMS.exe`, maps the exact caller return RVA, captures surrounding bytes, and uploads `exact-root-caller-code-latest.json`. No additional derelict run is required for this step.

### Exact root vtable resolution (v0.3.38)
After **Extract exact root caller + upload** reports the virtual call shape (`FF 52 10`), use **Resolve root vtable + upload**. It scans the installed `NMS.exe` offline for vtable entries whose `+0x10` slot points to the verified `0x00634BC0` function, records neighbouring virtual methods, tries to decode MSVC RTTI/class metadata, and records RIP-relative code references to candidate vtables. It does not launch NMS or write to the game.


**Extractor launcher troubleshooting:** the current launcher prefers Surveyor's saved Python interpreter, then tries `py -3` and `python.exe` on `PATH`. If neither the project folder nor a Python runtime is usable, it prints the exact failing path/runtime. Extract the package to a normal local folder and retry.


The logical-entry RVA may point inside the containing `.pdata` function rather than at its start. The output reports both addresses; analyze the full bounded body while keeping the observed hook RVA distinct from the function start.
