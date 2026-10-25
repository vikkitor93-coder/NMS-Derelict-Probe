# On-demand map server (2026-10-24, Claude)

User request: let visitors of the public static site ask for the map of ANY system; a small server on the user's PC makes it
with the existing generator. Visitors must not learn the home IP; the exposure (Tailscale Funnel / Cloudflare) is decided later.
**Nothing was exposed.** The server binds to 127.0.0.1 only (hard-coded). NMS was not launched, the scanner (port 8790) was not
started, stopped or restarted by me, nothing was committed or pushed, the atlas clone was not written. Backups of edited files:
`*.pre-ondemand-20261024`.

## What was built

All new files are in `D:/Orca/NMS-Derelict-Probe/ondemand/`:

| File | Purpose |
|---|---|
| `ondemand_server.py` | the public API (stdlib only, one file) |
| `Run-OnDemand-Server.cmd` | double-click start (127.0.0.1:8791, Ctrl+C stops) |
| `EXPOSE.md` | exposure plan (a) Funnel, (b) Cloudflare named tunnel, (c) quick tunnel; NOT done |
| `tests/run_tests.py`, `tests/timing.py`, `tests/client_test.js` | the tests below |

Viewer side (edited after both other agents posted DONE): new `viewer/static/ondemand.js` (client), `app.js` (`loadDerelict`,
`atlasOnlyView`, new `wireOnDemand`, a note on generated maps), `app.css` (2 rules), `index.html` (1 script tag), `config.js`
(`"ondemandBase": ""`), `tools/build_public_site.py` (whitelist + passes `ondemandBase` into the published config only when set).
With `ondemandBase` empty the published `config.js` is byte-identical to the current one (checked), and the button is hidden.

### API (exactly two routes)

- `GET /api/map/<ADDRESS16>[?wait=S]` -> 200 `{"v":4,"t":<piece table of this map>,"s":{ADDRESS16:<compact v4 view>},"m":{address, galaxy, preset, rooms, crates, footlockers, modules, modules_ambiguous, source}}`.
  This is a one-system bundle in the same shape as `viewer/static/compact/top100.v4.json.gz`, so the existing compact renderer
  (`compact.js expand` -> `model.js unpack/build`) draws it unchanged. 202 `{status: queued|generating, position, queue, eta_s}`
  while it works (the page polls the same URL with `?wait=3`; `wait` is capped at 90 s), 400 bad input, 404 no such system,
  429 rate limit, 503 busy.
- `GET /api/health` -> `{"ok":true,"queue":n,"running":n,"cache_entries":n,"cache_bytes":n,"clients_1min":n}` (`clients_1min` is a
  count only, to check that a tunnel passes the client address).
- Everything else 404; PUT/POST/DELETE 405; any request body 400. No files, no assets, no route to the scanner.

### Behaviour

- **Validation:** exactly 16 hex characters, `000 SSS 00 YYZZZXXX` (galaxy 0 only, other galaxies 400). The system must exist: the
  scanner's own rule (`engine.py safe_top`): in the scanner DB, or 1 <= index <= region count - 1 - edge_margin (8, or the scanner
  setting), raised to a confirmed visit. Region counts come from the scanner DB `regions` table (read-only), else this server's
  own table, else a lazily started `app/rc_worker.py` (Unicorn) whose answer is stored. An unseen region worked in the test
  (first count 34.8 s together with the first worker start, later counts about 2.5 s).
- **Generation:** 1-2 persistent `tools/scan_worker_705.py` processes (the live combined worker: native writer, writer cache on,
  fast POI, frigate module summary), started lazily, BelowNormal priority, stopped after 10 idle minutes. The layout is packed
  with the same code as the top-100 bundle (`derelict_view.pack` + `derelict_view_compact.encode`).
