"""Time per uncached map: 1 worker, requests one after the other (so each time is that map alone), on port 8796.
Pass 'cold' (writer cache OFF, true generator cost) or 'warm' (the shared scanner writer cache, as in production).
Sets: the 20 non-top sample systems, plus the slowest TURRETS systems in the scanner DB (by its writer_seconds) and
the slowest non-TURRETS ones.  Worker start-up is timed on a warm-up request and reported separately."""
import json
import sqlite3
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_tests as T  # noqa: E402


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "warm"
    n_slow = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    db = sqlite3.connect(f"file:{T.DB}?mode=ro", uri=True)
    slow_t = [r[0] for r in db.execute("SELECT address FROM systems WHERE preset LIKE '%TURRET%' AND writer_seconds IS NOT NULL "
                                       "ORDER BY writer_seconds DESC LIMIT ?", (n_slow,))]
    slow_o = [r[0] for r in db.execute("SELECT address FROM systems WHERE preset NOT LIKE '%TURRET%' AND writer_seconds IS NOT NULL "
                                       "ORDER BY writer_seconds DESC LIMIT ?", (n_slow,))]
    sample = T.choose_nontop(20)
    args = ["--workers", "1", "--no-db-layouts", "--rate-miss", "1000"]
    if mode == "cold":
        args += ["--writer-cache", "off"]
    s = T.Srv(8796, *args, cache=f"timing-{mode}.sqlite")
    out = {"mode": mode}
    try:
        t0 = time.perf_counter()
        st, _, _ = T.fetch(s, "0000010007607CAA")      # warm-up request: pays the worker start-up
        out["first_request_incl_worker_start_s"] = round(time.perf_counter() - t0, 2)
        for name, addrs in (("sample20", sample), ("slow_turrets", slow_t), ("slow_other", slow_o)):
            rows = []
            for a in addrs:
                st, body, secs = T.fetch(s, a)
                assert st == 200, (a, st)
                rows.append((a, body["m"]["preset"], round(secs, 2), db.execute("SELECT writer_seconds FROM systems WHERE address=?", (a,)).fetchone()[0]))
            ts = [r[2] for r in rows]
            out[name] = {"n": len(ts), "mean": round(statistics.mean(ts), 2), "median": round(statistics.median(ts), 2),
                         "worst": max(ts), "rows": rows}
            print(name, {k: v for k, v in out[name].items() if k != "rows"}, flush=True)
    finally:
        s.stop()
    Path(T.SCRATCH / f"timing-{mode}.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
