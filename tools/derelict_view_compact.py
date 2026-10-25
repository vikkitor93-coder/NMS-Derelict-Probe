"""EXPERIMENTAL, local only: compact map view (VIEW_FORMAT 4) <-> published view (format 3, tools/derelict_view.py).

Not published and not read by the scanner/atlas publisher. viewer/static/compact.js expand() is the browser decoder;
the viewer's map "Old / New / Side by side" switch compares both (viewer/static/compact/*.json.gz, built here).

What format 3 stores per system: "r" rooms, "c" crates/footlockers, "i" placed pieces, "x" briefcases/tall lockers.
Format 4 keeps "r" and "e" and rebuilds the rest exactly:
  - "c" and "x" are NOT stored: every container is an authored node of a placed piece (tools/extra_containers_705.py,
    --check reproduces d["containers"]), so they are the piece table's new "k" rows (per scene: kind code, local x, y, z
    from research-output/exact705-generatedbase-scenes-20261019/authored_*container_transform_index.csv) moved by each
    placed piece with the generator's float32 arithmetic, then rounded to cm like format 3. The pieces in a view are
    already rounded (exact yaw, 4-unit steps), so a value can land 1 cm off format 3: such entries go in "cc"/"xc" as
    [index, dx, dy, dz] (cm) corrections. If kinds or rooms ever differ, the format-3 columns are stored as "c3"/"x3".
  - "i" keeps the piece id, rotation and room columns; positions are coded against the room's own cells: structural
    tiles and their decoration sit on a cell of their room at translation = cell centre + R(rot) * (0, 0, -8), so the
    position column becomes the change of that cell's index in the room's cell list (roomCells order, "null" = not on
    an own cell: doors, spawners, stairs, dividers; those are listed in "ex" as 4-unit steps, as differences).
  - The room layout itself is not derivable from the room template (room shapes and decoration variants differ per
    seed: 142 shapes in 159 R_BUG_BARR rooms), so "r" and the piece ids stay per system.

  python -I tools/derelict_view_compact.py --build   writes viewer/static/compact/{top100,local}.{v3,v4}.json.gz
  python -I tools/derelict_view_compact.py --check   Python + Node round trip of every view in those files
"""
import gzip
import json
import math
import struct
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I leaves the script folder off sys.path
import extra_containers_705 as ec  # noqa: E402

VIEW_FORMAT = 4
ROTS = [[[1, 0, 0], [0, 1, 0], [0, 0, 1]], [[0, 0, -1], [0, 1, 0], [1, 0, 0]],
        [[-1, 0, 0], [0, 1, 0], [0, 0, -1]], [[0, 0, 1], [0, 1, 0], [-1, 0, 0]]]
PIVOT = [(0, -2), (-2, 0), (0, 2), (2, 0)]  # R(rot) * (0, 0, -8) in 4-unit steps (x, z)
STEP, CM = 4, 100
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "viewer" / "static" / "compact"
ATLAS_BUNDLE = Path("D:/Orca/NMS-Derelict-Atlas/views/top100.json.gz")  # read only


def _f32(v):
    return struct.unpack("<f", struct.pack("<f", v))[0]


def _round(x):  # JavaScript Math.round
    return math.floor(x + 0.5)


def _delta(a):
    return [v - a[k - 1] if k else v for k, v in enumerate(a)]


def _undelta(a):
    out, s = [], 0
    for v in a:
        s += v
        out.append(s)
    return out


def room_cells(r):
    """model.js roomCells() of a format-3 room row [template, x0, y0, z0, x1, y1, z1, m0, m1, m2, m3]."""
    x0, y0, z0, x1, y1, z1 = r[1:7]
    X, Y, Z = x1 - x0 + 1, y1 - y0 + 1, z1 - z0 + 1
    out = []
    for x in range(X):
        for y in range(Y):
            for z in range(Z):
                i = z + Z * (y + Y * x)
                if i < 64 and (r[7 + (i >> 4)] >> (i & 15)) & 1:
                    out.append((x0 + x, y0 + y, z0 + z))
    return out


def container_rows(names):
    """Per scene name: flat [kind code, local x, y, z, ...], crates/footlockers first, then briefcases/tall lockers,
    each in index order (= extra_containers_705.containers_from_instances order)."""
    main = ec._catalog(ec.MAIN_INDEX, ec.MAIN_KINDS)
    extra = ec._catalog(ec.EXTRA_INDEX, ec.EXTRA_KINDS)
    out = []
    for n in names:
        rows = []
        for row in main.get(n, []) + extra.get(n, []):
            rows += [ec.KIND_CODES[row["container_kind"]], float(row["direct_local_x"]), float(row["direct_local_y"]),
                     float(row["direct_local_z"])]
        out.append(rows)
    return out


def compact_table(t3):
    return {**t3, "v": VIEW_FORMAT, "k": container_rows(t3["n"])}


