# NMS Derelict Probe — AI handoff

## Current state

- Current package: **v0.3.57**. It fixes startup by placing the GitHub buttons in a nested frame, keeping geometry managers separate. The automatic upload toggle and v0.3.56 behavior remain.
- **Automatic GitHub evidence uploads** are controlled by a remembered checkbox under GitHub / updates. Enabled by default: a new persisted root capture is uploaded automatically, and after a research or lane action the Surveyor uploads a deduplicated all-lanes evidence batch if its contents changed. The lane-specific action upload remains part of its explicit action workflow. Uncheck the option to stop background root and shared-batch uploads; manual uploads remain available. The all-lanes fingerprint receipt is stored under `%LOCALAPPDATA%\NMSDerelictSurveyor`.
- **Upload all saved evidence** snapshots every existing research output declared by `ACTION_OUTPUTS` into one deduplicated `research-uploads/<timestamp>-all-saved-evidence-<id>/` folder on `main`. Its manifest lists which actions produced each file and marks it visible to all four lanes. The Surveyor writes a receipt to each lane card after success. This is a shared repository upload, not an automatic agent notification or a write to their status branches.
- Overlapping local `*-latest` outputs: `generation-baseline-latest.json` (measure/analyze-generation), `generation-measurements-summary.json` and `generation-measurements.csv` (measure/compare-measurements), `seed-room-correlation.json` (measure/analyze-correlation), and `exact-root-caller-latest.json` (analyze-generation/Runtime-A upload). Local latest files are replaced by a producer rerun; GitHub uploads are timestamped snapshots.
- Runtime-A can now upload its already-persisted root event after closing NMS via **Upload captured root event**; this panel action needs only the saved capture and an idle Surveyor workflow.
- Current source package: **v0.3.57**. Runtime-A probe is **0.3.35**; it captures owner+0x10 at the exact descriptor-correlated dungeon root event and atomically saves the full root event plus runtime metadata/universe address when available in `exact-root-caller-latest.json`. Upload all saved evidence includes this file. If the address is unavailable at root-load time, null/error metadata is saved rather than silently omitted. Capture still requires NMS running while the event occurs; upload/analysis can happen after quitting. Surveyor’s app updater stages the probe into the installed MODS folder; fully restart NMS after installing the app update.
- Surveyor does not redistribute DerelictFreighterFarming files. Download your own archive and use **Install Derelict Farming archive** in the GitHub / updates section. The installer accepts only three expected EXML files, validates their XML, stages them under `GAMEDATA/MODS/DerelictFreighterFarming`, and preserves conflicts. Roll back with `python tools/github_integration.py rollback-derelict-farming`. The supplied archive targets 7.04; NMS 7.05 behavior is not yet validated.
- Agent Console has four side-by-side lane cards. The fixed **NEEDED** box shows the published request, actual extension action, exact required prerequisite keys, and which prerequisites are currently missing. It does not contain generic step guidance. The actual host key is `probe.connected` (fresh probe heartbeat), not `probe.running`; the v1 extension contract is unchanged.
- Installed/published/reported versions remain immediately under NEEDED. Each evidence receipt checkbox stays fixed below its lane buttons.
- Compact top-right +/− controls collapse each major main-window section, each Agent Console card, lane action groups, and global action group. The controls and content begin expanded; lane/global buttons remain pinned in the bottom strip. Agent Console display toggles and refresh interval persist in `%LOCALAPPDATA%\NMSDerelictSurveyor\agent-console-options.json`.
- Auto-refresh defaults to one minute; choices are 20 seconds, 2 minutes, 5 minutes, or Off. **Refresh now** fetches status and extension index immediately. Network reads run on background threads; cache-busted lane status requests remain read-only.
- Polling reuses unchanged extension widgets and action readiness uses the main window’s latest NMS/probe status instead of launching new process checks per lane, keeping scroll position stable and refresh work lighter.
- The overlay display toggles now live in the main Surveyor window; opacity and horizontal/vertical placement sliders apply live. Agent objectives come from the published status snapshot, and the overlay shows root-detected completion plus “waiting for upload / don’t close game” where applicable. `Root dispatch +0x10` now reports the raw slot value and best-effort module identity when a read succeeds; its meaning remains unproven until live evidence is reviewed.
- Main Status and the in-game overlay now show the exact root resource path and observed event count. `Root dispatch +0x10` is shown separately and uses the capture field emitted by Runtime-A probe 0.3.34.
- **Start overlay** and **Stop overlay** sit beside the existing **Game overlay** auto-start toggle. Stop closes the titled overlay window and signals the local stop-request file, including overlays started by the NMS launcher.
- The package carries DUNGEON-C 1.0.2, Metadata-D 1.0.1, Runtime-A 1.0.1, and Seed-B 1.0.2, with prior installed versions retained for rollback. The Runtime-A panel stays data-only; its analyze/upload action is unchanged.

