# Writer-cache trim + real system names (2026-10-24, Claude)

NMS was not launched. The scanner was not started, stopped or restarted by me (another agent restarted it at 00:35 with the cache on). Nothing was committed or pushed. Backups: `*.pre-names-cachetrim-20261024`. Scratch: `D:/Orca/Temp/claude/cachetrim-20261024/` (results in `res/`, `runs/`).

## Task A: writer-cache trim (live in `D:/Orca/NMS-Derelict-Probe-fastgen/native_writer_705.py` and `app/config.py`)

Changes (format 2, new SQLite table `writer2`; the old table `writer` and its format-1 rows are never read, and the version key also changed):
- An entry is stored only if the writer run took at least `writer_cache_min_seconds`. Default 2.0 (in `DEFAULTS` of config.py, so it applies even when settings.json lacks the key). The env var `NMS_WRITER_CACHE_MIN_SECONDS` wins, and the module default is 2.0 too, so workers are right even before the app restarts. I did not edit settings.json (the running scanner rewrites it); add `"writer_cache_min_seconds": 1.0` there to change it, then restart.
- The record is byte-transposed (the 20-byte placement records column by column) plus raw LZMA2 (lc=2, pb=0, 64 KB dictionary), with one format byte. zlib-9 gave 1,220 B per record; this gives about 885 B. Also tried: zlib with a preset dictionary 1,020 B, bz2 1,190 B.
- The biggest saving was the table layout, not the compression. The old `WITHOUT ROWID` table spilled every ~1.2 KB row to a whole 4 KB overflow page, which is where 4.6 KB per entry came from. It is now a rowid table with a 16-byte version blob.
- The version key covers the same things as before (exe, tables, writer file, writer/hook addresses, build_inputs code) plus the format number. The on/off setting is unchanged.

### Size
| | per entry | 160k systems |
|---|---|---|
| before (all entries, zlib, WITHOUT ROWID) | 4,628 B on disk (1,388,544 B / 300) | ~740 MB |
| after, 300-system test set (26% stored) | payload 895 B; file 1,313 B per stored entry (102,400 B / 78, includes fixed pages) | n/a |
| after, region 0460ACAA (28% stored) | payload 885 B; file 1,245 B per stored entry (184,320 B / 148) | n/a |
| projection | ~1.0-1.3 KB per stored entry x 20.3% of systems (> 2 s) x 160k = 32.5k entries | **about 33-43 MB** (about 95% less) |

The test sets lean toward slow TURRETS systems, so 26-28% stored is above the 20.3% population share.

### Exactness (300 systems, `addrs300.txt`; reference = unmodified live writer, `ref.jsonl`)
| run | identical to reference | hits | generate s (sum) | TURRETS (108) | slowest 10 |
|---|---|---|---|---|---|
| off (new file, cache off) | 300/300 | 0 | 861.5 | 675.4 | 296.5 |
| cold (empty cache) | 300/300 | 0 | 882.9 | 686.1 | 296.1 |
| warm | 300/300 | 78 | **189.5** | **61.1** | **2.6** |
| mixed (every 2nd stored entry deleted) | 300/300 | 42 | 507.1 | 345.9 | 125.7 |

"Identical" means derelict.json without run-time fields, all writer output files and the exit codes (`cache_compare.py`). Scanner load varied between runs.
- Re-run speed-up, cold to warm: 4.7x overall (882.9 to 189.5 s), TURRETS 11.2x, the slowest 10 about 114x. Before the trim, caching everything gave 15.9x overall and 39.8x on TURRETS. That is the price of storing 95% less: only 78 of 300 systems (26%) are in the cache, and the rest cost under 2 s each so they are recomputed.
- Option: `writer_cache_min_seconds = 1.0` would store ~35% of systems (about 70 MB for 160k) and cover 86% of writer time (estimated from the DB table, not measured).

### Searcher (0460ACAA, 531 systems, 8 workers; fill run then re-run; scanner running)
| profile | cold | cached before trim | cached after trim (writer hits) |
|---|---|---|---|
| no-filter | 3.78/s | 17.5/s | 6.15/s (132/531) |
| balanced | 11.9/s | 46.0/s | 14.98/s (54/225) |
| fast | 22.2/s | 57.6/s | 20.74/s (23/168) |

`tools/frigate_search_profiles_705.json` is updated: cached figures for 8 workers; the 3-worker and `all` cached figures no longer apply and were removed; the old values are kept under `warm_full_cache_20261023`; the reason is in `warm_note`.