def table3(t4):
    return {**{k: v for k, v in t4.items() if k != "k"}, "v": 3}


def _pieces(v3):
    ids, rots, dx, dy, dz, room = v3["i"]
    return ids, rots, _undelta(dx), _undelta(dy), _undelta(dz), room


def derived_containers(ids, rots, xs, ys, zs, room, k_rows):
    """Format-3 style absolute columns ([kinds], [rooms], [x cm], [y cm], [z cm]) for main and extra containers."""
    main, extra = [[] for _ in range(5)], [[] for _ in range(5)]
    for j, sid in enumerate(ids):
        rows = k_rows[sid]
        if not rows:
            continue
        A, T = ROTS[rots[j]], (xs[j] * STEP, ys[j] * STEP, zs[j] * STEP)
        for q in range(0, len(rows), 4):
            kind, x, y, z = rows[q], _f32(rows[q + 1]), _f32(rows[q + 2]), _f32(rows[q + 3])
            p = []
            for c in range(3):
                v = _f32(_f32(y * A[1][c]) + _f32(x * A[0][c]))
                v = _f32(v + _f32(z * A[2][c]))
                p.append(_f32(v + _f32(T[c])))
            dst = main if kind < 2 else extra
            dst[0].append(kind)
            dst[1].append(room[j])
            for c in range(3):
                dst[2 + c].append(_round(p[c] * CM))
    return main, extra


def _code_containers(v4, key, col3, got):
    """Store nothing when the rebuild equals format 3, corrections for a few cm, the columns otherwise."""
    want = [col3[0], col3[1], *(_undelta(a) for a in col3[2:5])]
    if want[0] != got[0] or want[1] != got[1]:
        v4[key + "3"] = col3
        return
    fix = [[j, *(want[2 + c][j] - got[2 + c][j] for c in range(3))] for j in range(len(want[0]))
           if any(want[2 + c][j] != got[2 + c][j] for c in range(3))]
    if fix:
        v4[key + "c"] = fix


