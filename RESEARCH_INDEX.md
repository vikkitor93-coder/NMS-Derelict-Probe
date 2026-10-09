## DUNGEON-C Oct 9 combined-report review — 2026-10-09

The manual pointer-selected report research-uploads/20261009T163702Z-parallel-action-test/combined-results.json (run 20261009T163626Z-9056847b) has verified SHA-256 816587755486c772fa03efbb0461f7983bc196bf149eb90b1588024f6a54f439; it is an isolated offline run with 8 complete, 0 failed, 1 upload skipped, and no fresh NMS event. The separate automatic batch index research-uploads/20261009T163525Z-automatic-research-batch-20261009T163434Z-bf1ed756-3b9b70/batch-results.json verifies as 4ae5af8f6814e14d1e5e16ca1eeeaf455599b1e22d47286ba01e2b513f3f25cd; its per-session report research-uploads/20261009T163525Z-automatic-research-batch-20261009T163434Z-bf1ed756-3b9b70/reports/20261009T163435Z-b91c6dbb/combined-results.json verifies as fb7126c475d65d0e764d802b74ed6a6ca99c56fb72d75c65da9e0e3f6335f1f4 for saved session 20261009T161852Z_Stlepiosc_XIX.json. That separate run has 7 complete, 1 failed, 1 upload skipped. D actions completed in both reports with identical artifact hashes; this is repeated offline processing, not independent runtime evidence.

The exact-caller artifact records descriptor 0000022ADFB4A928, candidate root seed A5047E4E4B68F362, event time 16:18:44.420Z, and 02C08607: FF 52 10 / return 02C0860A for NMS.exe SHA-256 13d5060d4efb9d2a6a6b1b349bc4257231056cc2a055df4bb15d816262cc3499. Its logical-entry metadata says 0063A6D0, while the decoded indirect-call target remains null and no pre-call slot was sampled. The upstream action cites a different older session, and the zero-match resolver is a separate 02C04977 / 02C0497A sample against 00634BC0; neither proves this call's target. The owner+0x10 zero is post-call. Preserve 43 as an asset-derived prediction, separate from observed counts; historical 35 and post-update 16 remain distinct. No WinDbg or live NMS action was used. Full review: agent-patches/dungeon-decompile/PARALLEL_REVIEW_20261009.json.

## Seed-Lineage latest automatic report and runtime capture — 2026-10-09

The current automatic pointer verifies for batch `20261009T161519Z-fdc03736`; report `20261009T161520Z-7233c462` SHA-256 is `35e403f79d6e3c665a36f74eee13928dc5a9d77036278604efb1039143076e55`. Its one-observation root candidate `0001680006607CAC -> 2139770A2614E3DC` has no executable identity. The combined caller, upstream, and seed-function artifacts still cite the previous 000155 session; exact-root static extraction separately matches runtime return `02C0860A` in NMS.exe SHA `13d506...`. A newer runtime-only/all-saved capture at `00006D0006606CAB -> A5047E4E4B68F362` has the same dynamic caller offset, zero `+0x10`, and no executable hash; it is not part of that combined report. The 14 MEDI and 43 CARGO target values remain asset predictions, not physical counts; dispatch remains unresolved. The 1.0.5 extension exposes sequential caller, upstream, and seed-function actions.

## Automatic multi-session batches

For queued saved-session research, `research/LATEST_AUTOMATIC_RESEARCH_BATCH.json` points to a SHA-256-verified batch index. The index names each saved-session hash and its own immutable `combined-results.json` report. Compare sessions only as distinct cohorts and verify each report hash before citing it. The local PC mirror is `<project>/research-output/automatic-session-batches/<batch-id>/`; cloud lane agents use the GitHub pointer because they cannot access that device folder directly. The older `research/LATEST_PARALLEL_ACTION_TEST.json` continues to identify a single manual parallel run.

## Surveyor background research stays in the app — 2026-10-09

Automatic research sets `NMSDS_NONINTERACTIVE=1`. Both Python caller extractors now honor it and skip Explorer selection, preventing folder windows from opening during the saved-session backlog or parallel research. Direct interactive command runs still open the output location. Regression: `tests.test_tools.ToolTests.test_background_caller_extractions_do_not_open_explorer`.

## METADATA-D room-group reconciliation — 2026-10-08

Current pointer/report SHA-256 `b74d988e78f4001f870980e47776e77ddf3f14f97e5d8cfd4a9fde3c501dcd41` verifies for run `20261008T195817Z-1b73e442`: offline manual-button analysis of saved session `20261008T185119Z_0001550006607CAC`, not fresh live capture. MEDI_FLOATERS has 10 parent-key groups vs static `Rooms=7`; 14 targets are predicted, not observed. Historical CARGO run `20261008T140207Z-d8e24197` has 8 CARG + 2 BARRACKS + 1 END parent groups (11 total) and 43 asset-predicted targets (30 + 13), not an observed count.

