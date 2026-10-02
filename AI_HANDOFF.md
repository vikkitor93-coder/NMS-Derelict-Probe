# NMS Derelict Probe — AI handoff

## Current state

- Current source package: **v0.3.45**, release candidate for the Windows Surveyor UI. Probe and NMS launch protocols are unchanged.
- Agent Console has four side-by-side lane cards. The fixed **NEEDED** box shows the lane’s published request and actual extension action; installed/published/reported versions sit immediately below it. Each evidence receipt checkbox stays fixed under its lane buttons.
- **Options +** opens plus/minus visibility toggles for lane status, extension descriptions, and receipt details. Options and auto-refresh interval persist in `%LOCALAPPDATA%\NMSDerelictSurveyor\agent-console-options.json`.
- Auto-refresh defaults to one minute; choices are 20 seconds, 2 minutes, 5 minutes, or Off. **Refresh now** fetches status and extension index immediately. Network reads run on background threads. Cache-busted lane status requests remain read-only.
- Polling reuses unchanged extension widgets, so scroll position and layout do not churn on every refresh. Action readiness updates in place.
- The package carries DUNGEON-C 1.0.2, Metadata-D 1.0.1, Runtime-A 1.0.1, and Seed-B 1.0.2, with prior installed versions retained for rollback.

## Purpose and architecture

Reverse engineer No Man’s Sky abandoned-freighter generation using static and runtime evidence while keeping Surveyor independent from the game. `tools/surveyor_controller.py` is the Windows Tk app and action host; `mod/derelict_baseline_probe.py` collects read-only process evidence; `overlay/derelict_overlay.py` formats live status. `tools/agent_console.py` reads public GitHub lane status. `tools/agent_ui_extensions.py` validates and installs data-only JSON panels.

## Contracts, configuration, and diagnostics

- Start with `Start-Surveyor.cmd` / `Start-Surveyor.ps1`; Surveyor can run independently of NMS.
- Agent status uses schema v1 (`schema/agent-status-v1.schema.json`) from `agent-patches/<lane>/STATUS.json`; optional progress, blockers, extension version, and human-action fields are backward-compatible. Agent lanes publish status commits at meaningful milestones.
- Extension panels use shared UI host API 1.0 and hash-checked `manifest.json`/`panel.json` entries indexed by `agent-ui/extensions/index.json`. Extensions may call only registered host action IDs; no supplied shell or Python runs. Receipts are display-only and never lock actions.
- Session/live status schemas and probe/overlay command protocol remain v1. No data migration is required.
- Controller and workflow logs: `%LOCALAPPDATA%\NMSDerelictSurveyor\gui-actions\`; live status: `%LOCALAPPDATA%\NMSDerelictSurveyor\live-status.json`.
- UI settings contain only display booleans and refresh interval in the local options JSON above.

## Build, run, and test

- Windows with Python 3.12/3.13 and Tkinter; launch `Start-Surveyor.cmd`.
- `python -m compileall -q tools overlay tests`
- `python -m unittest discover -s tests`
- In Agent Console use **Refresh now** for an immediate poll or select **Off** to pause automatic status and extension checks.

## Latest changes and verification

- v0.3.45 separates the actual action from the published NEEDED request, pins both and the versions outside the scroll panel, moves the upload checkbox below lane controls, adds collapsible persisted display options and selectable refresh timing, and avoids replacing unchanged panel widgets on poll.
- `python -m compileall -q tools overlay tests` passed; `python -m unittest discover -s tests` passed (156 tests). The complete ZIP passed integrity checks, 62 JSON files parsed, all 10 extension-file hashes matched, and updater chunks reconstructed to the same SHA-256. Windows visual validation is still required because Tk cannot be rendered in this Linux workspace.
- Runtime-A’s `Root dispatch +0x10 captured` live event remains unverified; don’t treat exact-root-caller output as proof.

## Rollback and next action

- Roll back the app by reinstalling the previous complete v0.3.44 package. No probe, session, extension API, or saved evidence migration is needed. Extension versions retain their individual rollback controls.
- **Next action:** install v0.3.45 on Windows and verify the NEEDED/action box, footer versions, receipt checkbox beneath buttons, all plus/minus visibility toggles, interval persistence, and scrolling while the poll runs.
