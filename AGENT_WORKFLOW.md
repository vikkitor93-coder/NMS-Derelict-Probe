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
