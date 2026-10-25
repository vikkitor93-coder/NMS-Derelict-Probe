#!/usr/bin/env python3
"""On-demand map server for the public derelict atlas site (rebuilt in stage 2 / A4 from the 2026-10-24 reports).

A deliberately tiny public API, separate from the scanner (port 8790) and the viewer servers.  Exactly three routes, all GET:

  GET /api/map/<ADDRESS16>[?wait=SECONDS]
        200  {"v":4,"t":<piece table of this map>,"s":{ADDRESS16:<compact v4 view>},"m":{summary}}
        202  {"status":"queued"|"generating", position, queue, eta_s, ... same fields as /api/status, "retry_after":n}
        400  bad input   404 no such system   429 rate limit   503 busy / timed out
  GET /api/status/<ADDRESS16>
        200  read-only progress: status idle|queued|generating|ready|failed, stage 0-4, preset, rooms, position, queue,
             running, eta_s, elapsed_s, overdue, slow, upto_s, scanner_busy, poll_ms, msg{...ready-made texts...}.
             Never starts a job, is not charged to the miss limiter.  (400 bad address, 404 unknown system.)
  GET /api/health
        200  {"ok":true,"queue":n,"running":n,"cache_entries":n,"cache_bytes":n,"clients_1min":n}

Everything else is 404, other methods 405, any request body 400.  The primary listener binds 127.0.0.1 ONLY (hard-coded in
load_config).  An OPTIONAL second listener on the PC's Tailscale address (config tailnet_bind + relay_ips, both empty = off)
serves only the listed relay peers; see start_tailnet().  Nothing here exposes the server to the internet: see EXPOSE.md.

The generator is a thin adapter (class WorkerProc + MapBuilder): the real one is tools/scan_worker_705.py driven over a JSON
line protocol; `--generator stub` uses ondemand/stub_generator.py instead (tests, and while the real generator is rebuilt).

Privacy: client keys (CF-Connecting-IP / X-Forwarded-For when the peer is the local tunnel, X-Relay-Client when the peer is a
listed relay, else the peer address) live only in memory as salted hashes in the rate limiter; they are never written to
disk or logs.  The log holds aggregate counts only (no IPs, no user agents, no addresses).
"""
from __future__ import annotations

import argparse
import collections
import gzip
import hashlib
import hmac
import ipaddress
import json
import math
import os
import queue
import re
import secrets
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

HERE = Path(__file__).resolve().parent
TOOLS = Path("D:/Orca/NMS-Derelict-Probe/tools")
FASTGEN = Path("D:/Orca/NMS-Derelict-Probe-fastgen")
sys.path.insert(0, str(TOOLS))
if str(HERE) not in sys.path:          # python -I does not add the script folder; stub_generator lives next to this file
    sys.path.append(str(HERE))

CACHE_VERSION = 1
ADDR_RE = re.compile(r"^000([0-9A-F]{3})00([0-9A-F]{8})$")   # 000 SSS GG(=00, galaxy 0) YY ZZZ XXX
RELAY_KEY_RE = re.compile(r"^[0-9a-f]{18}$")
NO_CACHE = "no-store"
IS_WIN = sys.platform == "win32"

DEFAULTS = {
    "host": "127.0.0.1",          # fixed: loopback only (see load_config)
    "port": 8791,
    "tailnet_bind": "",           # OPTIONAL second listener on this PC's Tailscale address; "" = off (see start_tailnet)
    "relay_ips": [],              # Tailscale addresses of the relay(s) allowed to use that listener; trusted for X-Relay-Client
    "allowed_origins": ["https://vikkitor93-coder.github.io"],   # the public site; localhost / 127.0.0.1 always allowed
    "generator": "scan_worker",   # "scan_worker" (real, tools/scan_worker_705.py) | "stub" (ondemand/stub_generator.py)
    "workers": 2,                 # 1-2 persistent generator processes
    "queue_cap": 20,              # waiting generations; in flight (waiting + running) is capped at queue_cap + workers
    "rate_miss_per_min": 10,      # new generations per client per minute
    "rate_any_per_min": 120,      # every request per client per minute (polls, cache hits, health)
    "wait_max_s": 90,             # ?wait= long-poll cap, and how long a queued job may wait before "busy"
    "job_timeout_s": 150,         # a running generation longer than this is killed ("busy")
    "worker_idle_s": 600,         # stop idle worker processes after this
    "max_connections": 64,
    "socket_timeout_s": 15,
    "use_db_layouts": True,       # use the scanner DB's stored full layouts (top 100) instead of generating
    "scanner_db": "D:/Orca/NMS-Derelict-Probe-analysis/emu/fastgen/app-data/derelicts.sqlite",
    "scanner_settings": "D:/Orca/NMS-Derelict-Probe-analysis/emu/fastgen/app-data/settings.json",
    "cache_db": str(HERE / "cache" / "ondemand-cache-v1.sqlite"),
    "work_dir": str(HERE / "work"),
    "log_dir": str(HERE / "logs"),
    "eta_config": str(HERE / "eta_config.json"),
    "emu_python": os.path.expandvars("%USERPROFILE%/tools/NMS-Shipwright/.venv/Scripts/python.exe"),
    "worker_script": str(TOOLS / "scan_worker_705.py"),
    "worker_log": False,          # worker stderr -> DEVNULL (it could carry addresses); True writes logs/worker-N.log
    "writer_cache": "off",        # writer-result cache file for the worker, or "off" (default OFF since 2026-10-24)
    "writer_cache_min_seconds": "2.0",
    "piece_index": "D:/Orca/NMS-Derelict-Probe-analysis/meshcache/index.json",
    "game_exe": "D:/Orca/NMS-Derelict-Probe-analysis/rea/NMS-13D5060D.exe",   # size goes into the cache key
    "confirmed": str(FASTGEN / "region-count" / "confirmed_systems.json"),
    "edge_margin": 8,
    "stats_every_s": 600,
}


