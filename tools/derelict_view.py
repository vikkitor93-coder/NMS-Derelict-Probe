"""Python port of viewer/static/model.js pack(): generated derelict.json -> compact published view (format 3).

Byte-identical to the JavaScript version (`python -I tools/derelict_view.py --verify` compares them through Node), so
the atlas publisher (Python) can write views without Node. tools/build_top_bundle.py packs the top 100 systems into
one gzip file together with the piece table they use (its "o" = each piece's container rotations, from which
model.js unpack() gives every container its orientation; see model.js):

    names = sorted scene names used;  ids = {name: k for k, name in enumerate(names)}
    view = pack(derelict, ids);       table = pieces_table(piece_index, names)
"""
import json
import math
import sys
from pathlib import Path

VIEW_FORMAT = 3
CM, STEP = 100, 4
ROT_Q = 100  # piece table container rotations in 1/100 degree
ROTS = [[[1, 0, 0], [0, 1, 0], [0, 0, 1]], [[0, 0, -1], [0, 1, 0], [1, 0, 0]],
        [[-1, 0, 0], [0, 1, 0], [0, 0, -1]], [[0, 0, 1], [0, 1, 0], [-1, 0, 0]]]
# container kind codes, as in model.js: "c" = salvage crates (0) / crew footlockers (1); optional "x" = extra loot
# containers, briefcases (2) / tall lockers (3) (tools/extra_containers_705.py)
KIND_CODES = {"salvage_crate": 0, "crew_footlocker": 1, "briefcase": 2, "tall_locker": 3}


def _round(x):
    # JavaScript Math.round: halves go up (towards +infinity)
    return math.floor(x + 0.5)


def _rot(a):
    for k, r in enumerate(ROTS):
        if all(abs(r[i][j] - a[i][j]) < 1e-4 for i in range(3) for j in range(3)):
            return k
    raise ValueError(f"piece rotation is not one of the 4 yaw rotations: {a}")


def _step(x):
    v = _round(x / STEP)
    if abs(v - x / STEP) > 1e-3:
        raise ValueError(f"piece position {x} is not a multiple of {STEP} units")
    return v


def _delta(a):
    return [v - a[k - 1] if k else v for k, v in enumerate(a)]


def _extra_code(c):
    k = KIND_CODES.get(c["container_kind"])
    if k not in (2, 3):
        raise ValueError(f"not an extra container kind: {c['container_kind']}")
    return k


def pack(d, ids):
    rooms = []
    for k, r in enumerate(d["rooms"]):
        if r["room_index"] != k:
            raise ValueError(f"room {r['room_index']} at position {k}")
        raw = r["raw_u16_0x00_0x1F"]
        rooms.append([r["template_name"], *raw[0:6], *raw[12:16]])
    cs, ins = d["containers"], d["instances"]
    # columns; positions as differences from the previous entry (see model.js)
    containers = [[0 if c["container_kind"] == "salvage_crate" else 1 for c in cs], [c["room_index"] for c in cs],
                  *(_delta([_round(c["layout_local_xyz"][k] * CM) for c in cs]) for k in range(3))]
    pieces = [[ids[i["scene_resource"].upper()] for i in ins], [_rot(i["source_axes"]) for i in ins],
              *(_delta([_step(i["translation"][k]) for i in ins]) for k in range(3)), [i["room_index"] for i in ins]]
    view = {"v": VIEW_FORMAT, "a": d["address"], "s": d["seed"], "p": d["preset"], "e": d.get("entrance_origin") or [6, 3, 0],
            "r": rooms, "c": containers, "i": pieces}
    if d.get("extra_containers") is not None:  # only when the layout has them (model.js: if (d.extra_containers))
        xs = d["extra_containers"]
        view["x"] = [[_extra_code(c) for c in xs], [c["room_index"] for c in xs],
                     *(_delta([_round(c["layout_local_xyz"][k] * CM) for c in xs]) for k in range(3))]
    return view


def pieces_table(index, names, rotations=None):
    """Port of model.js piecesTable(): each scene's wall footprint and fixture boxes in 1/100 layout units, and "o":
    its container nodes [kind code, RotX, RotY, RotZ] (1/100 degree, tools/extra_containers_705.py
    authored_rotations(); model.js reads the same numbers from viewer/static/piece_props.json "o")."""
    if rotations is None:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import extra_containers_705 as ec
        rotations = ec.authored_rotations()
    q = lambda x: _round(x * 100)
    walls, fixtures, rots = [], [], []
    for n in names:
        e = index.get(n) or {}
        walls.append([v for w in e.get("walls") or [] for v in (q(w[0]), q(w[1]), q(w[2]), q(w[3]), w[4] if len(w) > 4 else 0)])
        fixtures.append([q(x) for b in e.get("fixtures") or [] for x in b])
        rots.append([v for k, rx, ry, rz in rotations.get(n, []) for v in (k, _round(rx * ROT_Q), _round(ry * ROT_Q), _round(rz * ROT_Q))])
    return {"v": VIEW_FORMAT, "q": 100, "n": list(names), "w": walls, "f": fixtures, "o": rots}


