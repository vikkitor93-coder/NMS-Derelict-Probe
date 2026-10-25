# Why the native layout writer is slow for TURRETS presets (2026-10-22, Claude)

This is an investigation only. No shared file was changed: nothing in fastgen `*.py`, `app/`, `tools/`, the atlas or any cache. NMS was not launched or attached.
All prototypes are scratch copies in `D:/Orca/Temp/claude/turrets-20261022/`, run at BelowNormal with 1-2 processes.
This report builds on `GENERATOR_PROFILE_20261022.md`, which gives the native leaf profile: A3FB0 27 %, A0AD0/A0FF0/A41F0 about 10 % each. It also builds on `FRIGATE_SEARCH_20261022.md`.

## Bottom line

1. **Root cause: rejection sampling inside the game's own writer.** Writer time is a fixed number of microseconds per topology attempt, times the number of attempts:
   **time = 0.19 s + 5.8 us x attempts** (r = 0.99, 680 systems). TURRETS layouts are accepted much less often, so they need 4-15x more attempts.
2. **This is inherent to the game, not caused by our harness.** All hot code is the game's own machine code running natively. Our stubs are called about 1,700 times per system (the allocator), against 10^8-10^9 game-helper calls. The timer stub is called once. The writer has no time limit (`while(true)`).
   The game runs the same function on the same inputs, so it does the same number of attempts and would be just as slow.
3. **Nothing inside the writer can be skipped without changing the output.** Every failed attempt advances the RNG, and the next attempt depends on that. The checks that reject most attempts (A2120, A1A00, A1DA0) use no RNG, but they need their predecessors' grid. The work after success (A4400/A4720/A51B0) is already stubbed or captured.
   The only big exact win is to **never run the writer twice for the same system**. A writer-result cache (about 1.2 KB per system) was prototyped:
   - **220/220 systems are byte-identical** (66 of them TURRETS): derelict.json without its 4 run-time fields, plus outbuf.bin, a2780_placements.bin and emu_placements.json.
   - Generation got **9.4x faster** over all 220 (2.08 s to 0.22 s per system) and **22.5x faster** for TURRETS (4.64 s to 0.21 s).
   - This only helps re-generation (backfills, the frigate search, top-100 rebuilds). A first scan of a new system still pays the full writer cost.

## 1. How the writer searches (static analysis of FUN_14039E5E0, exact build 13D5060D)

Decompile: `D:/Orca/Temp/nms-ghidra-targeted-20261019/dungeon_writer_methods.txt`. Retry nesting, as in `WRITER_CONTROL_FLOW_AUDIT_20261019.md`:

```
forever:                                   room selection (main/branch room ids) + GcRoomCountRule check (D6100) -> retry on fail
  200 x  A03E0 shuffle + A06E0 sequence check
    500 x  A0580 quest assignment + A0850 ordering check
      1000 x A01F0 grid init, per-room path lengths (RNG)          <- one "topology attempt"
             A0AD0 -> A0FF0 -> A15F0  (path/grid growth, RNG; A3FB0/A41F0/A3F00 helpers)
             A2120 grow rooms into free cells, A1A00 per-room bounds (no RNG)
             A1DA0 room-map fit (no RNG): for every room whose RoomTemplate MinContiguous W*H*D > 1, the room's
                   cells must contain a fully owned W x D block (either orientation)
             A2780 piece placement (RNG) -> success -> A4400/A4720/A51B0 -> return room count
```

Room templates (`generatedbasetemplatestable.MXML`): R_BARR/R_CARG/R_MEDI and R_HANG (and their FLO/BUG/SLI variants) are **3x3**, R_S_* rooms are 2x2, R_END is 3x2, and B_* rooms are 1x1.
**Only the two TURRETS presets have R_HANG**, with the rule `GcRoomCountRule R_HANG [1,1]` and BranchProbability 0.
MEDI_TURRETS also has `R_MEDI [2,100]`, `R_BARR [1,1]` and `R_S_BARR [1,1]`. So TURRETS layouts must fit more mandatory 3x3 rooms.

## 2. Evidence: counters on the real native run

