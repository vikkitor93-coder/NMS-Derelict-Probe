# Salvaged Frigate Module search with early rejection (2026-10-22, Claude)

New tool only: `tools/frigate_search_705.py` (driver) and `tools/frigate_search_worker_705.py` (persistent worker),
plus `research-output/FRIGATE_SEARCH_CONTAINER_TABLE_20261022.json`. No shared or other-owned file was changed
(fastgen, scanner app, atlas, caches). NMS was not launched. Scratch output is in
`D:/Orca/Temp/claude/frigate-search-20261022/`.

## Bottom line

- The **native layout writer takes about 80% of the time per system** (mean 1.95-2.35 s; median 0.66 s; up to 32 s),
  and it depends strongly on the preset. Transforms and containers take 0.14 s, the ABAND_FREIGHTER POI 0.37-0.41 s, and the loot 0.01 s.
- Container count is the real driver of modules (Binomial, p = 5/198 per crate or footlocker; correlation 0.38).
  Room count, floors and stairs predict nothing (|r| < 0.02). Hangars only weakly (0.10).
- The container count is **known exactly right after the writer**. Containers per placement template are constant in all
  1,680 local layouts (263 template ids), so a table lookup gives the exact crate+footlocker count. Checked on 1,207
  systems: 0 mismatches. But by then most of the cost has already been paid, so this stage only saves about 0.5 s per rejected system.
- So the useful early rejection is the **preset**, which takes microseconds from the address. MEDI_* derelicts have half the containers.
  TURRETS presets and MEDI_FLOATERS are also the slowest for the writer. The best filter keeps the 4 CARGO presets without SLIME.
- All results matched the atlas exactly (every field, every system computed, all runs).

## Step 1: what predicts frigate_modules (atlas, 66,201 systems with frigate_modules filled)

Module distribution: 0: 35,790, 1: 20,460, 2: 7,317, 3: 2,056, 4: 482, 5: 83, 6: 13. Mean 0.660 vs mean containers x 5/198 = 0.663,
so the binomial model fits.

| preset | share | mean containers | P(>=2) | P(>=3) | P(>=4) | writer s (mean) |
|---|---|---|---|---|---|---|
| CARGO_FLOATERS | 6.8% | 47.4 | .328 | .118 | .036 | 0.89 |
| CARGO_TURRETS | 13.8% | 40.7 | .277 | .090 | .022 | 3.08 |
| CARGO_MAZE | 3.3% | 34.1 | .202 | .066 | .015 | 0.44 |
| CARGO_BUGS | 21.0% | 31.8 | .191 | .050 | .009 | 0.60 |
| MEDI_TURRETS | 13.7% | 24.2 | .123 | .024 | .004 | **6.89** |
| MEDI_FLOATERS | 7.0% | 23.9 | .122 | .021 | .001 | 2.32 |
| MEDI_MAZE | 3.1% | 20.5 | .096 | .008 | .001 | 0.49 |
| CARGO_SLIME | 5.3% | 18.3 | .083 | .013 | .001 | 0.62 |
| MEDI_BUGS | 20.8% | 12.9 | .045 | .005 | .001 | 0.48 |
| MEDI_SLIME | 5.1% | 6.1 | .014 | .002 | .000 | 0.72 |

Writer seconds are from region 05605CAA, 8 workers (n = 15-136 per preset). Rooms (7-13) don't predict modules: P(>=3) is 3.6-4.2% for every room count.

Candidate filters over the atlas. Recall = share of all systems with >= k modules that survive. Speedup is modelled with the measured
per-preset writer cost + 0.53 s post-writer cost; stage-A rejects cost 0.

| filter | full pipeline on | R>=2 | R>=3 | R>=4 | model speedup |
|---|---|---|---|---|---|
| none (baseline) | 100% | 100% | 100% | 100% | 1.00x |
| containers >= 19-20 only (stage B) | 66% | 90.5% | 96.5% | 98.8% | 1.08x |
| containers >= 28 only | 44% | 73.3% | 84.5% | 91.9% | 1.14x |
| drop MEDI_SLIME + MEDI_BUGS | 74% | 93.3% | 97.4% | 98.8% | 1.13x |
| **balanced: CARGO_FLOATERS/TURRETS/MAZE/BUGS (+ c >= 19)** | **44.4%** | **71.2%** | **83.0%** | **91.5%** | **2.84x** |
| **fast: CARGO_FLOATERS/MAZE/BUGS (+ c >= 19)** | **31%** | **46%** | **52%** | **56%** | **6.7x** |
| CARGO_FLOATERS/MAZE only | 10% | 19% | 26% | 34% | 19x |

In hits per hour (>= 3 modules), balanced is about 0.83 x 2.84 = 2.4x the baseline and fast about 0.52 x 6.7 = 3.5x. For >= 4 modules, balanced
keeps 91.5% of the hits at about 2.8x.

What each stage knows first, and what it costs (one worker, 80 systems, backlog paused):

| stage | knows | cost per system |
|---|---|---|
| A seed -> preset (`derelict_seed_preset_705`) | preset, writer seed | ~3 us |
| writer (NativeSession) | room count, room templates, placements -> **exact container count** | 2.35 s mean (0.07-32 s) |
| fast generator transforms/containers (incl. derive 0.03 s, JSON I/O) | container positions | 0.14 s |
| space-POI (Shipwright SystemGen under Unicorn) | ABAND_FREIGHTER position | 0.41 s |
| crate loot + summarize | frigate_modules, ambiguity, rooms, ids | 0.012 s |

Total: 2.92 s per system, 0.34 systems/s with 1 worker. The other agent's generator-profile report
(`GENERATOR_PROFILE_20261022.md`) was not present yet when this was written.

## Step 2: the searcher

