"""Stub-generator tests for ondemand_server.py (stage 2 / A4).  Own fixtures, no real generator, no real scanner DB.

Starts throw-away servers on 127.0.0.1 only (ports 18801-18809) with `--generator stub`, a fixture scanner DB and a scratch
cache; stops them afterwards.  Nothing is exposed.  Run:  python -I ondemand/tests/stub_test.py [scratch-dir]
What it covers: map 202->200 flow + cache, /api/status (idle starts nothing, queued/generating/ready/failed, stages, ETA, slow,
scanner_busy), queue cap (4x202 + 5x503), 429 rate limits, CORS 403/204, bad input 400/404/405, scanner DB read-only and
optional, scanner-DB layout path, existence via region count, job timeout, generator failure, BelowNormal worker, loopback bind,
no IP/address in the log.
"""
import concurrent.futures as cf
import gzip
import hashlib
import http.client
import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp(prefix="od-stub-"))
SCRATCH.mkdir(parents=True, exist_ok=True)
PUBLIC = "https://vikkitor93-coder.github.io"
FAILS, PASSES = [], []
sys.path.insert(0, str(ROOT))
import stub_generator as G  # noqa: E402


def say(name, ok, note=""):
    print(("PASS  " if ok else "FAIL  ") + name + (f"  -- {note}" if note else ""), flush=True)
    (PASSES if ok else FAILS).append(name)


def addr(sss, region="07607CAA"):
    return f"000{sss:03X}00{region}"


def make_scanner_db(path):
    Path(path).unlink(missing_ok=True)
    db = sqlite3.connect(path)
    db.executescript(
        "CREATE TABLE systems(address TEXT PRIMARY KEY, preset TEXT, rooms INT, crates INT, footlockers INT,"
        " frigate_modules INT, frigate_modules_ambiguous INT, writer_seconds REAL, total_seconds REAL);"
        "CREATE TABLE regions(galaxy INT, region TEXT, count INT);"
        "CREATE TABLE layouts(address TEXT PRIMARY KEY, json_z BLOB);")
    db.execute("INSERT INTO regions VALUES(0,'07607CAA',500)")
    lay = G.layout_of(addr(5))
    lay["preset"] = "CARGO_BUGS"
    db.execute("INSERT INTO systems VALUES(?,?,?,?,?,?,?,?,?)", (addr(5), "CARGO_BUGS", len(lay["rooms"]), 1, 1, 3, 0, 0.5, 1.0))
    db.execute("INSERT INTO layouts VALUES(?,?)", (addr(5), zlib.compress(json.dumps(lay).encode())))
    db.execute("INSERT INTO systems VALUES(?,?,?,?,?,?,?,?,?)", (addr(6), "MEDI_TURRETS", 10, 1, 1, 3, 0, 34.4, 35.0))
    db.execute("INSERT INTO systems VALUES(?,?,?,?,?,?,?,?,?)", (addr(7), "MEDI_BUGS", 8, 1, 1, 3, 0, 0.4, 1.0))
    db.commit()
    db.close()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Srv:
    def __init__(self, port, *args, env=None, cache=None, scanner_db=None, fresh=True):
        self.port = port
        c = SCRATCH / (cache or f"cache-{port}.sqlite")
        if fresh:
            for s in ("", "-wal", "-shm"):
                Path(str(c) + s).unlink(missing_ok=True)
        self.log_path = SCRATCH / f"server-{port}.log"
        self.log = open(self.log_path, "w")
        self.p = subprocess.Popen(
            [sys.executable, "-I", str(ROOT / "ondemand_server.py"), "--port", str(port), "--generator", "stub",
             "--cache-db", str(c), "--scanner-db", scanner_db or str(SCRATCH / "scanner.sqlite"),
             "--work-dir", str(SCRATCH / f"work-{port}"), "--log-dir", str(SCRATCH / f"logs-{port}"),
             "--eta-config", str(ROOT / "eta_config.json"), *args],
            stdout=self.log, stderr=subprocess.STDOUT, env={**os.environ, **(env or {})})
        for _ in range(100):
            try:
                if self.get("/api/health")[0] == 200:
                    return
            except OSError:
                time.sleep(0.2)
        raise RuntimeError("server did not start")

    def get(self, path, headers=None, method="GET", body=None, timeout=60):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        c.request(method, path, body=body, headers={"Accept-Encoding": "gzip", **(headers or {})})
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
        return self.log_path.read_text(errors="replace")

    def fetch(self, a, wait=20, headers=None):
        t = time.perf_counter()
        for _ in range(200):
            st, body, h = self.get(f"/api/map/{a}?wait={wait}", headers)
            if st != 202:
                return st, body, time.perf_counter() - t
        raise RuntimeError("never finished")

    def poll_ready(self, a, limit=60):
        seen = []
        t = time.time()
        while time.time() - t < limit:
            st, b, _ = self.get(f"/api/status/{a}")
            seen.append((b["status"], b["stage"], b["position"]))
            if b["status"] in ("ready", "failed"):
                return b, seen
            time.sleep(0.15)
        return None, seen


