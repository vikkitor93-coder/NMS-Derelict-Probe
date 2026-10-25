"""Top-down render of a generated derelict from the game's own piece data (pure Python, stdlib only).

    python -I minimap/geomrender.py <ADDRESS16 | GLYPHS12> [--zooms 9,14,...] [--out DIR] [--png]

For every deck it draws, seen from above and brightened:
  1. the real geometry of the placed pieces (meshcache, built by tools/build_piece_meshes_705.py from the user's own installed game),
     cut at CUT metres above the floor so ceilings don't hide the rooms, shaded by height and slope;
  2. floor-standing props as footprint boxes (the piece index's fixtures; loot containers are left out, the overlay draws them);
  3. the walls, from each piece's waist-height footprint with the viewer's finishing (clip to rooms, fill pillar hollows, cut
     door openings; port of wallsOf in viewer/static/model.js).
A faint room tint helps orientation. Output: <out>/<address>/deck<level>_z<px per cell>.ppm (P6) and meta.json (written last).

Coordinates: layout metres. A piece vertex v (piece-local) goes to world[c] = sum_i v[i] * A[i][c] + T[c] with A = the instance's
source_axes (rows) and T = its translation. Grid: u = x/8 + e0 + 0.5, v = z/8 + e2 + 0.5, level = round(y/8) + e1; image column =
(13 - u) * px, row = (13 - v) * px (+x to the left, +z up, as in the overlay and the viewer). Deck `level` occupies world y in
[(level - e1) * 8, +CUT]. The game's textures are not used (flat shading); props are boxes, not their real models.
"""
from __future__ import annotations

import argparse
import array
import json
import math
import struct
import sys
import time
import zlib
from collections import deque
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import layoutmodel as LM  # noqa: E402
import settings as ST  # noqa: E402

GRID = 13
CUT = 2.4            # metres above the deck floor where the structure is cut
BG = (15, 19, 24)
FLOOR_LO, FLOOR_HI = (62, 76, 94), (132, 152, 176)   # surfaces by height
FIXTURE = (150, 160, 150)
WALL = (226, 232, 240)
GAIN = 1.3           # brightness boost
TINT = 0.16          # strength of the room tint
LIGHT = (0.35, 0.88, 0.32)
P = 32               # wall raster: px per cell (as the viewer)
MARGIN = 5           # outer-wall margin (px)
DEFAULT_ZOOMS = [9, 14, 20, 30, 44, 64]
PALETTE = [(78, 155, 230), (230, 150, 78), (95, 191, 106), (208, 97, 125), (154, 127, 224), (215, 192, 74), (70, 183, 176),
           (201, 119, 63), (122, 160, 194), (176, 111, 176), (143, 179, 75), (224, 122, 106), (92, 143, 214), (196, 163, 90)]


# ---------------------------------------------------------------- meshes
class Pieces:
    def __init__(self, mesh_dir: Path):
        self.dir = mesh_dir
        self.index = json.loads((mesh_dir / "index.json").read_text(encoding="utf-8"))
        self.cache: dict = {}

    def entry(self, scene: str):
        return self.index.get(scene.upper()) or self.index.get(scene)

    def mesh(self, scene: str):
        e = self.entry(scene)
        if not e or not e.get("tris"):
            return None
        sha = e["mesh"]
        if sha not in self.cache:
            try:
                b = (self.dir / "pieces" / f"{sha}.bin").read_bytes()
                nv, ni = struct.unpack_from("<II", b, 0)
                v = array.array("f")
                v.frombytes(b[8:8 + 12 * nv])
                ix = array.array("I")
                ix.frombytes(b[8 + 12 * nv:8 + 12 * nv + 4 * ni])
                self.cache[sha] = ([(v[3 * i], v[3 * i + 1], v[3 * i + 2]) for i in range(nv)], list(ix))
            except (OSError, struct.error):
                self.cache[sha] = None
        return self.cache[sha]


def clip_below(tri, ycut):
    """Parts of a triangle (3 xyz tuples) with y <= ycut, as a list of triangles."""
    inside = [p[1] <= ycut for p in tri]
    n = sum(inside)
    if n == 3:
        return [tri]
    if n == 0:
        return []
    poly = []
    for i in range(3):
        a, b = tri[i], tri[(i + 1) % 3]
        ia, ib = a[1] <= ycut, b[1] <= ycut
        if ia:
            poly.append(a)
        if ia != ib:
            t = (ycut - a[1]) / (b[1] - a[1])
            poly.append((a[0] + t * (b[0] - a[0]), ycut, a[2] + t * (b[2] - a[2])))
    return [(poly[0], poly[i], poly[i + 1]) for i in range(1, len(poly) - 1)]