CARGO_FLOATERS static rules: `Rooms=7`; five main IDs and two branch IDs; exactly one each `R_FLO_BARR`, `R_S_FLO_BARR`, and `R_END`, with END minimum index 6. Counts/family labels do not map parent-key groups to IDs. DUNGEON-C's separately recorded 11-room traverse supplies no per-room crosswalk. The current 7-versus-11/10 semantics remain unresolved. Details: `agent-patches/metadata/ROOM_MODEL_RECONCILIATION_20261008.json`.

## Startup recovery of unprocessed saved sessions — 2026-10-08

Surveyor 0.3.67 scans saved session JSON files at startup, queues those without a matching persisted queue record or exact-hash automatic report, and skips files already represented by a prior report. This backfills sessions queued by pre-0.3.66 builds. Each recovered file still gets a separate FIFO run/report.

## Surveyor saved-session queue — 2026-10-08

The 19:10 queue-specific combined report named one input session; it did not prove all three queued sessions ran. The later 19:58 manual parallel report is a separate saved-session analysis and does not establish that the FIFO drained. Surveyor 0.3.66 now queues each saved file separately, persists the FIFO across restarts, pins each worker to its triggering session SHA-256, and requires a matching trigger hash before recording completion. Local regression suite and package integrity checks passed; Windows end-to-end validation is pending.

## Runtime-A system-scoped root seed capture — 2026-10-08

The user's system-switch observation and F-pattern seed are separate from the latest parallel-action report. Main's current pointer names the sole authoritative 19:58 report for its run: `research-uploads/20261008T195856Z-parallel-action-test/combined-results.json` (run `20261008T195817Z-1b73e442`; SHA-256 `b74d988e78f4001f870980e47776e77ddf3f14f97e5d8cfd4a9fde3c501dcd41`, verified). It is an isolated offline analysis of saved session `20261008T185119Z_0001550006607CAC`; upload was skipped and worker data was not retained. It records root-seed candidate `00C9E8DF0327789E` with UseSeedValue=true, one observation, derivation unproven. MEDI_FLOATERS has 146 scene instances and predicts 14 targets (7+7); this is not an observed count. Keep it separate from the CARGO_FLOATERS asset-derived 43-target prediction (30+13 across 164 scenes). The caller extraction has target_rva_hex=null for `02C08607: FF 52 10` / return `02C0860A`. The separate zero-match resolver is `02C04977` / return `02C0497A` against candidate `00634BC0`; it does not resolve the target. The combined report's upstream action cites an older session and must not be joined to the fresh root candidate.

Probe 0.3.40 clears live root/caller buffers at a changed nonzero universe address and reports raw seed separately from UseSeedValue/effective state. Normal NMS system-switch validation remains pending.
## Runtime-A latest dispatch correction — 2026-10-08

The Oct 8 16:37 combined report remains the sole authority for that run (8 complete, 1 upload skipped, offline saved-evidence analysis, no NMS attach): `research-uploads/20261008T163844Z-parallel-action-test/combined-results.json`, SHA-256 `7eb7c6a62ee5a909d0e0f12df0890ac3653a73fa66ae11f51e0c651dc571994c`. Its raw `logical_entry_rva=00634BC0` field reflects a stale source constant.

The probe registers its hook by `@static_function_hook(signature=...)`; `CURRENT_BUILD_LOGICAL_ENTRY_RVA` is only written into evidence metadata. The user's read-only scan verified the NMS.exe SHA-256 `13d5060d4efb9d2a6a6b1b349bc4257231056cc2a055df4bb15d816262cc3499` and found one signature match at `0063A6D0`. DUNGEON-C's saved static artifact independently records that hook location and the .pdata range `0063A6D0..0063A729`.

The matched 16:31:47.935Z root event records caller return `02C0860A` after `02C08607: FF 52 10`. The unique signature-matched BEFORE hook resolves this event's dispatch destination to `0063A6D0`. Source labels `00634BC0` and `00634C63` were stale and are corrected to `0063A6D0` and `0063A773` in probe 0.3.39. Function semantic identity remains unresolved.

The owner+0x10 zero remains an unresolved after-call capture/data inconsistency, not a target. The separate resolver call `02C04977` is unrelated. The unresolved-preset zero output is not a physical count. The 43-target figure (30 crates + 13 footlockers over 164 scenes) remains a distinct asset-derived prediction, separate from historical 35 and post-update 16 counts. No WinDbg or live NMS action was used.

