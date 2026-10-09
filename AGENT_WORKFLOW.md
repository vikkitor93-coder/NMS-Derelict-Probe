# Parallel Agent Workflow

## Goal

Allow multiple AI coding/research agents to work simultaneously without blocking each other or corrupting the stable Surveyor.

## Autonomous execution and human gates

Agents are expected to finish executable work, not merely describe what should happen next. At each apparent stopping point, inspect whether the next useful step is possible with available repository files, evidence, code, tests, or tools; if so, perform it. Diagnose failures from the first useful error and try a reasonable fix or fallback. Do not hand off agent-owned analysis, implementation, testing, documentation, or publishing as if it were user work.

When the assigned objective is complete, continue with the next highest-value, non-duplicative task in the same lane that advances the shared goal. A dependency on another lane blocks only that path; record the dependency and continue independent work. Ask the user only for a genuine human-only step such as a live NMS/PC action, inaccessible local evidence, unavailable credentials/authorization, or information only the user can supply. Before asking, finish all independent work and send one precise numbered recipe with the exact Surveyor control/action, success condition, evidence to return, and whether a full traversal is required. Use `waiting_on_user` status only for that real gate.

Lane status `next_action` must say what the agent will do next, not what the user or another agent should do, unless a genuine human gate is active. Keep status, manifest, handoff, and workspace registry aligned with the latest published evidence. Publish meaningful completed changes to GitHub `main` under the direct-publish policy below; do not wait for a conversational reminder. Publish milestone status to the lane branch for Agent Console and keep the main copy synchronized.

## Branch ownership

- `main`: stable shared line. Lane authors publish completed lane research/status/evidence and complete build-request bundles directly to `main` after creating a backup reference or recording the exact base commit and rollback path. Shared Surveyor source and updater releases are published by the main compiler after request integration.
- `agent/runtime-dispatch`: live dispatch/caller/object classification.
- `agent/seed-lineage`: address/system/POI/root seed derivation and RNG research.
- `agent/dungeon-decompile`: historical/current binary mapping and `GcDungeonGenerationParams` consumer discovery.
- `agent/metadata`: abandoned-freighter component options, dungeon table/schema/assets.

Use a separate Git worktree or clone for every lane. Never share a writable working directory between agents. Keep incomplete experiments on the lane branch; after validation, publish lane research or a complete build request directly to `main` without waiting for an integration-agent merge. Do not directly publish shared Surveyor source/updater builds; submit those changes through the build-request queue for the main compiler. A PR is a fallback only if direct push is unavailable or rejected.

## Surveyor variants

Lane-specific UI additions use the shared contract in `AGENT_UI_EXTENSION_GUIDE.md`. Submit versioned JSON panels/manifests and stable host action IDs; do not fork the complete Surveyor window for a UI-only change. Keep standalone research workflows available while experimental work is unfinished.

Each lane may modify a local/lane Surveyor variant for experimentation. Shared Surveyor changes must be submitted through the build-request queue. A lane-specific UI extension that uses the shared JSON-only host contract may still be published by its owner. Every variant or extension must:

1. keep the stable controller/probe protocol backwards-compatible unless a deliberately versioned release changes it;
2. display an obvious lane/build label, e.g. `Surveyor · RUNTIME-A · <short SHA>`;
3. keep experimental buttons grouped under that lane, not silently replacing stable actions;
4. write experimental evidence to `research-uploads/<timestamp>-<lane>-<action>/`;
5. include lane/build/schema version in every new evidence JSON;
6. preserve read-only NMS behavior unless a separate explicit design review approves a game-state write;
7. include tests and evidence; for a shared-build change, put the exact requested files into the build-request bundle. The main compiler creates the complete integrated source ZIP.

## Main-build requests