Method (`instr.py`): each direct `call rel32` in 0x14039E5E0-0x1403A6000 to a watched helper goes through a near stub, `lock inc [counter]; jmp helper`. Stack and registers are unchanged at the callee.
All 680 systems produce the same room count as the atlas. On 3 systems, the instrumented hashes (outbuf + placements) equal plain runs.
The instrumented runs took 0-40 % longer under the varying scanner load (the `lock inc` sits on the hot helpers), but the counts don't depend on timing. Pass rates come from entry counts of the next stage.

Sample: 680 galaxy-0 atlas systems, with 100 per TURRETS preset and 60 for every other preset (`sample.csv`, seed 20261022). The scanner was running alongside, so absolute seconds are about 10-20 % noisy.

| preset | n | writer mean s | median | max | topology attempts mean (median) | P(A0AD0) | P(A0FF0 \| ) | P(A15F0 \| ) | **P(A1DA0 \| )** | A2780 calls | **P(A2780)** |
|---|---|---|---|---|---|---|---|---|---|---|---|
| MEDI_TURRETS | 100 | **5.70** | 3.49 | 18.6 | **973k** (596k) | .45 | .22 | .95 | **.00007** | 6.7 | **.15** |
| CARGO_TURRETS | 100 | **3.16** | 1.92 | 16.9 | **523k** (319k) | .46 | .24 | .96 | **.00010** | 5.7 | **.17** |
| MEDI_FLOATERS | 60 | 1.68 | 1.30 | 5.4 | 233k (179k) | .48 | .16 | .94 | .00038 | 6.5 | .15 |
| CARGO_FLOATERS | 60 | 1.24 | 0.67 | 6.5 | 159k (85k) | .46 | .19 | .94 | .00045 | 5.8 | .17 |
| CARGO_BUGS | 60 | 0.56 | 0.31 | 2.5 | 71k (38k) | .47 | .12 | .95 | .00067 | 2.5 | .40 |
| MEDI_SLIME | 60 | 0.55 | 0.36 | 2.5 | 79k (55k) | .48 | .15 | .94 | .00037 | 2.0 | .50 |
| CARGO_SLIME | 60 | 0.52 | 0.32 | 2.5 | 64k (42k) | .47 | .18 | .94 | .00054 | 2.7 | .38 |
| MEDI_BUGS | 60 | 0.48 | 0.32 | 3.1 | 62k (43k) | .50 | .13 | .96 | .00057 | 2.2 | .44 |
| MEDI_MAZE | 60 | 0.39 | 0.31 | 1.2 | 8k (5k) | .70 | .20 | .93 | .0068 | 7.4 | .14 |
| CARGO_MAZE | 60 | 0.32 | 0.22 | 2.4 | 6k (3k) | .71 | .20 | .94 | .0083 | 6.3 | .16 |

- **Time is explained by the number of attempts:** time = 0.19 s + 5.78 us x attempts, r = 0.990. The log-log correlation is 0.915; the fixed 0.19 s matters for MAZE. The cost per attempt is about the same for every preset (5.8-9 us).
  So TURRETS isn't doing more work per attempt. It needs more attempts.
- **Two filters explain the presets:**
  - The A1DA0 room-map fit passes 5-9x less often for TURRETS (0.7-1.0e-4 per proposal) than for BUGS/SLIME (3.7-6.7e-4).
  - A2780 piece placement passes 2.5-3x less often for TURRETS and FLOATERS (0.15-0.17) than for BUGS/SLIME (0.38-0.50).
  - Combined acceptance per proposal that reaches A1DA0: TURRETS about 1-1.7e-5, FLOATERS about 6-8e-5, BUGS/SLIME about 2-3e-4. This is the same ordering and roughly the same ratios as the writer times.
- The stages before that (A0AD0 ~46 %, A0FF0 ~12-24 %, A15F0 ~95 %) are similar for all non-MAZE presets. The room-selection and quest loops (D6100, A0580/A0850) are cheap. A0850 rejects about 99.9 % of quest assignments, but those calls don't appear in the native profile.
- Worst case seen: 00000E0005605CAA (MEDI_TURRETS), 29 s. It took 5.2 M attempts, 440 k A1DA0 checks and 30 A2780 calls. The helpers were called 163 M times (A3FB0) and 199 M times (A41F0). Allocator stub calls: 1,721.

