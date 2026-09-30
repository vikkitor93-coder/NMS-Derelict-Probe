# NMS Derelict Probe — Agent Start Here

Read this file first when joining the project from normal ChatGPT, Work, Codex, or another AI surface.

## Your role

You are one autonomous research/coding agent in a parallel reverse-engineering project. You are **not** the only AI working on the repository. Your job is to advance one non-overlapping research lane toward the shared goal, publish reproducible evidence, and leave enough state in GitHub that another AI can continue without this chat history.

Do not start by rereading the whole repository. Do not duplicate another claimed lane. Do not push experimental work directly to `main`.

## Shared goal

The project is reverse engineering No Man's Sky abandoned/derelict freighter procedural generation. The long-term target is to identify and safely invoke the real NMS derelict/dungeon generator directly, so the project can do roughly:

`seed -> call real NMS generator -> capture preset/layout/rooms/resources -> next seed`

The key unresolved chain is:

`universe/system -> system seed -> POI/derelict seed derivation -> weighted DungeonOptions preset -> GcDungeonGenerationParams consumer -> generated room/layout graph`

All lanes contribute evidence toward connecting that chain.

## Startup order

1. Read `WORKSPACE_STATE.json` for the **current** lane claims and next actions.
2. Read `RESEARCH_INDEX.md` for the short truth table: confirmed facts, public-structure facts, hypotheses, and disproven ideas.
3. Read `AI_HANDOFF.md` for architecture, current technical context, user workflow, and important constraints.
4. Read `AGENT_WORKFLOW.md` for branch/Surveyor/evidence/PR rules.
5. Read only your assigned lane manifest and relevant changed files/evidence.

Historical sections and old next-actions are never more authoritative than `WORKSPACE_STATE.json`.

## Lane rules

Current standard lanes are:

- `agent/runtime-dispatch` — live caller/dispatch/object classification.
- `agent/seed-lineage` — system/POI/root seed derivation and RNG research.
- `agent/dungeon-decompile` — current/historical executable mapping and dungeon-generator discovery.
- `agent/metadata` — abandoned-freighter DungeonOptions, weights, presets, schemas, and static assets.
- `main` — integration only; combines proven results.

If your lane is marked `claimed`, do not take it unless the user explicitly assigned you to that exact lane. For a new independent task, branch from current `main` as `agent/<short-lane-id>`.

## How to work

Continue autonomously until one of these occurs:

- the objective is completed with reproducible evidence;
- the next step genuinely requires the user's PC, NMS runtime, local NMS.exe, or another human-only action;
- progress is blocked by a dependency owned by another lane.

Do not stop just because you found one intermediate result. If a useful next step is safely available inside your lane, continue.

Keep measured facts, public reverse-engineered facts, inference, and hypotheses explicitly separate. Never promote a plausible interpretation to a confirmed fact.

Prefer narrow delta inspection: read unchanged project files only when required. For follow-up `check` requests, inspect only evidence/commits newer than the last reviewed state.

## Surveyor variants

You may extend Surveyor for your lane without waiting for other agents. Your variant must remain visibly identifiable, e.g. `Surveyor · METADATA-D · <short SHA>`, and experimental controls/evidence must stay lane-specific.

Preserve stable launcher/controller/probe behavior and backwards-compatible protocols unless a deliberate integration change says otherwise. Default to read-only NMS instrumentation; do not add game-state writes merely to simplify research.

## Required output from an agent

Publish enough information for integration to reproduce your work:

- objective and result;
- exact branch/commit;
- changed files;
- tests run and exact result;
- evidence files/schema;
- confirmed facts vs hypotheses;
- human intervention required or not;
- smallest proposed integration subset;
- rollback/migration notes when relevant;
- lane manifest under `agent-patches/<lane>/` when code/tooling was produced.

A complete experimental Surveyor build belongs in ChatGPT Library; GitHub stores manifests, reproducible patches, evidence, branches, PRs, and state summaries.

## Human intervention format

The user wants instructions that can be followed immediately without interpretation. When intervention is needed, give one linear recipe, for example:

`Open Surveyor RUNTIME-A > Start NMS > load the known derelict > wait for Root dispatch +0x10 captured > click Analyze generation + upload > tell Main AI "check"`

State explicitly whether a full derelict traversal is required. Default is **no traversal**.

## Important known cautions

- `owner+0x10` is not proven to be a conventional static C++ vtable; the static vtable search failed.
- the runtime `owner` object is not proven to be normal `cTkResource`.
- the public system-seed algorithm is confirmed as an upstream anchor, but the system-seed -> derelict-root-seed formula is unsolved.
- ReNMS general WFC/freighter-base `cGcMap` structures are not proven to be the abandoned-derelict generator.
- Pi demonstrates the desired direct-call pattern for other procedural generators; it does not already provide the derelict interior generator.

## If context seems inconsistent

Do not guess. Prefer, in order: current `WORKSPACE_STATE.json`, current lane manifest/evidence, `RESEARCH_INDEX.md`, then `AI_HANDOFF.md`. Report the inconsistency and update your lane's committed handoff/state before yielding control.
