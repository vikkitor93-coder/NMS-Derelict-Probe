"""Local derelict viewer: browse region sweeps and generated derelict layouts in the browser.

  python -I viewer/server.py [--port 8765] [--no-browser] [--host 0.0.0.0]

Serves viewer/static/ and a small JSON API (standard library, no packages). By default only this PC can connect
(127.0.0.1); --host 0.0.0.0 shares it on the local network (tools/Derelict-Viewer-LAN.cmd). Anyone on the network can
then browse and use the Generate box (strict hex input only; runs the fast generator, one job at a time).
  GET  /api/regions               summary-<region>.csv files found under the generated folders
  GET  /api/summary/<key>         one summary's rows (key = REGION8 or REGION8-label, from summary-<key>.csv);
                                  floors are recomputed from the room cell masks
  GET  /api/derelict/<ADDRESS16>  one derelict.json (fast generator output first, then the main tool's)
  GET  /api/meshes/index          simple piece meshes index (scene -> mesh id); {} until meshes are built
  GET  /api/meshes/<sha1>.bin     one piece mesh (u32 nv, u32 ni, f32 xyz*nv, u32 idx*ni)
  GET  /api/done                  {"<ADDRESS16>": "<ISO UTC time>", ...}: derelicts the user marked Done (shared by PC and phone)
  POST /api/done                  {"address": "<16 hex>", "done": bool} sets or clears one; returns the full list
                                  (stored in D:/Orca/NMS-Derelict-Probe-analysis/viewer-done.json; other tools may read it)
  POST /api/generate              {"input": "<12 glyph hex or 16 address hex>", "glyphs": bool, "galaxy": int}
                                  runs the fast generator for one derelict and returns {"address": ...}
Generation runs D:/Orca/NMS-Derelict-Probe-fastgen/fast_generate_705.py, one job at a time.
"""
import argparse
import csv
import json
import os
import re
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
_SR = os.environ.get("NMS_STAGING_ROOT")  # stage3 S2: scratch redirect of analysis paths (unset = unchanged)
def _sp(p):
    p = Path(p)
    return Path(_SR) / "analysis" / p.relative_to("D:/Orca/NMS-Derelict-Probe-analysis") if _SR else p
STATIC = HERE / "static"
FAST_GEN = Path("D:/Orca/NMS-Derelict-Probe-fastgen/fast_generate_705.py")
GENERATED = [_sp("D:/Orca/NMS-Derelict-Probe-analysis/emu/fastgen/generated"),
             _sp("D:/Orca/NMS-Derelict-Probe-analysis/emu/generated")]
MESH_CACHE = _sp(Path("D:/Orca/NMS-Derelict-Probe-analysis/meshcache"))  # built by tools/build_piece_meshes_705.py
# floors per derelict.json, keyed by path and mtime; a region's first load otherwise parses hundreds of files (~19 s)
FLOORS_FILE = _sp(Path("D:/Orca/NMS-Derelict-Probe-analysis/viewer-cache/floors.json"))
DONE_FILE = _sp(Path("D:/Orca/NMS-Derelict-Probe-analysis/viewer-done.json"))
DONE_LOCK = threading.Lock()
MESH_FILE = re.compile(r"^[0-9a-f]{40}\.bin$")
HEX16 = re.compile(r"^[0-9A-F]{16}$")
HEX12 = re.compile(r"^[0-9A-F]{12}$")
# summary key = "<REGION8>" or "<REGION8>-<label>" (summary-<key>.csv, e.g. 06607CAA-real)
SUMMARY_KEY = re.compile(r"^[0-9A-F]{8}(-[0-9A-Za-z_]{1,40}(-[0-9A-Za-z_]{1,40})*)?$")
NUMERIC = {"rooms", "instances", "salvage_crates", "footlockers", "floors", "stair_pieces", "hangar_pieces", "seconds"}
GEN_LOCK = threading.Lock()
FLOORS_LOCK = threading.Lock()
_FLOORS_CACHE = {}  # path -> [mtime, floors]
_floors_dirty = False


