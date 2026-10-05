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

## DUNGEON-C offline helper-export follow-up — 2026-10-05

The newest shared saved-evidence snapshot is `research-uploads/20261005T002907Z-all-saved-evidence-96c22a7b/`. Its run manifest uploaded on 2026-10-05 00:29 UTC. The exact root capture inside it is still the 2026-10-04 23:17 Angoto event: candidate root seed `5B4AE67D9C2A8F61` (unverified), owner+0x10 = zero, and target identity null-or-low-address. The code export has the same SHA-256 as the preceding upload (`207d8abc5d7d1e13fdb942315f8b7639d21ed30952a776638d6574ee22bfebb2`) and still contains no direct-call helper candidates or helper bodies. Treat this as the newest uploaded snapshot of saved evidence, not a new runtime sample or successful helper export.

The separate current-run layout remains user-confirmed at 11 rooms and 43 containers (30 Salvage + 13 Footlockers). The historical result remains 35 containers (31 Salvage + 4 Footlockers), 7 main rooms plus Room 0 dead-end, two vertical transitions, and one Shuttle Bay. The older same-address MEDI_FLOATERS model remains 8 main + 2 dead-end modeled rooms and 16 analyzer-predicted targets; its generation table says Rooms=7. Predicted counts are not physical measurements. The user attributes changed generation/replayability to the game update; this remains user-provided explanation. Root seeds `9256392A2F5A74AC` and `5B4AE67D9C2A8F61` remain candidates, not proven derivations.

The bounded function at `00634930..00634E03` has 33 direct E8 call sites grouped into seven unnamed targets; all relative targets were independently recalculated. Helper bodies are still unavailable. The matching local NMS.exe could not be transferred into this workspace. The standalone complete DUNGEON-C helper ZIP is based on the 0.3.58 source package plus extractor 0.3.39. Its launcher avoids the prior BOM-prone saved interpreter path, does not change directories, checks sibling imports, and selects Python 3.13/3.12/PATH Python. Focused tests passed 8/8; full suite 190/190; compileall passed; 72 JSON files parsed; ZIP integrity passed. Windows launcher execution and the local executable scan were not possible here. The stock updater archive omits this research tool; use the standalone ZIP listed in the DUNGEON-C manifest.

**Human step (offline; no NMS launch or full traversal):** download and extract the complete helper ZIP to a normal local folder > run `Extract-Runtime-Target-Function.cmd` from its root > confirm the output `exact-root-caller-code-latest.json` contains `runtime_target_function.direct_call_candidates` and at least one .pdata-bounded `target_function_body` > in Surveyor click **GitHub / updates > Upload all saved evidence** > tell me “check”. Then I will reconcile candidates against the 33-site inventory and verified helper .pdata ranges before tracing or naming any consumer.
