"""Tests for ondemand_server.py. Starts its own server processes on 127.0.0.1 (ports 8791-8794) with throw-away caches
under a scratch folder; never touches the scanner (8790), never binds anywhere but loopback.

  python -I ondemand/tests/run_tests.py [phase ...]       phases: map top nontop cache limits cors input timing db all
Results are printed as PASS/FAIL lines and written to <scratch>/results.json (real numbers only).
"""
import concurrent.futures as cf
import gzip
import http.client
import json
import random
import sqlite3
import statistics
import subprocess
import sys
import threading
import time
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT.parent
sys.path.insert(0, str(PROBE / "tools"))
SCRATCH = Path("D:/Orca/Temp/claude/od/tests")
SCRATCH.mkdir(parents=True, exist_ok=True)
DB = "D:/Orca/NMS-Derelict-Probe-analysis/emu/fastgen/app-data/derelicts.sqlite"
BUNDLE4 = PROBE / "viewer/static/compact/top100.v4.json.gz"
BUNDLE3 = PROBE / "viewer/static/compact/top100.v3.json.gz"
PUBLIC = "https://vikkitor93-coder.github.io"
RES = {}
FAILS = []


def say(name, ok, note=""):
    print(("PASS  " if ok else "FAIL  ") + name + (f"  -- {note}" if note else ""), flush=True)
    if not ok:
        FAILS.append(name)


class Srv:
    def __init__(self, port, *args, cache="cache.sqlite", fresh=True):
        self.port = port
        c = SCRATCH / f"{cache}"
        if fresh:
            for s in ("", "-wal", "-shm"):
                Path(str(c) + s).unlink(missing_ok=True)
        self.log = open(SCRATCH / f"server-{port}.log", "w")
        self.p = subprocess.Popen([sys.executable, "-I", str(ROOT / "ondemand_server.py"), "--port", str(port),
                                   "--cache-db", str(c), *args], stdout=self.log, stderr=subprocess.STDOUT)
        for _ in range(100):
            try:
                if self.get("/api/health")[0] == 200:
                    return
            except OSError:
                time.sleep(0.2)
        raise RuntimeError("server did not start")

    def get(self, path, headers=None, method="GET", body=None, timeout=200):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        h = {"Accept-Encoding": "gzip", **(headers or {})}
        c.request(method, path, body=body, headers=h)
        r = c.getresponse()
        data = r.read()
        if r.getheader("Content-Encoding") == "gzip":
            data = gzip.decompress(data)
        hdr = {k.lower(): v for k, v in r.getheaders()}
        c.close()
        try:
            return r.status, json.loads(data) if data else None, hdr
        except ValueError:
            return r.status, data, hdr

    def stop(self):
        self.p.terminate()
        try:
            self.p.wait(15)
        except subprocess.TimeoutExpired:
            self.p.kill()
        self.log.close()
        return (SCRATCH / f"server-{self.port}.log").read_text(errors="replace")


def fetch(srv, addr, wait=150, headers=None):
    """Request until a final answer; returns (status, body, seconds)."""
    t = time.perf_counter()
    while True:
        st, body, h = srv.get(f"/api/map/{addr}?wait={wait}", headers)
        if st != 202:
            return st, body, time.perf_counter() - t


# ---------------------------------------------------------------- reference data
def bundle_views():
    b4 = json.loads(gzip.decompress(BUNDLE4.read_bytes()))
    b3 = json.loads(gzip.decompress(BUNDLE3.read_bytes()))
    return b4, b3


def named_view(view, names):
    """View with piece ids replaced by scene names (ids are local to each table)."""
    v = json.loads(json.dumps(view))
    v["i"][0] = [names[k] for k in v["i"][0]]
    return v


def table_rows(t, names_wanted):
    pos = {n: k for k, n in enumerate(t["n"])}
    return {n: [t[c][pos[n]] for c in ("w", "f", "o", "k")] for n in names_wanted}


def choose_top(n=20):
    b4, _ = bundle_views()
    addrs = sorted(b4["s"])
    rnd = random.Random(2410)
    return sorted(rnd.sample(addrs, n))


