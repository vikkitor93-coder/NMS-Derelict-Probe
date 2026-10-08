## DUNGEON-C Oct 8 combined report and current hook recheck — 2026-10-08

The Oct 8 combined report was read from the user-provided local 0.3.62 candidate, and its bytes match the pointer SHA-256 12035c7362e77363af084bc24254c7b013edecba6ca9015f1d3c6985ea527eda. The attached candidate and its 13:02 run report are not published on main; DUNGEON-C did not publish or replace either shared file. GitHub main has since received a separate 13:43 combined report, now referenced by research/LATEST_PARALLEL_ACTION_TEST.json; its SHA-256 3af46d71fbeabc5810f3c83dbdd93b59cc2cfd71358dbaa6bb9c35c398e38592 was verified against the main-branch report bytes. Each combined report is authority only for its own run: both report 8 saved-evidence offline actions, upload skipped, and no NMS attachment or new capture.

The report's current caller is 02C08607: FF 52 10 / return 02C0860A. The separate resolver input is 02C04977 / 02C0497A and returns zero matches for 00634BC0; do not combine the samples or infer the target. Keep the 43 asset-derived prediction distinct from both the historical 35-container measurement and separate post-update 16-container observation.

DUNGEON-C rechecked its saved 89-byte 0063A6D0 hook body: its verified hash still matches, and bytes at 0063A706 encode an E8 rel32 destination of 033E1B60, followed by cmp rax,rbx and a conditional branch. The existing export lists zero direct-call candidates, so the inconsistency is recorded without assigning semantics. RVA 033E1B60 has no verified .pdata range/body because the matching executable is absent from the repository and standard checked game paths. Review: agent-patches/dungeon-decompile/PARALLEL_REVIEW_20261008.json.

Next D action: provide NMS.exe with SHA-256 13d5060d4efb9d2a6a6b1b349bc4257231056cc2a055df4bb15d816262cc3499, or a hash-matched export containing .pdata and code at 033E1B60. No live NMS session or traversal is needed for that offline validation.
# NMS Derelict Probe — AI handoff

## Seed-B review of main's 14:02 combined report

Main pointer run `20261008T140207Z-d8e24197` and report `research-uploads/20261008T140254Z-parallel-action-test/combined-results.json` were hash-verified (`11ec9ee30687570efda334a255ea27836bfb347d8bf7631ec4ffae981e9175f6`). The eight completed actions analyzed saved evidence offline; upload was skipped and the parallel run did not attach to NMS. Its generation artifact contains a saved root event from `20261008T140041Z_0001BF0004E84EFD`, timestamped 14:00:37Z, with descriptor `0000021C2457DD28`, owner `0000021C2457DC00`, and root seed candidate `5B4AE67D9C2A8F61`. The direct Engine caller is `0063AC20` -> `0183E770`. A separate logical-entry event from that saved trace is `02C08607: FF 52 10` / return `02C0860A`; owner+0x10 was read after the external call and at root add, both zero. Dispatch target and seed derivation remain unproven.

The asset analyzer infers CARGO_FLOATERS at high confidence and predicts 43 target containers (30 salvage, 13 footlockers) across 164 scene instances / 11 logical chunks. The 43 is asset-derived, not a measured physical count. POI generation receives the universe address as a raw argument, while its return is the component address; no root seed transformation is demonstrated. Caller-code and upstream results in the report use older source sessions and must not be joined to the fresh saved event as one trace.

Seed-Lineage extension 1.0.3 requests existing shared Surveyor actions in sequence: Extract caller code, then Extract upstream callers. The next human request is to refresh the extension, record a fresh root event in universe `0001BF0004E84EFD`, run those actions, and return both run manifests. No traversal is required. Full lane analysis: `agent-patches/seed-lineage/SEED_B_PARALLEL_REVIEW_140207_20261008.md`.

## Runtime-A Oct 8 combined report review

