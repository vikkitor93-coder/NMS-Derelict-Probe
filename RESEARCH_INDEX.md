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

- **Measured offline action result from the combined report:** `research.prepare_assets` completed with code 0 against saved session `20261006T223811Z_0001BF0004E84EFD`; 1,441 scene exports were indexed, 1,433 were dungeon scenes, 75 contained target references, and 164/164 saved scene instances resolved. The run did not attach to NMS or upload to GitHub. The attached 13:02 pointer/report live in a user-attached 0.3.62 local candidate and were not published to `main` by Agent D; the current main pointer names a distinct 13:43 run; see `agent-patches/metadata/PARALLEL_ACTION_REVIEW_20261008.json` for source hashes.
- **Asset-derived prediction:** 43 target containers comprise 30 salvage crates and 13 footlockers for those saved instances. This is separate from the historical 35-container measurement and later 16-container user observation. `crate-target-discovery` is diagnostic correlation data, not a physical count.
- **Inference:** `CARGO_FLOATERS` is high-confidence from saved scene family and hazard evidence, and exists among the ten measured static choices. The combined report does not measure which `DungeonOptions` choice the game selected or the meaning of its static 0.33 weight.
- **Analyzer-derived grouping:** the saved report groups the 43 predicted targets into eight CARG logical groups (33 targets), two BARRACKS groups (10), and one END group (0). These 11 groups are not a physical room count and cannot be equated one-for-one with the static `CARGO_FLOATERS` `Rooms=7` parameter or exact room IDs.
- **Unresolved outside Agent D:** zero owner+0x10 reads in one saved caller sample and a separate resolver sample do not identify the current dispatch target. Do not combine those callsites.

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


## Seed-Lineage latest combined report — 2026-10-08 18:53 UTC

- Main pointer run `20261008T185304Z-e95aae15` references `research-uploads/20261008T185341Z-parallel-action-test/combined-results.json`, SHA-256 `9576e887375b1d79ad629b07a26209337479ff6cf096222207de4c53a130dcbe`; hash verified. It is the sole results source for this run. The parallel actions were offline on a saved snapshot; the runtime upload action was disabled.
- The fresh saved session is `20261008T185119Z_0001550006607CAC`, universe `0001550006607CAC`; one root resource event at 18:51:04.549Z contains candidate `00C9E8DF0327789E`. The seed's derivation is unknown. Analyzer inference is `MEDI_FLOATERS`, 10 logical rooms / 146 instances, with 14 asset-predicted targets (7 salvage + 7 footlockers), not an observed count. Keep separate from the previous `CARGO_FLOATERS` asset prediction of 43 (30 salvage + 13 footlockers).
- Caller extraction cites older session `20261006T223811Z_0001BF0004E84EFD`; upstream cites `20261004T151219Z_0001BF0004E84EFD`; seed-function analysis cites `20261002T213047Z_00001A0004E84EFD`. None may be correlated as evidence for the fresh session. Static `FF 52 10` at `02C08607` returns at `02C0860A`; its target is unresolved. The separate zero-match resolver sample at `02C04977` / `02C0497A` is not dispatch evidence.
- Next: upload the saved event via shared-main RUNTIME-A 1.0.6; rerun Seed-Lineage 1.0.3 caller then upstream actions and verify both cite the fresh session and hash-matched executable. No new NMS launch or traversal is required if the saved capture remains available. See Seed-B STATUS.json for the exact request.
