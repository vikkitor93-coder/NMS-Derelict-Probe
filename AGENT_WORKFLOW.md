# Parallel Agent Workflow

## Goal

Allow multiple AI coding/research agents to work simultaneously without blocking each other or corrupting the stable Surveyor.

## Branch ownership

- `main`: integration-only stable line.
- `agent/runtime-dispatch`: live dispatch/caller/object classification.
- `agent/seed-lineage`: address/system/POI/root seed derivation and RNG research.
- `agent/dungeon-decompile`: historical/current binary mapping and `GcDungeonGenerationParams` consumer discovery.
- `agent/metadata`: abandoned-freighter component options, dungeon table/schema/assets.

Use a separate Git worktree or clone for every lane. Never share a writable working directory between agents.

## Surveyor variants

Lane-specific UI additions use the shared contract in `AGENT_UI_EXTENSION_GUIDE.md`. Submit versioned JSON panels/manifests and stable host action IDs; do not fork the complete Surveyor window for a UI-only change. Keep standalone research workflows available until integration accepts the panel.

Each lane may modify its own Surveyor immediately. It must:

1. keep the stable controller/probe protocol backwards-compatible unless an integration PR deliberately versions it;
2. display an obvious lane/build label, e.g. `Surveyor · RUNTIME-A · <short SHA>`;
3. keep experimental buttons grouped under that lane, not silently replacing stable actions;
4. write experimental evidence to `research-uploads/<timestamp>-<lane>-<action>/`;
5. include lane/build/schema version in every new evidence JSON;
6. preserve read-only NMS behavior unless a separate explicit design review approves a game-state write;
7. ship its own complete variant ZIP and tests in the PR.

## PR contract

Every agent PR must include:

- objective and result;
- files changed;
- exact tests run and results;
- evidence generated or required;
- confirmed facts vs hypotheses;
- whether human/NMS runtime intervention is required;
- migration/rollback notes;
- proposed integration subset (the smallest useful change main should take).

The integration agent may merge only the useful subset; experimental UI/tools can remain lane-specific until proven.

## Runtime test handoff

When human intervention is needed, the lane must reduce it to one explicit recipe: which ZIP/build to run, which known address/derelict to load, which button/action to use, what success indicator to wait for, and whether a traversal is required. Default is no traversal.

## Normal ChatGPT ↔ Work/Codex switching

The repository, not any chat's hidden context, is the continuity layer. A task must be resumable from GitHub alone.

Before yielding control or after any meaningful discovery, the active AI must update the relevant branch so another ChatGPT surface can continue without replaying the prior conversation. At minimum keep these current:

- `AI_HANDOFF.md`: architecture, confirmed facts, latest changes, test state, exact next action;
- `RESEARCH_INDEX.md`: measured/public-confirmed/inferred/hypothesis separation;
- `WORKSPACE_STATE.json`: current integration commit, lane states, human-intervention state, and next objective;
- the lane manifest under `agent-patches/<lane>/` when a lane has produced a build/tool;
- the PR/commit containing any code or research result not yet integrated.

When switching modes, the incoming AI should first read `WORKSPACE_STATE.json`, then `AI_HANDOFF.md` and `RESEARCH_INDEX.md`, then only the active lane manifest/changed files. Do not reread the whole repository unless those files say it is necessary.

Both normal ChatGPT and Work/Codex may act as the integration AI. Only one integration operation should be active at a time; research lanes remain isolated. Codex Local may use a local worktree/terminal for implementation and tests, while normal ChatGPT or Work may review results and integrate through GitHub. No conclusion may rely only on private chat context: commit the evidence or summary needed to reproduce it.

## Agent Console status publishing

Surveyor's read-only Agent Console shows only status that has been published to GitHub; it cannot see private chat messages. Every agent lane should keep `agent-patches/<lane>/STATUS.json` current on its own branch, using `schema/agent-status-v1.schema.json`.

Update that file when starting work, when the state changes, and before asking the user to do anything. For a human request, include the exact Surveyor request, numbered user steps, the visible success condition, evidence to return, and whether a full derelict traversal is required. Clear the request when no longer needed. Never include tokens, local paths, device details, or personal data.

Main remains responsible for syncing the integrated `WORKSPACE_STATE.json`. The console reads that main-branch registry and each lane's branch status/manifest; it labels an old registry as stale and keeps the last successful display if refresh fails. Do not treat an uncommitted chat update as visible or completed work.
