# AI handoff — NMS Derelict Probe v0.3.22

Read-only NMS.py/pyMHF derelict-freighter research project. Current target: deterministic address/seed -> dungeon layout path.

## Research state

Known 35-container address `00001A0004E84EFD` repeatedly produces dungeon-root descriptor seed `9256392A2F5A74AC`. v0.3.19 captured the outer Engine AddResource caller return at RVA `00635115`; the CALL is at `00635110` and targets `01831A10`. The descriptor is already seeded before Engine::AddResource. v0.3.20 added offline caller-code extraction.

## v0.3.22 integration

The pyMHF GUI has background research buttons plus GitHub upload/update controls. Live room/crate/research telemetry remains in the safe opaque/non-layered overlay instead of being duplicated in the action GUI.

GitHub upload setup uses `gh auth login --web`; the project does not persist a PAT/password. Successful research actions atomically commit the expected JSON/CSV outputs plus `run-manifest.json` under `research-uploads/<UTC>-<action>/`. Local command logs remain local.

Launchers persist the extracted source root in `%LOCALAPPDATA%\\NMSDerelictSurveyor\\project-root.txt`. The updater downloads the public manifest, reconstructs its base64 package, verifies SHA-256, validates each managed file, and then updates only the extracted source project. Restart is required.

Active v0.3.22 update package: `packages/v0.3.22-delta/part-000.b64` through `part-002.b64`, SHA-256 `e88c49f5aed55158c92c6c35bc5b39f360b87b679337e8aca0efd30187c466ed`. The interrupted original staging folder has been removed; only the verified `packages/v0.3.22-delta/` package remains active.

Verification of rebuilt v0.3.22: **77/77 unit tests**, Python compileall, packaged JSON parse, and ZIP integrity all pass. Windows CMD/PowerShell execution and first-time GitHub browser authentication still require user-machine smoke testing.

Next action: install/bootstrap v0.3.22, click **Set up GitHub uploads** once, then **Extract dungeon caller code + upload**. When it reports **Complete + uploaded**, the user can tell ChatGPT **check**.
