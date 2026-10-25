"use strict";
// Pre-builds derelict viewer views (viewer/static/model.js pack) for publishing next to the atlas.
//
//   node tools/build_views.js --out <dir> [--generated <dir>] [--index <meshcache/index.json>] [--check] [ADDRESS16 ...]
//
// Without addresses it builds every generated derelict found. Writes <out>/views/pieces.json (shared piece table;
// existing scene ids are kept and new scenes appended, so published views stay valid) and
// <out>/views/g<GG>/<YY>/<ZZZ>/<REGION>/<glyphs>.json (the atlas's locations/ layout). Prints raw and gzip sizes
// (GitHub serves raw files gzip-compressed).
// --check: also draws each derelict from the original derelict.json + index and from the published view, and compares
// rooms, containers, doors, stair links, wall pixels and fixtures.
const fs = require("fs");
const path = require("path");
const zlib = require("zlib");
const M = require("../viewer/static/model.js");

const args = process.argv.slice(2);
const opt = (name, dflt) => { const i = args.indexOf(name); if (i < 0) return dflt; const v = args[i + 1]; args.splice(i, 2); return v; };
const flag = (name) => { const i = args.indexOf(name); if (i < 0) return false; args.splice(i, 1); return true; };
const out = opt("--out", null);
const generated = opt("--generated", "D:/Orca/NMS-Derelict-Probe-analysis/emu/fastgen/generated");
const indexPath = opt("--index", "D:/Orca/NMS-Derelict-Probe-analysis/meshcache/index.json");
const check = flag("--check");
if (!out) { console.error("usage: node tools/build_views.js --out <dir> [--check] [ADDRESS16 ...]"); process.exit(2); }

const index = JSON.parse(fs.readFileSync(indexPath, "utf8"));
const tablePath = path.join(out, "views", "pieces.json");
const names = fs.existsSync(tablePath) ? JSON.parse(fs.readFileSync(tablePath, "utf8")).n : [];
for (const n of Object.keys(index).sort()) if (n !== "_meta" && !names.includes(n)) names.push(n);
const table = M.piecesTable(index, names);
const ids = new Map(names.map((n, k) => [n, k]));
const sceneId = (n) => { if (!ids.has(n)) throw new Error(`scene ${n} is not in the piece index`); return ids.get(n); };
fs.mkdirSync(path.dirname(tablePath), { recursive: true });
const tableText = JSON.stringify(table);
fs.writeFileSync(tablePath, tableText);

const addresses = args.length ? args.map((a) => a.toUpperCase())
  : fs.readdirSync(generated).filter((n) => /^[0-9A-F]{16}$/.test(n) && fs.existsSync(path.join(generated, n, "derelict.json")));

// wall pixels of one drawn model, as a set of "level,room,x,z" (rects back to the 1/32 raster)
function wallPixels(m) {
  const s = new Set();
  for (const w of m.walls) {
    for (let z = Math.round(w.v0 * 32); z < Math.round(w.v1 * 32); z++)
      for (let x = Math.round(w.u0 * 32); x < Math.round(w.u1 * 32); x++) s.add(`${w.level},${w.room},${x},${z}`);
  }
  return s;
}
const stats = { n: 0, raw: 0, gz: 0, worst: { size: 0 }, checked: 0, wallPxDiff: 0, wallPx: 0, fixtureMax: 0, containerMax: 0, mismatches: [] };
const t0 = Date.now();
for (const a of addresses) {
  const d = JSON.parse(fs.readFileSync(path.join(generated, a, "derelict.json"), "utf8"));
  if (!d.instances) continue;
  const view = M.pack(d, sceneId);
  const text = JSON.stringify(view);
  const glyphs = "0" + a.slice(3, 6) + a.slice(8), region = a.slice(8);
  const file = path.join(out, "views", `g${a.slice(6, 8).toLowerCase()}`, region.slice(0, 2), region.slice(2, 5), region, `${glyphs}.json`);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, text);
  const g = zlib.gzipSync(text, { level: 9 }).length;
  stats.raw += text.length; stats.gz += g; stats.n++;
  if (g > stats.worst.size) stats.worst = { size: g, a };
  if (!check) continue;
  // original drawing vs published drawing
  const A = M.build(d, index);
  const u = M.unpack(JSON.parse(text), JSON.parse(tableText));
  const B = M.build(u.d, u.index);
  const bad = [];
  const same = (what, x, y) => { if (JSON.stringify(x) !== JSON.stringify(y)) bad.push(what); };
  same("rooms", A.rooms.map((r) => [r.template_name, r.instance_count, r.crates, r.lockers, r.hangarPieces, [...r.cellSet]]),
    B.rooms.map((r) => [r.template_name, r.instance_count, r.crates, r.lockers, r.hangarPieces, [...r.cellSet]]));
  same("doors", A.doors.map((x) => [x.level, x.a, x.b, x.kind, x.slime, x.rooms]), B.doors.map((x) => [x.level, x.a, x.b, x.kind, x.slime, x.rooms]));
  same("links", A.links.map((l) => [l.room, l.upper, l.lower, l.cells, l.mark]), B.links.map((l) => [l.room, l.upper, l.lower, l.cells, l.mark]));
  same("containers", A.containers.map((c) => [c.container_kind, c.room_index, c.g.level]), B.containers.map((c) => [c.container_kind, c.room_index, c.g.level]));
  A.containers.forEach((c, k) => { for (let j = 0; j < 3; j++) stats.containerMax = Math.max(stats.containerMax, Math.abs(c.layout_local_xyz[j] - B.containers[k].layout_local_xyz[j])); });
  same("fixture count", A.fixtures.length, B.fixtures.length);
  A.fixtures.forEach((f, k) => { for (const key of ["u0", "u1", "v0", "v1", "h0", "h1"]) stats.fixtureMax = Math.max(stats.fixtureMax, Math.abs(f[key] - B.fixtures[k][key])); });
  const pa = wallPixels(A), pb = wallPixels(B);
  let diff = 0;
  for (const p of pa) if (!pb.has(p)) diff++;
  for (const p of pb) if (!pa.has(p)) diff++;
  stats.wallPxDiff += diff; stats.wallPx += pa.size; stats.checked++;
  if (bad.length) stats.mismatches.push(`${a}: ${bad.join(", ")}`);
}
const kb = (b) => (b / 1024).toFixed(1) + " KB";
const tgz = zlib.gzipSync(tableText, { level: 9 }).length;
console.log(`piece table: ${names.length} scenes, raw ${kb(tableText.length)}, gzip ${kb(tgz)} (loaded once per visit)`);
console.log(`${stats.n} views in ${((Date.now() - t0) / 1000).toFixed(1)} s · raw ${kb(stats.raw)} (avg ${kb(stats.raw / stats.n)}) · gzip ${kb(stats.gz)} (avg ${kb(stats.gz / stats.n)}) · largest gzip ${kb(stats.worst.size)} ${stats.worst.a}`);
if (check) {
  console.log(`check: ${stats.checked} derelicts · wall pixels differing ${stats.wallPxDiff} of ${stats.wallPx} · fixture max diff ${stats.fixtureMax.toFixed(4)} cells · container max diff ${stats.containerMax.toFixed(4)} m · mismatches ${stats.mismatches.length}`);
  for (const m of stats.mismatches.slice(0, 20)) console.log("  " + m);
}
