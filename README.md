# NMS Derelict Probe

Current stable package: **v0.3.28**.

## v0.3.28 — seed-function structural analysis

The v0.3.27 upstream scan found one direct rel32 reference to the function containing the root `Engine::AddResource` call. That reference is inside the same function, so it is a recursive/self-call rather than an external caller. The scan also corrected the nearest compiler-padding function candidate to `0x006345B0`.

v0.3.28 adds **Analyze seed function + upload**, an offline/read-only analysis that:

- uses x64 PE `.pdata` unwind metadata to establish the exact function start/end containing root call `0x00635110`;
- checks whether the earlier INT3-padding boundary agrees with `.pdata`;
- classifies direct rel32 references as internal/self-recursive vs external;
- scans the exact function bytes for references to the embedded descriptor (`+0x128`), primary seed (`+0x138`) and `UseSeedValue` (`+0x140`);
- conservatively identifies common direct memory-store encodings to those fields;
- scans non-code PE sections for pointers/RVAs to the function;
- best-effort parses standard MSVC x64 vftable/RTTI metadata when an absolute function pointer is present.

Output:

`%LOCALAPPDATA%\NMSDerelictSurveyor\asset-work-v1\dungeon-seed-function-analysis-latest.json`

No NMS launch or derelict traversal is required.

Existing GitHub upload/update, workflow diagnostics, safe real-Python helper launching, no-overlay mode, and the one-click clean **Restart Surveyor** button remain unchanged.

Research caution: a read of the descriptor seed before `Engine::AddResource` does **not by itself prove** that seed construction occurs in a different function; v0.3.28 explicitly checks for writes elsewhere in the containing recursive function before moving the boundary farther upstream.