The supplied local v0.3.62 candidate's pointer/report for run `20261008T130233Z-755d4c43` were verified (report SHA-256 `12035c7362e77363af084bc24254c7b013edecba6ca9015f1d3c6985ea527eda`). This remains a local candidate and is not the current `main` pointer. The latest `main` pointer now names run `20261008T140207Z-d8e24197`, report `research-uploads/20261008T140254Z-parallel-action-test/combined-results.json`, SHA-256 `11ec9ee30687570efda334a255ea27836bfb347d8bf7631ec4ffae981e9175f6`, verified against the report bytes. Its eight actions are offline reanalysis, upload was skipped, and the harness did not attach to NMS. Its saved-evidence snapshot includes a root event timestamped `2026-10-08T14:00:37.544Z`; the report does not establish how that event was captured. Neither shared pointer nor report was changed by Runtime-A.

The saved current caller is `02C08607: FF 52 10`, return `02C0860A`. In the latest report's saved event, the probe's logical-entry snapshot is after the external call; owner+0x10 is zero at entry and root-add, so the target remains unresolved. The resolver result is a separate sample at `02C04977`, return `02C0497A`, with zero offline vtable matches for candidate `00634BC0`; it does not resolve the current call. Asset analysis predicts 30 crates plus 13 footlockers (43 predicted targets) across 164 scene instances. This prediction is not an observed physical count and does not replace the historical 35-container measurement or post-update 16-container observation. See `agent-patches/runtime-dispatch/RUNTIME_A_PARALLEL_REVIEW_20261008.md` and the lane manifest for provenance and limits.

The latest saved event already repeats the post-call zero read. The remaining Runtime-A step is a pre-instruction observation at `NMS.exe+02C08607` (`FF 52 10`), recording `RDX` and `[RDX+0x10]` before execution; verify NMS.exe SHA-256 `13d5060d4efb9d2a6a6b1b349bc4257231056cc2a055df4bb15d816262cc3499`. A debugger capture at one root event is sufficient; no full traversal is needed. The data-only panel is version 1.0.3 and preserves 1.0.2 for rollback. Probe/app code did not change.

## METADATA-D combined offline action review — 2026-10-08

The user-attached local Surveyor 0.3.62 source ZIP contains `research/LATEST_PARALLEL_ACTION_TEST.json` and its combined report for run `20261008T130233Z-755d4c43`. The report SHA-256 matches the pointer: `12035c7362e77363af084bc24254c7b013edecba6ca9015f1d3c6985ea527eda`. The ZIP is a local candidate, and Agent D did not publish its 13:02 pointer or report to `main`. The current main pointer names a distinct 13:43 run. `agent-patches/metadata/PARALLEL_ACTION_REVIEW_20261008.json` is Agent D's derived review and records the ZIP hash, report provenance, metadata artifact hashes, and limits. A complete snapshot of the current published 0.3.61 source plus this review is encoded separately under `packages/v0.3.61-metadata-parallel-review-source/`, with `agent-patches/metadata/METADATA_PARALLEL_SOURCE_SNAPSHOT_20261008.json` as its transport manifest; it is not an updater release.

The offline `research.prepare_assets` action completed with code 0 using a saved October 6 session. It indexed 1,433 dungeon scenes, found target references in 75, and resolved 164/164 scene instances. Its 43 targets (30 salvage crates and 13 footlockers) are an **asset-derived prediction**, separate from historical observed counts of 35 and 16. The saved-generation analyzer groups those predictions into 11 logical rooms: 33 targets in eight CARG groups, 10 in two BARRACKS groups, and zero in one END group. These are analyzer-derived groupings, not physical room observations or an exact mapping to the table's `Rooms=7` field. `CARGO_FLOATERS` remains a high-confidence preset inference from saved scene and hazard evidence; the run did not observe a selected `DungeonOptions` value. It did not attach to NMS, capture a new event, or upload to GitHub. The report's zero owner+0x10 reads and its separate resolver sample do not resolve a dispatch target. METADATA-D 1.0.1 remains unchanged because this isolated test did not exercise its upload flow.

## Seed-B constructor capture candidate — 2026-10-08

