# AI handoff — NMS Derelict Probe v0.3.22

Read-only NMS.py/pyMHF derelict-freighter research project. Current target: deterministic address/seed -> dungeon layout path.

v0.3.22 adds background companion-GUI buttons for the existing research CMD workflows and automatic GitHub research evidence upload. GitHub upload setup uses GitHub CLI's credential store (optionally installed via winget); the project does not store a PAT/password. Successful actions atomically commit expected JSON/CSV outputs plus a hash/size run-manifest under research-uploads/<UTC-run>-<action>/. Local command logs remain local.

Updater contract remains schema 1 and intentionally retains the v0.3.21-compatible SHA-256-verified base64-chunk transport so installed v0.3.21 can update to v0.3.22. Updates modify the extracted source project only and require restart.

Verification: 77/77 unit tests pass, Python compileall passes, 36 packaged JSON files parse. Windows PowerShell/CMD execution and gh browser authentication still require first-machine smoke testing.

Next action: install/update v0.3.22, click Set up GitHub uploads once, then click Extract dungeon caller code + upload. When it reports Complete + uploaded, tell ChatGPT "check".
