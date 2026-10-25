# Frigate searcher on the fast pipeline + live writer-result cache (2026-10-23, Claude)

User request: "Implement both, but keep clear info about nr 1 when selecting them." NMS was not launched or attached.
Nothing was committed, pushed or published. I did not start, stop or restart the scanner. Scratch:
`D:/Orca/Temp/claude/searcher-cache-20261023/` (harnesses, `res/`, `runs/`).

**Scanner state:** the briefing said the scanner was stopped. At 19:20Z it was actually scanning regions with 8 workers
(jobs 338-355). It then ran on and off during the tests: it was active during the 3-worker runs and mostly idle during the
8-worker runs. The scanner rows created in each test window are in `res/summary.json` (`scanner_during`). All timings below
therefore include some background load (host CPU 34-85 %, 12 logical CPUs).

## Bottom line

- **Searcher (task 1):** the worker now runs the live combined-worker chain (`scan_worker_705`: generator, native
  writer, fast-hook POI, `crate.predict`, `summarize`) behind stage A/B. Jobs are streamed and collected as they finish.
  The writer cache is on by default.
  - **0 mismatches** against the scanner DB in all 16 timed runs: 4 modes x 3/8 workers, cold and cached, plus repeats.
  - The stage-B container estimate matched the DB every time.
  - Hits CSVs are byte-identical to the pre-port runs. The all-results CSVs are identical apart from their timing columns.
- **The old "2.2x slower than the scanner" figure was a measurement artifact.** The scanner's 176 s for 0460ACAA (job 193)
  had about 5.4 systems in flight on average (sum of `total_seconds` / wall time), not 3. Writer CPU per system was the same
  (875 s vs 869 s).
  - At equal worker counts, on the same 531 systems and under the same load, the old and the ported no-filter searcher
    run at scanner speed: 1.00x at 3 workers and 1.12x at 8.
  - The ported pipeline adds no extra speed for cold systems. Its gains come from stage A/B and from the writer cache.
- **Writer cache (task 2):** now live in `D:/Orca/NMS-Derelict-Probe-fastgen/native_writer_705.py`, as a diff on top of the
  live file. Output was byte-identical on 300/300 systems in every case: cold, warm, mixed hit/miss, and cache off.
  - Generate time per 300 systems: 816.9 s cold vs 51.4 s warm (15.9x). TURRETS: 39.8x. The 10 slowest: 204x
    (28.6 s down to 0.14 s each).
  - A different exe, a patched build profile or any edit of the writer file changes the version key, so old results are
    never served (test PASS).
  - The scanner picks the cache up only after its next restart.
- **Disk:** D: has 217,338,056,704 bytes free (202 GiB) at 19:20Z. The cache uses about 4.6 KB per system on disk, so
  about 400 MB for 87k systems and about 740 MB if all 160k DB systems are regenerated once.

## Task 1: searcher port

Files: `tools/frigate_search_705.py`, `tools/frigate_search_worker_705.py`, and new `tools/frigate_search_profiles_705.json`
(the profile numbers, kept in one place; the tool reads it at start).

- **Worker:** it imports `scan_worker_705` and uses its modules, so the sys.path set-up and generator chain are the live
  scanner's. It also uses the scanner worker's writer wrapper, including the Unicorn fallback (the old searcher raised
  instead).
  - It runs the writer once and computes stage B from the placement records. Survivors reuse that writer result for the
    layout, then run one fast POI and the loot step.
  - Its reply now also carries `cache_hit`, and the ready line reports `fast_poi` and `writer_cache`.
- **Driver:** `--profile no-filter|all|balanced|fast` (`--no-filter` still works as an alias) and `--list-profiles`.
  - `--writer-cache PATH|off` defaults to the shared `D:/Orca/NMS-Derelict-Probe-analysis/writer-cache/writer-cache-v1.sqlite`.
  - All jobs are queued longest-first and collected with `as_completed`. Output order is unchanged.
  - The run log JSON gains `profile`, `kept_after_A_pct` and `fully_computed_pct`.
- **Mode info:** the same table appears in `--help`, `--list-profiles` and the start banner, where `<== selected` marks
  the chosen profile.
  - The figures follow `--min-modules`, because the stage-B threshold is 7, 19 or 34.
  - Each run ends with a `RESULT` line: stage A kept count and %, stage B rejects, fully computed count and %, errors,
    hits, writer-cache hits, wall time, and systems/s with and without worker start-up.

### Correctness on 0460ACAA (531 systems, 001-213; truth: 81 with >=2, 18 with >=3, 1 with >=4 modules)