Seed-B has a tested read-only constructor-capture patch on `agent/seed-lineage` (`c429ff3`) and a local 0.3.62 candidate ZIP. It is not on main because live hook and object identity are unverified. The lane status gives a short root-capture recipe without traversal. The candidate keeps probe protocol `0.3.38` and marks root events with `seed_b_variant_version`; empty matches are diagnostic, not a negative proof. This is separate from the October 8 offline combined-report result.

## Seed-B combined-report review — 2026-10-08

Seed-B verified the user-attached 0.3.62 local candidate's `research/LATEST_PARALLEL_ACTION_TEST.json` against its combined report (SHA-256 `12035c7362e77363af084bc24254c7b013edecba6ca9015f1d3c6985ea527eda`). The report is not published here. It is the sole source for the October 8 parallel run: eight offline saved-evidence actions completed, one upload disabled, no new NMS event. Source sessions differ across generation/asset, seed-function, and upstream analysis. The 43 target containers are an asset-derived prediction (30 salvage crates + 13 footlockers), separate from historical observed 35 and post-update user-observed 16. The saved exact caller is `02C08607: FF 52 10`, return `02C0860A`; the zero owner `+0x10` read is not a pre-call slot target. The resolver's zero-match result comes from another caller sample (`02C04977`) and does not resolve current dispatch. See `agent-patches/seed-lineage/SEED_B_PARALLEL_REVIEW_20261008.md` for provenance, static constructor trace, and limitations. Root seed derivation remains unproven. No new extension or runtime behavior is published.

## METADATA-D publication — 2026-10-07

Agent D followed the active component's `DungeonRootScene` asset through its direct scene attachment. The root scene contains one `GeneratedBaseRoot` locator, which attaches `GENERATEDBASEROOT.ENTITY.MBIN`; that entity contains gravity-volume and static-physics components. The root scene has no direct room-scene reference. `agent-patches/metadata/STATIC_ROOT_SCENE_TRACE_20261007.json` records exact MBIN hashes and the ten presets' main/branch room IDs. A complete source snapshot containing this handoff is encoded in `packages/v0.3.61-metadata-static-source/` with its own `agent-patches/metadata/METADATA_SOURCE_SNAPSHOT_20261007.json` manifest; it is not a new updater version. This narrows the static boundary but does not establish how the runtime `DUNGEON.SCENE.MBIN` resource or room assets are chosen.

Surveyor 0.3.61 repairs `Prepare-Crate-Assets.ps1` by passing `--input-format=MBIN -y` to MBINCompiler. The persistent extraction directory may contain both MBIN and previously generated MXML files; the old command could stop at a prompt in the noninteractive METADATA-D action. The Windows action completed preparation and both uploads with exit status 0 after the local repair. The user subsequently confirmed the METADATA-D visual refresh and rollback check. This last check is user-reported; the action logs and main-branch run manifest are recorded separately in `agent-patches/metadata/PREPARE_ASSETS_REPAIR_20261007.md`.

The active abandoned-freighter entrance component has ten static `DungeonOptions` choices, all matched by name to current dungeon-table presets. The choices and exact source hashes are in `agent-patches/metadata/CURRENT_DUNGEON_OPTIONS_20261007.json`; method and limits are in `STATIC_DUNGEON_OPTIONS_MAP_20261007.md`. These weights do not prove runtime selection probabilities, seed input, or frequencies. The component's static `DungeonRootScene` field is not yet linked to the separately observed runtime `DUNGEON.SCENE.MBIN` resource. Seed-lineage and dungeon-decompile lanes own those other links.

The source package is a complete 0.3.61 ZIP, encoded in `packages/v0.3.61-full/` and described by the root `update-manifest.json`. The previous main commit is preserved at `backup/main-before-metadata-d-20261007-final`. The smallest functional change from 0.3.60 is one line in `Prepare-Crate-Assets.ps1`; no extension panel, host action ID, probe protocol, or NMS write behavior changed. Next Agent D task: continue independent static metadata and asset relationship analysis; require a live capture only if a specific remaining claim cannot be resolved offline.

## DUNGEON-C current hook export — 2026-10-07