Review: `agent-patches/runtime-dispatch/RUNTIME_A_HOOK_TARGET_CORRECTION_20261008.md`. Focused regression test `tests.test_runtime_hook_address_labels` is pending local run.

## DUNGEON-C latest combined report and executable call-path review (2026-10-08)

- **Pointer provenance:** `research/LATEST_PARALLEL_ACTION_TEST.json` names run `20261008T140207Z-d8e24197` and report `research-uploads/20261008T140254Z-parallel-action-test/combined-results.json`. Report SHA-256 `11ec9ee30687570efda334a255ea27836bfb347d8bf7631ec4ffae981e9175f6` matches the pointer. That combined report alone is authoritative for the run: 8 complete, 0 failed, 1 upload skipped; offline saved-evidence processing and no new NMS event.

- **Measured static bytes:** matching NMS.exe SHA-256 `13d5060d4efb9d2a6a6b1b349bc4257231056cc2a055df4bb15d816262cc3499` confirms the saved call at `0063A706` reaches stub `033E1B60`, whose `E9 EB FE FF FF` tail jump reaches `033E1A50`. Neither address is covered by a `.pdata` runtime-function range; the next listed range begins at `033E1B70`. This is a static call path only and is not proof of the runtime `02C08607: FF 52 10` target. See `agent-patches/dungeon-decompile/CURRENT_HOOK_CALL_TARGET_20261008.json`.

- **Unresolved exporter detail:** the 89-byte hook body contains the E8 rel32 call, although its saved `direct_call_candidates` list is empty. Cause remains unknown.

- **Limits:** the 43 targets (30 salvage + 13 footlockers) remain an asset-derived prediction for 164 resolved scene instances, separate from the historical 35-container count and distinct post-update 16-container observation. The after-call owner+0x10 zero and separate resolver sample do not resolve dispatch. No game launch or traversal occurred. Runtime target capture remains with `agent/runtime-dispatch`.

## Seed-B review of main's 14:02 combined report (2026-10-08)

- **Saved root event:** session `20261008T140041Z_0001BF0004E84EFD` records the 14:00:37Z root resource event, descriptor `0000021C2457DD28`, seed candidate `5B4AE67D9C2A8F61`, and direct Engine caller `0063AC20` -> `0183E770`. The same saved trace records logical entry `02C08607: FF 52 10`, returning at `02C0860A`; both owner+0x10 reads are after-call zeros. The indirect dispatch target is unresolved.
- **Asset prediction:** CARGO_FLOATERS is inferred at high confidence; 11 logical chunks and 164 scene instances yield an asset-derived prediction of 43 target containers (30 salvage, 13 footlockers), not a physical count.
- **Seed boundary:** the POI description raw argument matches universe address `0001BF0004E84EFD`; the description return matches the POI component address, not the universe address or dungeon-root seed. The root seed remains a candidate; its derivation and constructor identity are unproven.
- **Provenance:** main pointer `research/LATEST_PARALLEL_ACTION_TEST.json` names run `20261008T140207Z-d8e24197`, report SHA-256 `11ec9ee30687570efda334a255ea27836bfb347d8bf7631ec4ffae981e9175f6`. Eight actions reanalyzed saved evidence offline; upload was skipped. Caller and upstream results in that report use older saved sessions, so do not join them to the 14:00:37Z event as one runtime trace.
- **Next:** on the shared main Surveyor, capture a fresh root event, run Seed-Lineage extension 1.0.3 actions Extract caller code then Extract upstream callers, and return both evidence manifests. No traversal is required. Full review: `agent-patches/seed-lineage/SEED_B_PARALLEL_REVIEW_140207_20261008.md`.

## DUNGEON-C parallel report review (2026-10-08)

