# NMS Derelict Probe — AI handoff

## Current state

- Latest exact-root evidence (`20261002T213323Z`, probe 0.3.34): caller return RVA `02C0497A`; its instruction at `02C04977` is `call qword ptr [rdx+0x10]`, with RDX loaded from the vtable of an object referenced by `[rbx+0x48]`. The separate captured owner+0x10 slot is `FFFFFFFF00000000`, an invalid/non-module sentinel, so it is not the resolved call target. Root seed `9256392A2F5A74AC` remains candidate-captured-unverified.
- DUNGEON-C 1.0.3 adds a visible `Resolve root vtable + upload` action using registered host action `research.resolve_root_vtable`. This is the next offline analysis step; no derelict traversal is required.

- Latest exact-root evidence (`20261002T213323Z`, probe 0.3.34): caller return RVA `02C0497A`; its instruction at `02C04977` is `call qword ptr [rdx+0x10]`, with RDX loaded from the vtable of an object referenced by `[rbx+0x48]`. The separate captured owner+0x10 slot is `FFFFFFFF00000000`, an invalid/non-module sentinel, so it is not the resolved call target. Root seed `9256392A2F5A74AC` remains candidate-captured-unverified.
- DUNGEON-C 1.0.3 adds the visible `Resolve root vtable + upload` action using the registered `research.resolve_root_vtable` host handler. This is the next offline analysis step; no derelict traversal is required.

- Current source package: **v0.3.50**. Runtime-A probe is **0.3.34**; it captures owner+0x10 at the exact descriptor-correlated dungeon root event. Surveyor’s app updater stages that probe into the installed MODS folder; fully restart NMS after installing the app update.
- The updater bundles the supplied DerelictFreighterFarming 7.04 source EXML files and stages them as loose overrides under `GAMEDATA/MODS/DerelictFreighterFarming` when the installed probe path is known. Conflicts are backed up; run `python tools/github_integration.py rollback-derelict-farming` from the project folder to restore backups and remove unchanged installed files. This supplied payload has not been verified in NMS 7.05; restart NMS fully after update.
- Agent Console has four side-by-side lane cards. The fixed **NEEDED** box shows the published request, actual extension action, exact required prerequisite keys, and which prerequisites are currently missing. It does not contain generic step guidance. The actual host key is `probe.connected` (fresh probe heartbeat), not `probe.running`; the v1 extension contract is unchanged.
- Installed/published/reported versions remain immediately under NEEDED. Each evidence receipt checkbox stays fixed below its lane buttons.
- Compact top-right +/− controls collapse each major main-window section, each Agent Console card, lane action groups, and global action group. The controls and content begin expanded; lane/global buttons remain pinned in the bottom strip. Agent Console display toggles and refresh interval persist in `%LOCALAPPDATA%\NMSDerelictSurveyor\agent-console-options.json`.
- Auto-refresh defaults to one minute; choices are 20 seconds, 2 minutes, 5 minutes, or Off. **Refresh now** fetches status and extension index immediately. Network reads run on background threads; cache-busted lane status requests remain read-only.
- Polling reuses unchanged extension widgets and action readiness uses the main window’s latest NMS/probe status instead of launching new process checks per lane, keeping scroll position stable and refresh work lighter.
- The overlay display toggles now live in the main Surveyor window; opacity and horizontal/vertical placement sliders apply live. Agent objectives come from the published status snapshot, and the overlay shows root-detected completion plus “waiting for upload / don’t close game” where applicable. `Root dispatch +0x10` now reports the raw slot value and best-effort module identity when a read succeeds; its meaning remains unproven until live evidence is reviewed.
- Main Status and the in-game overlay now show the exact root resource path and observed event count. `Root dispatch +0x10` is shown separately and uses the capture field emitted by Runtime-A probe 0.3.34.
- **Start overlay** and **Stop overlay** sit beside the existing **Game overlay** auto-start toggle. Stop closes the titled overlay window and signals the local stop-request file, including overlays started by the NMS launcher.
- The package carries DUNGEON-C 1.0.3, Metadata-D 1.0.1, Runtime-A 1.0.1, and Seed-B 1.0.2, with prior installed versions retained for rollback. DUNGEON-C exposes the registered root-vtable resolver and preserves analyze-generation.

