# NMS Derelict Probe

Read-only No Man's Sky derelict-freighter generation research/modding toolkit.

Current stable package: **v0.3.22**.

## GitHub workflow

v0.3.22 is the one-time bootstrap for the integrated workflow. After installing it, the pyMHF companion GUI can:

- **Set up GitHub uploads** once using GitHub CLI's credential store;
- run **Measure derelict generation + upload**;
- run **Extract dungeon caller code + upload**;
- run the existing Prepare / Analyze research workflows in the background;
- **Check for Surveyor update** and **Install Surveyor update** from this repository.

Successful research actions commit only the expected generated JSON/CSV evidence plus a SHA-256/size run manifest under `research-uploads/<UTC>-<action>/`. Local command logs stay local.

Live room/crate/research telemetry remains in the safe external overlay; it is intentionally not duplicated in the action GUI.

## Update package

The active update manifest is `update-manifest.json`.

For v0.3.22 it references the verified three-part delta package under `packages/v0.3.22-delta/`:

- package SHA-256: `e88c49f5aed55158c92c6c35bc5b39f360b87b679337e8aca0efd30187c466ed`
- delta base: v0.3.20
- transport: SHA-256-verified base64 chunks
- update behavior: source-project files only; restart required; no live hot-patching

The interrupted original staging directory has been removed; the active v0.3.22 update package is only `packages/v0.3.22-delta/`.

## Current research target

Recover the deterministic transform from universe/system address to the dungeon-root resource descriptor seed and then to the generated room/container layout. The known 35-container system `00001A0004E84EFD` repeatedly produces root seed `9256392A2F5A74AC`; the current next evidence target is the caller code around RVA `0x00635110`.
