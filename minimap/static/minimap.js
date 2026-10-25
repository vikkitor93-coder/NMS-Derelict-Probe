"use strict";
// Live derelict minimap. Polls /api/live (player position, read-only from the game) and draws the current system's
// derelict deck by deck with the shared viewer model (model.js build()). Screen mapping is the viewer's:
// sx(u) = 13 - u, sy(v) = 13 - v (seen from above, entrance at the bottom).
(function () {
  const M = window.DerelictModel;
  const N = 13;
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const sx = (u) => N - u, sy = (v) => N - v;
  const COLORS = ["#4e9be6", "#e6964e", "#5fbf6a", "#d0617d", "#9a7fe0", "#d7c04a", "#46b7b0", "#c9773f", "#7aa0c2",
    "#b06fb0", "#8fb34b", "#e07a6a", "#5c8fd6", "#c4a35a"];
  const PRESETS = { CARGO: "Cargo", MEDI: "Medical", BUGS: "Bugs", FLOATERS: "Floaters", TURRETS: "Turrets", SLIME: "Slime" };

  let shownAddr = null, sysCard = null, model = null, deck = null, follow = true, live = null;
  let meshIndex = null, props = null, trail = [], heading = null;

  const get = (u) => fetch(u, { cache: "no-store" }).then((r) => (r.ok || r.status === 202 ? r.json() : Promise.reject(r.status)));
  const post = (u, body) => fetch(u, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).then((r) => r.json());

  function presetLabel(p) { return (p || "").split("_").map((w) => PRESETS[w] || w).join(" · "); }

  // ---- card ----
  function renderCard(c, lv) {
    if (!c || !c.address) { $("card").innerHTML = `<p class="muted">${esc(c && c.status || "Waiting for a system…")}</p>`; return; }
    const k = c.containers || {};
    const stat = (n, label) => `<div class="stat"><b>${n ?? "…"}</b><span>${label}</span></div>`;
    let reward = `<span class="muted">end reward: ${c.status === "ready" ? "unknown for this system" : "working it out…"}</span>`;
    if (c.reward && c.reward.name) {
      reward = `<span class="cls cls-${esc(c.reward.class)}">${esc(c.reward.class)}</span><b>${esc(c.reward.name)}</b>` +
        (c.reward.ambiguous ? ` <span class="warn">(uncertain${c.reward.alt ? ": may be " + esc(c.reward.alt) : ""})</span>` : "");
    }
    let dist = "";
    if (lv && lv.in_shown_system && lv.distance_m != null && lv.distance_m > 150) {
      dist = ` · <span class="muted">derelict ${lv.distance_m >= 1000 ? (lv.distance_m / 1000).toFixed(1) + " km" : Math.round(lv.distance_m) + " m"} away</span>`;
    }
    $("card").innerHTML = `<h2><span class="mono">${esc(c.glyphs)}</span><span>${esc(presetLabel(c.preset))}</span>${dist}</h2>
      <div class="stats">${stat(k.salvage_crate, "salvage crates")}${stat(k.crew_footlocker, "footlockers")}${stat(k.briefcase, "briefcases")}${stat(k.tall_locker, "tall lockers")}${stat(c.rooms, "rooms")}${stat(c.decks, "decks")}</div>
      <div class="reward">End reward: ${reward}</div>
      ${c.status === "error" ? `<p class="warn">${esc(c.error)}</p>` : ""}
      ${c.poi_note ? `<p class="muted">${esc(c.poi_note)}</p>` : ""}`;
  }

  // ---- map ----
  function levels() { return model ? [...new Set(model.rooms.flatMap((r) => r.levels))].sort((a, b) => b - a) : []; }
  const deckNo = (y) => levels().indexOf(y) + 1;

  function renderDecks(here) {
    $("decks").innerHTML = levels().map((y) => `<button role="tab" aria-selected="${y === deck}" class="${y === here ? "here" : ""}" data-y="${y}">Deck ${deckNo(y)}</button>`).join("");
  }

  function renderMap() {
    if (!model || deck == null) { $("map").innerHTML = ""; return; }
    const y = deck, e = model.e;
    let s = `<svg viewBox="-0.3 -0.3 ${N + 0.6} ${N + 0.6}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Deck ${deckNo(y)} map">`;
    for (const r of model.rooms) {
      const col = COLORS[r.room_index % COLORS.length];
      const cells = r.cells.filter((c) => c.y === y);
      for (const c of cells) s += `<rect x="${sx(c.x + 1)}" y="${sy(c.z + 1)}" width="1" height="1" fill="${col}" fill-opacity="0.22"/>`;
      // outline: edges with no same-room neighbour
      for (const c of cells) {
        const has = (dx, dz) => r.cellSet.has(M.cellKey(c.x + dx, y, c.z + dz));
        const x0 = sx(c.x + 1), x1 = sx(c.x), y0 = sy(c.z + 1), y1 = sy(c.z);
        const L = (a, b, c2, d) => `<line x1="${a}" y1="${b}" x2="${c2}" y2="${d}" stroke="${col}" stroke-width="0.04"/>`;
        if (!has(1, 0)) s += L(x0, y0, x0, y1);
        if (!has(-1, 0)) s += L(x1, y0, x1, y1);
        if (!has(0, 1)) s += L(x0, y0, x1, y0);
        if (!has(0, -1)) s += L(x0, y1, x1, y1);
      }
      if (cells.length) {
        const cx = cells.reduce((a, c) => a + c.x, 0) / cells.length + 0.5, cz = cells.reduce((a, c) => a + c.z, 0) / cells.length + 0.5;
        s += `<text class="room-label" x="${sx(cx)}" y="${sy(cz) + 0.42}">${r.room_index}</text>`;
      }
    }
    s += `<g class="walls">`;
    for (const w of model.walls || []) {
      if (w.level !== y) continue;
      const col = COLORS[w.room % COLORS.length];
      s += `<rect x="${N - w.u1}" y="${N - w.v1}" width="${w.u1 - w.u0}" height="${w.v1 - w.v0}" fill="${col}" fill-opacity="0.85"/>`;
    }
    s += `</g>`;
    for (const dr of model.doors) {
      if (dr.level !== y) continue;
      const ex = (dr.a.x + dr.b.x) / 2 + 0.5, ez = (dr.a.z + dr.b.z) / 2 + 0.5, h = 0.28;
      const [x1, y1, x2, y2] = dr.nx ? [sx(ex), sy(ez - h), sx(ex), sy(ez + h)] : [sx(ex - h), sy(ez), sx(ex + h), sy(ez)];
      s += `<line class="door" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}"/>`;
    }
    for (const l of model.links) {
      if (l.upper !== y && l.lower !== y) continue;
      const down = l.upper === y, mx = sx(l.mark.x + 0.5), my = sy(l.mark.z + 0.5);
      s += `<g class="link"><rect x="${mx - 0.42}" y="${my - 0.3}" width="0.84" height="0.6" rx="0.12"/><text x="${mx}" y="${my + 0.12}">${down ? "↓" : "↑"}${deckNo(down ? l.lower : l.upper)}</text></g>`;
    }
    for (const c of model.containers) {
      if (c.g.level !== y) continue;
      const cx = sx(c.g.u), cy = sy(c.g.v);
      s += c.container_kind === "salvage_crate"
        ? `<rect x="${cx - 0.13}" y="${cy - 0.13}" width="0.26" height="0.26" fill="var(--crate)" stroke="var(--crate-edge)" stroke-width=".03"/>`
        : `<circle cx="${cx}" cy="${cy}" r="0.13" fill="var(--locker)" stroke="var(--crate)" stroke-width=".05"/>`;
    }
    for (const c of model.extras || []) {
      if (c.g.level !== y) continue;
      const cx = sx(c.g.u), cy = sy(c.g.v);
      s += c.container_kind === "tall_locker"
        ? `<rect x="${cx - 0.06}" y="${cy - 0.14}" width="0.12" height="0.28" rx="0.02" fill="var(--tall)" stroke="var(--tall-edge)" stroke-width=".03"/>`
        : `<rect x="${cx - 0.11}" y="${cy - 0.06}" width="0.22" height="0.12" rx="0.02" fill="var(--brief)" stroke="#0d0e0d" stroke-width=".02"/>`;
    }
    if (y === e[1]) s += `<path d="M ${sx(e[0] + 0.5)} ${sy(e[2]) - 0.15} l -0.35 0.5 l 0.7 0 z" fill="var(--accent)"/>`;
    s += `<polyline id="trail" fill="none" stroke="var(--trail)" stroke-width="0.05" stroke-opacity="0.45" points=""/>`;
    s += `<g id="me" visibility="hidden"><circle r="0.22" fill="var(--me)" stroke="var(--panel)" stroke-width="0.06"/><path id="me-dir" d="M 0 -0.5 L 0.17 -0.2 L -0.17 -0.2 Z" fill="var(--me)" visibility="hidden"/></g>`;
    $("map").innerHTML = s + `</svg>`;
    drawMe();
  }

  // player: layout metres -> grid; deck by floor height (player origin is ~1.85 m above the deck floor)
  function playerGrid(lay) {
    const e = model.e;
    return { u: lay[0] / 8 + e[0] + 0.5, v: lay[2] / 8 + e[2] + 0.5, level: Math.round((lay[1] - 1.85) / 8) + e[1] };
  }

  function roomAt(g) {
    const key = M.cellKey(Math.floor(g.u), g.level, Math.floor(g.v));
    return model.rooms.find((r) => r.cellSet.has(key)) || null;
  }

  function drawMe() {
    const me = document.getElementById("me");
    if (!me || !model) return;
    const lay = live && live.in_shown_system && live.layout;
    const g = lay ? playerGrid(lay) : null;
    const onMap = g && g.u > -1 && g.u < N + 1 && g.v > -1 && g.v < N + 1;
    if (!onMap || g.level !== deck) { me.setAttribute("visibility", "hidden"); }
    else {
      me.setAttribute("visibility", "visible");
      me.setAttribute("transform", `translate(${sx(g.u)} ${sy(g.v)})${heading != null ? ` rotate(${heading})` : ""}`);
      document.getElementById("me-dir").setAttribute("visibility", heading != null ? "visible" : "hidden");
    }
    const pts = trail.filter((t) => t.level === deck).map((t) => `${sx(t.u).toFixed(2)},${sy(t.v).toFixed(2)}`).join(" ");
    document.getElementById("trail").setAttribute("points", pts);
  }

  function updateWhere() {
    const w = $("where");
    if (!live || !live.connected) { w.textContent = live ? live.note || "" : ""; return; }
    if (!live.in_shown_system) { w.textContent = live.selected ? "Showing a picked system; you are elsewhere." : ""; return; }
    if (!live.layout) { w.textContent = model ? "Placing the derelict in space…" : ""; return; }
    if (!model) return;
    const g = playerGrid(live.layout), r = roomAt(g);
    if (r) w.innerHTML = `You: <b>Deck ${deckNo(g.level)}</b>, room ${r.room_index} <span class="muted">(${esc(r.template_name)})</span>`;
    else if (live.distance_m < 150) w.textContent = "You are at the derelict, outside the rooms (hangar, airlock or outside).";
    else w.textContent = "You are outside the derelict.";
  }

  // ---- data flow ----
  async function loadSystem(addr) {
    shownAddr = addr; model = null; trail = []; heading = null; deck = null;
    renderMap();
    sysCard = await get(`/api/system?address=${addr}`).catch(() => null);
    while (shownAddr === addr && sysCard && sysCard.status === "preparing") {
      renderCard(sysCard, live);
      await new Promise((r) => setTimeout(r, 700));
      sysCard = await get(`/api/system?address=${addr}`).catch(() => sysCard);
    }
    if (shownAddr !== addr) return;
    renderCard(sysCard, live);
    const d = await get(`/api/derelict?address=${addr}`).catch(() => null);
    if (!d || !d.rooms || shownAddr !== addr) return;
    if (meshIndex === null) meshIndex = await get("/api/meshes/index").catch(() => ({}));
    if (props === null) props = await get("/piece_props.json").then((j) => j.scenes || {}).catch(() => ({}));
    model = M.build(d, Object.keys(meshIndex).length ? meshIndex : null, Object.keys(props).length ? props : null);
    deck = levels().includes(model.e[1]) ? model.e[1] : levels()[0];
    renderDecks(null);
    renderMap();
    // keep the card's reward fresh (the POI step may finish after the layout)
    for (let i = 0; i < 40 && shownAddr === addr && sysCard.status !== "ready" && sysCard.status !== "error"; i++) {
      await new Promise((r) => setTimeout(r, 1000));
      sysCard = await get(`/api/system?address=${addr}`).catch(() => sysCard);
      renderCard(sysCard, live);
    }
  }

  async function tick() {
    try {
      live = await get("/api/live");
      $("live").textContent = live.connected ? "live" : (live.note || "offline");
      $("live").classList.toggle("on", !!live.connected);
      const want = live.selected || live.derelict || null;
      if (want && want !== shownAddr) loadSystem(want);
      if (!want && !shownAddr) renderCard({ status: live.note || "Waiting for a system…" });
      $("anchor-reset").hidden = live.anchor !== "entrance";
      if (model && live.in_shown_system && live.layout) {
        const g = playerGrid(live.layout), last = trail[trail.length - 1];
        if (!last || Math.hypot(g.u - last.u, g.v - last.v) > 0.04) {
          if (last && last.level === g.level) {
            const du = sx(g.u) - sx(last.u), dv = sy(g.v) - sy(last.v);
            heading = (Math.atan2(du, -dv) * 180) / Math.PI;
          }
          trail.push(g); if (trail.length > 600) trail.shift();
        }
        const levs = levels();
        if (follow && levs.includes(g.level) && g.level !== deck) { deck = g.level; renderMap(); }
        renderDecks(levs.includes(g.level) ? g.level : null);
      }
      drawMe();
      updateWhere();
      if (sysCard) renderCard(sysCard, live);
    } catch (err) {
      $("live").textContent = "server offline"; $("live").classList.remove("on");
    }
    setTimeout(tick, 250);
  }

  async function dev() {
    try { $("dev").textContent = JSON.stringify(await get("/api/dev"), null, 1); } catch (e) { /* ignore */ }
    setTimeout(dev, 3000);
  }

  $("decks").addEventListener("click", (ev) => {
    const b = ev.target.closest("button[data-y]"); if (!b) return;
    deck = Number(b.dataset.y); follow = false; $("follow").checked = false; renderDecks(null); renderMap();
  });
  $("follow").addEventListener("change", (ev) => { follow = ev.target.checked; });
  $("pick").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const r = await post("/api/select", { input: $("pick-input").value.trim() });
    if (r.error) alert(r.error); else if (!r.selected) shownAddr = null;
  });
  $("anchor").addEventListener("click", () => post("/api/anchor", { mode: "entrance" }).then(() => { trail = []; }));
  $("anchor-reset").addEventListener("click", () => post("/api/anchor", { mode: "poi" }).then(() => { trail = []; }));
  tick(); dev();
})();