def view_json(d, ids):
    return json.dumps(pack(d, ids), separators=(",", ":"), ensure_ascii=False)


def rotation_angle(a, b):
    """Angle in degrees between two [RotX, RotY, RotZ] orientations (game order, tools/extra_containers_705.py)."""
    import extra_containers_705 as ec
    m, n = ec.euler_matrix(*a), ec.euler_matrix(*b)
    tr = sum(m[k][i] * n[k][i] for i in range(3) for k in range(3))  # trace(m^T n) = 1 + 2 cos(angle)
    return math.degrees(math.acos(max(-1.0, min(1.0, (tr - 1) / 2))))


def verify(addresses, generated=Path("D:/Orca/NMS-Derelict-Probe-analysis/emu/fastgen/generated")):
    """Pack each layout here and with model.js (Node) and compare the JSON text; compare the piece tables (Python
    pieces_table() from the scene catalogs, model.js piecesTable() from viewer/static/piece_props.json); and check that
    model.js unpack() + build() give every container the orientation tools/extra_containers_705.py computes (largest angle)."""
    import subprocess
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import extra_containers_705 as ec
    index = json.loads(Path("D:/Orca/NMS-Derelict-Probe-analysis/meshcache/index.json").read_text(encoding="utf-8"))
    names = sorted(k for k in index if k != "_meta")
    ids = {n: k for k, n in enumerate(names)}
    static = Path(__file__).resolve().parent.parent / "viewer" / "static"
    js = ("const M=require(process.argv[1]),fs=require('fs');const a=JSON.parse(fs.readFileSync(0,'utf8'));"
          "const props=JSON.parse(fs.readFileSync(a.props,'utf8')).scenes,index=JSON.parse(fs.readFileSync(a.index,'utf8'));"
          "const ids=new Map(a.n.map((n,k)=>[n,k]));const t=M.piecesTable(index,a.n,props);console.log(JSON.stringify(t));"
          "for(const f of a.f){const d=JSON.parse(fs.readFileSync(f,'utf8'));const v=M.pack(d,(n)=>ids.get(n));const u=M.unpack(v,t),m=M.build(u.d,u.index,props);"
          "console.log(JSON.stringify(v));console.log(JSON.stringify([m.containers.map(c=>c.orientation||null),(m.extras||[]).map(c=>c.orientation||null)]));}")
    files = [str(generated / a / "derelict.json") for a in addresses]
    arg = {"n": names, "f": files, "props": str(static / "piece_props.json"),
           "index": "D:/Orca/NMS-Derelict-Probe-analysis/meshcache/index.json"}
    out = subprocess.run(["node", "-e", js, str(static / "model.js")], input=json.dumps(arg), capture_output=True,
                         text=True, check=True).stdout.splitlines()
    table_same = json.dumps(pieces_table(index, names), separators=(",", ":"), ensure_ascii=False) == out[0]
    bad, n_or, missing, worst = 0, 0, 0, 0.0
    for k, f in enumerate(files):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        bad += view_json(d, ids) != out[1 + 2 * k]
        js_main, js_extra = json.loads(out[2 + 2 * k])
        want = ec.with_orientations(d)
        for got, cs in ((js_main, want["containers"]), (js_extra, want["extra_containers"])):
            for g, c in zip(got, cs):
                if g is None:
                    missing += 1
                else:
                    n_or += 1
                    worst = max(worst, rotation_angle(g, c["orientation"]))
            missing += abs(len(got) - len(cs))
    print(f"{len(files)} layouts packed in Python and JavaScript, {bad} different; piece table "
          f"{'identical' if table_same else 'DIFFERENT'}; {n_or} containers oriented by model.js, {missing} without, "
          f"largest difference from the Python orientation {worst:.4f} degrees")
    return bad == 0 and table_same and missing == 0 and worst < 0.05 and len(out) == 1 + 2 * len(files)


if __name__ == "__main__" and sys.argv[1:2] == ["--verify"]:
    gen = Path("D:/Orca/NMS-Derelict-Probe-analysis/emu/fastgen/generated")
    picks = sys.argv[2:] or sorted(p.name for p in gen.iterdir() if (p / "derelict.json").exists())
    sys.exit(0 if verify(picks, gen) else 1)
