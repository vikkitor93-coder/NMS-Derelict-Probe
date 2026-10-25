"""Runs the phases of the ORIGINAL run_tests.py that do not need the real renderer/bundles, against the stub generator.
The original main() cannot start without viewer/static/compact/top100.v4.json.gz (lost/not in the tree), so this harness:
  - imports run_tests as T (unchanged copy), replaces T.bundle_views by an empty bundle (nothing is "top")
  - needs a fixture scanner DB at T.DB and ondemand/config.json {"generator":"stub", "scanner_db": <same fixture>}
  - runs: input, cors, cache, limits  (skipped: top / nontop / db, they compare against the real bundles and decode with
    derelict_view_compact; timing needs real generation time)
python -I ondemand/tests/run_original_phases_stub.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_tests as T  # noqa: E402

T.bundle_views = lambda: ({"s": {}}, {"s": {}})
non = T.choose_nontop(30)
s = T.Srv(8791, "--workers", "2", "--no-db-layouts", cache="main.sqlite")
try:
    for a in non[:6]:
        st, body, secs = T.fetch(s, a)
        T.say(f"fetch {st}", st == 200)
    T.phase_cache(s, non[:6])
    T.phase_input(s)
    T.phase_cors(s)
    st, h, _ = s.get("/api/health")
    T.say(f"health: {h}", st == 200 and h["ok"] is True)
finally:
    log = s.stop()
T.say("server log has no addresses/IPs", not any(a in log for a in non) and "127.0.0.1 -" not in log)
T.phase_limits()
print("FAILS:", T.FAILS or "none")