def load_config(argv=None):
    cfg = dict(DEFAULTS)
    cfg["relay_ips"] = list(DEFAULTS["relay_ips"])
    p = HERE / "config.json"
    if p.is_file():
        cfg.update({k: v for k, v in json.loads(p.read_text(encoding="utf-8")).items() if k in DEFAULTS})
    p = HERE / "config.local.json"   # untracked (.gitignore): this machine's real tailnet_bind / relay_ips; wins over config.json
    if p.is_file():
        cfg.update({k: v for k, v in json.loads(p.read_text(encoding="utf-8")).items() if k in DEFAULTS})
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--port", type=int)
    ap.add_argument("--workers", type=int)
    ap.add_argument("--origin", action="append", help="allowed browser origin (repeatable; replaces the configured list)")
    ap.add_argument("--queue-cap", type=int)
    ap.add_argument("--rate-miss", type=int)
    ap.add_argument("--rate-any", type=int)
    ap.add_argument("--cache-db")
    ap.add_argument("--stats-every", type=int, help="seconds between aggregate stats lines in the log")
    ap.add_argument("--writer-cache", help="writer cache file, or 'off' (default)")
    ap.add_argument("--generator", choices=("scan_worker", "stub"))
    ap.add_argument("--scanner-db")
    ap.add_argument("--eta-config")
    ap.add_argument("--work-dir")
    ap.add_argument("--log-dir")
    ap.add_argument("--job-timeout", type=float)
    ap.add_argument("--tailnet-bind", help="Tailscale address of this PC for the optional relay listener (default: off)")
    ap.add_argument("--relay-ip", action="append", help="Tailscale address of an allowed relay (repeatable)")
    ap.add_argument("--no-db-layouts", action="store_true", help="always generate (tests)")
    a = ap.parse_args(argv)
    for key, val in (("port", a.port), ("workers", a.workers), ("queue_cap", a.queue_cap), ("rate_miss_per_min", a.rate_miss),
                     ("rate_any_per_min", a.rate_any), ("cache_db", a.cache_db), ("writer_cache", a.writer_cache),
                     ("generator", a.generator), ("scanner_db", a.scanner_db), ("eta_config", a.eta_config),
                     ("work_dir", a.work_dir), ("log_dir", a.log_dir), ("job_timeout_s", a.job_timeout),
                     ("tailnet_bind", a.tailnet_bind)):
        if val is not None:
            cfg[key] = val
    if a.origin:
        cfg["allowed_origins"] = a.origin
    if a.relay_ip:
        cfg["relay_ips"] = list(a.relay_ip)
    if a.stats_every:
        cfg["stats_every_s"] = a.stats_every
    if a.no_db_layouts:
        cfg["use_db_layouts"] = False
    cfg["workers"] = max(1, min(2, int(cfg["workers"])))
    cfg["host"] = "127.0.0.1"          # never anything else
    return cfg


# ------------------------------------------------------------------ small helpers
def below_normal_self():
    if IS_WIN:
        try:
            import ctypes
            ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
        except Exception:
            pass


def popen_low(cmd, **kw):
    """Child process at BelowNormal priority without a console window (Windows); niceness 5 elsewhere."""
    if IS_WIN:
        return subprocess.Popen(cmd, creationflags=0x4000 | 0x08000000, **kw)       # BELOW_NORMAL | CREATE_NO_WINDOW
    return subprocess.Popen(cmd, preexec_fn=lambda: os.nice(5), **kw)


def tailnet_ok(ip) -> bool:
    """True only for Tailscale addresses: 100.64.0.0/10 or fd7a:115c:a1e0::/48."""
    try:
        a = ipaddress.ip_address(str(ip).strip())
    except ValueError:
        return False
    if a.version == 4:
        return a in ipaddress.ip_network("100.64.0.0/10")
    return a in ipaddress.ip_network("fd7a:115c:a1e0::/48")


class Stats:
    """Aggregate counters only (no per-client data)."""

    def __init__(self):
        self.lock = threading.Lock()
        self.c = collections.Counter()
        self.t0 = time.time()

    def add(self, key, n=1):
        with self.lock:
            self.c[key] += n

    def line(self):
        with self.lock:
            items = " ".join(f"{k}={v}" for k, v in sorted(self.c.items()))
        return f"stats up={int(time.time() - self.t0)}s {items}"


class RateLimiter:
    """Per-client sliding window kept in memory only; the key is a salted hash, never the address itself."""

    def __init__(self, per_min):
        self.per_min = per_min
        self.lock = threading.Lock()
        self.hits = {}

    def allow(self, key, now=None):
        now = now or time.monotonic()
        with self.lock:
            if len(self.hits) > 5000:      # bounded memory
                for k in [k for k, d in self.hits.items() if not d or d[-1] < now - 60]:
                    del self.hits[k]
                if len(self.hits) > 5000:
                    self.hits.clear()
            d = self.hits.setdefault(key, collections.deque())
            while d and d[0] < now - 60:
                d.popleft()
            if len(d) >= self.per_min:
                return False, max(1, int(60 - (now - d[0])) + 1)
            d.append(now)
            return True, 0

    def active(self, now=None):
        """Number of distinct clients seen in the last minute (a count only)."""
        now = now or time.monotonic()
        with self.lock:
            return sum(1 for d in self.hits.values() if d and d[-1] >= now - 60)


# ------------------------------------------------------------------ cache
class MapCache:
    """Own SQLite file: maps(address, v, data=zlib(JSON {"n": scene names, "v": v4 view, "m": summary})) and
    regions(region, count) for the existence check."""

    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False, timeout=10)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(
            "CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);"
            "CREATE TABLE IF NOT EXISTS maps(address TEXT PRIMARY KEY, v INTEGER, data BLOB);"
            "CREATE TABLE IF NOT EXISTS regions(region TEXT PRIMARY KEY, count INTEGER);")
        self.lock = threading.Lock()
        row = self.db.execute("SELECT count(*), coalesce(sum(length(data)),0) FROM maps").fetchone()
        self.entries, self.bytes = row

    def key_ok(self, key):
        """Drop every cached map when the game build / format key changes."""
        with self.lock:
            r = self.db.execute("SELECT v FROM meta WHERE k='key'").fetchone()
            if r and r[0] == key:
                return
            with self.db:
                self.db.execute("DELETE FROM maps")
                self.db.execute("INSERT OR REPLACE INTO meta VALUES('key',?)", (key,))
            self.entries = self.bytes = 0

    def has(self, address):
        with self.lock:
            return self.db.execute("SELECT 1 FROM maps WHERE address=? AND v=?", (address, CACHE_VERSION)).fetchone() is not None

    def get(self, address):
        with self.lock:
            r = self.db.execute("SELECT data FROM maps WHERE address=? AND v=?", (address, CACHE_VERSION)).fetchone()
        return json.loads(zlib.decompress(r[0])) if r else None

    def put(self, address, entry):
        blob = zlib.compress(json.dumps(entry, separators=(",", ":")).encode("utf-8"), 9)
        with self.lock, self.db:
            old = self.db.execute("SELECT length(data) FROM maps WHERE address=?", (address,)).fetchone()
            self.db.execute("INSERT OR REPLACE INTO maps VALUES(?,?,?)", (address, CACHE_VERSION, blob))
            self.entries += 0 if old else 1
            self.bytes += len(blob) - (old[0] if old else 0)
        return len(blob)

    def region_count(self, region):
        with self.lock:
            r = self.db.execute("SELECT count FROM regions WHERE region=?", (region,)).fetchone()
        return r[0] if r else None

    def set_region_count(self, region, count):
        with self.lock, self.db:
            self.db.execute("INSERT OR REPLACE INTO regions VALUES(?,?)", (region, int(count)))

    def close(self):
        with self.lock:
            try:
                self.db.close()
            except sqlite3.Error:
                pass


