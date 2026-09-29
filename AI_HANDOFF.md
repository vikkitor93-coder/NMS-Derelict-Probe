# AI handoff — NMS Derelict Probe v0.3.24

v0.3.24 is a diagnostics hardening release for the GUI GitHub/research workflow.

Observed user evidence: their v0.3.23 `latest.log` showed the probe starting but contained no GitHub/upload action failures. The old workflow runner wrote those failures only to separate `gui-actions` files, so the normal log was silent.

v0.3.24 changes:
- mirrors workflow start/success/failure/exception into `latest.log`;
- persistent `gui-actions/workflow-latest.log`;
- per-action + timestamped action logs;
- `workflow-diagnostic-latest.txt` with sanitized command, return code, stdout/stderr and exceptions;
- `github-integration.log` with CLI discovery, auth return codes, upload output discovery and API stages/failures;
- read-only `diagnose` subcommand + **Run GitHub diagnostic** button;
- **Open workflow log** and **Open workflow diagnostic** buttons;
- short GUI status/detail strings to avoid right-edge truncation;
- Windows GitHub web auth runs in a visible console so the device-code prompt cannot be hidden.

No PAT/password/token is logged. The v0.3.23 real-Python-only helper fix is preserved.

Verification: 82/82 tests, Python compileall, all packaged JSON parses, helper smoke tests, ZIP integrity.

Next user action: update/install v0.3.24, click **Run GitHub diagnostic**, then **Open workflow diagnostic** if anything is not OK. Send that diagnostic file or the updated `latest.log`. After setup succeeds, use **Extract dungeon caller code + upload** and tell ChatGPT `check`.

Research state is unchanged: address `00001A0004E84EFD`, root seed `9256392A2F5A74AC`, next caller-code target around RVA `0x00635110`.
