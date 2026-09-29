# NMS Derelict Probe

Read-only No Man's Sky derelict-freighter generation research/modding toolkit.

Current stable package: **v0.3.22**.

The pyMHF companion GUI can:
- check/install project updates from this repository (restart required; no live hot-patching);
- run the existing safe research CMD workflows, including **Measure derelict generation + upload**;
- automatically upload generated research JSON/CSV evidence under `research-uploads/<UTC-run>-<action>/` after one-time GitHub CLI authentication.

The in-game overlay remains the place for live room/crate/research telemetry; the pyMHF GUI does not duplicate that overlay data.

For a research handoff, run a GUI action ending in **+ upload**, wait for **Complete + uploaded**, then tell ChatGPT **check**.
