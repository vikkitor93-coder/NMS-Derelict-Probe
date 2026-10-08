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