| mode | writer run for | fully computed | found >=2 / >=3 / >=4 | mismatches | stage-B count mismatches |
|---|---|---|---|---|---|
| no-filter | 531 (100 %) | 531 (100 %) | 81/81, 18/18, 1/1 | 0 | 0 |
| all | 531 (100 %) | 369 (69.5 %) | 74/81, 18/18, 1/1 | 0 | 0 |
| balanced | 225 (42.4 %) | 222 (41.8 %) | 56/81, 15/18, 1/1 | 0 | 0 |
| fast | 168 (31.6 %) | 165 (31.1 %) | 39/81, 11/18, 0/1 | 0 | 0 |

The comparison covers every field: preset, rooms, crates, footlockers and the five frigate fields
(`compare_db.py`, DB opened read-only). The same counts and 0 mismatches hold for all cold, cached and repeat runs.
The scanner-equivalent bench also had 0 frigate mismatches.

### Speed (0460ACAA, 531 systems, systems/s over the whole run including worker start-up)

"Scanner" here means a scanner-equivalent pass: N `scan_worker_705.py` processes fed in address order like a region job,
with the cache off. Each figure is the mean of 2 runs: 3 workers 1.585 / 1.556, 8 workers 3.615 / 3.135.
"Cached" means the writer results were already in the cache, filled by one no-filter run.

| mode | 3 workers cold | vs scanner | 3 w cached | vs scanner | 8 workers cold | vs scanner | 8 w cached | vs scanner |
|---|---|---|---|---|---|---|---|---|
| scanner | 1.57 | 1.00x | - | - | 3.38 | 1.00x | - | - |
| no-filter | 1.58 (337 s) | 1.00x | 9.76 | 6.2x | 3.78 (141 s) | 1.12x | 17.5 | 5.2x |
| all | 1.63 | 1.04x | 11.9 | 7.6x | 4.14 | 1.23x | 29.4 | 8.7x |
| balanced | 4.68 | 2.98x | 24.0 | 15.2x | 11.9 | 3.52x | 46.0 | 13.6x |
| fast | 8.97 | 5.71x | 31.2 | 19.9x | 22.2 | 6.58x | 57.6 | 17.1x |

- Host CPU during the runs:
  - 3-worker runs: 34-61 %; the scanner was active in some of them, with 0-561 of its own systems in the window.
  - 8-worker cold runs: 48-85 %.
  - Cached runs are shorter than the 5 s sample interval, so their CPU reads 0-53 %.
- The first, loaded 3-worker cold runs gave 1.59 / 1.66 / 4.84 / 8.95 systems/s. They are within 4 % of the repeats above.
  They are kept in `runs/loaded/`.
- A no-filter run with the cache ON but empty (the fill run, 8 workers) took 3.78 systems/s, the same as cache off. So
  filling costs nothing measurable.
- 8 workers beat 3 by 2.4x cold. With a cached writer, worker start-up (1.6-1.9 s) and the POI/layout steps dominate.

## Task 2: writer-result cache, live

Live code: `WriterCache` and `writer_cache_path()` in `native_writer_705.py`.
- `NativeSession.run()` checks the cache first. The old body is now `_run_native()`, unchanged.
- The file was built by `mkwriter.py` from the live file. The diff is additions only. CRLF line endings are kept.
- Off unless `NMS_WRITER_CACHE=<file>` is set. The values `off`, `0`, `none`, `false` and empty also mean off.
- **Differences from staging:**
  1. The version key also covers the table MXML, the writer/hook addresses and the code of the current `build_inputs`. So
     `build_profile_705.apply_profile` (a new game build run through in-memory patches) always misses.
  2. The key is computed from the module globals at session start, not once per class.
  3. A hit restores the image/heap snapshots first, so `write_outputs` reads the same state as the all-hit staging test.
     That test ran in a mixed hit/miss process.
  4. Any cache error disables the cache for that process and the writer runs normally. Messages go to stderr only,
     never to the worker's stdout protocol.
  5. A `stats` table collects hit/miss counts: each worker adds to it every 50 lookups and at exit.
- **App (minimal, takes effect at the next scanner restart):**
  - `app/config.py`: new settings `"writer_cache": true` (on/off) and `"writer_cache_path"`, plus
    `apply_writer_cache()`, which `load_cfg()` calls.
    - It sets `NMS_WRITER_CACHE` in the server process, and every worker launched after that inherits it: region
      `scan_worker_705`, `fast_worker_705`, the backlog crate-loot/reward pools and the research jobs.
    - An `NMS_WRITER_CACHE` set outside the app always wins.
    - `writer_cache_stats()` reads the file size plus the tiny stats table.
  - `app/derelict_app.py`: one line, so the desktop app applies the same setting.
  - `app/server.py`: `"writer_cache"` added to `/api/status` (cached for 15 s).
  - `app/web/simple.html`: one status line, e.g. "Writer cache 1.3 MB · hit rate 50% (300 hits / 300 misses)", or
    "Writer cache off".
  - To turn the cache off: set `"writer_cache": false` in `app-data/settings.json`, then restart the scanner.
