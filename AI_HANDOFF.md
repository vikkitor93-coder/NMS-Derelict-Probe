# NMS Derelict Probe — AI handoff

## Current state

- Current package: **v0.3.44**. This is a Windows Surveyor update candidate; the host/probe contracts remain unchanged.
- v0.3.44 updates the four-column Agent Console: published action and extension versions stay in fixed footers above lane buttons; lane scrollbars hide when content fits; no-scroll and boundary wheel events are ignored.
- Published request-only actions stay clickable while Surveyor is idle. A click explains missing NMS/probe requirements and can offer to start NMS. The upload receipt is display-only and never locks an action.
- Agent Console refreshes GitHub status every 20 seconds with cache-busting requests. Per-lane status shows progress, blockers, timestamp/freshness, request, and agent-reported extension version.
- The package includes the current extensions from `main`: DUNGEON-C 1.0.2, Metadata-D 1.0.1, Runtime-A 1.0.1, and Seed-B 1.0.2. Older versions remain installed for rollback.
- Linux tests pass; Windows Tk visual check and live action test are the next steps.

## Purpose and architecture

Reverse engineer No Man's Sky abandoned-freighter generation from seed and runtime evidence while keeping Surveyor independent from the game. The Windows `tools/surveyor_controller.py` is the standalone Tk app; `mod/derelict_baseline_probe.py` collects read-only process evidence; `overlay/derelict_overlay.py` renders live status. The Agent Console is a separate Tk `Toplevel`; it reads public GitHub status and extension data only.

## Key files and contracts

- `Start-Surveyor.cmd` / `Start-Surveyor.ps1`: start Surveyor; `Start NMS` launches the classic console-backed pyMHF path.
- `tools/surveyor_controller.py`: main UI, action routing, lane cards, status refresh, extension host.
- `tools/agent_console.py`: public, read-only status fetch/normalization for `main` and all four lane branches.
- `tools/agent_ui_extensions.py`: data-only JSON extension validation, install/activation, action records, rollback.
- `agent-ui/extensions/index.json`: extension versions published on `main`; each version has `manifest.json` and `panel.json` with SHA-256 hashes.
- `AGENT_UI_EXTENSION_GUIDE.md`: stable Surveyor UI API 1.0 and the lane agent prompt.
- `schema/agent-status-v1.schema.json`: lane status contract. Agents commit `agent-patches/<lane>/STATUS.json` to their lane branch, updating it at each meaningful milestone. Fields include progress, blockers, next action, human action, and extension version.
- `WORKSPACE_STATE.json`: integrated lane state. Main owns updates to this file.
- Session/live status schemas remain v1. NMS probe/overlay command protocol is unchanged.

Extensions can request only registered `research.*` host actions. The host rechecks preconditions immediately before running a handler; extensions cannot supply shell commands, paths, or code. Request-only actions require a published lane request. Upload receipts are local action-record history under `%LOCALAPPDATA%\\NMSDerelictSurveyor\\ui-extensions\\<lane>\\runs` and are not action locks. GitHub evidence is uploaded under timestamped `research-uploads/<lane>-<action>-<run-id>/` folders.

## Dependencies, configuration, and diagnostics

- Windows with Python 3.12 or 3.13 and Tkinter. The pyMHF/NMS launcher uses the installed Python environment; status and extension feeds use Python standard-library HTTPS.
- Main app controls include **Open workflow log** and **Open workflow diagnostic**. Controller/action logs live under `%LOCALAPPDATA%\\NMSDerelictSurveyor\\gui-actions\\`; live probe status is `live-status.json` in the same app data root.
- GitHub status files and extension manifests are public repository content; never publish credentials, local paths, device identifiers, or unrelated personal data.

## Build, run, and test

- Extract the complete ZIP and launch `Start-Surveyor.cmd`.
- Run tests: `python -m unittest discover -s tests`.
- Syntax check: `python -m compileall -q tools overlay tests`.
- Use **Refresh agents** to fetch lane status immediately. The automatic poll runs every 20 seconds; each lane heartbeat older than 15 minutes is marked stale. The main registry age is shown separately.
- Use **Check extensions** to inspect published extension versions, then update one lane or all lanes. Each extension can be rolled back from the lane footer.

## Latest verification and limitations

- v0.3.44: `python -m compileall -q tools overlay tests` passed; `python -m unittest discover -s tests` passed (155 tests).
- v0.3.43 baseline: 151 tests passed; compileall passed; package ZIP and updater chunk reconstruction passed.
- Windows Tk layout, scrollbar appearance, NMS-start prompt, and click-through prerequisite handling cannot be visually tested in this Linux workspace.
- Runtime-A's required `Root dispatch +0x10 captured` event is still not emitted by the standard probe feed; do not treat an ordinary exact-root-caller result as proof of that event.

## Rollback and next action

- App rollback: install the previous complete Surveyor ZIP (v0.3.43) or restore its updater manifest/chunks.
- Extension rollback: use each lane's **Roll back to v…** control; old installed versions are retained.
- No migration to saved sessions or probe protocols is required.
- **Next action:** install v0.3.44 on Windows, confirm action/version footer placement, wheel scrolling when content fits and overflows, and press Runtime-A's requested action with NMS closed. Verify it offers to start NMS and does not depend on the upload checkbox. Then check a newly committed lane STATUS.json appears within one refresh interval.
