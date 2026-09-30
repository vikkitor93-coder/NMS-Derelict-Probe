# AI handoff — NMS Derelict Probe v0.3.26

Read-only NMS.py/pyMHF derelict research project. Goal: derive deterministic universe-address/system coordinates -> dungeon descriptor seed -> room layout -> target-container count offline.

## Newly proven from uploaded caller-code evidence
- Uploaded action commit: `Add extract-caller research evidence 20260930T001319Z`.
- NMS.exe fingerprint in evidence: SHA-256 `b7913f268dfc62386b6b68f524bfc8ade4a44a9f4fbad39085b7bf51be3680cb`, PE timestamp `6AB0FFC9`.
- Known address: `00001A0004E84EFD`; root descriptor seed: `9256392A2F5A74AC`.
- Root `Engine::AddResource` call RVA: `0x00635110`; return `0x00635115`; target `0x01831A10`.
- The containing function starts at candidate RVA `0x00634BC0`, immediately after compiler `INT3` padding.
- Function prologue copies its second argument into `RSI`.
- Descriptor address is formed as `RSI + 0x128`.
- The function reads 16 bytes beginning at `RSI + 0x138` before the root add. Current public NMS.py defines `cTkResourceDescriptor.mSeed` at descriptor offset `+0x10`, matching `0x128 + 0x10 = 0x138`.
- It checks `RSI + 0x140`, matching the `GcSeed.UseSeedValue` byte at seed offset `+0x8` / descriptor offset `+0x18`.
- Therefore the root seed already exists before this function performs the resource add. This function is not the seed constructor.
- Current public NMS.py did not provide a matching named signature for the `0x00634BC0` function; do not invent a symbol name.

## v0.3.26
Adds `tools/extract_nms_upstream_callers.py`, `Extract-Dungeon-Upstream-Callers.cmd`, GUI **Extract upstream callers + upload**, and GitHub upload action `extract-upstream`. The tool derives the current containing-function start from padding/prologue evidence, scans the installed `.text` section for direct E8/E9 rel32 references to it, and captures bounded code windows around each reference. This is offline/read-only; NMS does not need to run.

## Stable workflow
GitHub CLI auth/update/upload works. GUI research actions run in explicit background steps and persistent diagnostics remain under `%LOCALAPPDATA%\NMSDerelictSurveyor\gui-actions`. The external live overlay remains separate and opaque/non-layered. Never reintroduce alpha/layered rendering by default.

## Safety
Runtime probe remains observational only. Do not add setters, inventory/reward/save mutation, or online hooks. Do not call the dungeon-root descriptor seed the actual room-selection RNG state until causality is proven.

## Verification
88/88 unit tests pass. Python compileall passes. All 35 packaged JSON files parse. Windows/NMS xref scan itself cannot be executed in the build environment because the user's NMS.exe is not present.

## Exact next action
Install/update v0.3.26, restart Surveyor/NMS.py, click **Extract upstream callers + upload**, then tell ChatGPT `check`. No NMS/derelict run is needed.