**Which room makes A1DA0 fail** (`instr2.py`, 120 systems, 12 per preset). The rel32 of the `jle` after the volume check and of the `ja` to the `return 0` exit were redirected to near stubs. These count, per room name, the rooms checked and the room that failed. Outputs are unchanged (hash-checked).

| preset | room: P(fail when checked), share of all A1DA0 failures |
|---|---|
| MEDI_TURRETS | R_MEDI .71 / 34 %, **R_HANG .80 / 27 %**, R_BARR .73 / 16 %, R_S_BARR .43 / 14 %, R_S_MEDI .42 / 8 % |
| CARGO_TURRETS | **R_HANG .80 / 29 %**, R_CARG .70 / 26 %, R_S_CARG .42 / 16 %, R_BARR .72 / 15 %, R_S_BARR .43 / 14 % |
| MEDI_FLOATERS | R_FLO_MEDI .70 / 46 %, R_S_FLO_MEDI .43 / 21 %, R_FLO_BARR .71 / 18 %, R_S_FLO_BARR .43 / 14 % |
| CARGO_BUGS | R_BUG_CARG .70 / 43 %, R_BUG_BARR .76 / 20 %, R_S_BUG_CARG .53 / 17 %, R_S_CARG .10 / 10 %, R_S_BUG_BARR .57 / 10 % |
| (others) | 3x3 rooms fail 60-77 % of their checks, 2x2 rooms 22-57 %, R_END about 0.6 but it is rarely reached |

So every 3x3 room fails the fit 70-80 % of the time it is checked. **R_HANG has the highest failure rate (0.80) and is mandatory in exactly the TURRETS presets**, and MEDI_TURRETS also forces two R_MEDI rooms.
The fit is the product of passing every big room in turn, so each extra mandatory 3x3 room multiplies the acceptance by about 0.2-0.3. That is the 5-9x lower A1DA0 pass rate.
The extra A2780 rejections for TURRETS and FLOATERS (piece placement fails 83-85 % of the time) were not broken down by piece. The likely cause is the hangar and floater room scenes' placement constraints, but this is **not verified**.

Atlas-weighted, using the preset shares from `FRIGATE_SEARCH_20261022.md` and the means above:
- mean writer time is about 1.72 s per system;
- **TURRETS presets are 27.5 % of systems but about 71 % of writer time**, and FLOATERS are about 12 %.

## 3. Harness or game?

- **Game.** The hot path is the game's own .text, run natively: A0AD0/A0FF0/A15F0/A3FB0/A41F0/A3270/A2780. The other agent's out-of-process sampler confirms the same functions.
  The harness only stubs these: the allocator (bump pointer, about 1.7 k calls per run even in the worst case), the timer (1 call), A4400/A4720/A51B0 (once, after success) and free (about 1.5 k calls).
  There is no Python on the writer's path, no trampoline per call and no logging. The reset per run (snapshot memmove plus a 32 MB stack memset) costs about 12 ms.
- The game executes the same function with the same seed and inputs (validated byte-identical outputs), so the game makes the same 10^5-10^6 attempts. In-game this probably runs on a loading/worker thread. It is not something our harness adds.

## 4. Can it be faster without changing outputs?

| idea | verdict |
|---|---|
| Skip or early-exit failed attempts | **No.** Every attempt consumes RNG in A01F0/A0AD0/A0FF0/A15F0 (and A2780), and the next attempt starts from that RNG state. A1DA0/A1A00/A2120 use no RNG, but A1DA0 needs A1A00's per-room bounds and A2120's grid, so they can't be reordered or skipped. |
| Early exit once the container count is final | **Already as early as possible.** The placements exist only after A2780 succeeds. After that the writer only calls A4400/A4720/A51B0, which are stubbed or captured, so there is nothing left to cut. |
| Faster stubs, no Python callbacks | **Nothing to gain.** Stubs are under 0.01 % of calls, and there are no Python callbacks. (The Python-hook cost the profiler found is in the separate Unicorn POI step, not the writer.) |
| Parallelise one system | **No.** The attempts form a sequential RNG chain. |
| Hand-optimise the hot helpers (A3FB0 weighted direction shuffle, A41F0 neighbour test) | Possible but risky: the float semantics must be exact, and the release code is already optimised. The upper bound is maybe 20-30 % of writer time. Not prototyped. |
| **Cache the writer result per (seed, preset)** | **Exact and large for re-generation.** Prototyped below. |
| Schedule by preset (longest first, streaming) | Already in `frigate_search_705.py`. The profiler's proposal #1 (streaming backlog) matters most because of this heavy TURRETS tail. |

