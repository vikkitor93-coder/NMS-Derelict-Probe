"use strict";
// Client checks that do NOT need the real compact renderer (the stub's view is not a renderable v4 view):
//   node ondemand/tests/client_stub_test.js <base> <address-with-no-map> <viewer/static dir>
// request() through status polls to a cached map, OnDemand.view() 95% cap / "taking longer", offline, unknown system, bad address.
const path = require("path");
const base = process.argv[2], address = process.argv[3], st = path.resolve(process.argv[4]);
globalThis.DV_CONFIG = { ondemandBase: base };
const OnDemand = require(path.join(st, "ondemand.js"));
(async () => {
  let fails = 0;
  const check = (n, ok, note) => { console.log((ok ? "PASS  " : "FAIL  ") + n + (note ? "  -- " + note : "")); if (!ok) fails++; };
  const seen = [];
  const body = await OnDemand.request(address, { onStatus: (s) => seen.push(s.state + ":" + s.position + ":" + s.stage) });
  check("request(): status polls then a v4 bundle", body.v === 4 && !!body.s[address] && seen.some((x) => x.startsWith("generating") || x.startsWith("queued")) && seen[seen.length - 1].startsWith("ready"), seen.join(" "));
  check("second request served from memory", OnDemand.cached(address) === body);
  const v = (st_, el) => OnDemand.view({ st: { ...st_, t_recv: 1 }, t0: 1, pct: 0 }, el);
  const long = { status: "generating", eta_s: 10, stage: 2, msg: { title: "T", stages: ["a", "b", "c", "d", "e"], over: "taking longer than usual… still working (elapsed {s} s)", left: "about {s} s left" } };
  check("view(): never above 95% before ready", v(long, 5000).pct < 95 && v(long, 500000).pct === 95);
  check("view(): after the ETA 'taking longer than usual' with elapsed", /taking longer than usual.*85 s/.test(v(long, 85000).time), v(long, 85000).time);
  check("view(): ready = 100%", v({ ...long, status: "ready", msg: { ready: "Map ready" } }, 1000).pct === 100);
  globalThis.DV_CONFIG = { ondemandBase: "http://127.0.0.1:9" };
  let err = null;
  try { await OnDemand.request("0000010007607CAA", {}); } catch (e) { err = e; }
  check("unreachable server -> offline text", err && err.code === "offline" && OnDemand.message(err) === "Map server offline, try later.");
  globalThis.DV_CONFIG = { ondemandBase: base };
  err = null; try { await OnDemand.request("0001F00007607CAA", {}); } catch (e) { err = e; }
  check("unknown system -> nosystem", err && err.code === "nosystem", err && err.code);
  err = null; try { await OnDemand.request("XYZ", {}); } catch (e) { err = e; }
  check("bad address rejected locally", err && err.code === "bad");
  console.log(fails ? "FAILS: " + fails : "all passed");
  process.exit(fails ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