### Tests run (real outcomes)
- `cache_guard_test.py` (min seconds set to 0 for it, because its two systems are fast): PASS (same inputs 2/2 hits; changed exe and replaced build_inputs give a new key and 0 hits; cache off).
- Config test `cfg2.py`: default 2.0, settings value 5 gives 5.0, external env 7 wins; `writer_cache_stats()` reads the new file.
- `python -I tools/test_scanner_update_guard.py`: 11/11 PASS (RESULT PASS).
- `python -I tools/regression_test_705.py` (fast): **26 passed, 0 failed, 1 skipped** (b needs --full), 122 s. It includes `c) derelict_view.py --verify` PASS and the new name checks h1-h3.
- `py_compile` of native_writer_705.py and config.py: OK.
- Not tested: the running scanner picking up the new config key (needs a restart; workers it starts already use the new writer file). Workers started before about 00:31 wrote format-1 rows into the old `writer` table of the shared cache file. They are harmless and can be removed with `DROP TABLE writer` when the scanner is idle.

## Task B: system names

The user changed this mid-task: **no stored `system_name` column**; names are computed from the address. Nothing was added to the scanner DB, `index/systems.csv.gz` or any builder.

New files: `tools/system_names_705.py` (Python port; MIT notice and credit in the header), `tools/system_names_705_data.json.gz` (314 KB: the 8 alphasets and the letter map, flattened; equal to the upstream tree search for all 24,458 leaves), `tools/js/system_names_705.js` (**8.5 KB, 3.6 KB gzipped**; browser global `NMSNames` or node; two-uint32 arithmetic, no BigInt), `tools/system_names_705_vectors.json` (568 upstream vectors), `tools/system_names_705_parity.js`. `tools/regression_test_705.py` got checks h1-h3.
Usage: `name("0000360006607CAA")` or `name("03E9F3545C3E", 0)`. The sources were downloaded as data into `D:/Orca/Temp/claude/namegen-20261024/{hadsh,elegra}`; no script of theirs was run, and the elegra1965 nms-core was read only as a cross-reference.

### Verification (honest)
- Upstream vectors: 562 "AGT-verified" names (`system_names.json`, galaxy 0): **562/562**. 443 golden vectors (generated by the upstream library itself, so regression only; 6 galaxies): 443/443. 6 unit-test names: 6/6. Upstream says it has not scored names against its own ground truth because that would be circular.
- Our own in-game captures (`live-runtime/NMSDerelictSurveyor/capture-journal-*.jsonl`, probe fields `system_name` next to `universe_address_hex`): 7 distinct systems, **6/7 exact**: `00006D0006606CAB` Stlepiosc XIX, `0000750006606CAB` Ruflas-Simly V, `0000790006606CAB` Gersid XVI, `0001550006607CAC` Uzawan XI, `0001680006607CAC` Otsues, `0001BF0004E84EFD` Angoto.
- One mismatch: `0000760006606CAB`, game "Irchol-Luhimo XVII", port "Irchol-Luhomo". Float32 variants (target, weight sums, index) did not change it. The second half starts with the triplet "lho" in the port where the game must have "lhi", which points at an entry in upstream's alphaset 4 data rather than a porting error (the port agrees with upstream on all 1,000+ vectors). Not proven.
- `0000360006607CAA` and `0000FE0006607CAA`: no in-game system name for them exists in our files (only the freighter "SS Hinoku XV" for FE).
- Match rate on our own data is 6/7 (86%), a tiny sample; the upstream data suggests about 99%. So the name is very likely right but unverified: keep the label **unverified** in the UI until more in-game names are collected (the probe records the name at every capture, so the sample grows for free). Players can rename systems, which this cannot know.

### Parity and speed
- Python == JS on 2,000 random atlas addresses plus 562 AGT plus 443 golden addresses: 3,005 cases, 0 mismatches. The regression check repeats it on 300 + 100.
- Naming all 185,078 index rows in node takes 0.82 s on the first pass and 0.54-0.56 s warmed; data load + init is 87 ms. Browser time should be of the same order, so under 1 s: name on load (or lazily in chunks) and make it searchable. The data download is 314 KB (gzip), once.

### Not done / blocked
- Viewer wiring (`viewer/static/*`: table column, search, system page title, Credits entry 2 "hadsh/nms_namegen, MIT; original by Stuart Coyle with GoodGuysFree") is **blocked** on the public-site agent's DONE in `NMS-COORDINATION.md`, as instructed. It had not posted when this report was written.
- Recipe: load the gz with `DecompressionStream`, call `NMSNames.init(json)`, then `NMSNames.name(address16)` per row, where address16 = `000` + glyphs[1:4] + galaxy as 2 hex digits + glyphs[4:]. The Pages copy needs `system_names_705.js` and the data file next to the viewer.