- **Source and provenance:** The user-provided local 0.3.62 candidate contained pointer research/LATEST_PARALLEL_ACTION_TEST.json and combined report research/parallel-action-tests/20261008T130233Z-755d4c43/combined-results.json. Pointer SHA-256 matched the report bytes: 12035c7362e77363af084bc24254c7b013edecba6ca9015f1d3c6985ea527eda. The candidate and shared report were not published or modified by DUNGEON-C. The combined report is the sole authority for the Oct 8 action results: 8 offline actions completed, upload skipped, no NMS session or new event.
- **Published update:** After the attached 13:02 candidate report, main published a separate 13:43 combined report at research-uploads/20261008T134355Z-parallel-action-test/combined-results.json (SHA-256 3af46d71fbeabc5810f3c83dbdd93b59cc2cfd71358dbaa6bb9c35c398e38592). Its hash matches the later main pointer. The two combined reports are kept as separate runs and each is authoritative only for its own action results.
- **Measured from the report:** the exact-caller extraction decodes 02C08607: FF 52 10, returning at 02C0860A, for executable SHA-256 13d5060d4efb9d2a6a6b1b349bc4257231056cc2a055df4bb15d816262cc3499. This does not resolve the indirect dispatch target. The resolver used a different saved callsite, 02C04977 / return 02C0497A, against candidate 00634BC0; zero offline matches there do not establish the current dispatch destination.
- **Static byte recheck:** in the existing 89-byte, SHA-256-verified hook body at 0063A6D0, 0063A706 contains E8 55 74 DA 02, which calculates to relative-call destination 033E1B60; the following bytes compare RAX with RBX and conditionally branch. This is a byte-derived destination only. The saved export reports zero direct-call candidates despite this instruction; that discrepancy remains unresolved. The destination's .pdata boundary and body have not been checked against the matching executable.
- **Count and dispatch limits:** 43 (= 30 Salvage + 13 Footlockers) is the asset-derived prediction for 164 scene instances, not a fresh physical count. Preserve the historical 35-container measurement and separate post-update 16-container user observation. The owner+0x10 zero is after-call and not the pre-call virtual slot; the separate resolver sample is not dispatch proof.
- **Next:** provide NMS.exe with the recorded SHA-256, or an equivalent hash-matched .pdata and bounded-code export for RVA 033E1B60. No NMS launch or traversal is needed.
- Full review and field-level evidence are in agent-patches/dungeon-decompile/PARALLEL_REVIEW_20261008.json.
# NMS Derelict Probe — Research Index

## Agent D review of attached parallel-action report (2026-10-08)

- **Latest combined report and capture provenance:** GitHub main points to `research-uploads/20261008T140254Z-parallel-action-test/combined-results.json` for run `20261008T140207Z-d8e24197`; its SHA-256 verifies as `11ec9ee30687570efda334a255ea27836bfb347d8bf7631ec4ffae981e9175f6`. The parallel actions ran offline on saved evidence that includes capture session `20261008T140041Z_0001BF0004E84EFD` and a root event at `2026-10-08T14:00:37.544Z`. The attached 13:02 candidate report remains historical provenance, not the latest report.
- **Asset-derived prediction:** scene preparation resolves 164/164 instances and predicts 43 target containers (30 salvage crates + 13 footlockers). This is not a physical count and remains separate from historical counts 35 and 16.
- **Analyzer/static discrepancy:** high-confidence `CARGO_FLOATERS` inference is not direct observation of a selected option. The report groups captured scenes under `Room 0`–`Room 10`: 11 main groups versus static `Rooms=7`. The final END group at index 10 meets static `R_END` minimum index 6, while the total mismatch remains unexplained. The two BARRACKS groups are compatible with the two one-count static BARRACKS rules but do not identify those exact room IDs; eight CARG groups remain unexplained. The model is `needs-review`, manual room markers are zero, and earlier 0.3.62 regression fixtures assert seven main rooms for historical 51- and 35-target cases.
- **Dispatch boundary:** zero owner `+0x10` value at the exact caller and zero candidates from a separate resolver callsite do not resolve the dispatch target. Keep runtime/decompile conclusions in their owning lanes.
- Full provenance and artifact hashes: `agent-patches/metadata/PARALLEL_ACTION_REVIEW_20261008.json`.
## Seed-B combined-report review — 2026-10-08

Seed-B verified the user-attached 0.3.62 local candidate's `research/LATEST_PARALLEL_ACTION_TEST.json` against its combined report (SHA-256 `12035c7362e77363af084bc24254c7b013edecba6ca9015f1d3c6985ea527eda`). The report is not published here. It is the sole source for the October 8 parallel run: eight offline saved-evidence actions completed, one upload disabled, no new NMS event. Source sessions differ across generation/asset, seed-function, and upstream analysis. The 43 target containers are an asset-derived prediction (30 salvage crates + 13 footlockers), separate from historical observed 35 and post-update user-observed 16. The saved exact caller is `02C08607: FF 52 10`, return `02C0860A`; the zero owner `+0x10` read is not a pre-call slot target. The resolver's zero-match result comes from another caller sample (`02C04977`) and does not resolve current dispatch. See `agent-patches/seed-lineage/SEED_B_PARALLEL_REVIEW_20261008.md` for provenance, static constructor trace, and limitations. Root seed derivation remains unproven. No new extension or runtime behavior is published.

Last updated: 2026-10-08. This file is the short shared truth table for humans and parallel AI agents.

## Agent D static abandoned-freighter map (2026-10-07)