# ------------------------------------------------------------------ scanner DB (read only)
class ScannerDB:
    """The scanner's derelicts.sqlite through a read-only URI (mode=ro + query_only).  A missing or unreadable file means
    "no data" for every question; nothing is ever written."""

    def __init__(self, path):
        self.path = path
        self.local = threading.local()

    def _db(self):
        db = getattr(self.local, "db", None)
        if db is None:
            try:
                if not Path(self.path).is_file():
                    raise sqlite3.Error("missing")
                db = sqlite3.connect(f"file:{Path(self.path).as_posix()}?mode=ro", uri=True, timeout=5)
                db.execute("PRAGMA query_only=1")
            except (sqlite3.Error, OSError):
                db = False
            self.local.db = db
        return db or None

    def _q(self, sql, args=()):
        db = self._db()
        if db is None:
            return None
        try:
            return db.execute(sql, args).fetchone()
        except sqlite3.Error:
            self.local.db = None          # reopen next time (file replaced / schema missing)
            return None

    def has_system(self, address):
        return self._q("SELECT 1 FROM systems WHERE address=?", (address,)) is not None

    def info(self, address):
        """-> (preset, rooms, writer_seconds) or (None, None, None)"""
        r = self._q("SELECT preset, rooms, writer_seconds FROM systems WHERE address=?", (address,))
        return (r[0], r[1], r[2]) if r else (None, None, None)

    def region_count(self, region):
        r = self._q("SELECT count FROM regions WHERE galaxy=0 AND region=?", (region,))
        return r[0] if r else None

    def modules(self, address):
        r = self._q("SELECT frigate_modules, frigate_modules_ambiguous FROM systems WHERE address=?", (address,))
        return (r[0], r[1]) if r else (None, None)

    def has_layout(self, address):
        return self._q("SELECT 1 FROM layouts WHERE address=? AND json_z IS NOT NULL", (address,)) is not None

    def layout(self, address):
        r = self._q("SELECT json_z FROM layouts WHERE address=?", (address,))
        if not r or r[0] is None:
            return None
        try:
            d = json.loads(zlib.decompress(r[0]))
        except Exception:
            return None
        return d if isinstance(d, dict) and "instances" in d else None

    def last_write(self):
        """Newest mtime of the DB file or its WAL (None when absent): "the scanner is busy" if this is recent."""
        best = None
        for suffix in ("", "-wal"):
            try:
                m = os.stat(self.path + suffix).st_mtime
                best = m if best is None else max(best, m)
            except OSError:
                pass
        return best


# ------------------------------------------------------------------ existence
class Existence:
    """The scanner's "existing systems only" rule (app/engine.py safe_top): 1 <= system index <= region count - 1 -
    edge_margin, raised to a confirmed visit.  A system that is in the scanner DB exists."""

    def __init__(self, cfg, scanner, cache):
        self.cfg, self.scanner, self.cache = cfg, scanner, cache
        self.margin = int(cfg["edge_margin"])
        try:
            self.margin = int(json.loads(Path(cfg["scanner_settings"]).read_text(encoding="utf-8")).get("edge_margin", self.margin))
        except (OSError, ValueError):
            pass
        self.confirmed_mtime, self.confirmed = None, {}

    def _confirmed(self):
        p = Path(self.cfg["confirmed"])
        try:
            m = p.stat().st_mtime
            if m != self.confirmed_mtime:
                self.confirmed = {k.upper(): v for k, v in json.loads(p.read_text(encoding="utf-8")).items() if not k.startswith("_")}
                self.confirmed_mtime = m
        except (OSError, ValueError):
            pass
        return self.confirmed

    def quick(self, address):
        """True / False, or None when the region's system count is not known yet (needs the region counter)."""
        if self.scanner.has_system(address):
            return True
        m = ADDR_RE.match(address)
        idx, region = int(m.group(1), 16), m.group(2)
        n = self.scanner.region_count(region)
        if n is None:
            n = self.cache.region_count(region)
        if n is None:
            return None
        return self.verdict(idx, region, n)

    def verdict(self, idx, region, n):
        top = n - 1 - self.margin
        c = self._confirmed().get(region, {})
        if "max_confirmed" in c:
            try:
                top = max(top, int(c["max_confirmed"], 16))
            except (TypeError, ValueError):
                pass
        return 1 <= idx <= min(top, n - 1)


# ------------------------------------------------------------------ generator adapter
class StubRegionCounter:
    def count(self, region, timeout=0):
        import stub_generator
        return stub_generator.region_count(region)

    def close(self):
        pass


class RegionCounter:
    """Lazy persistent app/rc_worker.py (Unicorn, Shipwright venv) for regions the scanner has never counted."""

    def __init__(self, cfg):
        self.cfg, self.p, self.lock, self.q = cfg, None, threading.Lock(), None

    def _start(self):
        self.p = popen_low([self.cfg["emu_python"], "-I", str(FASTGEN / "app" / "rc_worker.py")], stdin=subprocess.PIPE,
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1, env={**os.environ})
        self.q = queue.Queue()
        threading.Thread(target=self._pump, args=(self.p, self.q), daemon=True).start()
        self.q.get(timeout=120)     # {"ready": true}

    @staticmethod
    def _pump(p, q):
        for line in p.stdout:
            q.put(line)
        q.put("")

    def count(self, region, timeout=120):
        with self.lock:
            for _ in range(2):
                try:
                    if self.p is None or self.p.poll() is not None:
                        self._start()
                    self.p.stdin.write(json.dumps({"region": region, "galaxy": 0}) + "\n")
                    self.p.stdin.flush()
                    r = json.loads(self.q.get(timeout=timeout))
                    if r.get("ok"):
                        return int(r["count"])
                except (OSError, ValueError, queue.Empty):
                    pass
                self.close()
        return None

    def close(self):
        p, self.p = self.p, None
        if p and p.poll() is None:
            p.kill()


