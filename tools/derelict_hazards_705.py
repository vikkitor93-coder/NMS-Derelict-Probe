"""Enemy spawners, turrets and other hazards in a generated NMS 7.05 derelict layout (milestones #21 / #22).

  python -I tools/derelict_hazards_705.py <derelict.json | ADDRESS16 dir> [--json OUT] [--text]
  python -I tools/derelict_hazards_705.py --summary [GENERATED_DIR] [--csv OUT.csv] [--json OUT.json]

Reads derelict.json (instances[]: scene_resource, source_axes, translation, room_index) and the decompiled piece scenes
in the mesh cache (D:/Orca/NMS-Derelict-Probe-analysis/meshcache/raw, read-only). Every placed piece scene is walked
through its REFERENCE nodes (incl. InstanceTransforms); a node that references one of the hazard scenes in CATALOG is
a hazard. Its piece-local matrix is the composition of the node transforms (tools/build_piece_meshes_705.trs:
R = Rz*Ry*Rx, column vectors), and layout space is p*A + t (row vectors; A = source_axes, t = translation).

Grid (viewer): u = x/8 + Ex + 0.5, v = z/8 + Ez + 0.5, level = round(y/8) + Ey, E = entrance_origin.

What comes from the layout (deterministic, same as the generator's placements): which spawners/turrets/sacs exist,
in which room, where. What is decided at run time (NOT in the layout): how many creatures each spawner releases
(random in [min, max] of metadata/simulation/scene/experiencespawntable.mbin, per difficulty column), when they spawn,
whether a sac bursts. See research-output/ENEMIES_TURRETS_20261020.md for the evidence.
"""
import argparse
import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_piece_meshes_705 as bpm  # noqa: E402  (scene(), member(), trs(), matmul(); read-only use)

GENERATED = Path("D:/Orca/NMS-Derelict-Probe-analysis/emu/fastgen/generated")
SB = "models/planets/biomes/common/buildings/parts/buildableparts/spacebase/"

# Spawn counts from experiencespawntable.mbin CreatureSpawnTable (Event -> MinNum/MaxNum per difficulty column
# Off/Slow/Normal/Fast). The column is a run-time difficulty option, so counts are ranges, not layout data.
SPAWN_EVENTS = {
    "FLOATER": {"archetype": "FLOATER", "creature": "Floater", "scale": 0.9,
                "min": {"Off": 1, "Slow": 1, "Normal": 1, "Fast": 1}, "max": {"Off": 2, "Slow": 2, "Normal": 2, "Fast": 2}},
    "FAST_FLOATER": {"archetype": "FAST_FLOATER", "creature": "Floater", "scale": 0.5,
                     "min": {"Off": 1, "Slow": 1, "Normal": 1, "Fast": 1}, "max": {"Off": 2, "Slow": 2, "Normal": 2, "Fast": 2}},
    "MINIDRONE": {"archetype": "MINIDRONE", "creature": "MiniDrone", "scale": 0.5,
                  "min": {"Off": 2, "Slow": 2, "Normal": 2, "Fast": 2}, "max": {"Off": 3, "Slow": 3, "Normal": 3, "Fast": 3}},
    "BUG": {"archetype": "BUG", "creature": "Scuttler", "scale": 1.0,
            "min": {"Off": 3, "Slow": 3, "Normal": 3, "Fast": 3}, "max": {"Off": 5, "Slow": 5, "Normal": 5, "Fast": 5}},
    # raised by the *_destroyed scene of a hanging / pillar sac (sketch OnSpawned -> RaiseEvent PE_SPAWN FIEND_DROP)
    "FIEND_DROP": {"archetype": "BUG", "creature": "Scuttler", "scale": 1.0, "appear": "VENTDROP at SPAWNPOS",
                   "min": {"Off": 1, "Slow": 3, "Normal": 6, "Fast": 6}, "max": {"Off": 3, "Slow": 5, "Normal": 8, "Fast": 10}},
    "FIEND_EGG": {"archetype": "BUG", "creature": "Scuttler", "scale": 1.0, "appear": "HATCH",
                  "min": {"Off": 1, "Slow": 1, "Normal": 1, "Fast": 1}, "max": {"Off": 1, "Slow": 1, "Normal": 1, "Fast": 1}},
}