def priority_of_stub_workers(port_dir_marker):
    """Win32_Process.Priority of python processes running stub_generator.py (6 = Below Normal)."""
    if sys.platform != "win32":
        return None
    ps = ("Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.CommandLine -like '*stub_generator.py*' } | "
          "ForEach-Object { $_.Priority }")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=60).stdout.split()
    return [int(x) for x in out if x.isdigit()]


def main():
    db_path = str(SCRATCH / "scanner.sqlite")
    make_scanner_db(db_path)
    before = sha(db_path)
    a_new = addr(0x10)              # not in scanner DB, region known (500) -> exists
    a_new2 = addr(0x11)
    a_gone = addr(0x1F0)            # beyond region top (500-1-8=491=0x1EB)
    a_db = addr(5)                  # scanner DB layout
    a_slow = addr(6)                # MEDI_TURRETS, writer 34.4 s in the DB

    # ------------------------------------------------------------ main server
    s = Srv(18801, "--workers", "2", "--rate-miss", "1000", "--stats-every", "2", env={"STUB_DELAY_S": "0.4"})
    try:
        st, h, _ = s.get("/api/health")
        say("health: ok + counters", st == 200 and h["ok"] is True and {"queue", "running", "cache_entries", "cache_bytes", "clients_1min"} <= set(h), str(h))

        # status of an idle (never requested) system: answers, starts nothing
        t = time.perf_counter()
        st, b, _ = s.get(f"/api/status/{a_new}")
        dt = time.perf_counter() - t
        health = s.get("/api/health")[1]
        need = {"status", "stage", "preset", "rooms", "position", "queue", "running", "eta_s", "elapsed_s", "overdue", "slow",
                "upto_s", "scanner_busy", "poll_ms", "msg"}
        say("status idle: 200, all fields, fast, starts nothing",
            st == 200 and need <= set(b) and b["status"] == "idle" and b["stage"] == 0 and b["preset"] == G.preset_of(a_new)
            and dt < 0.5 and health["queue"] == 0 and health["running"] == 0 and "title" in b["msg"] and b["msg"]["stages"] == [
                "Waiting in queue", "Checking the system", "Generating layout", "Packing map", "Done"],
            f"{dt * 1000:.0f} ms preset={b.get('preset')} eta={b.get('eta_s')}")
        say("status idle cold worker: ETA includes the 6 s worker start (> 6)", b["eta_s"] > 6, str(b["eta_s"]))
        st, b2, _ = s.get(f"/api/status/{a_slow}")
        say("status of a DB system: preset + rooms from the scanner DB, TURRETS flagged slow with 'longer' wording, upto_s set",
            b2["preset"] == "MEDI_TURRETS" and b2["rooms"] == 10 and b2["slow"] is True and "longer" in b2["msg"]["kind"] and b2["upto_s"] >= 30
            and b2["msg"]["rooms"] == "10 rooms", json.dumps({k: b2[k] for k in ("preset", "rooms", "slow", "upto_s", "eta_s")}))
        for path, want in ((f"/api/status/XYZ", 400), ("/api/status/0000010107607CAA", 400), ("/api/status/0000000007607CAA", 404),
                           (f"/api/status/{a_gone}", 404), ("/api/status", 404), ("/api/status/" + "A" * 17, 400)):
            say(f"status {path} -> {want}", s.get(path)[0] == want)
        say("POST to status -> 405", s.get(f"/api/status/{a_new}", method="POST")[0] == 405)

        # map flow: 202 first (wait=0), then ready, then served from cache
        st, b, _ = s.get(f"/api/map/{a_new}?wait=0")
        say("map ?wait=0 starts the job without holding the connection: 202 with status fields",
            st == 202 and b["status"] in ("queued", "generating") and "eta_s" in b and "queue" in b and b["retry_after"] >= 1, str(st))
        fin, seen = s.poll_ready(a_new)
        stages = [x[1] for x in seen]
        say("status polls end in ready; stage never goes backwards and reaches 4",
            fin is not None and fin["status"] == "ready" and fin["stage"] == 4 and stages == sorted(stages), str(seen[-6:]))
        st, body, h = s.get(f"/api/map/{a_new}")
        m = body["m"]
        lay = G.layout_of(a_new)
        say("map 200 body: v4 bundle {v,t,s,m} with the summary",
            st == 200 and body["v"] == 4 and a_new in body["s"] and "t" in body and m["address"] == a_new and m["preset"] == lay["preset"]
            and m["rooms"] == len(lay["rooms"]) and m["crates"] == lay["container_kinds"]["salvage_crate"]
            and m["modules"] == lay["frigate"][0] and m["source"] == "generated" and h.get("cache-control", "").startswith("public"),
            json.dumps(m))
        ts = []
        for _ in range(30):
            t = time.perf_counter()
            st, _b, _h = s.get(f"/api/map/{a_new}")
            ts.append((time.perf_counter() - t) * 1000)
        say(f"cache hit: 30 repeats all 200, worst {max(ts):.1f} ms (< 50)", max(ts) < 50)
        st, b, _ = s.get(f"/api/status/{a_new}")
        say("status of a cached map: ready, eta 0, stage 4", b["status"] == "ready" and b["eta_s"] == 0 and b["stage"] == 4)
        hl = s.get("/api/health")[1]
        say("health counts cache entries", hl["cache_entries"] >= 1 and hl["cache_bytes"] > 0, str(hl))

        # DB layout path
        st, body, secs = s.fetch(a_db)
        say("scanner-DB layout used without generating (source scanner-db-layout, modules from DB)",
            st == 200 and body["m"]["source"] == "scanner-db-layout" and body["m"]["modules"] == 3, f"{secs:.2f}s")
        # existence
        st, b, _ = s.get(f"/api/map/{a_gone}")
        say("system beyond the region top -> 404 (existence rule: 1 <= idx <= count-1-margin)", st == 404, str(st))
        unseen = addr(0x20, "05001234")
        st, body, _ = s.fetch(unseen)
        say("system in a region the scanner never counted: region count taken from the counter, exists -> 200", st == 200)
        st, body, _ = s.fetch(addr(0x7FF, "05001234"))
        say("same region (count now stored): index beyond the top -> 404", st == 404, str(st))
        st, b, _ = s.get(f"/api/status/{addr(0x7FF, '05001234')}")
        say("status of a system the job just found nonexistent: failed with http 404 (or 404)", (st == 404) or (b["status"] == "failed" and b["http"] == 404), f"{st}")

        # bad input / routes
        cases = [("short", "/api/map/ABC", 400), ("long", "/api/map/" + "A" * 17, 400), ("non-hex", "/api/map/" + "Z" * 16, 400),
                 ("empty", "/api/map/", 400), ("traversal", "/api/map/..%2F..%2Fetc", 400), ("dots", "/api/map/../../x", 404),
                 ("galaxy 1", "/api/map/0000010107607CAA", 400), ("prefix", "/api/map/1000010007607CAA", 400),
                 ("system 000", "/api/map/0000000007607CAA", 404), ("bad wait", f"/api/map/{a_new}?wait=abc", 400),
                 ("nan wait", f"/api/map/{a_new}?wait=nan", 400),
                 ("unknown route", "/api/summary/x", 404), ("root", "/", 404), ("static", "/viewer/static/app.js", 404),
                 ("health extra", "/api/health/x", 404)]
        bad = [(n, p, s.get(p)[0], w) for n, p, w in cases if s.get(p)[0] != w]
        say(f"bad input / unknown routes: {len(cases)} cases", not bad, str(bad))
        say("POST refused 405", s.get(f"/api/map/{a_new}", method="POST", body=b"x=1")[0] == 405)
        say("PUT / DELETE refused 405", s.get("/api/health", method="PUT")[0] == 405 and s.get("/api/health", method="DELETE")[0] == 405)
        c = http.client.HTTPConnection("127.0.0.1", s.port, timeout=20)
        c.request("GET", "/api/health", body=b"hello", headers={"Content-Length": "5"})
        r = c.getresponse()
        r.read()
        say("GET with a body refused (400)", r.status == 400)
        c.close()

        # CORS
        st, _, h = s.get("/api/health", {"Origin": PUBLIC})
        say("CORS: public origin allowed", st == 200 and h.get("access-control-allow-origin") == PUBLIC)
        for o in ("http://localhost:8765", "http://127.0.0.1:3000"):
            st, _, h = s.get("/api/health", {"Origin": o})
            say(f"CORS: {o} allowed", st == 200 and h.get("access-control-allow-origin") == o)
        for o in ("https://evil.example", PUBLIC + ".evil.com", "http://vikkitor93-coder.github.io", "null", "http://localhost.evil.com"):
            st, _, h = s.get("/api/health", {"Origin": o})
            say(f"CORS: {o} -> 403 without ACAO", st == 403 and "access-control-allow-origin" not in h)
        for route in (f"/api/map/{a_new}", f"/api/status/{a_new}"):
            say(f"CORS: {route[:11]} rejects another origin", s.get(route, {"Origin": "https://evil.example"})[0] == 403)
        say("CORS: preflight 204 for the public origin, 403 for another",
            s.get("/api/health", method="OPTIONS", headers={"Origin": PUBLIC})[0] == 204 and s.get("/api/health", method="OPTIONS", headers={"Origin": "https://evil.example"})[0] == 403)

        # worker priority + at most 2 workers
        prio = priority_of_stub_workers(None)
        say("generator workers run at BelowNormal (Win32 Priority 6)", prio is None or (len(prio) >= 1 and all(p == 6 for p in prio)), str(prio))
        say("at most 2 worker processes", prio is None or len(prio) <= 2, str(prio))
        time.sleep(2.5)                      # let one stats line get printed
    finally:
        log = s.stop()
    say("log holds no IP and no address", "127.0.0.1" not in log and not any(x in log for x in (a_new, a_db, a_slow, a_gone, unseen)), log.strip()[:200])
    say("log has the aggregate stats line", "stats up=" in log)
    say("scanner DB file untouched by the server (sha256 equal)", sha(db_path) == before)

    # ------------------------------------------------------------ queue states + ETA
    q = Srv(18802, "--workers", "1", "--rate-miss", "1000", "--rate-any", "100000", "--no-db-layouts", env={"STUB_DELAY_S": "0.6"})
    try:
        addrs = [addr(0x30 + i) for i in range(3)]
        pre = [q.get(f"/api/status/{a}")[1]["eta_s"] for a in addrs]
        out = [q.get(f"/api/map/{a}?wait=0") for a in addrs]
        say("3 requests, 1 worker: all 202", [o[0] for o in out] == [202] * 3, str([o[0] for o in out]))
        etas = [o[1]["eta_s"] for o in out]
        say("ETA grows with queue position (free-slot simulation)", etas[0] <= etas[1] <= etas[2] and etas[2] > etas[0], str(etas))
        st, b, _ = q.get(f"/api/status/{addrs[2]}")
        say("queued job: status queued, position >= 1, queue count, text 'Position n of m'",
            b["status"] in ("queued", "generating") and (b["status"] != "queued" or (b["position"] >= 1 and "Position" in b["msg"]["queue"])), json.dumps({k: b[k] for k in ("status", "position", "queue", "stage", "eta_s")}))
        pos_seen = set()
        t0 = time.time()
        while time.time() - t0 < 30:
            sts = [q.get(f"/api/status/{a}")[1] for a in addrs]
            pos_seen.update(x["position"] for x in sts)
            if all(x["status"] == "ready" for x in sts):
                break
            time.sleep(0.1)
        say("all three finish; positions counted down", all(x["status"] == "ready" for x in sts) and max(pos_seen) >= 1, str(sorted(pos_seen)))
    finally:
        q.stop()

    # ------------------------------------------------------------ queue cap: 4x202 + 5x503
    c3 = Srv(18803, "--workers", "1", "--queue-cap", "3", "--no-db-layouts", "--rate-miss", "1000", env={"STUB_DELAY_S": "1.5"})
    try:
        addrs = [addr(0x40 + i) for i in range(9)]

        def one(i):
            st, body, h = c3.get(f"/api/map/{addrs[i]}?wait=0", {"X-Forwarded-For": f"10.0.0.{i + 1}"})
            return st, h.get("retry-after")
        with cf.ThreadPoolExecutor(9) as ex:
            out = list(ex.map(one, range(9)))
        codes = [x[0] for x in out]
        say(f"queue cap 3 + 1 worker, 9 simultaneous distinct requests -> {codes.count(202)}x202 + {codes.count(503)}x503",
            codes.count(202) == 4 and codes.count(503) == 5 and all(r for s_, r in out if s_ == 503), str(codes))
        say("health shows queue + running", c3.get("/api/health")[1]["queue"] >= 1)
        # an already running job can still be joined when the queue is full
        first_ok = addrs[codes.index(202)]
        joined = c3.get(f"/api/map/{first_ok}?wait=0")[0]
        say("a full queue still lets visitors join an existing job (202)", joined == 202, str(joined))
    finally:
        log = c3.stop()
    say("queue-cap server log has no client IPs", "10.0.0." not in log)

    # ------------------------------------------------------------ rate limits
    r = Srv(18804, "--rate-miss", "3", "--workers", "1", env={"STUB_DELAY_S": "0.2"})
    try:
        codes = [r.get(f"/api/map/{addr(0x1F0 + i)}", {"X-Forwarded-For": "192.0.2.7"})[0] for i in range(6)]
        other = r.get(f"/api/map/{addr(0x1F8)}", {"X-Forwarded-For": "192.0.2.8"})[0]
        st, _, h = r.get(f"/api/map/{addr(0x1F9)}", {"X-Forwarded-For": "192.0.2.7"})
        say(f"miss limit 3/min per client: {codes}, other client {other}",
            codes[:3] == [404] * 3 and codes[3:] == [429] * 3 and other == 404 and st == 429 and "retry-after" in h)
        say("peer address (no header) has its own bucket", r.get(f"/api/map/{addr(0x1FA)}")[0] == 404)
        say("status is not charged to the miss limiter", all(r.get(f"/api/status/{addr(0x50)}", {"X-Forwarded-For": "192.0.2.7"})[0] == 200 for _ in range(10)))
    finally:
        log = r.stop()
    say("rate-limit server log has no IPs", "192.0.2" not in log)
    a2 = Srv(18805, "--workers", "1")
    try:
        codes = [a2.get("/api/health", {"X-Forwarded-For": "198.51.100.1"})[0] for _ in range(125)]
        say(f"any-request limit 120/min: {codes.count(200)}x200 then {codes.count(429)}x429", codes.count(200) == 120 and codes.count(429) == 5)
        say("clients_1min counts distinct clients", a2.get("/api/health", {"X-Forwarded-For": "198.51.100.2"})[1]["clients_1min"] >= 2)
    finally:
        a2.stop()

    # ------------------------------------------------------------ failures: timeout, generator failure
    t = Srv(18806, "--workers", "1", "--job-timeout", "1", "--no-db-layouts", "--rate-miss", "1000", env={"STUB_HANG_S": "6"})
    try:
        ta = addr(0x60)
        st, body, secs = t.fetch(ta, wait=10)
        say("generation over job_timeout is killed -> 503 busy with Retry-After", st == 503 and body.get("error") == "busy", f"{st} {secs:.1f}s")
        st, b, _ = t.get(f"/api/status/{ta}")
        say("status of the failed job: failed + http 503 + retry_after", b["status"] == "failed" and b["http"] == 503 and b["retry_after"] > 0, str(b.get("status")))
        stt = t.get(f"/api/map/{ta}")
        say("repeat request within the failure window answers 503 at once", stt[0] == 503 and "retry-after" in stt[2])
    finally:
        t.stop()
    f = Srv(18807, "--workers", "1", "--no-db-layouts", "--rate-miss", "1000", env={"STUB_FAIL": "1", "STUB_DELAY_S": "0.1"})
    try:
        st, body, _ = f.fetch(addr(0x61))
        say("generator failure (code != 0) -> 503 'failed', server keeps serving", st == 503 and f.get("/api/health")[0] == 200, f"{st} {body}")
    finally:
        f.stop()

    # ------------------------------------------------------------ scanner DB optional + busy flag
    nodb = Srv(18808, "--workers", "1", "--rate-miss", "1000", scanner_db=str(SCRATCH / "missing.sqlite"), env={"STUB_DELAY_S": "0.1"})
    try:
        st, body, _ = nodb.fetch(addr(0x70))
        stt, b, _ = nodb.get(f"/api/status/{addr(0x71)}")
        say("no scanner DB at all: map still generated (region counter fallback), status answers, scanner_busy false",
            st == 200 and stt == 200 and b["scanner_busy"] is False and b["preset"], f"{st} {stt}")
    finally:
        nodb.stop()
    sb_db = str(SCRATCH / "busy.sqlite")
    make_scanner_db(sb_db)                              # just written -> "scanner busy"
    bz = Srv(18809, "--workers", "1", scanner_db=sb_db)
    try:
        b = bz.get(f"/api/status/{a_slow}")[1]
        old = time.time() - 600
        os.utime(sb_db, (old, old))
        b2 = bz.get(f"/api/status/{a_slow}")[1]
        say("scanner_busy follows the scanner DB's last write; busy raises the ETA by the load factor and shows the note",
            b["scanner_busy"] is True and b2["scanner_busy"] is False and b["eta_s"] > b2["eta_s"] and b["msg"]["busy"] and not b2["msg"]["busy"],
            f"busy eta {b['eta_s']} vs idle {b2['eta_s']}")
    finally:
        bz.stop()

    # ------------------------------------------------------------ loopback only
    lan = None
    try:
        lan = socket.gethostbyname(socket.gethostname())
    except OSError:
        pass
    lb = Srv(18810, "--workers", "1", "--tailnet-bind", "192.168.1.5", "--relay-ip", "192.168.1.9")
    try:
        refused = None
        if lan and not lan.startswith("127."):
            try:
                socket.create_connection((lan, 18810), timeout=3).close()
                refused = False
            except OSError:
                refused = True
        say("listener is loopback only: LAN address refuses the port" + ("" if lan else " (no LAN address, skipped)"), refused in (True, None), f"lan={'set' if lan else 'none'}")
        log = open(lb.log_path).read()
    finally:
        log = lb.stop()
    say("non-Tailscale tailnet_bind: relay listener NOT started", "relay listener=off" in log and "NOT started" in log)

    print(f"\n{len(PASSES)} passed, {len(FAILS)} failed")
    if FAILS:
        print("FAILS:", FAILS)
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
