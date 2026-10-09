# NMS Derelict Probe — Agent Start Here

Read this file first when joining the project from normal ChatGPT, Work, Codex, or another AI surface.

## Your role

You are one autonomous research/coding agent in a parallel reverse-engineering project. You are **not** the only AI working on the repository. Your job is to advance one non-overlapping research lane toward the shared goal, publish reproducible evidence, and leave enough state in GitHub that another AI can continue without this chat history.

Do not start by rereading the whole repository. Do not duplicate another claimed lane. Keep unfinished experiments on your lane branch. When lane research or a build request is complete, tested, and documented, publish that lane output directly to `main` under the policy below; shared Surveyor source/updater releases are published only by the primary integration assistant.

## Work until a real human gate

Treat the assigned objective as work to complete, not a request to describe a plan. At every apparent stopping point, check whether the next useful step can be done with repository files, existing evidence, code, tests, or available tools. If it can, do it. If an attempt fails, inspect the first useful error, fix or work around the cause, and retry. Do not stop after an intermediate finding or leave an agent-owned next step for the user or another agent.

When the assigned objective is complete, continue with the next highest-value task in the same lane that advances the shared goal and does not duplicate another lane. If another lane is blocking one path, record the concrete dependency and continue independent lane work. Stop and ask the user only when the remaining action truly requires their PC/live NMS, inaccessible local evidence, credentials/authorization unavailable to the agent, or information only they can provide. Before asking, finish independent work and provide one precise numbered recipe with the exact control/action and success condition. Do not label ordinary analysis, coding, testing, documentation, publishing, or handoff as a human blocker.

Do not report “next step” as a handoff while that step is still agent-owned and executable. Keep `next_action` in lane status focused on the next action the agent will perform. Set `waiting_on_user` only for a genuine human gate; include the requested action, numbered steps, success condition, evidence to return, and traversal requirement.


## Direct publishing policy

- `main` is the stable shared branch. Completed lane research/status/evidence and complete build-request bundles may be published there directly by their author.
- Before publishing, create a backup branch from current `main` or record the exact base commit and a revert path.
- Keep incomplete or experimental work on the assigned lane branch. Publish lane research with tests, evidence, and lane manifest/status. Submit shared Surveyor source/updater changes as a build request; only the primary integration assistant publishes the integrated app build. Include extension/index hashes when a separately published JSON lane extension changes.
- Do not wait for an integration-agent merge. A PR is a fallback only when direct push is unavailable or rejected.

## Requesting a shared Surveyor build change

Do not publish a competing full Surveyor build. Put complete requested files and a `request.json` under `build-requests/<lane-id>/<request-id>/`, then publish that request bundle to `main`. Follow `build-requests/README.md` for required hashes, base commit, tests, status, and rollback fields. Leave it as `draft` until complete; use `ready` when it is ready for the next main compile. The primary integration assistant is the main compiler: it stages valid ready requests, resolves conflicts, runs integration tests, and publishes a single combined build. A queued request is not shipped until it appears in a compiled release/handoff.

## Shared goal

The project is reverse engineering No Man's Sky abandoned/derelict freighter procedural generation. The long-term target is to identify and safely invoke the real NMS derelict/dungeon generator directly, so the project can do roughly:

`seed -> call real NMS generator -> capture preset/layout/rooms/resources -> next seed`

The key unresolved chain is:

`universe/system -> system seed -> POI/derelict seed derivation -> weighted DungeonOptions preset -> GcDungeonGenerationParams consumer -> generated room/layout graph`

All lanes contribute evidence toward connecting that chain.

## Startup order

1. Read `WORKSPACE_STATE.json` for the **current** lane claims, next actions, publishing policy, and latest combined research pointer.
2. Open `research/LATEST_PARALLEL_ACTION_TEST.json` and read the report it names. For the latest parallel-action run, this combined report is the sole source for action results. Do not use its queue or separate per-action latest files as competing results. Preserve the report's provenance and interpretation notes.
3. If `research/LATEST_ROOT_SEED_BATCH.json` exists, verify its report SHA-256 and use the referenced batch report plus its listed source capture journals for multi-system seed correlation. The report keeps different process journals separate; do not substitute `root-event-latest.json`, which represents only the newest event.
4. Read `RESEARCH_INDEX.md` for the truth table and `AI_HANDOFF.md` for architecture/current technical context.
5. Read `AGENT_WORKFLOW.md` for publishing and Surveyor/evidence rules.
6. Read `build-requests/README.md` before asking for a shared Surveyor build change.
7. Read only your assigned lane manifest and files/evidence needed for your objective. Do not replace a combined-report finding with an unreviewed historical file.

For any Surveyor panel/action request, also follow `AGENT_UI_EXTENSION_GUIDE.md`. All four lanes share its single versioned, data-only extension contract; do not add lane-specific Python UI modules or shell-command strings.

The latest combined report is authoritative only for the parallel run it records; its source sessions and limitations remain explicit. Historical evidence stays historical and must not be relabeled as current. For lane ownership and next actions, `WORKSPACE_STATE.json` remains authoritative.

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

Do not stop just because you found one intermediate result. If a useful next step is safely available inside your lane, continue. When the assigned objective is complete, continue with the next useful non-duplicative lane task. A dependency on another lane blocks only that dependent path; keep working on independent tasks.

Keep the Surveyor Agent Console informed by committing `agent-patches/<lane>/STATUS.json` to your lane branch at start, after meaningful progress/prerequisite/evidence/extension changes, before any user request, and when the request completes. Keep the main-branch copy of completed status/manifest updates synchronized so every agent can find the same project state in one place. Update its timestamp and include progress, blockers, next action, and the published extension version when relevant. The console polls every 20 seconds; uncommitted chat text is not visible to it.

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
