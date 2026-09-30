# AI handoff — NMS Derelict Probe v0.3.28

Read-only NMS.py/pyMHF derelict-freighter reverse-engineering project.

## Stable evidence

Known address `00001A0004E84EFD` repeatedly correlates with dungeon-root descriptor seed `9256392A2F5A74AC`.
Runtime capture established root `Engine::AddResource` CALL RVA `0x00635110` and caller return `0x00635115`; the descriptor already contains that seed at the resource boundary.

The 20 KiB offline caller extraction matched the installed NMS.exe exactly. The v0.3.26 upstream scan now places the nearest INT3-padding containing-function candidate at `0x006345B0` (correcting the earlier informal `0x00634BC0` estimate). It found exactly one direct rel32 reference to `0x006345B0`: CALL `0x00634C76 -> 0x006345B0`. Because `0x00634C76` lies inside the same candidate function, this is a self/recursive call, not an external upstream caller.

The same scan observed descriptor-related offsets in this routine: embedded descriptor around second-argument `+0x128`, primary seed at `+0x138` (descriptor `+0x10`), and UseSeedValue at `+0x140` (descriptor `+0x18`). Treat the register/base interpretation as byte-pattern evidence, not a fully recovered C++ signature.

## v0.3.28

Adds `tools/analyze_nms_seed_function.py` and GUI action **Analyze seed function + upload**. It is fully offline/read-only and produces `dungeon-seed-function-analysis-latest.json`.

It uses PE `.pdata` runtime-function entries as authoritative function-boundary evidence, classifies direct xrefs as internal/external, scans all references to offsets `0x128/0x138/0x140`, conservatively flags common direct writes, scans non-text function-pointer references, and attempts validated standard MSVC x64 RTTI/vftable recovery.

Important correction: do not claim the seed is definitely constructed in another function merely because it is read before root AddResource. The same containing recursive function could have populated it on an earlier branch. v0.3.28 is designed to test that before adding a risky runtime hook.

Next action: update/install v0.3.28, restart once, click **Analyze seed function + upload**, then tell ChatGPT `check`.