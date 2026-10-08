# Runtime-A review of parallel-action report — 2026-10-08

## Source and scope

This review uses the local v0.3.62 source candidate supplied for this task. Its `research/LATEST_PARALLEL_ACTION_TEST.json` points to `research/parallel-action-tests/20261008T130233Z-755d4c43/combined-results.json`. The report SHA-256 is `12035c7362e77363af084bc24254c7b013edecba6ca9015f1d3c6985ea527eda`, matching the pointer. This combined report is the sole source used here for the eight action results. Its `research_review` says the actions reanalyzed the start-of-run saved-evidence snapshot offline; there was no NMS attachment or new in-game capture. The ninth upload action was not run because uploads were disabled. The candidate ZIP and its report are not asserted to be published on GitHub `main`.

The latest `main` pointer was also checked: run `20261008T140207Z-d8e24197`, report `research-uploads/20261008T140254Z-parallel-action-test/combined-results.json`, SHA-256 `11ec9ee30687570efda334a255ea27836bfb347d8bf7631ec4ffae981e9175f6`. The bytes match the pointer. This is a distinct report and is authoritative only for its own run: mode `isolated_parallel_test_no_github_upload`, eight actions complete, upload skipped, no NMS attachment during the run. Its start-of-run snapshot contains a saved root event timestamped `2026-10-08T14:00:37.544Z`; the report does not attribute the event's capture process to the isolated action run.

## Runtime-dispatch findings

- The exact-caller extraction in the report associates the saved 2026-10-06 root event with the current executable call instruction at `02C08607` (`FF 52 10`) and return RVA `02C0860A`. The logical-entry hook snapshot records `RCX=00000113E5829960`, `RDX=00000112B726B400`, and a captured `RDX+0x10` value of zero. The corresponding owner+0x10 entry and root-add reads are both zero. This does not resolve the indirect call target: zero is not a target address.
- The latest `main` report's saved event (2026-10-08 14:00:37.544Z) matches the same caller instruction and return RVA. Its probe 0.3.38 logical-entry snapshot occurs after the external call; `RDX+0x10` is zero at entry and root-add. This newer event still does not provide a pre-instruction slot value or identify the dispatch target.
- A distinct resolver result in the combined report analyzes call instruction `02C04977` (`FF 52 10`), return RVA `02C0497A`, candidate function `00634BC0`, and slot `+0x10`; its offline search found zero vtable matches. This is a separate callsite/sample and does not identify the target for `02C08607`.
- Generation analysis reports 164 resolved scene instances and predicts 30 salvage crates plus 13 footlockers (43 target containers) from assets. That is an asset-derived prediction, not an observed physical loot count. It does not replace the historical pre-update 35-container measurement or the post-update 16-container user observation.
- The report describes repeated-address stability as offline comparison of saved records, not additional physical derelict traversals.

## Next action and limits

Offline work available from both reports is complete. The latest saved event has already repeated the post-call zero read; resolving the dispatch target now requires a pre-instruction observation at `NMS.exe+02C08607` (`FF 52 10`), recording `RDX` and the 8-byte value at `[RDX+0x10]` before the instruction executes, or equivalent current runtime evidence. Verify the executable against SHA-256 `13d5060d4efb9d2a6a6b1b349bc4257231056cc2a055df4bb15d816262cc3499`. No full traversal is required. The pointer and shared reports were not modified by this lane.
