# NMS Derelict Probe

Current stable package: **v0.3.25**.

## v0.3.25 — fixed upload execution and clipped workflow text

The v0.3.24 diagnostic proved GitHub itself was healthy: GitHub CLI installed, authentication OK, repository API access OK, and push permission true. The failure occurred before GitHub because the GUI built one quoted `cmd.exe /s /c ... && ...` chain and Windows rejected the quoted CMD path.

v0.3.25 removes that shell chain.

GUI research/upload actions now run as two explicit background steps:

1. **Run research command**
2. **Upload generated evidence**

PowerShell-backed workflows launch their `.ps1` file directly. Caller extraction launches its Python tool directly. Step 2 runs only when step 1 returns exit code 0. Normal research/upload actions remain hidden/background and do not open an empty CMD window.

pyMHF STRING rows do not word-wrap, so the old long workflow detail field is replaced by three short rows: **Workflow message 1 / 2 / 3**. Long information is split across rows rather than disappearing off the right edge.

Persistent diagnostics from v0.3.24 remain available:
- `gui-actions/workflow-latest.log`
- per-action and timestamped logs
- `gui-actions/workflow-diagnostic-latest.txt`
- `gui-actions/github-integration.log`
- `gui-actions/github-diagnostic-latest.txt`
- mirrored workflow events in normal `latest.log`

Active update package: `packages/v0.3.25-delta/`
SHA-256: `508c9320461aadf6329a48d4ec3d826d5e566aa9b18eef66d82bb86d8e33bff6`

Verification: **85/85 tests**, Python compileall, packaged JSON parse, ZIP integrity.