def choose_nontop(n=20):
    b4, _ = bundle_views()
    top = set(b4["s"])
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = db.execute("SELECT address,preset FROM systems WHERE frigate_modules IS NOT NULL").fetchall()
    rows = [r for r in rows if r[0] not in top]
    rnd = random.Random(2411)
    turrets = [r for r in rows if "TURRET" in r[1]]
    other = [r for r in rows if "TURRET" not in r[1]]
    pick = rnd.sample(turrets, 4) + rnd.sample(other, n - 4)
    return sorted(a for a, _ in pick)


def db_row(addr):
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    return dict(db.execute("SELECT * FROM systems WHERE address=?", (addr,)).fetchone())


# ---------------------------------------------------------------- phases
def phase_top(srv, label, addrs):
    """0 mismatches against the top-100 bundles (v4 as the viewer loads it, and v3 after decode)."""
    import derelict_view_compact as C
    b4, b3 = bundle_views()
    bad, detail, times = 0, [], []
    for a in addrs:
        st, body, secs = fetch(srv, a)
        times.append(secs)
        if st != 200:
            bad += 1
            detail.append((a, st, str(body)[:100]))
            continue
        names = body["t"]["n"]
        mine = named_view(body["s"][a], names)
        ref = named_view(b4["s"][a], b4["t"]["n"])
        ok = mine == ref
        rows_ok = table_rows(body["t"], names) == table_rows(b4["t"], names)
        # also: decode -> v3 and compare with the published format-3 view of the same system (names, not ids)
        v3 = C.decode(body["s"][a], body["t"])
        v3 = named_view(v3, names)
        ref3 = named_view(b3["s"][a], b3["t"]["n"])
        ok3 = v3 == ref3
        if not (ok and rows_ok and ok3):
            bad += 1
            detail.append((a, ok, rows_ok, ok3))
    say(f"top-100 bundle match ({label}): {len(addrs)} systems, mismatches={bad}", bad == 0, str(detail[:3]))
    RES[f"top_{label}"] = {"systems": len(addrs), "mismatches": bad, "seconds": [round(x, 2) for x in times]}


def phase_nontop(srv, addrs):
    import derelict_view_compact as C
    bad, detail, times = 0, [], {}
    for a in addrs:
        st, body, secs = fetch(srv, a)
        times[a] = secs
        row = db_row(a)
        if st != 200:
            bad += 1
            detail.append((a, st, str(body)[:100]))
            continue
        m = body["m"]
        v3 = C.decode(body["s"][a], body["t"])
        kinds = v3["c"][0]
        want = {"preset": row["preset"], "rooms": row["rooms"], "crates": row["crates"], "footlockers": row["footlockers"],
                "modules": row["frigate_modules"], "modules_ambiguous": int(row["frigate_modules_ambiguous"] or 0)}
        got = {"preset": m["preset"], "rooms": m["rooms"], "crates": m["crates"], "footlockers": m["footlockers"],
               "modules": m["modules"], "modules_ambiguous": int(m["modules_ambiguous"] or 0)}
        dec = {"crates": kinds.count(0), "footlockers": kinds.count(1), "rooms": len(v3["r"])}
        if want != got or dec != {k: want[k] for k in dec}:
            bad += 1
            detail.append((a, want, got, dec))
    say(f"non-top systems vs scanner DB: {len(addrs)} systems, mismatches={bad}", bad == 0, str(detail[:2]))
    RES["nontop"] = {"systems": len(addrs), "mismatches": bad,
                     "seconds": {a: round(s, 2) for a, s in times.items()}}
    return times


def phase_cache(srv, addrs):
    ts = []
    for a in addrs:
        for _ in range(3):
            t = time.perf_counter()
            st, body, h = srv.get(f"/api/map/{a}")
            ts.append((time.perf_counter() - t) * 1000)
            assert st == 200
    worst, mean = max(ts), statistics.mean(ts)
    say(f"cache hit under 50 ms: {len(ts)} repeats, mean {mean:.1f} ms, worst {worst:.1f} ms", worst < 50)
    RES["cache_hit_ms"] = {"n": len(ts), "mean": round(mean, 2), "median": round(statistics.median(ts), 2), "worst": round(worst, 2)}


