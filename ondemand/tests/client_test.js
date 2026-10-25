"use strict";
// Node test of viewer/static/ondemand.js against a running server (default http://127.0.0.1:8791):
//   node ondemand/tests/client_test.js <base> <address-with-no-map> [offline-base]
// 1. request() polls through queued/generating and resolves; 2. the body goes through compact.js expand + model.js
// unpack + build (the renderer path) and the container counts equal the summary; 3. the offline message.
const path = require("path");
const static_ = path.resolve(__dirname, "../../viewer/static");
globalThis.DerelictCompact = require(path.join(static_, "compact.js"));
globalThis.DerelictModel = require(path.join(static_, "model.js"));
const base = process.argv[2] || "http://127.0.0.1:8791";
const address = process.argv[3];
globalThis.DV_CONFIG = { ondemandBase: base + "/" };
const OnDemand = require(path.join(static_, "ondemand.js"));
const fs = require("fs");

(async () => {
  let fails = 0;
  const check = (name, ok, note) => { console.log((ok ? "PASS  " : "FAIL  ") + name + (note ? "  -- " + note : "")); if (!ok) fails++; };
  check("available() with a configured base", OnDemand.available());
  const seen = [];
  const t0 = Date.now();
  const body = await OnDemand.request(address, { onStatus: (s) => seen.push(s.state + ":" + s.position) });
  check("request resolves with a v4 one-system bundle", body.v === 4 && !!body.s[address], `${((Date.now() - t0) / 1000).toFixed(1)} s, statuses ${seen.join(" ")}`);
  const u = OnDemand.unpack(address, body);
  const props = JSON.parse(fs.readFileSync(path.join(static_, "piece_props.json"), "utf8")).scenes;
  const m = DerelictModel.build(u.d, u.index, props);
  const crates = m.containers.filter((c) => c.container_kind === "salvage_crate").length;
  const lockers = m.containers.length - crates;
  check("renderer path builds the map; container counts equal the summary",
    crates === body.m.crates && lockers === body.m.footlockers && m.rooms.length === body.m.rooms,
    `rooms ${m.rooms.length}/${body.m.rooms}, crates ${crates}/${body.m.crates}, footlockers ${lockers}/${body.m.footlockers}`);
  check("second request is served from memory", OnDemand.cached(address) === body);
  globalThis.DV_CONFIG = { ondemandBase: "http://127.0.0.1:9" };      // nothing listens there
  let err = null;
  try { await OnDemand.request("0000010007607CAA", {}); } catch (e) { err = e; }
  check("unreachable server -> code offline, message 'Map server offline, try later.'", err && err.code === "offline" && OnDemand.message(err) === "Map server offline, try later.", err && err.code);
  globalThis.DV_CONFIG = { ondemandBase: base };
  err = null;
  try { await OnDemand.request("000FFF0004E84EFD", {}); } catch (e) { err = e; }
  check("unknown system -> code nosystem", err && err.code === "nosystem", err && err.code);
  err = null;
  try { await OnDemand.request("XYZ", {}); } catch (e) { err = e; }
  check("bad address rejected locally", err && err.code === "bad");
  // the button wiring in viewer/static/app.js (wireOnDemand), run against stubs for the DOM and derelictView
  const vm = require("vm");
  const src = fs.readFileSync(path.join(static_, "app.js"), "utf8").replace(/\r\n/g, "\n");
  const m1 = src.match(/function wireOnDemand\([\s\S]*?\n}\n/);
  check("app.js contains wireOnDemand", !!m1);
  if (m1 && process.argv[4]) {
    const addr2 = process.argv[4];
    const texts = [], redraws = [];
    const btn = { disabled: false, textContent: "Generate map", onclick: null };
    const status = { textContent: "" };
    const ctx = { OnDemand, AbortController, window: { addEventListener() {} }, location: { hash: "#/d/" + addr2 },
      derelictView: async (a) => { redraws.push(a); }, console };
    vm.createContext(ctx);
    vm.runInContext(m1[0], ctx);
    ctx.wireOnDemand(addr2, btn, new Proxy(status, { set(o, k, v) { if (k === "textContent") texts.push(v); o[k] = v; return true; } }));
    await btn.onclick();
    check("button flow: progress texts, then the page is redrawn", redraws.length === 1 && redraws[0] === addr2 && texts.length >= 2 && /drawing/.test(texts[texts.length - 1]), JSON.stringify(texts));
    globalThis.DV_CONFIG = { ondemandBase: "http://127.0.0.1:9" };
    const btn2 = { disabled: false, textContent: "Generate map", onclick: null };
    const texts2 = [];
    ctx.wireOnDemand("0000010007607CAB", btn2, new Proxy({}, { set(o, k, v) { texts2.push(v); return true; } }));
    await btn2.onclick();
    check("button flow: offline server shows 'Map server offline, try later.' and re-enables the button", texts2[texts2.length - 1] === "Map server offline, try later." && btn2.disabled === false && btn2.textContent === "Try again", JSON.stringify(texts2));
  }
  console.log(fails ? "FAILS: " + fails : "all passed");
  process.exit(fails ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