def load_floors_cache():
    try:
        _FLOORS_CACHE.update(json.loads(FLOORS_FILE.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass


def save_floors_cache():
    global _floors_dirty
    with FLOORS_LOCK:
        if not _floors_dirty:
            return
        snapshot, _floors_dirty = dict(_FLOORS_CACHE), False
    try:
        FLOORS_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = FLOORS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(snapshot), encoding="utf-8")
        tmp.replace(FLOORS_FILE)
    except OSError as exc:
        print("floors cache not saved:", exc, file=sys.stderr)


def cell_floors(address):
    """Number of grid levels occupied by the derelict's rooms, from the room-record cell masks.

    Room record u16[0..5] = inclusive box x0 y0 z0 x1 y1 z1; u16[12..15] = 64-bit mask of occupied box cells,
    bit index z + Z*(y + Y*x). More reliable than counting piece origins (they are corners of rotated pieces).
    """
    global _floors_dirty
    for root in GENERATED:
        path = root / address / "derelict.json"
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        cached = _FLOORS_CACHE.get(str(path))
        if cached and cached[0] == mtime:
            return cached[1]
        levels = set()
        for room in json.loads(path.read_text(encoding="utf-8")).get("rooms", []):
            raw = room["raw_u16_0x00_0x1F"]
            x0, y0, z0, x1, y1, z1 = raw[:6]
            nx, ny, nz = x1 - x0 + 1, y1 - y0 + 1, z1 - z0 + 1
            mask = raw[12] | raw[13] << 16 | raw[14] << 32 | raw[15] << 48
            levels |= {y0 + y for x in range(nx) for y in range(ny) for z in range(nz) if mask >> (z + nz * (y + ny * x)) & 1}
        with FLOORS_LOCK:
            _FLOORS_CACHE[str(path)] = [mtime, len(levels)]
            _floors_dirty = True
        return len(levels)
    return None


def warm_floors():
    """Fill the floors cache for every listed summary in the background, so first page loads are quick."""
    for r in regions():
        summary(r["region"])
    save_floors_cache()


def read_done():
    try:
        data = json.loads(DONE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in data.items() if HEX16.match(k)} if isinstance(data, dict) else {}


def set_done(address, done):
    """Mark or unmark one derelict as Done; atomic write (temp file + os.replace). Returns the new list."""
    with DONE_LOCK:
        data = read_done()
        if done:
            data.setdefault(address, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        else:
            data.pop(address, None)
        DONE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = DONE_FILE.with_name(DONE_FILE.name + ".tmp")
        tmp.write_text(json.dumps(data, indent=1, sort_keys=True), encoding="utf-8")
        os.replace(tmp, DONE_FILE)
        return data


def glyphs_to_address(glyphs, galaxy):
    # same mapping as tools/generate_derelict_705.py --glyphs (planet forced to 0)
    return f"000{glyphs[1:4]}{galaxy & 0xFF:02X}{glyphs[4:6]}{glyphs[6:9]}{glyphs[9:12]}"


def find_derelict(address):
    for root in GENERATED:
        path = root / address / "derelict.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if "instances" in data:
                return data
    return None


def regions():
    seen = {}
    for root in GENERATED:
        for path in sorted(root.glob("summary-*.csv")):
            key = path.stem.removeprefix("summary-")
            if SUMMARY_KEY.match(key) and key not in seen:
                with open(path, encoding="utf-8") as fh:
                    seen[key] = {"region": key, "rows": sum(1 for _ in fh) - 1, "source": str(path)}
    return list(seen.values())


def summary(key):
    for root in GENERATED:
        path = root / f"summary-{key}.csv"
        if path.exists():
            with open(path, encoding="utf-8", newline="") as fh:
                rows = list(csv.DictReader(fh))
            for row in rows:
                for col in NUMERIC & row.keys():
                    try:
                        row[col] = float(row[col]) if col == "seconds" else int(row[col])
                    except (TypeError, ValueError):
                        row[col] = None
                if row.get("status") == "ok" and HEX16.match(row.get("address", "")):
                    floors = cell_floors(row["address"])
                    if floors is not None:
                        row["floors"] = floors
            return rows
    return None


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC), **kwargs)

    def end_headers(self):
        # always revalidate, so an updated app.js/app.css shows on a normal refresh
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.log_date_time_string(), fmt % args))

    def send_json(self, obj, status=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/regions":
            return self.send_json(regions())
        if path.startswith("/api/summary/"):
            key = path.rsplit("/", 1)[1]
            key = key[:8].upper() + key[8:]
            rows = summary(key) if SUMMARY_KEY.match(key) else None
            save_floors_cache()
            return self.send_json(rows) if rows is not None else self.send_json({"error": "unknown region"}, 404)
        if path == "/api/done":
            return self.send_json(read_done())
        if path == "/api/meshes/index":
            index = MESH_CACHE / "index.json"
            return self.send_json(json.loads(index.read_text(encoding="utf-8")) if index.exists() else {})
        if path.startswith("/api/meshes/"):
            name = path.rsplit("/", 1)[1]
            mesh = MESH_CACHE / "pieces" / name
            if not MESH_FILE.match(name) or not mesh.exists():
                return self.send_json({"error": "no such mesh"}, 404)
            body = mesh.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return None
        if path.startswith("/api/derelict/"):
            address = path.rsplit("/", 1)[1].upper()
            data = find_derelict(address) if HEX16.match(address) else None
            return self.send_json(data) if data else self.send_json({"error": "not generated yet"}, 404)
        return super().do_GET()

    def do_POST(self):
        if self.path == "/api/done":
            try:
                req = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length", 0)) or 0, 4096)) or b"{}")
                address, done = str(req.get("address", "")).upper(), req.get("done")
            except (ValueError, TypeError, AttributeError):
                return self.send_json({"error": "bad request"}, 400)
            if not HEX16.match(address) or not isinstance(done, bool):
                return self.send_json({"error": "need address (16 hex digits) and done (true/false)"}, 400)
            try:
                return self.send_json(set_done(address, done))
            except OSError as exc:
                return self.send_json({"error": f"could not save: {exc}"}, 500)
        if self.path != "/api/generate":
            return self.send_json({"error": "not found"}, 404)
        try:
            req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)) or 0) or b"{}")
            text = str(req.get("input", "")).upper().replace(" ", "").replace("-", "")
            galaxy = int(req.get("galaxy", 0))
        except (ValueError, TypeError):
            return self.send_json({"error": "bad request"}, 400)
        if not 0 <= galaxy <= 255:
            return self.send_json({"error": "galaxy must be 0-255"}, 400)
        if req.get("glyphs"):
            if not HEX12.match(text):
                return self.send_json({"error": "glyph code must be 12 hex digits"}, 400)
            address = glyphs_to_address(text, galaxy)
        else:
            if not HEX16.match(text):
                return self.send_json({"error": "address must be 16 hex digits"}, 400)
            address = text
        if find_derelict(address):
            return self.send_json({"address": address, "cached": True})
        if not GEN_LOCK.acquire(blocking=False):
            return self.send_json({"error": "another generation is running; try again shortly"}, 409)
        try:
            proc = subprocess.run([sys.executable, "-I", str(FAST_GEN), address], capture_output=True,
                                  text=True, timeout=1800)
        except subprocess.TimeoutExpired:
            return self.send_json({"error": "generation timed out"}, 504)
        finally:
            GEN_LOCK.release()
        if find_derelict(address):
            return self.send_json({"address": address, "cached": False})
        return self.send_json({"error": "generation failed", "log": (proc.stdout + proc.stderr)[-2000:]}, 500)


def lan_addresses():
    """IPv4 addresses of this PC on private networks (for the printed LAN links)."""
    import socket
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    try:  # the address used for outbound traffic (no packet is sent)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))
            ips.add(s.getsockname()[0])
    except OSError:
        pass
    private = lambda ip: ip.startswith(("192.168.", "10.")) or (ip.startswith("172.") and 16 <= int(ip.split(".")[1]) <= 31)
    return sorted(ip for ip in ips if private(ip))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1", help="bind address; 0.0.0.0 = reachable from the local network")
    ap.add_argument("--done-file", help="Done list file (default: the analysis folder; for tests)")
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    if a.done_file:
        global DONE_FILE
        DONE_FILE = Path(a.done_file)
    load_floors_cache()
    threading.Thread(target=warm_floors, daemon=True).start()
    server = ThreadingHTTPServer((a.host, a.port), Handler)
    url = f"http://127.0.0.1:{a.port}/"
    print("Derelict viewer at", url, "(Ctrl+C to stop)", flush=True)
    if a.host not in ("127.0.0.1", "localhost"):
        for ip in lan_addresses():
            print(f"  on your network: http://{ip}:{a.port}/", flush=True)
    if not a.no_browser:
        threading.Timer(0.5, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