## Autonomous progress

Agents must keep working until human intervention is genuinely required. A reported next step is not a stopping point: first check whether it can be done with repository files, code, available tools, or existing evidence and execute it if possible. Diagnose failures and try reasonable alternatives. After completing the assigned objective, continue with the next highest-value task in the lane. Ask the user to act only for a true human-only dependency, after completing independent work and preparing one exact numbered recipe. Another lane's dependency is not a reason to idle; continue independent work and prepare a concrete handoff.

## Publishing workflow

Agents may publish completed, tested, and documented changes directly to `main`; a separate integration-agent merge or user approval is not required. Keep unfinished experiments on lane branches. Before direct publishing, preserve a backup branch or exact base commit, run relevant checks, publish the full consistent change (including extension index/hash updates when applicable), update lane status and workspace handoff files, and report the main commit plus rollback steps. A PR is optional or a fallback if direct pushing is unavailable.

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

- v0.3.57 fixes the startup `TclError` caused by mixing `pack` and `grid` in the GitHub / updates body.
- v0.3.56 adds a persistent auto-upload toggle. When on, saved Runtime-A captures upload automatically and changed all-lanes evidence is published after research/agent workflows. Batch fingerprints prevent repeated uploads of identical saved files.
- v0.3.54 persists the complete runtime root event, metadata, and universe address in the existing atomically saved/uploaded capture artifact; schema and upload path remain compatible.
- v0.3.48 adds main-window overlay display controls, live opacity/position settings, and published agent objectives. v0.3.47 adds visible root-resource and dispatch-capture status plus manual overlay lifecycle controls. v0.3.46 shows exact prerequisites and missing state in NEEDED, adds per-section +/− controls in both windows, and uses cached game/probe state for action readiness.
- `python -m compileall -q tools overlay tests mod` and the full unittest suite passed for v0.3.51 (173 tests). Windows pyMHF/NMS live validation is still required for the new capture.
- Runtime-A’s new capture implementation is present in probe 0.3.34, but live Windows/NMS validation and semantic interpretation remain pending; exact-root-caller output alone is not proof of a slot read.

## Rollback and next action

- Roll back the app by reinstalling the previous complete v0.3.49 package. Roll back the installed farming mod with `python tools/github_integration.py rollback-derelict-farming`. No probe, session, extension API, or saved evidence migration is needed. Extension versions retain their individual rollback controls.
- **Next action:** update Surveyor, select your downloaded mod ZIP with **Install Derelict Farming archive**, fully restart NMS, then test repeat derelicts in the same system. Confirm `+0x10` remains pending until a real capture is reported.

## DUNGEON-C 2026-10-05 — helper ZIP refreshed

The complete offline helper build has been refreshed against the 0.3.58 source package. Its embedded `WORKSPACE_STATE.json` and `AI_HANDOFF.md` now match the active main handoff. ZIP SHA-256: `6fa8c84fc5d9c8060f86ad13e271e408487d7861f675c0830d5a6c6e6429da19`; size 414,185 bytes; 160 files. Focused tests 8/8, full suite 190/190, compileall, 72 JSON parses, and ZIP integrity all pass. The launcher fixes the BOM path and incomplete-package/directory-launch errors; actual Windows execution remains untested here.

The next human-only dependency is to run this complete ZIP's `Extract-Runtime-Target-Function.cmd` on the user's Windows machine with the matching NMS.exe, confirm helper candidates and at least one bounded target body, then upload all saved evidence. No game launch or derelict traversal is needed. Earlier requests for a duplicate capture/upload are superseded.