Ran the v0.3.39 offline helper exporter on a derived copy of the October 6 event with its stale hook label corrected by the unique current executable signature. The original uploaded event is untouched. The resulting `agent-patches/dungeon-decompile/ROOT_CALLBACK_CODE_20261007.json` contains the current `0063A6D0..0063A729` bounded hook bytes and explicit raw-source provenance. Its adjacent branch range `0063A729..0063AB6C` has a direct self call at `0063A76E`, returning at `0063A773`; this independently confirms the current recursive return. The actual pre-call dispatch slot remains uncaptured.

## DUNGEON-C October 6 root review — 2026-10-07

A fresh root event, descriptor `00000112B726B528`, records caller return `02C0860A` on the current executable; the bytes at `02C08607` are `FF 52 10`. The probe source hook signature matches uniquely at current `.pdata` function start `0063A6D0`. The report is `agent-patches/dungeon-decompile/NEW_ROOT_CAPTURE_REVIEW_20261007.json`. The probe still publishes old-build labels `00634BC0` (logical entry) and `00634C63` (recursive return), and the uploaded code/vtable exports are from the older executable and descriptor. The prior map to `006369F0` remains a map of that old label only; its five-helper dataflow is not established as the root callback.

The captured zero is owner+0x10 after the call, not a pre-call `[RDX+0x10]` dispatch target. Analyze `0063A6D0` offline; a future current-build event with a pre-call slot read is needed to prove the indirect target.

## DUNGEON-C helper dataflow — 2026-10-05

The current-build parent conditionally processes four nonzero 32-bit fields in the order `RSI+0x50`, `+0x58`, `+0x54`, `+0x5C`. Each follows a retain-like helper, appends the value to a 32-bit resizable list at `RSI+0x40`/`+0x44`/`+0x48`, and then follows a release-like helper. The exact instruction evidence and `.pdata` limitations are in `agent-patches/dungeon-decompile/HELPER_DATAFLOW_20261005.json`. Field meanings, list consumers, and the actual indirect callback destination remain unproven.

## DUNGEON-C updated executable map — 2026-10-05

The installed NMS.exe changed after the earlier runtime captures (current SHA-256 `13d5060d4efb9d2a6a6b1b349bc4257231056cc2a055df4bb15d816262cc3499`). Offline byte matching and PE unwind ranges map the old bounded parent `00634930..00634E03` to current `00636760..00636C33`; its old hook offset maps to `006369F0`. The indirect caller bytes `FF 52 10` map from `02C04977` to `02C08607`. All 33 decoded direct calls retain the same position relative to the parent and map to seven current targets. See `agent-patches/dungeon-decompile/CURRENT_BUILD_STATIC_MAP_20261005.json` for the target table and hashes.

These are static cross-build mappings, not a new runtime root event or proof that `[RDX+0x10]` resolves to the mapped parent. Use current-build RVAs only with the matching executable; retain the earlier runtime and gameplay evidence as historical.

## DUNGEON-C helper export review — 2026-10-05

The offline helper export and shared upload are complete. The newest shared batch is `research-uploads/20261005T014820Z-all-saved-evidence-a065a8b5/`; its 01:03 root event and code export have matching descriptor `000001DCBF948128`. The 23:17 event was also exported separately for local review with matching descriptor `0000015E2450A928`; it was not the later shared batch's latest event.

DUNGEON-C validated all 20 exported callsites against its 33-site decoded inventory and independently decoded their instruction boundaries. Five helper bodies match their declared byte counts, SHA-256 hashes, and `.pdata` ranges. The other 13 decoded calls reach a small `ret 0` leaf (12) and a `VCRUNTIME140.dll!memcpy` import thunk (one). See `agent-patches/dungeon-decompile/HELPER_EXPORT_REVIEW_20261005.json`. The indirect `FF 52 10` destination remains unproven; `00634BC0` is the runtime-correlated hook RVA within `.pdata` range `00634930..00634E03`, not that range's start. The historical 35-container baseline, earlier 16-target prediction, and user's newer physical layout/count confirmation remain separate.

