"use strict";
// node shard_compare.js <viewer/static dir> <atlas dir> <cache-export.json>
// cache-export.json = {address: server-response-body}. For each address: the map drawn from the direct server response and
// from views/ondemand/<REGION>.json.gz (compact.js expand -> model.js unpack -> build) must be deeply equal.
const fs = require("fs"), zlib = require("zlib"), path = require("path"), assert = require("assert");
const st = process.argv[2], atlas = process.argv[3];
const C = require(path.join(st, "compact.js")), M = require(path.join(st, "model.js"));
const props = JSON.parse(fs.readFileSync(path.join(st, "piece_props.json"), "utf8")).scenes;
const bodies = JSON.parse(fs.readFileSync(process.argv[4], "utf8"));
const draw = (view, t) => { const u = M.unpack(C.expand(view, t), C.table3(t)); return M.build(u.d, u.index, props); };
const norm = (m) => JSON.parse(JSON.stringify(m));
let n = 0, bad = [];
for (const [a, body] of Object.entries(bodies)) {
  const f = path.join(atlas, "views", "ondemand", a.slice(8) + ".json.gz");
  const shard = JSON.parse(zlib.gunzipSync(fs.readFileSync(f)).toString("utf8"));
  try {
    assert.deepStrictEqual(norm(draw(shard.s[a], shard.t)), norm(draw(body.s[a], body.t)));
    assert.deepStrictEqual(shard.m[a], body.m);
    n++;
  } catch (e) { bad.push(a + ": " + String(e.message).split("\n")[0]); }
}
console.log(bad.length ? "MISMATCH " + JSON.stringify(bad) : `identical render and summary for ${n} maps`);
process.exit(bad.length ? 1 : 0);