def deck_triangles(d: dict, pieces: Pieces, level: int, cut: float = CUT):
    """[(p0, p1, p2, room_index)] in world space, clipped to y <= base + cut; what lies below the deck is dropped."""
    e = d.get("entrance_origin") or [6, 3, 0]
    base = (level - e[1]) * 8.0
    out = []
    for inst in d["instances"]:
        mesh = pieces.mesh(inst["scene_resource"])
        if not mesh:
            continue
        A, T = inst["source_axes"], inst["translation"]
        if not (base - 9 <= T[1] <= base + 9):
            continue
        verts, idx = mesh
        w = [(x * A[0][0] + y * A[1][0] + z * A[2][0] + T[0],
              x * A[0][1] + y * A[1][1] + z * A[2][1] + T[1],
              x * A[0][2] + y * A[1][2] + z * A[2][2] + T[2]) for (x, y, z) in verts]
        room = inst.get("room_index", -1)
        # pieces of the deck below are rooms one cell tall: their ceilings sit at this deck's floor, so only what rises above
        # the floor (ladder wells, stair openings) counts; this deck's own pieces include the floor slab's thickness
        lowest = base - 0.5 if T[1] >= base - 0.5 else base + 0.05
        for k in range(0, len(idx) - 2, 3):
            tri = (w[idx[k]], w[idx[k + 1]], w[idx[k + 2]])
            if min(p[1] for p in tri) < lowest:
                continue
            for part in clip_below(tri, base + cut):
                out.append((*part, room))
    return out, base


# ---------------------------------------------------------------- walls (port of wallsOf, viewer/static/model.js)
def walls_of(d: dict, e, model: dict, pieces: Pieces) -> dict[int, list[tuple[int, int, int, int, int]]]:
    """level -> [(x0, x1, z0, z1, room)] wall rectangles in raster px (P per cell), finished like the viewer's."""
    N = GRID * P
    raw: dict[int, list] = {}
    for inst in d["instances"]:
        ent = pieces.entry(inst["scene_resource"])
        if not ent or not ent.get("walls"):
            continue
        A, T = inst["source_axes"], inst["translation"]
        base = LM.round_(T[1] / 8) + e[1]
        for w in ent["walls"]:
            x0, z0, x1, z1 = w[:4]
            dl = w[4] if len(w) > 4 else 0
            xs = [x * A[0][0] + z * A[2][0] + T[0] for x in (x0, x1) for z in (z0, z1)]
            zs = [x * A[0][2] + z * A[2][2] + T[2] for x in (x0, x1) for z in (z0, z1)]
            raw.setdefault(base + dl, []).append((inst.get("room_index", -1), min(xs) / 8 + e[0] + 0.5, max(xs) / 8 + e[0] + 0.5,
                                                  min(zs) / 8 + e[2] + 0.5, max(zs) / 8 + e[2] + 0.5))
    out: dict[int, list] = {}
    for level, rects in raw.items():
        wall = array.array("h", [-1]) * (N * N)
        allowed = bytearray(N * N)
        in_room = array.array("h", [-1]) * (N * N)
        for idx, r in model["rooms"].items():
            for (cx, cy, cz) in r["cells"]:
                if cy != level:
                    continue
                for z in range(max(0, cz * P - MARGIN), min(N, (cz + 1) * P + MARGIN)):
                    allowed[z * N + max(0, cx * P - MARGIN):z * N + min(N, (cx + 1) * P + MARGIN)] = b"\x01" * (
                        min(N, (cx + 1) * P + MARGIN) - max(0, cx * P - MARGIN))
                for z in range(cz * P, (cz + 1) * P):
                    in_room[z * N + cx * P:z * N + (cx + 1) * P] = array.array("h", [idx]) * P
        for (room, u0, u1, v0, v1) in rects:
            for z in range(max(0, math.floor(v0 * P)), min(N, math.ceil(v1 * P))):
                row = z * N
                for x in range(max(0, math.floor(u0 * P)), min(N, math.ceil(u1 * P))):
                    if allowed[row + x]:
                        wall[row + x] = room
        # fill small, compact, fully enclosed free areas inside rooms (a pillar's hollow)
        seen = bytearray(N * N)
        limit = 16 * P * P // 64
        for s0 in range(N * N):
            if seen[s0] or wall[s0] >= 0 or in_room[s0] < 0:
                continue
            comp = [s0]
            seen[s0] = 1
            opened = False
            owner = -1
            xa = xb = s0 % N
            za = zb = s0 // N
            head = 0
            while head < len(comp):
                p = comp[head]
                head += 1
                x, z = p % N, p // N
                xa, xb, za, zb = min(xa, x), max(xb, x), min(za, z), max(zb, z)
                for q in ((p - 1) if x > 0 else -1, (p + 1) if x < N - 1 else -1, (p - N) if z > 0 else -1, (p + N) if z < N - 1 else -1):
                    if q < 0:
                        opened = True
                    elif wall[q] >= 0:
                        owner = wall[q]
                    elif in_room[q] < 0:
                        opened = True
                    elif not seen[q]:
                        seen[q] = 1
                        comp.append(q)
            if len(comp) > limit:
                opened = True
            wpx, hpx = (xb - xa + 1) / P * 8, (zb - za + 1) / P * 8
            if not opened and wpx <= 4.5 and hpx <= 4.5:
                for p in comp:
                    wall[p] = owner
        for (ex, ez, vert, _slime) in model["decks"].get(level, {}).get("doors", []):   # door openings
            hu, hv = (0.35, 0.25) if vert else (0.25, 0.35)
            for z in range(max(0, math.floor((ez - hv) * P)), min(N, math.ceil((ez + hv) * P))):
                for x in range(max(0, math.floor((ex - hu) * P)), min(N, math.ceil((ex + hu) * P))):
                    wall[z * N + x] = -1
        rects_out = []
        for z in range(N):                                    # runs per row
            x = 0
            row = z * N
            while x < N:
                r = wall[row + x]
                if r < 0:
                    x += 1
                    continue
                x2 = x
                while x2 + 1 < N and wall[row + x2 + 1] == r:
                    x2 += 1
                rects_out.append((x, x2 + 1, z, z + 1, r))
                x = x2 + 1
        out[level] = rects_out
    return out


