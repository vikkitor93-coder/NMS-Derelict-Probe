# Seed-B reconciliation: latest combined and lane-exclusive evidence (2026-10-08)

## Parallel report — sole authority for the 19:58 run

Main pointer names run `20261008T195817Z-1b73e442`, report `research-uploads/20261008T195856Z-parallel-action-test/combined-results.json`, SHA-256 `b74d988e78f4001f870980e47776e77ddf3f14f97e5d8cfd4a9fde3c501dcd41`. The report bytes were fetched and the SHA-256 matched the pointer. Run mode was `isolated_parallel_test_no_github_upload`; trigger was manual; 8 actions completed, 0 failed, 1 upload skipped; worker data was not retained.

The combined report's generation artifact and caller-code action cite session `20261008T185119Z_0001550006607CAC`, universe `0001550006607CAC`, root-seed candidate `00C9E8DF0327789E`, call RVA `0063AC20` targeting `0183E770`, NMS.exe SHA-256 `13d5060d4efb9d2a6a6b1b349bc4257231056cc2a055df4bb15d816262cc3499`, and `baseline_window_matches_exe=true`. Root-seed derivation remains unknown.

The same combined report's upstream-scan and seed-function actions cite older session `20261006T223811Z_0001BF0004E84EFD`; they are not fresh capture correlations. This is explained by `tools/test_parallel_research_actions.py`: each action gets an isolated copy of the common starting snapshot, and actions run concurrently. An upstream action therefore cannot consume a caller artifact newly produced by its sibling in that run. The report remains authoritative for that parallel run; its stale input provenance is preserved rather than overwritten.

Generation analysis infers `MEDI_FLOATERS`, 10 logical rooms, and 146 scene instances; 14 targets (7 salvage + 7 footlockers) are asset-predicted, not observed. Keep this distinct from the separate CARGO_FLOATERS asset-derived 43-target prediction (30 salvage + 13 footlockers). Neither prediction is a physical count. The zero `+0x10` value and separate resolver sample do not identify a dispatch target.

## Later lane-exclusive uploads — separate evidence chain

After the combined run, Seed-Lineage uploaded caller evidence at `research-uploads/20261008T213906Z-seed-lineage-extract-caller-b7822170/` and upstream evidence at `research-uploads/20261008T213956Z-seed-lineage-extract-upstream-40576b80/`. Both run-manifest SHA-256 values were checked against the raw uploaded JSON: caller `83ba43c47011c7c455b2cb079a210f9aaae2b9a6436a6ee408c233e63af5eee9`; upstream `8e66960e4483fa6656f25ba91148322f774eba220dd41246c529d18f227db941`. Both cite session `20261008T185119Z_0001550006607CAC`, universe `0001550006607CAC`, the same candidate seed and NMS.exe SHA-256; upstream explicitly cites the caller evidence and root call RVA `0063AC20`.

The fresh upstream scan identifies a logical-function-entry candidate at `0063A6D0`, 52 direct rel32 references, second-argument copy to RSI at `0063A6F1`, descriptor at second-argument +`0x128`, primary seed at +`0x138` (descriptor +`0x10`) read at `0063A8CE`, and use-seed flag at +`0x140` (descriptor +`0x18`) checked at `0063A936`, before root AddResource at `0063AC20`. This supports that the seed is read before AddResource and construction is upstream; it does not establish how the root seed was derived or name a C++ class.

The 21:40 all-saved-evidence bundle still contains seed-function analysis from `20261002T213047Z_00001A0004E84EFD` and NMS.exe SHA-256 `671de22649274b49fa07f5a246bc7252c4e08bb9ab623d2e65722fbab4e497a4`, so its zero possible writes / zero RTTI candidates must not be applied to the current executable. The newer fresh upstream result is suitable input for the existing Analyze Seed Function action, but that action must be run after upstream, not in the parallel test.

## Current state and human gate

Two distinct address/root-seed pairs are currently available in prior measurement evidence: `00001A0004E84EFD -> 9256392A2F5A74AC` and `0001550006607CAC -> 00C9E8DF0327789E`. The newest event repeats the second pair. That is insufficient to establish a general address-to-root-seed derivation. Agent-owned review and static correlation are complete; the remaining useful sample requires a live NMS capture at a third universe address.

Requested sequence: use current main Surveyor v0.3.67 with Seed-Lineage extension 1.0.4; load a derelict in a universe address different from both addresses above; wait until a saved `MODELS/SPACE/POI/DUNGEON.SCENE.MBIN` root event shows that address and a candidate seed; exit NMS; upload the captured runtime event; then run caller extraction, upstream callers, and seed-function analysis sequentially, waiting for each upload to complete before the next. Full derelict traversal is not required; stop after the root event is captured.
