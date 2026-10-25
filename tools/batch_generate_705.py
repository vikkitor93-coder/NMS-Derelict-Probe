"""Batch-generate derelict layouts for many systems of one region and write a summary CSV.

Usage:
  python tools/batch_generate_705.py --region 06607CAA --systems 0x001-0x2FF [--workers 4] [--galaxy 0]

--region is the last 8 portal-glyph hex digits (YY ZZZ XXX). Each system index SSS gives
address 000SSS GG YY ZZZ XXX (planet 0), the same mapping as generate_derelict_705.py --glyphs.
floors = distinct grid levels used, stair_pieces = STAIRS scenes (level transitions),
hangar_pieces = HANGAR scenes. Runs tools/generate_derelict_705.py per address at below-normal priority, skips addresses that
already have derelict.json, and writes <out-root>/summary.csv. Whether a system index actually
exists in the region is not known here.
"""
import argparse
import csv
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "tools" / "generate_derelict_705.py"
OUT_ROOT = Path("D:/Orca/NMS-Derelict-Probe-analysis/emu/generated")
BELOW_NORMAL = 0x00004000


def parse_range(text):
    lo, _, hi = text.partition("-")
    lo = int(lo, 0)
    return range(lo, (int(hi, 0) if hi else lo) + 1)


def run_one(address, out_root):
    out = out_root / address
    if not done(out / "derelict.json"):
        out.mkdir(parents=True, exist_ok=True)
        with open(out / "generate.log", "w", encoding="utf-8") as log:
            subprocess.run([sys.executable, "-I", str(GEN), address, "--out", str(out)],
                           stdout=log, stderr=subprocess.STDOUT, creationflags=BELOW_NORMAL)
    path = out / "derelict.json"
    if not done(path):
        return {"address": address, "status": "failed"}
    d = json.loads(path.read_text(encoding="utf-8"))
    kinds = d.get("container_kinds") or {}
    ins = d["instances"]
    scenes = [x["scene_resource"] for x in ins]
    return {"address": address, "status": "ok", "preset": d.get("preset"), "rooms": d.get("room_count"),
            "instances": d.get("instance_count"), "salvage_crates": kinds.get("salvage_crate", 0),
            "footlockers": kinds.get("crew_footlocker", 0), "seconds": d.get("emulator_seconds"),
            "floors": len({x["origin_xyz"][1] for x in ins}),
            "stair_pieces": sum(1 for r in scenes if "STAIRS" in r),
            "hangar_pieces": sum(1 for r in scenes if "HANGAR" in r),
            "templates": " ".join(r["template_name"] for r in d.get("rooms", []))}


def done(path):
    """A finished layout: derelict.json exists and holds instances (capped/failed runs do not)."""
    try:
        return "instances" in json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", required=True, help="last 8 glyph hex digits: YY ZZZ XXX, e.g. 06607CAA")
    ap.add_argument("--systems", required=True, help="system index range, e.g. 0x001-0x2FF")
    ap.add_argument("--galaxy", type=lambda v: int(v, 0), default=0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out-root", default=str(OUT_ROOT))
    a = ap.parse_args()
    region = a.region.upper()
    if len(region) != 8 or any(c not in "0123456789ABCDEF" for c in region):
        ap.error("--region must be 8 hex digits")
    out_root = Path(a.out_root)
    addrs = [f"000{s:03X}{a.galaxy & 0xFF:02X}{region}" for s in parse_range(a.systems)]
    rows, t0 = [], time.time()
    with ThreadPoolExecutor(a.workers) as pool:
        futs = {pool.submit(run_one, x, out_root): x for x in addrs}
        for n, f in enumerate(as_completed(futs), 1):
            r = f.result()
            r["glyphs"] = "0" + r["address"][3:6] + r["address"][8:]
            rows.append(r)
            print(f"[{n}/{len(addrs)} {time.time() - t0:.0f}s] {r['address']} {r.get('preset')} rooms={r.get('rooms')} "
                  f"crates={r.get('salvage_crates')}+{r.get('footlockers')} {r['status']}", flush=True)
    rows.sort(key=lambda r: r["address"])
    summary = out_root / f"summary-{region}.csv"
    fields = ["address", "glyphs", "status", "preset", "rooms", "instances", "salvage_crates", "footlockers", "floors", "stair_pieces", "hangar_pieces", "seconds", "templates"]
    with open(summary, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print("wrote", summary)


if __name__ == "__main__":
    main()