## Purpose and architecture

Reverse engineer No Man’s Sky abandoned-freighter generation using static and runtime evidence while keeping Surveyor independent from the game. `tools/surveyor_controller.py` is the Windows Tk app and action host; `mod/derelict_baseline_probe.py` collects read-only process evidence; `overlay/derelict_overlay.py` formats live status. `tools/agent_console.py` reads public GitHub lane status. `tools/agent_ui_extensions.py` validates and installs data-only JSON panels.

## Contracts, configuration, and diagnostics

- Start with `Start-Surveyor.cmd` / `Start-Surveyor.ps1`; Surveyor can run independently of NMS.
- Agent status uses schema v1 (`schema/agent-status-v1.schema.json`) from `agent-patches/<lane>/STATUS.json`; optional progress, blockers, extension version, and human-action fields are backward-compatible. Agent lanes publish status commits at meaningful milestones.
- Extension panels use shared UI host API 1.0 and hash-checked `manifest.json`/`panel.json` entries indexed by `agent-ui/extensions/index.json`. Extensions may call only registered host action IDs; no supplied shell or Python runs. Receipts are display-only and never lock actions.
- Session/live status schemas and probe/overlay command protocol remain v1. No data migration is required.
- Controller and workflow logs: `%LOCALAPPDATA%\NMSDerelictSurveyor\gui-actions\`; live status: `%LOCALAPPDATA%\NMSDerelictSurveyor\live-status.json`.
- Agent Console settings remain in its local options JSON. Overlay display settings live in `%LOCALAPPDATA%\NMSDerelictSurveyor\overlay-settings.json`; the current objective snapshot is `overlay-objectives.json`.

## Build, run, and test

- Windows with Python 3.12/3.13 and Tkinter; launch `Start-Surveyor.cmd`.
- `python -m compileall -q tools overlay tests`
- `python -m unittest discover -s tests`
- In Agent Console use **Refresh now** for an immediate poll or select **Off** to pause automatic status and extension checks.

## Latest changes and verification

- DUNGEON-C 1.0.3 adds the root-vtable resolution action after review of exact caller RVA `02C04977`; extension action registry, preconditions, panel hash, rollback, and API 1.0 dependencies are covered by 6 focused tests.
- v0.3.50 bundles DerelictFreighterFarming 7.04 staging with rollback.
- v0.3.48 adds main-window overlay display controls, live opacity/position settings, and published agent objectives. v0.3.47 adds visible root-resource and dispatch-capture status plus manual overlay lifecycle controls. v0.3.46 shows exact prerequisites and missing state in NEEDED, adds per-section +/− controls in both windows, and uses cached game/probe state for action readiness.
- `python -m compileall -q tools overlay tests mod` and the full unittest suite passed for v0.3.50 (169 tests). Windows pyMHF/NMS live validation is still required for the new capture.
- Runtime-A’s new capture implementation is present in probe 0.3.34, but live Windows/NMS validation and semantic interpretation remain pending; exact-root-caller output alone is not proof of a slot read.

## Rollback and next action

- Roll back the app by reinstalling the previous complete v0.3.49 package. Roll back only the bundled farming mod with `python tools/github_integration.py rollback-derelict-farming`. No probe, session, extension API, or saved evidence migration is needed. Extension versions retain their individual rollback controls.
- **Next action:** in Surveyor Agent Console, refresh the DUNGEON-C extension and click **Resolve root vtable + upload**. Review the resulting target and continue decompilation from that resolved function. No derelict traversal is required for this step.