- **Measured from installed game assets:** `DungeonRootScene` points to a scene with one `GeneratedBaseRoot` locator, whose attachment entity has gravity-volume and static-physics components. Neither the scene nor its direct attachment names a dungeon room scene. Ten preset main/branch room ID lists are recorded in `agent-patches/metadata/STATIC_ROOT_SCENE_TRACE_20261007.json`; mapping those IDs to actual runtime room scenes remains open.

- **Measured from installed game assets:** the active `MODELS/SPACE/POI/PARTS/DUNGEON_ENTRANCE/ENTITIES/DUNGEONENTRANCE.ENTITY.MBIN` has `GcAbandonedFreighterComponentData`, ten weighted `DungeonOptions`, and `GcOutpostComponentData.AbandonedFreighter=true`. Its SHA-256 is `7ae4acec4521f5e8347b9d61514cf59dae7a24e722a7058a1126beb999b243e8`.
- **Measured from installed game assets:** all ten option names match the ten current `FREIGHTERDUNGEONSTABLE.MBIN` presets. Each MEDI and CARGO set has TURRETS 0.66, FLOATERS 0.33, BUGS 1.00, SLIME 0.25, and MAZE 0.15. MAZE presets specify four rooms; the other eight specify seven. See `agent-patches/metadata/CURRENT_DUNGEON_OPTIONS_20261007.json`.
- **Measured from installed game assets:** the component's `DungeonRootScene.Filename` is `MODELS/PLANETS/BIOMES/COMMON/BUILDINGS/PARTS/BUILDABLEPARTS/SPACEBASE/GENERATEDBASEROOT.SCENE.MBIN`. The similarly named spacecraft entrance entity has an empty options list and `AbandonedFreighter=false`.
- **Unproven:** runtime choice probabilities, normalization, seed input, selection frequency, and whether this static root field resolves to the observed runtime `MODELS/SPACE/POI/DUNGEON.SCENE.MBIN` through intervening calls.

## Seed-lineage capture consistency (2026-10-01)

- **Measured:** caller and upstream evidence both show universe `00001A0004E84EFD`, root seed `9256392A2F5A74AC`, and call RVA `00635110`.
- **Measured:** caller session `20260930T030805Z_00001A0004E84EFD` and upstream session `20260929T203022Z_00001A0004E84EFD` differ. Caller NMS.exe hash is `671de22649274b49fa07f5a246bc7252c4e08bb9ab623d2e65722fbab4e497a4`; upstream hash is `b7913f268dfc62386b6b68f524bfc8ade4a44a9f4fbad39085b7bf51be3680cb`. Caller evidence says `baseline_window_matches_exe: false`.
- **Measured:** rerunning the current boundary detector against the attached caller evidence raises `No compiler-padding function boundary found before the call`.
- **Inference:** the upstream candidate `00634BC0` is not validated for this caller window; do not use it as a current boundary.
- **Hypothesis:** evidence was captured across a running-process/executable change or otherwise mixed across states. A fresh post-relaunch capture is needed to verify.
- **Next:** relaunch NMS from the installed executable, capture one root resource event at the known system, run **Extract caller code + upload**, and verify `baseline_window_matches_exe` before rerunning upstream analysis. No full traversal is required.

## Confirmed runtime facts

- Known baseline universe address: `00001A0004E84EFD` (reality index 0; system index 26; voxel `-259, 4, -380`).
- Root resource: `MODELS/SPACE/POI/DUNGEON.SCENE.MBIN`.
- Root descriptor seed: `9256392A2F5A74AC`.
- Logical shared entry: `NMS.exe + 00634BC0`.
- Exact external root-path return RVA: `02BFCC1A`.
- Call instruction: `02BFCC17: FF 52 10` -> `call qword ptr [RDX+0x10]`.
- Runtime owner pointer in the baseline capture: `0000017475826C00`.
- Runtime descriptor pointer: `0000017475826D28` = owner + `0x128`.
- Primary/secondary captured seeds: `9256392A2F5A74AC` / `FFFFFFFFFFFFFFFF`.
- Offline static resolver found no coherent conventional static vtable candidate for `00634BC0`.

## Confirmed public structure/algorithm facts

- `cTkResourceDescriptor`: descriptors vector at `+0x0`, primary seed at `+0x10`, secondary seed at `+0x20` in current NMS.py definitions.
- `cGcAbandonedFreighterComponentData`: `DungeonRootScene` + weighted `DungeonOptions`.
- `cGcFreighterDungeonChoice`: preset `Name` + `Weighting`.
- `cGcDungeonGenerationParams`: map size, entrance, room count, directional probabilities, straight multiplier, main/branch room types, quests, generation/pruning rules.
- The project already parses current `FREIGHTERDUNGEONSTABLE.MBIN` data; reuse it.
- A public disassembly-derived address->system-seed implementation produces system seed `B006BAB6` for the baseline address. Relation to the derelict root seed remains unproven.

