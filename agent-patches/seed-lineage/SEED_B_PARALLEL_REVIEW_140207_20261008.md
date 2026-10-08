# Seed-B review of main's 14:02 combined report

## Provenance

The authoritative pointer on main names run `20261008T140207Z-d8e24197` at `research-uploads/20261008T140254Z-parallel-action-test/combined-results.json`. The report SHA-256 is `11ec9ee30687570efda334a255ea27836bfb347d8bf7631ec4ffae981e9175f6`, matching the pointer. The report mode is `isolated_parallel_test_no_github_upload`: eight research actions completed, none failed, and the runtime upload action was skipped. The analysis used saved evidence; it did not attach to NMS during the parallel run.

## Findings

- The generation artifact derives from saved session `20261008T140041Z_0001BF0004E84EFD` (probe 0.3.38). It records universe address `0001BF0004E84EFD`, root seed candidate `5B4AE67D9C2A8F61`, CARGO_FLOATERS inference at high confidence, 11 logical chunks, and 164 scene instances. Its 43 targets (30 salvage crates and 13 footlockers) are asset-derived predictions, not an observed container count.
- The saved root event at `2026-10-08T14:00:37.545Z` records root descriptor `0000021C2457DD28` under owner `0000021C2457DC00`, seed `5B4AE67D9C2A8F61`, and direct Engine caller `0063AC20` targeting `0183E770`. A matching logical-entry trace at `02C08607: FF 52 10` returns at `02C0860A`. Both recorded owner `+0x10` reads are zero after the external call, including at root add; the indirect target remains unresolved.
- The POI description trace receives the universe address as its raw argument (two observations). Its return `0000004225AFD180` matches the POI component address, not the universe address or root seed. It does not supply a demonstrated root-seed transform.
- The caller-code action output uses a separate saved session, `20261006T223811Z_0001BF0004E84EFD`; its caller window matches the supplied current executable hash. The upstream-caller output uses session `20261004T151219Z_0001BF0004E84EFD` and candidate `006388A0`. Those results do not establish the constructor of the 14:00:37 root event. A fresh caller export followed by upstream extraction is the next useful shared-build workflow.
- The resolver reports zero matches for candidate `00634BC0` from the separate sample `02C04977` returning at `02C0497A`. It does not resolve the `02C08607` call.
- The report contains six saved-record measurements; two repeated-address groups have stable layout signatures. These are offline comparisons, not additional traversals.

The root seed remains a candidate, its derivation remains unproven, and the constructor identity and indirect dispatch target remain unresolved. This review does not claim any physical container count from the 43-target asset prediction.

## Shared Surveyor next step

Seed-Lineage extension 1.0.3 requests only existing shared host actions: Extract caller code, then Extract upstream callers. It adds no Surveyor code or probe hook. After a fresh root event is recorded, the user can run both actions from the shared main build and return their evidence. The caller capture should match the current NMS executable; both outputs should refer to the fresh evidence before they are joined. A full derelict traversal is unnecessary.