class MapBuilder:
    """layout dict -> cache entry; the same pack/encode code as tools/build_top_bundle.py + derelict_view_compact.py.
    Needs tools/{derelict_view,derelict_view_compact,extra_containers_705}.py and the piece index (all imported lazily)."""

    def __init__(self, cfg):
        self.cfg = cfg
        self._ready = False
        self.table_cache = {}
        self.lock = threading.Lock()

    def _load(self):
        with self.lock:
            if self._ready:
                return
            import derelict_view as V
            import derelict_view_compact as C
            import extra_containers_705 as ec
            self.V, self.C, self.ec = V, C, ec
            self.index = json.loads(Path(self.cfg["piece_index"]).read_text(encoding="utf-8"))
            self.rotations = ec.authored_rotations()
            self._ready = True

    @staticmethod
    def summary(layout, modules, modules_ambiguous, source):
        kinds = layout.get("container_kinds") or {}
        return {"address": layout["address"], "galaxy": 0, "preset": layout["preset"], "rooms": len(layout["rooms"]),
                "crates": kinds.get("salvage_crate", 0), "footlockers": kinds.get("crew_footlocker", 0),
                "modules": modules, "modules_ambiguous": modules_ambiguous, "source": source}

    def entry(self, layout, modules, modules_ambiguous, source):
        self._load()
        V, C = self.V, self.C
        d = {**layout, "extra_containers": self.ec.extra_containers(layout)}
        names = sorted({i["scene_resource"].upper() for i in d["instances"]})
        ids = {n: k for k, n in enumerate(names)}
        v4 = C.encode(V.pack(d, ids), self.table(names))
        return {"n": names, "v": v4, "m": self.summary(layout, modules, modules_ambiguous, source)}

    def table(self, names):
        self._load()
        key = tuple(names)
        t = self.table_cache.get(key)
        if t is None:
            t = self.C.compact_table(self.V.pieces_table(self.index, names, self.rotations))
            if len(self.table_cache) > 256:
                self.table_cache.clear()
            self.table_cache[key] = t
        return t

    def body(self, address, entry):
        return {"v": 4, "t": self.table(entry["n"]), "s": {address: entry["v"]}, "m": entry["m"]}


class StubBuilder(MapBuilder):
    """Test double: same body SHAPE ({"v":4,"t":{n,w,f,o,k},"s":{addr:view},"m":summary}) but NOT a renderable compact view."""

    def entry(self, layout, modules, modules_ambiguous, source):
        names = sorted({i["scene_resource"].upper() for i in layout["instances"]})
        view = {"stub": True, "i": [[names.index(i["scene_resource"].upper()) for i in layout["instances"]]]}
        return {"n": names, "v": view, "m": self.summary(layout, modules, modules_ambiguous, source)}

    def table(self, names):
        z = [0] * len(names)
        return {"n": list(names), "w": z, "f": z, "o": z, "k": z}


# ------------------------------------------------------------------ ETA model
class EtaModel:
    """eta_config.json: table + wording; reloaded when the file changes.  Missing file = built-in defaults."""

    BUILTIN = {"overhead_s": 0.7, "worker_start_s": 6.0, "load_factor_busy": 1.25, "busy_window_s": 120, "slow_after_s": 15,
               "poll_ms": 1500, "default": {"median_s": 1.5, "p90_s": 4.0}, "presets": {},
               "stages": ["Waiting in queue", "Checking the system", "Generating layout", "Packing map", "Done"],
               "texts": {"title": "Generating map\u2026", "kind": "{preset} derelict",
                         "kind_slow": "{preset} derelict: these take longer, up to ~{upto} s", "rooms": "{rooms} rooms",
                         "queue": "Position {position} of {queue} in queue",
                         "busy": "The map server is also scanning right now, so this may be slower",
                         "left": "about {s} s left", "over": "taking longer than usual\u2026 still working (elapsed {s} s)",
                         "ready": "Map ready, drawing\u2026"}}

    def __init__(self, path):
        self.path, self.mtime, self.c = Path(path), None, dict(self.BUILTIN)

    def cfg(self):
        try:
            m = self.path.stat().st_mtime
            if m != self.mtime:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                c = dict(self.BUILTIN)
                c.update({k: v for k, v in loaded.items() if not k.startswith("_")})
                c["texts"] = {**self.BUILTIN["texts"], **(loaded.get("texts") or {})}
                self.c, self.mtime = c, m
        except (OSError, ValueError):
            pass
        return self.c

    def preset_row(self, preset):
        c = self.cfg()
        return (c.get("presets") or {}).get(preset) or c["default"]

    def expected(self, preset, writer_s, busy):
        """Expected seconds of one generation (without worker start): own writer_seconds if the scanner DB has it, else the
        preset median; times the load factor when the scanner is busy; plus the fixed overhead."""
        c = self.cfg()
        base = float(writer_s) if writer_s is not None else float(self.preset_row(preset).get("median_s", 1.5))
        return base * (float(c["load_factor_busy"]) if busy else 1.0) + float(c["overhead_s"])

    def upto(self, preset, busy):
        c = self.cfg()
        row = self.preset_row(preset)
        return float(row.get("p90_s", row.get("median_s", 2.0))) * (float(c["load_factor_busy"]) if busy else 1.0) + float(c["overhead_s"])


# ------------------------------------------------------------------ workers and queue
class WorkerProc:
    """One persistent generator process (JSON lines over stdin/stdout, BelowNormal priority)."""

    def __init__(self, cfg, slot):
        self.cfg, self.slot = cfg, slot
        env = {**os.environ, "NMS_WRITER_CACHE": cfg["writer_cache"] or "off",
               "NMS_WRITER_CACHE_MIN_SECONDS": str(cfg["writer_cache_min_seconds"])}
        if cfg["generator"] == "stub":
            cmd = [sys.executable, "-I", str(HERE / "stub_generator.py")]
        else:
            cmd = [cfg["emu_python"], "-I", cfg["worker_script"]]
        self.err = None
        if cfg["worker_log"]:
            Path(cfg["log_dir"]).mkdir(parents=True, exist_ok=True)
            self.err = open(Path(cfg["log_dir"]) / f"worker-{slot}.log", "w", encoding="utf-8")
        self.p = popen_low(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.err or subprocess.DEVNULL,
                           text=True, bufsize=1, env=env)
        self.q = queue.Queue()
        threading.Thread(target=self._pump, args=(self.p, self.q), daemon=True).start()
        try:
            ready = self.q.get(timeout=180)
            if '"ready"' not in ready:
                raise RuntimeError("worker did not start")
        except Exception:
            self.kill()
            raise

    @staticmethod
    def _pump(p, q):
        for line in p.stdout:
            q.put(line)
        q.put("")

    def alive(self):
        return self.p.poll() is None

    def run(self, address, out, timeout):
        self.p.stdin.write(json.dumps({"address": address, "out": str(out)}) + "\n")
        self.p.stdin.flush()
        line = self.q.get(timeout=timeout)
        if not line:
            raise RuntimeError("worker died")
        return json.loads(line)

    def kill(self):
        try:
            self.p.kill()
        except OSError:
            pass
        if self.err:
            try:
                self.err.close()
            except OSError:
                pass

    def close(self):
        try:
            self.p.stdin.close()
            self.p.wait(timeout=15)
        except Exception:
            self.kill()
        if self.err:
            try:
                self.err.close()
            except OSError:
                pass


