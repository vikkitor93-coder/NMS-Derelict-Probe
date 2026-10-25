"use strict";
// Derelict Viewer front end. Two views: "#/" (region sweep table) and "#/d/<ADDRESS16>" (one derelict).

const app = document.getElementById("app");
const tip = document.getElementById("tip");
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const SITE = window.DV_CONFIG || {};   // config.js: siteBase, staticSite (no local server), gate

function store(key, value) {
  try {
    if (value === undefined) return JSON.parse(localStorage.getItem("dv." + key) || "null");
    localStorage.setItem("dv." + key, JSON.stringify(value));
  } catch { return null; }
}

async function api(path, opts) {
  const res = await fetch(path, opts);
  let body = null;
  try { body = await res.json(); } catch { /* empty */ }
  if (!res.ok) throw Object.assign(new Error((body && body.error) || res.statusText), { status: res.status, body });
  return body;
}

// "Done" list: derelicts already visited. The local server keeps it (viewer-done.json, shared by PC and phone); without a
// server (static atlas build) or if it fails, it lives in this browser (dv.done). Value = ISO time.
let DONE = {};
const isDone = (a) => Object.prototype.hasOwnProperty.call(DONE, a);
async function setDone(address, done) {
  if (done) DONE[address] = new Date().toISOString(); else delete DONE[address];
  store("done", DONE);
  if (!HAS_SERVER) return true;
  try { DONE = await api("/api/done", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ address, done }) }); store("done", DONE); return true; }
  catch { return false; }  // kept in this browser only
}
function doneBoxHtml(address) {
  return `<label class="done-box" title="Mark this derelict as done so you do not visit it again. Shown on the main page too."><input id="done-box" type="checkbox"${isDone(address) ? " checked" : ""}> Done</label><span id="done-note" class="muted"></span>`;
}
function wireDone(address) {
  const box = document.getElementById("done-box"), note = document.getElementById("done-note");
  if (!box) return;
  box.onchange = async () => {
    const ok = await setDone(address, box.checked);
    box.checked = isDone(address);
    note.textContent = ok ? "" : "saved in this browser only (server not reachable)";
  };
}

// address 000 SSS GG YY ZZZ XXX  ->  portal glyph hex P SSS YY ZZZ XXX (planet 0)
const glyphsOf = (a) => "0" + a.slice(3, 6) + a.slice(8);
const glyphsPretty = (a) => { const g = glyphsOf(a); return `${g[0]} ${g.slice(1, 4)} ${g.slice(4, 6)} ${g.slice(6, 9)} ${g.slice(9)}`; };
// Portal glyph icons or hex digits (header switch). With the local server: the game's own icons (glyphs/<0-f>.png, from
// tools/build_glyph_icons_705.py, never published); elsewhere (public site): hand-drawn lookalikes (glyphs-svg/<0-f>.svg).
// Stored modes: "icons" (official when there is a server, else public), "public" (lookalikes; local preview of the public
// site) and "hex".
let HAS_SERVER = false;
const serverReady = (SITE.staticSite ? Promise.resolve() : fetch("/api/regions").then((r) => { HAS_SERVER = r.ok; }).catch(() => { /* static hosting */ }));
const doneReady = serverReady.then(async () => {
  const local = store("done");
  DONE = local && typeof local === "object" ? local : {};
  if (!HAS_SERVER) return;
  try { DONE = { ...DONE, ...(await api("/api/done")) }; } catch { /* keep the browser copy */ }
});
const GLYPH_NAMES = ["Sunset", "Bird", "Face", "Diplo", "Eclipse", "Balloon", "Boat", "Bug", "Dragonfly", "Galaxy", "Voxel", "Fish",
  "Tent", "Rocket", "Tree", "Atlas"];
const glyphMode = () => store("glyphMode") || "icons";
function glyphHtml(a, big = false) {
  const mode = glyphMode();
  if (mode === "hex") return `<span class="mono${big ? " glyph" : ""}">${esc(glyphsPretty(a))}</span>`;
  return `<span class="glyph-icons${big ? " big" : ""}">${[...glyphsOf(a)].map((c) =>
    `<img src="${HAS_SERVER && mode !== "public" ? `glyphs/${c.toLowerCase()}.png` : `glyphs-svg/${c.toLowerCase()}.svg`}" alt="${c}" title="${GLYPH_NAMES[parseInt(c, 16)]} (${c})">`).join("")}</span>`;
}

// Room template -> readable type and colour.
function roomInfo(t) {
  const fam = t === "R_END" ? "end" : t.includes("HANG") ? "hangar" : t.includes("CARG") ? "cargo"
    : t.includes("BARR") ? "barracks" : t.includes("MED") ? "medical" : "other";
  const famName = { end: "End room", hangar: "Hangar", cargo: "Cargo", barracks: "Barracks", medical: "Medical", other: t }[fam];
  const size = t.startsWith("B_") ? "branch" : t.startsWith("R_S_") ? "small" : "";
  const theme = t.includes("BUG") ? "Bugs" : t.includes("FLO") ? "Floaters" : t.includes("SLI") ? "Slime" : "";
  const label = [famName, size].filter(Boolean).join(" ") + (theme ? ` · ${theme}` : "");
  return { fam, label, color: `var(--${fam})` };
}

function showTip(ev, html) {
  tip.innerHTML = html;
  tip.hidden = false;
  const x = Math.min(ev.clientX + 14, window.innerWidth - tip.offsetWidth - 8);
  const y = Math.min(ev.clientY + 14, window.innerHeight - tip.offsetHeight - 8);
  tip.style.left = x + "px";
  tip.style.top = y + "px";
}
const hideTip = () => { tip.hidden = true; };

// ---------------------------------------------------------------- region sweep view

// Predicted end reward (index/systems.csv.gz columns reward_name, reward_class C/B/A/S, reward_ambiguous 1/0, reward_alt "name class|name class").
// Empty = not computed yet: shown as "–" and sorted last. Absent columns are fine too.
const REWARD_RANK = { C: 1, B: 2, A: 3, S: 4 };
const REWARD_CLASSES = ["C", "B", "A", "S"];
const parseRewardAlt = (txt) => String(txt || "").split("|").map((x) => x.trim()).filter(Boolean).map((x) => {
  const i = x.lastIndexOf(" ");
  return i < 0 ? { name: x, cls: "" } : { name: x.slice(0, i), cls: x.slice(i + 1).toUpperCase() };
});
// all the rewards a system might give: the predicted one first, then the alternatives of an ambiguous prediction
const rewardOptions = (r) => (r.reward_name ? [{ name: r.reward_name, cls: r.reward_class || "" }, ...(r.reward_ambiguous ? parseRewardAlt(r.reward_alt) : [])] : []);
const rewardBadge = (cls) => (cls ? `<span class="rw rw-${esc(cls)}" title="Reward class ${esc(cls)}">${esc(cls)}</span>` : "");
function rewardHtml(r) {
  if (!r.reward_name) return `<span class="muted" title="not computed yet">–</span>`;
  const alts = r.reward_ambiguous ? parseRewardAlt(r.reward_alt) : [];
  const tip = r.reward_ambiguous ? `Ambiguous prediction${alts.length ? ": could also be " + alts.map((a) => `${a.name} ${a.cls}`.trim()).join(", ") : ""}` : "";
  return `<span${tip ? ` title="${esc(tip)}"` : ""}>${r.reward_ambiguous ? "≈ " : ""}${esc(r.reward_name)} ${rewardBadge(r.reward_class)}</span>`;
}

// Which top lists a system with a full map is in: map 1 = top 100 by crates + footlockers, 2 = top 100 by frigate modules, 3 = both.
const MAP_LIST_NAMES = { 1: "Top 100 by crates", 2: "Top 100 by frigate modules", 3: "Top 100 by crates and by frigate modules" };
function mapChips(m) {
  const tip = (t) => `${t}: full map and 3D view`;
  return `${m & 1 ? ` <span class="chip map" title="${tip("Top 100 by crates + footlockers")}">Top crates</span>` : ""}${m & 2 ? ` <span class="chip map mod" title="${tip("Top 100 by predicted frigate modules")}">Top modules</span>` : ""}`;
}

// Region table columns. To add one, add an entry: key (also the row field it sorts by, unless `sort` names another), label,
// num (right-aligned), cls (extra cell class) and cell(row) -> inner HTML of its <td>. New keys show up at the end of a
// saved layout and are listed in the Columns panel; add them to DEFAULT_COLUMN_LAYOUT.order to place them in the default.
const COLUMNS = [
  { key: "glyphs", label: "Glyph code", cell: (r) => `${glyphHtml(r.address)}${mapChips(r.map)}${r.existence === "purple" ? ` <span class="chip purple">purple</span>` : ""}` },
  { key: "system_name", label: "System name", title: "Computed from the address (port of nms_namegen); a 20-system sample matched NMS Almanac. Players can rename systems.", cell: (r) => esc(r.system_name || "") },
  { key: "region", label: "Region", cls: "mono muted", cell: (r) => esc(r.region) },
  { key: "preset", label: "Preset", cell: (r) => `<span class="chip ${esc(r.preset.split("_")[0])}">${esc(r.preset)}</span>` },
  { key: "rooms", label: "Rooms", num: true, cell: (r) => r.rooms },
  { key: "floors", label: "Floors", num: true, cell: (r) => r.floors ?? "" },
  { key: "stair_pieces", label: "Stairs", num: true, cell: (r) => r.stair_pieces ?? "" },
  { key: "hangar", label: "Hangar", cell: (r) => (r.hangar ? "yes" : "") },
  { key: "salvage_crates", label: "Crates", num: true, cell: (r) => r.salvage_crates },
  { key: "footlockers", label: "Footlockers", num: true, cell: (r) => r.footlockers },
  { key: "total", label: "Total", num: true, title: () => `Total of: ${totalNames(totalGroups())}. Change it with "Total counts" above the table. The top-100 map ranking is always salvage crates + footlockers. "N+" = at least N: a ticked group is not known yet for that system.`,
    cell: (r) => `<b${r.totalTip ? ` title="${esc(r.totalTip)}"` : ""}>${r.totalText}</b>` },
  // extra loot containers: only part of Total when ticked under "Total counts"; not part of the top-100 ranking; blank in the atlas = not known yet (never 0)
  { key: "briefcases", label: "Briefcases", num: true, title: "Briefcases (R_ABAND_CASE: units, nanites, salvage; no frigate module). Part of Total only when ticked under Total counts.", cell: (r) => unknownDash(r.briefcases) },
  { key: "reward", label: "Reward", title: "Predicted end reward of the system's own derelict (name and class). Sorts by class S > A > B > C; unknown last. ≈ = ambiguous prediction, hover for the alternatives.", cell: (r) => rewardHtml(r) },
  { key: "tall_lockers", label: "Tall lockers", num: true, title: "Tall lockers (R_ABAND_LOCK: curios, ammo, tech; no frigate module). Part of Total only when ticked under Total counts.", cell: (r) => unknownDash(r.tall_lockers) },
  { key: "frigate_modules", label: "Frigate modules", num: true, title: "Predicted Salvaged Frigate Modules from salvage crates and crew footlockers. Blank means not computed; ? marks prediction uncertainty.", cell: (r) => r.frigate_modules === null ? unknownDash(null) : `${r.frigate_modules}${r.frigate_modules_ambiguous ? " ?" : ""}` },
];
const unknownDash = (v) => (v === null || v === undefined ? `<span class="muted" title="not known yet">–</span>` : v);

// "Total" counts only the groups ticked under "Total counts:" (saved with the filters, shared by the atlas table and the derelict page).
// The default is "Salvaged Frigate Module Crates" = salvage crates + crew footlockers, the containers that can give the frigate module.
// A ticked group whose count is not known yet for a system (briefcases / tall lockers before the region was rescanned) is never
// counted as 0: the total is shown as a lower bound "61+" and sorts after known totals of the same value.
const TOTAL_GROUPS = [
  { key: "frigate", short: "Frigate Module Crates", label: "Salvaged Frigate Module Crates", title: "Salvage crates + crew footlockers: the containers that can give the frigate module. Always known." },
  { key: "briefcases", short: "Briefcases", label: "Briefcases", title: "Briefcases (R_ABAND_CASE: units, nanites, salvage; no frigate module). Unknown for systems that have not been rescanned for them yet." },
  { key: "tall", short: "Tall lockers", label: "Tall lockers", title: "Tall lockers (R_ABAND_LOCK: curios, ammo, tech; no frigate module). Unknown for systems that have not been rescanned for them yet." },
];
const DEFAULT_TOTAL_GROUPS = { frigate: true, briefcases: false, tall: false };
const totalGroups = () => ({ ...DEFAULT_TOTAL_GROUPS, ...(((store("filters") || {}).totalGroups) || {}) });
const saveTotalGroups = (g) => store("filters", { ...(store("filters") || {}), totalGroups: g });
// c: { salvage_crates, footlockers, briefcases, tall_lockers } (null = unknown) -> { n: sum of the known ticked groups, unknown: [names of ticked groups without a count] }
function totalOf(c, g) {
  let n = 0;
  const unknown = [];
  if (g.frigate) n += (c.salvage_crates || 0) + (c.footlockers || 0);
  if (g.briefcases) { if (c.briefcases === null || c.briefcases === undefined) unknown.push("briefcases"); else n += c.briefcases; }
  if (g.tall) { if (c.tall_lockers === null || c.tall_lockers === undefined) unknown.push("tall lockers"); else n += c.tall_lockers; }
  return { n, unknown };
}
const totalText = (t) => `${t.n}${t.unknown.length ? "+" : ""}`;
const totalNames = (g) => TOTAL_GROUPS.filter((x) => g[x.key]).map((x) => x.short).join(" + ") || "nothing ticked";
const totalTip = (t) => (t.unknown.length ? `At least ${t.n}: the ${t.unknown.join(" and ")} count of this system is not known yet, so it is not included. Shown as ${t.n}+.` : "");
// the "Total counts:" checkboxes (ids <prefix>-tg-<key>)
const totalGroupsHtml = (prefix, g) => `<span class="total-groups" title="Which containers the Total adds up (saved in this browser)"><b>Total counts:</b>${TOTAL_GROUPS.map((x) =>
  `<label title="${esc(x.title)}"><input id="${prefix}-tg-${x.key}" type="checkbox"${g[x.key] ? " checked" : ""}> ${esc(x.label)}</label>`).join("")}</span>`;
