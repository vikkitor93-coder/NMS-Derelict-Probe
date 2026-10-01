# Surveyor agent UI extension contract

Contract version: **1**. Surveyor host UI API: **1.0**. This guide applies to all four research lanes; lane extensions add panels to the shared Agent Console rather than shipping separate Surveyor builds.

## Files and identity

Publish extensions under `agent-ui/extensions/<lane-id>/<extension-version>/`:

- `manifest.json` declares `schema_version: 1`, `extension_id` (the stable lane ID), semantic `version`, `compatible_surveyor_api_version: "1.0"`, `min_surveyor_version`, `dependencies`, `entry_point`, and `files`.
- `files` is a list of every panel/asset JSON path plus its lowercase SHA-256. The entry point must appear in this list.
- `panel.json` is the entry point. It declares `schema_version: 1`, a short `title`, optional `summary`, an `actions` list, and optional `request_only` (default false). When `request_only` is true, Surveyor shows action buttons only while that lane's published status says it needs human input.
- `agent-ui/extensions/index.json` lists each current extension identity, version, and relative manifest path.

All paths are relative POSIX `.json` paths. Do not include `..`, absolute paths, executable files, Python modules, URLs, or shell commands. Surveyor validates identity/version compatibility and every listed hash before it activates a panel. The loader accepts only the documented JSON keys; extra fields are rejected.

## Panel and action requests

Each action request uses this shape:

```json
{
  "action_id": "research.extract_exact_root_caller",
  "label": "Extract exact root caller + upload",
  "description": "Runs the reviewed offline extractor.",
  "preconditions": ["workflow.idle"],
  "evidence_namespace": "dungeon-decompile",
  "parameters": {}
}
```

`action_id` must be one of the stable host IDs below. The extension requests an action; Surveyor maps it to its own reviewed handler. Extensions cannot provide commands, paths, process arguments, or executable code. API 1.0 accepts empty parameters because the current registered actions do not need caller input. A future host API may add named parameters only when the host defines and validates their type/range; do not encode user input into action strings.

Stable action IDs in host API 1.0:

| Action ID | Host behavior |
| --- | --- |
| `research.analyze_seed_function` | Analyze the seed function and upload evidence |
| `research.extract_upstream_callers` | Extract upstream callers and upload evidence |
| `research.extract_exact_root_caller` | Extract the exact root caller and upload evidence |
| `research.resolve_root_vtable` | Resolve the root vtable and upload evidence |
| `research.extract_caller_code` | Extract caller code and upload evidence |
| `research.measure_generation` | Measure generation and upload evidence |
| `research.prepare_assets` | Prepare crate assets and upload evidence |
| `research.analyze_generation` | Analyze generation and upload evidence |

Supported declarative preconditions are `workflow.idle`, `nms.running`, and `probe.connected`. Surveyor checks them both before displaying and immediately before running an action. Unknown IDs, unsatisfied preconditions, and actions unavailable in the installed host are disabled or rejected without invoking a process.

`dependencies` is a list of capability IDs. API 1.0 supports `agent-console.ui.v1` and `action.<stable-action-id>` for the host actions listed above. Unsupported dependencies prevent activation. `evidence_namespace` must equal the extension/lane ID. The existing upload helper appends it and a unique short run ID to the timestamped repository folder (`research-uploads/<UTC>-<lane>-<action>-<run-id>/`) and run manifest. Surveyor also writes a collision-safe local action record below its extension state folder. Keep action outputs within these lane/action folders; never use a shared `latest` filename as the only evidence artifact.

## Lifecycle, errors, and rollback

Extensions are data-only panels, so loading/reloading does not import agent code. Surveyor downloads into a staging folder, checks version/API compatibility and SHA-256 values, then atomically installs and activates the extension while the main window stays open. Prior versions remain installed. If download, validation, or rendering fails, the prior panel remains active and the core Surveyor actions continue to work. The panel provides rollback to the newest older installed version.

Panels may update live. Changes to Surveyor host code require a normal Surveyor update/restart; changes to injected probe hooks require a compatible probe build and an NMS restart. Never hot-swap probe/backend code into a running NMS process.

## Publishing and integration review

1. Create a new semantic extension-version directory; never overwrite an already published version.
2. Recompute SHA-256 for every file and update `manifest.json` and the shared index.
3. Run the extension validation/update/rollback tests and include the exact results in the PR.
4. Submit the manifest, panel JSON, index change, and any required tests in the lane PR. Keep the lane's standalone research workflow usable until integration accepts it.
5. Integration reviews the action IDs and preconditions, file hashes, lane output namespace, host/API compatibility, and rollback. Do not combine different lane actions into an indiscriminate “Run All.”

## Copy/paste prompt for a lane agent

```text
Read AGENT_UI_EXTENSION_GUIDE.md and the current WORKSPACE_STATE.json. Implement only the optional Surveyor UI extension for your lane `<LANE-ID>` using the shared host UI API 1.0 contract. Add a versioned data-only JSON panel and manifest with hashed files; request only stable host action IDs that fit your lane, declare exact preconditions and the lane evidence namespace, and do not provide shell commands, executable code, or arbitrary process arguments. Preserve Surveyor core behavior, controller/probe protocols, and your standalone workflow. Test compatibility, integrity rejection, live refresh, and rollback; then publish the extension, index update, tests, and a manifest/patch/PR. Do not invent a second extension API or combine lane actions into Run All.
```