def phase_input(srv):
    cases = [
        ("short", "/api/map/ABC", 400), ("long", "/api/map/" + "A" * 17, 400), ("non-hex", "/api/map/" + "Z" * 16, 400),
        ("empty", "/api/map/", 400), ("traversal", "/api/map/..%2F..%2Fetc", 400), ("dots", "/api/map/../../x", 404),
        ("galaxy 1", "/api/map/0000010007607C01"[:0] + "/api/map/0000010107607CAA", 400),
        ("prefix", "/api/map/1000010007607CAA", 400), ("system 000", "/api/map/0000000007607CAA", 404),
        ("beyond region top", "/api/map/0000FFF004E84EFD", 404), ("bad wait", "/api/map/0000010007607CAA?wait=abc", 400),
        ("unknown route", "/api/summary/x", 404), ("root", "/", 404), ("static", "/viewer/static/app.js", 404),
        ("scanner route", "/api/status", 404), ("health extra", "/api/health/x", 404),
    ]
    bad = []
    for name, path, want in cases:
        st, body, _ = srv.get(path)
        if st != want:
            bad.append((name, path, st, want))
    say(f"bad input / unknown routes: {len(cases)} cases", not bad, str(bad))
    st, _, _ = srv.get("/api/map/0000010007607CAA", method="POST", body=b"x=1", headers={"Content-Type": "text/plain"})
    say("POST refused (405 or 400)", st in (400, 405), f"got {st}")
    st, _, _ = srv.get("/api/health", method="PUT")
    say("PUT refused", st == 405, f"got {st}")
    # body on GET
    c = http.client.HTTPConnection("127.0.0.1", srv.port, timeout=20)
    c.request("GET", "/api/health", body=b"hello", headers={"Content-Length": "5"})
    r = c.getresponse()
    r.read()
    say("GET with a body refused (400)", r.status == 400, f"got {r.status}")
    c.close()
    RES["input"] = {"cases": len(cases), "failed": bad}


def phase_cors(srv):
    path = "/api/health"
    st, _, h = srv.get(path, {"Origin": PUBLIC})
    say("CORS: public site origin allowed", st == 200 and h.get("access-control-allow-origin") == PUBLIC, f"{st} {h.get('access-control-allow-origin')}")
    for o in ("http://localhost:8765", "http://127.0.0.1:3000", "http://localhost"):
        st, _, h = srv.get(path, {"Origin": o})
        say(f"CORS: {o} allowed", st == 200 and h.get("access-control-allow-origin") == o)
    for o in ("https://evil.example", "https://vikkitor93-coder.github.io.evil.com", "http://vikkitor93-coder.github.io",
              "https://other.github.io", "null", "http://localhost.evil.com"):
        st, _, h = srv.get(path, {"Origin": o})
        say(f"CORS: {o} rejected", st == 403 and "access-control-allow-origin" not in h, f"{st}")
    st, _, h = srv.get("/api/map/0000010007607CAA", {"Origin": "https://evil.example"})
    say("CORS: map route rejects other origin", st == 403)
    st, _, h = srv.get(path, method="OPTIONS", headers={"Origin": PUBLIC})
    say("CORS: preflight for the public origin (204)", st == 204 and h.get("access-control-allow-origin") == PUBLIC, f"{st}")
    st, _, h = srv.get(path, method="OPTIONS", headers={"Origin": "https://evil.example"})
    say("CORS: preflight for another origin rejected", st == 403)