## Hypotheses / open links

1. Classify the unknown runtime owner/dispatch object and resolve `[owner+0x10]` live.
2. Identify the weighted `DungeonOptions` selection boundary and the RNG/seed input used there.
3. Locate the runtime function that consumes `GcDungeonGenerationParams`.
4. Trace system/POI state to root descriptor seed `9256392A2F5A74AC`.
5. Once the generator entry is safe and understood, adapt the Pi pattern to call it repeatedly without gameplay.

## Explicitly disproven / downgraded

- Do not call the `owner+0x10` structure a proven static C++ vtable. Static vtable search returned no coherent candidate.
- Do not identify `owner` as a normal `cTkResource`; public/current `cTkResource` layout places its embedded descriptor elsewhere than `owner+0x128`.
- Do not treat ReNMS general WFC/freighter-base `cGcMap` as the abandoned-derelict generator without direct evidence.
- Do not claim the system-seed -> derelict-root-seed formula is solved.

## Evidence rule

Every conclusion must be tagged mentally as **measured**, **public-structure confirmed**, **inferred**, or **hypothesis**. Never promote an inference to measured fact merely because it fits the current model.

\n


## Seed-B review of latest combined report (2026-10-08 18:53 UTC)

Main pointer run `20261008T185304Z-e95aae15` references `research-uploads/20261008T185341Z-parallel-action-test/combined-results.json`, SHA-256 `9576e887375b1d79ad629b07a26209337479ff6cf096222207de4c53a130dcbe`; fetched report bytes match the pointer. This combined report is the sole source used for this parallel run's results. The parallel run was isolated/offline, used an input snapshot, retained no worker data, and marked `research.upload_runtime_capture` `not_run_upload_disabled`.

The generation artifact derives from session `20261008T185119Z_0001550006607CAC`, universe `0001550006607CAC`. It records one root `DUNGEON.SCENE.MBIN` event at `2026-10-08T18:51:04.549Z` with root-seed candidate `00C9E8DF0327789E`; derivation remains unproven. The analyzer infers `MEDI_FLOATERS`, 10 logical rooms and 146 scene instances, and predicts 14 target containers (7 salvage + 7 footlockers) from assets. This is not a physical count and is separate from the earlier `CARGO_FLOATERS` asset-derived 43-target prediction (30 salvage + 13 footlockers).

Seed-Lineage caller output cites older session `20261006T223811Z_0001BF0004E84EFD`; upstream output cites `20261004T151219Z_0001BF0004E84EFD`; seed-function analysis cites `20261002T213047Z_00001A0004E84EFD`. Do not join these offline results to the fresh root event. Static extraction decodes `02C08607: FF 52 10` returning at `02C0860A`, but does not resolve its target. The zero-match resolver sample at `02C04977` / `02C0497A` is a separate callsite.

Next: on shared main Surveyor, close NMS if open, use RUNTIME-A 1.0.6 **Upload captured root event**, then Seed-Lineage 1.0.3 **Extract caller code + upload** and **Extract upstream callers + upload** in order. Verify the caller cites fresh session `20261008T185119Z_0001550006607CAC` and the hash-matched executable, and verify upstream cites that caller. No new NMS launch or traversal is needed if the saved capture remains available. Full lane review: `agent-patches/seed-lineage/SEED_B_PARALLEL_REVIEW_185304_20261008.md`.


## Seed-B current evidence reconciliation (2026-10-08 23:36 UTC)

Main combined report `research-uploads/20261008T195856Z-parallel-action-test/combined-results.json` for run `20261008T195817Z-1b73e442` hash-verifies (`b74d988e78f4001f870980e47776e77ddf3f14f97e5d8cfd4a9fde3c501dcd41`). It remains the sole authority for that isolated parallel run: fresh root/caller session `20261008T185119Z_0001550006607CAC`; upstream and seed-function outputs were from the harness's independent old snapshots. Later lane-exclusive caller and upstream evidence uploads at 21:39 UTC each hash-verify and cite the same fresh session and executable `13d5060d4efb9d2a6a6b1b349bc4257231056cc2a055df4bb15d816262cc3499`. Upstream static evidence places descriptor at argument +0x128, primary seed at +0x138 (descriptor +0x10), and reads it before root AddResource; derivation remains unknown. The 21:40 all-saved seed-function analysis is stale (Oct 2 session and executable hash 671de...). Fourteen MEDI_FLOATERS targets are asset-predicted, not observed; the 43-target CARGO_FLOATERS figure remains a separate asset-derived prediction. Zero +0x10 and unrelated resolver sample do not resolve dispatch. A third distinct address/root-seed sample is needed; full traversal is unnecessary.

