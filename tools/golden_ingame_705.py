"""Check the derelict chain against every user-confirmed in-game fact (tools/golden_ingame_705.json).

    python -I tools/golden_ingame_705.py [--quick] [--profile 7.05|stock|<build_id>] [--full-profile] [--json]

--quick      only the pure-Python seed checks (captured reward seeds -> item/amount; milliseconds, any python)
default      also the full chain for the golden systems (fresh layouts, space POI, crate loot, end reward), run in one
             persistent tools/compare_builds_worker_705.py (Shipwright python, a few seconds per system).
--profile    which build to check. Default 7.05 with the space-POI step pinned to the 7.05 exe + game-data snapshot
             (so an installed game update cannot leak in); 'stock' = exactly what the scanner runs;
             --full-profile = all of tools/build_profile_705.apply_profile (the path a new build uses).
Exit 0 = all checks passed. Used by minimap/check_update.py, tools/update_guard_705.py (quick) and
tools/compare_builds_705.py (full, on the new build).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
DATA = HERE / "golden_ingame_705.json"
EMU_PY = os.environ.get("EMU_PYTHON", os.path.expandvars("%USERPROFILE%/tools/NMS-Shipwright/.venv/Scripts/python.exe"))
WORKER = HERE / "compare_builds_worker_705.py"
BELOW_NORMAL = 0x4000 if os.name == "nt" else 0


def golden() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def quick_checks(g: dict | None = None) -> dict:
    """Captured in-game reward seeds -> the predictor's item / amount / class (pure Python)."""
    import predict_crate_loot_705 as C
    g = g or golden()
    res = {"checks": [], "passed": 0, "failed": 0, "total": 0}

    def add(ok, name, detail):
        res["checks"].append(["PASS" if ok else "FAIL", name, detail])
        res["passed" if ok else "failed"] += 1
        res["total"] += 1
    for run in g["seed_runs"]:
        got = {}
        for s in run["seeds"]:
            lo = C.loot(int(s["seed"], 16), run["table"], run["address"])
            item, amount, cls = lo.get("id") or lo.get("key"), lo.get("amount"), lo.get("tech_class")
            got[s["seq"]] = (item, amount)
            want = [s["item"], s.get("amount"), s.get("class")]
            have = [item, amount if "amount" in s else None, cls if "class" in s else None]
            add(want == have, f"{run['name']} #{s['seq']}", f"expected {want}, predicted {[item, amount, cls]}")
        for sm in run.get("sums", []):
            items = {got[q][0] for q in sm["seqs"]}
            total = sum(got[q][1] or 0 for q in sm["seqs"])
            add(items == {sm["item"]} and total == sm["amount"], f"{run['name']} #{'+'.join(map(str, sm['seqs']))}",
                f"expected {sm['item']} x{sm['amount']}, predicted {sorted(items)} x{total}")
    return res


def evaluate(records: dict, g: dict | None = None) -> dict:
    """records: {address: compare_builds_worker record} -> layout / container / end-reward checks."""
    g = g or golden()
    res = {"checks": [], "passed": 0, "failed": 0, "total": 0}

    def add(ok, name, detail):
        res["checks"].append(["PASS" if ok else "FAIL", name, detail])
        res["passed" if ok else "failed"] += 1
        res["total"] += 1
    for lay in g["layouts"]:
        r = records.get(lay["address"]) or {}
        if "error" in r or not r:
            add(False, f"layout {lay['address']}", f"no result: {r.get('error')}")
            continue
        got = {"seed": r["seed"], "preset": r["preset"], "rooms": len(r["rooms"]), "crates": len(r["crates"]),
               "footlockers": len(r["footlockers"]), "instances": r["pieces"]["n"]}
        want = {k: lay[k] for k in got if k in lay}
        diff = {k: (want[k], got[k]) for k in want if want[k] != got[k]}
        add(not diff, f"layout {lay['address']} ({lay['preset']})",
            "rooms/crates/footlockers " + f"{got['rooms']}/{got['crates']}/{got['footlockers']}" + (f"; DIFF {diff}" if diff else ""))
    for er in g["end_rewards"]:
        r = records.get(er["address"]) or {}
        got = (r.get("end_reward") or ["", ""])[:2]
        add(got == [er["name"], er["class"]], f"end reward {er['address']}", f"expected {er['name']} {er['class']}, predicted {' '.join(got)}")
    for c in g["containers"]:
        r = records.get(c["address"]) or {}
        cands = [x for x in r.get("loot", []) if x[0] == c["kind"] and x[1] == c["room"]]
        want = [c["item"], c.get("amount"), c.get("class")]
        hits = [x for x in cands if [x[5], x[6] if "amount" in c else None, x[7] if "class" in c else None] == want]
        add(bool(hits), f"{c['kind']} {c['address']} room {c['room']}",
            f"expected {want}, predicted {[(x[5], x[6], x[7]) for x in cands] or 'no such container'}")
    return res


def full_addresses(g: dict | None = None) -> list[str]:
    g = g or golden()
    out = [x["address"] for x in g["layouts"]] + [x["address"] for x in g["end_rewards"]] + [x["address"] for x in g["containers"]]
    return list(dict.fromkeys(out))


def run_worker(addresses, profile="7.05", pin_only=True, log=None) -> dict:
    args = [EMU_PY, "-I", str(WORKER), "--profile", profile] + (["--pin-only"] if pin_only else [])
    p = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log or subprocess.DEVNULL,
                         text=True, bufsize=1, creationflags=BELOW_NORMAL)
    try:
        ready = json.loads(p.stdout.readline() or "{}")
        if not ready.get("ready"):
            raise RuntimeError("golden worker did not start (see its log)")
        out = {}
        for a in addresses:
            p.stdin.write(json.dumps({"address": a}) + "\n")
            p.stdin.flush()
            r = json.loads(p.stdout.readline())
            out[a] = r
        return out
    finally:
        p.stdin.close()
        p.wait(timeout=120)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--profile", default="7.05")
    ap.add_argument("--full-profile", action="store_true", help="apply the whole profile, not only the POI pin")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    g = golden()
    q = quick_checks(g)
    parts = {"seed checks (pure Python)": q}
    if not a.quick:
        with open(os.devnull, "w") as dn:
            recs = run_worker(full_addresses(g), a.profile, pin_only=(a.profile != "stock" and not a.full_profile), log=dn)
        parts["full chain (fresh layouts, POI, loot, end reward)"] = evaluate(recs, g)
    passed = sum(p["passed"] for p in parts.values())
    total = sum(p["total"] for p in parts.values())
    if a.json:
        print(json.dumps({"passed": passed, "total": total, "failed": total - passed, "profile": a.profile,
                          "parts": parts}, indent=1))
    else:
        for name, p in parts.items():
            print(f"== {name}: {p['passed']}/{p['total']}")
            for st, n, d in p["checks"]:
                if st != "PASS" or not a.quick:
                    print(f"[{st}] {n} - {d}")
        print(f"RESULT: {passed}/{total} golden checks passed" + ("" if passed == total else f", {total - passed} FAILED"))
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