# target scene (archive member, lower case) -> hazard description
CATALOG = {
    SB + "spawners/floater_hostile_spawner.scene.mbin": dict(kind="floater_spawner", category="enemy_spawner", enemy="floater", event="FLOATER", trigger="spawner entity OnSpawned"),
    SB + "spawners/floater_fast_spawner.scene.mbin": dict(kind="fast_floater_spawner", category="enemy_spawner", enemy="fast_floater", event="FAST_FLOATER", trigger="spawner entity OnSpawned"),
    SB + "spawners/drone_hostile_spawner.scene.mbin": dict(kind="drone_spawner", category="enemy_spawner", enemy="minidrone", event="MINIDRONE", trigger="spawner entity OnSpawned"),
    SB + "spawners/bug_neutral_spawner.scene.mbin": dict(kind="bug_spawner", category="enemy_spawner", enemy="bug", event="BUG", trigger="spawner entity OnSpawned"),
    SB + "turret.scene.mbin": dict(kind="turret", category="turret", enemy="turret", event=None, trigger="base-defence perception (LASER), deploys from 'Retracted'"),
    SB + "infestation/mediumhangslime.scene.mbin": dict(kind="hanging_sac", category="bug_source", enemy="bug", event="FIEND_DROP", trigger="alien-pod agro (movement/torch); destroyed model raises FIEND_DROP"),
    SB + "infestation/largepillarslime.scene.mbin": dict(kind="pillar_sac", category="bug_source", enemy="bug", event="FIEND_DROP", trigger="alien-pod agro (movement/torch); destroyed model raises FIEND_DROP"),
    SB + "fiendegg.scene.mbin": dict(kind="fiend_egg", category="bug_source", enemy="bug", event="FIEND_EGG", trigger="egg hatch"),
    SB + "infestation/largecornerslime.scene.mbin": dict(kind="slime", category="slime", enemy=None, event=None, trigger="destructible (FiendCrime EggDestroyed)"),
    SB + "infestation/large90slime.scene.mbin": dict(kind="slime", category="slime", enemy=None, event=None, trigger="destructible (FiendCrime EggDestroyed)"),
    SB + "infestation/medium90slime.scene.mbin": dict(kind="slime", category="slime", enemy=None, event=None, trigger="destructible (FiendCrime EggDestroyed)"),
    SB + "infestation/mediumflatslime.scene.mbin": dict(kind="slime", category="slime", enemy=None, event=None, trigger="destructible (FiendCrime EggDestroyed)"),
    SB + "explodingbarrel.scene.mbin": dict(kind="explosive_barrel", category="environment", enemy=None, event=None, trigger="destructible, area damage BARRELEXPLODE"),
    SB + "door_slime.scene.mbin": dict(kind="slime_door", category="slime", enemy=None, event=None, trigger="door with slime model (no own destructible entity)"),
}
SKIP_PREFIX = ("models/effects/",)
SYMBOL = {"floater_spawner": "F", "fast_floater_spawner": "f", "drone_spawner": "D", "bug_spawner": "B", "turret": "T",
          "hanging_sac": "S", "pillar_sac": "P", "fiend_egg": "E", "slime": "~", "explosive_barrel": "X", "slime_door": "="}
IDENT = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]

_piece_cache = {}


def piece_hazards(scene_resource):
    """[(kind, node_name, 4x4 piece-local matrix)] for one placed piece scene (cached)."""
    key = bpm.member(scene_resource)
    if key in _piece_cache:
        return _piece_cache[key]
    out, missing = [], []

    def visit_scene(name, mat, depth):
        root = bpm.scene(name)
        if root is None:
            missing.append(name)
            return
        visit(root, mat, depth, True)

    def visit(n, parent, depth, is_root=False):
        mat = parent if is_root else bpm.matmul(parent, bpm.trs(n["t"]))
        if n["type"] == "REFERENCE":
            target = bpm.member(n["attrs"].get("SCENEGRAPH", ""))
            for it in n["inst"] or [None]:
                m = mat if it is None else bpm.matmul(mat, bpm.trs(it))
                if target in CATALOG:
                    out.append((target, n["name"], m))
                elif target.endswith(".scene.mbin") and not target.startswith(SKIP_PREFIX) and depth < 12:
                    visit_scene(target, m, depth + 1)
            return
        for c in n["children"]:
            visit(c, mat, depth)

    visit_scene(key, IDENT, 0)
    _piece_cache[key] = (out, missing)
    return out, missing


def to_layout(p, inst):
    a, t = inst["source_axes"], inst["translation"]
    return [sum(p[k] * a[k][j] for k in range(3)) + t[j] for j in range(3)]


def dir_to_layout(d, inst):
    a = inst["source_axes"]
    return [sum(d[k] * a[k][j] for k in range(3)) for j in range(3)]