function wireTotalGroups(prefix, g, onChange) {
  for (const x of TOTAL_GROUPS) {
    const el = document.getElementById(`${prefix}-tg-${x.key}`);
    if (el) el.onchange = () => { g[x.key] = el.checked; onChange(g); };
  }
}
// The default column layout (what "Reset columns" restores): order = every column key, hidden = keys not shown.
// To lock in a layout the user sent via "Copy column layout", paste their JSON over this value.
const DEFAULT_COLUMN_LAYOUT = {"order":["glyphs","system_name","total","salvage_crates","footlockers","briefcases","tall_lockers","rooms","floors","stair_pieces","hangar","region","preset","reward","frigate_modules"],"hidden":[]};
// Layout version: a browser that still has the OLD default saved (never customised) is reset once to the current default.
const COLUMN_LAYOUT_VERSION = 2;
const OLD_DEFAULT_COLUMNS = '{"order":["glyphs","region","preset","rooms","floors","stair_pieces","hangar","salvage_crates","footlockers","total","briefcases","tall_lockers"],"hidden":[]}';
function migrateColumnLayout() {
  if (store("columnsVer") === COLUMN_LAYOUT_VERSION) return;
  const saved = store("columns");
  if (saved && JSON.stringify({ order: saved.order, hidden: saved.hidden }) === OLD_DEFAULT_COLUMNS) store("columns", null);
  store("columnsVer", COLUMN_LAYOUT_VERSION);
}

// Saved layout merged with the known columns: unknown keys dropped, columns missing from it appended (visible).
function resolveColumnLayout(saved) {
  const keys = COLUMNS.map((c) => c.key);
  const src = saved && Array.isArray(saved.order) ? saved : DEFAULT_COLUMN_LAYOUT;
  const order = [...new Set(src.order)].filter((k) => keys.includes(k));
  for (const k of keys) if (!order.includes(k)) order.push(k);
  let hidden = (Array.isArray(src.hidden) ? src.hidden : []).filter((k) => order.includes(k));
  if (hidden.length >= order.length) hidden = [];  // never hide everything
  return { order, hidden };
}

// The published atlas (github.com/vikkitor93-coder/nms-derelict-atlas) is read by each visitor's browser straight from
// GitHub (raw.githubusercontent.com: CDN-cached, CORS open), so the machine serving this page does no work for it:
//   index/systems.csv.gz                     every published system in one gzip file (tools/build_atlas_index.py)
//   regions/g<GG>/<YY>/<ZZZ>/<REGION>.csv    the verified region files (fallback, and per-room detail)
//   views/top100.json.gz                     full maps of the top 100 systems (tools/build_top_bundle.py, model.js)
const ATLAS = { repo: "vikkitor93-coder/nms-derelict-atlas", branch: "main" };
// static site (config.js staticSite): the data files sit next to the page on the same origin (GitHub Pages of the atlas repo)
const ATLAS_RAW = new URLSearchParams(location.search).get("atlas") || (SITE.staticSite ? new URL("./", location.href).href : `https://raw.githubusercontent.com/${ATLAS.repo}/${ATLAS.branch}/`);
const ATLAS_FILE = /^regions\/g([0-9a-f]{2})\/[0-9A-F]{2}\/[0-9A-F]{3}\/([0-9A-F]{8})\.csv$/i;