def encode(v3, t4):
    if v3["v"] != 3:
        raise ValueError(f"view format {v3['v']}, expected 3")
    e = v3["e"]
    cells = [{c: k for k, c in enumerate(room_cells(r))} for r in v3["r"]]
    ids, rots, xs, ys, zs, room = _pieces(v3)
    code, ex, last = [], [], {}
    for j in range(len(ids)):
        ax, az = xs[j] - PIVOT[rots[j]][0], zs[j] - PIVOT[rots[j]][1]
        k = None
        if ax % 2 == 0 and az % 2 == 0 and ys[j] % 2 == 0:
            k = cells[room[j]].get((ax // 2 + e[0], ys[j] // 2 + e[1], az // 2 + e[2]))
        if k is None:
            code.append(None)
            ex.append(j)
        else:
            code.append(k - last.get(room[j], -1))
            last[room[j]] = k
    v4 = {"v": VIEW_FORMAT, "a": v3["a"], "s": v3["s"], "p": v3["p"], "e": e, "r": v3["r"],
          "i": [ids, rots, code, room, [_delta([a[j] for j in ex]) for a in (xs, ys, zs)]]}
    main, extra = derived_containers(ids, rots, xs, ys, zs, room, t4["k"])
    _code_containers(v4, "c", v3["c"], main)
    if "x" in v3:
        v4["x"] = 1
        _code_containers(v4, "x", v3["x"], extra)
    return v4


def _apply(col, fix):
    if fix:
        for j, dx, dy, dz in fix:
            for c, d in enumerate((dx, dy, dz)):
                col[2 + c][j] += d
    return [col[0], col[1], *(_delta(a) for a in col[2:5])]


def decode(v4, t4):
    """Python mirror of compact.js expand(): format-4 view -> the format-3 view."""
    if v4["v"] != VIEW_FORMAT:
        raise ValueError(f"view format {v4['v']}, expected {VIEW_FORMAT}")
    e = v4["e"]
    cells = [room_cells(r) for r in v4["r"]]
    ids, rots, code, room, (exx, exy, exz) = v4["i"]
    exx, exy, exz = _undelta(exx), _undelta(exy), _undelta(exz)
    xs, ys, zs, last, q = [], [], [], {}, 0
    for j, d in enumerate(code):
        if d is None:
            xs.append(exx[q]), ys.append(exy[q]), zs.append(exz[q])
            q += 1
            continue
        k = last.get(room[j], -1) + d
        last[room[j]] = k
        gx, gy, gz = cells[room[j]][k]
        xs.append((gx - e[0]) * 2 + PIVOT[rots[j]][0])
        ys.append((gy - e[1]) * 2)
        zs.append((gz - e[2]) * 2 + PIVOT[rots[j]][1])
    v3 = {"v": 3, "a": v4["a"], "s": v4["s"], "p": v4["p"], "e": e, "r": v4["r"]}
    main, extra = derived_containers(ids, rots, xs, ys, zs, room, t4["k"])
    v3["c"] = v4["c3"] if "c3" in v4 else _apply(main, v4.get("cc"))
    v3["i"] = [ids, rots, _delta(xs), _delta(ys), _delta(zs), room]
    if "x" in v4:
        v3["x"] = v4["x3"] if "x3" in v4 else _apply(extra, v4.get("xc"))
    return v3


def dumps(o):
    return json.dumps(o, separators=(",", ":"), ensure_ascii=False)


def gz(o):
    return gzip.compress(dumps(o).encode("utf-8"), compresslevel=9, mtime=0)


def bundle_v4(b3):
    t4 = compact_table(b3["t"])
    s4 = {a: encode(v, t4) for a, v in b3["s"].items()}
    sizes = {a: [len(gz(b3["s"][a])), len(gz(s4[a]))] for a in s4}
    return {"v": VIEW_FORMAT, "t": t4, "s": s4, "z": sizes}


def local_bundle_v3(skip):
    """Format-3 bundle (tools/build_top_bundle.py build_bundle) of every layout generated on this PC, minus skip."""
    from build_top_bundle import GENERATED, PIECE_INDEX, build_bundle
    layouts, seen, bad = [], set(skip), 0
    for root in GENERATED:
        if not root.exists():
            continue
        for p in sorted(root.iterdir()):
            f = p / "derelict.json"
            if p.name in seen or not f.exists():
                continue
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
            except ValueError:
                bad += 1
                continue
            if "instances" not in d or d.get("address") != p.name:
                continue
            seen.add(p.name)
            layouts.append(d)
    data, _ = build_bundle(layouts, json.loads(PIECE_INDEX.read_text(encoding="utf-8")))
    return json.loads(gzip.decompress(data)), bad


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    top3_bytes = ATLAS_BUNDLE.read_bytes()
    top3 = json.loads(gzip.decompress(top3_bytes))
    local3, bad = local_bundle_v3(top3["s"])
    for name, b3, raw3 in (("top100", top3, top3_bytes), ("local", local3, None)):
        b4 = bundle_v4(b3)
        raw3 = raw3 or gz(b3)
        (OUT / f"{name}.v3.json.gz").write_bytes(raw3)
        raw4 = gz(b4)
        (OUT / f"{name}.v4.json.gz").write_bytes(raw4)
        report(name, b3, b4, len(raw3), len(raw4))
    if bad:
        print(f"{bad} unreadable local layout file(s) skipped")


def report(name, b3, b4, raw3, raw4):
    n = len(b4["s"])
    z3 = sum(v[0] for v in b4["z"].values()) / n
    z4 = sum(v[1] for v in b4["z"].values()) / n
    t3, t4 = len(gz(b3["t"])), len(gz(b4["t"]))
    fixes = sum(len(v.get("cc", [])) + len(v.get("xc", [])) for v in b4["s"].values())
    fallback = sum(("c3" in v) + ("x3" in v) for v in b4["s"].values())
    print(f"{name}: {n} systems; bundle gz v3 {raw3 / 1024:.1f} KB -> v4 {raw4 / 1024:.1f} KB; per system (own gzip) "
          f"v3 {z3:.0f} B -> v4 {z4:.0f} B ({z4 / z3:.1%}); table gz v3 {t3} B, v4 {t4} B; "
          f"{fixes} container cm corrections, {fallback} column fallbacks")
    for total in (87264, 45619):
        print(f"   {total} systems: v3 {total * z3 / 1e6:.1f} MB, v4 {total * z4 / 1e6:.1f} MB (+ table once)")


def check():
    """Python decode(encode(v3)) == v3 for every view, then the same with compact.js expand() in Node, also comparing
    model.js unpack() of both (the structures the page draws from)."""
    ok = True
    for name in ("top100", "local"):
        b3 = json.loads(gzip.decompress((OUT / f"{name}.v3.json.gz").read_bytes()))
        b4 = json.loads(gzip.decompress((OUT / f"{name}.v4.json.gz").read_bytes()))
        bad = [a for a, v in b3["s"].items() if a not in b4["s"] or dumps(decode(b4["s"][a], b4["t"])) != dumps(v)]
        print(f"{name}: Python round trip {len(b3['s']) - len(bad)}/{len(b3['s'])} identical" + (f"; differ: {bad[:20]}" if bad else ""))
        ok &= not bad
    js = ROOT / "tools" / "check_compact_view.js"
    r = subprocess.run(["node", str(js), str(OUT)], capture_output=True, text=True)
    print(r.stdout.strip() or r.stderr.strip())
    return ok and r.returncode == 0


if __name__ == "__main__":
    if sys.argv[1:2] == ["--build"]:
        build()
    elif sys.argv[1:2] == ["--check"]:
        sys.exit(0 if check() else 1)
    else:
        sys.exit(__doc__)
