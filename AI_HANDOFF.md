# NMS Derelict Probe — AI handoff

## Agent operating contract — 2026-10-08

Agents must keep executing their assigned work until a genuine human-only gate remains. At every apparent stopping point, check whether the next useful action can be completed from available code, repository history, uploaded evidence, tests, or tools; if it can, do it. Diagnose failed attempts and try a reasonable fix or fallback. Do not leave an executable agent-owned “next step” for the user or another agent, and do not stop after an intermediate finding. When the assigned task is complete, continue with the next useful non-duplicative task in the same lane. A dependency blocks only the work that depends on it; continue independent work.

Ask the user only for a required live NMS/PC action, inaccessible local evidence, unavailable credentials/authorization, or information only they can provide. First complete all independent work, then publish a single numbered recipe with the exact Surveyor control/action, success condition, evidence to return, and whether traversal is required. Lane status must say `waiting_on_user` only for such a real gate; otherwise `next_action` names work the agent will perform.

Publish completed, tested, documented lane research and build-request bundles to GitHub `main` under the direct-publish policy, with a backup reference or exact base commit and rollback path. Keep unfinished experiments on the lane branch. Lane authors own their lane status/manifest and affected lane-specific handoff/research records; keep completed main-branch copies synchronized and update `WORKSPACE_STATE.json` and relevant handoff sections when lane facts or shared research pointers change. The primary integration assistant alone compiles shared Surveyor/updater releases from ready build requests. When project/source files change, update this handoff and include a complete current source ZIP. See `AGENT_START_HERE.md`, `AGENT_WORKFLOW.md`, and `build-requests/README.md` for the detailed contract.

## METADATA-D room-group reconciliation — 2026-10-08

The latest pointer is `research/LATEST_PARALLEL_ACTION_TEST.json`; its report is `research-uploads/20261008T195856Z-parallel-action-test/combined-results.json`, SHA-256 `b74d988e78f4001f870980e47776e77ddf3f14f97e5d8cfd4a9fde3c501dcd41`, run `20261008T195817Z-1b73e442`. The hash was recomputed from the report bytes and matches the pointer. This is an isolated manual-button reanalysis of saved session `20261008T185119Z_0001550006607CAC`, not a fresh live capture. It infers MEDI_FLOATERS with 10 analyzer parent-key groups versus static `Rooms=7`; 14 targets are asset-predicted, not observed.

The earlier CARGO_FLOATERS run remains authoritative for its own run: `20261008T140207Z-d8e24197`, report SHA-256 `11ec9ee30687570efda334a255ea27836bfb347d8bf7631ec4ffae981e9175f6`. It reports 8 CARG-dominant, 2 BARRACKS-dominant, and 1 END-dominant parent-key groups (11 total). Its 43 targets (30 salvage + 13 footlockers over 164 resolved scenes) remain an asset-derived prediction, separate from physical observations.

Static CARGO_FLOATERS has `Rooms=7`, five main IDs (`R_END`, `R_FLO_BARR`, `R_S_FLO_BARR`, `R_FLO_CARG`, `R_S_FLO_CARG`) and two branch IDs (`B_FLO_BARR`, `B_FLO_CARG`). Exact-count rules require one each of `R_FLO_BARR`, `R_S_FLO_BARR`, and `R_END`; `R_END` has minimum index 6. The two BARRACKS-dominant groups and END group at index 10 are only numerically compatible with those constraints. Eight CARG-dominant groups cannot be assigned among the two CARG main IDs and one CARG branch ID from family labels or `Room N` names.

The current DUNGEON-C branch `agent/dungeon-current-target-20261008-reconciled` (commit `1904a3c381889ed1c0418ee91ebd38b571c914d1`) records a separate user-reported 11-room traverse but has no per-room RoomId crosswalk in its manifest, status, or tracked mapping artifacts. Therefore the 7-versus-11/10 difference remains unresolved: parent-key grouping/classification may contribute, but generator semantics are not established. See `agent-patches/metadata/ROOM_MODEL_RECONCILIATION_20261008.json`.

## v0.3.67 publication record — 2026-10-08