No further offline export or derelict traversal is needed for this step. The next DUNGEON-C work is static helper dataflow analysis; proving the indirect callback destination requires a later live slot/register capture in the runtime-dispatch lane.


## Current crash-recovery update — 2026-10-05

The current published base is Surveyor **0.3.59**, built from v0.3.58. The working update is Surveyor **0.3.60** with probe **0.3.38**. It appends and flushes each trace event to a per-process JSONL journal, fsyncs root events immediately and other records in bounded batches, persists every dungeon root event (seed and universe metadata included) even if exact caller or `+0x10` capture is unavailable, and adds these artifacts to deduplicated Upload all saved evidence. With automatic uploads enabled, root evidence uploads after a short debounce and changed journal evidence is batched every 30 seconds, including after a successful slot capture. Pending root evidence remains distinct from a successful slot capture. Session snapshots remain periodic and are atomically flushed before replacement. The Linux test suite passes; Windows UI and live NMS validation remain outstanding.

The game must still be running while an event occurs for a runtime hook to observe it. Once observed, the journal and root-event artifact are local durable files and can be uploaded after the game exits or crashes. Automatic sharing follows the existing remembered auto-upload toggle.

## Historical Runtime-A candidate — 2026-10-04

This was the recorded 0.3.57 investigation state before the current v0.3.58 package was published. The old base-version and candidate notes below are retained as historical context.

Runtime-A probe 0.3.37 now combines the existing shared-entry owner+0x10 capture with RCX/RDX and raw [RDX+0x10] capture at that same entry hook. The later root-add sample remains separate. The lane patch and manifest must state the official package SHA-256 and the embedded base probe version (0.3.35).

Surveyor v0.3.58 and probe 0.3.37 were the previous published base. v0.3.59 / probe 0.3.38 is now published; v0.3.60 keeps the same probe.


## Current state