def fixtures_of(d: dict, e, pieces: Pieces, props: dict | None):
    """level -> [(u0, u1, v0, v1, h1_cells)] footprint boxes of floor-standing props (tagged loot containers left out)."""
    out: dict[int, list] = {}
    for inst in d["instances"]:
        key = inst["scene_resource"].upper()
        ent = pieces.entry(key)
        if not ent or not ent.get("fixtures"):
            continue
        tagged = {t[0] for t in ((props or {}).get(key, {}).get("p") or [])}
        A, T = inst["source_axes"], inst["translation"]
        level = LM.round_(T[1] / 8) + e[1]
        base = (level - e[1]) * 8
        for fi, b in enumerate(ent["fixtures"]):
            if fi in tagged:
                continue
            lo, hi = [1e18] * 3, [-1e18] * 3
            for x in (b[0], b[3]):
                for y in (b[1], b[4]):
                    for z in (b[2], b[5]):
                        for k in range(3):
                            q = x * A[0][k] + y * A[1][k] + z * A[2][k] + T[k]
                            lo[k], hi[k] = min(lo[k], q), max(hi[k], q)
            out.setdefault(level, []).append((lo[0] / 8 + e[0] + 0.5, hi[0] / 8 + e[0] + 0.5, lo[2] / 8 + e[2] + 0.5,
                                              hi[2] / 8 + e[2] + 0.5, max(0.0, hi[1] - base)))
    return out