- **Scanner DB reuse (read-only URI):** a system in it exists without a region count; the 100 full layouts it stores are used
  without generating (`source: "scanner-db-layout"`, 0.22 s max in the test). Other systems have no stored layout (the DB and the
  scan cache keep no placed pieces), so the map part has to be generated; only the part that is missing is.
- **Cache:** own SQLite file `ondemand/cache/ondemand-cache-v1.sqlite`, zlib JSON per system. Measured 1,295 bytes per system
  (40 systems = 51,807 bytes; the view alone is about 700 bytes gzipped). A response is about 5.2 KB gzipped, of which about 4.5 KB is the
  piece table of that map. The cache is dropped if the pinned game exe size or the format key changes. A small in-memory LRU
  (512 maps) holds the finished response bytes.
- **Abuse limits** (config values in `DEFAULTS`): queue cap 20 queued generations; 10 new generations per client per minute and
  120 requests per client per minute (in memory, keyed by a salted hash of `CF-Connecting-IP`, else `X-Forwarded-For`, accepted
  only when the connection comes from the local tunnel, else the peer address; the salt is random per run, nothing goes to
  disk); a queued job older than 90 s is dropped with 503 "busy, try later"; a running job over 150 s is killed (503); no bodies;
  64 concurrent connections; 15 s socket timeout.
- **CORS:** `https://vikkitor93-coder.github.io` (config value `allowed_origins`) plus `http(s)://localhost` and `127.0.0.1` on any
  port. Any other `Origin` gets 403 and no `Access-Control-Allow-Origin`. No `Origin` header (curl, health checks) is allowed.
- **Logging:** no access log at all; only an aggregate counter line every 10 minutes (e.g. `requests=… cache_hits=… generated=…
  http_404=…`). No IPs, no user agents, no addresses. Verified in the tests.

### Viewer button

On the public site a system without a stored map (`atlasOnlyView`, no local server) shows **Generate map** when
`DV_CONFIG.ondemandBase` is set. It shows "Connecting…", "Waiting in the queue: 2 of 5, about 10 s…", "Making the map… 12 s",
then redraws the page with the generated map (all floor maps, 3D view, hazards, containers) and a note that it was made on demand.
Server offline or tunnel down: "Map server offline, try later." (button becomes "Try again"). Busy, rate limit, unknown
system and unsupported galaxy have their own texts. Leaving the page cancels polling.

## Tests (all run; real outcomes)

Servers started by the tests on 127.0.0.1:8791-8796 with throw-away caches; the scanner kept running (6 workers) the whole time,
so timings include its load.

| Test | Result |
|---|---|
| 20 top systems (random from the published atlas bundle `views/top100.json.gz`, 194 systems), generated, compared by scene name against the bundle (format 3 after decoding v4), and for the 5 that are in the viewer's `compact/top100.v4` also the v4 view and piece-table rows | **0 mismatches** |
| same 20 via the scanner-DB layouts path (8 of the 20 are also in the compact v4) | **0 mismatches**; 5 served in 0.22 s max |
| 20 non-top systems (4 TURRETS + 16 others, random, from the scanner DB) vs the scanner DB: preset, rooms, crates, footlockers, modules, modules_ambiguous, and crates/footlockers/rooms recounted from the decoded v4 | **0 mismatches** |
| cache hit (60 repeat requests) | mean 9.8 ms, worst 36.5 ms (another run: mean 6.3, worst 24.5); under 50 ms |
| queue cap 3, 1 worker, 9 simultaneous distinct uncached requests | 4 x 202 (1 running + 3 queued), 5 x 503 with `Retry-After` |
| per-client miss limit 3/min | 404, 404, 404, then 429 x3 (Retry-After set); a second client unaffected; peer address has its own bucket |
| request limit 120/min | 120 x 200, then 429 |
| CORS | public origin, localhost, 127.0.0.1 allowed; evil.example, the public origin with a suffix, http instead of https, another github.io, `null`, `localhost.evil.com` all 403; preflight 204 / 403 |
| bad input | 16 cases (short, long, non-hex, empty, traversal, `..`, galaxy 1, wrong prefix, system 000, beyond the region top, bad `wait`, unknown routes, `/`, a static file path, a scanner route, extra path on health) all as expected; POST and PUT 405; GET with a body 400 |
| logs | no IPs, no addresses (checked for the test client keys and all test addresses) |
| client (`node ondemand/tests/client_test.js`) | request + polling, map built through `compact.js` + `model.js` (rooms/crates/footlockers equal the summary on 2 systems), offline text, unknown system, bad address, and the `wireOnDemand` flow with stubbed DOM: all pass |
| regression suite `tools/regression_test_705.py` (fast) | **27 passed, 0 failed, 1 skipped** (the skip is the `--full` Unicorn comparison) |

