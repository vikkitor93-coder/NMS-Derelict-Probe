"""Persistent worker: one game build's full derelict chain for any number of systems (JSON lines; Shipwright python).

    <EMU python> -I tools/compare_builds_worker_705.py --profile stock|7.05|<build_id>|<build.json> [--pin-only]

  stock      the shipped modules exactly as the scanner runs them (POI step reads the INSTALLED game)
  --pin-only only pin the space-POI step (Shipwright) to the profile's exe + game-data snapshot; generator unchanged
  otherwise  tools/build_profile_705.apply_profile(): exe, addresses, data root, fingerprints, predictor overrides

stdin : {"address": "<16 hex>"}            stdout: {"ready": true, ...} once, then one record per request:
  {"address", "seed", "preset", "rooms": [templates], "room_raw_sha", "pieces": {"n", "sha"},
   "crates"|"footlockers"|"briefcases"|"tall_lockers": [[room, x, y, z], ...],
   "loot": [[kind, room, x, y, z, item, amount, class, confidence], ...], "end_reward": [name, class, ambiguous, alt],
   "frigate": {...crate_loot_worker summary...}, "poi": [x, y, z] | null, "seconds": {...}}
Layouts are always generated fresh (never the cached derelict.json), into a temp folder that is deleted.
Never touches the game process; reads only the files named by the profile.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, "D:/Orca/NMS-Derelict-Probe-fastgen")
TMP = Path("D:/Orca/NMS-Derelict-Probe-analysis/builds/_tmp")
MAIN_KINDS = ("salvage_crate", "crew_footlocker")


def r(v, n=3):
    return [round(float(x), n) for x in v]


def record(address, layout, point, C, P, RB, CW) -> dict:
    out = {"address": address, "seed": layout.get("seed"), "preset": layout.get("preset"),
           "rooms": [rm["template_name"] for rm in layout["rooms"]],
           "room_raw_sha": hashlib.sha1("|".join(rm["raw_hex"] for rm in layout["rooms"]).encode()).hexdigest()[:16]}
    pieces = sorted([i["room_index"], i["scene_resource"].upper(), r(i["translation"], 3),
                     [r(ax, 3) for ax in i.get("source_axes", [])]] for i in layout["instances"])
    out["pieces"] = {"n": len(pieces), "sha": hashlib.sha1(json.dumps(pieces).encode()).hexdigest()[:16]}
    by_kind = {"salvage_crate": "crates", "crew_footlocker": "footlockers", "briefcase": "briefcases", "tall_locker": "tall_lockers"}
    for k in by_kind.values():
        out[k] = []
    for c in list(layout["containers"]) + list(layout.get("extra_containers") or []):
        key = by_kind.get(c["container_kind"])
        if key:
            out[key].append([c.get("room_index"), *r(c["layout_local_xyz"], 2)])
    for k in by_kind.values():
        out[k].sort(key=lambda x: (x[0] if x[0] is not None else 99, x[1:]))
    out["poi"] = (point or {}).get("aband_freighter")
    pred = C.predict(address, point, layout, None, tuple(C.TABLE_OF_KIND))
    loot = []
    for c in pred.get("containers", []):
        lo = c["loot"]
        loot.append([c["kind"], c["room"], *r(c["layout_xyz"], 2), lo.get("id") or lo.get("key"), lo.get("amount"),
                     lo.get("tech_class"), "ambiguous" if c["confidence"].startswith("AMBIGUOUS") else "ok"])
    out["loot"] = sorted(loot, key=lambda x: (x[1] if x[1] is not None else 99, x[0], x[2:5]))
    out["loot_status"] = pred.get("status")
    main = {**pred, "containers": [c for c in pred.get("containers", []) if c["kind"] in MAIN_KINDS]}
    try:
        out["frigate"] = CW.summarize(address, layout, main) if "containers" in pred else None
    except Exception as exc:
        out["frigate"] = {"error": repr(exc)[:200]}
    res = P.predict(address, point, layout)
    try:
        out["end_reward"] = list(RB.result_row(res))
    except Exception as exc:
        out["end_reward"] = ["", "", "", f"none: {res.get('status') or exc}"]
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--profile", default="stock")
    ap.add_argument("--pin-only", action="store_true")
    a = ap.parse_args()
    proto = sys.stdout
    with contextlib.redirect_stdout(sys.stderr):
        import build_profile_705 as BP
        import fast_generate_705 as F
        import native_writer_705 as N
        import predict_crate_loot_705 as C
        import predict_end_reward_705 as P
        import end_reward_batch_705 as RB
        import crate_loot_worker_705 as CW
        import space_poi_position_705 as SP
        patched, prof = {}, None
        if a.profile != "stock":
            prof = BP.load_profile(a.profile)
            patched = BP.apply_profile(prof, full=not a.pin_only)
        session = N.NativeSession()
        F.cached_catalog()
        poi = SP.PoiGen()
    TMP.mkdir(parents=True, exist_ok=True)

    def writer(seed, preset_index, out, max_insns, counters=False):
        if counters or max_insns:
            return F.run_writer(seed, preset_index, out, max_insns, counters)
        res, secs, info = session.run(seed, preset_index)
        _, code = session.write_outputs(out, res, secs, info)
        if code:
            raise RuntimeError(f"native writer returned {code}")
        F._engine_used["engine"] = "native-compare-worker"
        return 0, secs

    print(json.dumps({"ready": True, "profile": a.profile, "pin_only": a.pin_only, "patched": patched,
                      "exe": str(N.EXE), "writer": hex(N.WRITER)}), file=proto, flush=True)
    for line in sys.stdin:
        if not line.strip():
            continue
        address = None
        try:
            req = json.loads(line)
            address = str(req["address"]).upper()
            if len(address) != 16 or any(ch not in "0123456789ABCDEF" for ch in address):
                raise ValueError("address must be 16 hex digits")
            t0 = time.monotonic()
            with tempfile.TemporaryDirectory(prefix="cmp_", dir=TMP) as d:
                with contextlib.redirect_stdout(sys.stderr):
                    code = F.generate(["fast_generate_705.py", address, "--out", d, "--override", "0"], writer=writer)
                if code:
                    raise RuntimeError(f"fast generator returned {code}")
                layout = json.loads((Path(d) / "derelict.json").read_text(encoding="utf-8"))
            t1 = time.monotonic()
            point = poi.positions(int(address, 16))
            t2 = time.monotonic()
            rec = record(address, layout, point, C, P, RB, CW)
            rec["seconds"] = {"layout": round(t1 - t0, 3), "poi": round(t2 - t1, 3), "total": round(time.monotonic() - t0, 3)}
            print(json.dumps(rec, separators=(",", ":")), file=proto, flush=True)
        except Exception as exc:
            print(json.dumps({"address": address, "error": f"{type(exc).__name__}: {exc}"[:500]}), file=proto, flush=True)


if __name__ == "__main__":
    main()
