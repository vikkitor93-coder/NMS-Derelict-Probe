# Name check (NMS Almanac), writer cache OFF, Generate-map progress, requested-map shards, Pi relay PC side (2026-10-24, Claude)

NMS was not launched. The scanner (8790) was not started, stopped or restarted by me. Nothing was exposed (no Funnel, no tunnel; every test socket is on 127.0.0.1, the relay-listener test used 127.0.0.2). Backups of every edited file: `*.pre-namecheck-eta-20261024`. Scratch and raw API answers: `D:/Orca/Temp/claude/namecheck-20261024/`.

## 1. Writer-result cache: default OFF

- `D:/Orca/NMS-Derelict-Probe-fastgen/app/config.py`: `DEFAULTS["writer_cache"]` is now `False` (code and switch kept; `"writer_cache": true` in settings.json turns it back on; env `NMS_WRITER_CACHE` still wins).
- IMPORTANT: the scanner's `settings.json` (`.../emu/fastgen/app-data/settings.json`) had `"writer_cache": true` stored explicitly, which overrides a changed default. I changed that line to `false` (backup `settings.json.pre-namecheck-eta-20261024`). The running scanner holds the old value in memory and may write the file again before it is restarted; if the line says `true` after a restart, set it to `false`. Takes effect at the next scanner restart (the user does that).
- Status line: `app/web/simple.html` now says "Writer cache off (default since 2026-10-24; no results are stored or reused)" when off (backup kept).
- On-demand map server: it does not rely on the writer cache (it has its own per-map result cache, which stays). Its config default `writer_cache` is now `"off"`, so generation is the plain cost and the ETA table matches. Cost: a system whose writer result is still in the old cache file is no longer sped up. Clearly not harmful, because every requested map is generated once and then served from its own cache.
- Old cache file, not deleted: `D:/Orca/NMS-Derelict-Probe-analysis/writer-cache/writer-cache-v1.sqlite` is 16,211,968 bytes (15.5 MB) plus `-wal` (about 1 MB) and `-shm` (32 KB) at 02:22; the running scanner is still writing to it until it is restarted. Delete the three files (or the folder) after the restart.
- Tests run: config test `D:/Orca/Temp/claude/namecheck-20261024/cfg_off.py`: no key -> DEFAULT False and `NMS_WRITER_CACHE=off`, stats `on=False`; settings `true` -> on; external env wins. `tools/test_scanner_update_guard.py`: RESULT PASS (all PASS lines).

## 2. Names checked against NMS Almanac: 19 of 20 matched; the one miss is fixed; "unverified" removed

