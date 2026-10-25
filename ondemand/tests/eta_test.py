"""ETA / progress status test (2026-10-24). Starts its own server on 127.0.0.1:8797 (1 worker, always generate, scratch cache,
writer cache OFF = the new default) and compares the predicted time with the real one:
  A  one cached system        (status 'ready', map served from cache in ms)
  B  one fast uncached system (first one also pays the worker start)
  C  one slow TURRETS system  (writer_seconds in the scanner DB between 15 and 40 s)
  D  a 3-request queue        (3 distinct systems at once, 1 worker: positions 1..3, predicted vs real finish time)
plus: the status endpoint never starts a job, input validation, no IP in the log.
Run: python -I ondemand/tests/eta_test.py   -> writes D:/Orca/Temp/claude/od/tests/eta_test.json"""
import json
import sqlite3
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_tests as T  # noqa: E402

OUT = {}


def pick(db, where, order, n, skip=()):
    rows = db.execute(f"SELECT address, preset, writer_seconds, rooms FROM systems WHERE {where} AND address NOT IN "
                      f"(SELECT address FROM layouts) ORDER BY {order} LIMIT 400").fetchall()
    rows = [r for r in rows if r[0] not in skip]
    return rows[:n]


def poll_until_done(s, addr, t0, rec):
    """poll /api/status like the browser; records (t, status, position, eta_s) and the finish time."""
    while True:
        st, b, _ = s.get(f"/api/status/{addr}")
        rec.append((round(time.perf_counter() - t0, 2), b.get("status"), b.get("position"), b.get("eta_s")))
        if b.get("status") in ("ready", "failed"):
            return time.perf_counter() - t0, b
        time.sleep(1.0)


