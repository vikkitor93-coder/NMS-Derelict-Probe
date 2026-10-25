# CURRENT AI HANDOFF ? 2026-10-22

Read `D:/Orca/NMS-COORDINATION.md`, then `research-output/CODEX_HANDOFF_20261022.md`, `STATUS.md`, and `WORKSPACE_STATE.json`. The scanner was explicitly paused by the user; the old 17:56 progress figure is historical. Do not restart/resume it or publish an index while working through the staged coding/tests. Update-resilience comparison and regression state are summarized at the top of `STATUS.md`; staged speed work and remaining benchmarks are in `research-output/SPEED_FIXES_STAGING_20261022.md`. Never launch or attach to NMS.

## 95% USAGE STOP (2026-10-22 late, Claude main session) - NEXT AGENT START HERE

All agents paused/stopped for the 95% usage rule. State:
- DONE today: Done checkbox (viewer, server restarted); Tailscale PC + phone (<phone>) working; compact map format 4 (local only, 1,772/1,772 identical, ~2x smaller); cloud CPU research (research-output/CLOUD_CPU_COST_20261022.md); generator profile (GENERATOR_PROFILE_20261022.md); frigate early-reject searcher (FRIGATE_SEARCH_20261022.md, tools/frigate_search_705.py); TURRETS root cause (TURRETS_WRITER_SLOWNESS_20261022.md: game retry loop, no exact early exit; writer-result cache 9.4x on re-runs posted as REQUEST to scanner agent).
- PAUSED: staging speed fixes 1-4 (resume: `bash run_phase1.sh` in D:/Orca/Temp/claude/staging-20261022/tests; apply diffs on top of current live files, do NOT copy files over; see staging PAUSED note below). Update-guard steps 1-5 (see its PAUSED note; tools exist: tools/update_guard_705.py, relocate_generator_705.py, compare_builds_705.py, golden_ingame_705.py).
- QUEUED (after staging): searcher items 2 (per-preset probability table + --recall-target) and 3 (2% audit sampling of rejected systems).
- USER APPROVALS PENDING: staging fixes 1-4 switch-over (after results); writer-result cache; prune threshold; compact format for all maps; public vs private site.
- User decisions: cloud test = not now. Scanner backlog was paused by the user for timing tests - user resumes it.
- The 95% stop rule stands (the user skipped it once, "just now").

# CURRENT HANDOFF ? NMS Derelict Probe ? 2026-10-22 17:56 UTC

`research-output/CODEX_HANDOFF_20261022.md` is the authoritative current handoff for this NMS project. Older handoff sections below are historical and may describe obsolete scanner states.

Immediate state: LAN scanner PID 44808 is in the Salvaged Frigate Module backlog, 39,266/87,264 finished at the last check, 7 BelowNormal workers, 1.65 systems/s, ETA 08:04; no regions active and no API error. `finish_after=true` is set: the user asked the scanner to stop after the module backlog. **Do not restart or interrupt it.** Refresh the scanner page to monitor; its page-side formatter is already on disk. After it stops, audit cache and actual atlas publication, recompute pruning numbers, and do not delete anything without user approval.

For priorities, human-only checks, paths, test record, and public-site gate, read `research-output/CODEX_HANDOFF_20261022.md`, then `STATUS.md` and `WORKSPACE_STATE.json`. First read `D:/Orca/NMS-COORDINATION.md`. Never launch or attach to NMS.

---

## CLAUDE HANDOFF - 2026-10-21 evening (latest)

The current state and open items are in STATUS.md, section "NEXT AGENT START HERE". Nothing is running. Read D:/Orca/NMS-COORDINATION.md first.

## CODEX HANDOFF ? 2026-10-21 (latest)

- **Live minimap (2026-10-21):** `minimap/` + `tools/live_position_705.py` (read-only memory reader, NMS 13D5060D). Launch `tools/Derelict-Minimap.cmd`; details `minimap/README.md`, STATUS.md line 'Live minimap'. Local only, not published.
- User direction: rewards must run inside the normal scanner and show visible progress. The user said this flow is untested, so code only for now; no actual reward or layout scan was started. Updated code is in `D:/Orca/NMS-Derelict-Probe-fastgen/app/scanner.py`; restart the scanner LAN server/desktop app before a user-started run. On Scan, it reconciles the cache, computes missing rewards, displays progress in existing status detail, uploads every 500 newly computed rows plus the final remainder, then enters ordinary region scanning. Pause/stop take effect at chunk boundaries.
- Mock-only check: 1,003 fake addresses, 1,003 cache rows, three checkpoint uploads. Scanner module compile passed. Latest fast suite: 20 passed, 0 failed, 1 skipped. Viewer verify: 1,456 layouts, 0 different. Full suite: **21 passed, 0 failed, 0 skipped** (91s).
- Partial rewards on disk: 7,706/60,190 (12.8%; C=4,099, B=2,038, A=1,215, S=354). No backfill process is active. Last published atlas commits `7a27af3`, `3efd509`.
- Low-poly GLBs replaced viewer 3D container geometry. Public candidate v5 is staged at `D:/Orca/NMS-Derelict-Probe-analysis/public-site-candidate-20261021-v5/site/`; it includes `piece_props.json` and excludes official glyph PNGs. No site deployed. User will provide destination choice later.
- User confirms pointer lock works; narrow-passage issue and mobile controls still need user browser testing.
- Remaining user actions: start scanner after restart when ready; test mobile/tight-space Walk inside; provide public-site destination when ready; complete the listed in-game blind/reward/count/turret/hazard checks in `research-output/CODEX_HANDOFF_CHECKLIST_20261021.md`.

## CURRENT STATE - 2026-10-20 14:30 UTC (read first)

- **LATEST (2026-10-21): HANDOFF 2026-10-21 (usage 92%, resets 04:30): two agents were told to save and write progress notes: research-output/VIEWER_AGENT_PROGRESS_20261021.md (viewer tasks 1-5: locked column layout, draggable Columns rows, totals = Salvaged Frigate Module Crates by default, 3D layer checkboxes and no duplicate fixtures with game-coloured shapes, first-person walk mode, end-reward column/picker/card) and research-output/END_REWARD_DATA_PROGRESS_20261021.md (fast batch end-reward predictor, precompute cache D:/Orca/NMS-Derelict-Probe-analysis/end-reward-cache/rewards.csv, REQUEST to the scanner for reward columns). Next agent: read those two notes and D:/Orca/NMS-COORDINATION.md, then finish what's left. Still the user's decision: GitHub Pages location. Full detail: STATUS.md top entries.**