def analyse(d):
    ex, ey, ez = d["entrance_origin"]
    rooms = {r["room_index"]: {"room_index": r["room_index"], "template": r.get("template_name"), "hazards": []} for r in d.get("rooms", [])}
    missing = set()
    for inst in d["instances"]:
        hz, miss = piece_hazards(inst["scene_resource"])
        missing.update(miss)
        for target, node, m in hz:
            info = CATALOG[target]
            local = [m[0][3], m[1][3], m[2][3]]
            x, y, z = to_layout(local, inst)
            fwd = dir_to_layout([m[0][2], m[1][2], m[2][2]], inst)   # local +Z
            up = dir_to_layout([m[0][1], m[1][1], m[2][1]], inst)    # local +Y
            h = {"kind": info["kind"], "category": info["category"], "symbol": SYMBOL[info["kind"]],
                 "x": round(x, 3), "y": round(y, 3), "z": round(z, 3),
                 # level of the deck the hazard stands on / hangs from: hazards sit 0..4 m above their deck (decks 8 m
                 # apart), so floor((y + 1) / 8) instead of round(y / 8) (round(-0.5) would put a -4 m ceiling turret
                 # on the deck above).
                 "u": round(x / 8 + ex + 0.5, 3), "v": round(z / 8 + ez + 0.5, 3), "level": math.floor((y + 1) / 8) + ey,
                 "yaw_deg": round(math.degrees(math.atan2(fwd[0], fwd[2])) % 360, 1),
                 "template_id": inst.get("template_id"), "piece": inst["scene_resource"], "scene_node": node}
            if info["kind"] == "turret":
                h["mount"] = "ceiling" if up[1] < -0.5 else ("floor" if up[1] > 0.5 else "wall")
            if info["event"]:
                ev = SPAWN_EVENTS[info["event"]]
                h["spawn"] = {"event": info["event"], "creature": ev["creature"], "archetype": ev["archetype"],
                              "count_normal": [ev["min"]["Normal"], ev["max"]["Normal"]],
                              "count_by_difficulty": {k: [ev["min"][k], ev["max"][k]] for k in ev["min"]}}
            h["trigger"] = info["trigger"]
            rooms.setdefault(inst["room_index"], {"room_index": inst["room_index"], "template": None, "hazards": []})["hazards"].append(h)
    totals, enemies = Counter(), defaultdict(lambda: [0, 0])
    for r in rooms.values():
        r["counts"] = dict(Counter(h["kind"] for h in r["hazards"]))
        for h in r["hazards"]:
            totals[h["kind"]] += 1
            if "spawn" in h:
                lo, hi = h["spawn"]["count_normal"]
                enemies[h["spawn"]["archetype"]][0] += lo
                enemies[h["spawn"]["archetype"]][1] += hi
    return {"address": d.get("address"), "preset": d.get("preset"), "seed": d.get("seed"), "entrance_origin": d["entrance_origin"],
            "totals": dict(sorted(totals.items())),
            "turrets": totals["turret"],
            "enemy_spawners": sum(v for k, v in totals.items() if k.endswith("_spawner")),
            "bug_sacs": totals["hanging_sac"] + totals["pillar_sac"],
            "expected_creatures_normal": {k: v for k, v in sorted(enemies.items())},
            "rooms": [rooms[k] for k in sorted(rooms)],
            "missing_scenes": sorted(missing),
            "notes": "positions in layout metres; creature counts are run-time random ranges (difficulty 'Normal' column); "
                     "bug counts from sacs assume every sac bursts once"}


def load(path):
    p = Path(path)
    if p.is_dir():
        p = p / "derelict.json"
    elif not p.exists() and len(p.name) == 16:
        p = GENERATED / p.name / "derelict.json"
    return json.loads(p.read_text(encoding="utf-8"))