// region file listing, only needed while the combined list is not published
async function atlasFiles() {
  try {
    const hit = JSON.parse(sessionStorage.getItem("dv.atlasFiles") || "null");
    if (hit && Date.now() - hit.at < 5 * 60 * 1000) return hit.files;  // spares the GitHub API's 60 calls/hour/IP
  } catch { /* no storage */ }
  let paths;
  try {
    const tree = await api(`https://api.github.com/repos/${ATLAS.repo}/git/trees/${ATLAS.branch}?recursive=1`);
    paths = tree.tree.map((n) => n.path);
  } catch {
    const flat = await api(`https://data.jsdelivr.com/v1/packages/gh/${ATLAS.repo}@${ATLAS.branch}?structure=flat`);
    paths = flat.files.map((n) => n.name.replace(/^\//, ""));
  }
  const files = paths.filter((x) => ATLAS_FILE.test(x));
  try { sessionStorage.setItem("dv.atlasFiles", JSON.stringify({ at: Date.now(), files })); } catch { /* no storage */ }
  return files;
}

// Fetches a .gz file and returns its text (null if missing). Decompresses in the browser unless the host already did.
async function fetchGzipText(url) {
  const res = await fetch(url);
  if (!res.ok) return null;
  const bytes = new Uint8Array(await res.arrayBuffer());
  if (bytes[0] !== 0x1f || bytes[1] !== 0x8b) return new TextDecoder().decode(bytes);
  return new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"))).text();
}

// System names: computed here from the address (names.js + names-data.json.gz, a port of hadsh/nms_namegen). Checked on a sample against NMS Almanac.
let namesReady = null;
function loadNames() {
  if (!namesReady) namesReady = (async () => {
    try {
      if (!window.NMSNames) return false;
      const t = await fetchGzipText(new URL("names-data.json.gz", document.baseURI).href);
      if (!t) return false;
      NMSNames.init(JSON.parse(t));
      return true;
    } catch { return false; }
  })();
  return namesReady;
}
const sysName = (address) => (window.NMSNames && NMSNames.ready() ? NMSNames.name(address) : "");
const nameHtml = (address) => { const n = sysName(address); document.title = n ? `${n} - Derelict Viewer` : "Derelict Viewer";
  return n ? `<h1 class="sys-name">${esc(n)} <span class="chip" title="Computed from the address by a port of nms_namegen. Checked against NMS Almanac on a 20-system sample (20/20 after one correction). Players can rename systems.">name checked</span></h1>` : ""; };

// atlas CSV (region file or combined list) -> the same row shape as the local summaries.
// glyphs P SSS YY ZZZ XXX -> address 000 SSS GG YY ZZZ XXX; region = YY ZZZ XXX
function parseAtlasCsv(text, gal) {
  const lines = text.split(/\r?\n/).filter((l) => l && !l.startsWith("#"));
  const head = lines.shift().split(",");
  return lines.map((line) => {
    const v = Object.fromEntries(line.split(",").map((x, k) => [head[k], x]));
    const n = (k) => (v[k] === undefined || v[k] === "" ? null : Number(v[k]));
    const g = v.glyphs.toUpperCase(), gg = v.galaxy === undefined ? gal.toUpperCase() : Number(v.galaxy).toString(16).padStart(2, "0").toUpperCase();
    return { status: "ok", region: g.slice(4), glyphs: g, address: `000${g.slice(1, 4)}${gg}${g.slice(4)}`, map: Number(v.map) || 0,  // 0 none, 1 top crates, 2 top frigate modules, 3 both (full map in views/top100.json.gz)
      preset: v.preset, rooms: n("rooms"), floors: n("floors"), stair_pieces: n("stairs"), hangar_pieces: n("hangars"),
      salvage_crates: n("crates"), footlockers: n("footlockers"), briefcases: n("briefcases"), tall_lockers: n("tall_lockers"), room_detail: v.room_detail || "",
      reward_name: v.reward_name || null, reward_class: (v.reward_class || "").toUpperCase() || null, reward_ambiguous: v.reward_ambiguous === "1" || v.reward_ambiguous === "true", reward_alt: v.reward_alt || "",
      frigate_modules: n("frigate_modules"), frigate_modules_ambiguous: n("frigate_modules_ambiguous"), frigate_module_rooms: v.frigate_module_rooms || "",
      frigate_module_ids: v.frigate_module_ids || "", frigate_module_alt_ids: v.frigate_module_alt_ids || "",
      game_build: v.game_build || null,  // per-row only in a mixed-build index (format 6); else see atlasBuild
      templates: (v.room_detail || "").replace(/:[^|]*/g, "") };
  });
}

let atlasRowsCache = null;  // the combined list is fetched once per visit (the derelict page reads the reward from it)
function atlasRows() {
  if (!atlasRowsCache) atlasRowsCache = loadAtlasRows().catch((e) => { atlasRowsCache = null; throw e; });
  return atlasRowsCache;
}
// Game build the atlas rows were generated with: the index's first '#' line ends with "game_build 7.05 13D5060D"
// (or "game_build mixed (...)" plus a per-row column); region files name it in "NMS.exe 7.05 SHA-256 ...".
// No tag = 7.05 (every row published before 2026-10-22 came from the 7.05 generator).
let atlasBuild = null;
function readAtlasBuild(text) {
  const head = text.split(/\r?\n/, 6).filter((l) => l.startsWith("#")).join(" ");
  const m = head.match(/game_build (mixed \([^)]*\)|\S+ [0-9A-Fa-f]{8})/) || head.match(/NMS\.exe (\S+) SHA-256 ([0-9A-Fa-f]{8})/);
  return !m ? "7.05 13D5060D" : m[2] ? `${m[1]} ${m[2].toUpperCase()}` : m[1];
}
function buildLabel(b) {
  const m = /^(\S+) ([0-9A-F]{8})$/.exec(b || "");
  return m ? `game build NMS ${m[1]} (exe ${m[2]})` : `game builds ${b}`;
}
async function loadAtlasRows() {
  const text = await fetchGzipText(ATLAS_RAW + "index/systems.csv.gz");
  if (text) { atlasBuild = readAtlasBuild(text); return parseAtlasCsv(text, "00"); }
  const files = await atlasFiles();
  const builds = new Set();
  const parts = await Promise.all(files.map(async (path) => {
    const r = await fetch(ATLAS_RAW + path);
    if (!r.ok) throw new Error(`${path}: ${r.status}`);
    const t = await r.text();
    builds.add(readAtlasBuild(t));
    return parseAtlasCsv(t, path.match(ATLAS_FILE)[1]);
  }));
  atlasBuild = builds.size > 1 ? `mixed (${[...builds].sort().join(", ")})` : [...builds][0] || "7.05 13D5060D";
  return parts.flat();
}

// One system's atlas row (address 000 SSS GG YY ZZZ XXX -> regions/gGG/YY/ZZZ/YYZZZXXX.csv), or null.
async function atlasSystem(address) {
  const path = `regions/g${address.slice(6, 8).toLowerCase()}/${address.slice(8, 10)}/${address.slice(10, 13)}/${address.slice(8)}.csv`;
  const res = await fetch(ATLAS_RAW + path);
  if (!res.ok) return null;
  return parseAtlasCsv(await res.text(), address.slice(6, 8)).find((r) => r.address === address) || null;
}

async function sweepView(params) {
  app.innerHTML = `<p class="muted">Loading the atlas from GitHub…</p>`;
  await doneReady;
  // sources: the GitHub atlas (default, all regions together) or this PC's own sweeps (local server only)
  let local = [];
  if (HAS_SERVER) try { local = await api("/api/regions"); } catch { /* server gone */ }
  const keys = ["atlas", ...local.map((r) => r.region)];
  const wanted = params.get("region") || store("source");
  const source = keys.includes(wanted) ? wanted : "atlas";
  store("source", source);
  let rows, sourceNote;
  try {
    if (source === "atlas") {
      rows = await atlasRows();
      sourceNote = `${new Set(rows.map((r) => r.region)).size} regions from <a href="https://github.com/${ATLAS.repo}" target="_blank" rel="noopener">${ATLAS.repo}</a>, loaded by this browser`
        + ` · <span class="game-build" title="the NMS build the generator, rewards and loot of these rows were made with">${esc(buildLabel(atlasBuild))}</span>`;
    } else {
      rows = (await api(`/api/summary/${source}`)).map((r) => ({ ...r, region: source.slice(0, 8) }));
      sourceNote = "this PC's sweep " + esc(source);
    }
  } catch (e) { app.innerHTML = `<p class="error">Could not load ${source === "atlas" ? "the atlas from GitHub" : esc(source)}: ${esc(e.message)}</p>`; return; }
  const seen = new Set();
  rows = rows.filter((r) => r.status === "ok" && !seen.has(r.address) && seen.add(r.address)).map((r) => ({
    ...r,
    briefcases: r.briefcases ?? null, tall_lockers: r.tall_lockers ?? null,
    reward: REWARD_RANK[r.reward_class] ?? null,  // sort value of the Reward column; total, totalText: set in render() from the "Total counts" groups
    hangar: (r.hangar_pieces || 0) > 0 || /\bR_HANG\b/.test(r.templates || ""),
  }));
  if (await loadNames()) for (const r of rows) r.system_name = NMSNames.name(r.address);
  const regionKeys = [...new Set(rows.map((r) => r.region))].sort();
  const presets = [...new Set(rows.map((r) => r.preset))].sort();
  const f = Object.assign({ region: "", preset: "", maxRooms: "", maxFloors: "", noStairs: false, noHangar: false, hasMap: false, mapList: "", hideDone: false, minCrates: "", minTotal: "", minBriefcases: "", minTallLockers: "", minFrigateModules: "", q: "",
    sort: "total", asc: false, pageSize: 100 }, store("filters") || {});
  f.totalGroups = { ...DEFAULT_TOTAL_GROUPS, ...(f.totalGroups || {}) };
  if (!Array.isArray(f.rwNames)) f.rwNames = [];
  if (!Array.isArray(f.rwClasses)) f.rwClasses = [];
  const rewardNames = [...new Set(rows.flatMap((r) => rewardOptions(r).map((o) => o.name)))].sort();
  f.rwNames = f.rwNames.filter((n) => rewardNames.includes(n));
  const PAGE_SIZES = [100, 250, 500, 1000];
  if (!PAGE_SIZES.includes(Number(f.pageSize))) f.pageSize = 100;
  let page = 0;
  const pager = (id) => `<div class="pager" id="${id}"><button type="button" data-p="prev">◀ Prev</button>
    <span class="pg-info"></span><button type="button" data-p="next">Next ▶</button>
    <label>Per page <select class="pg-size">${PAGE_SIZES.map((n) => `<option${n === Number(f.pageSize) ? " selected" : ""}>${n}</option>`).join("")}</select></label></div>`;

  app.innerHTML = `
    <div class="head"><h1>Derelict atlas</h1>
      ${local.length ? `<label class="muted">Source <select id="region"><option value="atlas">GitHub atlas (all regions)</option>${local.map((r) =>
        `<option value="${esc(r.region)}"${r.region === source ? " selected" : ""}>This PC: ${esc(r.region)} (${r.rows})</option>`).join("")}</select></label>` : ""}
      <span class="muted">${sourceNote}</span></div>
    <div class="filters">
      <label>Region <select id="f-region"><option value="">All</option>${regionKeys.map((k) => `<option value="${k}">${k.slice(0, 2)} ${k.slice(2, 5)} ${k.slice(5)}</option>`).join("")}</select></label>
      <label>Preset <select id="f-preset"><option value="">All</option>${presets.map((p) => `<option>${esc(p)}</option>`).join("")}</select></label>
      <label>Max rooms <input id="f-maxRooms" type="number" min="1"></label>
      <label>Max floors <input id="f-maxFloors" type="number" min="1"></label>
      <label><input id="f-noStairs" type="checkbox"> No stairs</label>
      <label><input id="f-noHangar" type="checkbox"> No hangar</label>
      <label title="Hide the derelicts you marked Done on their page"><input id="f-hideDone" type="checkbox"> Hide done</label>
      <label title="The top 100 systems by crates and the top 100 by frigate modules have a full map and 3D view"><input id="f-hasMap" type="checkbox"> Has map</label>
      <label title="Which top list: crates + footlockers, or predicted frigate modules (a system can be in both)">List <select id="f-mapList"><option value="">Any</option><option value="crates">Top crates</option><option value="modules">Top modules</option></select></label>
      <label>Min crates <input id="f-minCrates" type="number" min="0"></label>
      <label title="Minimum of the Total column (the counts ticked under Total counts; a 'N+' total is compared by its known part N)">Min total <input id="f-minTotal" type="number" min="0"></label>
      ${totalGroupsHtml("f", f.totalGroups)}
      <label title="Systems whose briefcase count is not known yet are left out">Min briefcases <input id="f-minBriefcases" type="number" min="0"></label>
      <label title="Systems whose tall locker count is not known yet are left out">Min tall lockers <input id="f-minTallLockers" type="number" min="0"></label>
      <label title="Systems without a computed prediction are left out">Min frigate modules <input id="f-minFrigateModules" type="number" min="0"></label>
      <label>Search <input id="f-q" placeholder="glyphs / name / template" style="width:150px"></label>
      <button id="f-reset" type="button">Reset</button>
      <button id="col-toggle" type="button" aria-expanded="false" aria-controls="col-panel">Columns</button>
    </div>
    ${rewardNames.length ? `<div class="filters reward-picker"><b>Reward:</b>
      <details class="rw-names"><summary id="rw-sum"></summary><div class="rw-list">${rewardNames.map((n, k) =>
        `<label><input type="checkbox" data-rw="${k}"> ${esc(n)}</label>`).join("")}</div></details>
      <span class="rw-classes">Class ${REWARD_CLASSES.map((c) => `<label>${rewardBadge(c)}<input type="checkbox" data-rwc="${c}"></label>`).join("")}</span>
      <label title="Hide the systems that do not match; otherwise they stay below the matching ones"><input id="f-rwOnly" type="checkbox"> Only matching</label>
      <span class="muted">Matching systems come first, best class first, then the sort below. A system with an ambiguous prediction matches if any alternative does.</span></div>`
      : ""}
    <div id="col-panel" class="col-panel" hidden></div>
    <details id="pruned-stats" class="note" hidden><summary>Pruned systems statistics</summary><label>Scope <select id="pruned-scope"></select></label><div id="pruned-stats-body"></div></details>
    <div id="stats" class="stats"></div>
    ${pager("pager-top")}
    <div class="table-wrap"><table><thead><tr id="head-row"></tr></thead>
      <tbody id="rows"></tbody></table></div>
    ${pager("pager-bottom")}
    <p class="note">Floors come from the rooms' occupied grid cells; stairs and hangar from the generator's scene pieces; room and container
      counts are confirmed in-game on several derelicts. A "-real" list holds only systems that exist (purple systems need the purple-star unlock);
      other lists may include system numbers that do not exist. Atlas rows are verified by re-generation (see the atlas README). The glyph code's first digit (planet) can be any planet in the system.</p>`;

  fetchGzipText(ATLAS_RAW + "stats/pruned.json.gz").then((text) => {
    if (!text) return;
    const data = JSON.parse(text), panel = document.getElementById("pruned-stats"), select = document.getElementById("pruned-scope");
    const scopes = [["overall", data.overall], ...Object.entries(data.by_region || {}).sort(([a], [b]) => a.localeCompare(b))];
    if (!data.overall || !scopes.length) return;
    panel.hidden = false;
    select.innerHTML = scopes.map(([key]) => `<option value="${esc(key)}">${key === "overall" ? "All regions" : esc(key)}</option>`).join("");
    const fmt = (n) => Number(n).toLocaleString();
    const renderPruned = () => {
      const s = scopes.find(([key]) => key === select.value)?.[1];
      if (!s) return;
      const measures = Object.entries(s.container_counts || {}).map(([name, x]) => `<tr><td>${esc(name)}</td><td>${fmt(x.median)}</td><td>${fmt(x.mean)}</td><td>${fmt(x.max)}</td></tr>`).join("");
      const dist = (title, values) => `<details><summary>${title}</summary><pre>${esc(Object.entries(values || {}).sort(([a], [b]) => a.localeCompare(b)).map(([k, v]) => `${k}: ${fmt(v)}`).join("\n") || "No data")}</pre></details>`;
      document.getElementById("pruned-stats-body").innerHTML = `<p>${fmt(s.count)} systems excluded; threshold: ${esc(data.rule?.expression || "")}; applied ${esc(data.applied_at || "")}. Estimated/predicted frigate modules lost: ${s.frigate_modules_lost == null ? "not computed" : fmt(s.frigate_modules_lost)}.</p>
        <table><thead><tr><th>Containers</th><th>Median</th><th>Mean</th><th>Max</th></tr></thead><tbody>${measures}</tbody></table>
        ${dist("Derelict types", s.preset_counts)}${dist("Room counts", s.room_count_counts)}${dist("End rewards by item and class", s.reward_counts)}`;
    };
    select.onchange = renderPruned;
    renderPruned();
  }).catch((e) => console.warn("pruned-system statistics unavailable", e));

  const srcEl = document.getElementById("region");
  if (srcEl) srcEl.onchange = (e) => { store("source", e.target.value); location.hash = `#/?region=${e.target.value}`; };
  if (f.region && !regionKeys.includes(f.region)) f.region = "";
  for (const k of ["region", "preset", "maxRooms", "maxFloors", "minCrates", "minTotal", "minBriefcases", "minTallLockers", "minFrigateModules", "mapList", "q"]) {
    const el = document.getElementById("f-" + k);
    el.value = f[k];
    el.oninput = () => { f[k] = el.value; render(); };
  }
  for (const k of ["noStairs", "noHangar", "hasMap", "hideDone"]) {
    const el = document.getElementById("f-" + k);
    el.checked = f[k];
    el.onchange = () => { f[k] = el.checked; render(); };
  }
  wireTotalGroups("f", f.totalGroups, () => { renderHead(); render(); });
  const rwBoxes = [...app.querySelectorAll("[data-rw]")], rwClassBoxes = [...app.querySelectorAll("[data-rwc]")];
  const rwSum = () => { const el = document.getElementById("rw-sum"); if (el) el.textContent = f.rwNames.length ? `${f.rwNames.length} of ${rewardNames.length} reward types` : `All reward types (${rewardNames.length})`; };
  rwBoxes.forEach((b) => { b.checked = f.rwNames.includes(rewardNames[Number(b.dataset.rw)]); });
  rwClassBoxes.forEach((b) => { b.checked = f.rwClasses.includes(b.dataset.rwc); });
  const rwOnlyEl = document.getElementById("f-rwOnly");
  if (rwOnlyEl) { rwOnlyEl.checked = Boolean(f.rwOnly); rwOnlyEl.onchange = () => { f.rwOnly = rwOnlyEl.checked; render(); }; }
  const readRewardPick = () => {
    f.rwNames = rwBoxes.filter((b) => b.checked).map((b) => rewardNames[Number(b.dataset.rw)]);
    f.rwClasses = rwClassBoxes.filter((b) => b.checked).map((b) => b.dataset.rwc);
    rwSum(); render();
  };
  [...rwBoxes, ...rwClassBoxes].forEach((b) => { b.onchange = readRewardPick; });
  rwSum();
  document.getElementById("f-reset").onclick = () => { store("filters", null); sweepView(params); };

  // Columns: order and visibility live in `layout` (saved as dv.columns). Header cells sort on click and reorder when dragged
  // (pointer events: mouse and touch); the Columns panel does the same with checkboxes and up/down buttons.
  migrateColumnLayout();
  let layout = resolveColumnLayout(store("columns"));
  const colByKey = Object.fromEntries(COLUMNS.map((c) => [c.key, c]));
  const visibleCols = () => layout.order.filter((k) => !layout.hidden.includes(k)).map((k) => colByKey[k]);
  const layoutJson = () => JSON.stringify({ order: layout.order, hidden: layout.hidden });
  const headRow = document.getElementById("head-row"), colPanel = document.getElementById("col-panel");
  const colToggle = document.getElementById("col-toggle");
  function renderHead() {
    headRow.innerHTML = visibleCols().map((c) => `<th data-k="${c.key}" class="${c.num ? "num" : ""}"${c.title ? ` title="${esc(typeof c.title === "function" ? c.title() : c.title)}"` : ""}>${esc(c.label)}</th>`).join("");
  }
  function renderColPanel(focus) {
    const visible = layout.order.length - layout.hidden.length;
    colPanel.innerHTML = `<ul>${layout.order.map((k, i) => `<li data-k="${k}"${layout.hidden.includes(k) ? ' class="off"' : ""}>
        <span class="grip" title="Drag to reorder" aria-hidden="true">⠿</span><label><input type="checkbox" data-act="show"${layout.hidden.includes(k) ? "" : " checked"}${visible <= 1 && !layout.hidden.includes(k) ? " disabled" : ""}> ${esc(colByKey[k].label)}</label>
        <button type="button" data-act="up" aria-label="Move ${esc(colByKey[k].label)} left"${i === 0 ? " disabled" : ""}>▲</button>
        <button type="button" data-act="down" aria-label="Move ${esc(colByKey[k].label)} right"${i === layout.order.length - 1 ? " disabled" : ""}>▼</button></li>`).join("")}</ul>
      <div class="col-actions"><button type="button" data-act="reset">Reset columns</button>
        <button type="button" data-act="copy">Copy column layout</button></div>
      <textarea id="col-json" readonly rows="3" aria-label="Column layout JSON" hidden></textarea>`;
    if (focus) { const el = colPanel.querySelector(focus); if (el && !el.disabled) el.focus(); }
  }
  function setLayout(next, focus) {
    layout = next;
    store("columns", layout);
    renderHead();
    renderColPanel(focus);
    render(true);
  }
  function moveColumn(key, targetKey) {
    const order = layout.order.filter((k) => k !== key);
    order.splice(layout.order.indexOf(targetKey), 0, key);
    setLayout({ order, hidden: layout.hidden });
  }
  colToggle.onclick = () => {
    colPanel.hidden = !colPanel.hidden;
    colToggle.setAttribute("aria-expanded", String(!colPanel.hidden));
  };
  colPanel.onclick = async (ev) => {
    const btn = ev.target.closest("button");
    if (!btn) return;
    const li = btn.closest("li"), act = btn.dataset.act;
    if (act === "reset") return setLayout(resolveColumnLayout(DEFAULT_COLUMN_LAYOUT));
    if (act === "copy") {
      const box = document.getElementById("col-json"), text = layoutJson();
      box.value = text; box.hidden = false; box.focus(); box.select();
      try { await navigator.clipboard.writeText(text); } catch { try { document.execCommand("copy"); } catch { /* user can copy the box */ } }
      return;
    }
    const i = layout.order.indexOf(li.dataset.k), j = act === "up" ? i - 1 : i + 1;
    if (j < 0 || j >= layout.order.length) return;
    const order = [...layout.order];
    [order[i], order[j]] = [order[j], order[i]];
    setLayout({ order, hidden: layout.hidden }, `li[data-k="${li.dataset.k}"] [data-act="${act}"]`);
  };
  // drag a row by its grip (mouse and touch) onto another row; the line shows where it lands
  let pd = null;
  const clearPanelDrop = () => { for (const li of colPanel.querySelectorAll("li")) li.classList.remove("dragging", "drop-before", "drop-after"); };
  const rowAt = (x, y) => { const el = document.elementFromPoint(x, y); return el && el.closest ? el.closest("#col-panel li") : null; };
  colPanel.onpointerdown = (ev) => {
    const grip = ev.target.closest(".grip");
    if (!grip || ev.button !== 0) return;
    ev.preventDefault();
    pd = { li: grip.closest("li"), id: ev.pointerId, to: null, after: false };
    pd.li.classList.add("dragging");
    try { colPanel.setPointerCapture(ev.pointerId); } catch { /* not capturable */ }
  };
  colPanel.onpointermove = (ev) => {
    if (!pd || ev.pointerId !== pd.id) return;
    const over = rowAt(ev.clientX, ev.clientY);
    for (const li of colPanel.querySelectorAll("li")) li.classList.remove("drop-before", "drop-after");
    pd.to = over && over !== pd.li ? over : null;
    if (pd.to) {
      const b = pd.to.getBoundingClientRect(), lis = [...colPanel.querySelectorAll("li")];
      pd.after = lis.indexOf(pd.to) > lis.indexOf(pd.li);  // moving down/right: land after the target, like moving up lands before
      pd.to.classList.add(pd.after ? "drop-after" : "drop-before");
    }
  };
  const endPanelDrag = (ev, cancelled) => {
    if (!pd || ev.pointerId !== pd.id) return;
    const d = pd; pd = null;
    clearPanelDrop();
    if (cancelled || !d.to) return;
    const key = d.li.dataset.k, order = layout.order.filter((k) => k !== key), at = order.indexOf(d.to.dataset.k);
    order.splice(d.after ? at + 1 : at, 0, key);
    setLayout({ order, hidden: layout.hidden });
  };
  colPanel.onpointerup = (ev) => endPanelDrag(ev, false);
  colPanel.onpointercancel = (ev) => endPanelDrag(ev, true);
  colPanel.onchange = (ev) => {
    const li = ev.target.closest("li");
    if (!li || ev.target.dataset.act !== "show") return;
    const hidden = ev.target.checked ? layout.hidden.filter((k) => k !== li.dataset.k) : [...layout.hidden, li.dataset.k];
    setLayout({ order: layout.order, hidden }, `li[data-k="${li.dataset.k}"] [data-act="show"]`);
  };
  // header: click sorts, a drag past 6px reorders (and swallows the click that follows)
  let drag = null, dragged = false;
  const headAt = (x) => [...headRow.children].find((th) => { const b = th.getBoundingClientRect(); return x >= b.left && x < b.right; });
  const clearDrop = () => { for (const th of headRow.children) th.classList.remove("dragging", "drop-l", "drop-r"); };
  headRow.onpointerdown = (ev) => {
    const th = ev.target.closest("th");
    if (th && ev.button === 0) drag = { th, x: ev.clientX, id: ev.pointerId, on: false, to: null };
  };
  headRow.onpointermove = (ev) => {
    if (!drag || ev.pointerId !== drag.id) return;
    if (!drag.on) {
      if (Math.abs(ev.clientX - drag.x) < 6) return;
      drag.on = true;
      try { headRow.setPointerCapture(ev.pointerId); } catch { /* not capturable */ }
      drag.th.classList.add("dragging");
    }
    const over = headAt(ev.clientX);
    for (const th of headRow.children) th.classList.remove("drop-l", "drop-r");
    drag.to = over && over !== drag.th ? over : null;
    if (drag.to) drag.to.classList.add([...headRow.children].indexOf(drag.to) < [...headRow.children].indexOf(drag.th) ? "drop-l" : "drop-r");
  };
  const endDrag = (ev, cancelled) => {
    if (!drag || ev.pointerId !== drag.id) return;
    const d = drag; drag = null;
    clearDrop();
    if (!d.on) return;
    dragged = true;
    setTimeout(() => { dragged = false; }, 0);
    if (!cancelled && d.to) moveColumn(d.th.dataset.k, d.to.dataset.k);
  };
  headRow.onpointerup = (ev) => endDrag(ev, false);
  headRow.onpointercancel = (ev) => endDrag(ev, true);
  headRow.onclick = (ev) => {
    const th = ev.target.closest("th");
    if (!th || dragged) return;
    const k = th.dataset.k; f.asc = f.sort === k ? !f.asc : false; f.sort = k; render();
  };
  renderHead();
  renderColPanel();
  for (const el of app.querySelectorAll(".pager")) {
    const turn = (step) => { page += step; render(true); if (el.id === "pager-bottom") document.getElementById("pager-top").scrollIntoView(); };
    el.querySelector('[data-p="prev"]').onclick = () => turn(-1);
    el.querySelector('[data-p="next"]').onclick = () => turn(1);
    el.querySelector(".pg-size").onchange = (ev) => { f.pageSize = Number(ev.target.value); render(); };
  }

  // keepPage: only the page changed (Prev/Next); any filter, sort or page-size change goes back to page 1
  function render(keepPage = false) {
    if (!keepPage) page = 0;
    store("filters", f);
    const num = (v) => (v === "" || v === null || v === undefined ? null : Number(v));
    const q = f.q.trim().toUpperCase();
    for (const r of rows) {
      const t = totalOf(r, f.totalGroups);
      r.total = t.n; r.totalUnknown = t.unknown.length ? 1 : 0; r.totalText = totalText(t); r.totalTip = totalTip(t);
    }
    // reward picker: a system matches when its predicted reward (or, if ambiguous, an alternative) is one of the picked types in one of the picked classes
    const picking = f.rwNames.length > 0 || f.rwClasses.length > 0;
    const matchRank = (r) => {  // best class rank among the matching options, 0 = no match
      let best = 0;
      for (const o of rewardOptions(r)) {
        if ((!f.rwNames.length || f.rwNames.includes(o.name)) && (!f.rwClasses.length || f.rwClasses.includes(o.cls))) best = Math.max(best, REWARD_RANK[o.cls] || 1);
      }
      return best;
    };
    if (picking) for (const r of rows) r.rwMatch = matchRank(r);
    const shown = rows.filter((r) =>
      (!picking || !f.rwOnly || r.rwMatch > 0) &&
      (!f.region || r.region === f.region) && (!f.preset || r.preset === f.preset) &&
      (num(f.maxRooms) === null || r.rooms <= num(f.maxRooms)) &&
      (num(f.maxFloors) === null || r.floors <= num(f.maxFloors)) &&
      (!f.hideDone || !isDone(r.address)) && (!f.noStairs || !r.stair_pieces) && (!f.noHangar || !r.hangar) && (!f.hasMap || r.map) && (!f.mapList || (f.mapList === "crates" ? r.map & 1 : r.map & 2)) &&
      (num(f.minCrates) === null || r.salvage_crates >= num(f.minCrates)) &&
      (num(f.minTotal) === null || r.total >= num(f.minTotal)) &&
      (num(f.minBriefcases) === null || (r.briefcases !== null && r.briefcases >= num(f.minBriefcases))) &&
      (num(f.minTallLockers) === null || (r.tall_lockers !== null && r.tall_lockers >= num(f.minTallLockers))) &&
      (num(f.minFrigateModules) === null || (r.frigate_modules !== null && r.frigate_modules >= num(f.minFrigateModules))) &&
      (!q || r.glyphs.includes(q) || r.address.includes(q) || (r.templates || "").includes(q) || (r.system_name || "").toUpperCase().includes(q)));
    const dir = f.asc ? 1 : -1;
    shown.sort((a, b) => {
      if (picking && (a.rwMatch > 0 || b.rwMatch > 0)) {  // matching systems first, best class first
        const d = (b.rwMatch > 0) - (a.rwMatch > 0) || b.rwMatch - a.rwMatch;
        if (d) return d;
      }
      const x = a[f.sort], y = b[f.sort];
      const nx = x === null || x === undefined, ny = y === null || y === undefined;  // unknown values sort last in both directions
      if (nx || ny) return nx && ny ? b.total - a.total : nx ? 1 : -1;
      // equal values: a known total comes before an "N+" lower bound, then the larger total first
      return (x > y ? 1 : x < y ? -1 : 0) * dir || (f.sort === "total" ? a.totalUnknown - b.totalUnknown : 0) || (b.total - a.total);
    });
    for (const th of app.querySelectorAll("th")) {
      th.classList.toggle("sorted", th.dataset.k === f.sort);
      th.classList.toggle("asc", th.dataset.k === f.sort && f.asc);
    }
    const totals = shown.map((r) => r.total).sort((a, b) => a - b);
    const median = totals.length ? totals[Math.floor(totals.length / 2)] : 0;
    document.getElementById("stats").textContent =
      `${shown.length} of ${rows.length} systems${Object.keys(DONE).length ? ` (${rows.filter((r) => isDone(r.address)).length} done)` : ""} · median total ${median} · max ${totals.length ? totals[totals.length - 1] : 0} (total of: ${totalNames(f.totalGroups)})`
      + (shown.some((r) => r.totalUnknown) ? " · systems with an unknown ticked group count their known part only" : "");
    const size = Number(f.pageSize), pages = Math.max(1, Math.ceil(shown.length / size));
    page = Math.min(Math.max(page, 0), pages - 1);
    const first = page * size, last = Math.min(shown.length, first + size);
    for (const el of app.querySelectorAll(".pager")) {
      el.querySelector(".pg-info").textContent = shown.length
        ? `${first + 1}–${last} of ${shown.length} · page ${page + 1} of ${pages}` : "no matches";
      el.querySelector('[data-p="prev"]').disabled = page === 0;
      el.querySelector('[data-p="next"]').disabled = page >= pages - 1;
      el.querySelector(".pg-size").value = String(size);
    }
    const cols = visibleCols();
    document.getElementById("rows").innerHTML = shown.slice(first, last).map((r) => `
      <tr data-a="${esc(r.address)}"${isDone(r.address) ? ' class="done" title="Done"' : ""}>${cols.map((c) => `<td class="${[c.num ? "num" : "", c.cls || ""].join(" ").trim()}">${c.cell(r)}</td>`).join("")}</tr>`).join("");
    for (const tr of document.querySelectorAll("#rows tr")) tr.onclick = () => { location.hash = `#/d/${tr.dataset.a}`; };
  }
  render();
}

// ---------------------------------------------------------------- one derelict

const { cellKey } = DerelictModel;
let bundleCache = null;  // views/top100.json.gz: {v, t: piece table, s: {ADDRESS16: view}}, fetched once per visit
const shardCache = new Map();
// views/ondemand/<REGION>.json.gz (REGION = the last 8 hex digits of the address): maps visitors requested. -> shard or null
function ondemandShard(address) {
  const region = address.slice(8);
  if (!shardCache.has(region)) {
    shardCache.set(region, fetchGzipText(ATLAS_RAW + `views/ondemand/${region}.json.gz`).then((t) => (t ? JSON.parse(t) : null)).catch(() => null));
  }
  return shardCache.get(region).then((sh) => (sh && sh.v === 4 && sh.s && sh.s[address] ? sh : null));
}

async function atlasBundle() {
  if (!bundleCache) {
    bundleCache = fetchGzipText(ATLAS_RAW + "views/top100.json.gz").then((text) => (text ? JSON.parse(text) : null))
      .catch((e) => { bundleCache = null; throw e; });
  }
  return bundleCache;
}

// viewer/static/piece_props.json (viewer/build_piece_props.py): per placed piece, its extra loot containers and hazards
// (enemy spawners, turrets, bug sacs), so layouts without them and the published views get them from their pieces alone.
let propsCache = null;
function pieceProps() {
  if (!propsCache) propsCache = fetch("piece_props.json").then((r) => (r.ok ? r.json() : null)).then((j) => (j && j.scenes) || null).catch(() => null);
  return propsCache;
}

// -> { m: DerelictModel.build result, local: derelict.json when generated on this PC } or null when neither exists.
// Local derelicts go through the same pack/unpack as published views, so both draw identically.
async function loadDerelict(address) {
  const props = await pieceProps();
  if (HAS_SERVER) {
    let d = null;
    try { d = await api(`/api/derelict/${address}`); } catch (e) { if (e.status !== 404) throw e; }
    if (d) {
      let index = null;
      try { index = await api("/api/meshes/index"); } catch { /* not built */ }
      const names = index ? Object.keys(index).filter((n) => n !== "_meta").sort() : [];
      if (!names.length) return { m: DerelictModel.build(d, null, props), local: d };
      const ids = new Map(names.map((n, k) => [n, k]));
      const u = DerelictModel.unpack(DerelictModel.pack(d, (n) => ids.get(n)), DerelictModel.piecesTable(index, names, props));
      return { m: DerelictModel.build(u.d, u.index, props), local: d };
    }
  }
  const bundle = await atlasBundle();
  if (!bundle || !bundle.s[address]) {
    // not in the published top lists: a map made by the on-demand map server earlier in this visit (ondemand.js)
    const od = typeof OnDemand !== "undefined" ? OnDemand.cached(address) : null;
    if (!od) {
      // a map that an earlier visitor requested is published in the region's file views/ondemand/<REGION>.json.gz (same compact v4 as the
      // top-100 bundle; tools/publish_ondemand_maps.py): draw it from there, "Generate map" is then not offered
      const shard = await ondemandShard(address);
      if (!shard) return null;
      const us = DerelictModel.unpack(DerelictCompact.expand(shard.s[address], shard.t), DerelictCompact.table3(shard.t));
      return { m: DerelictModel.build(us.d, us.index, props), local: null, onDemand: shard.m[address], requested: true };
    }
    const u = OnDemand.unpack(address, od);
    return { m: DerelictModel.build(u.d, u.index, props), local: null, onDemand: od.m, requested: true };
  }
  const u = DerelictModel.unpack(bundle.s[address], bundle.t);
  return { m: DerelictModel.build(u.d, u.index, props), local: null };
}

// EXPERIMENTAL, local only: map data format comparison. viewer/static/compact/{top100,local}.{v3,v4}.json.gz
// (tools/derelict_view_compact.py --build): "Old" = the format-3 view as published, "New" = the compact format 4
// rebuilt in this browser (compact.js expand) and drawn through the same model.js unpack + build. Static hosting has
// no such files: then there is no switch. -> null or { old, neu (build results), same, bytes: { old, neu } (own gzip) }
const compareCache = {};
function compareFile(name) {
  if (!(name in compareCache)) compareCache[name] = fetchGzipText("compact/" + name).then((t) => (t ? JSON.parse(t) : null)).catch(() => null);
  return compareCache[name];
}
async function loadCompare(address) {
  if (!HAS_SERVER || typeof DerelictCompact === "undefined") return null;
  const props = await pieceProps();
  for (const set of ["top100", "local"]) {
    const b4 = await compareFile(`${set}.v4.json.gz`);
    if (!b4 || !b4.s[address]) continue;
    const b3 = await compareFile(`${set}.v3.json.gz`);
    if (!b3 || !b3.s[address]) continue;
    const u3 = DerelictModel.unpack(b3.s[address], b3.t);
    const [n3, n4] = b4.z[address] || [null, null];
    let u4, error = null;
    try { u4 = DerelictModel.unpack(DerelictCompact.expand(b4.s[address], b4.t), DerelictCompact.table3(b4.t)); } catch (err) { error = err.message; }
    // identical = the decoded derelicts (rooms, every piece, crates/footlockers with orientation, extras) match exactly
    const same = !error && JSON.stringify(u3.d) === JSON.stringify(u4.d);
    return { set, same, error, bytes: { old: n3, neu: n4 }, old: DerelictModel.build(u3.d, u3.index, props),
      neu: error ? null : DerelictModel.build(u4.d, u4.index, props) };
  }
  return null;
}

// "Predicted end reward" card: the reward comes from the combined list (index/systems.csv.gz), "–" while unknown or unreachable.
function fillReward(address) {
  const el = document.getElementById("reward-card");
  if (!el) return;
  const note = `<div class="rw-note muted">Applies to the system's own derelict found in space, not to summoned ones.</div>`;
  atlasRows().then((rows) => rows.find((r) => r.address === address)).catch(() => null).then((r) => {
    if (!document.getElementById("reward-card")) return;  // navigated away
    if (!r || !r.reward_name) { el.querySelector(".v").textContent = "–"; el.insertAdjacentHTML("beforeend", note.replace("Applies", r ? "Not computed yet. Applies" : "Not in the atlas index. Applies")); return; }
    const alts = r.reward_ambiguous ? parseRewardAlt(r.reward_alt) : [];
    el.querySelector(".v").innerHTML = `${r.reward_ambiguous ? "≈ " : ""}${esc(r.reward_name)} ${rewardBadge(r.reward_class)}`;
    el.insertAdjacentHTML("beforeend", (r.reward_ambiguous ? `<div class="rw-note">Ambiguous prediction${alts.length ? ": could also be " + alts.map((a) => esc(`${a.name} ${a.cls}`.trim())).join(", ") : ""}.</div>` : "") + note);
  });
}

// No full layout here: show the atlas row (per-room counts), and offer generation when this PC can.
async function atlasOnlyView(address) {
  let row = null;
  try { row = await atlasSystem(address); } catch { /* offline */ }
  const rooms = row && row.room_detail ? row.room_detail.split("|").map((x, k) => {
    const [tmpl, cl = "0/0"] = x.split(":"), [c, l] = cl.split("/").map(Number);
    return { k, info: roomInfo(tmpl), c, l };
  }) : [];
  let kind = row ? row.map : 0;
  try { const b = await atlasBundle(); if (b && b.k && b.k[address]) kind = b.k[address]; } catch { /* offline */ }
  if (row) row.map = kind;
  await loadNames();
  const shareCtx = row ? { address, name: sysName(address), glyphs: glyphsOf(address), pretty: glyphsPretty(address), map: row.map, mapName: MAP_LIST_NAMES[row.map] || "", getView3d: null,
    counts: { preset: row.preset, crates: row.salvage_crates, footlockers: row.footlockers, modules: row.frigate_modules, rooms: row.rooms, floors: row.floors, briefcases: row.briefcases } } : null;
  if (shareCtx) shareCtx.getView3d = null;
  app.innerHTML = `<p><a href="#/">← Atlas</a></p>
    ${nameHtml(address)}
    <div class="head">${glyphHtml(address, true)}${glyphMode() === "hex" ? "" : ` <span class="mono">${esc(glyphsPretty(address))}</span>`}
      ${row ? `<span class="chip ${esc(row.preset.split("_")[0])}">${esc(row.preset)}</span>` : ""}${row ? mapChips(row.map) : ""}${doneBoxHtml(address)}</div>
    ${shareCtx ? DvShare.html(shareCtx) : ""}
    ${row ? `<div class="cards"><div class="card"><div class="v">${row.rooms}</div><div class="k">Rooms</div></div>
      <div class="card"><div class="v">${row.floors ?? ""}</div><div class="k">Floors</div></div>
      <div class="card"><div class="v">${row.salvage_crates}</div><div class="k">Salvage crates</div></div>
      <div class="card"><div class="v">${row.footlockers}</div><div class="k">Footlockers</div></div>
      <div class="card" id="total-card"></div>
      <div class="card reward-card" id="reward-card" title="Predicted end reward of this system's own derelict found in space; summoned derelicts can differ."><div class="v">–</div><div class="k">Predicted end reward</div></div>
      ${row.briefcases !== null ? `<div class="card"><div class="v">${row.briefcases}</div><div class="k">Briefcases</div></div>` : ""}
      ${row.tall_lockers !== null ? `<div class="card"><div class="v">${row.tall_lockers}</div><div class="k">Tall lockers</div></div>` : ""}</div>
      <div class="table-wrap"><table><thead><tr><th class="num">#</th><th>Room</th><th class="num">Crates</th><th class="num">Footlockers</th></tr></thead><tbody>
      ${rooms.map((r) => `<tr><td class="num">${r.k}</td><td><span class="dot" style="background:${r.info.color}"></span> ${esc(r.info.label)}</td>
        <td class="num">${r.c}</td><td class="num">${r.l}</td></tr>`).join("")}</tbody></table></div>` : `<p>This system is not in the atlas.</p>`}
    ${HAS_SERVER ? `<p>Floor maps and the 3D view need the full layout: <button id="go">Generate now</button> <span id="go-status" class="muted"></span></p>`
      : `<p class="note">Full maps and the 3D view are published for two lists of 100 systems (top by crates, top by frigate modules) (tick <b>Has map</b> in the table; the top 100 by crates and the top 100 by frigate modules). Other systems show their room counts here.</p>
        ${typeof OnDemand !== "undefined" && OnDemand.available() ? `<div class="od-box"><button id="od-go">Generate map</button> <div id="od-status" class="od-status muted">Asks the map server for this system's map. Usually a few seconds; some systems take over a minute.</div></div>` : ""}`}`;
  fillReward(address);
  wireDone(address);
  if (shareCtx) DvShare.wire(shareCtx);
  const tc = document.getElementById("total-card");
  if (tc && row) {
    const g = totalGroups();
    tc.insertAdjacentHTML("beforebegin", `<div class="total-bar">${totalGroupsHtml("a", g)}</div>`);
    const fill = () => { const t = totalOf(row, g); tc.title = `Total of: ${totalNames(g)}. ${totalTip(t)}`.trim(); tc.innerHTML = `<div class="v">${totalText(t)}</div><div class="k">Total: ${totalNames(g)}</div>`; };
    fill();
    wireTotalGroups("a", g, () => { saveTotalGroups(g); fill(); });
  }
  const go = document.getElementById("go");
  if (go) go.onclick = () => generate(address, false, 0, document.getElementById("go-status"), go);
  const odGo = document.getElementById("od-go");
  if (odGo) wireOnDemand(address, odGo, document.getElementById("od-status"));
}

// "Generate map" on the public site: asks the on-demand map server (DV_CONFIG.ondemandBase, ondemand/ondemand_server.py),
// shows what is happening (preset, queue position "N of M", stage, a progress bar that never reaches 100% early, a pulse that
// shows work is going on, "taking longer than usual" when the ETA has passed), then draws the result with the same renderer
// as the top-100 maps (loadDerelict). The wording comes from the server (ondemand/eta_config.json); OnDemand.view() decides
// what to show. aria-live text changes only when something meaningful changes, not every second.
function wireOnDemand(address, btn, status) {
  btn.onclick = async () => {
    btn.disabled = true;
    const ctl = new AbortController();
    let timer = 0;
    const stop = () => { ctl.abort(); clearInterval(timer); };
    window.addEventListener("hashchange", stop, { once: true });   // left the page: stop asking
    status.className = "od-status";
    status.innerHTML = `<div class="od-line"><span class="od-pulse" aria-hidden="true"></span><strong class="od-title"></strong></div>
      <div class="od-kind muted"></div><div class="od-queue"></div>
      <div class="od-bar" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0" aria-label="Map progress"><div class="od-fill"></div></div>
      <div class="od-time muted" aria-hidden="true"></div><div class="od-busy muted"></div><ol class="od-stages muted"></ol>
      <div class="od-live sr-only" role="status" aria-live="polite"></div>`;
    const q = (sel) => status.querySelector(sel);
    const el = { title: q(".od-title"), kind: q(".od-kind"), queue: q(".od-queue"), bar: q(".od-bar"), fill: q(".od-fill"),
      time: q(".od-time"), busy: q(".od-busy"), stages: q(".od-stages"), live: q(".od-live"), line: q(".od-line") };
    const run = { st: null, t0: Date.now(), pct: 0 };
    let lastLive = "", lastStages = "";
    const paint = () => {
      const v = OnDemand.view(run, Date.now());
      run.pct = v.pct;
      el.title.textContent = v.title;
      el.kind.textContent = [v.kind, v.rooms].filter(Boolean).join(" · ");
      el.queue.textContent = v.queue;
      el.fill.style.width = v.pct + "%";
      el.bar.setAttribute("aria-valuenow", String(v.pct));
      el.bar.className = "od-bar" + (v.over ? " od-over" : "");
      el.time.textContent = [v.time, v.over ? "" : v.pct ? v.pct + "%" : ""].filter(Boolean).join(" · ");
      el.busy.textContent = v.busy;
      const sig = v.stages.join("|") + "#" + v.stage;
      if (sig !== lastStages) {
        lastStages = sig;
        el.stages.innerHTML = v.stages.map((t, k) => `<li class="${k < v.stage ? "od-done" : k === v.stage ? "od-now" : ""}">${esc(t)}</li>`).join("");
      }
      if (v.live !== lastLive) { lastLive = v.live; el.live.textContent = v.live; }
    };
    const onStatus = (s) => { run.st = s; paint(); };
    timer = setInterval(() => { if (run.st) paint(); }, 500);
    try {
      await OnDemand.request(address, { onStatus, signal: ctl.signal });
      clearInterval(timer);
      if (location.hash !== `#/d/${address}`) return;
      el.time.textContent = "Map ready, drawing…";
      el.live.textContent = "Map ready, drawing the map";
      await derelictView(address);
    } catch (err) {
      clearInterval(timer);
      if (err && err.code === "aborted") return;
      status.className = "od-status muted";
      status.textContent = OnDemand.message(err);
      status.setAttribute("role", "alert");
      btn.disabled = false;
      btn.textContent = "Try again";
    }
  };
}

async function derelictView(address) {
  app.innerHTML = `<p class="muted">Loading ${esc(address)}…</p>`;
  await doneReady;
  let got;
  try { got = await loadDerelict(address); } catch (err) { app.innerHTML = `<p class="error">${esc(err.message)}</p>`; return; }
  if (!got) return atlasOnlyView(address);
  let cmp = null;
  try { cmp = await loadCompare(address); } catch { /* comparison files unavailable: page as before */ }
  // map data (experimental): "old" format 3, "new" compact format 4 (the whole page then comes from it), "both" = maps
  // of both side by side (the rest of the page from format 3)
  const urlFmt = new URLSearchParams(location.search).get("fmt");  // ?fmt=old|new|both overrides the saved choice
  const fmt = cmp ? (cmp.neu ? (["old", "new", "both"].includes(urlFmt) ? urlFmt : store("mapFmt") || "old") : "old") : null;
  const M = cmp ? (fmt === "new" ? cmp.neu : cmp.old) : got.m, e = M.e;
  const rooms = M.rooms.map((r) => Object.assign(r, { info: roomInfo(r.template_name) }));
  const mapCtx = (m) => {
    for (const r of m.rooms) if (!r.info) r.info = roomInfo(r.template_name);
    return { rooms: m.rooms, containers: m.containers, extras: m.extras, hazards: m.hazards, doors: m.doors, links: m.links,
      e: m.e, byIndex: m.byIndex, walls: m.walls, fixtures: m.fixtures };
  };
  const mapSets = fmt === "both" ? [["Old", "format 3", cmp.bytes.old, mapCtx(cmp.old)], ["New", "compact format 4", cmp.bytes.neu, mapCtx(cmp.neu)]]
    : [[null, null, null, mapCtx(M)]];
  const byIndex = M.byIndex, containers = M.containers, doors = M.doors, links = M.links;
  let moduleRow = null;
  try { moduleRow = await atlasSystem(address); } catch (_) { /* local maps still work without the published index */ }
  if (!moduleRow && got.onDemand && got.onDemand.modules != null) moduleRow = { frigate_modules: got.onDemand.modules, frigate_modules_ambiguous: got.onDemand.modules_ambiguous ? 1 : 0, map: 0 };
  const moduleIds = new Set((moduleRow?.frigate_module_ids || "").split(".").filter(Boolean).map(Number));
  const possibleModuleIds = new Set((moduleRow?.frigate_module_alt_ids || "").split(".").filter(Boolean).map(Number));
  let outside = 0;
  for (const c of containers) {
    const r = byIndex.get(c.room_index);
    if (r && !r.cellSet.has(cellKey(Math.floor(c.g.u), c.g.level, Math.floor(c.g.v)))) outside++;
  }
  const levels = [...new Set(rooms.flatMap((r) => r.levels))].sort((a, b) => b - a);
  const deckNo = (y) => levels.indexOf(y) + 1;
  const crates = containers.filter((c) => c.container_kind === "salvage_crate").length, lockers = containers.length - crates;
  // extra loot containers and hazards: null = unknown for this layout (no data), shown as "–", never 0
  const extras = M.extras, hazards = M.hazards, HT = M.hazardTotals;
  const nExtra = (k) => (extras ? extras.filter((c) => c.container_kind === k).length : null);
  const briefcases = nExtra("briefcase"), tallLockers = nExtra("tall_locker");
  const dash = (v) => (v === null || v === undefined ? "–" : v);
  const layers = Object.assign({ extras: true, hazards: true, barrels: false }, store("layers") || {});
  const HK = DerelictModel.HAZARD_KINDS;
  const HZ_ORDER = ["T", "F", "f", "D", "B", "S", "P", "E", "X"];
  const HZ_NAMES = { T: "turret", F: "floater spawner", f: "fast floater spawner", D: "drone spawner", B: "bug spawner", S: "hanging sac",
    P: "pillar sac", E: "fiend egg", X: "explosive barrel" };
  const hzBadge = (r) => HZ_ORDER.filter((l) => r.hazardCounts[HK[l].kind]).map((l) => `${l}${r.hazardCounts[HK[l].kind]}`).join(" ");
  const hzTitle = (r) => HZ_ORDER.filter((l) => r.hazardCounts[HK[l].kind]).map((l) => `${r.hazardCounts[HK[l].kind]} ${HZ_NAMES[l]}`).join(", ")
    + (r.creaturesHi ? ` · creatures (Normal, run-time range) ${r.creaturesLo}–${r.creaturesHi}` : "");
  // hover text of a map / 3D marker (extra container or hazard)
  const MARK_TIPS = {
    c: "<b>Salvage crate</b>: can give the frigate module", l: "<b>Crew footlocker</b>: can give the frigate module",
    b: "<b>Briefcase</b> (R_ABAND_CASE): units, nanites, salvage; no frigate module",
    t: "<b>Tall locker</b> (R_ABAND_LOCK): curios, ammo, tech; no frigate module",
    F: "<b>Floater spawner</b>: 1-2 floaters (run-time range, Normal)", f: "<b>Fast floater spawner</b>: 1-2 small fast floaters (run-time range, Normal)",
    D: "<b>Drone spawner</b>: 2-3 mini drones (run-time range, Normal)", B: "<b>Bug spawner</b>: 3-5 bugs", E: "<b>Fiend egg</b>",
    T: "<b>Ceiling turret</b> (deploys when it detects you)", S: "<b>Hanging sac</b>: bursts into 6-8 biological horrors (Normal, run-time range)",
    P: "<b>Pillar sac</b>: 6-8 biological horrors (Normal, run-time range)", X: "<b>Explosive barrel</b>",
  };
  const markTip = (code, room) => {
    const r = byIndex.get(room);
    return `${MARK_TIPS[code]}${r ? `<br><span class="muted">room ${r.room_index} · ${esc(r.info.label)}</span>` : ""}`;
  };
  const d = { address: M.address, preset: M.preset, seed: M.seed, room_count: rooms.length, instance_count: M.instanceCount,
    notes: got.local ? got.local.notes : "" };

  let view3d = null;
  let mapKind = moduleRow ? moduleRow.map : 0;   // region files have no map column: the bundle's "k" says which top lists a system is in
  try { const b = await atlasBundle(); if (b && b.k && b.k[address]) mapKind = b.k[address]; } catch { /* offline */ }
  await loadNames();
  const shareCtx = { address: d.address, name: sysName(d.address), glyphs: glyphsOf(d.address), pretty: glyphsPretty(d.address), map: mapKind, mapName: MAP_LIST_NAMES[mapKind] || "",
    getView3d: () => view3d,
    counts: { preset: d.preset, crates, footlockers: lockers, modules: moduleRow ? moduleRow.frigate_modules : null, rooms: d.room_count, floors: levels.length, briefcases: extras ? briefcases : null } };
  app.innerHTML = `
    <p><a href="#/">← Atlas</a></p>
    ${nameHtml(d.address)}
    <div class="head">${glyphHtml(d.address, true)}${glyphMode() === "hex" ? "" : ` <span class="mono">${esc(glyphsPretty(d.address))}</span>`}
      <span class="chip ${esc(d.preset.split("_")[0])}">${esc(d.preset)}</span>${mapChips(mapKind)}
      <span class="muted mono">address ${esc(d.address)} · seed ${esc(d.seed)}</span>
      ${doneBoxHtml(d.address)}</div>
    ${DvShare.html(shareCtx)}
    ${got.requested ? `<p class="note"><span class="chip" title="A visitor asked the map server for this system; the map was generated and published.">Requested map</span> Made on request by the map server; it is not one of the top lists.</p>` : ""}
    <div class="total-bar">${totalGroupsHtml("d", totalGroups())}</div>
    <div class="cards">
      ${card(d.room_count, "Rooms")}${card(levels.length, "Floors")}${card(crates, "Salvage crates")}
      ${card(lockers, "Footlockers")}<div class="card" id="total-card"></div>
      ${card(moduleRow?.frigate_modules == null ? "–" : `${moduleRow.frigate_modules}${moduleRow.frigate_modules_ambiguous ? " ?" : ""}`, "Frigate modules", "Predicted from crates and crew footlockers. ? means at least one container's prediction is ambiguous; yellow map markers are predicted modules, orange dashed markers are possible modules.")}
    <div class="card reward-card" id="reward-card" title="Predicted end reward of this system's own derelict found in space; derelicts summoned with a beacon use another seed and can differ."><div class="v">–</div><div class="k">Predicted end reward</div></div>
      ${card(dash(briefcases), "Briefcases", "R_ABAND_CASE: units, nanites, salvage. Part of the total only when ticked under Total counts." + (extras ? "" : " Not known for this layout."))}
      ${card(dash(tallLockers), "Tall lockers", "R_ABAND_LOCK: curios, ammo, tech. Part of the total only when ticked under Total counts." + (extras ? "" : " Not known for this layout."))}
      ${card(d.instance_count, "Scene pieces")}
      ${HT ? `${card(HT.turrets, "Turrets", "Ceiling turrets placed in the layout")}${card(HT.spawners, "Enemy spawners", "Floater, fast floater and drone spawners")}
        ${card(HT.sacs, "Bug sacs", "Hanging and pillar sacs; each releases 6-8 bugs at Normal difficulty")}
        ${card(HT.creaturesHi ? `${HT.creaturesLo}–${HT.creaturesHi}` : "0", "Creatures (Normal)", "Creatures released by all spawners and sacs at the Normal difficulty column. The layout fixes where the spawners are; how many creatures appear (and when) is decided at run time, so this is a range, and bugs only come out of sacs that burst or are shot.")}` : ""}
    </div>
    <h2>Floor maps</h2>
    <div class="layers">
      <label><input id="lay-extras" type="checkbox"${layers.extras ? " checked" : ""}> Briefcases &amp; tall lockers</label>
      ${hazards ? `<label><input id="lay-hazards" type="checkbox"${layers.hazards ? " checked" : ""}> Enemies &amp; turrets</label>
      <label><input id="lay-barrels" type="checkbox"${layers.barrels ? " checked" : ""}> Barrels</label>` : ""}
    </div>
    ${cmp ? `<div class="fmt-bar" role="group" aria-label="Map data format (experimental)"><b>Map data (experimental):</b>
      <span class="fmt-switch">${[["old", "Old"], ["new", "New"], ["both", "Side by side"]].map(([k, label]) =>
        `<button type="button" data-fmt="${k}" class="${fmt === k ? "on" : ""}"${!cmp.neu && k !== "old" ? " disabled" : ""}>${label}</button>`).join("")}</span>
      <span>Old (format 3) <b>${cmp.bytes.old ?? "?"} B</b> · New (compact format 4) <b>${cmp.bytes.neu ?? "?"} B</b>${cmp.bytes.old && cmp.bytes.neu ? ` (${Math.round(100 * cmp.bytes.neu / cmp.bytes.old)}%)` : ""} gzip for this system</span>
      <span class="${cmp.same ? "fmt-ok" : "error"}" title="Decoded derelicts compared in this browser: rooms, every placed piece, crates and footlockers (with orientation), briefcases and tall lockers">${cmp.same ? "identical ✓" : `differs ✗${cmp.error ? ": " + esc(cmp.error) : ""}`}</span>
      ${fmt === "new" ? `<span class="muted">The whole page is drawn from the compact data.</span>` : fmt === "both" ? `<span class="muted">Cards, 3D view and room table use Old.</span>` : ""}</div>` : ""}
    ${mapSets.length > 1 ? `<div class="fmt-compare">` : ""}${mapSets.map(([label, what, bytes, K]) => `${label ? `<div class="fmt-col"><h3 class="fmt-h">${label} <span class="muted">· ${what} · ${bytes ?? "?"} B</span></h3>` : ""}
    <div class="maps${layers.extras ? "" : " no-extras"}${layers.hazards ? "" : " no-hazards"}${layers.barrels ? "" : " no-barrels"}">${levels.map((y) => floorSvg(y, K)).join("")}</div>${label ? "</div>" : ""}`).join("")}${mapSets.length > 1 ? "</div>" : ""}
    <div class="legend">
      ${["cargo", "barracks", "medical", "end", "hangar"].map((k) => `<span><span class="dot" style="background:var(--${k})"></span>${k[0].toUpperCase() + k.slice(1)}</span>`).join("")}
      <span><span class="dot" style="background:var(--crate);border:1px solid var(--crate-edge)"></span>Salvage crate</span>
      <span><span class="dot" style="background:var(--locker);border:2px solid var(--crate);border-radius:50%"></span>Footlocker</span>
      <span class="lg-extra" title="${esc(MARK_TIPS.b.replace(/<[^>]+>/g, ""))}"><span class="dot" style="background:var(--briefcase);width:11px;height:6px"></span>Briefcase</span>
      <span class="lg-extra" title="${esc(MARK_TIPS.t.replace(/<[^>]+>/g, ""))}"><span class="dot" style="background:var(--tall);width:6px;height:12px"></span>Tall locker</span>
      ${hazards ? `<span class="lg-hazard" title="Floater spawner: 1-2 floaters"><span class="mk-dot" style="border:2px solid var(--floater);border-radius:50%;background:#a77bff44">F</span>Floater spawner</span>
      <span class="lg-hazard" title="Fast floater spawner: 1-2 small fast floaters"><span class="mk-dot" style="border:2px solid var(--fastfloater);border-radius:50%;background:#d4bcff44">f</span>Fast floater spawner</span>
      <span class="lg-hazard" title="Drone spawner: 2-3 mini drones"><span class="mk-dot" style="border:2px solid var(--drone);transform:rotate(45deg);"><i style="transform:rotate(-45deg)">D</i></span>Drone spawner</span>
      <span class="lg-hazard" title="Ceiling turret (deploys when it detects you)"><span class="mk-tri"></span>Turret (ceiling)</span>
      <span class="lg-hazard" title="Hanging sac: bursts into 6-8 biological horrors (Normal)"><span class="mk-dot" style="background:var(--sac);border-radius:50% 50% 50% 50%/65% 65% 35% 35%;width:9px;height:12px"></span>Bug sac (hanging)</span>
      <span class="lg-hazard" title="Pillar sac: 6-8 biological horrors (Normal)"><span class="mk-dot" style="background:var(--pillar);border-radius:5px;width:7px;height:14px"></span>Bug sac (pillar)</span>
      <span class="lg-barrel" title="Explosive barrel"><b style="color:var(--barrel)">✕</b> Barrel</span>` : ""}
      <span><b style="color:var(--accent)">↓2</b> stairs down to deck 2 (lines connect both ends) · ▲ entrance</span>
      <span><span class="dot" style="background:var(--accent)"></span>door (main path)</span>
      <span><span class="dot" style="background:var(--branch)"></span>door (branch)</span>
      <span><span class="dot" style="background:#7bd36b"></span>slime door</span>
      <span><span class="dot" style="background:#2b313a;border:1px solid #556"></span>fixture (not walkable)</span>
    </div>
    <p class="note">Top-down as seen in-game, entrance at the bottom; one grid square is 8 layout units. Room shapes are the generator's
      occupied grid cells for each room; a room spanning two floors appears on both. Crate and footlocker positions are the generator's exact positions.
      Briefcases and tall lockers come from the same placed scenes (same transform as the crates; not checked in-game yet).
      ${hazards ? "Enemy spawners, turrets and sacs are placed pieces too; how many creatures they release is decided at run time (ranges at Normal difficulty), and turrets deploy when they detect you." : ""}
      ${outside ? `<span class="error">${outside} container(s) are not on a cell of their room; the map may be off for this derelict.</span>` : "Every container lies inside its room."}</p>
    <h2>3D view</h2>
    <div class="view3d-bar">
      ${levels.map((y) => `<label><input type="checkbox" class="deck-toggle" value="${y}" checked> Deck ${deckNo(y)}</label>`).join("")}
      <label>Deck spacing <input id="spread" type="range" min="1" max="4" step="0.1" value="1.6"></label>
      <label title="Experimental: the game's own meshes for each placed piece (coarsest detail, structure only)"><input id="geom" type="checkbox" disabled> Game meshes (experimental)</label>
      <label>Cut height <input id="cut" type="range" min="0.15" max="1.05" step="0.05" value="0.6" disabled></label>
      <span id="geom-status" class="muted"></span>
      <button id="reset-3d" type="button">Reset view</button>
      <button id="walk-3d" type="button" title="Enter first-person fullscreen; use the touch controls on mobile. Esc or Leave exits." disabled>Walk inside</button>
      <span class="muted">Drag to rotate · right-drag to pan · wheel to zoom</span>
    </div>
    <div class="view3d-layers" id="layers3d" role="group" aria-label="Map and 3D layers"><b>Map and 3D layers:</b></div>
    <div id="view3d" class="view3d"></div>
    <p class="note">Rooms: light floors and darker walls in the room's colour, walls at the room height (4 units; decks are 8 apart).
      Walls follow the game's real outline (alcoves, wall bumps, pillars) once the piece data has loaded.
      Doors are framed openings (cyan main path, orange branch, green slime-covered). Stairwells are holes in the upper deck with
      a ladder down; dark blocks are fixtures (worktops, shelving, machinery; from the props' bounding boxes) you cannot walk through.
      Hangars get a simple stand-in ship. Crates (blue box, light lid band), footlockers (low long grey box, blue lid), briefcases (flat grey slab,
      black handle) and tall lockers (upright dark cabinet, blue doors) sit at their exact generated heights. Their colours are the dominant colours of the
      game's own textures for those props (the three loot containers share the game's blue/grey trim sheet, so shape tells them apart). Enemies and turrets:
      violet spheres are floater spawners, dark diamonds with a pink core drone spawners, grey ceiling mounts with an orange glow strip turrets, olive blobs bug
      spawners, brown teardrops and columns bug sacs, pink eggs fiend eggs; hover any marker for details. Props that are drawn as their own object (tall
      lockers, barrels) are no longer also drawn as dark fixture blocks. Every layer has its own checkbox. <b>Walk inside</b> opens the 3D view fullscreen
      and puts you at eye height (1.7 m) at the entrance: mouse to look, WASD to walk, Shift to run, Space/E and Q/C to climb a ladder when you stand in a stairwell.
      On touchscreens, drag the left joystick to walk, drag the right side to look, and tap Up or Down at a ladder. Use Leave or Esc to return.
      <b>Game meshes (experimental)</b> draws the game's own coarse meshes instead (floors light, walls darker); <b>Cut height</b> clips them per deck.
      Floor shaping inside rooms (raised or sunken sections) is not decoded yet.</p>
    <h2>Rooms</h2>
    <div class="table-wrap"><table><thead><tr><th class="num">#</th><th>Type</th><th>Template</th><th class="num">Crates</th>
      <th class="num">Footlockers</th><th class="num" title="Not part of the crate/locker total">Briefcases</th>
      <th class="num" title="Not part of the crate/locker total">Tall lockers</th><th title="T turret, F floater spawner, f fast floater spawner, D drone spawner, S hanging sac, P pillar sac, X barrel; hover for creature counts (Normal, run-time range)">Enemies &amp; turrets</th><th class="num">Pieces</th><th>Floors</th><th>Notes</th></tr></thead><tbody id="room-rows">
      ${rooms.map((r) => `<tr data-r="${r.room_index}"><td class="num">${r.room_index}</td>
        <td><span class="dot" style="background:${r.info.color}"></span>${esc(r.info.label)}</td><td class="mono">${esc(r.template_name)}</td>
        <td class="num">${r.crates}</td><td class="num">${r.lockers}</td><td class="num">${extras ? r.briefcases : "–"}</td><td class="num">${extras ? r.tallLockers : "–"}</td>
        <td class="mono" title="${esc(hazards ? hzTitle(r) : "")}">${hazards ? esc(hzBadge(r)) || '<span class="muted">·</span>' : "–"}</td><td class="num">${r.instance_count}</td>
        <td>${r.levels.map((y) => levels.indexOf(y) + 1).join(", ")}</td><td>${[...links.filter((l) => l.room === r.room_index).map((l) => `stairs deck ${deckNo(l.upper)}↔${deckNo(l.lower)}`),
          r.hangarPieces ? "hangar" : "", r.room_index === 0 ? "start" : ""].filter(Boolean).join(", ")}</td></tr>`).join("")}
    </tbody></table></div>
    <p class="note">${esc(d.notes || "")}</p>`;

  const tGroups = totalGroups();
  const fillTotal = () => {
    const t = totalOf({ salvage_crates: crates, footlockers: lockers, briefcases, tall_lockers: tallLockers }, tGroups);
    const el = document.getElementById("total-card");
    el.title = `Total of: ${totalNames(tGroups)}. Change it with Total counts above. ${totalTip(t)}`.trim();
    el.innerHTML = `<div class="v">${totalText(t)}</div><div class="k">Total: ${totalNames(tGroups)}</div>`;
  };
  fillTotal();
  fillReward(address);
  wireDone(d.address);
  DvShare.wire(shareCtx);
  wireTotalGroups("d", tGroups, () => { saveTotalGroups(tGroups); fillTotal(); });
  function card(v, k, title) { return `<div class="card"${title ? ` title="${esc(title)}"` : ""}><div class="v">${v}</div><div class="k">${k}</div></div>`; }
  function roomCounts(r) {
    return `${r.crates} crates, ${r.lockers} footlockers` + (extras ? `, ${r.briefcases} briefcases, ${r.tallLockers} tall lockers` : "")
      + (hazards && hzBadge(r) ? `<br>${esc(hzTitle(r))}` : "");
  }
  function floorName(y) { const i = levels.indexOf(y); return i === 0 ? "Deck 1 (top)" : `Deck ${i + 1}`; }

  function floorSvg(y, K) {
    const { rooms, containers, extras, hazards, doors, links, e } = K;  // one map data set (mapCtx), see mapSets
    const N = 13, pad = 0.6;
    const sy = (v) => N - v;  // entrance (z = 0) at the bottom
    const sx = (u) => N - u;  // NMS is right-handed (Y up): seen from above with +Z up the screen, +X points left
    let s = `<div class="map" data-level="${y}"><h3>${floorName(y)}${y === e[1] ? " · entrance" : ""}</h3>
      <svg viewBox="${-pad} ${-pad} ${N + 2 * pad} ${N + 2 * pad}" role="img" aria-label="${floorName(y)} map">`;
    for (let k = 0; k <= N; k++) s += `<line class="grid-line" x1="${k}" y1="0" x2="${k}" y2="${N}"/><line class="grid-line" x1="0" y1="${k}" x2="${N}" y2="${k}"/>`;
    for (const r of rooms) {
      const cells = r.cells.filter((c) => c.y === y);
      if (!cells.length) continue;
      // cell (x, z) covers screen x sx(x+1)..sx(x) and screen y sy(z+1)..sy(z)
      for (const c of cells) {
        s += `<rect class="room-rect" data-r="${r.room_index}" x="${sx(c.x + 1)}" y="${sy(c.z + 1)}" width="1" height="1" fill="${r.info.color}" fill-opacity="0.2"/>`;
      }
      // outline: cell edges whose neighbour on this floor is not in the room, inset slightly so touching rooms stay distinct
      const k = 0.05;
      for (const c of cells) {
        const L = sx(c.x + 1), R = sx(c.x), T = sy(c.z + 1), B = sy(c.z);
        const has = (dx, dz) => r.cellSet.has(cellKey(c.x + dx, y, c.z + dz));
        const edge = (x1, y1, x2, y2) => `<line class="room-edge" data-r="${r.room_index}" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${r.info.color}"/>`;
        if (!has(0, 1)) s += edge(has(1, 0) ? L : L + k, T + k, has(-1, 0) ? R : R - k, T + k);  // +z neighbour is above
        if (!has(0, -1)) s += edge(has(1, 0) ? L : L + k, B - k, has(-1, 0) ? R : R - k, B - k);
        if (!has(1, 0)) s += edge(L + k, has(0, 1) ? T : T + k, L + k, has(0, -1) ? B : B - k);  // +x neighbour is to the left
        if (!has(-1, 0)) s += edge(R - k, has(0, 1) ? T : T + k, R - k, has(0, -1) ? B : B - k);
      }
      const top = cells.reduce((a, c) => (c.z > a.z || (c.z === a.z && c.x > a.x) ? c : a));  // top-left on screen
      s += `<text class="room-label" x="${sx(top.x + 1) + 0.18}" y="${sy(top.z + 1) + 0.58}">${r.room_index}</text>`;
    }
    let containerMarks = "";
    for (const [containerIndex, c] of containers.entries()) {
      if (c.g.level !== y) continue;
      const cx = sx(c.g.u), cy = sy(c.g.v), crate = c.container_kind === "salvage_crate";
      const moduleMark = moduleIds.has(containerIndex), possibleMark = !moduleMark && possibleModuleIds.has(containerIndex);
      const mark = moduleMark || possibleMark ? `<circle cx="${cx}" cy="${cy}" r="0.19" fill="none" stroke="${moduleMark ? "#ffd34e" : "#ff9b42"}" stroke-width=".06" stroke-dasharray="${possibleMark ? ".08 .05" : "none"}" pointer-events="none"><title>${moduleMark ? "Predicted Salvaged Frigate Module" : "Possible Salvaged Frigate Module (ambiguous prediction)"}</title></circle>` : "";
      const icon = crate
        ? `<rect x="${cx - 0.11}" y="${cy - 0.11}" width="0.22" height="0.22" fill="var(--crate)" stroke="var(--crate-edge)" stroke-width=".025" pointer-events="none"/>`
        : `<circle cx="${cx}" cy="${cy}" r="0.12" fill="var(--locker)" stroke="var(--crate)" stroke-width=".05" pointer-events="none"/>`;
      containerMarks += `<g class="layer-${crate ? "crates" : "footlockers"}">${mark}${icon}</g>`;
    }
    for (const c of extras || []) {
      if (c.g.level !== y) continue;
      const cx = sx(c.g.u), cy = sy(c.g.v), tall = c.container_kind === "tall_locker";
      s += `<g class="mk mk-extra layer-${tall ? "tallLockers" : "briefcases"}" data-mk="${tall ? "t" : "b"}" data-room="${c.room_index}">` + (tall
        ? `<rect x="${cx - 0.05}" y="${cy - 0.12}" width="0.1" height="0.24" rx="0.02" fill="var(--tall)" stroke="var(--tall-edge)" stroke-width=".025"/>`
        : `<rect x="${cx - 0.1}" y="${cy - 0.055}" width="0.2" height="0.11" rx="0.02" fill="var(--briefcase)" stroke="var(--briefcase-edge)" stroke-width=".02"/>`) + `</g>`;
    }
    for (const h of hazards || []) {
      if (h.g.level !== y) continue;
      const cx = sx(h.g.u), cy = sy(h.g.v), c = h.code;
      const letter = (r, col, ch, fs) => `<circle cx="${cx}" cy="${cy}" r="${r}" fill="${col}" fill-opacity=".3" stroke="${col}" stroke-width=".04"/><text class="mk-letter" x="${cx}" y="${cy + fs * 0.35}" font-size="${fs}">${ch}</text>`;
      const shape = c === "F" ? letter(0.13, "var(--floater)", "F", 0.2) : c === "f" ? letter(0.09, "var(--fastfloater)", "f", 0.15)
        : c === "D" ? `<polygon points="${cx},${cy - 0.15} ${cx + 0.15},${cy} ${cx},${cy + 0.15} ${cx - 0.15},${cy}" fill="var(--drone)" fill-opacity=".3" stroke="var(--drone)" stroke-width=".04"/><text class="mk-letter" x="${cx}" y="${cy + 0.07}" font-size=".2">D</text>`
        : c === "T" ? `<polygon points="${cx - 0.13},${cy - 0.1} ${cx + 0.13},${cy - 0.1} ${cx},${cy + 0.13}" fill="var(--turret)" stroke="var(--turret-edge)" stroke-width=".03"/>`
        : c === "S" ? `<path d="M ${cx} ${cy - 0.15} C ${cx + 0.15} ${cy - 0.02} ${cx + 0.13} ${cy + 0.13} ${cx} ${cy + 0.13} C ${cx - 0.13} ${cy + 0.13} ${cx - 0.15} ${cy - 0.02} ${cx} ${cy - 0.15} Z" fill="var(--sac)" stroke="var(--sac-edge)" stroke-width=".02"/>`
        : c === "P" ? `<rect x="${cx - 0.07}" y="${cy - 0.16}" width="0.14" height="0.32" rx="0.07" fill="var(--pillar)" stroke="var(--sac-edge)" stroke-width=".02"/>`
        : c === "X" ? `<path d="M ${cx - 0.08} ${cy - 0.08} L ${cx + 0.08} ${cy + 0.08} M ${cx + 0.08} ${cy - 0.08} L ${cx - 0.08} ${cy + 0.08}" stroke="var(--barrel)" stroke-width=".07" stroke-linecap="round"/>`
        : c === "B" ? letter(0.1, "var(--bug)", "B", 0.16) : c === "E" ? letter(0.1, "var(--egg)", "E", 0.16)
        : letter(0.1, "var(--drone)", c, 0.16);
      const layerKey = ({ T: "turret", F: "floater", f: "fastFloater", D: "drone", B: "bugSpawner", S: "hangSac", P: "pillarSac", E: "egg", X: "barrel" })[c];
      s += `<g class="mk ${c === "X" ? "mk-barrel" : "mk-hazard"} layer-${layerKey}" data-mk="${c}" data-room="${h.room_index}">${shape}</g>`;
    }
    for (const dr of doors) {
      if (dr.level !== y) continue;
      const ex = (dr.a.x + dr.b.x) / 2 + 0.5, ez = (dr.a.z + dr.b.z) / 2 + 0.5, h = 0.28;
      const [x1, y1, x2, y2] = dr.nx ? [sx(ex), sy(ez - h), sx(ex), sy(ez + h)] : [sx(ex - h), sy(ez), sx(ex + h), sy(ez)];
      s += `<line class="door door-${dr.slime ? "slime" : dr.kind}" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}"><title>Door${dr.kind === "branch" ? " (branch)" : " (main path)"}${dr.slime ? ", slime-covered" : ""}: room ${dr.rooms.join(" ↔ ")}</title></line>`;
    }
    s += `<g class="walls" data-level="${y}"></g><g class="fixtures" data-level="${y}"></g>`;
    for (const l of links) {
      if (l.upper !== y && l.lower !== y) continue;
      const down = l.upper === y;
      const mx = sx(l.mark.x + 0.5), my = sy(l.mark.z + 0.5);
      s += `<g class="link-mark" data-link="${l.id}" data-end="${down ? "upper" : "lower"}">
        <rect x="${mx - 0.42}" y="${my - 0.3}" width="0.84" height="0.6" rx="0.12"/>
        <text x="${mx}" y="${my + 0.17}" text-anchor="middle">${down ? "↓" : "↑"}${deckNo(down ? l.lower : l.upper)}</text></g>`;
    }
    if (y === e[1]) s += `<path class="entrance-mark" d="M ${sx(e[0] + 0.5)} ${sy(e[2]) - 0.15} l -0.35 0.5 l 0.7 0 z" fill="var(--accent)"/>`;
    // Keep loot containers above rooms, fixtures, doors, hazards and stair markers.
    s += containerMarks;
    return s + `</svg></div>`;
  }

  // Connector lines between the two ends of each stair link, drawn over the maps (redrawn on resize). One ".maps" per
  // map data set (two when comparing formats side by side), each with its own overlay.
  const mapsEls = [...app.querySelectorAll(".maps")];
  const linkResize = new ResizeObserver((entries) => { for (const en of entries) en.target.dvDrawLinks?.(); });
  mapsEls.forEach((mapsEl, k) => {
    const K = mapSets[k][3];
    const overlay = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    overlay.classList.add("link-overlay");
    mapsEl.appendChild(overlay);
    mapsEl.dvDrawLinks = () => {
      const box = mapsEl.getBoundingClientRect();
      overlay.setAttribute("width", box.width);
      overlay.setAttribute("height", box.height);
      let out = `<defs><marker id="arrow${k}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
        <path d="M0 0 L10 5 L0 10 z" fill="var(--accent)"/></marker></defs>`;
      for (const l of K.links) {
        const a = mapsEl.querySelector(`.link-mark[data-link="${l.id}"][data-end="upper"] rect`);
        const b = mapsEl.querySelector(`.link-mark[data-link="${l.id}"][data-end="lower"] rect`);
        if (!a || !b) continue;
        const ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
        const x1 = ra.left + ra.width / 2 - box.left, y1 = ra.top + ra.height / 2 - box.top;
        const x2 = rb.left + rb.width / 2 - box.left, y2 = rb.top + rb.height / 2 - box.top;
        const bend = Math.max(30, Math.abs(x2 - x1) * 0.15);
        out += `<path class="link-line" data-link="${l.id}" d="M ${x1} ${y1} C ${x1} ${y1 - bend}, ${x2} ${y2 - bend}, ${x2} ${y2}" marker-end="url(#arrow${k})"/>`;
      }
      overlay.innerHTML = out;
    };
    // marker hover on the maps (markers are inside the SVG; the room under them still highlights through its own rect)
    mapsEl.addEventListener("mousemove", (ev) => {
      const mk = ev.target.closest && ev.target.closest(".mk");
      if (mk) showTip(ev, markTip(mk.dataset.mk, Number(mk.dataset.room)));
    });
    mapsEl.addEventListener("mouseout", (ev) => { if (ev.target.closest && ev.target.closest(".mk")) hideTip(); });
    linkResize.observe(mapsEl);
    for (const m of mapsEl.querySelectorAll(".link-mark")) {
      const l = K.links[Number(m.dataset.link)], r = K.byIndex.get(l.room);
      m.onmouseenter = () => overlay.querySelector(`.link-line[data-link="${m.dataset.link}"]`)?.classList.add("hot");
      m.onmouseleave = () => { overlay.querySelector(`.link-line[data-link="${m.dataset.link}"]`)?.classList.remove("hot"); hideTip(); };
      m.onmousemove = (ev) => showTip(ev, `<b>Stairs</b> in room ${r.room_index} (${esc(r.info.label)})<br>Deck ${deckNo(l.upper)} ↔ Deck ${deckNo(l.lower)}`);
    }
  });
  const applyLayers = () => {
    store("layers", layers);
    for (const mapsEl of mapsEls) {
      mapsEl.classList.toggle("no-extras", !layers.extras);
      mapsEl.classList.toggle("no-hazards", !layers.hazards);
      mapsEl.classList.toggle("no-barrels", !layers.barrels);
    }
    for (const el of app.querySelectorAll(".lg-extra")) el.hidden = !layers.extras;
    for (const el of app.querySelectorAll(".lg-hazard")) el.hidden = !layers.hazards;
    for (const el of app.querySelectorAll(".lg-barrel")) el.hidden = !layers.barrels;
  };
  for (const [id, key] of [["lay-extras", "extras"], ["lay-hazards", "hazards"], ["lay-barrels", "barrels"]]) {
    const el = document.getElementById(id);
    if (el) el.onchange = () => { layers[key] = el.checked; applyLayers(); };
  }
  // map data switch (experimental): remembered in this browser, page redrawn at the same scroll position
  for (const b of app.querySelectorAll(".fmt-switch button")) {
    b.onclick = async () => {
      if (b.dataset.fmt === fmt) return;
      store("mapFmt", b.dataset.fmt);
      if (urlFmt) { const q = new URLSearchParams(location.search); q.delete("fmt"); history.replaceState(null, "", `${location.pathname}${q.size ? "?" + q : ""}${location.hash}`); }
      const y = window.scrollY;
      if (viewCleanup) { viewCleanup(); viewCleanup = null; }
      await derelictView(address);
      window.scrollTo(0, y);
    };
  }

  // 3D view (loaded on demand; needs WebGL)
  const model3d = {
    rooms, links, entrance: e, doors, fixtures: M.fixtures || [], walls: M.walls || undefined,
    instances: got.local ? got.local.instances.map((i) => ({ scene: i.scene_resource.toUpperCase(), axes: i.source_axes, t: i.translation,
      room: i.room_index, level: Math.round(i.translation[1] / 8) + e[1] })) : [],
    // rot: [RotX, RotY, RotZ] degrees (model.js; null = unknown, drawn upright)
    containers: containers.map((c, id) => ({ id, kind: c.container_kind, module: moduleIds.has(id), modulePossible: possibleModuleIds.has(id), u: c.g.u, v: c.g.v, level: c.g.level, room: c.room_index,
      h: Math.max(0, c.layout_local_xyz[1] / 8 + e[1] - c.g.level), rot: c.orientation || null })),
    extras: (extras || []).map((c) => ({ kind: c.container_kind, u: c.g.u, v: c.g.v, level: c.g.level, room: c.room_index,
      h: Math.max(0, c.layout_local_xyz[1] / 8 + e[1] - c.g.level), rot: c.orientation || null })),
    hazards: (hazards || []).map((c) => ({ code: c.code, kind: c.kind, group: c.group, mount: c.mount, room: c.room_index, u: c.g.u, v: c.g.v, level: c.g.level,
      h: Math.max(0, c.xyz[1] / 8 + e[1] - c.g.level) })),
  };
  mapsEls.forEach((el, k) => { const K = mapSets[k][3]; if (K.walls) drawWalls2d(K.walls, el, K.byIndex); });
  const walkBtn = document.getElementById("walk-3d");
  applyLayers();
  mapsEls.forEach((el, k) => { const K = mapSets[k][3]; if (K.fixtures) drawFixtures2d(K.fixtures, el); });
  import("./view3d.js").then((m) => {
    if (!document.getElementById("view3d")) return;  // navigated away meanwhile
    view3d = m.mount(document.getElementById("view3d"), model3d, {
      onHover: (hit, ev) => {
        if (!hit) return hideTip();
        if (hit.marker) {
          const m = hit.marker;
          return showTip(ev, markTip(m.container ? (m.container === "salvage_crate" ? "c" : "l") : m.extra ? (m.extra === "tall_locker" ? "t" : "b") : m.hazard.code, m.room));
        }
        if (hit.door) return showTip(ev, `<b>Door</b> ${hit.door.kind === "branch" ? "(branch)" : "(main path)"}${hit.door.slime ? ", slime-covered" : ""}<br>room ${hit.door.rooms.join(" ↔ ")}`);
        const r = byIndex.get(hit.room);
        if (!r) return hideTip();
        if (hit.fixture) return showTip(ev, `<b>Fixture</b> in room ${r.room_index} (${esc(r.info.label)}): not walkable`);
        showTip(ev, hit.link ? `<b>Stairs</b> in room ${r.room_index} · Deck ${deckNo(hit.link.upper)} ↔ Deck ${deckNo(hit.link.lower)}`
          : `<b>Room ${r.room_index}</b> · ${esc(r.info.label)}<br>${roomCounts(r)}`);
      },
      onFirstPerson: (on) => { walkBtn.textContent = on ? "Leave (Esc)" : "Walk inside"; },
    });
    document.getElementById("view3d").dvView = view3d;  // handle for the automated checks (DevTools)
    walkBtn.disabled = false;
    walkBtn.onclick = () => { if (view3d.firstPerson().active) view3d.exitFirstPerson(); else view3d.enterFirstPerson(); };
    // one checkbox per layer, remembered in this browser
    const layers3d = Object.assign({}, store("layers3d") || {});
    const layerBox = document.getElementById("layers3d");
    layerBox.insertAdjacentHTML("beforeend", m.LAYERS.map(([k, label]) =>
      `<label><input type="checkbox" data-layer="${k}"${(m.DEFAULT_OFF.has(k) ? layers3d[k] === true : layers3d[k] !== false) ? " checked" : ""}> ${esc(label)}</label>`).join(""));
    const applyMapLayers = () => {
      for (const [key] of m.LAYERS) for (const mapsEl of mapsEls) mapsEl.classList.toggle(`no-layer-${key}`, layers3d[key] === false);
    };
    layerBox.onchange = (ev) => {
      const k = ev.target.dataset.layer;
      if (!k) return;
      layers3d[k] = ev.target.checked;
      store("layers3d", layers3d);
      applyMapLayers();
      view3d.setOptions({ layers: { ...layers3d } });
    };
    applyMapLayers();
    view3d.setOptions({ layers: { ...layers3d } });
    const deckSet = () => new Set([...app.querySelectorAll(".deck-toggle")].filter((c) => c.checked).map((c) => Number(c.value)));
    for (const cb of app.querySelectorAll(".deck-toggle")) cb.onchange = () => view3d.setOptions({ visibleLevels: deckSet() });
    document.getElementById("spread").oninput = (ev) => view3d.setOptions({ spread: Number(ev.target.value) });
    document.getElementById("reset-3d").onclick = () => view3d.resetView();
    const geomBox = document.getElementById("geom"), cut = document.getElementById("cut"), status = document.getElementById("geom-status");
    if (!got.local) { status.textContent = "game meshes: local viewer only"; return; }
    status.textContent = "loading room geometry…";
    m.loadMeshes(model3d.instances).then((meshes) => {
      if (!document.getElementById("geom")) return;
      if (!meshes.size) { status.textContent = "room geometry not built yet (tools/build_piece_meshes_705.py)"; return; }
      const missing = new Set(model3d.instances.map((i) => i.scene).filter((sc) => !meshes.has(sc))).size;
      status.textContent = missing ? `${missing} piece type(s) have no mesh` : "";
      geomBox.disabled = cut.disabled = false;
      view3d.setOptions({ meshes, geometry: false, cut: Number(cut.value) });
      geomBox.onchange = () => view3d.setOptions({ geometry: geomBox.checked });
      cut.oninput = () => view3d.setOptions({ cut: Number(cut.value) });
    }).catch((err) => { status.textContent = "room geometry unavailable: " + err.message; });
  }).catch((err) => {
    const el = document.getElementById("view3d");
    if (el) el.innerHTML = `<p class="error" style="padding:12px">3D view unavailable: ${esc(err.message)}</p>`;
  });
  viewCleanup = () => { linkResize.disconnect(); if (view3d) view3d.dispose(); };

  function drawWalls2d(walls, rootEl, bi) {
    const N = 13;
    for (const gEl of rootEl.querySelectorAll("g.walls")) {
      const y = Number(gEl.dataset.level);
      gEl.innerHTML = walls.filter((w) => w.level === y).map((w) => {
        const r = bi.get(w.room);
        return `<rect class="wall-px" x="${N - w.u1}" y="${N - w.v1}" width="${w.u1 - w.u0}" height="${w.v1 - w.v0}" fill="${r ? r.info.color : "#888"}"/>`;
      }).join("");
    }
  }
  function drawFixtures2d(fixtures, rootEl) {
    const N = 13;
    for (const gEl of rootEl.querySelectorAll("g.fixtures")) {
      const y = Number(gEl.dataset.level);
      gEl.innerHTML = fixtures.filter((f) => f.level === y && !f.prop).map((f) =>
        `<rect class="fixture" x="${N - f.u1}" y="${N - f.v1}" width="${f.u1 - f.u0}" height="${f.v1 - f.v0}"/>`).join("");
    }
  }

  const select = (idx) => {
    for (const el of app.querySelectorAll(".room-rect, .room-edge")) el.classList.toggle("dim", idx !== null && Number(el.dataset.r) !== idx);
    for (const tr of app.querySelectorAll("#room-rows tr")) tr.classList.toggle("sel", Number(tr.dataset.r) === idx);
  };
  let selected = null;
  for (const el of app.querySelectorAll(".room-rect")) {
    const r = byIndex.get(Number(el.dataset.r));
    el.onmousemove = (ev) => showTip(ev, `<b>Room ${r.room_index}</b> · ${esc(r.info.label)}<br><span class="mono">${esc(r.template_name)}</span><br>
      ${roomCounts(r)} · ${r.instance_count} pieces${r.stairs ? ` · ${r.stairs} stair piece(s)` : ""}`);
    el.onmouseleave = hideTip;
    el.onclick = () => { selected = selected === r.room_index ? null : r.room_index; select(selected); };
  }
  for (const tr of app.querySelectorAll("#room-rows tr")) {
    tr.onclick = () => { const i = Number(tr.dataset.r); selected = selected === i ? null : i; select(selected); };
  }
}

// ---------------------------------------------------------------- generation

async function generate(input, glyphs, galaxy, statusEl, button) {
  statusEl.textContent = "Generating… usually a few seconds";
  statusEl.className = "muted";
  if (button) button.disabled = true;
  try {
    const res = await api("/api/generate", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ input, glyphs, galaxy }) });
    statusEl.textContent = res.cached ? "Already generated" : "Done";
    if (location.hash === `#/d/${res.address}`) route(); else location.hash = `#/d/${res.address}`;
  } catch (e) {
    statusEl.textContent = e.message;
    statusEl.className = "error";
  } finally {
    if (button) button.disabled = false;
  }
}

