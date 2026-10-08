# Seed-B review of combined report 20261008T185304Z-e95aae15

## Provenance

The main pointer names `research-uploads/20261008T185341Z-parallel-action-test/combined-results.json`, SHA-256 `9576e887375b1d79ad629b07a26209337479ff6cf096222207de4c53a130dcbe`. The fetched 1,555,003-character report was hashed and matched the pointer. This combined report is the sole source used for this run's action results; queue and separate per-action latest files were not used.

The parallel run started 2026-10-08 18:53:04.466Z and finished 18:53:36.479Z in `isolated_parallel_test_no_github_upload` mode. It had an input snapshot; worker data was not retained. Eight actions completed and the `research.upload_runtime_capture` action was `not_run_upload_disabled`. The parallel run itself did not attach to NMS.

## Seed-Lineage evidence

The report's saved generation artifact is session `20261008T185119Z_0001550006607CAC`, universe `0001550006607CAC`. It records one `MODELS/SPACE/POI/DUNGEON.SCENE.MBIN` resource event at 2026-10-08 18:51:04.549Z with primary seed candidate `00C9E8DF0327789E`; status is `candidate-captured-unverified`. This is consistent with the lane's prior baseline candidate for the same address, but does not establish a system-to-root-seed derivation.

The `MEDI_FLOATERS` preset inference is high confidence in the analyzer output. The saved model has 10 logical rooms and 146 scene instances; assets predict 14 target containers (7 salvage + 7 footlockers). This is an asset-derived prediction, not a physical container count. Preserve it separately from the earlier `CARGO_FLOATERS` asset-derived prediction of 43 targets (30 salvage + 13 footlockers).

## Evidence that must not be joined to the fresh event

- `research.extract_caller_code` cites source session `20261006T223811Z_0001BF0004E84EFD`, universe `0001BF0004E84EFD`, candidate seed `5B4AE67D9C2A8F61`; its bytes match the recorded executable, but it is an older session.
- `research.extract_upstream_callers` cites source session `20261004T151219Z_0001BF0004E84EFD` and the same older universe/seed; it is not derived from the fresh caller export.
- `research.analyze_seed_function` cites source session `20261002T213047Z_00001A0004E84EFD`; it reports no direct references outside the known prefix, no possible descriptor-field writes, and no RTTI candidates. It cannot identify the fresh event's constructor.
- Exact-caller static extraction decodes `02C08607: FF 52 10`, returning at `02C0860A`; it does not resolve the indirect destination.
- The zero-match static resolver sample is `02C04977` / `02C0497A`, not the `02C08607` event. It does not resolve the event target.

## Next step

The fresh root event is already saved in the report snapshot. On shared main Surveyor, close NMS if open, use RUNTIME-A 1.0.6 **Upload captured root event**, then run Seed-Lineage 1.0.3 **Extract caller code + upload** followed by **Extract upstream callers + upload**. Verify that the caller cites session `20261008T185119Z_0001550006607CAC`, universe `0001550006607CAC`, and matching NMS.exe SHA-256 `13d5060d4efb9d2a6a6b1b349bc4257231056cc2a055df4bb15d816262cc3499`; verify upstream points to that caller. No new NMS launch or derelict traversal is required if the saved capture is still available.
