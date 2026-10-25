# Generator profile: where time per system goes (NMS 7.05 derelict pipeline), 2026-10-22

Profiling only. No shared file was changed: nothing in `app/`, the fast generator, `tools/`, the atlas or any cache.
All runs used scratch outputs in `D:/Orca/Temp/claude/profile-20261022/`. All prototypes are monkeypatches loaded
from there. NMS was never launched or attached.

## Conditions (read this before trusting numbers)

- PC: i7-7800X, 6 cores / 12 threads. My runs used one worker at BelowNormal.
- **Scanner live (before the user paused it), ~21:30.** I measured it for 60 s: 7 BelowNormal crate-loot workers, 144 rows written (2.4 systems/s), 243 worker CPU-s (**1.69 CPU-s per system**), and the machine at 43.6 % average. The workers were only **58 % busy** (4.05 cores of 7). The long-run average was 1.48 systems/s.
- **Scanner paused (all timings below).** The backlog was paused at ~21:40, but another agent's frigate search (8 workers) started soon after. So the background load was **17-44 %** for the base100/opt100/region50 runs and **~80 %** for aio50/base50b/region50b. Runs that are compared directly ran back to back on the same systems under the same load. Absolute ms are 5-15 % noisy; ratios are solid.
- Systems: region `06606CAC` (atlas, galaxy 0), systems 001-096 hex. None had a cached layout, so every run regenerated the layout, as the backlog does.

## What the scanner runs per system

- **Region scan** (`engine.Job._one`):
  1. `fast_worker_705.py` (persistent, system Python) generates the layout and writes the temp dir and `derelict.json`.
  2. The scanner process reads `derelict.json` and runs `Store.add_layout`.
  3. `RewardPool` (2 Shipwright workers) gets the layout as JSON over a pipe, then computes the **POI** and the end reward.
  4. `CrateLootPool` (2 workers) gets the layout as JSON again, computes the **POI again**, then predicts crate loot.
  5. `set_reward` / `set_frigate`, then rmtree.
- **Frigate-module backlog** (`_backfill_frigate_modules`): `CrateLootPool(7-10)`, which regenerates the layout, computes the POI and predicts crates. It is called in **chunks of 24 with a barrier** (`raw_many` waits for all 24), then fsync. It publishes every 500 rows from the same loop, and the workers sit idle while it publishes.

## Breakdown: backlog worker (`crate_loot_worker_705.py` replica), 100 systems, one persistent worker

| Stage | ms/system | % | Native or Python | Notes |
|---|---:|---:|---|---|
| Native writer call FUN_14039E5E0 | 1279 | 69.7 | **native game code** | layout retry search (200/500/1000 driver) |
| Writer reset (snapshot memmove + stack memset) | 12 | 0.7 | ctypes memmove | ~70 MB of sections + 32 MB stack |
| `write_outputs` (outbuf/placements files) | 21 | 1.2 | Python + file I/O | file create cost (AV) shows up in cProfile |
| derive: transforms + authored containers | 38 | 2.1 | Python | cached catalog works (no MXML parse) |
| with_orientations + extra_containers | 18 | 1.0 | Python | extra_containers runs 3x per system |
| Rest of generate (derelict.json dump indent=1, re-read + rewrite by fast_generate, parse_rooms) | 58 | 3.2 | Python + I/O | |
| Read + parse derelict.json again in the worker | 19 | 1.0 | Python | ~170 KB JSON |
| **POI position (Shipwright SystemGen under Unicorn)** | **373** | **20.3** | Unicorn + **Python hooks** | ~88 % of it is the Python import-stub hook |
| Crate loot predict | 12 | 0.6 | Python | |
| Summarize + reply JSON | 0.5 | 0 | Python | |
| Temp-dir cleanup | 4 | 0.2 | I/O | |
| **Total** | **1835** (CPU 1750) | 100 | | 17-44 % background load |

### Where the native writer time goes

I sampled the native writer from outside the process (33.5k samples over 40 systems; the in-process sampler deadlocked on the GIL). Its leaf time:

| Function | Leaf time |
|---|---:|
| `0x1403A3FB0` (grid helper) | 27 % |
| `0x1403A0AD0` | 11 % |
| `0x1403A0FF0` | 11 % |
| `0x1403A41F0` (grid helper) | 10 % |
| `0x1403A3270` | 8 % |
| `0x1403A2780` | 6 % |
| `0x1403A1A00` | 6 % |
| `0x1403A3F00` | 6 % |
| `0x1403A15F0` | 5 % |
| Writer body | 3 % |