Not tested: the page in a real browser (no browser is installed here; JS syntax checked with `node --check`, flow tested with stubs),
and no tunnel (nothing was exposed).

### Time per uncached map (1 worker, one request at a time; writer cache OFF = the true miss cost)

| Set | n | mean | median | worst |
|---|---|---|---|---|
| 20 non-top systems, run 1 (included a MEDI_TURRETS at 24.7 s) | 20 | 3.07 s | 1.02 s | 24.74 s |
| 20 non-top systems, run 2 (different sample after I widened the exclusion to all 194) | 20 | 2.61 s | 1.75 s | 8.30 s |
| 5 slowest TURRETS systems in the scanner DB, run 1 / run 2 | 5 | 31.8 / 28.1 s | 7.3 / 6.6 s | **73.5 / 65.6 s** |
| 5 slowest non-TURRETS, run 1 / run 2 | 5 | 1.32 / 1.36 s | 1.01 / 1.06 s | 2.75 / 2.56 s |

Worker start-up (first request after a cold start): 4.8-7.2 s here (12 s the first time ever). With the shared writer cache on, the
same TURRETS systems took 6-7 s for three of them (cache hit from my earlier run) and 60.6 / 61.4 s for the two that were
misses; typical systems are about 1 s. A slow MEDI_TURRETS system therefore takes over a minute on a miss, less than the 90 s
wait cap but close; with the scanner busy or a long queue of such systems the later ones get "busy, try later".

## Exposure

See `ondemand/EXPOSE.md`. **Recommended: (a) Tailscale Funnel first** (free, already installed, v1.104.2, currently no serve or
funnel config), after renaming the machine to a neutral name (`tailscale set --hostname=nms-atlas`; the tailnet part `TAILNET`
cannot be typed freely, only re-rolled from Tailscale's generated list, which I did not test because it changes the account).
Move to (b) a Cloudflare named tunnel (about $10/year domain) if traffic grows: edge caching of `/api/map/*` with one free Cache Rule,
DDoS shield, stable URL independent of the PC. (c) quick tunnels change URL at every start: testing only.
Facts about Funnel/Cloudflare limits and the `X-Forwarded-For` header come from the vendors' documentation as I know it and were not
verified live (no tunnel was started). `clients_1min` on `/api/health` lets you check the header after going live.

## What the user does to go live

1. Double-click `ondemand\Run-OnDemand-Server.cmd`; check `http://127.0.0.1:8791/api/health`.
2. Funnel: `tailscale set --hostname=nms-atlas`, then `tailscale funnel --bg 8791` (first time it prints a link to enable Funnel/HTTPS
   in the tailnet admin console). Check `https://nms-atlas.<tailnet>.ts.net/api/health` from a phone on mobile data. Off: `tailscale funnel reset`.
3. Put that URL into `viewer/static/config.js` as `"ondemandBase"`, run `python -I tools/build_public_site.py D:/Orca/NMS-Derelict-Atlas`,
   and publish the atlas repo (a commit under `atlas.repo_lock`; I did not do this).
4. The PC and the server window must be on for the button to work; otherwise visitors see "Map server offline, try later."
