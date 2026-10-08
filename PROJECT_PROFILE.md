# Project Profile — NMS Derelict Probe

## Purpose
Reverse engineer No Man's Sky abandoned/derelict freighter procedural generation. The long-term goal is to identify and safely invoke the real game generator repeatedly from seeds, capturing the selected preset, layout, rooms, and resources.

The shared research chain is:

`universe/system -> system seed -> POI/derelict seed -> weighted DungeonOptions choice -> GcDungeonGenerationParams consumer -> generated layout`

## Scope
This repository coordinates the Surveyor research tool, read-only runtime captures, offline executable analysis, metadata/schema research, reproducible evidence, and integration across research lanes. It is not a general-purpose NMS mod or a substitute for the installed game.

Use `AGENT_START_HERE.md` and `AGENT_WORKFLOW.md` for agent roles, startup order, lane ownership, autonomous-work expectations, publishing, and evidence rules. Agents continue executable work until a genuine human-only gate; they do not stop at describing an agent-owned next step. Use `WORKSPACE_STATE.json` as the authority for current lane claims and next actions. Use `AI_HANDOFF.md` for the changing technical checkpoint and `RESEARCH_INDEX.md` for the current evidence truth table.

## Stable architecture and data boundaries
- The standalone Surveyor controller is `tools/surveyor_controller.py`; launcher and NMS-start scripts are in the repository root.
- The injected `DerelictBaselineProbe` is a read-only backend. Controller/probe commands and acknowledgements use JSON files under `%LOCALAPPDATA%\NMSDerelictSurveyor`.
- Local analysis state and captures are kept under `%LOCALAPPDATA%\NMSDerelictSurveyor\asset-work-v1`. Lane evidence published to GitHub belongs in timestamped `research-uploads/` folders and must identify its lane, build, and schema.
- NMS executables and other user-installed game binaries are local inputs; do not commit them. GitHub holds code, state summaries, manifests, reproducible evidence, and integration history. Complete experimental builds are kept separately as described in the current handoff.

Consult `AI_HANDOFF.md` for the current exact launch path, protocol details, baseline values, canonical artifact, and latest technical state; these can change.

## Research and safety constraints
- Label conclusions as measured runtime fact, confirmed public/static fact, inference, or hypothesis. Preserve contradictions and unknowns; never present an inference as proven.
- Default to read-only game instrumentation. Do not write game state or change memory to simplify capture.
- Preserve the stable launcher, controller/probe behavior, evidence formats, and protocols. Keep experimental features and evidence lane-specific until integration.
- Do not assume the runtime dispatch object is a conventional C++ vtable or a normal `cTkResource` without direct evidence. Do not treat general WFC/freighter-base research or other procedural generators as proof of the abandoned-derelict interior generator.
- Work from narrow deltas. Avoid re-reading unchanged files and avoid repeating uploads, pushes, or other external actions until their outcome has been checked.

## User handoff preference
When a step requires the user's PC or live NMS, give one linear, literal recipe naming the exact build, action/button, expected success indicator, and upload step. State explicitly whether a full derelict traversal is needed; default to no traversal. When the user says `check`, inspect only new evidence since the last reviewed state.

## Verification
Run focused offline tests and compile checks for code changes, then relevant regressions. Live runtime claims require the stated in-game capture; do not imply NMS was tested if only offline checks ran. Report exact commands/results and any human action still required.