All of it is the game's own retry and constraint search: the graph/preset checks and the A3FB0/A41F0 grid helpers, as earlier research described them. Almost no time is spent in stubs or imports.

**Heavy tail by preset:** per-system time ranges from 0.47 s to 14.5 s (median 1.13 s, mean 1.83 s). It is reproducible.

| Preset | Share of systems | Mean time | Share of total time |
|---|---:|---:|---:|
| MEDI_TURRETS | 10 % | 6.1 s | 33 % |
| CARGO_TURRETS | 14 % | 2.8 s | 21 % |
| All the rest | 76 % | 0.8-1.7 s | 46 % |

### Python hotspots (cProfile, 30 systems)

`emu_start` is called 2x per system. Under it, `nms_procgen/emu.py:_on_stub` runs **~7,900 times per system**:

- 3,650 `powf` calls (always `powf(2, 4|6|7)`)
- 3,650 `frexp` calls
- each call does 3-5 unicorn-py3 `reg_read`/`reg_write` calls through `_select_reg_class` and UcReg128 objects

Those wrappers are the top self-time functions after the native call. Next come `_io.open` and `write_bytes` (about 5 ms per new file; antivirus on file creation is likely), then `extra_containers_705.containers_from_instances`, `predict_crate_loot_705.predict` and `nms_dungeon_instance_705.transform_point`. The Python layout code itself is small, about 130 ms in total.

## Breakdown: region-scan pipeline, 50 systems, one job thread (as `Job._one` runs it)

| Stage | ms/system (17-44 % load) | % | ms/system (~80 % load) | Notes |
|---|---:|---:|---:|---|
| fast_worker generate (subprocess) | 1435 | 59.6 | 1604 | as above, minus the POI |
| Read derelict.json in the scanner process | 16.5 | 0.7 | | runs under the scanner's GIL |
| `Store.add_layout` | 0.7 | 0 | | scratch DB |
| End reward via RewardPool (layout JSON IPC + **POI** + predict) | 471.5 | 19.6 | 530 | ~95 ms of it is JSON IPC |
| Frigate via CrateLootPool (layout JSON IPC + **POI again** + predict) | 478.8 | 19.9 | 537 | ~95 ms JSON IPC |
| set_reward / set_frigate / rmtree | 4.4 | 0.2 | | |
| **Total** | **2407** | | **2697** | |

So a region scan costs **~2.4 thread-seconds per system**, and the POI is computed twice (~0.75 s). Today's region jobs ran at 1.68 systems/s with 7 workers (job 156: 537 systems in 5 min 20 s). With 12 threads that comes to roughly 7 thread-s per system at the wall, against 2.4 s of actual work. The gap is hyperthreading sharing, the CPU-target auto-scaler and other load.

## Why the backlog wastes ~40 % of its workers

I fed the measured per-system time distribution into a simulation of `raw_many` with a chunk barrier:

| Workers | Chunk of 24 (today) | Chunk of 96 | Streaming (no barrier) |
|---:|---:|---:|---:|
| 7 | 57 % | 85 % | 99.8 % |
| 10 | 44 % | 75 % | 99.9 % |
| 12 | 37 % | 70 % | 99.8 % |

The 57 % matches the **58 % busy** I measured live. The heavy TURRETS tail is why the barrier costs so much. Publishing every 500 rows inline adds more idle time, which accounts for the gap between 2.4/s in the window and the 1.48/s average.

## Prototypes (scratch copies or monkeypatches, measured)

1. **Fast POI stub hook** (`proto_opts.py: poi_fasthook`).
   - What it does: it replaces `Emu._on_stub` with fast paths for `powf` and `frexp`. Registers are read and written through `uclib` directly. The arithmetic, struct packing and side effects are the same: xmm0's upper bits are zeroed, RAX = 0, and the NaN fallback on exceptions is kept. All other imports go to the original handler.
   - **POI: 389/404/369 ms → 134/137 ms per system (2.9x).**
   - Check: POI output JSON byte-identical for **150/150** systems.
   - End to end (backlog worker, 100 systems): **1835 → 1502 ms/system (-18 %)**. Background load was 17-44 % for the base run and 22-44 % for the optimized run.
   - Check: derelict.json identical for **100/100** (timing fields excluded). Frigate rows identical to the production `predictions-v2.csv` for **100/100**. Preset, rooms, crates and footlockers match the atlas region file for 100/100.
   - Same-load check on 50 systems: base 1645 ms vs 1479 ms with the hook plus reward.