- **Update guard:**
  - Unchanged, and `tools/test_scanner_update_guard.py` passes 11/11.
  - The cache cannot serve results across builds, because its key includes the pinned exe, the data tables, the writer
    file and the profile patch.
  - If the installed NMS.exe changes, the guard stops scanning as before. The writer always runs the pinned
    `NMS-13D5060D.exe` copy, so a hit is exactly what the writer would compute.

### Verification

`cache_check.py` uses a persistent `NativeSession` through the unchanged fast generator, as the workers do. On 300 systems
(100 random TURRETS, the 10 slowest with writer < 100 s, which are 8 MEDI_TURRETS + CARGO_BUGS + MEDI_FLOATERS, and 190
random others; 108 TURRETS in total), the hashed outputs were derelict.json without run-time fields, outbuf.bin,
a2780_placements.bin, emu_placements.json, stub_call_log.json and last_run_summary.json without its seconds.

| run | writer | cache | identical to unmodified live writer | hits | generate s sum / mean / median / max |
|---|---|---|---|---|---|
| ref | old live file | - | (reference) | - | 810.4 / 2.701 / 0.806 / 54.58 |
| cold | new (scratch copy) | empty | 300/300 | 0 | 816.9 / 2.723 / 0.819 / 54.49 |
| warm | new LIVE file | full | 300/300 | 300 | **51.4 / 0.171 / 0.141 / 1.16** |
| mixed | new LIVE file | every 2nd deleted | 300/300 | 150 | 382.6 / 1.275 (hits 0.143, misses 2.408) |
| off | new LIVE file | off | 300/300 | 0 | 861.5 / 2.872 / 0.856 / 69.41 |

- Breakdown, cold to warm:
  - TURRETS: 661.5 to 16.6 s (39.8x).
  - Others: 155.4 to 34.8 s (4.5x).
  - The 10 slowest: 285.8 to 1.4 s (204x).
  - Writer step mean: 2.577 to 0.017 s.
- Ref and cold ran in parallel; warm ran alone; mixed and off ran in parallel. Scanner load varied between them.
- Record mean 1,220 B, max 1,639 B. The file is 1,388,544 B for 300 systems.
- Guard test (`cache_guard_test.py`, each case in its own process, against the live file; PASS):
  - Same inputs: 2/2 hits.
  - `EXE` pointed at a copy with one byte changed: new version key, 0 hits.
  - A replaced `build_inputs`, as a build profile does: new key, 0 hits.
  - `NMS_WRITER_CACHE=off`: no cache.
  - The writer's room counts were the same in every case.
- `python -I tools/regression_test_705.py` (fast): **21 passed, 0 failed, 1 skipped** (b needs --full), 108 s.
- `python -I -m py_compile` passed for every changed file under system Python and Shipwright Python. `node --check` passed
  on the inline script of simple.html.
- Config test (`cfg_test.py`):
  - Default: on, with the live path.
  - `writer_cache: false`: env becomes "off".
  - An external env always wins.
  - The stats function returned size 1.3 MB with 300 hits / 300 misses.
- Live scanner health after the writer file was replaced (19:45Z): more than 1,420 systems from new worker processes,
  engine native-worker, 0 failures, empty worker logs. The cache stays off for them until restart.
- Not tested: the live server's status endpoint with the new code, which needs a restart.

### Caveats

- `writer_seconds` in the DB and in derelict.json's `last_run_summary` is the restore time (~0.01 s) on a hit. That is
  intended: it is run-time data.
- The cache helps only re-generation: backfills, re-searches and top-100 rebuilds. It is empty now and fills from the
  next restart on. First scans still pay the writer.

## Rollback

1. Cache off without code changes: set `"writer_cache": false` in `D:/Orca/NMS-Derelict-Probe-analysis/emu/fastgen/app-data/settings.json`
   (or set env `NMS_WRITER_CACHE=off`), then restart the scanner. For the searcher, use `--writer-cache off`.
2. Full code rollback: copy each `*.pre-searcher-cache-20261023` back over its file:
   - fastgen: `native_writer_705.py`, `app/config.py`, `app/server.py`, `app/derelict_app.py`, `app/web/simple.html`
   - probe: `tools/frigate_search_705.py`, `tools/frigate_search_worker_705.py`
   - then delete `tools/frigate_search_profiles_705.json` and restart the scanner.
3. Delete the cache: `D:/Orca/NMS-Derelict-Probe-analysis/writer-cache/` (it can always be deleted; it is rebuilt on demand).

## To refresh the profile numbers

Run `matrix.py cold|warm` and then `summarize.py --write` in the scratch folder. They rewrite the `region_m3`, `speed`
and `scanner_reference` entries in `tools/frigate_search_profiles_705.json`. The atlas figures come from
`atlas_recall.py`; paste its output into the `atlas` entries.