class Job:
    def __init__(self, address, preset, expected):
        self.address = address
        self.preset = preset
        self.expected = expected      # seconds, without worker start
        self.extra = 0.0              # worker start added when it begins on a cold worker
        self.eta0 = 0
        self.created = time.monotonic()
        self.started = None
        self.stage = 0                # 0 queue, 1 checking, 2 generating, 3 packing, 4 done
        self.event = threading.Event()
        self.result = None            # (http status, dict)


class QueueFull(Exception):
    pass


class Engine:
    def __init__(self, cfg, stats):
        self.cfg, self.stats = cfg, stats
        self.stub = cfg["generator"] == "stub"
        self.cache = MapCache(cfg["cache_db"])
        self.scanner = ScannerDB(cfg["scanner_db"])
        self.exist = Existence(cfg, self.scanner, self.cache)
        self.builder = StubBuilder(cfg) if self.stub else MapBuilder(cfg)
        self.counter = StubRegionCounter() if self.stub else RegionCounter(cfg)
        self.eta = EtaModel(cfg["eta_config"])
        self.cache.key_ok(self._cache_key())
        self.cv = threading.Condition()
        self.queued = collections.deque()
        self.jobs = {}               # address -> Job (queued or running)
        self.recent = {}             # address -> (expires, status, body) for failed jobs
        self.running = 0
        self.warm = 0                # worker processes currently alive
        self.stop = False
        self.last_activity = time.monotonic()
        self.threads = [threading.Thread(target=self._loop, args=(i,), daemon=True, name=f"gen-{i}") for i in range(cfg["workers"])]
        for t in self.threads:
            t.start()
        threading.Thread(target=self._reaper, daemon=True).start()

    def _cache_key(self):
        try:
            tag = f"{Path(self.cfg['game_exe']).name}:{Path(self.cfg['game_exe']).stat().st_size}"
        except OSError:
            tag = "noexe"
        return f"v{CACHE_VERSION}|view4|{'stub' if self.stub else 'real'}|{tag}"

    # ---- hints for the status (cheap, read-only)
    def preset_hint(self, address):
        """Preset known before any generation: the scanner DB, else the seed (derelict_seed_preset_705, 12 us), else None."""
        preset, rooms, writer_s = self.scanner.info(address)
        if preset:
            return preset, rooms, writer_s
        if self.stub:
            import stub_generator
            return stub_generator.preset_of(address), None, None
        try:
            import derelict_seed_preset_705 as sp
            r = sp.derelict_seed_preset(address)
            if isinstance(r, (tuple, list)):
                r = next((x for x in r if isinstance(x, str)), None)
            if isinstance(r, dict):
                r = r.get("preset")
            return (r if isinstance(r, str) else None), None, None
        except Exception:
            return None, None, None

    def scanner_busy(self):
        m = self.scanner.last_write()
        return m is not None and (time.time() - m) < float(self.eta.cfg()["busy_window_s"])

    def _expected_for(self, address, busy):
        preset, rooms, writer_s = self.preset_hint(address)
        if self.cfg["use_db_layouts"] and self.scanner.has_layout(address):
            return preset, rooms, 0.3, writer_s
        return preset, rooms, self.eta.expected(preset, writer_s, busy), writer_s

    # ---- ETA simulation: free-slot model
    def simulate(self, target=None, hypo_expected=None):
        """Seconds until `target` (a queued/running Job) is done, or until a hypothetical new job of `hypo_expected` seconds
        is done if it were queued now.  -> (eta seconds, position, overdue)"""
        now = time.monotonic()
        start_s = float(self.eta.cfg()["worker_start_s"])
        with self.cv:
            running = [j for j in self.jobs.values() if j.started is not None]
            queued = list(self.queued)
            warm = self.warm
        workers = self.cfg["workers"]
        slots, overdue = [], False
        for j in running:
            left = j.expected + j.extra - (now - j.started)
            if j is target and left < 0:
                overdue = True
            slots.append(max(0.0, left))
        idle_slots = max(0, workers - len(running))
        slots += [0.0] * idle_slots
        warm_idle = max(0, warm - len(running))           # idle slots whose worker process is already running
        if target in running:
            return slots[running.index(target)], 0, overdue
        order = queued + ([None] if target is None else [])
        for k, j in enumerate(order, 1):
            slots.sort()
            begin = slots[0]
            dur = hypo_expected if j is None else j.expected
            if begin == 0.0:
                if warm_idle > 0:
                    warm_idle -= 1
                else:
                    dur += start_s                 # a cold worker has to start first
            slots[0] = begin + dur
            if j is target or j is None:
                return slots[0], k, False
        return 0.0, 0, False

    def messages(self, preset, rooms, position, queue_n, upto, slow, busy):
        c = self.eta.cfg()
        t = c["texts"]
        pname = (preset or "").split("_")[-1] or "derelict"
        msg = {"title": t["title"], "rooms": (t["rooms"].format(rooms=rooms) if rooms else ""),
               "queue": (t["queue"].format(position=position, queue=queue_n) if position else ""),
               "busy": t["busy"] if busy else "", "left": t["left"], "over": t["over"], "ready": t["ready"],
               "stages": list(c["stages"])}
        if preset:
            msg["kind"] = (t["kind_slow"] if slow else t["kind"]).format(preset=pname, upto=int(math.ceil(upto)))
        else:
            msg["kind"] = ""
        return msg

    def status(self, address):
        """Read-only progress for GET /api/status.  Starts nothing."""
        c = self.eta.cfg()
        busy = self.scanner_busy()
        with self.cv:
            job = self.jobs.get(address)
            q_n, run_n = len(self.queued), self.running
        base = {"poll_ms": int(c["poll_ms"]), "queue": q_n, "running": run_n, "scanner_busy": busy}
        if job is None and self.cache.has(address):
            preset, rooms, _ = self.preset_hint(address)
            return {**base, "status": "ready", "stage": 4, "preset": preset, "rooms": rooms, "position": 0, "eta_s": 0,
                    "elapsed_s": 0, "overdue": False, "slow": False, "upto_s": 0,
                    "msg": self.messages(preset, rooms, 0, q_n, 0, False, False)}
        if job is None:
            bad = self.recent_failure(address)
            if bad:
                st, body = bad
                return {**base, "status": "failed", "stage": 0, "http": st, "error": body.get("error"),
                        "retry_after": body.get("retry_after", 30), "preset": None, "rooms": None, "position": 0, "eta_s": 0,
                        "elapsed_s": 0, "overdue": False, "slow": False, "upto_s": 0,
                        "msg": self.messages(None, None, 0, q_n, 0, False, False)}
        if job is not None:
            preset, rooms, _ = self.preset_hint(address)
            eta, pos, overdue = self.simulate(target=job)
            started = job.started is not None
            elapsed = time.monotonic() - (job.started if started else job.created)
            status, stage = ("generating", max(1, job.stage)) if started else ("queued", 0)
            hyp = job.expected
        else:
            preset, rooms, hyp, _w = self._expected_for(address, busy)
            eta, pos, overdue = self.simulate(None, hyp)
            status, stage, elapsed = "idle", 0, 0
        pos_out = pos if status == "queued" else 0
        upto = self.eta.upto(preset, busy) if preset else hyp
        slow = hyp >= float(c["slow_after_s"])
        return {**base, "status": status, "stage": stage, "preset": preset, "rooms": rooms, "position": pos_out,
                "eta_s": int(eta) + 1 if not overdue else 0, "elapsed_s": int(elapsed), "overdue": bool(overdue), "slow": bool(slow),
                "upto_s": int(math.ceil(upto)), "msg": self.messages(preset, rooms, pos_out, q_n, upto, slow, busy)}

    def status_of(self, job):
        """Fields for a 202 answer (same as /api/status for a queued/running job, plus retry_after)."""
        s = self.status(job.address)
        s["retry_after"] = 2
        return s

    # ---- request side
    def lookup(self, address):
        e = self.cache.get(address)
        if e is not None:
            return "hit", self.builder.body(address, e)
        return None

    def submit(self, address):
        """-> (Job, created). Raises QueueFull when waiting + running jobs reach queue_cap + workers."""
        busy = self.scanner_busy()
        preset, _rooms, expected, _w = self._expected_for(address, busy)
        with self.cv:
            job = self.jobs.get(address)
            if job is not None:
                return job, False
            if len(self.jobs) >= self.cfg["queue_cap"] + self.cfg["workers"]:
                raise QueueFull
            job = Job(address, preset, expected)
            self.jobs[address] = job
            self.queued.append(job)
            self.cv.notify()
            self.last_activity = time.monotonic()
        job.eta0 = int(self.simulate(target=job)[0]) + 1
        return job, True

    def recent_failure(self, address):
        r = self.recent.get(address)
        if r and r[0] > time.monotonic():
            return r[1], r[2]
        self.recent.pop(address, None)
        return None

    def depth(self):
        with self.cv:
            return len(self.queued), self.running

    # ---- worker side
    def _finish(self, job, status, body, keep=0):
        with self.cv:
            self.jobs.pop(job.address, None)
            job.result = (status, body)
            job.stage = 4 if status == 200 else job.stage
            if keep:
                self.recent[job.address] = (time.monotonic() + keep, status, body)
            if len(self.recent) > 2000:
                self.recent.clear()
        job.event.set()

    def _loop(self, slot):
        proc, last_used = None, time.monotonic()
        while not self.stop:
            job, idle_proc, expired = None, None, False
            with self.cv:
                if not self.queued:
                    self.cv.wait(timeout=5)
                if self.stop:
                    break
                if not self.queued:
                    if proc is not None and time.monotonic() - last_used > self.cfg["worker_idle_s"]:
                        idle_proc, proc = proc, None          # idle too long: free the worker process
                        self.warm = max(0, self.warm - 1)
                else:
                    job = self.queued.popleft()
                    if time.monotonic() - job.created > self.cfg["wait_max_s"]:
                        self.jobs.pop(job.address, None)
                        expired = True
                    else:
                        job.started = time.monotonic()
                        job.stage = 1
                        job.extra = float(self.eta.cfg()["worker_start_s"]) if (proc is None or not proc.alive()) else 0.0
                        self.running += 1
            if idle_proc is not None:
                idle_proc.close()
                continue
            if job is None:
                continue
            if expired:
                self.stats.add("queue_timeouts")
                self._finish(job, 503, {"error": "busy", "message": "Map server is busy, try later", "retry_after": 30}, keep=10)
                continue
            try:
                had = proc is not None and proc.alive()
                proc = self._run(job, slot, proc)
                now_alive = proc is not None and proc.alive()
                with self.cv:
                    self.warm = max(0, self.warm + int(now_alive) - int(had))
            except Exception as exc:     # never kill the thread
                self.stats.add("errors")
                sys.stderr.write(f"job error: {type(exc).__name__}\n")
                self._finish(job, 503, {"error": "failed", "message": "Map could not be made, try later", "retry_after": 60}, keep=20)
                if proc is not None:
                    proc.kill()
                    proc = None
                    with self.cv:
                        self.warm = max(0, self.warm - 1)
            finally:
                last_used = time.monotonic()
                with self.cv:
                    self.running -= 1
                    self.last_activity = last_used
        if proc is not None:
            proc.close()
            with self.cv:
                self.warm = max(0, self.warm - 1)

    def _run(self, job, slot, proc):
        address = job.address
        t0 = time.monotonic()
        # 1. existence (needs the region counter only for regions nobody counted yet)
        verdict = self.exist.quick(address)
        if verdict is None:
            m = ADDR_RE.match(address)
            n = self.counter.count(m.group(2))
            if n is None:
                raise RuntimeError("region count failed")
            self.cache.set_region_count(m.group(2), n)
            self.stats.add("region_counts")
            verdict = self.exist.verdict(int(m.group(1), 16), m.group(2), n)
        if not verdict:
            self.stats.add("not_found")
            self._finish(job, 404, {"error": "no_such_system", "message": "No such system"}, keep=60)
            return proc
        # 2. layout: the scanner DB's stored full layout if it has one, else generate
        layout, source, mods, amb = None, "generated", None, None
        if self.cfg["use_db_layouts"]:
            layout = self.scanner.layout(address)
            if layout is not None:
                source = "scanner-db-layout"
                mods, amb = self.scanner.modules(address)
        if layout is None:
            job.stage = 2
            if proc is None or not proc.alive():
                if proc is not None:
                    proc.kill()
                proc = WorkerProc(self.cfg, slot)
                self.stats.add("worker_starts")
            out = Path(self.cfg["work_dir"]) / f"s{slot}" / address
            shutil.rmtree(out, ignore_errors=True)
            try:
                reply = proc.run(address, out, self.cfg["job_timeout_s"])
            except (queue.Empty, RuntimeError, OSError, ValueError):
                self.stats.add("gen_timeouts")
                proc.kill()
                self._finish(job, 503, {"error": "busy", "message": "Map server is busy, try later", "retry_after": 60}, keep=30)
                return None
            try:
                if reply.get("code") != 0 or "layout" in (reply.get("errors") or {}):
                    raise ValueError("generation failed")
                layout = json.loads((out / "derelict.json").read_text(encoding="utf-8"))
                if "instances" not in layout:
                    raise ValueError("no layout")
            finally:
                shutil.rmtree(out, ignore_errors=True)
            fr = reply.get("frigate")
            if fr:
                mods, amb = fr[0], fr[1]
        job.stage = 3
        entry = self.builder.entry(layout, mods, amb, source)
        self.cache.put(address, entry)
        self.stats.add("generated" if source == "generated" else "from_db_layout")
        self._finish(job, 200, self.builder.body(address, entry))
        return proc

    def _reaper(self):
        while not self.stop:
            time.sleep(5)
            if (not self.queued and self.running == 0
                    and time.monotonic() - self.last_activity > self.cfg["worker_idle_s"]):
                self.counter.close()
                with self.cv:
                    self.cv.notify_all()

    def shutdown(self):
        self.stop = True
        with self.cv:
            self.cv.notify_all()
        self.counter.close()
        for t in self.threads:
            t.join(timeout=20)


