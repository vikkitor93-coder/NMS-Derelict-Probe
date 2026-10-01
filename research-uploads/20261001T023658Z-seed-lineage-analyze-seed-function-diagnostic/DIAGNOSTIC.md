# Seed-lineage analyzer diagnostic — 2026-10-01

## Measured facts

- The controller diagnostic at `2026-10-01T02:36:58.410Z` failed in `analyze_nms_seed_function.py` while calling `find_function_start_from_padding`; the call raised `No compiler-padding function boundary found before the call`.
- Caller evidence session: `20260930T030805Z_00001A0004E84EFD`; upstream evidence session: `20260929T203022Z_00001A0004E84EFD`.
- Both files report universe address `00001A0004E84EFD` and root seed `9256392A2F5A74AC`. Both report call RVA `00635110`.
- Caller evidence reports NMS.exe SHA-256 `671de22649274b49fa07f5a246bc7252c4e08bb9ab623d2e65722fbab4e497a4`, size `88545352`, PE timestamp `6ABB9CC5`, and `baseline_window_matches_exe: False`.
- Upstream evidence reports NMS.exe SHA-256 `b7913f268dfc62386b6b68f524bfc8ade4a44a9f4fbad39085b7bf51be3680cb`, size `88480328`, PE timestamp `6AB0FFC9`, and saved function candidate `00634BC0`.
- The uploaded caller JSON reproduces the same boundary-detector exception using the v0.3.41 source.
- SHA-256: caller JSON `65848956f3e08a554f2f15c21421dfe70cd7d9a3490a6172cad822d184c42a09`; upstream JSON `6e8fa383811dab07fc9d05a66c20b110a77b7c5a0a6c06645aad323e1194cde1`.

## Interpretation

The matching address, seed, and call RVA do not make these captures interchangeable: their session IDs and NMS.exe hashes differ, and the caller capture says its probe window did not match its executable. Therefore the saved upstream candidate is **not validated for the caller capture** and is not used as a current function boundary.

## Inference / hypothesis

The caller capture and upstream analysis are stale or mixed across process/executable states. A fresh capture after launching NMS from the currently installed executable should establish whether the mismatch is resolved. This evidence does not identify why the runtime window differed from the executable, nor prove the current function boundary.

## Next action

After fully exiting and relaunching NMS, reproduce only the root resource event in the known system, then run Surveyor's **Extract caller code + upload**. Recheck the executable-window match before running upstream analysis. No full derelict traversal is requested.