- **Objective:** finish the NMS 7.05 offline arbitrary-address derelict generator. No NMS launch or attach; crate contents and rewards are out of scope.
- **Fixture:** the exact-build native writer reproduces address `00003B0006606CAA` from asset-derived inputs: 11 rooms and 145 placements. A4720 transforms fit 145/145 captured component positions within `1e-5` (124 exact); all 23 authored containers fit within the same tolerance. See `research-output/A4720_TRANSFORM_CONTAINER_FIT_20261020.md`. This is a model-to-capture check, not a live A4720 observation.
- **Second seed:** RESOLVED. `0000320006606CAA` completes (CARGO_FLOATERS, 9 rooms, 140 instances, 29+18). The earlier runs stopped at the instruction cap; the native search is long but finite.
- **Validated (2026-10-20):** `tools/generate_derelict_705.py <ADDRESS16>` (address → seed → preset → emulated native writer) matches the user-confirmed live census exactly for 3 derelicts, in rooms/crates/footlockers: `00003B0006606CAA` BUGS 11/17/6 (plus all 145 positions), `0000750006606CAB` BUGS 9/18/5, `0000320006606CAA` FLOATERS 9/29/18. It matches the old root-seed analyzer counts for 3 more addresses. The default is uncapped (about 6× faster, byte-identical). Report: `research-output/GENERATOR_VALIDATION_VS_LIVE_20261020.md`. Next steps: `STATUS.md` → Next actions. No user action required.
- **Blind test #1 CONFIRMED (2026-10-20 09:38Z):** at a new system (glyphs `122506607CAA`), the live writer seed `0A94CF6386B356A4` and CARGO_FLOATERS preset exactly match the prediction made before boarding. See `research-output/BLIND_PREDICTION_0002250006607CAA_20261020.md`.
- **Viewer (2026-10-20):** `tools/Derelict-Viewer.cmd` -> http://127.0.0.1:8765/ (`viewer/`, docs `viewer/README.md`): region table (real systems), per-derelict 2D deck maps (exact room cell masks, mirrored x, doors, stair links, fixtures) and 3D view (clean rooms, doors, stairwell holes + steps, fixtures, hangar stand-in ship; experimental game meshes from `tools/build_piece_meshes_705.py`). Decoded: room record u16[0..5] bbox + u16[12..15] cell mask (z fastest); doors = DOOR_* t + 4*A[2]; piece geometry centre = t + 8*A[2].
- **Walls done:** real wall outlines in the viewer; see `STATUS.md` -> 'Wall shapes DONE'. User action: none required.
- **HANDOFF 2026-10-20 ~18:00 local (usage 95%, resets 18:30): viewer v4-v6.** Read `STATUS.md` 'Viewer v6' first.
  - Done and tested:
    - official glyph icons with an Icons/Hex switch, and table paging (100–1000);
    - floors cache, so a cold region load is 0.5 s;
    - the table reads the GitHub atlas in the browser, all regions in one table;
    - shared `viewer/static/model.js` with pack/unpack/build;
    - pre-built views at 1.2 KB gzip per system, regression-checked on 1,367 derelicts;
    - `tools/derelict_view.py`, a byte-identical Python pack;
    - combined list `tools/build_atlas_index.py`;
    - lookalike SVG glyphs in `viewer/static/glyphs-svg/`;
    - a staged public site test in `D:/Orca/NMS-Derelict-Probe-analysis/site-test`.
  - The local LAN server is running (http://192.168.x.x:8765/).
  - **ANSWERED 18:00:** top 100 only, minimise size and file count. v7 DONE (see STATUS 'Viewer v7'); waiting on the scanner agent via D:/Orca/NMS-COORDINATION.md. Pages location still open.
  - **Waiting on the user's answers** (asked in chat):
    1. Publish views for all systems or only the top 100? Recommendation: all.
    2. Views in the atlas repo or a separate views repo? Recommendation: separate.
    3. GitHub Pages location: `docs/` in the atlas repo or its own repo.
  - After those answers:
    - Publish `index/` and `views/`. Nothing is pushed yet.
    - Integrate `build_atlas_index` and the view writing into the scanner/publisher (`D:/Orca/NMS-Derelict-Probe-fastgen/app/atlas.py`). That code is another agent's and was being edited; coordinate before changing it.
    - Do not commit in `D:/Orca/NMS-Derelict-Atlas` while the scanner is pushing.
    - Note: the scanner keeps no derelict.json, so views must be written at scan time.
- **Codex usage:** latest query was 5% of the 5-hour session and 50% weekly. The `NMS-Derelict-Research-Backup` task runs every 30 minutes and snapshots the shared workspace, including Codex changes; it skips unchanged snapshots. A manual Codex snapshot was also created at `D:/Orca/NMS-Derelict-Probe-backups/NMS-Derelict-Probe-snapshot-20261020T024956Z-codex-20261020.zip` (SHA-256 `2E9F2FBA8BA845631501AC93544D18771B79F2302C6623875FBC2414620E8C3C`).
- `WORKSPACE_STATE.json` is the machine-readable current state; `STATUS.md` is the concise project status. The prior Probe crash-capture milestone below is historical.

## HISTORICAL MILESTONE - resolve the Probe 0.3.55 r4 crash (2026-10-19)

The user reordered the previous offline layout-reconstruction milestone. This crash-resolution milestone is exclusive until a bounded replacement candidate is reviewed and ready for one user-run. r4 and the earlier Python-hook canaries remain suspended. The agent did not launch or attach to NMS.

Confirmed defect: r4 declares the generation worker with one pointer argument, but the matching-build caller places the copied preset in RDX and seed pointer in R8 as well as the component in RCX. pyMHF builds the detour and original trampoline from that declared signature, so the other two arguments are not preserved. The dump's NMS return address maps to the instruction after this worker call. This is a confirmed ABI defect on the observed crash path, but does not alone prove the complete `python313.dll` access-violation cause.

The r4 profile also loaded seven native hooks across three mods, including NMS.py's application-update hook; its runtime hash label actually identifies the target executable. The worker path is fiber-backed and the dump lacks private symbols. A bounded ABI/fiber harness reproduced the one-argument corruption and passed the corrected three-argument bridge for thread, fiber, and same-thread fiber-yield cases. An offline inventory preserved the full hook/runtime-entry-point scope.

The replacement transport is an external, one-shot CDB breakpoint at writer RVA `0x0039E5E0`; it does not load Python hooks. Its disposable event/timeout fixture passed: one hit captured the four register arguments plus two stack arguments and detached; the no-event controller break detached and the child stayed alive. The event-call interval was 76 ms in that .NET fixture, not an NMS pause estimate. Candidate files: `tools/Run-Layout-Capture-0.3.55-cdb.cmd`, `tools/run_layout_capture_0_3_55_cdb.ps1`, and `tools/Run-Layout-Capture-0.3.55-cdb-README.md`. It captures only six raw scalar arguments at entry; it does not read pointers, capture the return, or produce a layout. Static review is complete (2026-10-19): r1 had a blocking defect (its `bl` check expected `NMS+0x39e5e0`, but NMS.exe exports put an `AK::WriteBytesBuffer::GetPos+...` name there, so every run would fail after pausing NMS) plus symbol-server, post-detach `DebugBreakProcess`, and parse-scope hazards. Profile `0.3.55-cdb-r2` fixes all four and passed event, no-event, and forced-mismatch end-to-end runs of the real script against the fixture; details and hashes in `tools/Run-Layout-Capture-0.3.55-cdb-README.md`. r2 is ready for one user-run; the agent has not attached to NMS. Incident record: `research-output/probe-layout-capture-0.3.55-capture-only-r4-canary/R4_CRASH_TRIAGE_20261019.md`.

## DEFERRED MILESTONE - reproduce one known derelict outside gameplay (deferred 2026-10-19)

This milestone was active until the user reordered the work on 2026-10-19; it is now **deferred**. The known NMS 7.05 fixture has an offline replay of 145 captured room-component instances in 11 labeled rooms and 23 authored crate/footlocker positions, matching the fixture's per-room and total counts. That replay reconstructs a captured layout; it does not generate the layout from a seed. Completion requires producing the room graph, selected scenes, and container placements outside gameplay from the fixture's generator inputs, then matching the replay. Crate contents and reward selection remain out of scope.

Preferred fixture: universe address `00003B0006606CAA`; 11 rooms, 17 square crates, and 6 footlockers. The original session is `user-data/NMSDerelictSurveyor-moved-from-C-20261018/sessions/20261018T005220Z_00003B0006606CAA.json` (SHA-256 `87EBE6B171C2396423C18AFA4D114784078D895569ECDAABC5D7AC1D36EDB31C`). The new capture is session `20261019T003952Z_00003B0006606CAA` (SHA-256 `AE9D0241531866792F67CA3E1A84B40C56247AC7579E4326541EE6EC2C588049`), Probe 0.3.54, matching NMS executable SHA-256 `13d5060d4efb9d2a6a6b1b349bc4257231056cc2a055df4bb15d816262cc3499`.

The new capture's 145 room/resource events match the original fixture event-for-event. It has 148 delayed transform samples; all 145 room-component instances join to a valid nonzero sample. The 69 unique room-scene members were extracted from the matching 7.05 archive (SHA-256 `58958536E58DFAEB81E0423B5508C7D3DBF3713BAC09E857577FEB275D9F2627`), converted to MXML, and each conversion matches the existing cache byte for byte.

Replay outputs: `research-output/known-derelict-replay-20261019/KNOWN_DERELICT_LAYOUT_REPLAY_20261019.md`, the full JSON, and room/container CSVs in the same folder. Rebuild the replay with `tools/reconstruct_known_derelict_layout.py`. The exact member hashes and extraction/converter provenance are in `exact705/exact705-room-scene-members.sha256.json`; output/input hashes are listed in `KNOWN_DERELICT_LAYOUT_REPLAY_20261019.sha256`.

The Probe-recorded `C7DD2B2F667D36DD` is the `DUNGEON.SCENE.MBIN` resource seed and is absent from the current worker-to-writer seed path. Under the stock zero-override path, the address-derived `7D7ED1B33E15365D` reaches `FUN_14039E5E0` unchanged, but runtime override and selected component rows are not observed, so the saved fixture's seed/preset link remains conditional. The helper ports now compose through `nms_dungeon_writer_search_705.py`: one RNG is carried through room selection, the 200/500/1000 native retries, topology, A1DA0, and A2780. The driver returns room rows, grid, sparse placement descriptors, and RNG state. The A2780 theme tag and descriptor byte `+0x0E` are the logical room index; the shuffled slot counter only selects a candidate row. `nms_dungeon_instance_705.py` composes candidate source-row transforms with A4720's grid offset and authored direct crate/footlocker references.

Latest checkpoint at deferral: the composed conditional candidate reached A2780 but generated 59,606 placements versus the replay's 145 scene instances. Its static map provider walks only each root MXML and misses callback-tagged nodes in referenced scenes. Exact-build A3270 confirms that a zero-dimension map returns success, while A5480 writes no grid cells for it; do not filter zero rows in the port. Whether recursive references are active in this writer context remains unresolved, so the candidate is not a reproduction. The capture-only Probe 0.3.55 profiles are quarantined after two original-draft crashes, a further r1 crash, and the user's report of machine-wide lag followed by a forced shutdown. This layout milestone is deferred; the active work is defined above. Crate contents and reward selection remain out of scope.

## Latest runtime retest checkpoint - 2026-10-19

- Two original-draft runs and one capture-only r1 run recorded the same Windows signature: `python313.dll`, access violation `0xC0000005`, fault offset `0x2ABDA3`. The second original-draft run's last live status showed 538,606 resource lookups, 920 scene-probe events, and 107 generated-scene events. The r1 run then attached at NMS startup and also crashed. No retained dump identifies the callback; see `research-output/probe-layout-capture-0.3.55-capture-only-r1/CODE_REVIEW.md` and the quarantine follow-up at the end of this handoff.
- Capture-only r1 keeps the three exact-build layout hooks and disables other native Probe hooks before registration. Its source SHA-256 is `73A07CBA13F2A0761A2C44DC85B930AA0F364FF4A67E8B9CF8ED60260A1ECF5D`. It is not a safe fix: the r1 run also crashed, and the user reported system-wide lag and a forced shutdown.
- The r2 candidate reduces the native profile further but has not run. Both profiles and the one-click launcher are quarantined. Do not attach until the callbacks have an offline audit and the capture design is revised.
- Per-process NMS minidumps were configured for `live-runtime/NMSDerelictSurveyor/crash-dumps/` (up to three), but the latest archived WER report contained no dump. After reboot, no NMS or pyMHF attach process was running.
## Resume checkpoint — 2026-10-17 01:25Z — next objective: fix infinite loading

- User paused work for today. Tomorrow's first objective is to diagnose and fix the NMS infinite-loading regression; this was the original blocking problem. Do not substitute a downgraded probe as the solution.
- Active local candidate: `D:\Orca\Temp\NMS-Derelict-Probe-v0.3.80-safety-build-20261016`, Probe 0.3.51. Its source SHA-256 is `521BFF0946AE1A4A308ED6E7073ACE4E4CA2E08CEB152249AE034B776FABFC96`. Exact previous installed .50 backup: `%LOCALAPPDATA%\NMSDerelictSurveyor\installed-probe-backup\derelict_baseline_probe.py.before-0.3.51-20261017` (SHA-256 `FD75A143B46C36D8D371430BB8EB7C68A87E18EB12141AB4BB3E467634EA842B`). Candidate source ZIP `.83` is local/unpublished; SHA-256 `68E17CF12867893D4AC58C0645C998D55420B16A7054D5F5CE3D225D01E2DB00`.
- Live NMS PID `14904`, exe version `180836`, SHA-256 `13d5060d4efb9d2a6a6b1b349bc4257231056cc2a055df4bb15d816262cc3499`. Probe .51 attached and reported `state=ready`, heartbeat advancing, `latest_error=none`, but `recording=false`, universe/position unavailable, and no room or crate capture. NMS responded during this observation; the infinite-loading failure was not reproduced or cleared by that fact.
- Overlay was started as PID `29840`; it hides when NMS is not the foreground window. Windows kept Orca foreground when asked to switch, so no overlay was visible in that state. Overlay and probe are runtime processes, not project source changes.
- Tomorrow: inspect the exact .51 diff against .48 and .50, follow the startup/save-transition call path, isolate risky hooks/imports/callbacks and lifecycle behavior, use existing NMS logs/candidate history, and make the smallest reversible correction. Then launch the game without probe, verify normal save loading, attach the fixed probe only after load, and compare results. Only claim success after a real save reaches playable state and the probe stays healthy.
## Live research checkpoint - 2026-10-16 23:24Z

- Exact NMS.exe SHA-256 remains `13d5060d4efb9d2a6a6b1b349bc4257231056cc2a055df4bb15d816262cc3499`. The installed mod probe is 0.3.46, SHA-256 `64309747C7F7FB3BD42E139864A13C5A4CC0DD1A9586EC3FB978B46532BDE6B1`. The isolated candidate is 0.3.47, SHA-256 `04FD47A07E656852B2FC4CFA65CA0FD55DAAC81FD17E344A0C3D2D43BBA45015`; its 0.3.79 source ZIP was independently checked at SHA-256 `8FEC6CD4541198D17D5A49C2C5C2391C7EEED316D4A9DED2FC04951740A4A32A`, 200 members, CRC clean. It has not been installed.
- The candidate census reports scene-graph presence and Room ancestry, not active state or payout. Root review flagged two live-use questions: duplicate/cycle links can be skipped while `complete` remains true, and the synchronous after-hook may perform up to 512 nodes across 64 captures, with multiple `ReadProcessMemory` calls and `GetNodeName` calls per node. D is investigating active-state semantics, callback cost, and the completeness contract. Do not install until this review is resolved.
- A confirmed the current/candidate `GiveGenericReward.before` event provides reward ID, seed, flags, and candidate marker context, but neither version captures owner `+0x4F8` or the caller object vtable. B's bounded GcRewardTable parser/registration trace still does not prove a chooser or grant edge. One controlled crate opening can document an actual reward outcome, but cannot establish selection or RNG.
- Latest local session `20261016T153622Z_0000750006606CAB` began in AbandonedFreighter but is unended, has zero markers and no reward events. No NMS.exe process was present during this checkpoint and there is no newer session file; it is not evidence of a fresh run.
- Four distinct Orca Tasks are active: A audits saved reward events (`task_01998dce7c6f`); B searches exact-build reward-table consumers (`task_8be6958aef68`); C traces asynchronous population of manager entry `+0x30` (`task_f42806d8be40`); D traces node active-state semantics and census safety (`task_2133f9abfd92`). Keep them bounded and validate each report against local evidence before using it.
- Existing saved vector remains system `0001550006607CAC`, root `00C9E8DF0327789E`, nine Room groups, and 32/19 authored CRATEM/FOOT_LOCKER references. These reference totals are not confirmed active instances. Next: complete candidate safety review and the four offline routes, then request only the smallest live observation that remains necessary.
## Live investigation checkpoint - 2026-10-16 23:07Z

- Independently verified the matching executable SHA-256 `13d5060d4efb9d2a6a6b1b349bc4257231056cc2a055df4bb15d816262cc3499`. A traced the GenericReward type-10 callback through `0x14054D060` and `0x14054F660` to manager row base `+0x4B68 + index*0x248`; the owner `+0x4F8` key reaches row-state/event maintenance, not a proven grant. B mapped the reward-table constructor/parser/hash path at `0x140EEBD2F`, `0x1424D1F30`, and `0x1424DCFC0`; the selector and payout remain unresolved. C verified the manager entry constructor sets `+0x30` null and publishes at `+0x90[index]`; an unrelated callback record also has a `+0x30` field. Async population and the dungeon graph builder remain unresolved. A/B/C have new distinct Tasks for those exact next edges.
- D verified an exact-build hierarchy route: `GetNodeNumChildren` at RVA `0x1843DA0`, next-sibling helper at `0x141843CD0`, structure table at manager `+0x70`, and `0x14`-byte records with count `+0`, parent `+4`, first child `+8`, next sibling `+0x10`. A bounded walk can prove scene-graph presence and Room association, not active state or payout. D is implementing the isolated candidate change.
- Runtime project root is `D:\Orca\Temp\NMS-Derelict-Probe-v0.3.75-build-20261015`; its Probe 0.3.46 source SHA-256 `64309747C7F7FB3BD42E139864A13C5A4CC0DD1A9586EC3FB978B46532BDE6B1` matches the installed probe. Main checkout source 0.3.40 is stale for this capture path. No game install or live run has been done.
- Current validation vector remains saved session `20260929T175122Z_0001550006607CAC`: 9 observed room groups and 32/19 authored references, not verified live container instances. Wait for D candidate review/build before asking for a new traversal.
## Live investigation checkpoint - 2026-10-16 22:45Z

- Shipwright remains a verified system-generator harness baseline on NMS.exe SHA-256 `13d5060d4efb9d2a6a6b1b349bc4257231056cc2a055df4bb15d816262cc3499`; it provides no derelict generation evidence.
- Independent join of saved session `20260929T175122Z_0001550006607CAC.json` (SHA-256 `D83AEBB07E4E14E47F5432A7C2175EC3B71C1BC0D061F650D4C1093ADC4019B9`) with `room-crate-index.json` (SHA-256 `B2E1E5C7F4F5273D373FD5DB44049EFB3C84A7C5F6D0F22DC9F2690B93BEF721`) yields nine runtime Room 0..8 groups and 32 CRATEM / 19 FOOT_LOCKER authored refs. D extracted the exact room and prop members from local `NMSARC.EntitySceneMBIN.pak` SHA-256 `58958536E58DFAEB81E0423B5508C7D3DBF3713BAC09E857577FEB275D9F2627`; all 23 room-scene member hashes match the cached raw files. The spacebase prop entities configure both types as `GenericReward / R_ABAND_CRATE` with identical interaction data. This verifies 51 authored rewardable references for that session, not 51 instantiated, active, reachable, or paid-out objects. Detailed offsets and hashes: `research-output/ghidra-static-20261015/ROOM_CRATE_ASSET_CROSSWALK_20261016.md`.
- `NMSARC.Precache.pak` remains SHA-256 `A6371A8B2F065ECA33FD306A16CBE2BACA9D4CE75806C71E42F74E1AB9295032`; D is checking whether current probe hooks can record per-container instance IDs, room parents, and active/present state. B decoded all 18 configured table entries and the serialized list pointer, then began tracing runtime selection/grant. A mapped `GenericReward=10` and continues from type-10 activation state; C traces the manager loader behind a dynamic virtual call at resource slot `+0x80`.
- The saved session's auto-crate result remains `count=0`, `confidence=unproven`, `method=none`; it is unresolved detection, not a zero-container result. Static table probabilities are configuration only; actual selection, quantities, RNG, reward payout, and technology rank are unverified.
- No human action is requested while exact-pak extraction and the bounded static dispatch traces remain executable.

## Previous live investigation checkpoint - 2026-10-16 22:09Z

- Shipwright compatibility remains a harness baseline only. The note is now in commit 9048267 on GitHub main; the recurring backup script includes the note.
- Matching-build container assets configure both square salvage crates and footlockers as GenericReward / R_ABAND_CRATE. Native selection/grant/RNG/rank remain unresolved.
- Cached session 20260929T175122Z_0001550006607CAC.json ties root 00C9E8DF0327789E to live scene nodes Room 0..Room 8, supporting 9 rooms in that session. Its scanner reports 0 containers with confidence unproven; CSV totals 32/19 remain table-validated model output, not live counts.
- FUN_1411001D0 -> FUN_1411015C0 and its callback chain resolve to resource traversal and flag updates, not the room graph builder. The generator topology path remains unidentified.
- A-D are continuing distinct bounded offline tasks: A activation dispatch, B loaded reward-list consumers, C dungeon parameter layout/consumer offsets, D saved-vector provenance. No live game action is needed yet.

## Shipwright Windows baseline â€” 2026-10-16

The existing MIT-licensed Shipwright checkout at `%USERPROFILE%\tools\NMS-Shipwright` (commit `f89691ed037edf437a7406c176aa6b96e654d314`) resolved its function signatures against the local NMS.exe SHA-256 `13d5060d4efb9d2a6a6b1b349bc4257231056cc2a055df4bb15d816262cc3499`. `SystemGen.system` also completed a Unicorn smoke run for valid UA `0000750006606CAB`, returning 50 ship records. This is a star-system harness baseline only; it provides no derelict generation evidence. Full inputs and limits: `research-output/SHIPWRIGHT_WINDOWS_BASELINE_20261016.md`.

## Current research checkpoint â€” RTTI narrowed, generic reward dispatch unresolved â€” 2026-10-16

A targeted scan of the matching executableâ€™s `.text` found five references to `cGcRewardManager` lambda TypeDescriptors; all are tiny RTTI accessor thunks, not reward implementations. The `GiveReward` node type names had no `.text` RIP-relative references. This does not resolve generic reward-table dispatch; continue with bounded container interaction dispatch tracing. Detailed addresses and byte checks are in `research-output/ghidra-static-20261015/REWARD_TABLE_PIPELINE_20261016.md`.
## Current research checkpoint â€” container reward dispatch â€” 2026-10-16

The square salvage crate and footlocker both configure `GenericReward / R_ABAND_CRATE`. Their table config includes ammo, recipes, procedural technology, and other entries; selection and payout behavior remain unresolved. Exact asset hashes and the table fields are recorded in `research-output/ghidra-static-20261015/REWARD_TABLE_PIPELINE_20261016.md`.

On the matching NMS.exe build, raw labels include `TryFirst_ThenSelectAlways`, `RewardChoice`, and `cGcGenericRewardTableEntry`; RTTI contains several `cGcRewardManager::GiveReward...` lambda names. These confirm reward-manager code exists but do not identify the generic table roller. The no-analysis Ghidra project exposes interaction vtables, but targeted string xrefs are absent and must not be interpreted as proof of no use. Continue offline with bounded code references and reward-manager dispatch. No game action is needed for this static trace.
## DUNGEON-C Lane C status â€” 2026-10-10 00:09Z

Lane C reviewed the available executable-matched entry bytes. In the 89-byte entry range `0063A6D0..0063A729`, the call at `0063A706` targets helper stub `033E1B60` (tail destination `033E1A50`). Its return is compared with RBX: equality returns 1, and inequality branches to `0063A722` to compare byte `[RSI+0x295]`. This does not establish a helper role or function name. Full analysis: `agent-patches/dungeon-decompile/CALLBACK_ENTRY_RANGE_REVIEW_20261010.json`.

The primary callback candidate spans three chained `.pdata` ranges totaling 2,430 bytes; the prior 1,180-byte hash covers only its first two ranges. The 23:55:20Z all-saved snapshot has two root events and includes an unrelated stale Oct 5 code-export artifact. The 23:44 80-byte window match does not prove full executable identity. Owner+0x10 remains post-call data, and the raw `FF 52 10` target remains unresolved.

Lane C is now `waiting_on_user` for the missing final chained funclet listing `0063B130..0063BEEC`, which contains table `0063BEBC`. In Ghidra CodeBrowser for the matching executable, press `G`, enter `0063B130`, then copy/export the Listing through `0063BEEC` with addresses, bytes, disassembly, and references to `0063BEBC` into one text file. Success means the listing covers that entire range and identifies executable SHA-256 `13d5060d4efb9d2a6a6b1b349bc4257231056cc2a055df4bb15d816262cc3499`. No Surveyor action, NMS launch, WinDbg, or full traversal is required. Other lanes' pending requests remain intact.

## Seed-Lineage extension and current evidence â€” 2026-10-09 16:20Z

- Seed-Lineage JSON extension 1.0.5 is published directly in the shared extension index, with a 491-character summary. The panel shows actions only while lane status is `waiting_on_user`. The ready build request remains for the primary compiler to include the same files and test in the compiled Surveyor release and complete source ZIP.
- The current automatic pointer names batch `20261009T161519Z-fdc03736`; batch-index SHA-256 `69a195338658155ed8165b7e69abf459b9c904a9fca22d75304e2356a45ed418` and combined report SHA-256 `35e403f79d6e3c665a36f74eee13928dc5a9d77036278604efb1039143076e55` verify. Report `20261009T161520Z-7233c462` has one fresh 000168 root candidate `2139770A2614E3DC`; caller/upstream/seed-function action outputs still cite prior 000155.
- A later runtime-only capture at 16:18:44Z records a different address `00006D0006606CAB`, candidate `A5047E4E4B68F362`, and external return `02C0860A`; it has no executable hash and is not part of that combined report. Its `+0x10` read is zero. The all-saved upload copies the earlier static artifacts, so no matched 00006D caller chain exists.
- The separate exact-root static extraction in the combined report uses NMS.exe SHA-256 `13d506...` and correlates the 16:13 runtime return `02C0860A`; this does not identify a dispatch target. The separate resolver sample and zero `+0x10` remain unresolved.
- MEDI 14 and CARGO 43 remain asset predictions, not physical counts. The next action is the extension's sequential caller â†’ upstream â†’ seed-function chain on the newest saved sample; no NMS launch or full traversal is needed. Python unittest was not run because the local execution helper failed to start; JSON, SHA, panel-limit, index and action-contract checks are being validated before publication.

## Current release â€” Surveyor 0.3.70 parallel saved-session batches â€” 2026-10-09

- Queued saved sessions now run in bounded parallel groups: up to three sessions concurrently, with four isolated research actions for each. Additional queued sessions continue in later waves.
- Each saved session has an independent hash-pinned report and queue/log files in `<project>/research-output/automatic-session-batches/<batch-id>/`. This local device folder is easy to inspect and survives closing NMS.
- If automatic upload is enabled, one batch upload publishes each session report, a batch index, and `research/LATEST_AUTOMATIC_RESEARCH_BATCH.json` to GitHub `main`. Agents verify the pointer and report hashes and keep sessions as separate cohorts. Cloud agents cannot access the PC's local folder directly, so GitHub is the shared path.
- Manual **Parallel research actions** remains a single-run action with its existing `research/LATEST_PARALLEL_ACTION_TEST.json` pointer.
- The caller-code extraction tools continue to honor `NMSDS_NONINTERACTIVE=1`, suppressing Explorer during background research while preserving output selection for direct interactive runs.
- Multi-system root-seed analysis from 0.3.68 remains available: capture root events across different systems in one NMS launch, then use Surveyor > **Multi-system root seed correlation** > **Analyze saved root events across systems + upload**.
- Verification: full suite (225 tests), compileall, and full updater-package integrity checks are recorded in `CANDIDATE_SOURCE.json`; Windows installation validation remains pending.

# NMS Derelict Probe â€” AI handoff

## v0.3.68 multi-system root-seed workflow â€” 2026-10-08

- **Version:** Surveyor source/updater 0.3.68, based on 0.3.67. The batch analyzer is read-only and uses evidence already written by the probe.
- **Capture:** run NMS once and visit different universe addresses. Each `MODELS/SPACE/POI/DUNGEON.SCENE.MBIN` resource-add event is appended and flushed to the current process's `capture-journal-*.jsonl`, including the captured address, system metadata, and primary/secondary seed fields. `root-event-latest.json` remains a compatibility snapshot containing only the newest event.
- **Analyze and publish:** Surveyor > **Multi-system root seed correlation** > **Analyze saved root events across systems + upload**. The action groups events by journal/process and address, reports repeats and collisions, then publishes the report and exact source journals to all four lanes. Pointer: `research/LATEST_ROOT_SEED_BATCH.json`.
- **Report contract:** schema 1, type `root-seed-multi-system-correlation`. Each observation has source journal and line, event ID/time, address, seed candidate, `UseSeedValue`, and descriptor. Three distinct addresses allow an initial comparison, not proof of a general formula. Different process journals remain separate because legacy events lack a verified executable hash.
- **Key files:** `tools/analyze_root_seed_batch.py`, `tools/surveyor_controller.py`, `tools/github_integration.py`, `Analyze-Root-Seed-Batch.cmd` / `.ps1`; tests `tests/test_root_seed_batch.py` and `tests/test_root_seed_batch_upload.py`.
- **Run/tests:** `python tools/analyze_root_seed_batch.py --root <SurveyorDataRoot> --out <report.json>`; `python -m unittest tests.test_root_seed_batch tests.test_root_seed_batch_upload -v`; full regression `python -m unittest discover -s tests -v`.
- **Next action:** capture one root event in each of five different systems during one NMS launch, exit after the last capture, then run the Surveyor batch button once. Agents verify the pointer/report/journal hashes and compare only compatible cohorts. Stop after each root resource is captured; a full derelict traversal is unnecessary.

## Historical handoff notes

## Agent operating contract â€” 2026-10-08

Agents must keep executing their assigned work until a genuine human-only gate remains. At every apparent stopping point, check whether the next useful action can be completed from available code, repository history, uploaded evidence, tests, or tools; if it can, do it. Diagnose failed attempts and try a reasonable fix or fallback. Do not leave an executable agent-owned â€œnext stepâ€ for the user or another agent, and do not stop after an intermediate finding. When the assigned task is complete, continue with the next useful non-duplicative task in the same lane. A dependency blocks only the work that depends on it; continue independent work.

Ask the user only for a required live NMS/PC action, inaccessible local evidence, unavailable credentials/authorization, or information only they can provide. First complete all independent work, then publish a single numbered recipe with the exact Surveyor control/action, success condition, evidence to return, and whether traversal is required. Lane status must say `waiting_on_user` only for such a real gate; otherwise `next_action` names work the agent will perform.

Publish completed, tested, documented lane research and build-request bundles to GitHub `main` under the direct-publish policy, with a backup reference or exact base commit and rollback path. Keep unfinished experiments on the lane branch. Lane authors own their lane status/manifest and affected lane-specific handoff/research records; keep completed main-branch copies synchronized and update `WORKSPACE_STATE.json` and relevant handoff sections when lane facts or shared research pointers change. The primary integration assistant alone compiles shared Surveyor/updater releases from ready build requests. When project/source files change, update this handoff and include a complete current source ZIP. See `AGENT_START_HERE.md`, `AGENT_WORKFLOW.md`, and `build-requests/README.md` for the detailed contract.

## METADATA-D room-group reconciliation â€” 2026-10-08

The latest pointer is `research/LATEST_PARALLEL_ACTION_TEST.json`; its report is `research-uploads/20261008T195856Z-parallel-action-test/combined-results.json`, SHA-256 `b74d988e78f4001f870980e47776e77ddf3f14f97e5d8cfd4a9fde3c501dcd41`, run `20261008T195817Z-1b73e442`. The hash was recomputed from the report bytes and matches the pointer. This is an isolated manual-button reanalysis of saved session `20261008T185119Z_0001550006607CAC`, not a fresh live capture. It infers MEDI_FLOATERS with 10 analyzer parent-key groups versus static `Rooms=7`; 14 targets are asset-predicted, not observed.

The earlier CARGO_FLOATERS run remains authoritative for its own run: `20261008T140207Z-d8e24197`, report SHA-256 `11ec9ee30687570efda334a255ea27836bfb347d8bf7631ec4ffae981e9175f6`. It reports 8 CARG-dominant, 2 BARRACKS-dominant, and 1 END-dominant parent-key groups (11 total). Its 43 targets (30 salvage + 13 footlockers over 164 resolved scenes) remain an asset-derived prediction, separate from physical observations.

Static CARGO_FLOATERS has `Rooms=7`, five main IDs (`R_END`, `R_FLO_BARR`, `R_S_FLO_BARR`, `R_FLO_CARG`, `R_S_FLO_CARG`) and two branch IDs (`B_FLO_BARR`, `B_FLO_CARG`). Exact-count rules require one each of `R_FLO_BARR`, `R_S_FLO_BARR`, and `R_END`; `R_END` has minimum index 6. The two BARRACKS-dominant groups and END group at index 10 are only numerically compatible with those constraints. Eight CARG-dominant groups cannot be assigned among the two CARG main IDs and one CARG branch ID from family labels or `Room N` names.

The current DUNGEON-C branch `agent/dungeon-current-target-20261008-reconciled` (commit `1904a3c381889ed1c0418ee91ebd38b571c914d1`) records a separate user-reported 11-room traverse but has no per-room RoomId crosswalk in its manifest, status, or tracked mapping artifacts. Therefore the 7-versus-11/10 difference remains unresolved: parent-key grouping/classification may contribute, but generator semantics are not established. See `agent-patches/metadata/ROOM_MODEL_RECONCILIATION_20261008.json`.

## v0.3.67 publication record â€” 2026-10-08

Surveyor v0.3.67 and its full updater package are published on `main`. The release recovers unprocessed saved sessions at startup, checks exact source hashes against prior automatic reports, and runs each unprocessed session separately in FIFO order. The updater manifest points to 37 package chunks; each remote chunk was checked against the verified local package. Package SHA-256: `2a00db2de00b09f6b89685c0f0e302b731a0db0097a658d8242c249d524e5ca0`. Local verification: 210 unit tests, compileall, harness self-test, and ZIP/member/index/hash checks passed. Backup branch: `backup/main-before-saved-session-backfill-20261008` (based on main `fb1edd38c94774b3f4be08a198702840d1bdf559`). Windows backlog execution remains pending.

## Startup recovery for saved-session research â€” 2026-10-08

The first queue fix restored persisted pending items but could not recover sessions queued by older builds, because those builds did not save the queue. Surveyor 0.3.67 now scans saved session JSON files on startup, verifies each file and its ended state, and queues files that lack both a persisted queue record and an automatic combined report with the same SHA-256. It orders recovered sessions by ended time and records any exact-hash prior report as already processed. This allows sessions from the earlier in-memory queue to be recovered after updating, while avoiding duplicates for the one session represented by the existing report.

The queue continues one report per saved session, persists queued work across restart, and checks the source hash again in each worker. Automated tests cover recovery, ordering, duplicate prevention, report pinning, and FIFO execution.

## Saved-session queue correction â€” 2026-10-08

The latest verified combined report covers one source session, `20261008T185119Z_Uzawan_XI.json`; it does not establish that the other two sessions in the user's queue ran. The expected behavior is one separate research run and combined report per saved session, processed sequentially.

The source fix is now on main in `tools/surveyor_controller.py` and `tools/test_parallel_research_actions.py`. It persists the FIFO queue across restarts, pins each worker to its triggering session file, verifies the session SHA-256, and rejects completion if the report trigger hash does not match. Regression tests cover queue order, persistence/recovery, session pinning, and stale-report rejection. Local verification: 206 unit tests passed, Python compileall passed, and the harness self-test passed.

The v0.3.66 updater package now includes the queue fix and current indexed extension files. The previous package defects were fixed: Seed Lineage 1.0.3 was added to the managed payload, Runtime-Dispatch tests target 1.0.6, and the truncated test source was repaired. Full Windows end-to-end queue validation remains pending.

## Runtime-A system-scoped root seed capture â€” 2026-10-08

Probe 0.3.40 closes an active capture and clears live root-seed/caller buffers when the observed nonzero universe address changes. It accepts a root capture into a session only when its capture address matches that session. Seed evidence reports the raw value, UseSeedValue, and effective state separately. The user's system-switch observation and F-pattern remain separate from the parallel-action data; without that run's UseSeedValue field, the F-pattern cannot be classified.

The current main pointer names run `20261008T195817Z-1b73e442` at `research-uploads/20261008T195856Z-parallel-action-test/combined-results.json`; the report SHA-256 `b74d988e78f4001f870980e47776e77ddf3f14f97e5d8cfd4a9fde3c501dcd41` matches the pointer. This was an isolated manual parallel test with an input snapshot and no retained worker data; 8/9 actions completed and the upload action was skipped. The report analyzes saved session `20261008T185119Z_0001550006607CAC`, not a fresh live capture. It reports one root-seed candidate `00C9E8DF0327789E` with `UseSeedValue=true`; derivation remains unproven. `MEDI_FLOATERS`, 146 scene instances, and 14 targets (7 salvage + 7 footlockers) are analysis/prediction results, not an observed physical container count. Keep the separate 43-target `CARGO_FLOATERS` asset prediction (30 + 13 across 164 scenes) distinct from both 14 and all observed counts. The caller extraction decodes `02C08607: FF 52 10` returning at `02C0860A`, but `target_rva_hex` is null. The report's resolver action tests a different callsite (`02C04977` / return `02C0497A`) against stale candidate `00634BC0` and finds zero matches; it does not resolve the `02C08607` target. The report's upstream-callers action cites older session `20261006T223811Z_0001BF0004E84EFD` / seed `5B4AE67D9C2A8F61`; do not join it to the fresh `00C9` event. The separate signature/caller correlation to `0063A6D0` remains distinct evidence and is not inferred from either zero result.

Focused system/seed tests and package integrity checks passed in GitHub Actions. Normal NMS system-switch verification remains pending.

## Runtime-A latest dispatch correction â€” 2026-10-08

The Oct 8 16:37 combined report remains the sole authority for that run (8 complete, 1 upload skipped, offline saved-evidence analysis, no NMS attach): `research-uploads/20261008T163844Z-parallel-action-test/combined-results.json`, SHA-256 `7eb7c6a62ee5a909d0e0f12df0890ac3653a73fa66ae11f51e0c651dc571994c`. Its raw `logical_entry_rva=00634BC0` field reflects a stale source constant.

The probe registers its hook by `@static_function_hook(signature=...)`; `CURRENT_BUILD_LOGICAL_ENTRY_RVA` is only written into evidence metadata. The user's read-only scan verified the NMS.exe SHA-256 `13d5060d4efb9d2a6a6b1b349bc4257231056cc2a055df4bb15d816262cc3499` and found one signature match at `0063A6D0`. DUNGEON-C's saved static artifact independently records that hook location and the .pdata range `0063A6D0..0063A729`.

The matched 16:31:47.935Z root event records caller return `02C0860A` after `02C08607: FF 52 10`. The unique signature-matched BEFORE hook resolves this event's dispatch destination to `0063A6D0`. Source labels `00634BC0` and `00634C63` were stale and are corrected to `0063A6D0` and `0063A773` in probe 0.3.39. Function semantic identity remains unresolved.

The owner+0x10 zero remains an unresolved after-call capture/data inconsistency, not a target. The separate resolver call `02C04977` is unrelated. The unresolved-preset zero output is not a physical count. The 43-target figure (30 crates + 13 footlockers over 164 scenes) remains a distinct asset-derived prediction, separate from historical 35 and post-update 16 counts. No WinDbg or live NMS action was used.

Review: `agent-patches/runtime-dispatch/RUNTIME_A_HOOK_TARGET_CORRECTION_20261008.md`. Published to `main` in merge commit `373a5e8247823ab5c1a5955d31c70bc25bb610e9` (PR #51); registry now points to extension 1.0.6. The five focused address/evidence assertions were checked against the branch files and all passed; the Python unittest itself was not run because the local command runner is unavailable. Backup: `backup/main-before-runtime-a-signature-correction-20261008-1820` at `7b62524a018c52801084548d21b47b771683cc38`. Workspace state was synced in `ed1c3108661d5ea90636174c122feb89ee2911eb`.

## DUNGEON-C Oct 9 combined-report review â€” 2026-10-09

The current manual pointer selects run 20261009T163626Z-9056847b, report research-uploads/20261009T163702Z-parallel-action-test/combined-results.json, SHA-256 816587755486c772fa03efbb0461f7983bc196bf149eb90b1588024f6a54f439; the report bytes were hashed and match the pointer. It is an isolated manual-button offline run (8 complete, 0 failed, 1 upload action skipped), with no new NMS event. The separate automatic pointer selects batch index research-uploads/20261009T163525Z-automatic-research-batch-20261009T163434Z-bf1ed756-3b9b70/batch-results.json, SHA-256 4ae5af8f6814e14d1e5e16ca1eeeaf455599b1e22d47286ba01e2b513f3f25cd; that index and its per-session report research-uploads/20261009T163525Z-automatic-research-batch-20261009T163434Z-bf1ed756-3b9b70/reports/20261009T163435Z-b91c6dbb/combined-results.json (SHA-256 fb7126c475d65d0e764d802b74ed6a6ca99c56fb72d75c65da9e0e3f6335f1f4) were verified. That saved-session run is a separate cohort (7 complete, 1 failed, 1 upload skipped); the metadata asset-preparation action failed, while D's exact-caller, upstream, and resolver actions completed. The two reports carry identical D artifact hashes, so this is repeated offline processing of the same embedded evidence, not two independent runtime captures.

The exact-caller artifact records the 2026-10-09 16:18:44.420Z event, descriptor 0000022ADFB4A928, candidate root seed A5047E4E4B68F362, NMS.exe SHA-256 13d5060d4efb9d2a6a6b1b349bc4257231056cc2a055df4bb15d816262cc3499, and 02C08607: FF 52 10 returning at 02C0860A. Its logical_entry_rva_hex metadata is 0063A6D0, but the decoded call has target_rva_hex=null and no pre-call [RDX+0x10] sample. Treat the entry metadata as event association; direct target proof and callback identity remain unresolved. The zero owner+0x10 value is post-call and does not resolve the slot.

The upstream-scan artifact cites older session 20261008T185119Z_0001550006607CAC and seed 00C9E8DF0327789E; it is not joined to the Oct 9 descriptor. The vtable resolver tests 00634BC0 at the distinct callsite 02C04977 / return 02C0497A and finds zero matches; this neither resolves nor disproves the 02C08607 call. Keep the asset-derived 43-target prediction separate from physical observations, and preserve historical 35 and post-update 16 as separate records. WinDbg remains ruled out because the user reports that it crashes NMS; no debugger or live game was used.

Review: agent-patches/dungeon-decompile/PARALLEL_REVIEW_20261009.json. Continue with offline caller/callback and generator-consumer analysis; no D-lane user action is required for this evidence review.

## DUNGEON-C reconciled with Runtime-A dispatch evidence â€” 2026-10-08

The D status and manifest had remained on the 14:02 report and described runtime dispatch as unresolved. Reconciliation uses current main's Runtime-A review plus the pointer-selected 19:58 combined report. The latest pointer names run `20261008T195817Z-1b73e442`, report `research-uploads/20261008T195856Z-parallel-action-test/combined-results.json`, SHA-256 `b74d988e78f4001f870980e47776e77ddf3f14f97e5d8cfd4a9fde3c501dcd41`; a downloaded copy was independently hashed and matches the pointer. That combined report is the sole result source for this run: isolated offline test, 8 complete, 0 failed, 1 upload action skipped, and no fresh NMS event. Do not substitute queue or per-action latest files.

The report's D actions extracted exact root caller and upstream caller artifacts and ran the exact-root-vtable resolver. That resolver queried stale target label `00634BC0` and found zero matches. This scoped result does not override Runtime-A's separate signature-matched BEFORE-hook correlation for descriptor `000002752ED7F928` at `2026-10-08T16:31:47.935Z`: on the SHA-matched executable, the unique hook signature is at `0063A6D0`, and the event's caller return `02C0860A` follows `02C08607: FF 52 10`. The effective destination is resolved to `0063A6D0` for that event only. The raw `[RDX+0x10]` slot was not separately read, and the callback's semantic identity remains unresolved.

D's static call at `0063A706` inside the callback reaches stub `033E1B60`, which jumps to `033E1A50`; this is an internal direct helper call, not the indirect dispatch destination. The zero `owner+0x10` read remains unrelated and unresolved. The 43-target (30 salvage + 13 footlockers) figure remains an asset-derived prediction, distinct from the historical 35-container baseline and post-update 16-target model. The user reports WinDbg crashes NMS, so D will not repeat that method. D continues offline semantic analysis using the published matching-build callback and caller artifacts; no live gameplay/traversal is requested.
## Prior DUNGEON-C Oct 8 report reviews â€” 2026-10-08

The Oct 8 combined report was read from the user-provided local 0.3.62 candidate, and its bytes match the pointer SHA-256 12035c7362e77363af084bc24254c7b013edecba6ca9015f1d3c6985ea527eda. The attached candidate and its 13:02 run report are not published on main; DUNGEON-C did not publish or replace either shared file. GitHub main has since received a separate 13:43 combined report, now referenced by research/LATEST_PARALLEL_ACTION_TEST.json; its SHA-256 3af46d71fbeabc5810f3c83dbdd93b59cc2cfd71358dbaa6bb9c35c398e38592 was verified against the main-branch report bytes. Each combined report is authority only for its own run: both report 8 saved-evidence offline actions, upload skipped, and no NMS attachment or new capture.

The report's current caller is 02C08607: FF 52 10 / return 02C0860A. The separate resolver input is 02C04977 / 02C0497A and returns zero matches for 00634BC0; do not combine the samples or infer the target. Keep the 43 asset-derived prediction distinct from both the historical 35-container measurement and separate post-update 16-container observation.

DUNGEON-C rechecked its saved 89-byte 0063A6D0 hook body: its verified hash still matches, and bytes at 0063A706 encode an E8 rel32 destination of 033E1B60, followed by cmp rax,rbx and a conditional branch. The existing export lists zero direct-call candidates, so the inconsistency is recorded without assigning semantics. RVA 033E1B60 has no verified .pdata range/body because the matching executable is absent from the repository and standard checked game paths. Review: agent-patches/dungeon-decompile/PARALLEL_REVIEW_20261008.json.

Next D action: provide NMS.exe with SHA-256 13d5060d4efb9d2a6a6b1b349bc4257231056cc2a055df4bb15d816262cc3499, or a hash-matched export containing .pdata and code at 033E1B60. No live NMS session or traversal is needed for that offline validation.
# NMS Derelict Probe â€” AI handoff

## Seed-B review of main's 14:02 combined report

Main pointer run `20261008T140207Z-d8e24197` and report `research-uploads/20261008T140254Z-parallel-action-test/combined-results.json` were hash-verified (`11ec9ee30687570efda334a255ea27836bfb347d8bf7631ec4ffae981e9175f6`). The eight completed actions analyzed saved evidence offline; upload was skipped and the parallel run did not attach to NMS. Its generation artifact contains a saved root event from `20261008T140041Z_0001BF0004E84EFD`, timestamped 14:00:37Z, with descriptor `0000021C2457DD28`, owner `0000021C2457DC00`, and root seed candidate `5B4AE67D9C2A8F61`. The direct Engine caller is `0063AC20` -> `0183E770`. A separate logical-entry event from that saved trace is `02C08607: FF 52 10` / return `02C0860A`; owner+0x10 was read after the external call and at root add, both zero. Dispatch target and seed derivation remain unproven.

The asset analyzer infers CARGO_FLOATERS at high confidence and predicts 43 target containers (30 salvage, 13 footlockers) across 164 scene instances / 11 logical chunks. The 43 is asset-derived, not a measured physical count. POI generation receives the universe address as a raw argument, while its return is the component address; no root seed transformation is demonstrated. Caller-code and upstream results in the report use older source sessions and must not be joined to the fresh saved event as one trace.

Seed-Lineage extension 1.0.3 requests existing shared Surveyor actions in sequence: Extract caller code, then Extract upstream callers. The next human request is to refresh the extension, record a fresh root event in universe `0001BF0004E84EFD`, run those actions, and return both run manifests. No traversal is required. Full lane analysis: `agent-patches/seed-lineage/SEED_B_PARALLEL_REVIEW_140207_20261008.md`.

## Runtime-A Oct 8 combined report review

The supplied local v0.3.62 candidate's pointer/report for run `20261008T130233Z-755d4c43` were verified (report SHA-256 `12035c7362e77363af084bc24254c7b013edecba6ca9015f1d3c6985ea527eda`). This remains a local candidate and is not the current `main` pointer. The latest `main` pointer now names run `20261008T140207Z-d8e24197`, report `research-uploads/20261008T140254Z-parallel-action-test/combined-results.json`, SHA-256 `11ec9ee30687570efda334a255ea27836bfb347d8bf7631ec4ffae981e9175f6`, verified against the report bytes. Its eight actions are offline reanalysis, upload was skipped, and the harness did not attach to NMS. Its saved-evidence snapshot includes a root event timestamped `2026-10-08T14:00:37.544Z`; the report does not establish how that event was captured. Neither shared pointer nor report was changed by Runtime-A.

The saved current caller is `02C08607: FF 52 10`, return `02C0860A`. In the latest report's saved event, the probe's logical-entry snapshot is after the external call; owner+0x10 is zero at entry and root-add, so the target remains unresolved. The resolver result is a separate sample at `02C04977`, return `02C0497A`, with zero offline vtable matches for candidate `00634BC0`; it does not resolve the current call. Asset analysis predicts 30 crates plus 13 footlockers (43 predicted targets) across 164 scene instances. This prediction is not an observed physical count and does not replace the historical 35-container measurement or post-update 16-container observation. See `agent-patches/runtime-dispatch/RUNTIME_A_PARALLEL_REVIEW_20261008.md` and the lane manifest for provenance and limits.

The latest saved event already repeats the post-call zero read. The remaining Runtime-A step is a pre-instruction observation at `NMS.exe+02C08607` (`FF 52 10`), recording `RDX` and `[RDX+0x10]` before execution; verify NMS.exe SHA-256 `13d5060d4efb9d2a6a6b1b349bc4257231056cc2a055df4bb15d816262cc3499`. A debugger capture at one root event is sufficient; no full traversal is needed. The data-only panel is version 1.0.3 and preserves 1.0.2 for rollback. Probe/app code did not change.

### Runtime-A debugger recipe (superseded)

The previous WinDbg breakpoint recipe is withdrawn. The user's WinDbg attachment stalled or crashed NMS, and the saved output showed no breakpoint hit or slot capture. Do not repeat it. Runtime-A's only pending user check is the normal Surveyor system-switch validation described above; no debugger is needed.

The captured zero is owner+0x10 after the call, not a pre-call `[RDX+0x10]` target. The signature/caller correlation to `0063A6D0` is separate evidence; the latest combined report's caller decode still has no target RVA, and the `02C04977` resolver sample is unrelated. No further WinDbg capture is requested.

## DUNGEON-C helper dataflow â€” 2026-10-05

The current-build parent conditionally processes four nonzero 32-bit fields in the order `RSI+0x50`, `+0x58`, `+0x54`, `+0x5C`. Each follows a retain-like helper, appends the value to a 32-bit resizable list at `RSI+0x40`/`+0x44`/`+0x48`, and then follows a release-like helper. The exact instruction evidence and `.pdata` limitations are in `agent-patches/dungeon-decompile/HELPER_DATAFLOW_20261005.json`. Field meanings, list consumers, and the actual indirect callback destination remain unproven.

## DUNGEON-C updated executable map â€” 2026-10-05

The installed NMS.exe changed after the earlier runtime captures (current SHA-256 `13d5060d4efb9d2a6a6b1b349bc4257231056cc2a055df4bb15d816262cc3499`). Offline byte matching and PE unwind ranges map the old bounded parent `00634930..00634E03` to current `00636760..00636C33`; its old hook offset maps to `006369F0`. The indirect caller bytes `FF 52 10` map from `02C04977` to `02C08607`. All 33 decoded direct calls retain the same position relative to the parent and map to seven current targets. See `agent-patches/dungeon-decompile/CURRENT_BUILD_STATIC_MAP_20261005.json` for the target table and hashes.

These are static cross-build mappings, not a new runtime root event or proof that `[RDX+0x10]` resolves to the mapped parent. Use current-build RVAs only with the matching executable; retain the earlier runtime and gameplay evidence as historical.

## DUNGEON-C helper export review â€” 2026-10-05

The offline helper export and shared upload are complete. The newest shared batch is `research-uploads/20261005T014820Z-all-saved-evidence-a065a8b5/`; its 01:03 root event and code export have matching descriptor `000001DCBF948128`. The 23:17 event was also exported separately for local review with matching descriptor `0000015E2450A928`; it was not the later shared batch's latest event.

DUNGEON-C validated all 20 exported callsites against its 33-site decoded inventory and independently decoded their instruction boundaries. Five helper bodies match their declared byte counts, SHA-256 hashes, and `.pdata` ranges. The other 13 decoded calls reach a small `ret 0` leaf (12) and a `VCRUNTIME140.dll!memcpy` import thunk (one). See `agent-patches/dungeon-decompile/HELPER_EXPORT_REVIEW_20261005.json`. The indirect `FF 52 10` destination remains unproven; `00634BC0` is the runtime-correlated hook RVA within `.pdata` range `00634930..00634E03`, not that range's start. The historical 35-container baseline, earlier 16-target prediction, and user's newer physical layout/count confirmation remain separate.

No further offline export or derelict traversal is needed for this step. The next DUNGEON-C work is static helper dataflow analysis; proving the indirect callback destination requires a later live slot/register capture in the runtime-dispatch lane.


## Current crash-recovery update â€” 2026-10-05

The current published base is Surveyor **0.3.59**, built from v0.3.58. The working update is Surveyor **0.3.60** with probe **0.3.38**. It appends and flushes each trace event to a per-process JSONL journal, fsyncs root events immediately and other records in bounded batches, persists every dungeon root event (seed and universe metadata included) even if exact caller or `+0x10` capture is unavailable, and adds these artifacts to deduplicated Upload all saved evidence. With automatic uploads enabled, root evidence uploads after a short debounce and changed journal evidence is batched every 30 seconds, including after a successful slot capture. Pending root evidence remains distinct from a successful slot capture. Session snapshots remain periodic and are atomically flushed before replacement. The Linux test suite passes; Windows UI and live NMS validation remain outstanding.

The game must still be running while an event occurs for a runtime hook to observe it. Once observed, the journal and root-event artifact are local durable files and can be uploaded after the game exits or crashes. Automatic sharing follows the existing remembered auto-upload toggle.

## Historical Runtime-A candidate â€” 2026-10-04

This was the recorded 0.3.57 investigation state before the current v0.3.58 package was published. The old base-version and candidate notes below are retained as historical context.

Runtime-A probe 0.3.37 now combines the existing shared-entry owner+0x10 capture with RCX/RDX and raw [RDX+0x10] capture at that same entry hook. The later root-add sample remains separate. The lane patch and manifest must state the official package SHA-256 and the embedded base probe version (0.3.35).

Surveyor v0.3.58 and probe 0.3.37 were the previous published base. v0.3.59 / probe 0.3.38 is now published; v0.3.60 keeps the same probe.


## Current state

- Current package: **v0.3.60 candidate**. It retains the nested-frame startup fix, automatic upload toggle, and existing v0.3.58 behavior while adding crash recovery.
- **Automatic GitHub evidence uploads** are controlled by a remembered checkbox under GitHub / updates. Enabled by default: a new persisted root capture is uploaded automatically, and after a research or lane action the Surveyor uploads a deduplicated all-lanes evidence batch if its contents changed. The lane-specific action upload remains part of its explicit action workflow. Uncheck the option to stop background root and shared-batch uploads; manual uploads remain available. The all-lanes fingerprint receipt is stored under `%LOCALAPPDATA%\NMSDerelictSurveyor`.
- **Upload all saved evidence** snapshots every existing research output declared by `ACTION_OUTPUTS` into one deduplicated `research-uploads/<timestamp>-all-saved-evidence-<id>/` folder on `main`. Its manifest lists which actions produced each file and marks it visible to all four lanes. The Surveyor writes a receipt to each lane card after success. This is a shared repository upload, not an automatic agent notification or a write to their status branches.
- Overlapping local `*-latest` outputs: `generation-baseline-latest.json` (measure/analyze-generation), `generation-measurements-summary.json` and `generation-measurements.csv` (measure/compare-measurements), `seed-room-correlation.json` (measure/analyze-correlation), and `exact-root-caller-latest.json` (analyze-generation/Runtime-A upload). Local latest files are replaced by a producer rerun; GitHub uploads are timestamped snapshots.
- Runtime-A can now upload its already-persisted root event after closing NMS via **Upload captured root event**; this panel action needs only the saved capture and an idle Surveyor workflow.
- Current source package: **v0.3.60 candidate**. Probe **0.3.38** preserves exact root caller and entry register capture, and now writes root-event recovery data even when caller correlation or the slot read is unavailable. Capture still requires NMS running while the event occurs; saved artifacts can be uploaded after quitting. Surveyorâ€™s app updater stages the probe into the installed MODS folder; fully restart NMS after installing the app update.
- Surveyor does not redistribute DerelictFreighterFarming files. Download your own archive and use **Install Derelict Farming archive** in the GitHub / updates section. The installer accepts only three expected EXML files, validates their XML, stages them under `GAMEDATA/MODS/DerelictFreighterFarming`, and preserves conflicts. Roll back with `python tools/github_integration.py rollback-derelict-farming`. The supplied archive targets 7.04; NMS 7.05 behavior is not yet validated.
- Agent Console has four side-by-side lane cards. The fixed **NEEDED** box shows the published request, actual extension action, exact required prerequisite keys, and which prerequisites are currently missing. It does not contain generic step guidance. The actual host key is `probe.connected` (fresh probe heartbeat), not `probe.running`; the v1 extension contract is unchanged.
- Installed/published/reported versions remain immediately under NEEDED. Each evidence receipt checkbox stays fixed below its lane buttons.
- Compact top-right +/âˆ’ controls collapse each major main-window section, each Agent Console card, lane action groups, and global action group. The controls and content begin expanded; lane/global buttons remain pinned in the bottom strip. Agent Console display toggles and refresh interval persist in `%LOCALAPPDATA%\NMSDerelictSurveyor\agent-console-options.json`.
- Auto-refresh defaults to one minute; choices are 20 seconds, 2 minutes, 5 minutes, or Off. **Refresh now** fetches status and extension index immediately. Network reads run on background threads; cache-busted lane status requests remain read-only.
- Polling reuses unchanged extension widgets and action readiness uses the main windowâ€™s latest NMS/probe status instead of launching new process checks per lane, keeping scroll position stable and refresh work lighter.
- The overlay display toggles now live in the main Surveyor window; opacity and horizontal/vertical placement sliders apply live. Agent objectives come from the published status snapshot, and the overlay shows root-detected completion plus â€œwaiting for upload / donâ€™t close gameâ€ where applicable. `Root dispatch +0x10` now reports the raw slot value and best-effort module identity when a read succeeds; its meaning remains unproven until live evidence is reviewed.
- Main Status and the in-game overlay now show the exact root resource path and observed event count. `Root dispatch +0x10` is shown separately and uses the capture field emitted by Runtime-A probe 0.3.34.
- **Start overlay** and **Stop overlay** sit beside the existing **Game overlay** auto-start toggle. Stop closes the titled overlay window and signals the local stop-request file, including overlays started by the NMS launcher.
- The package carries DUNGEON-C 1.0.2, Metadata-D 1.0.1, Runtime-A 1.0.1, and Seed-B 1.0.2, with prior installed versions retained for rollback. The Runtime-A panel stays data-only; its analyze/upload action is unchanged.

## Purpose and architecture

Reverse engineer No Manâ€™s Sky abandoned-freighter generation using static and runtime evidence while keeping Surveyor independent from the game. `tools/surveyor_controller.py` is the Windows Tk app and action host; `mod/derelict_baseline_probe.py` collects read-only process evidence; `overlay/derelict_overlay.py` formats live status. `tools/agent_console.py` reads public GitHub lane status. `tools/agent_ui_extensions.py` validates and installs data-only JSON panels.

## Contracts, configuration, and diagnostics

- Start with `Start-Surveyor.cmd` / `Start-Surveyor.ps1`; Surveyor can run independently of NMS.
- Agent status uses schema v1 (`schema/agent-status-v1.schema.json`) from `agent-patches/<lane>/STATUS.json`; optional progress, blockers, extension version, and human-action fields are backward-compatible. Agent lanes publish status commits at meaningful milestones.
- Extension panels use shared UI host API 1.0 and hash-checked `manifest.json`/`panel.json` entries indexed by `agent-ui/extensions/index.json`. Extensions may call only registered host action IDs; no supplied shell or Python runs. Receipts are display-only and never lock actions.
- Session/live status schemas and probe/overlay command protocol remain v1. No data migration is required.
- Controller and workflow logs: `%LOCALAPPDATA%\NMSDerelictSurveyor\gui-actions\`; live status: `%LOCALAPPDATA%\NMSDerelictSurveyor\live-status.json`.
- Agent Console settings remain in its local options JSON. Overlay display settings live in `%LOCALAPPDATA%\NMSDerelictSurveyor\overlay-settings.json`; the current objective snapshot is `overlay-objectives.json`.

## Build, run, and test

- Windows with Python 3.12/3.13 and Tkinter; launch `Start-Surveyor.cmd`.
- `python -m compileall -q tools overlay tests`
- `python -m unittest discover -s tests`
- In Agent Console use **Refresh now** for an immediate poll or select **Off** to pause automatic status and extension checks.

## Latest changes and verification

- v0.3.57 fixed the startup `TclError` caused by mixing `pack` and `grid` in the GitHub / updates body.
- v0.3.56 adds a persistent auto-upload toggle. When on, saved Runtime-A captures upload automatically and changed all-lanes evidence is published after research/agent workflows. Batch fingerprints prevent repeated uploads of identical saved files.
- v0.3.54 persists the complete runtime root event, metadata, and universe address in the existing atomically saved/uploaded capture artifact; schema and upload path remain compatible.
- v0.3.48 adds main-window overlay display controls, live opacity/position settings, and published agent objectives. v0.3.47 adds visible root-resource and dispatch-capture status plus manual overlay lifecycle controls. v0.3.46 shows exact prerequisites and missing state in NEEDED, adds per-section +/âˆ’ controls in both windows, and uses cached game/probe state for action readiness.
- `python -m compileall -q tools overlay tests mod` and the full unittest suite passed for v0.3.51 (173 tests). Windows pyMHF/NMS live validation is still required for the new capture.
- Runtime-Aâ€™s new capture implementation is present in probe 0.3.34, but live Windows/NMS validation and semantic interpretation remain pending; exact-root-caller output alone is not proof of a slot read.

## Rollback and next action

- Roll back the app by reinstalling the previous complete v0.3.49 package. Roll back the installed farming mod with `python tools/github_integration.py rollback-derelict-farming`. No probe, session, extension API, or saved evidence migration is needed. Extension versions retain their individual rollback controls.
- **Next action:** update Surveyor, select your downloaded mod ZIP with **Install Derelict Farming archive**, fully restart NMS, then test repeat derelicts in the same system. Confirm `+0x10` remains pending until a real capture is reported.


## Seed-B review of latest combined report (2026-10-08 18:53 UTC)

Main pointer run `20261008T185304Z-e95aae15` references `research-uploads/20261008T185341Z-parallel-action-test/combined-results.json`, SHA-256 `9576e887375b1d79ad629b07a26209337479ff6cf096222207de4c53a130dcbe`; fetched report bytes match the pointer. This combined report is the sole source used for this parallel run's results. The parallel run was isolated/offline, used an input snapshot, retained no worker data, and marked `research.upload_runtime_capture` `not_run_upload_disabled`.

The generation artifact derives from session `20261008T185119Z_0001550006607CAC`, universe `0001550006607CAC`. It records one root `DUNGEON.SCENE.MBIN` event at `2026-10-08T18:51:04.549Z` with root-seed candidate `00C9E8DF0327789E`; derivation remains unproven. The analyzer infers `MEDI_FLOATERS`, 10 logical rooms and 146 scene instances, and predicts 14 target containers (7 salvage + 7 footlockers) from assets. This is not a physical count and is separate from the earlier `CARGO_FLOATERS` asset-derived 43-target prediction (30 salvage + 13 footlockers).

Seed-Lineage caller output cites older session `20261006T223811Z_0001BF0004E84EFD`; upstream output cites `20261004T151219Z_0001BF0004E84EFD`; seed-function analysis cites `20261002T213047Z_00001A0004E84EFD`. Do not join these offline results to the fresh root event. Static extraction decodes `02C08607: FF 52 10` returning at `02C0860A`, but does not resolve its target. The zero-match resolver sample at `02C04977` / `02C0497A` is a separate callsite.

Next: on shared main Surveyor, close NMS if open, use RUNTIME-A 1.0.6 **Upload captured root event**, then Seed-Lineage 1.0.3 **Extract caller code + upload** and **Extract upstream callers + upload** in order. Verify the caller cites fresh session `20261008T185119Z_0001550006607CAC` and the hash-matched executable, and verify upstream cites that caller. No new NMS launch or traversal is needed if the saved capture remains available. Full lane review: `agent-patches/seed-lineage/SEED_B_PARALLEL_REVIEW_185304_20261008.md`.

## Surveyor source candidate 0.3.64 (2026-10-08)

# NMS Derelict Probe â€” AI handoff


Windows UI/focus and live end-to-end queue validation remain pending. Source and the v0.3.66 updater package are published on `main`.


## Runtime-A reconciliation and next action â€” 2026-10-08

The verified current report and callsite/counter caveats are recorded above and in `agent-patches/runtime-dispatch/RUNTIME_A_MANIFEST.json`. The indexed Runtime-A extension remains 1.0.6; its existing panel already separates the `0063A6D0` signature/caller correlation from the zero post-call slot and unrelated resolver sample, so no extension or index hash change was needed. Probe 0.3.40's system-boundary reset is covered by focused tests and package integrity checks in GitHub Actions; the only remaining check is a normal system switch in Surveyor 0.3.67 with Runtime-A 1.0.6. No full derelict traversal or debugger is required. See the lane `STATUS.json` for the exact steps and evidence to return.


## Seed-B reconciliation â€” current combined run and later lane evidence (2026-10-08 23:36 UTC)

The current parallel pointer references run `20261008T195817Z-1b73e442` at `research-uploads/20261008T195856Z-parallel-action-test/combined-results.json`, SHA-256 `b74d988e78f4001f870980e47776e77ddf3f14f97e5d8cfd4a9fde3c501dcd41` (verified). That isolated report is authoritative for its run: 8 actions completed, 0 failed, upload skipped; fresh caller/session `20261008T185119Z_0001550006607CAC`; the parallel upstream and seed-function actions used an older common snapshot. Later separate caller and upstream uploads at 21:39 UTC hash-verify and cite the fresh session/executable. Upstream reports descriptor +0x128, seed +0x138, use-seed +0x140, seed read before root AddResource; the derivation is still unknown. The all-saved 21:40 seed-function artifact is stale (Oct 2 and old executable hash). The 14 MEDI targets and separate 43 CARGO targets are asset predictions, not physical counts. Zero +0x10 and the separate resolver sample remain unresolved. Current panel 1.0.4 runs caller â†’ upstream â†’ seed-function sequentially. Next human gate is one root event at a third universe address; no full traversal is required. See `agent-patches/seed-lineage/STATUS.json` for steps.

## METADATA-D uploaded archive review â€” 2026-10-09

The uploaded `dungeon.zip` is on main at blob `ce8ca51535db34165cd72477ab7b9ae9c94a86fa` (9,733,369 bytes; SHA-256 `5ef8b70e92e8923ce8dac3c96c055f52841dc831516bbb35f976b8c265196c60`). All 2,866 file entries, including binary files, were read and searched for ASCII/UTF-16 `R_*`/`B_*` room IDs and `RoomId`, `DungeonOptions`, or `DungeonRootScene` fields; there were no matches. The ZIP contains scene/model assets but no scene-to-static-RoomId crosswalk. Full record: `agent-patches/metadata/DUNGEON_ZIP_ROOM_ID_REVIEW_20261009.json`.

The current pointer's sole authoritative report for run `20261009T004054Z-9fedea65` is `research-uploads/20261009T004133Z-parallel-action-test/combined-results.json` (SHA-256 `af6166966fb37b738d9a584103275a10f28d1d39e6e39f23181e63a4beacd972`, verified). It is isolated automatic analysis of saved session `20261008T184737Z_Uzawan_XI.json`; upload was disabled and worker data was not retained. It reports MEDI_FLOATERS, 10 analyzer groups, 146 scene instances, `needs-review`, zero manual room markers, and 14 asset-predicted targets (7+7), not a fresh capture or observed physical count. Keep the historical CARGO result separate: 8 CARG + 2 BARRACKS + 1 END analyzer parent groups (11 total), with 43 asset-derived predictions across 164 resolved scenes, not observed. Static CARGO_FLOATERS remains `Rooms=7`; the 7-versus-11/10 relationship is unresolved.


## METADATA-D repository-wide crosswalk search â€” 2026-10-09

Searched all 137 fetched remote refs under `agent-patches/dungeon-decompile/` and `agent-patches/metadata/`. The only three unique files containing both room-ID and scene-path terms are explanatory notes (`METADATA_D_20261007_MANIFEST.json`, `ROOM_MODEL_RECONCILIATION_20261008.json`, and `STATIC_ROOT_SCENE_TRACE_20261007.json`); none maps a room ID to a scene. Also checked all 55 room-crate-index files on main: each records `scene_path` and crate/footlocker counts but no dungeon `RoomId` (the `id_*_refs` fields refer to entity references). All 51 main dungeon-generation-table exports contain static room IDs but no scene path. The two evidence sets have no join key. Details: `agent-patches/metadata/DUNGEON_ZIP_ROOM_ID_REVIEW_20261009.json`.

The remaining request is a separate source artifact explicitly pairing a generated scene path with a static `R_*`/`B_*` room ID. The supplied `dungeon.zip` does not contain it. No Surveyor action or full traversal is required.


## METADATA-D repository crosswalk search update (2026-10-09 01:22 UTC)

The final main-repository scan found 97 JSON files mentioning both room-ID and scene-path terms; zero same-record RoomId-to-scene pairs exist. The user does not need to search for an existing repository file. Further reconciliation requires new source evidence explicitly pairing a generated scene with a static `R_*`/`B_*` ID. No Surveyor control sequence is currently established; full traversal is not required. Details: `agent-patches/metadata/DUNGEON_ZIP_ROOM_ID_REVIEW_20261009.json`. Preserve the report distinction: historical CARGO has 11 analyzer groups vs static `Rooms=7`, and 43 asset-derived target predictions; the separate MEDI report has 10 analyzer groups and 14 asset-derived predictions. Neither prediction total is an observed count.


## Seed-Lineage â€” 2026-10-09 automatic batch and Surveyor panel fix

- Latest automatic batch `20261009T015908Z-d4d6ae3f` and its session report `20261009T015909Z-77532ce2` are SHA-256 verified (`b1ea5afaee7aa2f6d2a49bd48c28b73a67d59a9aad3f6b53702d41fe2b0ea18a`, `721427df0b4d95a3bb0cfee5ececa3fdb5517713c0abd998fca4802e3ced994b`). The input session SHA-256 is `2b6c2767cdc1d01c4ef2c36a5536a787379bcd72bc3159ae5871a8fb786807a7`.
- Its measurement artifact adds a third distinct address/root candidate: `0001680006607CAC -> 2139770A2614E3DC`, one observation, root resource `MODELS/SPACE/POI/DUNGEON.SCENE.MBIN`, UseSeedValue true. The measurement artifact contains no NMS.exe hash, so executable identity is unverified. The caller and seed-function artifacts from this same report still cite the older `0001550006607CAC` session; no fresh full chain exists for the third candidate. Derivation remains unproven.
- The seed-function scan reports candidate logical entry `0063A6D0`, 51 direct external refs, zero possible descriptor-field writes, and zero RTTI candidates. These do not establish a construction formula or runtime class identity.
- The screenshot's 1.0.4 activation failure is explained by the 635-character summary exceeding the host's 500-character maximum. Ready request `seed-panel-summary-limit-20261009` supplies 1.0.5 with a 432-character summary and updated tests. It is not integrated until the primary compiler stages and publishes the request and complete source ZIP.
- Keep 14 MEDI_FLOATERS and 43 CARGO_FLOATERS as asset-derived predictions, separate from any measurement fields. The zero `+0x10` read and the separate resolver sample remain unresolved dispatch evidence.
- Next: main compiler stages the request and runs `python -m unittest tests.test_seed_lineage_ui_extension`; lane continues offline analysis. After integration, obtain a caller â†’ upstream â†’ seed-function chain for the already captured third-address session. No new traversal is currently needed.


## Seed-Lineage public address-seed comparison â€” 2026-10-09

Using pinned upstream `hadsh/nms_namegen` commit `52ad48affaa4089c8f487a470a888dc9b7a650aa`, I independently reproduced `indexPrimedPRNG` with fixed-width BigInt arithmetic. The implementation matches the two existing address anchors (`00001A0004E84EFD -> B006BAB6`; `0001550006607CAC -> 9E1A7905`) and returns `8A6EF089` for the third saved address `0001680006607CAC`. The hash-verified automatic session report records that address's separate 64-bit dungeon-root candidate as `2139770A2614E3DC`. The calculation is an address-to-public-system-seed comparison only; the root-seed relation remains unknown, and the third sample lacks an executable hash and a fresh same-capture caller/upstream/function chain. See `agent-patches/seed-lineage/SEED_B_SYSTEM_SEED_COMPARISON_20261009.md` and its JSON record. Keep the 43 CARGO asset prediction distinct from report measurement fields, and do not assert physical counts. The zero `+0x10` read and separate resolver sample remain unresolved.


## Seed-Lineage latest automatic batch â€” 2026-10-09

# Seed-Lineage review â€” 2026-10-09 automatic session report 20261009T163435Z-b91c6dbb

The current automatic pointer names batch `20261009T163434Z-bf1ed756`. Its batch index at `research-uploads/20261009T163525Z-automatic-research-batch-20261009T163434Z-bf1ed756-3b9b70/batch-results.json` has SHA-256 `4ae5af8f6814e14d1e5e16ca1eeeaf455599b1e22d47286ba01e2b513f3f25cd`. The index names this report at `research-uploads/20261009T163525Z-automatic-research-batch-20261009T163434Z-bf1ed756-3b9b70/reports/20261009T163435Z-b91c6dbb/combined-results.json`, SHA-256 `fb7126c475d65d0e764d802b74ed6a6ca99c56fb72d75c65da9e0e3f6335f1f4`, input session SHA-256 `15c10763f0a5df6c3b7caec8b9ed771361d806912a1fb74c43b249f5c676e23a`. Fetched content hashes match pointer/index. Use this combined report as the sole authoritative source for this saved-session run. Provenance: automatic_saved_session, isolated_parallel_test_no_github_upload, input snapshot available, worker data not retained; 7 complete, 1 failed, 1 upload skipped. The failed action was Metadata-D prepare_assets, not Seed-Lineage.

Fresh generation baseline: session `20261009T161852Z_00006D0006606CAB`, address `00006D0006606CAB`, root candidate `A5047E4E4B68F362`, artifact SHA-256 `a950ddd7d2bf56c8a62ea5b26dee0ca0c40e51432ccb67a9d7a5f7b70dec32b7`. It reports 9 logical chunks and 130 scene instances. Its 21 target containers (12 salvage + 9 footlockers) are derived predictions, not physically observed counts. The caller, upstream, and seed-function outputs do not use this fresh sample; they are not a same-sample chain.

The historical 43 CARGO targets remain a separate asset-derived prediction. Neither 21 nor 43 is an observed count. Root derivation remains unknown. Zero `+0x10` and the separate resolver sample do not identify a resolved dispatch target.

Seed-B 1.0.6 adds an ordered refresh-first action list: analyze generation, extract caller, extract upstream callers, analyze seed function. Button ordering is a user sequence, not an enforced dependency; verify each output references the preceding artifact. Static panel/index/action/hash checks were completed. Python unittest was not run because the local execution helper could not start. One short local Agent Console action sequence is required; no NMS launch or full traversal is required.


## Seed-Lineage follow-up evidence â€” 2026-10-09 23:28 UTC

The saved evidence snapshot `research-uploads/20261009T232439Z-seed-lineage-all-saved-evidence-c443da47-a318d1ad/run-manifest.json` was uploaded at 23:24:39 UTC. Its SHA-256 entries were verified against the fetched files. The fresh generation baseline is session `20261009T230838Z_0000790006606CAB`, address `0000790006606CAB`, root-seed candidate `C36137A0B4914AD9`; it infers `CARGO_FLOATERS`, 10 logical chunks, 134 scene instances, and 32 predicted targets. The 32 are predictions, not physical observations, and are separate from the historical 43-target asset prediction.

Fresh caller and upstream evidence both use that session/address/root and the same NMS.exe SHA-256 `13d5060d4efb9d2a6a6b1b349bc4257231056cc2a055df4bb15d816262cc3499`. Caller artifact SHA-256: `e63c2a420c9d30e1d21509ff815cdb2250ce9ede1583f59379fbf7a3e332ffbe`. Upstream artifact SHA-256: `65cf35f2aca92aa21aea0082ca2dd0fa1ff8c211a05ea9b5b323b0730bee0a52`; its root Add call is RVA `0063AC20`. The seed-function file in the all-saved snapshot SHA-256 `e7590db2377d25ff88f46aa203691daf6008098650e991d28b4efde7aacb3013` is still from the older `000155` session/root `00C9E8DF0327789E`. The snapshot reuses that stale file; it is not evidence that a fresh seed-function action completed. No fresh function analysis or root-seed formula is claimed. The zero `+0x10` and separate resolver sample remain unresolved dispatch evidence.

Next human action: rerun only Seed-B action 4, **Analyze seed function + upload**, after the fresh upstream action. See current Seed-Lineage status for the success check. No NMS launch or full traversal is required.


## Seed-Lineage fresh function analysis â€” 2026-10-09 23:39 UTC

The lane-exclusive analyze-seed-function upload at `research-uploads/20261009T233349Z-seed-lineage-analyze-seed-function-1ac8a6b3/dungeon-seed-function-analysis-latest.json` and the 23:33:56 all-saved snapshot both point to session `20261009T230838Z_0000790006606CAB`, universe address `0000790006606CAB`, root candidate `C36137A0B4914AD9`, executable SHA-256 `13d5060d4efb9d2a6a6b1b349bc4257231056cc2a055df4bb15d816262cc3499`, and fresh upstream artifact SHA-256 `65cf35f2aca92aa21aea0082ca2dd0fa1ff8c211a05ea9b5b323b0730bee0a52`. Both upload manifests declare the seed-function artifact SHA-256 `38f2b537f2e6c33d6bdf69e74561cf5a11be39f018bd4e6d87577fda1dc99212` and 15,904 bytes; the review records that an independent SHA-256 recomputation is still pending. Review: `agent-patches/seed-lineage/SEED_FUNCTION_REVIEW_20261009T233349Z.json`.

The analyzer proposes logical entry RVA `0063A6D0` from four bytes of INT3 padding plus prologue evidence. The PE `.pdata` fragment begins at `0063AB6C` and contains the root AddResource call at `0063AC20`; it is not by itself the full logical function boundary. The scan reports 51 direct references outside the known prefix and one inside. It locates a primary-seed field occurrence at owner displacement `+0x138` and descriptor occurrences at `+0x128`, but reports no possible descriptor writes. These are byte-level observations, not proof of assignment, seed derivation, or dispatch resolution. The root-seed formula remains unknown. The fresh CARGO_FLOATERS 32-target value and historical 43-target value are separate asset-derived predictions, not observed counts; zero `+0x10` and the separate resolver sample remain unresolved dispatch evidence.

Seed-B is no longer waiting on a user action. Next: continue offline dataflow comparison across the fresh function, caller, and upstream evidence. No NMS launch or traversal is currently needed.


Seed-B offline trace update (2026-10-09 23:40Z): same-sample upstream analysis shows the function copies its second argument to RSI at RVA `0063A6F1`, reads the descriptor primary-seed field at owner `+0x138` / descriptor `+0x10` at `0063A8CE`, checks UseSeedValue at owner `+0x140` / descriptor `+0x18` at `0063A936`, then reaches root AddResource at `0063AC20`. No possible writes to the descriptor or seed were reported. This indicates the function consumes an already-present seed; it does not locate its construction or prove its derivation. Next agent task is to trace callers and descriptor setup. See `agent-patches/seed-lineage/SEED_FUNCTION_REVIEW_20261009T233349Z.json`.


Hash verification correction (2026-10-09 23:45Z): the exact GitHub base64 content bytes for `research-uploads/20261009T233349Z-seed-lineage-analyze-seed-function-1ac8a6b3/dungeon-seed-function-analysis-latest.json` were independently SHA-256 checked; the digest is `38f2b537f2e6c33d6bdf69e74561cf5a11be39f018bd4e6d87577fda1dc99212` at 15,904 bytes and matches both upload manifests.


## Seed-Lineage latest combined batch and root capture â€” 2026-10-09 23:51 UTC

The latest automatic batch pointer identifies index `research-uploads/20261009T231823Z-automatic-research-batch-20261009T231727Z-4cc0e6a5-286919/batch-results.json` (SHA-256 `e8f703afa93485172c9108153696e518a2cf381446cb0aaccc63468fd75bb909`) and its sole-session report `research-uploads/20261009T231823Z-automatic-research-batch-20261009T231727Z-4cc0e6a5-286919/reports/20261009T231728Z-208c8af6/combined-results.json` (SHA-256 `48bdc7cbeebdf489752d4b0f1bc3bbfcbd2bf6eadc7682d03c3f8344aa58bab3`); both hashes were independently verified. Provenance is `automatic_saved_session`, input session `20261009T230838Z_Gersid_XVI.json` (SHA-256 `ac8cef02578a2b667723b5e6ceda4f52a23c058b09b606d7d72bc6bdcd8449c5`), isolated parallel with input snapshot available, worker data not retained, and upload disabled. In that report the fresh 000079 generation baseline predicts 32 CARGO_FLOATERS target containers from assets; its seed-function result is from 000155/root 00C9E8..., caller from 00006D/root A504..., and upstream from 000155/root 00C9E8.... They do not form a same-sample chain. The later lane-exclusive 000079 seed-function upload is separately verified and matches its same-sample caller/upstream chain. Review: `agent-patches/seed-lineage/SEED_B_AUTO_BATCH_REVIEW_20261009T231727Z.json`.

A separate lane upload at `research-uploads/20261009T234615Z-analyze-generation/exact-root-caller-latest.json` has verified SHA-256 `87813ff2737bca7f6e85a07235844bf773af4a956ee1572bcd3fb0fbf43e8246`. It records root candidate `9C2818C7FE094FC8` at address `0000760006606CAB`, UseSeedValue true, exact external caller return `02C0860A`, and logical root call `0063AC25`. A fixed-width reimplementation of the pinned public system-address algorithm passes the three existing anchors and yields system seed `D4759808` for this address. The sample lacks executable identity, so keep it separate from the hash-matched 000079 chain. The owner `+0x10` read is zero at entry and root-add phases with null target identity; it does not resolve dispatch. The capture records no traversed rooms or physical container count. Review: `agent-patches/seed-lineage/SEED_B_ROOT_CAPTURE_REVIEW_20261009T234615Z.json`.

Next Seed-B action is offline comparison of address/system-seed/root-candidate pairs plus descriptor-construction tracing. No live NMS action is currently required. The 43-target historical asset prediction remains distinct from the 32-target 000079 prediction; neither is an observed container count.


## Seed-B owner/descriptor producer trace (2026-10-09 23:57Z)

Offline same-executable analysis of session `20261009T230838Z_0000790006606CAB` matched two direct caller sites to a common helper: call at `006395D3` (`E8 08 06 00 00`) and call at `00639B99` (`E8 42 00 00 00`) both target `00639BE0`. At both sites, the helper return in RAX is copied into RBX, then passed as RDX to logical entry candidate `0063A6D0` (with RSI copied to RCX). That callee reads the primary seed at owner `+0x138` / descriptor `+0x10`. The helper is therefore a candidate owner/descriptor producer or setup path. Available windows do not establish a write to `owner+0x138`, the helper's full behavior, or a seed formula. Evidence is recorded in `agent-patches/seed-lineage/SEED_B_OWNER_PRODUCER_TRACE_20261009T2357.json`. The 000079 32-target and historical 43-target values remain separate asset-derived predictions, not observed container counts. The zero `+0x10` owner read and the separate resolver sample remain unresolved dispatch evidence. Next agent action: obtain wider code around `00639BE0` and test whether it assigns the seed or forwards it from its arguments, preserving the verified executable cohort.


## Seed-B waiting gate â€” helper body needed (2026-10-10 00:00Z)

The offline lane found two same-executable callsites (006395D3 and 00639B99) that call helper 00639BE0, pass its returned pointer into 0063A6D0, and the latter reads a primary seed at owner+0x138. The available repository windows do not include the helper's complete body. The Seed-Lineage Surveyor extension does not support arbitrary-RVA code extraction, and this session cannot read the local NMS.exe. The lane is `waiting_on_user` only for that missing static source evidence; no game launch or derelict traversal is required.

Requested evidence: use the matching NMS.exe SHA-256 `13d5060d4efb9d2a6a6b1b349bc4257231056cc2a055df4bb15d816262cc3499` in Ghidra CodeBrowser; Go To `140639BE0` (RVA `00639BE0` at image base `140000000`); export the full Listing disassembly and Decompiler output through function return, plus the function's X cross-reference list; attach one text file. Success: function begins with bytes `48 89 5C 24 10` and xrefs show `006395D3` and `00639B99`. This is a static-only request.
## Current research checkpoint â€” historical manager lead ruled non-actionable â€” 2026-10-16

The old ReNMS SDK declares a generic reward ID map on `cGcRealityManager`, but the exact 7.05 executable has no matching manager TypeDescriptor or field-name string. The only substring hit is the distinct `cGcRealityManagerData` RTTI name. This historical hint gives no code edge; generic reward selection remains unresolved. Details and exact offsets are in `research-output/ghidra-static-20261015/REWARD_TABLE_PIPELINE_20261016.md`.


## Runtime incident: Probe 0.3.49 late-attach candidate — 2026-10-17

- The isolated 0.3.81 source package carried Probe 0.3.49 with a new `cGcApplication.Update.before` callback intended to recover nmspy's application singleton after late attach.
- On matching NMS 7.05 PID 30272 (SHA-256 `13D5060D4EFB9D2A6A6B1B349BC4257231056CC2A055DF4BB15D816262CC3499`), the callback logged `late_application_singleton_recovered` with address `0xE`. This is not a plausible application pointer. The user then reported a crash. The injector later reported `ConnectionRefusedError: [WinError 1225]`; the precise crash cause is not independently proven, but the new recovery hook is unsafe and is the leading suspect.
- NMS and the injector were no longer running. The attach monitor started for this run was stopped by exact PID/script identity. The installed mod was restored from the pre-0.3.49 backup and verified SHA-256 `6BBEEAB0A8C9391C99833B129455DFF1B4C04FC9861AB41BEAE28BB42199176E` against that backup.
- Do not redeploy this recovery callback as written. Before another live attempt, establish pyMHF's callback argument representation for `cGcApplication.Update`, validate a plausible pointer without mapping arbitrary addresses, and add a non-mutating diagnostic path. The prior successful attach heartbeat does not establish that runtime game data is valid.

## Runtime incident: Probe 0.3.55 capture-only r1 crash and r2 mitigation — 2026-10-19

- The one-click capture-only r1 run started at 14:44:32 UTC. It attached pyMHF to NMS PID 13956 at 14:44:37, before game states `APPLOCALLOAD` (14:48:13) and `APPVIEW` (14:49:55). pyMHF reported 3 mods and 8 hooks. The user reported severe startup lag from white screen to ship.
- Windows recorded another `NMS.exe` access violation in `python313.dll`, `0xC0000005` at `0x2ABDA3`, at 14:52:05.969 UTC. The r1 session contained 45 path samples ending at 14:51:49.700 and no layout, scene, resource, or trace events. The layout capture remained armed. This narrows the issue away from the original high-volume hooks but does not identify the faulting callback.
- The per-user `HKCU` LocalDumps value did not retain a dump. Microsoft documents per-process LocalDumps under `HKLM` and requires administrator rights. An HKLM write failed with access denied in this session; the next runtime incident still needs a dump for stack attribution.
- A new untested candidate is `research-output/probe-layout-capture-0.3.55-capture-only-r2/derelict_baseline_probe.py`, SHA-256 `8EFF802E82A29CD81AC2448C58F0C274E94FDC470EBC2D6008EF88F9C4983C46`. It retains only the top-level layout-generator detour, reduces main-loop/status polling, and is staged under `live-runtime/NMSDerelictSurveyor/diagnostics/layout-capture-only-r2-modroot/` with the same hash.
- `Run-Layout-Capture-0.3.55.cmd` now starts NMS and the overlay immediately, then waits for `Ctrl+Alt+Shift+F12` at the ship before attaching pyMHF. The overlay shows this waiting state. This avoids debugger/instrumentation during startup; it is a mitigation candidate, not confirmed live behavior. r2 captures top-level seed/preset inputs only, not source rows or manager-map rows.

## Runtime incident follow-up: Probe 0.3.55 quarantine — 2026-10-19

- The user reports that after the 0.3.55 capture run, the whole PC became laggy and they forced a shutdown. Windows records an NMS `AppHangTransient` at 14:53:39 UTC, an NMS access violation in `python313.dll` at 14:52:05 UTC, an unexpected prior shutdown at 15:33:31, and Kernel-Power event 41 after boot at 15:50:10. These corroborate the hang/crash and unclean shutdown but do not identify a callback or prove the probe caused all machine-wide lag.
- The persisted run state and installed-file record identify capture-only r1, SHA-256 `73A07CBA13F2A0761A2C44DC85B930AA0F364FF4A67E8B9CF8ED60260A1ECF5D`, attached to PID 13956 four seconds after NMS launch. r1 enabled the layout-writer, source-row-builder, and manager-map-acceptance detours; pyMHF reported eight hooks. The captured session has only 45 position samples and no layout event. The exact faulting callback remains unknown; the archived WER report contains no dump.
- r2 (`8EFF802E82A29CD81AC2448C58F0C274E94FDC470EBC2D6008EF88F9C4983C46`) has no run record and remains untested. r1 and r2 stay quarantined; `tools/PROBE_0.3.55_CAPTURE_QUARANTINED.md` still gates both legacy entry points.
- Offline review found a synchronous hot-path risk in r1: per-row `ReadProcessMemory`, metadata reads, dictionary construction, and hex encoding run inside the source-row detour; the 2,048-row cap is enforced after this work. A second detour copies/hex-encodes up to 1,024 manager rows inside its callback. This could stall NMS if reached, but the missing capture event and dump leave causality unproven. r2 removes those two detours but retains the top-level writer hook and is not approved for live use.
- The attach helper also serialized `Get-Content` provider objects directly into JSON, expanding `PSPath`/`PSDrive` metadata. `launcher-events.jsonl` is 351,812,112 bytes and was written at 14:54:33 UTC. The helper now converts its tail to plain strings; original bytes are preserved at `research-output/probe-layout-capture-0.3.55-capture-only-r2/launch_nms_classic.ps1.before-log-tail-fix-20261019` (SHA-256 `E7619EE7DF507DB150A9C6D5FDE5A00E52BC64245D3737C0BB54DF5ECD9C368D`). The log was left intact. D: had about 290.9 GB free, so no disk-full cause is established. This logging bug is a credible additional load contributor but does not prove the cause of the shutdown.

## Runtime incident follow-up: r3 low-work canary prepared — 2026-10-19

- New source: `research-output/probe-layout-capture-0.3.55-capture-only-r3-canary/derelict_layout_canary.py`, SHA-256 `21481554D78BC0F2454E45993F67B9A077D9674D421EBF15BD8A1B17E29AAEB0`; staged mod-root copy has the same hash.
- r3 enables only the exact-build `FUN_14039E5E0` after-hook. It captures six scalar argument values and the return byte for the first call. The callback does no pointer reads, `ReadProcessMemory`, formatting, JSON serialization, or file I/O. A daemon worker writes one small event and status file. There are no other native hooks or per-frame callbacks.
- The launcher is `tools/Run-Layout-Capture-0.3.55-r3.cmd`, with PowerShell worker `tools/run_layout_capture_0_3_55_r3.ps1`. It pins the NMS and r3 source hashes, plus attach helper SHA-256 `166CB9F5C8E612F9921BDB705AD49D6E7DC6DB8C89753DE1FD7E446E2446CDAC` and the log-tail-fixed classic launcher SHA-256 `0B0ED571DAF479CFCB5D162E3B1C38069699E7F069B9F8E6DFC2D3E07A4C0EF5`.
- r3 is a one-shot stability canary, not the requested native-buffer capture: it does not read seed, preset, output, or room-map memory. A persisted event proves the callback ran with those scalar values; it does not establish pointer contents or runtime safety for a later data-reading hook.
- No NMS launch, injection, or gameplay was performed. The source and PowerShell launcher received static inspection only. A new human run is ready through the r3 `.cmd`; stop and do not retry if the system becomes laggy.


## Codex continuation: 2026-10-21 01:33Z

- Implemented fullscreen entry/exit, mobile walking controls, and reduced first-person collision radius for narrow spaces. Backups are next to each changed viewer file with `.pre-fullscreen-mobile-20261021`.
- Added `research-output/CODEX_HANDOFF_CHECKLIST_20261021.md`, which consolidates the outstanding live checks without launching NMS.
- JS syntax checks passed. Browser touch and tight-passage validation is still open. Reward batch remains unattended in the background; remaining independent work is in progress.

- Full offline regression: `python -I tools/regression_test_705.py --full` yielded 20 passed and only e2 failed because the published index is still older than format 4. `piece_props.py --check` passed; the fresh `derelict_view.py --verify` was still running at 01:41Z. Refreshed public candidate v3 served all requested static files and `?atlas=` index with HTTP 200.

- At 01:46Z, `derelict_view.py --verify` passed on 1,456 layouts (0 different). Full regression completed with 20 pass and only the expected stale-index e2 failure. The snapshot builder was optimized after its scheduled run remained active while enumerating excluded trees; its fresh rerun is pending.

- The 01:45 backup snapshot completed after the excluded-tree/hash optimization: 13,776,602 bytes, 2,258 entries, ZIP CRC clean; reward-cache copy was also made and hashed. Next scheduled run 02:10Z.

- 01:48Z fast regression rerun: 19 pass, 1 fail, 1 skip in 59s; full mode: 20 pass, 1 fail, 0 skip in 115s. Both fail only e2 because format-4 reward index publication is pending. `derelict_view.py --verify`: 1,456 layouts, 0 differences.


## 2026-10-23 portable minimap package

Portable minimap package BUILT (2026-10-23, user: 'make all necessary arrangements for the portable real mod version'; local only, nothing uploaded): `python -I mod/build_package.py [--with-mbincompiler] [--keep-data]` -> `D:/Orca/NMS-Derelict-Minimap-dist/NMS-Derelict-Minimap/` (python.org runtime + unicorn/pefile/hgpaktool, our code with machine paths rewritten in COPIES, nothing in fastgen/app edited). Install.cmd -> `minimap/first_run.py` builds all game data from the user's own install (extract_build_data_705 via first_run_driver; verified byte-identical to the validated 7.05 data, 653/653 files) -> choose autostart (Startup shortcut, self-removing after NMS missing 3 days over >=7 days or unused 30 days), Steam launch option (nothing resident), or by hand; `minimap/lifecycle.py` install/uninstall + Installed-apps entry. Native writer is NOT shipped (RWX memory = antivirus flag); package uses `--engine unicorn` (identical layout, ~25 s per new derelict). Tested cold in the package: golden layouts, golden reward, 54 seed checks PASS; derelict 0000760004607CAB = same card/modules as the dev tree; map render 6/6 byte-identical; overlay single-instance + STOP file + shortcut create/remove OK. 23 minimap + 5 mod tests pass. See `mod/README.md`. Open: Defender/VirusTotal results, MBINCompiler licence, code signing, second-PC test, GOG/Game Pass. 
