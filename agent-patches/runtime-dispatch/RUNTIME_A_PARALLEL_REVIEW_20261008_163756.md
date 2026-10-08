# Runtime-A review of latest combined report — 2026-10-08

## Source and scope

GitHub main pointer research/LATEST_PARALLEL_ACTION_TEST.json names run 20261008T163756Z-cd3dbef7 and report research-uploads/20261008T163844Z-parallel-action-test/combined-results.json. The report SHA-256 is 7eb7c6a62ee5a909d0e0f12df0890ac3653a73fa66ae11f51e0c651dc571994c, verified against the report bytes. This combined report is the sole authority for results of that parallel-action run. It ran in isolated_parallel_test_no_github_upload mode from 16:37:56.568Z to 16:38:38.823Z: 8 complete, 0 failed, 0 unsupported, and 1 upload action skipped. It analyzed saved evidence offline; it did not attach to NMS or capture a fresh live event. Neither the shared pointer nor report was changed by Runtime-A.

## Runtime-dispatch evidence

- research.extract_exact_root_caller ties the saved dungeon-root descriptor 000002752ED7F928, seed candidate 5B4AE67D9C2A8F61, and event time 2026-10-08T16:31:47.935Z to logical entry RVA 00634BC0. The exact external caller return RVA is 02C0860A; the caller bytes decode 02C08607: FF 52 10, returning immediately after the indirect call.
- The probe source identifies 00634BC0 as the current-build logical-entry hook location. Matching the same descriptor at that hook with caller return 02C0860A resolves the destination entry for this event to 00634BC0 by runtime control-flow correlation. This conclusion uses the observed callee entry and caller return, not the slot value or the separate resolver sample.
- The reported owner/RDX+0x10 sample is explicitly logical-entry-after-external-call; its raw value is 0000000000000000, and root-add also reads zero. This zero is not a dispatch target. The probe registers the entry callback as a BEFORE detour, so the zero remains an instrumentation/data inconsistency even though the separate control-flow correlation resolves the destination address.
- The separate resolver sample is 02C04977: FF 52 10 / return 02C0497A; its zero-match search against 00634BC0 is a different callsite and does not confirm or refute the 02C08607 runtime correlation.
- The caller 0063AC20 -> 0183E770 is a separate Engine caller/seed-lineage result, not the indirect dispatch destination. The unrelated static helper path at 0063A706 is also not evidence for this runtime target. The earlier 0063A6D0 target claim is unsupported.

## Hook timing and target resolution

The checked-in probe source, mod/derelict_baseline_probe.py (SHA-256 ACC8942B792A3EB0C9FFC4A688676E42B24587703655CE6675F11082CFD47750), pins CURRENT_BUILD_LOGICAL_ENTRY_RVA to 00634BC0 and registers _trace_resource_descriptor_walk_entry with @_resource_descriptor_walk_entry.before and @get_caller. In installed pyMHF 0.2.4, _compound_detour executes BEFORE callbacks before self.original. Its caller-address trampoline loads the qword at [RSP] (the function's return address) and caller_address returns that saved address relative to the module base. Source hashes: pymhf.core.hooking.py 5008B2D3106C598DFCA7AB7A0641F7A879DDCE93E0EF8836950A16983EA2A9AA; pymhf.utils.iced.py 8EDDAF92E8B718490D0CB48AF6AC9FFF2B45EACA7051011D442663FC5711E254.

Therefore the exact root descriptor match at the 00634BC0 BEFORE hook, paired with return 02C0860A immediately after 02C08607: FF 52 10, resolves the dispatch destination for this event to 00634BC0. The +0x10 value remains contradictory and unresolved; it is not used as the target evidence. The function's semantic identity is not established by this address correlation.

## Counts and limits

The latest report's generation-baseline artifact is session 20261008T163203Z_0001BF0004E84EFD with probe 0.3.38. It reports zero resolved dungeon scene instances and zero predicted containers because the preset is unresolved. These analyzer outputs are not a physical container count. The separate asset-derived 43-target prediction (30 salvage crates + 13 footlockers across 164 resolved scene instances) is from the distinct 14:02 main report at research-uploads/20261008T140254Z-parallel-action-test/combined-results.json, SHA-256 11ec9ee30687570efda334a255ea27836bfb347d8bf7631ec4ffae981e9175f6; it is not a result of the latest 16:37 run. The prediction remains distinct from the historical 35-container measurement and the separate post-update 16-container user observation. The latest report's asset index says 75 of 1,433 indexed dungeon scenes contain target-container assets; that is an asset-index result, not a generated or observed count.

## Next work

Do not use WinDbg for this capture: the user reported that attaching the debugger crashes NMS, while NMS runs normally without it. Continue offline by checking why the BEFORE-hook owner+0x10 read is zero despite the confirmed entry/caller dispatch correlation, and investigate the argument mapping or concurrent mutation. If needed, design and test a read-only callsite capture. Do not request a live NMS action unless repository and saved evidence are exhausted. No full traversal is required.

Evidence for the report's returned artifacts and provenance is preserved in the combined JSON above; no queue or separate per-action latest file was used.
