"use strict";
// On-demand map client for the public site (written 2026-10-24, NOT yet wired into viewer/static: that waits for the
// other agents' DONE entries in D:/Orca/NMS-COORDINATION.md). Browser global `OnDemand`, also usable from Node (tests).
//
//   OnDemand.available()                         true when DV_CONFIG.ondemandBase is set (one config value, see EXPOSE.md)
//   OnDemand.request(address, { onStatus, signal })
//        asks GET <base>/api/map/<ADDRESS16> and polls while the server queues/generates; resolves to the response body
//        {v:4, t, s:{ADDRESS16: view}, m:{summary}} or rejects with an Error whose .code is one of
//        "offline" (server unreachable / timeout / not JSON: show "Map server offline, try later"), "busy", "rate",
//        "nosystem", "unsupported", "bad", "aborted", and .retryAfter (seconds) when the server gave one.
//        onStatus({state: "connecting"|"queued"|"generating", position, queue, eta_s, elapsed_s}) is called for every poll.
//   OnDemand.cached(address)                     body of an earlier request in this page visit, or null
//   OnDemand.unpack(address, body)               -> { d, index } like DerelictModel.unpack(view3, table3); needs compact.js + model.js
//   OnDemand.message(err)                        the text to show for a rejected request
(function (root) {
  const POLL_WAIT_S = 3;            // long-poll length: the server answers sooner when the map is ready
  const TOTAL_LIMIT_MS = 180000;    // give up (as "busy") after this
  const mem = new Map();

  const base = () => String((root.DV_CONFIG && root.DV_CONFIG.ondemandBase) || "").replace(/\/+$/, "");
  const available = () => !!base();

  function fail(code, message, retryAfter) {
    const e = new Error(message);
    e.code = code;
    if (retryAfter) e.retryAfter = retryAfter;
    return e;
  }

  const MESSAGES = {
    offline: "Map server offline, try later.",
    busy: "The map server is busy, try again in a minute.",
    rate: "Too many map requests from this connection, wait a minute.",
    nosystem: "This system could not be found, so no map can be made.",
    unsupported: "Only galaxy 0 (Euclid) maps can be generated for now.",
    bad: "That address is not valid.",
    aborted: "Cancelled.",
  };
  const message = (err) => (err && MESSAGES[err.code]) || "Map server offline, try later.";

  async function request(address, opts) {
    const o = opts || {};
    const addr = String(address).toUpperCase();
    if (!available()) throw fail("offline", MESSAGES.offline);
    if (!/^[0-9A-F]{16}$/.test(addr)) throw fail("bad", MESSAGES.bad);
    if (mem.has(addr)) return mem.get(addr);
    const t0 = Date.now();
    const status = (s) => { if (o.onStatus) { try { o.onStatus({ elapsed_s: Math.round((Date.now() - t0) / 1000), ...s }); } catch (_) { /* UI errors never stop the request */ } } };
    status({ state: "connecting", position: 0, queue: 0, eta_s: null });
    for (;;) {
      if (o.signal && o.signal.aborted) throw fail("aborted", MESSAGES.aborted);
      if (Date.now() - t0 > TOTAL_LIMIT_MS) throw fail("busy", MESSAGES.busy, 60);
      let r, body;
      try {
        r = await fetch(`${base()}/api/map/${addr}?wait=${POLL_WAIT_S}`, { signal: o.signal, cache: "no-store" });
        body = await r.json();
      } catch (err) {
        if (err && err.name === "AbortError") throw fail("aborted", MESSAGES.aborted);
        throw fail("offline", MESSAGES.offline);     // network error, tunnel down, HTML error page from a proxy
      }
      if (r.status === 200) {
        if (!body || body.v !== 4 || !body.s || !body.s[addr]) throw fail("offline", MESSAGES.offline);
        mem.set(addr, body);
        return body;
      }
      if (r.status === 202) {
        status({ state: body.status || "queued", position: body.position || 0, queue: body.queue || 0, eta_s: body.eta_s ?? null });
        continue;
      }
      const retry = Number(r.headers.get("Retry-After")) || (body && body.retry_after) || 0;
      if (r.status === 429) throw fail("rate", MESSAGES.rate, retry);
      if (r.status === 503) throw fail("busy", MESSAGES.busy, retry);
      if (r.status === 404) throw fail("nosystem", MESSAGES.nosystem);
      if (r.status === 400) throw fail(body && body.error === "galaxy" ? "unsupported" : "bad", body && body.error === "galaxy" ? MESSAGES.unsupported : MESSAGES.bad);
      throw fail("offline", MESSAGES.offline);
    }
  }

  const cached = (address) => mem.get(String(address).toUpperCase()) || null;

  // the response is a one-system bundle in the compact format 4: the existing renderer path (compact.js expand, then
  // model.js unpack/build) draws it exactly like a top-100 map from viewer/static/compact/top100.v4.json.gz
  function unpack(address, body) {
    const C = root.DerelictCompact || (typeof require !== "undefined" ? require("./compact.js") : null);
    const M = root.DerelictModel || (typeof require !== "undefined" ? require("./model.js") : null);
    return M.unpack(C.expand(body.s[address], body.t), C.table3(body.t));
  }

  const api = { available, request, cached, unpack, message };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.OnDemand = api;
})(typeof window !== "undefined" ? window : globalThis);
