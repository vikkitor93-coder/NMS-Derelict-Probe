# Runtime-A hook-signature correction — 2026-10-08

## Provenance

For results from the Oct 8 16:37 parallel-action run, the sole authority remains the combined report named by `research/LATEST_PARALLEL_ACTION_TEST.json`: run `20261008T163756Z-cd3dbef7`, report `research-uploads/20261008T163844Z-parallel-action-test/combined-results.json`, SHA-256 `7eb7c6a62ee5a909d0e0f12df0890ac3653a73fa66ae11f51e0c651dc571994c`. It is an offline saved-evidence analysis (8 complete, 1 upload skipped, no NMS attach or fresh capture). Its raw `logical_entry_rva=00634BC0` is preserved as report provenance; it is a stale probe constant, not the installed hook address.

The probe declares `_resource_descriptor_walk_entry` with `@static_function_hook(signature=...)` and no fixed offset. The old `CURRENT_BUILD_LOGICAL_ENTRY_RVA` is only serialized into evidence. The user's read-only scan verified NMS.exe SHA-256 `13d5060d4efb9d2a6a6b1b349bc4257231056cc2a055df4bb15d816262cc3499` and found the hook signature once, at RVA `0063A6D0`, file offset `0x639AD0`.

DUNGEON-C's prior static artifacts independently record that same executable hash and unique match at `0063A6D0`; `ROOT_CALLBACK_CODE_20261007.json` records the .pdata range `0063A6D0..0063A729`, 89-byte body SHA-256 `dc6fa62fa2578901da50c294098f08b4bc25afb0672c3e7475161de66f9d90d7`. Those artifacts analyze an earlier event; they corroborate static hook location and recursive-return evidence only.

## Finding

The saved 16:31:47.935Z root event ties descriptor `000002752ED7F928` and seed candidate `5B4AE67D9C2A8F61` to caller return `02C0860A`, immediately after `02C08607: FF 52 10`. The BEFORE callback that recorded this exact descriptor and return address is installed at the unique signature match `0063A6D0`. The dispatch destination for this matched event is therefore resolved to `0063A6D0`.

The old labels `00634BC0` (logical entry) and `00634C63` (recursive return) are stale. The matching-build DUNGEON-C review records recursive-like caller return `0063A773`. Runtime-A source constants are corrected to `0063A6D0` and `0063A773`, and the probe source version advances from `0.3.38` to `0.3.39`. A focused regression test compares the source labels to the hash-matched artifacts. The function's semantic identity remains unresolved.

## Limits

- Owner/RDX+0x10 is zero at the after-call hook capture and root-add. This remains a capture/data inconsistency, not a dispatch target.
- The resolver sample at `02C04977: FF 52 10` is a separate call and does not resolve this event.
- The latest report's zero scenes/targets comes from an unresolved preset, not an observed physical count.
- The 43-target figure (30 salvage crates + 13 footlockers across 164 instances) is an asset-derived prediction from the distinct 14:02 report, SHA-256 `11ec9ee30687570efda334a255ea27836bfb347d8bf7631ec4ffae981e9175f6`; it remains separate from historical 35 and post-update 16 observed counts.
- No WinDbg attach, new NMS capture, game launch, or traversal was performed.
- The targeted regression test is pending because the local command runner is unavailable; no test pass is claimed.

## Next action

Run `python -m unittest tests.test_runtime_hook_address_labels` from this Runtime-A branch. If it passes, publish the correction to main, then continue offline semantic analysis of `0063A6D0` and the zero-slot discrepancy.