Surveyor v0.3.67 and its full updater package are published on `main`. The release recovers unprocessed saved sessions at startup, checks exact source hashes against prior automatic reports, and runs each unprocessed session separately in FIFO order. The updater manifest points to 37 package chunks; each remote chunk was checked against the verified local package. Package SHA-256: `2a00db2de00b09f6b89685c0f0e302b731a0db0097a658d8242c249d524e5ca0`. Local verification: 210 unit tests, compileall, harness self-test, and ZIP/member/index/hash checks passed. Backup branch: `backup/main-before-saved-session-backfill-20261008` (based on main `fb1edd38c94774b3f4be08a198702840d1bdf559`). Windows backlog execution remains pending.

## Startup recovery for saved-session research — 2026-10-08

The first queue fix restored persisted pending items but could not recover sessions queued by older builds, because those builds did not save the queue. Surveyor 0.3.67 now scans saved session JSON files on startup, verifies each file and its ended state, and queues files that lack both a persisted queue record and an automatic combined report with the same SHA-256. It orders recovered sessions by ended time and records any exact-hash prior report as already processed. This allows sessions from the earlier in-memory queue to be recovered after updating, while avoiding duplicates for the one session represented by the existing report.

The queue continues one report per saved session, persists queued work across restart, and checks the source hash again in each worker. Automated tests cover recovery, ordering, duplicate prevention, report pinning, and FIFO execution.

## Saved-session queue correction — 2026-10-08

The latest verified combined report covers one source session, `20261008T185119Z_Uzawan_XI.json`; it does not establish that the other two sessions in the user's queue ran. The expected behavior is one separate research run and combined report per saved session, processed sequentially.

The source fix is now on main in `tools/surveyor_controller.py` and `tools/test_parallel_research_actions.py`. It persists the FIFO queue across restarts, pins each worker to its triggering session file, verifies the session SHA-256, and rejects completion if the report trigger hash does not match. Regression tests cover queue order, persistence/recovery, session pinning, and stale-report rejection. Local verification: 206 unit tests passed, Python compileall passed, and the harness self-test passed.

The v0.3.66 updater package now includes the queue fix and current indexed extension files. The previous package defects were fixed: Seed Lineage 1.0.3 was added to the managed payload, Runtime-Dispatch tests target 1.0.6, and the truncated test source was repaired. Full Windows end-to-end queue validation remains pending.

## Runtime-A system-scoped root seed capture — 2026-10-08

Probe 0.3.40 closes an active capture and clears live root-seed/caller buffers when the observed nonzero universe address changes. It accepts a root capture into a session only when its capture address matches that session. Seed evidence reports the raw value, UseSeedValue, and effective state separately. The user's system-switch observation and F-pattern remain separate from the parallel-action data; without that run's UseSeedValue field, the F-pattern cannot be classified.

The current main pointer names run `20261008T195817Z-1b73e442` at `research-uploads/20261008T195856Z-parallel-action-test/combined-results.json`; the report SHA-256 `b74d988e78f4001f870980e47776e77ddf3f14f97e5d8cfd4a9fde3c501dcd41` matches the pointer. This was an isolated manual parallel test with an input snapshot and no retained worker data; 8/9 actions completed and the upload action was skipped. The report analyzes saved session `20261008T185119Z_0001550006607CAC`, not a fresh live capture. It reports one root-seed candidate `00C9E8DF0327789E` with `UseSeedValue=true`; derivation remains unproven. `MEDI_FLOATERS`, 146 scene instances, and 14 targets (7 salvage + 7 footlockers) are analysis/prediction results, not an observed physical container count. Keep the separate 43-target `CARGO_FLOATERS` asset prediction (30 + 13 across 164 scenes) distinct from both 14 and all observed counts. The caller extraction decodes `02C08607: FF 52 10` returning at `02C0860A`, but `target_rva_hex` is null. The report's resolver action tests a different callsite (`02C04977` / return `02C0497A`) against stale candidate `00634BC0` and finds zero matches; it does not resolve the `02C08607` target. The report's upstream-callers action cites older session `20261006T223811Z_0001BF0004E84EFD` / seed `5B4AE67D9C2A8F61`; do not join it to the fresh `00C9` event. The separate signature/caller correlation to `0063A6D0` remains distinct evidence and is not inferred from either zero result.

Focused system/seed tests and package integrity checks passed in GitHub Actions. Normal NMS system-switch verification remains pending.

## Runtime-A latest dispatch correction — 2026-10-08

The Oct 8 16:37 combined report remains the sole authority for that run (8 complete, 1 upload skipped, offline saved-evidence analysis, no NMS attach): `research-uploads/20261008T163844Z-parallel-action-test/combined-results.json`, SHA-256 `7eb7c6a62ee5a909d0e0f12df0890ac3653a73fa66ae11f51e0c651dc571994c`. Its raw `logical_entry_rva=00634BC0` field reflects a stale source constant.