# ---------------------------------------------------------------- shading + raster
def shade(tri, base, cut, room):
    """(sort key, colour) of a world triangle, or None when it is edge-on from above. Facing is ignored (winding is not reliable)."""
    (x0, y0, z0), (x1, y1, z1), (x2, y2, z2) = tri
    ux, uy, uz, vx, vy, vz = x1 - x0, y1 - y0, z1 - z0, x2 - x0, y2 - y0, z2 - z0
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    ln = math.sqrt(nx * nx + ny * ny + nz * nz)
    if ln < 1e-9 or abs(ny) / ln < 0.05:
        return None
    s = 1 if ny > 0 else -1
    lam = max(0.0, (s * (nx * LIGHT[0] + nz * LIGHT[2]) + abs(ny) * LIGHT[1]) / ln)
    ym = (y0 + y1 + y2) / 3 - base
    t = max(0.0, min(1.0, ym / cut))
    k = (0.62 + 0.38 * lam) * GAIN
    tint = PALETTE[room % len(PALETTE)] if room >= 0 else None
    col = []
    for i in range(3):
        c = FLOOR_LO[i] + (FLOOR_HI[i] - FLOOR_LO[i]) * t
        if tint:
            c = c * (1 - TINT) + tint[i] * TINT
        col.append(min(255, round(c * k)))
    return round(ym, 2), tuple(col)


def fill_polygon(buf, w, h, pts, col):
    (ax, ay), (bx, by), (cx, cy) = pts
    ymin, ymax = min(ay, by, cy), max(ay, by, cy)
    r0, r1 = max(0, math.ceil(ymin - 0.5)), min(h - 1, math.floor(ymax - 0.5))
    if r1 < r0:
        return
    cb = bytes(col)
    edges = ((ax, ay, bx, by), (bx, by, cx, cy), (cx, cy, ax, ay))
    for r in range(r0, r1 + 1):
        yc = r + 0.5
        xs = []
        for (x0, y0, x1, y1) in edges:
            if (y0 <= yc < y1) or (y1 <= yc < y0):
                xs.append(x0 + (yc - y0) * (x1 - x0) / (y1 - y0))
        if len(xs) < 2:
            continue
        c0, c1 = max(0, math.ceil(min(xs) - 0.5)), min(w - 1, math.floor(max(xs) - 0.5))
        if c1 >= c0:
            buf[(r * w + c0) * 3:(r * w + c1 + 1) * 3] = cb * (c1 - c0 + 1)


def fill_rect(buf, w, h, x0, x1, y0, y1, col):
    c0, c1, r0, r1 = max(0, round(x0)), min(w, round(x1)), max(0, round(y0)), min(h, round(y1))
    if c1 <= c0 or r1 <= r0:
        return
    row = bytes(col) * (c1 - c0)
    for r in range(r0, r1):
        buf[(r * w + c0) * 3:(r * w + c1) * 3] = row


def raster(tris, base, e, px, fixtures, walls, cells=(), cut=CUT):
    w = h = round(GRID * px)
    buf = bytearray(bytes(BG) * (w * h))
    for (cx, cz, room) in cells:                                # base floor under every room cell (pieces without a mesh)
        tint = PALETTE[room % len(PALETTE)]
        col = tuple(min(255, round((FLOOR_LO[i] * (1 - TINT) + tint[i] * TINT) * GAIN * 0.8)) for i in range(3))
        fill_rect(buf, w, h, (GRID - cx - 1) * px, (GRID - cx) * px, (GRID - cz - 1) * px, (GRID - cz) * px, col)
    items = []
    for (a, b, c, room) in tris:
        s = shade((a, b, c), base, cut, room)
        if s is None:
            continue
        pts = [((GRID - (p[0] / 8 + e[0] + 0.5)) * px, (GRID - (p[2] / 8 + e[2] + 0.5)) * px) for p in (a, b, c)]
        items.append((s[0], s[1], pts))
    items.sort(key=lambda it: it[0])
    for _y, col, pts in items:                                  # 1. real geometry, lowest first
        fill_polygon(buf, w, h, pts, col)
    for (u0, u1, v0, v1, h1) in fixtures:                       # 2. props as footprint boxes, taller = lighter
        t = min(1.0, h1 / cut)
        col = tuple(min(255, round((FIXTURE[i] * (0.55 + 0.45 * t)) * GAIN)) for i in range(3))
        fill_rect(buf, w, h, (GRID - u1) * px, (GRID - u0) * px, (GRID - v1) * px, (GRID - v0) * px, col)
    k = px / P
    for (x0, x1, z0, z1, room) in walls:                        # 3. walls (raster px -> output px; the image is mirrored in x and z)
        tint = PALETTE[room % len(PALETTE)] if room >= 0 else WALL
        col = tuple(min(255, round((WALL[i] * (1 - TINT) + tint[i] * TINT) * 0.92)) for i in range(3))
        fill_rect(buf, w, h, (GRID * P - x1) * k, (GRID * P - x0) * k, (GRID * P - z1) * k, (GRID * P - z0) * k, col)
    if cells:                                                   # trim to the room cells plus the viewer's outer-wall margin
        out = bytearray(bytes(BG) * (w * h))
        m = MARGIN / P * px
        for (cx, cz, _room) in cells:
            c0, c1 = max(0, round((GRID - cx - 1) * px - m)), min(w, round((GRID - cx) * px + m))
            for r in range(max(0, round((GRID - cz - 1) * px - m)), min(h, round((GRID - cz) * px + m))):
                out[(r * w + c0) * 3:(r * w + c1) * 3] = buf[(r * w + c0) * 3:(r * w + c1) * 3]
        buf = out
    return w, h, buf