def text_report(r):
    lines = [f"{r['address']}  {r['preset']}  turrets {r['turrets']}  spawners {r['enemy_spawners']}  bug sacs {r['bug_sacs']}",
             "  totals: " + ", ".join(f"{k} {v}" for k, v in r["totals"].items()),
             "  creatures (Normal, min-max): " + ", ".join(f"{k} {a}-{b}" for k, (a, b) in r["expected_creatures_normal"].items())]
    for room in r["rooms"]:
        hz = [h for h in room["hazards"] if h["category"] not in ("slime",)]
        if not hz:
            continue
        lines.append(f"  room {room['room_index']:2d} {room['template'] or '?':14s} " + ", ".join(f"{k} {v}" for k, v in sorted(room["counts"].items())))
        for h in hz:
            extra = f" mount={h['mount']}" if "mount" in h else ""
            sp = f" {h['spawn']['archetype']} x{h['spawn']['count_normal'][0]}-{h['spawn']['count_normal'][1]}" if "spawn" in h else ""
            lines.append(f"     {h['symbol']} {h['kind']:20s} xyz=({h['x']:7.2f},{h['y']:6.2f},{h['z']:7.2f}) u,v,L=({h['u']:.2f},{h['v']:.2f},{h['level']}) yaw={h['yaw_deg']:5.1f}{extra}{sp}")
    if r["missing_scenes"]:
        lines.append("  MISSING scene MXML (hazards inside them not counted): " + ", ".join(r["missing_scenes"]))
    return "\n".join(lines)


KINDS = ["floater_spawner", "fast_floater_spawner", "drone_spawner", "bug_spawner", "turret", "hanging_sac", "pillar_sac",
         "fiend_egg", "slime", "slime_door", "explosive_barrel"]


def summary(root, csv_out=None, json_out=None):
    rows, per = [], defaultdict(list)
    missing = set()
    for f in sorted(Path(root).glob("*/derelict.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not d.get("instances"):
            continue
        r = analyse(d)
        missing.update(r["missing_scenes"])
        row = {"address": r["address"], "preset": r["preset"], "rooms": len(r["rooms"]), **{k: r["totals"].get(k, 0) for k in KINDS},
               "rooms_with_turret": sum(1 for x in r["rooms"] if x["counts"].get("turret")),
               "rooms_with_spawner": sum(1 for x in r["rooms"] if any(k.endswith("_spawner") for k in x["counts"])),
               "spawner_in_room0": sum(v for k, v in r["rooms"][0]["counts"].items() if k.endswith("_spawner")) if r["rooms"] else 0,
               "max_turrets_one_room": max((x["counts"].get("turret", 0) for x in r["rooms"]), default=0),
               "creatures_normal_min": sum(a for a, b in r["expected_creatures_normal"].values()),
               "creatures_normal_max": sum(b for a, b in r["expected_creatures_normal"].values())}
        rows.append(row)
        per[r["preset"]].append(row)
    if csv_out:
        with open(csv_out, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    stats = {}
    for preset in sorted(per):
        rs = per[preset]
        s = {"layouts": len(rs)}
        for k in KINDS + ["creatures_normal_min", "creatures_normal_max", "max_turrets_one_room", "spawner_in_room0"]:
            vals = [x[k] for x in rs]
            s[k] = {"mean": round(sum(vals) / len(vals), 2), "min": min(vals), "max": max(vals), "zero": sum(1 for v in vals if v == 0)}
        stats[preset] = s
    out = {"layouts": len(rows), "presets": stats, "missing_scenes": sorted(missing)}
    if json_out:
        Path(json_out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("layout", nargs="?", help="derelict.json, its folder, or an ADDRESS16 under the generated folder")
    ap.add_argument("--summary", nargs="?", const=str(GENERATED), help="aggregate over all <dir>/*/derelict.json")
    ap.add_argument("--json", help="write the per-layout result (or the summary) as JSON")
    ap.add_argument("--csv", help="--summary: per-layout counts CSV")
    ap.add_argument("--text", action="store_true", help="print a readable per-room report")
    a = ap.parse_args()
    if a.summary:
        out = summary(a.summary, a.csv, a.json)
        print(f"{out['layouts']} layouts")
        cols = ["floater_spawner", "fast_floater_spawner", "drone_spawner", "turret", "hanging_sac", "pillar_sac", "slime", "slime_door", "explosive_barrel"]
        print(f"{'preset':15s} {'n':>4s} " + " ".join(f"{c[:12]:>12s}" for c in cols) + "  creatures(Normal)")
        for p, s in out["presets"].items():
            print(f"{p:15s} {s['layouts']:4d} " + " ".join(f"{s[c]['mean']:12.2f}" for c in cols)
                  + f"  {s['creatures_normal_min']['mean']:.1f}-{s['creatures_normal_max']['mean']:.1f}")
        if out["missing_scenes"]:
            print("missing scenes:", len(out["missing_scenes"]), out["missing_scenes"][:10])
        return 0
    if not a.layout:
        ap.error("give a layout or --summary")
    r = analyse(load(a.layout))
    if a.json:
        Path(a.json).write_text(json.dumps(r, indent=1), encoding="utf-8")
    if a.text or not a.json:
        print(text_report(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