document.getElementById("gen-form").onsubmit = (ev) => {
  ev.preventDefault();
  const text = document.getElementById("gen-input").value.toUpperCase().replace(/[\s-]/g, "");
  const status = document.getElementById("gen-status");
  if (!/^[0-9A-F]{12}$|^[0-9A-F]{16}$/.test(text)) {
    status.textContent = "Enter 12 hex digits (glyph code) or 16 (address)";
    status.className = "error";
    return;
  }
  generate(text, text.length === 12, Number(document.getElementById("gen-galaxy").value), status, ev.submitter);
};

const glyphModeEl = document.getElementById("glyph-mode");
function fillGlyphModes() {  // after serverReady: the official game icons exist only with the local server
  const opts = HAS_SERVER ? [["icons", "Icons (official)"], ["public", "Icons (public)"], ["hex", "Hex"]] : [["icons", "Icons"], ["hex", "Hex"]];
  glyphModeEl.innerHTML = opts.map(([v, n]) => `<option value="${v}">${n}</option>`).join("");
  glyphModeEl.value = opts.some(([v]) => v === glyphMode()) ? glyphMode() : "icons";
}
glyphModeEl.onchange = () => { store("glyphMode", glyphModeEl.value); route(); };

// ---------------------------------------------------------------- router

let viewCleanup = null;
function aboutView() {
  const credits = (window.DV_CREDITS || []).map((c) => `<li><b><a href="${esc(c.url)}" target="_blank" rel="noopener">${esc(c.name)}</a></b> by ${esc(c.by)}
    <span class="muted">(${esc(c.license)})</span><br>${esc(c.what)}</li>`).join("");
  app.innerHTML = `<p><a href="#/">← Atlas</a></p><h1>About and credits</h1>
    <p>Predicted derelict-freighter layouts for No Man's Sky 7.05 (Euclid galaxy), generated offline by running the game's own layout code.
      The data is the public atlas <a href="https://github.com/${ATLAS.repo}" target="_blank" rel="noopener">${ATLAS.repo}</a>.</p>
    <h2 id="credits">Credits</h2><ul class="credits">${credits}</ul>
    <h3>Links to</h3><ul class="credits">${(window.DV_LINKS_TO || []).map((c) => `<li><a href="${esc(c.url)}" target="_blank" rel="noopener noreferrer" referrerpolicy="no-referrer">${esc(c.name)}</a>
      by ${esc(c.by)} <span class="muted">(${esc(c.note)}; external, not affiliated)</span></li>`).join("")}</ul>
        <p class="note">${esc(window.DV_DISCLAIMER || "Unofficial fan project. Not affiliated with Hello Games.")}</p>`;
}

let ROUTE_READY = false;   // set once the server probe and the password gate (if any) are done
function route() {
  if (!ROUTE_READY) return;
  hideTip();
  if (viewCleanup) { viewCleanup(); viewCleanup = null; }
  const h = location.hash.slice(1) || "/";
  document.title = "Derelict Viewer";
  if (h === "/about") return aboutView();
  const m = h.match(/^\/d\/([0-9A-Fa-f]{16})$/);
  if (m) return derelictView(m[1].toUpperCase());
  const [, query = ""] = h.split("?");
  return sweepView(new URLSearchParams(query));
}
window.addEventListener("hashchange", route);
document.getElementById("foot-disc").textContent = "Unofficial fan project. Not affiliated with Hello Games.";
if (window.dvGateOn) {
  document.getElementById("foot-lock").hidden = false;
  document.getElementById("lock-link").onclick = (ev) => { ev.preventDefault(); window.dvLock(); };
}
Promise.all([serverReady, window.dvGateReady]).then(() => {
  ROUTE_READY = true;
  fillGlyphModes();
  if (!HAS_SERVER) document.getElementById("gen-form").hidden = true;  // static hosting: the Generate box can't work there
  route();
});