# ------------------------------------------------------------------ HTTP
def origin_allowed(cfg, origin):
    if origin in cfg["allowed_origins"]:
        return True
    return re.fullmatch(r"https?://(localhost|127\.0\.0\.1)(:\d{1,5})?", origin or "") is not None


class Handler(BaseHTTPRequestHandler):
    server_version = "od"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    # no access log at all (it would carry IPs and addresses); aggregate counters live in Stats
    def log_message(self, *a):
        pass

    def log_error(self, *a):
        pass

    @property
    def app(self):
        return self.server.app

    def setup(self):
        self.timeout = self.app.cfg["socket_timeout_s"]
        super().setup()

    # ---- client key (memory only, salted hash)
    def client_key(self):
        peer = self.client_address[0]
        ip = peer
        if peer in self.app.relay_ips:
            # a listed relay vouches for the visitor with X-Relay-Client (18 lowercase hex = its own salted hash); without a
            # valid header all of that relay's traffic shares one bucket (never the relay's own address, never a guess)
            h = self.headers.get("X-Relay-Client") or ""
            ip = ("relay:" + h) if RELAY_KEY_RE.match(h) else "relay:none"
        elif peer in ("127.0.0.1", "::1"):       # a local tunnel (cloudflared / Tailscale Funnel) vouches for the real client
            h = self.headers.get("CF-Connecting-IP") or (self.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
            if h:
                ip = h[:64]
        return hmac.new(self.app.salt, ip.encode("utf-8", "replace"), hashlib.sha256).digest()[:9]

    # ---- output
    def reply(self, status, obj, headers=None, cache=NO_CACHE):
        body = json.dumps(obj, separators=(",", ":")).encode("utf-8")
        hdr = {"Content-Type": "application/json; charset=utf-8", "Cache-Control": cache, "X-Content-Type-Options": "nosniff",
               "Referrer-Policy": "no-referrer", **(headers or {})}
        if len(body) > 600 and "gzip" in (self.headers.get("Accept-Encoding") or ""):
            body = gzip.compress(body, 6, mtime=0)
            hdr["Content-Encoding"] = "gzip"
        hdr["Vary"] = "Origin, Accept-Encoding"
        origin = self.headers.get("Origin")
        if origin and origin_allowed(self.app.cfg, origin):
            hdr["Access-Control-Allow-Origin"] = origin
        self.send_response(status)
        for k, v in hdr.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)
        self.app.stats.add(f"http_{status}")

    def err(self, status, code, message, headers=None):
        self.reply(status, {"error": code, "message": message}, headers)

    # ---- dispatch
    def do_GET(self):
        self.handle_any()

    do_HEAD = do_GET

    def do_OPTIONS(self):
        origin = self.headers.get("Origin")
        if self.body_present():
            return self.err(400, "no_body", "Request bodies are not accepted")
        if not origin or not origin_allowed(self.app.cfg, origin):
            return self.err(403, "origin", "Origin not allowed")
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Max-Age", "600")
        self.send_header("Vary", "Origin")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _no_method(self):
        self.close_connection = True
        self.err(405, "method", "GET only", {"Allow": "GET, HEAD, OPTIONS", "Connection": "close"})

    do_POST = do_PUT = do_DELETE = do_PATCH = _no_method

    def body_present(self):
        return (self.headers.get("Content-Length") not in (None, "", "0")) or bool(self.headers.get("Transfer-Encoding"))

    def handle_any(self):
        app = self.app
        app.stats.add("requests")
        if self.body_present():
            self.close_connection = True
            return self.err(400, "no_body", "Request bodies are not accepted", {"Connection": "close"})
        origin = self.headers.get("Origin")
        if origin and not origin_allowed(app.cfg, origin):
            app.stats.add("cors_rejected")
            return self.err(403, "origin", "Origin not allowed")
        if len(self.path) > 200:
            return self.err(400, "bad_request", "Path too long")
        parts = urlsplit(self.path)
        path = parts.path
        key = self.client_key()
        ok, retry = app.rate_any.allow(key)
        if not ok:
            app.stats.add("rate_limited")
            return self.err(429, "rate_limited", "Too many requests, slow down", {"Retry-After": str(retry)})
        if path == "/api/health":
            q, running = app.engine.depth()
            return self.reply(200, {"ok": True, "queue": q, "running": running,
                                    "cache_entries": app.engine.cache.entries, "cache_bytes": app.engine.cache.bytes,
                                    "clients_1min": app.rate_any.active()})
        if path.startswith("/api/map/"):
            return self.map_request(path[len("/api/map/"):], parts.query, key)
        if path.startswith("/api/status/"):
            return self.status_request(path[len("/api/status/"):])
        self.err(404, "not_found", "Not found")

    def parse_address(self, raw):
        """-> (address, None) or (None, (status, code, message))"""
        if "/" in raw:
            return None, (404, "not_found", "Not found")
        if not re.fullmatch(r"[0-9A-Fa-f]{16}", raw):
            return None, (400, "bad_address", "The address must be exactly 16 hexadecimal characters")
        address = raw.upper()
        m = ADDR_RE.match(address)
        if not m:
            if address[6:8] != "00":
                return None, (400, "galaxy", "Only galaxy 0 (Euclid) is supported for now")
            return None, (400, "bad_address", "Not a system address")
        if int(m.group(1), 16) == 0:
            return None, (404, "no_such_system", "No such system")
        return address, None

    def status_request(self, raw):
        eng = self.app.engine
        address, bad = self.parse_address(raw)
        if bad:
            return self.err(*bad)
        if not eng.cache.has(address) and address not in eng.jobs and eng.exist.quick(address) is False:
            self.app.stats.add("not_found")
            return self.err(404, "no_such_system", "No such system")
        self.app.stats.add("status_polls")
        self.reply(200, eng.status(address))

    def map_request(self, raw, query, key):
        app, eng = self.app, self.app.engine
        address, bad = self.parse_address(raw)
        if bad:
            return self.err(*bad)
        wait = 0
        try:
            w = parse_qs(query).get("wait")
            if w:
                wait = float(w[0])
                if not math.isfinite(wait):         # nan / inf
                    raise ValueError
                wait = max(0, min(wait, app.cfg["wait_max_s"]))
        except ValueError:
            return self.err(400, "bad_wait", "wait must be a number of seconds")
        hit = eng.lookup(address)
        if hit:
            app.stats.add("cache_hits")
            return self.reply(200, hit[1], cache="public, max-age=3600")
        bad = eng.recent_failure(address)
        if bad:
            st, body = bad
            return self.reply(st, body, {"Retry-After": str(body.get("retry_after", 30))} if st == 503 else None)
        # a new generation (or the cheap existence verdict) is charged to the miss limiter; joining a running job is free
        if address not in eng.jobs:
            ok, retry = app.rate_miss.allow(key)
            if not ok:
                app.stats.add("rate_limited")
                return self.err(429, "rate_limited", "Too many new maps requested, wait a minute", {"Retry-After": str(retry)})
            if eng.exist.quick(address) is False:
                app.stats.add("not_found")
                return self.err(404, "no_such_system", "No such system")
        try:
            job, created = eng.submit(address)
        except QueueFull:
            app.stats.add("queue_full")
            return self.err(503, "busy", "Map server is busy, try later", {"Retry-After": "30"})
        app.stats.add("misses_queued" if created else "joined")
        if wait:
            job.event.wait(timeout=wait)
        if job.result is not None:
            st, body = job.result
            if st == 200:
                return self.reply(200, body, cache="public, max-age=3600")
            return self.reply(st, body, {"Retry-After": str(body.get("retry_after", 30))} if st == 503 else None)
        self.reply(202, eng.status_of(job), {"Retry-After": "2"})


class AppServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 64
    allow_reuse_address = False

    def __init__(self, cfg, engine, host=None, twin=None):
        """host: only start_tailnet() passes one (after tailnet_ok checks); it makes this a relay listener that closes every
        peer not in relay_ips.  twin: the primary server whose limiters, salt and stats this listener shares."""
        self.relay_only = host is not None
        if host and ":" in host:
            self.address_family = socket.AF_INET6
        super().__init__((host or cfg["host"], cfg["port"]), Handler)
        self.cfg, self.engine, self.stats = cfg, engine, engine.stats
        self.relay_ips = {str(x) for x in cfg.get("relay_ips") or []}
        if twin is not None:
            self.salt, self.rate_miss, self.rate_any = twin.salt, twin.rate_miss, twin.rate_any
        else:
            self.salt = secrets.token_bytes(16)       # in memory only: client keys cannot be recovered or linked across restarts
            self.rate_miss = RateLimiter(cfg["rate_miss_per_min"])
            self.rate_any = RateLimiter(cfg["rate_any_per_min"])
        self.active = 0
        self.alock = threading.Lock()

    @property
    def app(self):
        return self

    def process_request(self, request, client_address):
        if self.relay_only and client_address[0] not in self.relay_ips:
            self.shutdown_request(request)             # closed without an answer
            self.stats.add("relay_peer_refused")
            return
        with self.alock:
            full = self.active >= self.cfg["max_connections"]
            if not full:
                self.active += 1
        if full:
            try:
                request.sendall(b"HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
            except OSError:
                pass
            self.shutdown_request(request)
            self.stats.add("conn_refused")
            return
        super().process_request(request, client_address)

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            with self.alock:
                self.active -= 1

    def handle_error(self, request, client_address):
        self.stats.add("handler_errors")      # no traceback, no address


def start_tailnet(cfg, engine, primary):
    """OPTIONAL relay listener.  Starts only when tailnet_bind AND every relay_ips entry is a Tailscale address
    (100.64.0.0/10 or fd7a:115c:a1e0::/48) and relay_ips is not empty; otherwise nothing is bound and None is returned.
    Shares limiters, queue and cache with the loopback listener; closes every peer not in relay_ips without an answer."""
    bind, relays = str(cfg.get("tailnet_bind") or "").strip(), list(cfg.get("relay_ips") or [])
    if not bind or not relays or not tailnet_ok(bind) or not all(tailnet_ok(r) for r in relays):
        return None
    try:
        srv = AppServer(cfg, engine, host=bind, twin=primary)
    except OSError:
        engine.stats.add("tailnet_bind_failed")
        return None
    threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.5}, daemon=True, name="tailnet").start()
    return srv