## METADATA-D uploaded archive review — 2026-10-09

The uploaded `dungeon.zip` is on main at blob `ce8ca51535db34165cd72477ab7b9ae9c94a86fa` (9,733,369 bytes; SHA-256 `5ef8b70e92e8923ce8dac3c96c055f52841dc831516bbb35f976b8c265196c60`). All 2,866 file entries, including binary files, were read and searched for ASCII/UTF-16 `R_*`/`B_*` room IDs and `RoomId`, `DungeonOptions`, or `DungeonRootScene` fields; there were no matches. The ZIP contains scene/model assets but no scene-to-static-RoomId crosswalk. Full record: `agent-patches/metadata/DUNGEON_ZIP_ROOM_ID_REVIEW_20261009.json`.

The current pointer's sole authoritative report for run `20261009T004054Z-9fedea65` is `research-uploads/20261009T004133Z-parallel-action-test/combined-results.json` (SHA-256 `af6166966fb37b738d9a584103275a10f28d1d39e6e39f23181e63a4beacd972`, verified). It is isolated automatic analysis of saved session `20261008T184737Z_Uzawan_XI.json`; upload was disabled and worker data was not retained. It reports MEDI_FLOATERS, 10 analyzer groups, 146 scene instances, `needs-review`, zero manual room markers, and 14 asset-predicted targets (7+7), not a fresh capture or observed physical count. Keep the historical CARGO result separate: 8 CARG + 2 BARRACKS + 1 END analyzer parent groups (11 total), with 43 asset-derived predictions across 164 resolved scenes, not observed. Static CARGO_FLOATERS remains `Rooms=7`; the 7-versus-11/10 relationship is unresolved.


## METADATA-D repository-wide crosswalk search — 2026-10-09

Searched all 137 fetched remote refs under `agent-patches/dungeon-decompile/` and `agent-patches/metadata/`. The only three unique files containing both room-ID and scene-path terms are explanatory notes (`METADATA_D_20261007_MANIFEST.json`, `ROOM_MODEL_RECONCILIATION_20261008.json`, and `STATIC_ROOT_SCENE_TRACE_20261007.json`); none maps a room ID to a scene. Also checked all 55 room-crate-index files on main: each records `scene_path` and crate/footlocker counts but no dungeon `RoomId` (the `id_*_refs` fields refer to entity references). All 51 main dungeon-generation-table exports contain static room IDs but no scene path. The two evidence sets have no join key. Details: `agent-patches/metadata/DUNGEON_ZIP_ROOM_ID_REVIEW_20261009.json`.

The remaining request is a separate source artifact explicitly pairing a generated scene path with a static `R_*`/`B_*` room ID. The supplied `dungeon.zip` does not contain it. No Surveyor action or full traversal is required.


## METADATA-D final repository record-pair check — 2026-10-09

A recursive same-record check covered 97 main JSON files under `agent-patches/dungeon-decompile/`, `agent-patches/metadata/`, and `research-uploads/` that mention both room-ID and scene-path terms. Zero records paired a `RoomId` field with a scene path or `.SCENE.MBIN` value. Together with the prior archive, all-ref, room-crate-index, and generation-table checks, this confirms there is no existing repository artifact for the user to locate. New source evidence is needed to continue the scene-to-static-ID comparison; no Surveyor action sequence is established and no full traversal is required. Detailed method and scope: `agent-patches/metadata/DUNGEON_ZIP_ROOM_ID_REVIEW_20261009.json`.


## Seed-Lineage automatic session 20261009T015909Z-77532ce2

Verified batch `20261009T015908Z-d4d6ae3f` SHA-256 `b1ea5afaee7aa2f6d2a49bd48c28b73a67d59a9aad3f6b53702d41fe2b0ea18a`; its session report SHA-256 is `721427df0b4d95a3bb0cfee5ececa3fdb5517713c0abd998fca4802e3ced994b`. The report has a third address/root candidate `0001680006607CAC -> 2139770A2614E3DC` from one saved-session observation; its executable hash is not present. Seed-Lineage caller and seed-function outputs in that report still cite `20261008T185119Z_0001550006607CAC`; a fresh chain for the third address is not present. Do not claim a derivation formula. The 14 MEDI_FLOATERS and 43 CARGO_FLOATERS figures are asset-derived predictions, not physical counts. The separate zero `+0x10` read and resolver sample do not identify the dispatch target.