2. **All-in-one worker** (`--opt poi_fasthook,reward`): generate, **one** POI, end reward and frigate summary in one Shipwright process. No layout JSON IPC and no second POI.
   - **1479 ms/system vs 2697 ms for today's region pipeline: the same 50 systems, run back to back under the same ~80 % load. 1.82x faster.**
   - Check: end rewards identical to `rewards.csv` for **50/50**; frigate rows identical to `predictions-v2.csv` for **50/50**.
   - Generate + POI + crate prediction in one process already exists as `crate_loot_worker_705.py`, so this is mostly wiring.
3. **Streaming backlog** (no chunk barrier). Not run against a live pool, because the CPU was shared. The simulation and the live 58 %-busy reading support **~1.7x** for the backlog at 7 workers, and more at 10-12.

## Ranked proposals (for the scanner agent / user to approve; none applied)

| # | Change | Where | Gain | Effort |
|---|---|---|---|---|
| 1 | Backlog: stream instead of `raw_many(chunk 24)` barrier. Keep ~2x workers requests in flight, append each row as it completes (the cache is keyed by address), and publish from another thread or after releasing the pool | `app/scanner.py` `_backfill_frigate_modules` (same for the reward backlog) | **~1.7x backlog** (simulated plus live 58 % busy) | small |
| 2 | Fast `_on_stub` hook for powf/frexp (prototype #1), as a subclass or patch in `space_poi_position_705.PoiGen` without editing Shipwright | `tools/space_poi_position_705.py` | **-240 ms per POI** (-18 % backlog, ~-480 ms per region system) | small; validated |
| 3 | Region scan: one Shipwright worker does generate + POI once + reward + frigate, returning compact results (no layout JSON round trips, no derelict.json write/read) | `engine.py` WorkerProc target, a new worker based on `crate_loot_worker_705.py` | **1.82x region scan** (measured with #2) | medium |
| 4 | Keep a compact per-system cache (container list + POI xyz, a few KB) at scan time, so future derived columns (new loot types) cost ~15 ms instead of a full regeneration | store / new cache file | backfills ~100x faster | medium |
| 5 | In-memory layout path: skip the writer's output files, the double derelict.json write and the re-read | fast_generate / G.main | ~60-80 ms (4-5 %), estimated from stage times | small-medium |
| 6 | Native `frexp` and table-based `powf(2, n)` inside the emulated code (the args seen are only 2^4, 2^6, 2^7) | PoiGen | remaining ~80-100 ms of POI | medium |
| 7 | Defender exclusion for the scratch/temp dirs (file create ~5 ms each) | user setting | small (part of #5) | trivial, needs user |
| 8 | Speed up the native writer's retry search (A3FB0/A41F0 helpers) | game-code port | the only big lever left (75-85 % after the above) | **large / risky** |

Not worth it: PyPy (only ~130 ms is pure Python), vectorising (same reason), and caching per preset or region (the writer output is per seed). Larger worker pools only help after #1.

## Achievable speed on this PC and the cloud math

| Item | Now | After the proposals | Basis |
|---|---|---|---|
| Single-thread work per system, region scan | 2.4-2.7 s | ~1.5 s | measured, #2 + #3 |
| Single-thread work per system, backlog | 1.83 s | ~1.5 s | measured, #2 |
| Backlog throughput at 7 workers | ~1.5-2.4 systems/s | **~3.5-4.5 systems/s** | estimate: #1 (from 58 % busy) and #2 |
| Region scan, 11-12 workers | 1.7 systems/s | **~4-5 systems/s** | estimate: 6 cores x ~1.2 HT yield / ~1.5 s |
| Physical-core-seconds per system | 3.5 (current assumption) | **~1.25-1.5** | estimate |
| Core-hours per 1M systems | ~970 | ~350-420 | from the line above |

None of the throughput figures were scaling-tested. That needs an idle machine; run 6 and 12 parallel copies of `prof_crate.py`.

Cloud cost per system drops **~2.3-2.8x**. Fix #1 alone also raises local backlog throughput ~1.7x at no cost. Do #1-#3 locally first, then re-measure before renting.

## Files (scratch)

`D:/Orca/Temp/claude/profile-20261022/`:

- `prof_crate.py`: stage-timed backlog worker replica with `--opt`
- `prof_region.py`: region pipeline replica
- `proto_opts.py`: prototypes
- `poi_ab.py`: POI A/B test
- `native_sampler2.py` + `native_target.py`: out-of-process native sampler
- Results: `base100/`, `opt100/`, `aio50/`, `base50b/`, `region50*/`, `poi_*.json`, `native_profile.json`, `prof30.out`
