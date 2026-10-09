# Seed-Lineage review of automatic run 20261009T161520Z-7233c462

## Authoritative combined report

- Automatic batch: `20261009T161519Z-fdc03736`.
- Batch index: `research-uploads/20261009T161615Z-automatic-research-batch-20261009T161519Z-fdc03736-828540/batch-results.json`, SHA-256 `69a195338658155ed8165b7e69abf459b9c904a9fca22d75304e2356a45ed418`; this matches `research/LATEST_AUTOMATIC_RESEARCH_BATCH.json`.
- Per-session report: `research-uploads/20261009T161615Z-automatic-research-batch-20261009T161519Z-fdc03736-828540/reports/20261009T161520Z-7233c462/combined-results.json`, SHA-256 `35e403f79d6e3c665a36f74eee13928dc5a9d77036278604efb1039143076e55`; this matches the batch index.
- Input session: `20261009T161406Z_Otsues.json`, SHA-256 `bd414953ea7592fa20e56e286b3189d214535476242e19cee2fc617e0b77e166`.
- Run status: completed with errors (7 complete, 1 failed, 1 upload skipped); mode is isolated parallel analysis with no GitHub upload.

## Seed-lineage result and limits

The fresh generation artifact names one root-resource candidate at address `0001680006607CAC`: `2139770A2614E3DC`, with `UseSeedValue=true`. It is one observation; NMS.exe identity is not present in that measurement artifact. The POI argument equals the universe address and its returned component address (`00000097FFFDD0E0`) matches neither that address nor the root seed. Prepare, activation, and lifecycle event counts are zero. The system-address-to-root-seed derivation remains unknown.

The report's exact-root-caller action extracts the static caller around return RVA `02C0860A` from NMS.exe SHA-256 `13d5060d4efb9d2a6a6b1b349bc4257231056cc2a055df4bb15d816262cc3499`; its embedded exact runtime match is at 16:13:49Z for the 000168 address and root candidate. This is a separate static-extraction result. The fresh runtime capture itself has no executable hash. Its `owner+0x10` reads zero. The separate resolver action reports zero matches for candidate `00634BC0` and caller `02C0497A`; it does not resolve the live `02C0860A` dispatch target.

The combined report's `extract_caller_code`, `extract_upstream_callers`, and `analyze_seed_function` artifacts still cite session `20261008T185119Z_0001550006607CAC`, address `0001550006607CAC`, and root `00C9E8DF0327789E`. They are not a same-sample chain for the fresh 000168 root. The parallel execution therefore cannot replace sequential lane actions.

Generation analysis predicts 14 MEDI_FLOATERS targets from static assets; this is not an observed physical count. The asset-derived CARGO_FLOATERS prediction of 43 targets remains separate from generation-measurement fields and is not a physical count. The prepare-assets action failure belongs to that asset workflow and does not change the Seed-Lineage result.

## Newer runtime-only capture and all-saved upload

A later, separate runtime-only capture is `research-uploads/20261009T161848Z-upload-runtime-capture/exact-root-caller-latest.json` (SHA-256 `e0f850e46dd8b36b24de323a212ec84043cfc872a111cb5e6060316aaa7af412`). It records one root event at address `00006D0006606CAB`, candidate `A5047E4E4B68F362`, dynamic external caller return `02C0860A`, and a zero `+0x10` slot. It has no NMS.exe hash and is not included in the 16:15 combined report; do not merge it into that report's 000168 result.

The newest all-saved upload is `research-uploads/20261009T161936Z-all-saved-evidence-89885315/run-manifest.json` (run-manifest SHA-256 `159c8d153e3b7020daf143ce8f574392a7c92791e8750d618437be500f3148af`). Its manifest verifies that the root/exact-caller file is this 00006D capture, while the bundled caller/upstream files still cite 000155 and seed-function analysis cites 00001A. The capture journal contains UI texture resource-add events, not a new dungeon root.

## Next lane action

Use the Seed-Lineage 1.0.5 panel sequentially on the newest saved 00006D capture: extract caller code, then upstream callers, then seed-function analysis. Require all output manifests to agree on session, address, root, caller and executable hash. No new NMS run or full traversal is required.