The screenshot's `Invalid extension panel summary` is explained by published panel 1.0.4's 635-character summary exceeding the host's 500-character limit. Corrected panel 1.0.5 (432 characters), manifest, index update, and regression change are in ready request `build-requests/seed-lineage/seed-panel-summary-limit-20261009/`; integration and the full current source ZIP remain the primary compiler's work. See `agent-patches/seed-lineage/SEED_B_PANEL_FIX_AND_AUTO_BATCH_20261009.md`.

- Seed-Lineage public address system-seed comparison: `agent-patches/seed-lineage/SEED_B_SYSTEM_SEED_COMPARISON_20261009.md` (two known anchors reproduced; third address yields `8A6EF089`; root derivation remains unknown).


## Seed-Lineage latest automatic batch — 2026-10-09

# Seed-Lineage review — 2026-10-09 automatic session report 20261009T163435Z-b91c6dbb

The current automatic pointer names batch `20261009T163434Z-bf1ed756`. Its batch index at `research-uploads/20261009T163525Z-automatic-research-batch-20261009T163434Z-bf1ed756-3b9b70/batch-results.json` has SHA-256 `4ae5af8f6814e14d1e5e16ca1eeeaf455599b1e22d47286ba01e2b513f3f25cd`. The index names this report at `research-uploads/20261009T163525Z-automatic-research-batch-20261009T163434Z-bf1ed756-3b9b70/reports/20261009T163435Z-b91c6dbb/combined-results.json`, SHA-256 `fb7126c475d65d0e764d802b74ed6a6ca99c56fb72d75c65da9e0e3f6335f1f4`, input session SHA-256 `15c10763f0a5df6c3b7caec8b9ed771361d806912a1fb74c43b249f5c676e23a`. Fetched content hashes match pointer/index. Use this combined report as the sole authoritative source for this saved-session run. Provenance: automatic_saved_session, isolated_parallel_test_no_github_upload, input snapshot available, worker data not retained; 7 complete, 1 failed, 1 upload skipped. The failed action was Metadata-D prepare_assets, not Seed-Lineage.

Fresh generation baseline: session `20261009T161852Z_00006D0006606CAB`, address `00006D0006606CAB`, root candidate `A5047E4E4B68F362`, artifact SHA-256 `a950ddd7d2bf56c8a62ea5b26dee0ca0c40e51432ccb67a9d7a5f7b70dec32b7`. It reports 9 logical chunks and 130 scene instances. Its 21 target containers (12 salvage + 9 footlockers) are derived predictions, not physically observed counts. The caller, upstream, and seed-function outputs do not use this fresh sample; they are not a same-sample chain.

The historical 43 CARGO targets remain a separate asset-derived prediction. Neither 21 nor 43 is an observed count. Root derivation remains unknown. Zero `+0x10` and the separate resolver sample do not identify a resolved dispatch target.

Seed-B 1.0.6 adds an ordered refresh-first action list: analyze generation, extract caller, extract upstream callers, analyze seed function. Button ordering is a user sequence, not an enforced dependency; verify each output references the preceding artifact. Static panel/index/action/hash checks were completed. Python unittest was not run because the local execution helper could not start. One short local Agent Console action sequence is required; no NMS launch or full traversal is required.


## DUNGEON-C current-build runtime/callback context (2026-10-09)

Two standalone runtime captures at 23:05:09.625Z and 23:08:33.349Z report unique descriptor/caller-return correlation to effective entry 0063A6D0. This is event-scoped correlation; raw `[RDX+0x10]` dispatch slot and callback semantic identity remain unresolved. Local hash-matched static review confirms caller `02C08607: FF 52 10` and a contiguous 1180-byte callback path across `.pdata` ranges `0063A6D0..0063A729` and `0063A729..0063AB6C`. Review: `agent-patches/dungeon-decompile/CURRENT_BUILD_CALLER_CONTEXT_20261009.json` (SHA-256 `d5be5c47d5532927e7154e91d55bffc51c3c16bc7dd24f6b1d793d3e4dec68e6`). Keep the 43-target asset prediction separate from observed counts; historical 35 and post-update 16 remain distinct.


DUNGEON-C 23:14 snapshot addendum: `research-uploads/20261009T231425Z-all-saved-evidence-a8f14cf4/` contains the already-reviewed 23:08 runtime event (artifact SHA-256 `eecced17a13f026a7f42eadd9969892504310eba4a66ea81a24f0b99de07b12d`), not an additional event. It reports 52 static direct references to entry 0063A6D0 and recursive return 0063A773. The `+0x10` value was captured after the external call and does not identify its destination.
