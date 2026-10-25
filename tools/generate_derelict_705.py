#!/usr/bin/env python3
"""End-to-end NMS 7.05 derelict generator: universe address -> seed, preset, rooms, instance transforms, containers.

Composes (no edits to them):
  derelict_seed_preset_705.derelict_seed_preset   address -> (writer seed, preset, index)
  emulate_writer_705_assets.py                    native writer under Unicorn (subprocess; ~1-4 min)
  transform_writer_output_705                     A4720 scene transforms + authored container positions
Output: D:/Orca/NMS-Derelict-Probe-analysis/emu/generated/<address>/derelict.json (+ raw emulator files).

  python tools/generate_derelict_705.py 0000320006606CAA [--override 0] [--fixture-check] [--reuse-run]
"""
from __future__ import annotations
import argparse, csv, json, math, subprocess, sys, time
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
GEN = Path("D:/Orca/NMS-Derelict-Probe-analysis/emu/generated")
REPLAY = ROOT / "research-output/known-derelict-replay-20261019"
CONT_INDEX = ROOT / "research-output/exact705-generatedbase-scenes-20261019/authored_container_transform_index.csv"


def run_writer(seed, preset_index, out, max_insns):
    cmd = [sys.executable, str(ROOT / "tools/emulate_writer_705_assets.py"), "--no-live-desc",
           "--max-insns", str(max_insns), "--seed", f"0x{seed:016X}", "--preset-index", str(preset_index), "--out", str(out)]
    t0 = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True)
    (out / "emulator_stdout.log").write_text(p.stdout + "\n---stderr---\n" + p.stderr, encoding="utf-8")
    return p.returncode, time.time() - t0


def parse_rooms(outbuf: bytes, n):
    rooms = []
    for i in range(n):
        r = outbuf[i * 0x40:(i + 1) * 0x40]
        name = r[0x28:0x40].split(b"\0")[0].decode("ascii", "replace")
        rooms.append({"room_index": i, "template_name": name,
                      "raw_u16_0x00_0x1F": [int.from_bytes(r[k:k + 2], "little") for k in range(0, 0x20, 2)],
                      "raw_hex": r.hex()})
    return rooms


def derive(run_dir, preset_index):
    import transform_writer_output_705 as T
    import build_source_rows_from_assets  # noqa: F401  (orientation-2 dimension fix, must precede transforms)
    sys.path.insert(0, str(T.OFF))
    from nms_dungeon_a2780_search_705 import A2780Placement
    from nms_dungeon_instance_705 import build_scene_instance_transforms, transform_authored_containers
    from nms_dungeon_reference_closure_q4_705 import Q4SourceCatalog
    from nms_dungeon_variable_placement_705 import VariablePlacementAppendRecord
    items = json.loads((run_dir / "emu_placements.json").read_text())
    pl = [A2780Placement(VariablePlacementAppendRecord(int(i["row"]), (int(i["xy"][0]), int(i["xy"][1]), int(i["z"])), 0, 0, 0),
                         int(i["room"]), bytes(16), "", 0, 0, "writer-output", "", int(i["row"])) for i in items]
    org = T.entrance_origin(preset_index)
    tr = build_scene_instance_transforms(pl, catalog=Q4SourceCatalog.from_workspace(ROOT), grid_origin_xyz=org)
    cont = transform_authored_containers(tr, container_index_csv=CONT_INDEX)
    return org, [asdict(t) for t in tr], [asdict(c) for c in cont]