def main():
    db = sqlite3.connect(f"file:{T.DB}?mode=ro", uri=True)
    fast = pick(db, "preset='MEDI_BUGS' AND writer_seconds BETWEEN 0.2 AND 0.6", "address", 6)
    slow = pick(db, "preset LIKE '%TURRETS' AND writer_seconds BETWEEN 15 AND 40", "address", 2)
    mid = pick(db, "preset LIKE '%FLOATERS' AND writer_seconds BETWEEN 1 AND 3", "address", 2)
    bug = pick(db, "preset LIKE '%BUGS' AND writer_seconds BETWEEN 0.3 AND 1", "address DESC", 3)
    s = T.Srv(8797, "--workers", "1", "--no-db-layouts", "--rate-miss", "1000", "--writer-cache", "off", cache="eta-test.sqlite")
    try:
        # status of an unknown-to-the-queue system: nothing is started
        a0 = fast[0][0]
        st, b, _ = s.get(f"/api/status/{a0}")
        health = s.get("/api/health")[1]
        T.say("status of an idle system answers fast with preset/queue/ETA and starts nothing",
              st == 200 and b["status"] == "idle" and b["preset"] and health["queue"] == 0 and health["running"] == 0 and "title" in b["msg"],
              json.dumps({k: b[k] for k in ("status", "preset", "rooms", "eta_s", "upto_s", "slow", "scanner_busy")}))
        OUT["idle_status"] = b
        for path, want in ((f"/api/status/XYZ", 400), ("/api/status/0000010107607CAA", 400), ("/api/status/0000000007607CAA", 404)):
            T.say(f"status {path} -> {want}", s.get(path)[0] == want)
        T.say("POST to status -> 405", s.get(f"/api/status/{a0}", method="POST")[0] == 405)

        # B: fast uncached, cold worker (first request pays the worker start)
        rows = []
        for i, (a, preset, w, rooms) in enumerate(fast[:3]):
            t0 = time.perf_counter()
            pred = s.get(f"/api/status/{a}")[1]
            st, b, _ = s.get(f"/api/map/{a}?wait=0")
            first = b if st == 202 else None
            rec = []
            fin, last = poll_until_done(s, a, t0, rec)
            rows.append({"address": a, "preset": preset, "db_writer_s": w, "predicted_idle_eta": pred["eta_s"],
                         "predicted_after_submit": first and first["eta_s"], "actual_s": round(fin, 2), "cold_worker": i == 0})
            print("B", rows[-1], flush=True)
        OUT["B_fast"] = rows

        # A: cached
        a = fast[1][0]
        st, b, _ = s.get(f"/api/status/{a}")
        t = time.perf_counter()
        st2, m, _ = s.get(f"/api/map/{a}?wait=0")
        dt = time.perf_counter() - t
        T.say("A cached system: status ready, map served from cache in under 100 ms", b["status"] == "ready" and st2 == 200 and dt < 0.1,
              f"status={b['status']} eta={b['eta_s']} map {dt * 1000:.0f} ms")
        OUT["A_cached"] = {"status": b["status"], "map_ms": round(dt * 1000, 1)}

        # C: slow TURRETS (warm worker)
        a, preset, w, rooms = slow[0]
        t0 = time.perf_counter()
        pred = s.get(f"/api/status/{a}")[1]
        st, b, _ = s.get(f"/api/map/{a}?wait=0")
        rec = []
        fin, last = poll_until_done(s, a, t0, rec)
        row = {"address": a, "preset": preset, "db_writer_s": w, "predicted_idle_eta": pred["eta_s"], "predicted_after_submit": b.get("eta_s"),
               "upto_s": pred["upto_s"], "slow_flag": pred["slow"], "title": pred["msg"].get("title"), "kind": pred["msg"].get("kind"),
               "actual_s": round(fin, 2), "polls": rec[:3] + rec[-2:]}
        OUT["C_slow"] = row
        print("C", row, flush=True)
        T.say("C slow TURRETS: flagged slow, wording says 'take longer'", pred["slow"] and "longer" in (pred["msg"].get("kind") or ""), pred["msg"].get("kind"))

        # D: 3-request queue (one worker): a TURRETS-free set so it finishes quickly
        trio = [bug[0], mid[0], bug[1]]
        t0 = time.perf_counter()
        preds, recs, fins = {}, {}, {}
        for r in trio:
            st, b, _ = s.get(f"/api/map/{r[0]}?wait=0")
            preds[r[0]] = (st, b.get("status"), b.get("position"), b.get("queue"), b.get("eta_s"), round(time.perf_counter() - t0, 2))
        threads = []

        def work(r):
            fins[r[0]], _ = poll_until_done(s, r[0], t0, recs.setdefault(r[0], []))
        for r in trio:
            th = threading.Thread(target=work, args=(r,))
            th.start()
            threads.append(th)
        for th in threads:
            th.join()
        qrows = [{"address": r[0], "preset": r[1], "db_writer_s": r[2], "at_submit(status,state,pos,queue,eta_s,t)": preds[r[0]],
                  "actual_finish_s": round(fins[r[0]], 2), "positions_seen": sorted({x[2] for x in recs[r[0]] if x[1] == "queued"}, reverse=True)} for r in trio]
        OUT["D_queue"] = qrows
        for q in qrows:
            print("D", q, flush=True)
        T.say("D queue: positions count down and the last request has the longest ETA",
              preds[trio[2][0]][4] >= preds[trio[1][0]][4] >= preds[trio[0][0]][4], json.dumps([preds[r[0]][2:5] for r in trio]))
    finally:
        log = s.stop()
    T.say("server log holds no IP / address", "127.0.0.1" not in log and "0000" not in log.replace("0000000000000000", ""), "")
    # ratios
    ratios = []
    for r in OUT.get("B_fast", []):
        ratios.append(("B", r["predicted_after_submit"] or r["predicted_idle_eta"], r["actual_s"]))
    c = OUT.get("C_slow")
    if c:
        ratios.append(("C", c["predicted_after_submit"] or c["predicted_idle_eta"], c["actual_s"]))
    for q in OUT.get("D_queue", []):
        ratios.append(("D", q["at_submit(status,state,pos,queue,eta_s,t)"][4], q["actual_finish_s"]))
    OUT["ratios_pred_vs_actual"] = [(k, p, a, round(p / a, 2) if a else None) for k, p, a in ratios]
    print(json.dumps(OUT["ratios_pred_vs_actual"]))
    Path(T.SCRATCH / "eta_test.json").write_text(json.dumps(OUT, indent=1, default=str))
    print("FAILS", T.FAILS)


if __name__ == "__main__":
    main()
