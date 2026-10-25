"use strict";
// EXPERIMENTAL format 4 check (tools/derelict_view_compact.py --check runs it):
//   node tools/check_compact_view.js [viewer/static/compact]
// For top100 and local: viewer/static/compact.js expand() of every format-4 view must give the format-3 view exactly
// (JSON text), column by column for "c" (crates/footlockers), "i" (pieces), "x" (extras), and model.js unpack() of both
// must give the same derelict (rooms, pieces, containers with orientation, extras). Exit code 1 on any difference.
const fs = require("fs"), path = require("path"), zlib = require("zlib");
const M = require(path.join(__dirname, "..", "viewer", "static", "model.js"));
const C = require(path.join(__dirname, "..", "viewer", "static", "compact.js"));
const dir = process.argv[2] || path.join(__dirname, "..", "viewer", "static", "compact");
const read = (f) => JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(dir, f))).toString("utf8"));
let fail = 0;
for (const name of ["top100", "local"]) {
  const b3 = read(`${name}.v3.json.gz`), b4 = read(`${name}.v4.json.gz`);
  const t3 = C.table3(b4.t);
  const tableSame = JSON.stringify(t3) === JSON.stringify(b3.t);
  const n = { all: 0, view: 0, c: 0, i: 0, x: 0, unpack: 0 }, bad = [];
  for (const [a, v3] of Object.entries(b3.s)) {
    n.all++;
    let w;
    try { w = C.expand(b4.s[a], b4.t); } catch (err) { bad.push(`${a}: ${err.message}`); continue; }
    const same = (k) => JSON.stringify(w[k]) === JSON.stringify(v3[k]);
    n.c += same("c"); n.i += same("i"); n.x += same("x");
    const view = JSON.stringify(w) === JSON.stringify(v3);
    n.view += view;
    const u3 = M.unpack(v3, b3.t).d, u4 = M.unpack(w, t3).d;
    const up = JSON.stringify(u3) === JSON.stringify(u4);
    n.unpack += up;
    if (!view || !up) bad.push(`${a}: ${["c", "i", "x"].filter((k) => !same(k)).join(",") || "other"} differ`);
  }
  console.log(`${name}: Node expand ${n.view}/${n.all} views identical (c ${n.c}, i ${n.i}, x ${n.x}); model.js unpack identical ${n.unpack}/${n.all}; piece table ${tableSame ? "identical" : "DIFFERENT"}` +
    (bad.length ? `\n  mismatches: ${bad.slice(0, 20).join("; ")}` : ""));
  if (bad.length || !tableSame || n.view !== n.all) fail = 1;
}
process.exit(fail);