def phase_limits():
    # queue cap: 1 worker, cap 3; 9 different uncached non-top systems from 9 different clients at once
    a = Srv(8792, "--workers", "1", "--queue-cap", "3", "--no-db-layouts", cache="cap.sqlite")
    addrs = choose_nontop(30)[10:19]

    def one(i):
        st, body, h = a.get(f"/api/map/{addrs[i]}", {"X-Forwarded-For": f"10.0.0.{i + 1}"})
        return st, h.get("retry-after")
    with cf.ThreadPoolExecutor(9) as ex:
        out = list(ex.map(one, range(9)))
    codes = [s for s, _ in out]
    acc, busy = codes.count(202), codes.count(503)
    say(f"queue cap 3 (1 worker): 9 requests -> {acc}x202, {busy}x503", busy >= 4 and acc <= 5 and acc + busy == 9 and all(r for s, r in out if s == 503),
        str(codes))
    st, body, _ = a.get("/api/health")
    RES["queue_cap"] = {"codes": codes, "health_after": body}
    # drain so the next test is clean
    for ad in addrs[:1]:
        fetch(a, ad)
    log = a.stop()
    say("server log has no IPs or addresses", "10.0.0." not in log and addrs[0] not in log, "")
    # rate limit: miss limiter 3/min; unknown system (cheap 404, still counted) from one client, other client unaffected
    b = Srv(8793, "--rate-miss", "3", "--workers", "1", cache="rate.sqlite")
    codes = [b.get(f"/api/map/0000{0xFF0 + i:03X}0004E84EFD", {"X-Forwarded-For": "192.0.2.7"})[0] for i in range(6)]
    other = b.get("/api/map/0000FF00004E84EFD"[:0] + "/api/map/0000FF30004E84EFD", {"X-Forwarded-For": "192.0.2.8"})[0]
    st, body, h = b.get("/api/map/0000FF40004E84EFD", {"X-Forwarded-For": "192.0.2.7"})
    say(f"rate limit 3/min per client: {codes}, other client {other}",
        codes[:3] == [404] * 3 and codes[3:] == [429] * 3 and other == 404 and st == 429 and "retry-after" in h)
    # real client address (no proxy header) is limited separately from header clients
    st, _, _ = b.get("/api/map/0000FF50004E84EFD")
    say("peer address (no header) has its own bucket", st == 404, f"got {st}")
    RES["rate_limit"] = {"codes": codes, "other_client": other}
    log = b.stop()
    say("rate-limit server log has no IPs", "192.0.2" not in log)
    # global request limiter (any bucket)
    c = Srv(8794, "--workers", "1", cache="any.sqlite")
    codes = [c.get("/api/health", {"X-Forwarded-For": "198.51.100.1"})[0] for _ in range(125)]
    say(f"any-request limiter 120/min: {codes.count(200)}x200 then {codes.count(429)}x429", codes.count(200) == 120 and codes.count(429) == 5)
    c.stop()


def phase_db(top_addrs):
    s = Srv(8795, cache="dbl.sqlite")        # use_db_layouts on
    t = []
    for a in top_addrs[:5]:
        st, body, secs = fetch(s, a)
        t.append(secs)
        assert st == 200 and body["m"]["source"] == "scanner-db-layout", body["m"] if st == 200 else st
    say(f"scanner-DB layouts used without generating: 5 systems, max {max(t):.2f} s", max(t) < 3, "")
    phase_top(s, "db-layout", top_addrs)
    s.stop()


def phase_timing(slow):
    s = Srv(8791, "--workers", "1", "--no-db-layouts", cache="timing.sqlite")
    return s


def main():
    phases = sys.argv[1:] or ["all"]
    top = choose_top(20)
    non = choose_nontop(20)
    json.dump({"top": top, "nontop": non}, open(SCRATCH / "samples.json", "w"))
    if "all" in phases or "map" in phases or "top" in phases or "nontop" in phases or "cache" in phases or "input" in phases or "cors" in phases:
        s = Srv(8791, "--workers", "2", "--no-db-layouts", cache="main.sqlite")
        try:
            t0 = time.time()
            phase_top(s, "generated", top)
            phase_nontop(s, non)
            phase_cache(s, top[:10] + non[:10])
            phase_input(s)
            phase_cors(s)
            st, h, _ = s.get("/api/health")
            RES["health_after"] = h
            say(f"health: {h}", st == 200 and h["ok"] is True)
            RES["main_wall_s"] = round(time.time() - t0, 1)
        finally:
            log = s.stop()
            RES["main_log_tail"] = log.strip().splitlines()[-3:]
            say("server log has no addresses/IPs", not any(a in log for a in top + non) and "127.0.0.1 -" not in log)
    if "all" in phases or "limits" in phases:
        phase_limits()
    if "all" in phases or "db" in phases:
        phase_db(top)
    (SCRATCH / "results.json").write_text(json.dumps(RES, indent=1))
    print("FAILS:", FAILS or "none")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