The probe registers its hook by `@static_function_hook(signature=...)`; `CURRENT_BUILD_LOGICAL_ENTRY_RVA` is only written into evidence metadata. The user's read-only scan verified the NMS.exe SHA-256 `13d5060d4efb9d2a6a6b1b349bc4257231056cc2a055df4bb15d816262cc3499` and found one signature match at `0063A6D0`. DUNGEON-C's saved static artifact independently records that hook location and the .pdata range `0063A6D0..0063A729`.

The matched 16:31:47.935Z root event records caller return `02C0860A` after `02C08607: FF 52 10`. The unique signature-matched BEFORE hook resolves this event's dispatch destination to `0063A6D0`. Source labels `00634BC0` and `00634C63` were stale and are corrected to `0063A6D0` and `0063A773` in probe 0.3.39. Function semantic identity remains unresolved.

The owner+0x10 zero remains an unresolved after-call capture/data inconsistency, not a target. The separate resolver call `02C04977` is unrelated. The unresolved-preset zero output is not a physical count. The 43-target figure (30 crates + 13 footlockers over 164 scenes) remains a distinct asset-derived prediction, separate from historical 35 and post-update 16 counts. No WinDbg or live NMS action was used.

Review: `agent-patches/runtime-dispatch/RUNTIME_A_HOOK_TARGET_CORRECTION_20261008.md`. Published to `main` in merge commit `373a5e8247823ab5c1a5955d31c70bc25bb610e9` (PR #51); registry now points to extension 1.0.6. The five focused address/evidence assertions were checked against the branch files and all passed; the Python unittest itself was not run because the local command runner is unavailable. Backup: `backup/main-before-runtime-a-signature-correction-20261008-1820` at `7b62524a018c52801084548d21b47b771683cc38`. Workspace state was synced in `ed1c3108661d5ea90636174c122feb89ee2911eb`.

## DUNGEON-C latest combined report and executable call-path review — 2026-10-08

The current main pointer names run `20261008T140207Z-d8e24197` at `research-uploads/20261008T140254Z-parallel-action-test/combined-results.json`; SHA-256 `11ec9ee30687570efda334a255ea27836bfb347d8bf7631ec4ffae981e9175f6` matches the pointer. This combined report is the sole authority for that run: 8 complete, 0 failed, 1 upload skipped; saved-evidence offline processing only, with no new NMS event. Do not use queue or per-action latest files as substitutes.

The provided NMS.exe is a byte-for-byte match for the recorded build (88,560,712 bytes; SHA-256 `13d5060d4efb9d2a6a6b1b349bc4257231056cc2a055df4bb15d816262cc3499`). Its `.pdata` table and code confirm that the saved `0063A706: E8 55 74 DA 02` call reaches a five-byte jump stub at `033E1B60`; that stub (`E9 EB FE FF FF`) jumps to `033E1A50`. Neither address is covered by a listed `.pdata` runtime-function entry; the next entry starts at `033E1B70`. These are static bytes and range-table facts only. The path is not proven to be related to the runtime `02C08607: FF 52 10` dispatch. The zero direct-call-candidate list remains inconsistent with the byte-verified E8 instruction. Detailed hashes and calculations: `agent-patches/dungeon-decompile/CURRENT_HOOK_CALL_TARGET_20261008.json`.

The report’s 43 targets (30 salvage crates + 13 footlockers from 164 resolved scene instances) remain an asset-derived prediction. Keep separate from the historical 35-container measurement and the distinct post-update 16-container user observation. The after-call owner+0x10 zero and separate resolver sample still do not identify the runtime dispatch destination. D-lane offline executable review is complete; runtime target correlation and any live slot capture remain with `agent/runtime-dispatch`. No game launch or traversal was performed.

## Prior DUNGEON-C Oct 8 report reviews — 2026-10-08

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

### Runtime-A debugger recipe (superseded)

The previous WinDbg breakpoint recipe is withdrawn. The user's WinDbg attachment stalled or crashed NMS, and the saved output showed no breakpoint hit or slot capture. Do not repeat it. Runtime-A's only pending user check is the normal Surveyor system-switch validation described above; no debugger is needed.

The captured zero is owner+0x10 after the call, not a pre-call `[RDX+0x10]` target. The signature/caller correlation to `0063A6D0` is separate evidence; the latest combined report's caller decode still has no target RVA, and the `02C04977` resolver sample is unrelated. No further WinDbg capture is requested.

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

Main pointer run `20261008T185304Z-e95aae15` references `research-uploads/20261008T185341Z-parallel-action-test/combined-results.json`, SHA-256 `9576e887375b1d79ad629b07a26209337479ff6cf096222207de4c53a130dcbe`; fetched report bytes match the pointer. This combined report is the sole source used for this parallel run's results. The parallel run was isolated/offline, used an input snapshot, retained no worker data, and marked `research.upload_runtime_capture` `not_run_upload_disabled`.

The generation artifact derives from session `20261008T185119Z_0001550006607CAC`, universe `0001550006607CAC`. It records one root `DUNGEON.SCENE.MBIN` event at `2026-10-08T18:51:04.549Z` with root-seed candidate `00C9E8DF0327789E`; derivation remains unproven. The analyzer infers `MEDI_FLOATERS`, 10 logical rooms and 146 scene instances, and predicts 14 target containers (7 salvage + 7 footlockers) from assets. This is not a physical count and is separate from the earlier `CARGO_FLOATERS` asset-derived 43-target prediction (30 salvage + 13 footlockers).

Seed-Lineage caller output cites older session `20261006T223811Z_0001BF0004E84EFD`; upstream output cites `20261004T151219Z_0001BF0004E84EFD`; seed-function analysis cites `20261002T213047Z_00001A0004E84EFD`. Do not join these offline results to the fresh root event. Static extraction decodes `02C08607: FF 52 10` returning at `02C0860A`, but does not resolve its target. The zero-match resolver sample at `02C04977` / `02C0497A` is a separate callsite.

Next: on shared main Surveyor, close NMS if open, use RUNTIME-A 1.0.6 **Upload captured root event**, then Seed-Lineage 1.0.3 **Extract caller code + upload** and **Extract upstream callers + upload** in order. Verify the caller cites fresh session `20261008T185119Z_0001550006607CAC` and the hash-matched executable, and verify upstream cites that caller. No new NMS launch or traversal is needed if the saved capture remains available. Full lane review: `agent-patches/seed-lineage/SEED_B_PARALLEL_REVIEW_185304_20261008.md`.

## Surveyor source candidate 0.3.64 (2026-10-08)

# NMS Derelict Probe — AI handoff


Windows UI/focus and live end-to-end queue validation remain pending. Source and the v0.3.66 updater package are published on `main`.


## Runtime-A reconciliation and next action — 2026-10-08

The verified current report and callsite/counter caveats are recorded above and in `agent-patches/runtime-dispatch/RUNTIME_A_MANIFEST.json`. The indexed Runtime-A extension remains 1.0.6; its existing panel already separates the `0063A6D0` signature/caller correlation from the zero post-call slot and unrelated resolver sample, so no extension or index hash change was needed. Probe 0.3.40's system-boundary reset is covered by focused tests and package integrity checks in GitHub Actions; the only remaining check is a normal system switch in Surveyor 0.3.67 with Runtime-A 1.0.6. No full derelict traversal or debugger is required. See the lane `STATUS.json` for the exact steps and evidence to return.


## Seed-B reconciliation — current combined run and later lane evidence (2026-10-08 23:36 UTC)

The current parallel pointer references run `20261008T195817Z-1b73e442` at `research-uploads/20261008T195856Z-parallel-action-test/combined-results.json`, SHA-256 `b74d988e78f4001f870980e47776e77ddf3f14f97e5d8cfd4a9fde3c501dcd41` (verified). That isolated report is authoritative for its run: 8 actions completed, 0 failed, upload skipped; fresh caller/session `20261008T185119Z_0001550006607CAC`; the parallel upstream and seed-function actions used an older common snapshot. Later separate caller and upstream uploads at 21:39 UTC hash-verify and cite the fresh session/executable. Upstream reports descriptor +0x128, seed +0x138, use-seed +0x140, seed read before root AddResource; the derivation is still unknown. The all-saved 21:40 seed-function artifact is stale (Oct 2 and old executable hash). The 14 MEDI targets and separate 43 CARGO targets are asset predictions, not physical counts. Zero +0x10 and the separate resolver sample remain unresolved. Current panel 1.0.4 runs caller → upstream → seed-function sequentially. Next human gate is one root event at a third universe address; no full traversal is required. See `agent-patches/seed-lineage/STATUS.json` for steps.