def fixture_check(inst, cont):
    """Compare against the captured-layout replay: counts and position error (greedy nearest match per key)."""
    def match(ours, theirs):
        og, tg = defaultdict(list), defaultdict(list)
        for k, p in ours: og[k].append(p)
        for k, p in theirs: tg[k].append(p)
        errs, unmatched = [], 0
        for k in set(og) | set(tg):
            o, t = og[k], tg[k]
            pairs = sorted((math.dist(a, b), i, j) for i, a in enumerate(o) for j, b in enumerate(t))
            uo, ut = set(range(len(o))), set(range(len(t)))
            for d, i, j in pairs:
                if i in uo and j in ut:
                    uo.discard(i); ut.discard(j); errs.append(d)
            unmatched += len(uo) + len(ut)
        return {"matched": len(errs), "unmatched": unmatched, "max_err": max(errs, default=0)}
    ri = list(csv.DictReader(open(REPLAY / "KNOWN_DERELICT_ROOM_COMPONENTS_20261019.csv")))
    rc = list(csv.DictReader(open(REPLAY / "KNOWN_DERELICT_CONTAINER_PLACEMENTS_20261019.csv")))
    f = lambda r: (float(r["layout_x"]), float(r["layout_y"]), float(r["layout_z"]))
    mi = match([((t["room_index"], t["scene_resource"]), tuple(t["translation"])) for t in inst],
               [((int(r["room_index"]), r["scene_resource"]), f(r)) for r in ri])
    mc = match([((c["room_index"], c["scene_resource"], c["scene_node_name"], c["container_kind"]), tuple(c["layout_local_xyz"])) for c in cont],
               [((int(r["room_index"]), r["scene_resource"], r["scene_node_name"], r["container_kind"]), f(r)) for r in rc])
    exp_rooms = [15, 3, 10, 13, 2, 27, 3, 26, 4, 20, 22]
    got = Counter(t["room_index"] for t in inst)
    kinds = Counter(c["container_kind"] for c in cont)
    ok = ([got[i] for i in range(len(exp_rooms))] == exp_rooms and len(inst) == 145 and len(cont) == 23
          and mi["unmatched"] == 0 and mc["unmatched"] == 0 and mi["max_err"] < 1e-4 and mc["max_err"] < 1e-4)
    return {"pass": ok, "instances_vs_replay": mi, "containers_vs_replay": mc, "container_kinds": dict(kinds)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("address", help="16-hex universe address, e.g. 00003B0006606CAA")
    ap.add_argument("--override", type=lambda v: int(v, 0), default=0, help="global seed override _DAT_14526D4F0 (default 0 = packed address)")
    ap.add_argument("--max-insns", type=int, default=0, help="0 = uncapped (the pipeline mode; fast_generate_705 then uses the native writer); N or --counters route to Unicorn")  # stage3 M1: default was 3_000_000_000 in the replayed copy, which forced the Unicorn path
    ap.add_argument("--out", help="output dir (default emu/generated/<address>)")
    ap.add_argument("--reuse-run", action="store_true", help="reuse emulator output already in the out dir")
    ap.add_argument("--fixture-check", action="store_true", help="compare with the captured fixture replay (only valid for 00003B0006606CAA)")
    a = ap.parse_args()
    addr = a.address.upper().removeprefix("0X").zfill(16)
    from derelict_seed_preset_705 import derelict_seed_preset
    seed, preset, pidx = derelict_seed_preset(addr, a.override)
    out = Path(a.out) if a.out else GEN / addr
    out.mkdir(parents=True, exist_ok=True)
    print(f"address {addr}  seed {seed:016X}  preset {preset} (index {pidx})", flush=True)
    secs = None
    if not (a.reuse_run and (out / "last_run_summary.json").exists()):
        rc, secs = run_writer(seed, pidx, out, a.max_insns)
        print(f"emulator exit {rc} in {secs:.0f}s", flush=True)
    summ = json.loads((out / "last_run_summary.json").read_text())
    res = summ.get("result", {})
    accepted = res.get("ok") == "0x1" and not summ.get("fault")
    result = {"address": addr, "global_override": f"{a.override:016X}", "seed": f"{seed:016X}", "preset": preset,
              "preset_index": pidx, "writer_accepted": accepted, "fault": summ.get("fault"),
              "emulator_seconds": summ.get("seconds"), "wall_seconds": secs}
    if not accepted:
        (out / "derelict.json").write_text(json.dumps(result, indent=1))
        print("writer did NOT accept:", res, summ.get("fault")); sys.exit(2)
    nrooms = int(res["rax"], 16)
    rooms = parse_rooms((out / "outbuf.bin").read_bytes(), nrooms)
    org, inst, cont = derive(out, pidx)
    per_room = Counter(t["room_index"] for t in inst)
    for r in rooms:
        r["instance_count"] = per_room.get(r["room_index"], 0)
        r["container_count"] = sum(1 for c in cont if c["room_index"] == r["room_index"])
    result.update(entrance_origin=list(org), room_count=nrooms, instance_count=len(inst), container_count=len(cont),
                  container_kinds=dict(Counter(c["container_kind"] for c in cont)),
                  rooms=rooms, instances=inst, containers=cont,
                  notes="transforms are offline-model output (authored bounds / callback order qualified); positions in layout space")
    if a.fixture_check:
        result["fixture_check"] = fixture_check(inst, cont)
    (out / "derelict.json").write_text(json.dumps(result, indent=1))
    fam = Counter(t["scene_resource"].split("/DUNGEON/")[-1].split("/")[0] for t in inst)
    print(f"rooms {nrooms}  instances {len(inst)}  per-room {[per_room.get(i, 0) for i in range(nrooms)]}")
    print(f"containers {len(cont)} {result['container_kinds']}  scene families {dict(fam)}")
    if a.fixture_check:
        print("fixture check:", json.dumps(result["fixture_check"]))
    print("wrote", out / "derelict.json")


if __name__ == "__main__":
    main()