```
python -I tools/frigate_search_705.py --region 05605CAA --min-modules 3 --workers 8              (balanced, default)
python -I tools/frigate_search_705.py --region 05605CAA --min-modules 4 --profile fast --workers 8
python -I tools/frigate_search_705.py --region XXXXXXXX --systems 001-21B ...   (region not in the atlas: give the range)
python -I tools/frigate_search_705.py --region 05605CAA --no-filter --workers 8                  (baseline)
python -I tools/frigate_search_705.py 0001056005605CAA ...   |   --addresses-file FILE
```

- Stage A: preset in `--profile` (balanced / fast / all) or `--presets A,B`.
- Stage B: exact crate+footlocker count from the writer placements. Reject if below `--min-containers`.
  `auto` is the smallest count with P(>= min-modules) >= `--tail` 0.01: 19 for 3 modules, 34 for 4, 7 for 2.
  A template id missing from the table counts as 0 there; the 56 unseen ids are mostly decor that derelicts never place.
- Stage C: the unchanged fast generator (it reuses the writer result already in memory), POI, `predict_crate_loot_705.predict`, and
  `crate_loot_worker_705.summarize`, the same code as the scanner.
- Persistent BelowNormal workers (Shipwright venv python). Jobs are submitted longest-first by preset writer cost.
- Output in `D:/Orca/Temp/claude/frigate-search-20261022/` (`--out-dir`): `frigate-search-<tag>-hits.csv` (address, glyphs,
  preset, rooms, crates, footlockers, containers, frigate_modules, ambiguous, module rooms/ids/alt ids),
  `-all.csv` (every system that reached the worker, with stage, container estimate and per-system seconds), and
  `-log.json` (counters, wall times, CPU seconds per stage).

## Step 3: validation (region 05605CAA, galaxy 0, 559 systems 001-22F, frigate_modules fully filled in the atlas)

- `--no-filter`: 559/559 systems match the atlas in preset, rooms, crates, footlockers, frigate_modules, ambiguous, module rooms, ids and alt ids. **0 mismatches.**
  The same holds for the 3 repeat runs and the 1-worker run.
- The filtered runs also have 0 mismatches on every system that reached stage C. The stage-B container estimate matched the generator or atlas count on every
  system, 1,207 checks, 0 mismatches.
- Recall in this region against the full truth (20 systems with >= 3 modules, 74 with >= 2, 2 with >= 4):

| run | full pipeline on | >= 2 | >= 3 | >= 4 |
|---|---|---|---|---|
| balanced | 262 (46.9%) | 49/74 (66%) | 13/20 (65%) | 2/2 |
| fast | 188 (33.6%) | 34/74 (46%) | 11/20 (55%) | 2/2 |
| all presets, c >= 19 | 386 (69.1%) | 67/74 (91%) | 18/20 (90%) | 2/2 |

  This region has more MEDI 3-module systems than average: 7 of 20, against 15% atlas-wide. So its recall is below the atlas-wide figures (83%, 52%),
  which are the better estimate. The two systems that stage B missed had 3 modules from only 11 and 14 containers (luck).

## Step 4: speed (region 05605CAA, 559 systems)

**All timing runs were taken with the scanner backlog paused by the user.** The backlog workers' CPU counters didn't change. The other agent's profiling
was still running: the background load was **27.5% before the runs** with nothing of mine running. The PC has 12 logical CPUs.

| run | workers | wall | systems/s | hits >= 3 | avg CPU load |
|---|---|---|---|---|---|
| baseline --no-filter | 1 (80 systems) | 233.9 s | 0.34 | - | 36% |
| baseline --no-filter | 8 | 179.7 s (189.5 s before longest-first order) | 3.11 | 20 | 75% |
| baseline --no-filter | 12 | 167.6 s | 3.34 | 20 | 90% |
| balanced | 8 | **66.3 s** | **8.43 (2.7x)** | 13 | 76% |
| balanced | 12 | 73.1 s (before longest-first order) | 7.65 | 13 | 88% |
| fast | 8 | **31.7 s** | **17.6 (5.7x)** | 11 | 61% |
| fast | 12 | 39.2 s (before longest-first order) | 14.2 | 11 | 78% |

All runs include about 3.4 s worker start-up. 12 workers barely beat 8: CPU is shared with the profiler, and with hyperthreading the extra threads add little.

Extrapolation on this PC, 8 workers, about 560 systems per region:

| mode | per region | per 1,000 regions | >= 3-module hits per hour |
|---|---|---|---|
| baseline | ~3.0 min | ~50 h | ~400 |
| balanced | ~1.1 min | ~18 h | ~700 |
| fast | ~0.55 min | ~9 h | ~1,250 |

The hits per hour assume the atlas-average hit rate of 4.0% of systems with >= 3 modules. The live scanner backlog (1.65 systems/s with 7 workers while it
competes with region scans) is consistent with the baseline cost per system.

## Next steps

1. **The writer is the bottleneck.** About 75% of all writer time on this region goes to TURRETS presets and MEDI_FLOATERS. Two things would make the balanced filter
   much faster:
   - an early-exit or cheaper container count inside the writer (for example, stop once the placement records are complete), or
   - finding why TURRETS presets retry so long.
   Either one is a change to shared fastgen code and needs a REQUEST to its owner. See the profiling report when it lands.
2. The POI step (0.4 s, Unicorn) runs only for survivors, but it could be cached per address or skipped for systems whose container count
   can't reach the target.
3. For new (not yet scanned) regions, `--systems` must be given. Hooking up the fastgen `region-count` logic (read-only) would make that automatic.
4. Optionally run unscanned regions with `--profile fast --min-modules 4` and feed hits to the viewer. Nothing is published by this tool.