Agents request changes to the shared Surveyor build through `build-requests/<lane-id>/<request-id>/`; they do not publish competing full Surveyor builds or directly replace shared app/updater files. Put the requested files under the request folder and list their source paths, final project destinations, SHA-256 values, and base-file SHA-256 values in `request.json`. Include the main base commit, a concise reason, completed tests, and rollback instructions. Use `status: "draft"` while any part is incomplete; set `status: "ready"` only when the request can be reviewed and staged.

Publish the complete request bundle to `main` so it is visible to the next main compile. Keep lane research and unfinished implementation on the lane branch. The main compiler (the primary integration assistant) reviews the request queue and stages every valid `ready` request into a disposable copy of current main with `python tools/compile_build_requests.py`. It then resolves any reported conflicts, runs integration tests, updates version/changelog/handoff/manifests, creates the complete source ZIP, and publishes the integrated build. Agents must not mark requests integrated; the main compiler records what actually shipped. Draft, integrated, and cancelled requests are skipped. Request files cannot execute commands or delete files, and the compiler rejects path escapes, changed base files, invalid hashes, and conflicting destinations.

The request folder schema and staging command are documented in `build-requests/README.md`. A request being present in the queue does not mean it has shipped; report its request ID and status in the lane status/manifest.

## Publish contract

Every completed publish must include:

- objective and result;
- files changed;
- exact tests run and results;
- evidence generated or required;
- confirmed facts vs hypotheses;
- whether human/NMS runtime intervention is required;
- migration/rollback notes;
- a backup reference or exact base commit and rollback path.

Before publishing lane research or a request bundle, preserve a backup reference and include tests, evidence, and lane status/manifest. Do not publish incomplete experiments. The lane author updates and publishes the lane's own manifest/status and affected lane-specific handoff/research records. Keep the main-branch copies of completed status/manifest changes synchronized so every agent can find one shared current state. Update `WORKSPACE_STATE.json` and relevant `AI_HANDOFF.md` sections in the same published change whenever lane ownership, objective, evidence pointer, blocker, next action, or shared research state changes; do not overwrite unrelated lane findings. The main compiler owns shared Surveyor integration/release fields, updater manifests, release version/changelog, and the complete source ZIP when compiling build requests. A PR is a fallback only if direct push is unavailable or rejected.

## Runtime test handoff

When human intervention is needed, the lane must reduce it to one explicit recipe: which ZIP/build to run, which known address/derelict to load, which button/action to use, what success indicator to wait for, and whether a traversal is required. Default is no traversal.

## Normal ChatGPT ↔ Work/Codex switching

The repository, not any chat's hidden context, is the continuity layer. A task must be resumable from GitHub alone.

Before a genuine human handoff and after each meaningful published milestone, update GitHub `main` and the lane status/manifest as applicable so another AI surface can continue without replaying private chat. Do not yield merely to announce an executable next step. At minimum keep these current when affected:

- `AI_HANDOFF.md`: architecture, confirmed facts, latest changes, test state, exact next action;
- `RESEARCH_INDEX.md`: measured/public-confirmed/inferred/hypothesis separation;
- `WORKSPACE_STATE.json`: current integration commit, lane states, human-intervention state, and next objective;
- the lane manifest under `agent-patches/<lane>/` when a lane has produced a build/tool;
- the main commit containing completed code/research, or the fallback PR if direct push is unavailable or rejected.

When switching modes, the incoming AI should first read `WORKSPACE_STATE.json`, then `AI_HANDOFF.md` and `RESEARCH_INDEX.md`, then only the active lane manifest/changed files. Do not reread the whole repository unless those files say it is necessary.

Both normal ChatGPT and Work/Codex may act as the integration AI. Only one integration operation should be active at a time; research lanes remain isolated. Codex Local may use a local worktree/terminal for implementation and tests, while normal ChatGPT or Work may review results and integrate through GitHub. No conclusion may rely only on private chat context: commit the evidence or summary needed to reproduce it.

## Agent Console status publishing