def write_ppm(path: Path, w: int, h: int, buf) -> None:
    path.write_bytes(b"P6\n%d %d\n255\n" % (w, h) + bytes(buf))


def write_png(path: Path, w: int, h: int, buf) -> None:
    raw = b"".join(b"\x00" + bytes(buf[r * w * 3:(r + 1) * w * 3]) for r in range(h))

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def render_derelict(d: dict, pieces: Pieces, out: Path, zooms=DEFAULT_ZOOMS, png=False, props=None, log=print) -> dict:
    e = d.get("entrance_origin") or [6, 3, 0]
    model = LM.build_model(d)
    levels = model["levels"]
    out.mkdir(parents=True, exist_ok=True)
    meta = {"address": d.get("address"), "entrance": e, "levels": levels, "zooms": zooms, "cut": CUT, "files": {}}
    t0 = time.time()
    walls = walls_of(d, e, model, pieces)
    fixtures = fixtures_of(d, e, pieces, props)
    log(f"walls and fixtures: {time.time() - t0:.1f}s")
    for level in levels:
        t0 = time.time()
        tris, base = deck_triangles(d, pieces, level)
        for z in zooms:
            w, h, buf = raster(tris, base, e, z, fixtures.get(level, []), walls.get(level, []), model["decks"][level]["cells"])
            name = f"deck{level}_z{z}.ppm"
            write_ppm(out / name, w, h, buf)
            if png:
                write_png(out / name.replace(".ppm", ".png"), w, h, buf)
            meta["files"][f"{level}/{z}"] = name
        log(f"deck {level}: {len(tris)} triangles, {time.time() - t0:.1f}s")
    (out / "meta.json.tmp").write_text(json.dumps(meta), encoding="utf-8")
    (out / "meta.json.tmp").replace(out / "meta.json")   # written last: its presence means the set is complete
    return meta


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("derelict", help="16-hex address or 12 glyph hex")
    ap.add_argument("--zooms", default=",".join(map(str, DEFAULT_ZOOMS)))
    ap.add_argument("--out", help="output folder (default: <analysis>/minimap-cache/geom)")
    ap.add_argument("--png", action="store_true", help="also write PNGs (for looking at the result)")
    ap.add_argument("--gain", type=float, default=GAIN, help="brightness boost")
    ap.add_argument("--name", help="output sub-folder name (default: the address)")
    a = ap.parse_args(argv)
    globals()["GAIN"] = a.gain
    p = ST.paths()
    sys.path.insert(0, str(HERE.parent / "tools"))
    import predict_end_reward_705 as PR
    t = a.derelict.upper().replace(" ", "")
    addr = PR.glyphs_to_address(t) if len(t) == 12 else t
    addr = f"{int(addr, 16) & ~(0xF << 52):016X}"
    PR.FASTGEN, PR.LAYOUT_DIRS = p["fast_generate"], p["layout_dirs"]
    d = PR.load_layout(addr)
    props = None
    try:
        props = json.loads((HERE.parent / "viewer" / "static" / "piece_props.json").read_text(encoding="utf-8")).get("scenes")
    except (OSError, ValueError):
        pass
    out = Path(a.out) if a.out else p["cache"] / "geom"
    render_derelict(d, Pieces(p["analysis"] / "meshcache"), out / (a.name or addr), [int(z) for z in a.zooms.split(",")], a.png, props)
    print("written to", out / (a.name or addr))
    return 0


if __name__ == "__main__":
    sys.exit(main())