- Exactly 20 API calls were made (`calls.txt` has 20 lines, 3 s apart, sequential, all HTTP 200, no 429, no Retry-After seen; the word table was not needed because the answer carries `names.game`). Portal = "1" + our 11 glyph digits (P=1), `?galaxy=1` (the Almanac numbers galaxies from 1; Euclid = 1). Raw answers: `D:/Orca/Temp/claude/namecheck-20261024/raw_NN_<portal>.json` plus `meta_NN.json`, results in `results.json`. Responses were treated as data only.
- Sample: 1 known mismatch + 19 picked at random across the 10 presets (each preset twice) and 19 different system indexes (SSS), all galaxy 0.
- The Almanac shows the numeral suffix inside the name (`"names":{"game":"Irchol-Luhimo XVII"}`), so both were compared exactly and without the suffix: 19/20 identical either way (suffixed names in the sample: Oichibet V, Tiffordi XV, Yanshan-Sama V, Iliersa-Nebets XIII, Iuquanpin XV all matched).
- The miss: `0000760006606CAB`, ours "Irchol-Luhomo", Almanac "Irchol-Luhimo XVII" (also what the game showed in our own capture). So it is an upstream data difference, not a porting error. I could not find which table entry is wrong (replacing the alphaset triple "lho" and/or the letter-map key did not reproduce "Luhimo"), so I did NOT edit the data tables. Fix: a small verified-corrections table `_OVERRIDES = {"0000760006606CAB": "Irchol-Luhimo XVII"}` in `tools/system_names_705.py`, `tools/js/system_names_705.js` and the viewer copy `viewer/static/names.js` (still byte-identical). Python and JS agree on the 20 sample systems (node parity 21 cases ok).
- New regression check h5: Python port == the Almanac name for all 20 sample systems (`tools/system_names_almanac_sample.json`). `NAME_STATUS` is now "checked".
- UI: the "unverified" chip is replaced by a "name checked" chip (tooltip: checked against NMS Almanac on a 20-system sample, 20/20 after one correction, players can rename); share text, share cards and the column tooltip no longer say unverified. Credits: Shipwright first, nms_namegen second, new third entry "NMS Almanac" (https://nmsalmanac.com): "Names checked against NMS Almanac (20/20 sample, after one correction). Data: NMS Almanac." (no Almanac data is shown or stored).
- Honest limit: 20 systems is a sample; it says nothing about player-renamed systems.

## 3. Generate map: what is happening (server + client)

New/changed: `ondemand/ondemand_server.py`, `ondemand/eta_config.json` (the ONE place for the ETA table and all wording), `ondemand/build_eta_table.py` (rebuilds the table from the scanner DB, read-only), `viewer/static/ondemand.js`, `viewer/static/app.js` (`wireOnDemand`), `viewer/static/app.css`.

- **Preset from the seed** (`derelict_seed_preset`, 12 microseconds) and rooms from the scanner DB (known for scanned systems) arrive in the first status, before anything is generated.
- **Endpoints (all GET, JSON, validated, rate-limited, no IP logged)**
  | Route | Use |
  |---|---|
  | `GET /api/status/<ADDR16>` | NEW. Read-only progress; never starts a job and does not use the miss limiter. Fields: `status` idle/queued/generating/ready/failed, `stage` 0-4, `preset`, `rooms`, `position`, `queue`, `running`, `eta_s`, `elapsed_s`, `overdue`, `slow`, `upto_s`, `scanner_busy`, `poll_ms`, `msg` (ready-made texts: title, kind, rooms, queue, busy, left, over, stages). The address is the job id; nothing else is kept per client. |
  | `GET /api/map/<ADDR16>[?wait=S]` | unchanged; 202 now carries the same status fields. `?wait=0` starts the job without holding the connection. |
  | `GET /api/health` | unchanged. |
  A plain pass-through proxy can forward all three unchanged (the Pi relay allowlist now has the status route).
- **ETA** = free-slot simulation: running jobs free their slot after (expected - already run); queued jobs ahead take the earliest free slot in order; then this one. Expected seconds of a system = its own `writer_seconds` in the scanner DB when it has one (else the preset median), times the load factor (1.25 when the scanner DB was written in the last 120 s = "scanner busy", else 1.0), plus 0.7 s overhead, plus 6 s worker start when no worker process is warm. Table (median / p90 / p99 per preset) is in `eta_config.json`, rebuilt by `build_eta_table.py`. Scanner busy is judged from the scanner DB's last write time (a process scan takes 17 s on this PC, too slow); this is an approximation.
- **Stages** reported by the server: Waiting in queue, Checking the system, Generating layout, Packing map, Done. ("Placing containers" is part of the generator and not visible from outside.)
- **Visitor sees** (example for a slow system): "Generating map... TURRETS derelict" / "TURRETS derelict: these take longer, up to ~44 s" / "10 rooms" / "Position 2 of 4 in queue" (updates every poll, moves up as the queue shrinks) / an animated bar with a pulsing dot / "about 25 s left · 40%" counting down in the browser between polls / "The map server is also scanning right now, so this may be slower" / stage list with the current step marked. The percent is elapsed / ETA, held at 95% and never decreases; when the ETA has passed the bar keeps moving (shimmer), the text becomes "taking longer than usual... still working (elapsed 85 s)" and the queue position and the scanner note stay. Success: "Map ready, drawing...". Failure texts: busy "try again in N s", timeout "the map took too long, try again in N s", offline "Map server offline, try later.", rate limit, unknown system.
- **Accessibility:** one `aria-live="polite"` region whose text changes only on a meaningful change (stage, queue text, overdue), while the per-second countdown is `aria-hidden`; `role="progressbar"` with `aria-valuenow`; `prefers-reduced-motion` replaces the pulse and shimmer with a calm opacity fade.
- **Polling cost:** one status request every 1.0-2.0 s (poll_ms 1500), about 700 bytes of JSON; if a job vanishes (3 idle answers after it started) the client stops with "busy".

### Tests run (real outcomes)
`python -I ondemand/tests/eta_test.py` (own server on 8797, 1 worker, always generate, writer cache off, scanner running with its workers, so timings include its load). Final run, predicted (first ETA after the request) vs actual seconds:
| Case | Predicted | Actual | Ratio |
|---|---|---|---|
| A cached system | status "ready", ETA 0 | map in 8 ms | - |
| B1 fast, cold worker (MEDI_BUGS) | 8 | 13.7 | 0.58 (within 2x) |
| B2 fast, warm | 2 | 2.5 | 0.8 |
| B3 fast, warm | 2 | 1.1 | 1.8 |
| C slow MEDI_TURRETS (DB writer 34.4 s) | 44 | 41.8 | 1.05 |
| D 3-request queue, request 1 / 2 / 3 | 2 / 4 / 6 | 2.3 / 4.5 / 6.4 | 0.88 / 0.90 / 0.93 |
All within 2x. Earlier runs, before I set worker start to 6 s and the overhead to 0.7 s: cold worker predicted 2 vs 15.3 actual, then 14 vs 4.1 actual (worker start varies 4-15 s under load), warm cases 0.99-1.9, TURRETS 1.5 and 1.04, queue 1.1-1.4 and 0.5-0.9. Also passed: status of an idle system starts nothing (health queue 0, running 0), 400 / 400 / 404 / 405 on bad input, the log holds no client IP and none of the requested addresses (the log has only the start line).
- `node ondemand/tests/client_test.js http://127.0.0.1:8798 0000010003606CAD 0000010003606CA8`: all passed (request through status polls ending "ready", renderer container counts equal the summary, offline text, unknown system, 5 view-function checks: queue text and countdown, 95% cap, "taking longer than usual... (elapsed 85 s)" with queue and busy note kept, no percent going backwards, ready = 100%, and the button flow against a fake DOM including the aria-live text).
- A real browser run of the new UI was not possible (no browser here): only the Node tests with a fake DOM. The CSS animation and reduced-motion rules are untested visually.

## 4. Requested maps published to the atlas

- **Tool:** `tools/publish_ondemand_maps.py` (stdlib). Reads the server's cache read-only, skips maps already in the top-100 bundle and maps that came from stored layouts, re-checks every map (decode, round trip, view counts equal the summary, and preset/rooms/crates/footlockers equal the scanner DB when it knows the system), merges into `views/ondemand/<REGION>.json.gz` (REGION = last 8 hex digits of the address). Each file is `{"v":4,"t":<piece table of this file's maps>,"s":{addr: compact v4 view},"m":{addr: summary}}`; deterministic; only adds or replaces.
- **Scanner hook or separate run?** I did NOT edit the scanner. Reason: the scanner only publishes when it uploads a region (it may be idle or stopped for days), requested maps should appear regardless, and a hook would add risk to scanner-owned code. Instead `python -I tools/publish_ondemand_maps.py --push` (or `ondemand\Run-Publish-OnDemand-Maps.cmd`) builds, commits and pushes a plain fast-forward under `atlas.repo_lock`, at most one push per 30 minutes (state in `ondemand/publish-state.json`), and does nothing when no shard changed. It was NOT run against the real atlas (the real cache holds only test maps); nothing was pushed for it. It can be called from `_derived_files` later (one line) if the scanner owner wants.
- **Viewer:** a system without a stored map first looks for its region file `views/ondemand/<REGION>.json.gz` on the site; if the map is there it is drawn from it with a "Requested map" chip and note and no "Generate map" button; only otherwise the button shows. (A 404 for a region without requests is one tiny failed fetch per visit.)
- **Tests run:** 7 generated maps in a scratch atlas: 6 shard files written; second build changes 0 files; a second independent build gives identical bytes (SHA-256 of all 6); a shard built in two steps (1 map, then +1) equals the one-shot shard byte for byte; `ondemand/tests/shard_compare.js`: the map drawn from the shard equals the map drawn from the direct server response (compact.js expand, model.js unpack and build, deep equal) and the summaries are equal, "identical render and summary for 7 maps".
- **Sizes (gzip):** measured single-map files 4,917 to 5,562 bytes (mean 5.3 KB; the piece table is about 4.5 KB of it); one file with 2 maps 8,687 bytes. Projection, from those and from a synthetic test with 1-100 top-list maps per file (a shared piece table amortises: 14.0, 7.4, 3.3, 2.0, 1.3, 0.87, 0.72 KB per map for 1, 2, 5, 10, 20, 50, 100 maps per file; those maps are bigger than typical, so treat the clustered figures as an estimate):
  | Requested maps | every map in its own region (worst case) | about 10 per region (estimate) |
  |---|---|---|
  | 1,000 | about 5.3 MB in 1,000 files | about 2 MB in about 100 files |
  | 10,000 | about 53 MB in 10,000 files | about 20 MB in about 1,000 files |
  Per-region sharding keeps the lookup trivial but, for scattered requests, makes many small files (the user wants few). If that happens, a coarser shard key (e.g. the first 4 hex digits of the region) is a one-line change in `region_of()` and the viewer's `ondemandShard()`; not done.

## 5. Pi relay, PC side (per `research-output/PI_RELAY_20261024.md`)

- `ondemand_server.py`: new config `tailnet_bind` (default "" = off) and `relay_ips` (default []). With both set to Tailscale addresses (100.64.0.0/10 or fd7a:115c:a1e0::/48; anything else and the listener is not started) a second listener serves `tailnet_bind:8791`, shares limiters, queue and cache with the loopback one, and closes every peer not in `relay_ips` without an answer. `X-Relay-Client` (18 lowercase hex) is used as the visitor key only when the TCP peer is in `relay_ips`; otherwise it is ignored (the loopback `X-Forwarded-For` rule is unchanged). Loopback stays; nothing else is bound; the PC's Tailscale IP is NOT in the config (empty, disabled).
- Docs: `ondemand/EXPOSE.md` section (d) with the config, the API table and the firewall command `New-NetFirewallRule -DisplayName "NMS on-demand (Pi relay only)" -Direction Inbound -Protocol TCP -LocalPort 8791 -RemoteAddress <PI_TAILNET_IP> -InterfaceAlias Tailscale -Action Allow` (NOT run; the user runs it in an administrator PowerShell). A Tailscale ACL is a good second lock.
- `D:/Orca/NMS-Traffic-Logger/relay.py` `route()`: added `GET /api/status/<ADDR16>` (same address checks as the server, query dropped, not cached). Tests: `tests/test_relay.py` 23 tests OK (was 22; added route cases and a forwarding test); `tests/e2e_relay.py` against the real server: 38 passed, 0 failed (it started and stopped its own server; no listener left on 8791).
- `python -I ondemand/tests/tailnet_test.py`: all PASS (refuses an empty or non-tailnet config, serves the listed peer on a 127.0.0.2 stand-in, closes other peers, relay keys are separate buckets only from a relay peer, the header is ignored from a non-relay peer, malformed values ignored). The real tailnet path (Pi to PC over Tailscale) is untested: the Pi is not on the tailnet yet.

## 6. Publish
See the end of STATUS.md for the commit; the regression result is below.

## Regression and other suites
(filled in at the end, see STATUS.md)
