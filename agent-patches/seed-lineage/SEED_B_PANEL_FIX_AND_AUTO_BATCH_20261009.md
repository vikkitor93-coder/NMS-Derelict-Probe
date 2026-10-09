# Seed-Lineage automatic batch review and panel fix — 2026-10-09

## Evidence provenance

The current automatic saved-session batch pointer names `20261009T015908Z-d4d6ae3f`, batch index `research-uploads/20261009T015948Z-automatic-research-batch-20261009T015908Z-d4d6ae3f-50cb03/batch-results.json`, SHA-256 `b1ea5afaee7aa2f6d2a49bd48c28b73a67d59a9aad3f6b53702d41fe2b0ea18a`. The batch index and its one session report were independently SHA-256 verified. The session report is `research-uploads/20261009T015948Z-automatic-research-batch-20261009T015908Z-d4d6ae3f-50cb03/reports/20261009T015909Z-77532ce2/combined-results.json`, SHA-256 `721427df0b4d95a3bb0cfee5ececa3fdb5517713c0abd998fca4802e3ced994b`. Its input session file is `20261009T015149Z_Otsues.json`, SHA-256 `2b6c2767cdc1d01c4ef2c36a5536a787379bcd72bc3159ae5871a8fb786807a7`.

The latest manual parallel-action pointer is a separate report/run: `20261009T004054Z-9fedea65`, SHA-256 `af6166966fb37b738d9a584103275a10f28d1d39e6e39f23181e63a4beacd972`. Its per-action results are not substituted for the automatic session report below.

## Automatic report findings

The automatic report completed 7 of 9 actions, failed 1 Metadata action, and skipped the upload action by design. Seed-Lineage caller and seed-function actions both cite the earlier session `20261008T185119Z_0001550006607CAC`, root candidate `00C9E8DF0327789E`, and NMS.exe SHA-256 `13d5060d4efb9d2a6a6b1b349bc4257231056cc2a055df4bb15d816262cc3499`. The seed-function analysis reports a candidate logical entry at RVA `0063A6D0`, 51 direct references outside the known prefix, zero possible descriptor-field writes, and zero RTTI candidates. These byte-level observations do not establish a seed-construction formula or class identity.

The same report's generation-measurement action contains a third universe address, `0001680006607CAC`, with root resource `MODELS/SPACE/POI/DUNGEON.SCENE.MBIN` candidate `2139770A2614E3DC`, `UseSeedValue=true`, and one observation. The measurement artifact does not include an NMS.exe hash, so its executable identity is unverified. The accumulated measurement artifact reports 6 measurements across 3 addresses. The caller/upstream/seed-function outputs do not form a fresh chain for this third-address sample. The third pair therefore advances the comparison but does not prove a general derivation.

Keep target quantities distinct: the 14 MEDI_FLOATERS value and separate 43 CARGO_FLOATERS value remain asset-derived predictions, not physical counts. The zero `+0x10` read and separate resolver sample do not resolve the dispatch target.

## Surveyor panel failure

The supplied screenshot reports `Invalid extension panel summary`. The published 1.0.4 panel summary is 635 characters; the host validator in `tools/agent_ui_extensions.py` rejects summaries longer than 500. The failed update safely leaves the prior installed extension active. Candidate 1.0.5 shortens the summary to 432 characters, keeps the same three stable action IDs in caller → upstream → seed-function order, and carries the current report ID and evidence limits.

Build request `seed-panel-summary-limit-20261009` is ready under `build-requests/seed-lineage/`. It contains versioned panel and manifest files, the shared-index update, and a focused test asserting the host summary limit. Request status is not evidence of integration; only the primary compiler publishes the integrated Surveyor build and complete source ZIP.

## Verification and limits

- Verified the batch index SHA-256 and its session-report SHA-256 against their respective pointers.
- Verified the Oct. 9 manual combined report SHA-256 against its pointer.
- Focused static contract check: panel JSON keys, summary length (432 ≤ 500), stable action IDs, preconditions, namespace, manifest identity and panel hash, index target, and request payload hashes all pass.
- Updated Python regression test: `python -m unittest tests.test_seed_lineage_ui_extension`; not run in this environment because local process setup failed. The main compiler must run it during request staging.
- No Windows visual smoke test has been run after the fix. The screenshot is the observed failure evidence.

## Next work

After request integration and a successful extension update, use the already captured third-address session for a fresh caller → upstream → seed-function chain. A new derelict traversal is not required unless that saved capture cannot be loaded or uploaded.
