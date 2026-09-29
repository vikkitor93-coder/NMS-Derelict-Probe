# NMS Derelict Probe

Current stable package: **v0.3.24**.

## v0.3.24 — diagnosable GitHub/upload workflow

This release fixes the main diagnostics gap in the v0.3.23 GUI workflow.

Every GUI research/GitHub action now leaves durable evidence in:

- `%LOCALAPPDATA%\NMSDerelictSurveyor\latest.log` — start/success/failure/exception events;
- `%LOCALAPPDATA%\NMSDerelictSurveyor\gui-actions\workflow-latest.log` — combined action history;
- `gui-actions\latest-<action>.log` — latest output for one action;
- timestamped action logs;
- `gui-actions\workflow-diagnostic-latest.txt` — command, return code, stdout/stderr;
- `gui-actions\github-integration.log` — GitHub CLI/auth/API/upload stages;
- `gui-actions\github-diagnostic-latest.txt` — read-only GitHub diagnostic.

New GUI buttons:

- **Open workflow log**
- **Open workflow diagnostic**
- **Run GitHub diagnostic**

The GUI status text is intentionally short so it remains readable in pyMHF's non-wrapping fields.

When GitHub CLI authentication is required on Windows, `gh auth login --web` opens in a visible console so the one-time device-code prompt is not hidden.

The v0.3.23 safety fix remains: helper actions resolve only a real Python interpreter and never use injected `NMS.exe`.

Active update package: `packages/v0.3.24-delta/`
SHA-256: `923ed244cdec57ccc8d28e7940e1c993999ebe9a7ee8dc39db9f6b1be9115c30`

Verification: **82/82 tests**, compileall, JSON parse, helper diagnostic/failure smoke tests, ZIP integrity.