- Current package: **v0.3.60 candidate**. It retains the nested-frame startup fix, automatic upload toggle, and existing v0.3.58 behavior while adding crash recovery.
- **Automatic GitHub evidence uploads** are controlled by a remembered checkbox under GitHub / updates. Enabled by default: a new persisted root capture is uploaded automatically, and after a research or lane action the Surveyor uploads a deduplicated all-lanes evidence batch if its contents changed. The lane-specific action upload remains part of its explicit action workflow. Uncheck the option to stop background root and shared-batch uploads; manual uploads remain available. The all-lanes fingerprint receipt is stored under `%LOCALAPPDATA%\NMSDerelictSurveyor`.
- **Upload all saved evidence** snapshots every existing research output declared by `ACTION_OUTPUTS` into one deduplicated `research-uploads/<timestamp>-all-saved-evidence-<id>/` folder on `main`. Its manifest lists which actions produced each file and marks it visible to all four lanes. The Surveyor writes a receipt to each lane card after success. This is a shared repository upload, not an automatic agent notification or a write to their status branches.
- Overlapping local `*-latest` outputs: `generation-baseline-latest.json` (measure/analyze-generation), `generation-measurements-summary.json` and `generation-measurements.csv` (measure/compare-measurements), `seed-room-correlation.json` (measure/analyze-correlation), and `exact-root-caller-latest.json` (analyze-generation/Runtime-A upload). Local latest files are replaced by a producer rerun; GitHub uploads are timestamped snapshots.
- Runtime-A can now upload its already-persisted root event after closing NMS via **Upload captured root event**; this panel action needs only the saved capture and an idle Surveyor workflow.
- Current source package: **v0.3.60 candidate**. Probe **0.3.38** preserves exact root caller and entry register capture, and now writes root-event recovery data even when caller correlation or the slot read is unavailable. Capture still requires NMS running while the event occurs; saved artifacts can be uploaded after quitting. Surveyor’s app updater stages the probe into the installed MODS folder; fully restart NMS after installing the app update.
- Surveyor does not redistribute DerelictFreighterFarming files. Download your own archive and use **Install Derelict Farming archive** in the GitHub / updates section. The installer accepts only three expected EXML files, validates their XML, stages them under `GAMEDATA/MODS/DerelictFreighterFarming`, and preserves conflicts. Roll back with `python tools/github_integration.py rollback-derelict-farming`. The supplied archive targets 7.04; NMS 7.05 behavior is not yet validated.
- Agent Console has four side-by-side lane cards. The fixed **NEEDED** box shows the published request, actual extension action, exact required prerequisite keys, and which prerequisites are currently missing. It does not contain generic step guidance. The actual host key is `probe.connected` (fresh probe heartbeat), not `probe.running`; the v1 extension contract is unchanged.
- Installed/published/reported versions remain immediately under NEEDED. Each evidence receipt checkbox stays fixed below its lane buttons.
- Compact top-right +/− controls collapse each major main-window section, each Agent Console card, lane action groups, and global action group. The controls and content begin expanded; lane/global buttons remain pinned in the bottom strip. Agent Console display toggles and refresh interval persist in `%LOCALAPPDATA%\NMSDerelictSurveyor\agent-console-options.json`.
- Auto-refresh defaults to one minute; choices are 20 seconds, 2 minutes, 5 minutes, or Off. **Refresh now** fetches status and extension index immediately. Network reads run on background threads; cache-busted lane status requests remain read-only.
- Polling reuses unchanged extension widgets and action readiness uses the main window’s latest NMS/probe status instead of launching new process checks per lane, keeping scroll position stable and refresh work lighter.
- The overlay display toggles now live in the main Surveyor window; opacity and horizontal/vertical placement sliders apply live. Agent objectives come from the published status snapshot, and the overlay shows root-detected completion plus “waiting for upload / don’t close game” where applicable. `Root dispatch +0x10` now reports the raw slot value and best-effort module identity when a read succeeds; its meaning remains unproven until live evidence is reviewed.
- Main Status and the in-game overlay now show the exact root resource path and observed event count. `Root dispatch +0x10` is shown separately and uses the capture field emitted by Runtime-A probe 0.3.34.
- **Start overlay** and **Stop overlay** sit beside the existing **Game overlay** auto-start toggle. Stop closes the titled overlay window and signals the local stop-request file, including overlays started by the NMS launcher.
- The package carries DUNGEON-C 1.0.2, Metadata-D 1.0.1, Runtime-A 1.0.1, and Seed-B 1.0.2, with prior installed versions retained for rollback. The Runtime-A panel stays data-only; its analyze/upload action is unchanged.

## Purpose and architecture

Reverse engineer No Man’s Sky abandoned-freighter generation using static and runtime evidence while keeping Surveyor independent from the game. `tools/surveyor_controller.py` is the Windows Tk app and action host; `mod/derelict_baseline_probe.py` collects read-only process evidence; `overlay/derelict_overlay.py` formats live status. `tools/agent_console.py` reads public GitHub lane status. `tools/agent_ui_extensions.py` validates and installs data-only JSON panels.

## Contracts, configuration, and diagnostics