### Prototype: writer-result cache (`cache_proto.py`)

- `fill`: the unchanged fast generator (`fast_generate_705.generate`) with an in-memory NativeSession writer, as `frigate_search_worker_705.py` does. After the writer runs, it stores `zlib(rax, A4720 record count, non-zero stub/import counts, outbuf 0x1000 B, A4720 records)`.
- `replay`: writes the cached bytes back into the session memory (outbuf, A4720 capture, counter slots) and calls the unchanged `NativeSession.write_outputs`. So every writer output file is produced by the same code.
- Record size: **mean 1,172 B, max 1,497 B**. That is about 100 MB for 87 k systems as files, or less as SQLite blobs.
- Same 220 systems (the first 220 of `sample.csv`, 66 of them TURRETS), one process at BelowNormal, scanner load in the background:

| | fill (writer runs) | replay (cache hit) | speedup |
|---|---|---|---|
| all 220: total generate s/system | 2.076 (writer 1.857) | **0.221** (cache read + memory restore 0.030) | **9.4x** |
| TURRETS 66: total generate s/system | 4.639 (writer 4.386) | **0.207** | **22.5x** |
| median s/system | 0.870 | 0.173 | 5.0x |

- **Identical-output check: 220/220** have the same sha256 of derelict.json (sorted keys, without `emulator_seconds`, `wall_seconds`, `writer_engine`, `fast_total_seconds`) and the same outbuf.bin, a2780_placements.bin and emu_placements.json. All 66 TURRETS systems are identical.
  `last_run_summary.json` differs only in `seconds`. Exit code 0 every time.
- The rest of a cache-hit run (about 0.19 s) is the Python transform/containers code and file I/O that the profiler already measured. The POI step (0.37 s, or 0.13 s with the profiler's fast hook) is separate, not included here.

## 5. Proposal (REQUEST to the scanner/fastgen owner; not applied)

Posted in `D:/Orca/NMS-COORDINATION.md`:
1. Add an optional writer-result cache to the fast generator path:
   - Key: `(writer seed, preset index)`, plus a version key of exe sha256, asset-rows and table file hashes.
   - Value: the ~1.2 KB record above.
   - Where: `native_writer_705.NativeSession` (or the persistent worker that wraps it), with `run()` returning a cached result and `write_outputs()` unchanged. Fill it during normal region scans (no extra cost), and read it in backfills, the frigate search and top-bundle rebuilds.
   - Exact by construction. Validate with the 220-system check in `cache_proto.py`, or the existing `validate_fast_vs_main.py` / regression tests.
2. Keep the TURRETS tail in mind for scheduling: stream the backlog without the chunk barrier, and order work longest-first by preset.
3. Don't spend effort on writer early-exit or skipping attempts: the output depends on every attempt's RNG consumption.

## Files (scratch, `D:/Orca/Temp/claude/turrets-20261022/`)

- `instr.py`, `count_run.py`: call-site counters. `part0/1.jsonl`: 680 systems. `analyze.py` writes `preset_stats.json`.
- `instr2.py`, `count_run2.py`: per-room A1DA0 fit counters. `fit120.jsonl`.
- `cache_proto.py`: the cache prototype. `proto220/{fill,replay}.jsonl` and `proto220/writer-cache/`.
- `rooms_from_cache.py`: room names from cached outbufs (the room name is at row +0x28).
- `disasm.py` (iced_x86) and `a1da0.asm`.
- `sample_prof.py`: in-process RIP sampler. Its overhead was 3x (88 s vs 29 s), so use it only for relative numbers.