def serve(cfg):
    below_normal_self()
    stats = Stats()
    engine = Engine(cfg, stats)
    srv = AppServer(cfg, engine)
    tail = start_tailnet(cfg, engine, srv) if cfg.get("tailnet_bind") else None
    if cfg.get("tailnet_bind") and tail is None:
        print("relay listener NOT started (tailnet_bind / relay_ips must be Tailscale addresses and reachable)", flush=True)

    def report():
        while True:
            time.sleep(cfg["stats_every_s"])
            print(stats.line(), flush=True)

    threading.Thread(target=report, daemon=True).start()
    print(f"ondemand server listening on loopback port {cfg['port']} (loopback only), generator={cfg['generator']}, "
          f"workers={cfg['workers']}, queue_cap={cfg['queue_cap']}, relay listener={'on' if tail else 'off'}, "
          f"cache entries={engine.cache.entries}", flush=True)
    signal.signal(signal.SIGINT, lambda *a: threading.Thread(target=srv.shutdown, daemon=True).start())
    try:
        signal.signal(signal.SIGTERM, lambda *a: threading.Thread(target=srv.shutdown, daemon=True).start())
    except (ValueError, AttributeError):
        pass
    try:
        srv.serve_forever(poll_interval=0.5)
    finally:
        print(stats.line(), flush=True)
        if tail is not None:
            tail.shutdown()
            tail.server_close()
        engine.shutdown()
        srv.server_close()
    return srv


if __name__ == "__main__":
    serve(load_config())
