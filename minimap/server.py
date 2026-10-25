"""Live derelict minimap: local server (stdlib only).

    python -I minimap/server.py [--port 8766] [--host 127.0.0.1] [--no-live]

Reads the running NMS 7.05 read-only (tools/live_position_705.py: universe address + player position; nothing is
written to or injected into the game). For the current system it prepares a card (preset, rooms, decks, container
counts, end reward) and the derelict layout, and maps the player into layout space:

    interior origin = ABAND_FREIGHTER space POI + RefDungeonEntrance + D   (no rotation;
                      research-output/END_REWARD_PREDICTION_20261020.md, section C)
    layout          = player world position - interior origin

A derelict reached another way (summoned) has no POI near it: press "I'm at the entrance" to anchor on the player.

  GET  /                      the minimap page (minimap/static/)
  GET  /api/live              {connected, address, derelict, world, layout, distance_m, anchor, ...}
  GET  /api/system[?address=] the system card; ?address=<16 hex> or ?glyphs=<12 hex> picks a system without the game
  GET  /api/derelict          derelict.json of the shown system (extra containers filled in)
  GET  /api/meshes/index      piece index for walls (D:/Orca/NMS-Derelict-Probe-analysis/meshcache/index.json)
  GET  /model.js, /piece_props.json   served read-only from viewer/static/
  POST /api/anchor            {"mode": "entrance" | "poi"}
  POST /api/select            {"input": "<12 glyph hex | 16 address hex | ''>"}  ('' = follow the game again)
  GET  /api/dev               diagnostics (versions, paths, last errors, sample rate)
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

VERSION = "0.1.0"
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

import end_reward_batch_705 as RB  # noqa: E402
import extra_containers_705 as XC  # noqa: E402
import live_position_705 as LIVE  # noqa: E402
import predict_end_reward_705 as PR  # noqa: E402

STATIC = HERE / "static"
VIEWER_STATIC = ROOT / "viewer" / "static"
ANALYSIS = Path("D:/Orca/NMS-Derelict-Probe-analysis")
MESH_INDEX = ANALYSIS / "meshcache" / "index.json"
REWARDS_CSV = ANALYSIS / "end-reward-cache" / "rewards.csv"
CACHE = ANALYSIS / "minimap-cache"
POI_CACHE = CACHE / "poi.json"
EMU_PY = PR.EMU_PY
FASTGEN = PR.FASTGEN
# layout position of the player standing just inside the entrance (live 2026-10-21 at 002F: 0.6, 1.9, 1.7;
# saved sessions 750 / 320: x 0, z 4.3); used only for the manual anchor
ENTRY_LAYOUT = (0.5, 1.85, 2.0)
SAMPLE_S = 0.2
HEX16 = re.compile(r"^[0-9A-F]{16}$")
HEX12 = re.compile(r"^[0-9A-F]{12}$")


def derelict_address(addr: str) -> str:
    """The derelict belongs to the system: zero the planet nibble (00502F.. -> 00002F..)."""
    return f"{int(addr, 16) & ~(0xF << 52):016X}"


def glyphs_of(addr: str) -> str:
    """16-hex address -> 12 portal glyph hex (planet 0): P SSS YY ZZZ XXX."""
    return "0" + addr[3:6] + addr[8:10] + addr[10:13] + addr[13:16]


def parse_input(text: str) -> str | None:
    t = (text or "").upper().replace(" ", "").replace("-", "")
    if HEX16.match(t):
        return derelict_address(t)
    if HEX12.match(t):
        return derelict_address(PR.glyphs_to_address(t))
    return None


def load_json(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1), encoding="utf-8")
    os.replace(tmp, p)


class Rewards:
    """rewards.csv (address -> name, class, ambiguous, alternatives), reloaded when the file changes."""

    def __init__(self):
        self.mtime = None
        self.rows: dict[str, dict] = {}

    def get(self, addr: str) -> dict | None:
        try:
            m = REWARDS_CSV.stat().st_mtime
        except OSError:
            return None
        if m != self.mtime:
            with REWARDS_CSV.open(encoding="utf-8", newline="") as f:
                self.rows = {r["address"].upper(): r for r in csv.DictReader(f)}
            self.mtime = m
        return self.rows.get(addr)


class System:
    """Everything the page shows for one system; prepared in a background thread."""

    def __init__(self, addr: str):
        self.address = addr
        self.status = "preparing"
        self.error = None
        self.card: dict = {"address": addr, "glyphs": glyphs_of(addr)}
        self.derelict: dict | None = None
        self.origin: list[float] | None = None  # interior origin in world space (from the POI)
        self.poi_note = None


class State:
    def __init__(self, live_enabled: bool):
        self.lock = threading.Lock()
        self.live_enabled = live_enabled
        self.reader: LIVE.LiveReader | None = None
        self.sample: dict | None = None
        self.sample_utc = None
        self.samples = 0
        self.systems: dict[str, System] = {}
        self.selected: str | None = None  # manual pick (no game needed)
        self.anchor: dict[str, list[float]] = {}  # derelict address -> manual origin
        self.rewards = Rewards()
        self.errors: list[str] = []
        self.poi_cache = load_json(POI_CACHE, {})

    def log_error(self, msg: str) -> None:
        with self.lock:
            self.errors = (self.errors + [f"{time.strftime('%H:%M:%S')} {msg}"])[-20:]

    # ---- live sampling ----
    def live_loop(self) -> None:
        while True:
            try:
                if self.reader is None:
                    try:
                        self.reader = LIVE.LiveReader()
                    except Exception:
                        self.reader = None
                        with self.lock:
                            self.sample = None
                        time.sleep(2)
                        continue
                s = self.reader.sample()
                if s is None and LIVE.find_pid() != self.reader.pid:
                    self.reader.close()
                    self.reader = None
                with self.lock:
                    self.sample = s
                    self.samples += 1
                if s and s["address"] != "0000000000000000":
                    self.system(derelict_address(s["address"]))
            except Exception as exc:  # keep sampling; record why
                self.log_error(f"live: {exc!r}")
                time.sleep(1)
            time.sleep(SAMPLE_S)

    # ---- systems ----
    def current_address(self) -> str | None:
        with self.lock:
            if self.selected:
                return self.selected
            s = self.sample
        if s and s["address"] != "0000000000000000":
            return derelict_address(s["address"])
        return None

    def system(self, addr: str) -> System:
        with self.lock:
            sysobj = self.systems.get(addr)
            if sysobj is None:
                sysobj = self.systems[addr] = System(addr)
                threading.Thread(target=self.prepare, args=(sysobj,), daemon=True).start()
            return sysobj

    def prepare(self, s: System) -> None:
        try:
            addr = s.address
            seed, preset, _ = PR.derelict_seed_preset(addr)
            s.card.update({"seed": f"{seed:016X}", "preset": preset})
            # reward: atlas cache first, else the predictor (1-10 s)
            r = self.rewards.get(addr)
            if r:
                s.card["reward"] = {"name": r["reward_name"], "class": r["reward_class"],
                                    "ambiguous": r["reward_ambiguous"] == "1",
                                    "alt": (r["reward_alt"] or "").replace("|", " or ") or None,
                                    "source": "atlas cache"}
            # layout
            d = PR.load_layout(addr)
            if not d.get("extra_containers"):
                d["extra_containers"] = XC.extra_containers(d)
            s.derelict = d
            kinds = {"salvage_crate": 0, "crew_footlocker": 0, "briefcase": 0, "tall_locker": 0}
            for c in d["containers"] + d["extra_containers"]:
                kinds[c["container_kind"]] = kinds.get(c["container_kind"], 0) + 1
            levels = set()
            for room in d["rooms"]:
                u = room["raw_u16_0x00_0x1F"]
                levels.update(range(u[1], u[4] + 1))
            s.card.update({"rooms": len(d["rooms"]), "decks": len(levels), "containers": kinds})
            s.status = "layout ready"
            # world placement of the interior (Unicorn POI step, ~8 s once per system, cached on disk)
            poi = self.poi_cache.get(addr)
            if poi is None:
                out = PR.poi_positions([addr]).get(addr, {})
                poi = {"aband_freighter": out.get("aband_freighter")}
                with self.lock:
                    self.poi_cache[addr] = poi
                    save_json(POI_CACHE, self.poi_cache)
            p = poi.get("aband_freighter")
            if p:
                s.origin = [p[k] + PR.ENTRANCE_REF[k] + PR.DUNGEON_D[k] for k in range(3)]
            else:
                s.poi_note = "this system has no derelict POI; anchor at the entrance"
            if "reward" not in s.card:
                if p:
                    # same in-game labels and alternative format as the atlas cache
                    name, cls, amb, alt = RB.result_row(PR.predict(addr, poi, d))
                    s.card["reward"] = {"name": name, "class": cls, "ambiguous": amb == "1",
                                        "alt": alt.replace("|", " or ") or None, "source": "predictor"}
                else:
                    s.card["reward"] = None
            s.status = "ready"
        except Exception as exc:
            s.status = "error"
            s.error = repr(exc)
            self.log_error(f"prepare {s.address}: {traceback.format_exc(limit=3)}")

    # ---- live view ----
    def live(self) -> dict:
        with self.lock:
            s = self.sample
            selected = self.selected
        out = {"connected": s is not None, "selected": selected, "version": VERSION}
        if s is None:
            out["note"] = ("live reading off" if not self.live_enabled else "NMS is not running" if self.reader is None
                           else "game running, waiting for a loaded save")
            return out
        out.update({"address": s["address"], "world": [s["x"], s["y"], s["z"]]})
        here = derelict_address(s["address"]) if s["address"] != "0000000000000000" else None
        out["derelict"] = here
        shown = selected or here
        out["shown"] = shown
        if shown is None or shown != here:
            out["in_shown_system"] = False
            return out
        out["in_shown_system"] = True
        sysobj = self.system(here)
        origin, anchor = self.anchor.get(here), "entrance"
        if origin is None:
            origin, anchor = sysobj.origin, "poi" if sysobj.origin else None
        out["anchor"] = anchor
        out["poi_note"] = sysobj.poi_note
        if origin:
            lay = [out["world"][k] - origin[k] for k in range(3)]
            out["layout"] = lay
            out["distance_m"] = sum(v * v for v in lay) ** 0.5
        return out

    def set_anchor(self, mode: str) -> dict:
        with self.lock:
            s = self.sample
        if not s:
            return {"ok": False, "error": "no live position"}
        here = derelict_address(s["address"])
        if mode == "poi":
            self.anchor.pop(here, None)
        else:
            self.anchor[here] = [(s["x"], s["y"], s["z"])[k] - ENTRY_LAYOUT[k] for k in range(3)]
        return {"ok": True, "anchor": mode}


STATE: State


class Handler(BaseHTTPRequestHandler):
    server_version = f"DerelictMinimap/{VERSION}"

    def log_message(self, fmt, *args):  # quiet
        pass

    def send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def json(self, obj, code: int = 200) -> None:
        self.send(code, json.dumps(obj, separators=(",", ":")).encode(), "application/json")

    def file(self, p: Path) -> None:
        types = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                 ".css": "text/css; charset=utf-8", ".json": "application/json", ".svg": "image/svg+xml"}
        if not p.is_file():
            return self.json({"error": "not found"}, 404)
        self.send(200, p.read_bytes(), types.get(p.suffix, "application/octet-stream"))

    def do_GET(self):
        path, _, query = self.path.partition("?")
        q = dict(kv.split("=", 1) for kv in query.split("&") if "=" in kv)
        if path in ("/", "/index.html"):
            return self.file(STATIC / "index.html")
        if path in ("/minimap.js", "/minimap.css"):
            return self.file(STATIC / path[1:])
        if path in ("/model.js", "/piece_props.json"):
            return self.file(VIEWER_STATIC / path[1:])
        if path == "/api/meshes/index":
            return self.file(MESH_INDEX) if MESH_INDEX.is_file() else self.json({})
        if path == "/api/live":
            return self.json(STATE.live())
        if path in ("/api/system", "/api/derelict"):
            addr = parse_input(q.get("address") or q.get("glyphs") or "") or STATE.current_address()
            if not addr:
                return self.json({"status": "no system (start NMS or pick a system)"}, 200 if path == "/api/system" else 404)
            s = STATE.system(addr)
            if path == "/api/system":
                return self.json({"status": s.status, "error": s.error, "poi_note": s.poi_note,
                                  "placed": s.origin is not None, **s.card})
            if s.derelict is None:
                return self.json({"status": s.status}, 404 if s.status == "error" else 202)
            return self.json(s.derelict)
        if path == "/api/dev":
            with STATE.lock:
                return self.json({"version": VERSION, "pid": STATE.reader.pid if STATE.reader else None,
                                  "samples": STATE.samples, "sample_s": SAMPLE_S, "live_enabled": STATE.live_enabled,
                                  "systems": {a: s.status for a, s in STATE.systems.items()},
                                  "errors": STATE.errors, "paths": {"rewards": str(REWARDS_CSV),
                                  "poi_cache": str(POI_CACHE), "mesh_index": str(MESH_INDEX)},
                                  "chain": {"app_rva": hex(LIVE.APP_RVA), "sim": hex(LIVE.DATA_SIMULATION),
                                            "ua": hex(LIVE.SIM_CURRENT_UA), "player": hex(LIVE.SIM_PLAYER),
                                            "pos": hex(LIVE.PLAYER_POSITION)}})
        return self.json({"error": "not found"}, 404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 10_000:
            return self.json({"error": "too large"}, 413)
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return self.json({"error": "bad json"}, 400)
        if self.path == "/api/anchor":
            mode = body.get("mode")
            if mode not in ("entrance", "poi"):
                return self.json({"error": "mode must be entrance or poi"}, 400)
            return self.json(STATE.set_anchor(mode))
        if self.path == "/api/select":
            text = body.get("input", "")
            addr = parse_input(text) if text else None
            if text and not addr:
                return self.json({"error": "enter 12 glyph hex digits or a 16-digit address"}, 400)
            with STATE.lock:
                STATE.selected = addr
            if addr:
                STATE.system(addr)
            return self.json({"ok": True, "selected": addr})
        return self.json({"error": "not found"}, 404)


def main(argv=None) -> int:
    global STATE
    ap = argparse.ArgumentParser(description="Live derelict minimap (local)")
    ap.add_argument("--host", default="127.0.0.1", help="0.0.0.0 to open it on a phone on the same network")
    ap.add_argument("--port", type=int, default=8766)
    ap.add_argument("--no-live", action="store_true", help="don't read the game (manual system pick only)")
    ap.add_argument("--open", action="store_true", help="open the page in the default browser")
    a = ap.parse_args(argv)
    STATE = State(live_enabled=not a.no_live)
    if not a.no_live:
        threading.Thread(target=STATE.live_loop, daemon=True).start()
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    url = f"http://{'127.0.0.1' if a.host == '0.0.0.0' else a.host}:{a.port}/"
    print(f"Derelict minimap {VERSION}: {url}", flush=True)
    if a.host == "0.0.0.0":
        import socket
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as so:
                so.connect(("192.0.2.1", 9))  # no packet is sent; picks the LAN interface
                print(f"  on your phone (same network): http://{so.getsockname()[0]}:{a.port}/", flush=True)
        except OSError:
            pass
    if a.open:
        import webbrowser
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