- Start with `Start-Surveyor.cmd` / `Start-Surveyor.ps1`; Surveyor can run independently of NMS.
- Agent status uses schema v1 (`schema/agent-status-v1.schema.json`) from `agent-patches/<lane>/STATUS.json`; optional progress, blockers, extension version, and human-action fields are backward-compatible. Agent lanes publish status commits at meaningful milestones.
- Extension panels use shared UI host API 1.0 and hash-checked `manifest.json`/`panel.json` entries indexed by `agent-ui/extensions/index.json`. Extensions may call only registered host action IDs; no supplied shell or Python runs. Receipts are display-only and never lock actions.
- Session/live status schemas and probe/overlay command protocol remain v1. No data migration is required.
- Controller and workflow logs: `%LOCALAPPDATA%\NMSDerelictSurveyor\gui-actions\`; live status: `%LOCALAPPDATA%\NMSDerelictSurveyor\live-status.json`.
- Agent Console settings remain in its local options JSON. Overlay display settings live in `%LOCALAPPDATA%\NMSDerelictSurveyor\overlay-settings.json`; the current objective snapshot is `overlay-objectives.json`.

## Build, run, and test

- Windows with Python 3.12/3.13 and Tkinter; launch `Start-Surveyor.cmd`.
- `python -m compileall -q tools overlay tests`
- `python -m unittest discover -s tests`
- In Agent Console use **Refresh now** for an immediate poll or select **Off** to pause automatic status and extension checks.

## Latest changes and verification

- v0.3.57 fixed the startup `TclError` caused by mixing `pack` and `grid` in the GitHub / updates body.
- v0.3.56 adds a persistent auto-upload toggle. When on, saved Runtime-A captures upload automatically and changed all-lanes evidence is published after research/agent workflows. Batch fingerprints prevent repeated uploads of identical saved files.
- v0.3.54 persists the complete runtime root event, metadata, and universe address in the existing atomically saved/uploaded capture artifact; schema and upload path remain compatible.
- v0.3.48 adds main-window overlay display controls, live opacity/position settings, and published agent objectives. v0.3.47 adds visible root-resource and dispatch-capture status plus manual overlay lifecycle controls. v0.3.46 shows exact prerequisites and missing state in NEEDED, adds per-section +/− controls in both windows, and uses cached game/probe state for action readiness.
- `python -m compileall -q tools overlay tests mod` and the full unittest suite passed for v0.3.51 (173 tests). Windows pyMHF/NMS live validation is still required for the new capture.
- Runtime-A’s new capture implementation is present in probe 0.3.34, but live Windows/NMS validation and semantic interpretation remain pending; exact-root-caller output alone is not proof of a slot read.

## Rollback and next action

- Roll back the app by reinstalling the previous complete v0.3.49 package. Roll back the installed farming mod with `python tools/github_integration.py rollback-derelict-farming`. No probe, session, extension API, or saved evidence migration is needed. Extension versions retain their individual rollback controls.
- **Next action:** update Surveyor, select your downloaded mod ZIP with **Install Derelict Farming archive**, fully restart NMS, then test repeat derelicts in the same system. Confirm `+0x10` remains pending until a real capture is reported.


## Seed-B review of latest combined report (2026-10-08 18:53 UTC)

The current main pointer names run `20261008T185304Z-e95aae15`, report `research-uploads/20261008T185341Z-parallel-action-test/combined-results.json`, SHA-256 `9576e887375b1d79ad629b07a26209337479ff6cf096222207de4c53a130dcbe`. The hash was verified against the fetched report bytes. This is the sole source used here for this parallel run's results. The parallel run itself was isolated/offline, with an input snapshot and no retained worker data; the runtime upload action was disabled.

The report's generation artifact derives from session `20261008T185119Z_0001550006607CAC`, universe `0001550006607CAC`. It records one root `DUNGEON.SCENE.MBIN` resource event at `2026-10-08T18:51:04.549Z` with root-seed candidate `00C9E8DF0327789E`; derivation remains unproven. The analyzer infers `MEDI_FLOATERS`, 10 logical rooms and 146 scene instances, predicting 14 target containers (7 salvage + 7 footlockers) from assets. This is not a physical count. It is separate from the prior `CARGO_FLOATERS` asset-derived prediction of 43 targets (30 salvage + 13 footlockers).

Seed-Lineage extraction did not consume the fresh event: caller output cites source session `20261006T223811Z_0001BF0004E84EFD`; upstream cites `20261004T151219Z_0001BF0004E84EFD`; seed-function analysis cites `20261002T213047Z_00001A0004E84EFD`. Do not join those static/offline results to the 18:51 event. Exact-root caller bytes decode `02C08607: FF 52 10` returning at `02C0860A`, but no dispatch target is established. The zero-candidate resolver sample is `02C04977` / `02C0497A`, a separate callsite.

Next: use shared-main RUNTIME-A 1.0.6 to upload the saved root event, then Seed-Lineage 1.0.3 Extract caller code and Extract upstream callers in order. Require the new caller to cite session `20261008T185119Z_0001550006607CAC` and the matching executable SHA-256 before correlating it. No new NMS launch or derelict traversal is required if the saved capture remains available. Full lane status: `agent-patches/seed-lineage/STATUS.json`.