Surveyor's read-only Agent Console shows only status that has been published to GitHub; it cannot see private chat messages. Every agent lane should keep `agent-patches/<lane>/STATUS.json` current on its own branch, using `schema/agent-status-v1.schema.json`.

Update that file when starting work, when the state changes, and before asking the user to do anything. For a human request, include the exact Surveyor request, numbered user steps, the visible success condition, evidence to return, and whether a full derelict traversal is required. Clear the request when no longer needed. Never include tokens, local paths, device details, or personal data.

The main compiler reconciles shared `WORKSPACE_STATE.json` and release-level `AI_HANDOFF.md` fields when it integrates a build request. Lane agents update and publish their own status/manifest as work changes, keep the main copies synchronized, and update affected lane-specific handoff/research records; include build-request IDs and states where relevant. The console reads the main-branch registry and each lane's branch status/manifest with cache-busting requests. It displays the main registry age separately from each lane's heartbeat, marks lane status older than 15 minutes as stale, and keeps the last successful display if refresh fails. Do not treat an uncommitted chat update as visible or completed work.

Publish again after each meaningful milestone: a new finding, a changed prerequisite, a generated/uploaded artifact, an extension version change, or a request being completed. Keep `updated_utc` current and use `progress` for what is happening now, `blockers` for concrete obstacles, `next_action` for the next agent-owned step, and `extension_version` when the lane has a published UI extension. Update `STATUS.json` on the lane branch as soon as the user-facing state changes, and carry completed status/manifest changes into the direct-to-main publish.

Example waiting status (keep fields irrelevant to your lane concise):

```json
{
  "schema_version": 1,
  "lane": "runtime-dispatch",
  "updated_utc": "2026-10-02T10:30:00Z",
  "state": "waiting_on_user",
  "summary": "The live root dispatch slot still needs one capture.",
  "progress": "Static analysis is complete; waiting for one short NMS run.",
  "blockers": [],
  "next_action": "After the capture is uploaded, verify the exact slot and continue offline.",
  "extension_version": "1.0.1",
  "human_action": {
    "required": true,
    "surveyor_request": "Capture the live owner+0x10 slot at the known root event.",
    "steps": ["Start NMS from Surveyor.", "Wait for Root dispatch +0x10 captured.", "Click Analyze generation + upload."],
    "success_condition": "A fresh upload shows owner+0x10 and the target identity.",
    "evidence_to_return": ["run manifest", "exact root caller evidence"],
    "full_derelict_required": false
  }
}
```


## Latest combined parallel research

For the latest automatic saved-session batch, read `research/LATEST_AUTOMATIC_RESEARCH_BATCH.json`, verify the SHA-256 of the `batch-results.json` it names, then verify and read each per-session report listed in its `reports` array. Each report is its own evidence cohort, keyed by `session_sha256`; do not merge claims across saved sessions without explicitly comparing compatible inputs. The batch index is not itself the research result. Manual single-run research still uses `research/LATEST_PARALLEL_ACTION_TEST.json` and the combined report it names. Treat per-action latest files and `queue.jsonl` as diagnostics, not competing authoritative results.

The Surveyor also keeps a convenient local mirror under `research-output/automatic-session-batches/<batch-id>/`. Every saved session has a unique `runs/<session>-<hash>/combined-results.json`; the batch folder also contains `batch-results.json`, `queue.jsonl`, and per-session logs. This folder is on the user's PC and is not directly visible to cloud lane agents. Use the published GitHub batch pointer for shared access. The uploader publishes every completed session report separately, then publishes one batch index and a latest pointer in the same commit.

When `research/LATEST_ROOT_SEED_BATCH.json` exists, verify the referenced report SHA-256 and inspect its listed source capture journals. The Surveyor batch action reads append-only root-resource events, groups them by process journal and universe address, and publishes the report with those exact journals for all lanes. Treat repeated samples at one address as repeats. Keep process journals separate unless executable identity is verified, and do not claim an address-to-root-seed formula from correlation alone.
