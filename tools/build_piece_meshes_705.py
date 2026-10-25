"""Build simple (coarsest-LOD) meshes for the dungeon pieces used by generated derelicts, for the viewer's 3D view.

  python -I tools/build_piece_meshes_705.py [--generated DIR ...] [--rebuild]

For every scene resource placed in the generated derelicts (instances[].scene_resource), it follows the scene graph
(REFERENCE -> SCENEGRAPH scenes, incl. InstanceTransforms; props/decoration/infestation/effects are skipped) down to MESH nodes, takes the coarsest LOD of each mesh
family in each scene file, and merges the triangles into one piece-local mesh (the space the instance matrix
source_axes/translation applies to). Read-only on the game: members are extracted from the NMS 7.05 .pak files with
HGPAKtool and decoded with the pinned MBINCompiler into the cache folder.

Output (CACHE = D:/Orca/NMS-Derelict-Probe-analysis/meshcache):
  pieces/<sha1(scene)>.bin  little-endian: u32 vertex count, u32 index count, f32 xyz * n, u32 indices
  index.json                {scene_resource: {"mesh": "<sha1>", "tris": n, "bbox": [min, max],
                             "fixtures": [[x0, y0, z0, x1, y1, z1], ...]}, "_meta": {...}}
  fixtures = piece-local AABBs of floor-standing props (worktops, shelves, machinery, ...): areas you cannot walk.
  walls    = piece-local 2D footprint of structure at waist height (walls, alcoves, pillars), merged rectangles
             [x0, z0, x1, z1, dl]; dl = deck offset from the piece's own deck (a ladder piece also walls the deck above).
Positions are half floats in the game files (stride 16, first 3 of 4 components); indices are u16 or u32.
Euler rotations (degrees) are composed in the game's order R = Ry * Rx * Rz (column vectors: Z first, then X, then Y;
three.js "YXZ"), established from the lying/leaning loot containers (research-output/container-orientation-20261021/
euler_order_check.txt; before 2026-10-21 this tool used R = Rz * Ry * Rx, wrong for parts rotated on more than one axis).
"""
import argparse
import hashlib
import json
import math
import re
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

PCBANKS = Path("G:/SteamLibrary/steamapps/common/No Man's Sky/GAMEDATA/PCBANKS")
MBINCOMPILER = Path("D:/Orca/Temp/mbincompiler-7.04.1-pre3/MBINCompiler.exe")
CACHE = Path("D:/Orca/NMS-Derelict-Probe-analysis/meshcache")
GENERATED = [Path("D:/Orca/NMS-Derelict-Probe-analysis/emu/fastgen/generated"), Path("D:/Orca/NMS-Derelict-Probe-analysis/emu/generated")]
LOD_RE = re.compile(r"^(.*?)LOD(\d+)$", re.I)
# Simple view: structure only. References into these are skipped (props/decoration were ~95% of all triangles).
SKIP_REFS = ("/props/", "/decoration/", "/infestation/", "/effects/", "explodingbarrel")
# Skipped props that stand on the floor become "fixture" boxes (areas you cannot walk through). Containers are drawn
# separately by the viewer, slime/effects are not obstacles.
FIXTURE_REFS = ("/props/", "/decoration/", "explodingbarrel")
# The structural wrapper scenes (dungeon/empty/room_floor, room_wall, ...) carry their own cell-sized 0..4 boxes
# (helper volumes, not visible walls: they drew as slabs and as seams on every cell edge). Their own geometry is
# skipped; the visible structure is the base-building parts they reference (cuberoom_wallside_3, ..._incorner_3, ...).
SKIP_OWN_GEOMETRY = ("models/space/poi/dungeon/empty/",)
NOT_FIXTURES = ("/cratem.scene", "/foot_locker.scene")


def mesh_aabb(scene_name, depth=0):
    """Union of the LOD0 MESH AABB attributes in a scene (and its references), in that scene's space."""
    root = scene(scene_name)
    if root is None or depth > 12:
        return None
    lo, hi = [math.inf] * 3, [-math.inf] * 3

    def grow(mat, a, b):
        for cx in (a[0], b[0]):
            for cy in (a[1], b[1]):
                for cz in (a[2], b[2]):
                    q = [mat[i][0] * cx + mat[i][1] * cy + mat[i][2] * cz + mat[i][3] for i in range(3)]
                    for i in range(3):
                        lo[i], hi[i] = min(lo[i], q[i]), max(hi[i], q[i])

    def walk(n, parent, is_root=False):
        mat = parent if is_root else matmul(parent, trs(n["t"]))
        at = n["attrs"]
        if n["type"] == "MESH" and at.get("LODLEVEL", "0") == "0" and "AABBMINX" in at:
            try:
                grow(mat, [float(at["AABBMIN" + k]) for k in "XYZ"], [float(at["AABBMAX" + k]) for k in "XYZ"])
            except (KeyError, ValueError):
                pass
        elif n["type"] == "REFERENCE" and at.get("SCENEGRAPH", "").upper().endswith(".SCENE.MBIN"):
            sub = mesh_aabb(member(at["SCENEGRAPH"]), depth + 1)
            if sub:
                for it in n["inst"] or [None]:
                    grow(mat if it is None else matmul(mat, trs(it)), *sub)
        if n["type"] in ("COLLISION", "LIGHT"):
            return
        for c in n["children"]:
            walk(c, mat)

    walk(root, [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]], True)
    return (lo, hi) if lo[0] < math.inf else None


def member(resource):
    """Game resource path (MODELS\\...\\X.SCENE.MBIN / X.GEOMETRY.MBIN) -> archive member name."""
    m = resource.replace("\\", "/").lower()
    if m.endswith(".geometry.mbin"):
        m += ".pc"
    return m


# ---------------------------------------------------------------- archives

def pak_index():
    from hgpaktool import HGPAKFile
    paks = sorted(PCBANKS.glob("*.pak"))
    stamp = [[p.name, p.stat().st_size, int(p.stat().st_mtime)] for p in paks]
    path = CACHE / "pak-index.json"
    if path.exists():
        cached = json.loads(path.read_text(encoding="utf-8"))
        if cached.get("stamp") == stamp:
            return cached["members"]
    members = {}
    for p in paks:
        try:
            with HGPAKFile(p) as a:
                for n in a.filenames:
                    if n.endswith((".scene.mbin", ".geometry.mbin.pc", ".geometry.data.mbin.pc")):
                        members.setdefault(n.lower(), p.name)
        except Exception as exc:  # some paks are not HGPAK archives; they hold nothing we need
            print("skipping", p.name, type(exc).__name__, flush=True)
    path.write_text(json.dumps({"stamp": stamp, "members": members}), encoding="utf-8")
    return members


def extract(names, index):
    """Extract archive members into CACHE/raw/<member>; returns the names that exist in some archive."""
    from hgpaktool import HGPAKFile
    raw = CACHE / "raw"
    by_pak, found = defaultdict(list), []
    for n in names:
        if (raw / n).exists():
            found.append(n)
        elif n in index:
            by_pak[index[n]].append(n)
    for pak, wanted in by_pak.items():
        with HGPAKFile(PCBANKS / pak) as a:
            for name, data in a.extract(wanted):
                dest = raw / name.lower()
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
                found.append(name.lower())
    return found


def decompile(names):
    """MBINCompiler -> .MXML next to each member (batched; skips ones already converted)."""
    todo = [CACHE / "raw" / n for n in names if not mxml_path(n).exists()]
    for i in range(0, len(todo), 150):
        subprocess.run([str(MBINCOMPILER), "convert", "-y", "-q", *map(str, todo[i:i + 150])],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def mxml_path(name):
    p = CACHE / "raw" / name
    stem = p.name
    for suffix in (".mbin.pc", ".mbin"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    return p.with_name(stem + ".MXML")


# ---------------------------------------------------------------- scenes

def prop(el, name):
    for c in el:
        if c.tag == "Property" and c.get("name") == name:
            return c
    return None


def parse_node(el):
    def val(name, default=""):
        p = prop(el, name)
        return p.get("value", default) if p is not None else default

    tr = prop(el, "Transform")
    t = {k: float(prop(tr, k).get("value")) for k in ("TransX", "TransY", "TransZ", "RotX", "RotY", "RotZ", "ScaleX", "ScaleY", "ScaleZ")} if tr is not None else None
    attrs = {}
    a = prop(el, "Attributes")
    if a is not None:
        for item in a:
            attrs[prop(item, "Name").get("value").upper()] = prop(item, "Value").get("value")
    inst = []
    it = prop(el, "InstanceTransforms")
    if it is not None:
        for item in it:
            inst.append({k: float(prop(item, k).get("value")) for k in ("TransX", "TransY", "TransZ", "RotX", "RotY", "RotZ", "ScaleX", "ScaleY", "ScaleZ")})
    ch = prop(el, "Children")
    return {"name": val("Name"), "type": val("Type"), "t": t, "attrs": attrs, "inst": inst,
            "children": [parse_node(c) for c in ch] if ch is not None else []}


_scenes = {}


def scene(name):
    if name not in _scenes:
        p = mxml_path(name)
        _scenes[name] = parse_node(ET.parse(p).getroot()) if p.exists() else None
    return _scenes[name]


def walk_refs(n, out_scenes, out_geoms):
    if n["type"] == "REFERENCE" and n["attrs"].get("SCENEGRAPH", "").upper().endswith(".SCENE.MBIN"):
        out_scenes.add(member(n["attrs"]["SCENEGRAPH"]))
    if n["attrs"].get("GEOMETRY", "").upper().endswith(".GEOMETRY.MBIN"):  # set on the scene root, used by its MESH nodes
        out_geoms.add(member(n["attrs"]["GEOMETRY"]))
    for c in n["children"]:
        walk_refs(c, out_scenes, out_geoms)


# ---------------------------------------------------------------- maths (4x4, column vectors, row-major lists)

def matmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


ROT_MULTI = [0]
ROT_SAMPLES = {}


def trs(t):
    if t is None:
        return [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    rx, ry, rz = (math.radians(t[k]) for k in ("RotX", "RotY", "RotZ"))
    if sum(1 for r in (rx, ry, rz) if abs(r) > 1e-6) > 1:
        ROT_MULTI[0] += 1
        key = tuple(round(t[k], 1) for k in ("RotX", "RotY", "RotZ"))
        ROT_SAMPLES[key] = ROT_SAMPLES.get(key, 0) + 1
    cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
    rxm = [[1, 0, 0], [0, cx, -sx], [0, sx, cx]]
    rym = [[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]
    rzm = [[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]]
    r = [[sum(rym[i][k] * sum(rxm[k][m] * rzm[m][j] for m in range(3)) for k in range(3)) for j in range(3)] for i in range(3)]  # Ry*Rx*Rz
    s = (t["ScaleX"], t["ScaleY"], t["ScaleZ"])
    return [[r[0][0] * s[0], r[0][1] * s[1], r[0][2] * s[2], t["TransX"]],
            [r[1][0] * s[0], r[1][1] * s[1], r[1][2] * s[2], t["TransY"]],
            [r[2][0] * s[0], r[2][1] * s[1], r[2][2] * s[2], t["TransZ"]],
            [0, 0, 0, 1]]


# ---------------------------------------------------------------- geometry

_geo = {}


def geometry(name):
    """{IDSTRING: (positions[(x,y,z)], indices[])} for one .geometry.mbin.pc."""
    if name in _geo:
        return _geo[name]
    head, data_path = mxml_path(name), CACHE / "raw" / name.replace(".geometry.mbin.pc", ".geometry.data.mbin.pc")
    streams = {}
    if head.exists() and data_path.exists():
        root = ET.parse(head).getroot()
        data = data_path.read_bytes()
        idx16 = prop(root, "Indices16Bit").get("value") == "1"
        pl = prop(root, "PositionVertexLayout")
        stride = int(prop(pl, "Stride").get("value"))
        ok = False
        for el in (prop(pl, "VertexElements") if prop(pl, "VertexElements") is not None else []):
            if prop(el, "SemanticID").get("value") == "0" and prop(el, "Type").get("value") == "5131" and prop(el, "Offset").get("value") == "0":
                ok = True
        if ok and stride:
            for m in (prop(root, "StreamMetaDataArray") if prop(root, "StreamMetaDataArray") is not None else []):
                g = lambda k: int(prop(m, k).get("value"))  # noqa: E731
                nv = g("VertexPositionDataSize") // stride
                vpo, vdo, ido, ids = g("VertexPositionDataOffset"), g("VertexDataOffset"), g("IndexDataOffset"), g("IndexDataSize")
                raw = data[vpo:vpo + nv * stride]
                if len(raw) < nv * stride:
                    continue
                pos = [struct.unpack_from("<3e", raw, i * stride) for i in range(nv)]
                ib = data[vdo + ido:vdo + ido + ids]
                idx = list(struct.unpack(f"<{len(ib) // 2}H", ib)) if idx16 else list(struct.unpack(f"<{len(ib) // 4}I", ib))
                if idx and max(idx) < nv:
                    streams[prop(m, "IdString").get("value").upper()] = (pos, idx)
    _geo[name] = streams
    return streams


WALL_BAND = (0.5, 2.0)  # waist-to-chest height above the piece floor: blocks walking (walls, pillars, alcoves);
                        # stays under archway/door lintels (~2.5-3 units), which would otherwise close corridors
WALL_RES = 0.25         # footprint pixel size, layout units (0.5 closed narrow corridor bends)
WALL_LOD = 1            # LOD used for footprints (the coarsest LODs are bounding boxes and would fill whole cells)


WALL_SKIP_OWN = ("models/space/poi/dungeon/",)  # for footprints: no own geometry of any dungeon wrapper scene


def wall_footprint(scene_name):
    """[x0, z0, x1, z1, dl] rects for every deck the piece reaches (dl = deck offset -1/0/+1; ladders span two decks)."""
    verts, tris = piece_mesh(scene_name, WALL_LOD, skip_own=WALL_SKIP_OWN)
    out = []
    for dl in (-1, 0, 1):
        out += [r + [dl] for r in wall_footprint_band(verts, tris, WALL_BAND[0] + 8 * dl, WALL_BAND[1] + 8 * dl)]
    return out


def wall_footprint_band(verts, tris, lo, hi):
    """Piece-local 2D footprint of structure at waist height, as merged rectangles [x0, z0, x1, z1] (layout units).

    Each triangle is clipped to WALL_BAND in y; the clipped polygon's xz projection is rasterised at WALL_RES (edges
    plus scanline fill), which captures vertical walls as lines and solid blocks as areas."""
    px = set()

    def mark(x, z):
        px.add((math.floor(x / WALL_RES), math.floor(z / WALL_RES)))

    for k in range(0, len(tris) - 2, 3):
        tri = [verts[tris[k]], verts[tris[k + 1]], verts[tris[k + 2]]]
        if max(v[1] for v in tri) < lo or min(v[1] for v in tri) > hi:
            continue
        poly = tri
        for bound, keep_above in ((lo, True), (hi, False)):  # Sutherland-Hodgman clip against y >= lo, y <= hi
            out = []
            for i in range(len(poly)):
                a, b = poly[i], poly[(i + 1) % len(poly)]
                ina = a[1] >= bound if keep_above else a[1] <= bound
                inb = b[1] >= bound if keep_above else b[1] <= bound
                if ina:
                    out.append(a)
                if ina != inb and b[1] != a[1]:
                    f = (bound - a[1]) / (b[1] - a[1])
                    out.append((a[0] + f * (b[0] - a[0]), bound, a[2] + f * (b[2] - a[2])))
            poly = out
            if not poly:
                break
        if not poly:
            continue
        pts = [(v[0], v[2]) for v in poly]
        for i in range(len(pts)):  # edges
            (x0, z0), (x1, z1) = pts[i], pts[(i + 1) % len(pts)]
            n = max(1, int(math.hypot(x1 - x0, z1 - z0) / (WALL_RES * 0.4)))
            for j in range(n + 1):
                mark(x0 + (x1 - x0) * j / n, z0 + (z1 - z0) * j / n)
        zs = [q[1] for q in pts]  # scanline fill for horizontal-ish areas
        z = math.floor(min(zs) / WALL_RES) * WALL_RES + WALL_RES / 2
        while z < max(zs):
            xs = []
            for i in range(len(pts)):
                (x0, z0), (x1, z1) = pts[i], pts[(i + 1) % len(pts)]
                if (z0 <= z < z1) or (z1 <= z < z0):
                    xs.append(x0 + (z - z0) * (x1 - x0) / (z1 - z0))
            xs.sort()
            for a, b in zip(xs[0::2], xs[1::2]):
                x = math.floor(a / WALL_RES) * WALL_RES + WALL_RES / 2
                while x < b:
                    mark(x, z)
                    x += WALL_RES
            z += WALL_RES
    # close 1-pixel gaps (dilate, then erode) so pillar rings are sealed before their holes are filled
    if px:
        nb = [(dx, dz) for dx in (-1, 0, 1) for dz in (-1, 0, 1)]
        dil = {(x + dx, z + dz) for x, z in px for dx, dz in nb}
        px |= {(x, z) for x, z in dil if all((x + dx, z + dz) in dil for dx, dz in nb)}
    # fill enclosed holes (e.g. the inside of a hollow pillar ring): flood the outside from a 1-pixel margin
    if px:
        xs0, xs1 = min(q[0] for q in px) - 1, max(q[0] for q in px) + 1
        zs0, zs1 = min(q[1] for q in px) - 1, max(q[1] for q in px) + 1
        outside, todo = {(xs0, zs0)}, [(xs0, zs0)]
        while todo:
            cx, cz = todo.pop()
            for nx, nz in ((cx + 1, cz), (cx - 1, cz), (cx, cz + 1), (cx, cz - 1)):
                if xs0 <= nx <= xs1 and zs0 <= nz <= zs1 and (nx, nz) not in px and (nx, nz) not in outside:
                    outside.add((nx, nz))
                    todo.append((nx, nz))
        # only small compact holes (a pillar's hollow inside); larger or elongated enclosed areas are walkable floor
        # (corridor and branch-room pieces enclose their own floor)
        holes = {(x, z) for x in range(xs0, xs1 + 1) for z in range(zs0, zs1 + 1) if (x, z) not in outside and (x, z) not in px}
        while holes:
            seed = holes.pop()
            comp, todo = {seed}, [seed]
            while todo:
                cx, cz = todo.pop()
                for q in ((cx + 1, cz), (cx - 1, cz), (cx, cz + 1), (cx, cz - 1)):
                    if q in holes:
                        holes.discard(q)
                        comp.add(q)
                        todo.append(q)
            w = (max(q[0] for q in comp) - min(q[0] for q in comp) + 1) * WALL_RES
            h = (max(q[1] for q in comp) - min(q[1] for q in comp) + 1) * WALL_RES
            if len(comp) * WALL_RES * WALL_RES < 16.0 and w <= 4.5 and h <= 4.5:  # compact (pillar), not a corridor
                px |= comp
    # merge: horizontal runs per row, then stack identical runs over consecutive rows
    rows = {}
    for ix, iz in px:
        rows.setdefault(iz, []).append(ix)
    runs = {}
    for iz, xs in rows.items():
        xs.sort()
        start = prev = xs[0]
        for x in xs[1:] + [None]:
            if x is not None and x == prev + 1:
                prev = x
                continue
            runs.setdefault((start, prev), []).append(iz)
            if x is not None:
                start = prev = x
    rects = []
    for (x0, x1), zs in runs.items():
        zs.sort()
        z0 = prevz = zs[0]
        for z in zs[1:] + [None]:
            if z is not None and z == prevz + 1:
                prevz = z
                continue
            rects.append([x0 * WALL_RES, z0 * WALL_RES, (x1 + 1) * WALL_RES, (prevz + 1) * WALL_RES])
            if z is not None:
                z0 = prevz = z
    return rects


def simplify(verts, tris, cell):
    """Vertex clustering: snap to a `cell`-unit grid, merge equal vertices, drop collapsed and duplicate triangles."""
    remap, out_v, keyed = [], [], {}
    for x, y, z in verts:
        k = (round(x / cell), round(y / cell), round(z / cell))
        if k not in keyed:
            keyed[k] = len(out_v)
            out_v.append((k[0] * cell, k[1] * cell, k[2] * cell))
        remap.append(keyed[k])
    out_t, seen = [], set()
    for i in range(0, len(tris), 3):
        a, b, c = remap[tris[i]], remap[tris[i + 1]], remap[tris[i + 2]]
        if a == b or b == c or a == c:
            continue
        key = tuple(sorted((a, b, c)))
        if key in seen:
            continue
        seen.add(key)
        out_t += (a, b, c)
    return out_v, out_t


def piece_mesh(scene_name, lod_target=99, skip_own=None):
    """Merged triangles of one scene (recursively), in that scene's local space.

    Per mesh family the LOD used is min(lod_target, coarsest available); the default takes the coarsest."""
    verts, tris = [], []
    fixtures = []
    stack = set()

    def fixture(mat, target):
        if not any(k in target for k in FIXTURE_REFS) or any(k in target for k in NOT_FIXTURES):
            return
        box = mesh_aabb(target)
        if not box:
            return
        lo, hi = [math.inf] * 3, [-math.inf] * 3
        for cx in (box[0][0], box[1][0]):
            for cy in (box[0][1], box[1][1]):
                for cz in (box[0][2], box[1][2]):
                    q = [mat[i][0] * cx + mat[i][1] * cy + mat[i][2] * cz + mat[i][3] for i in range(3)]
                    for i in range(3):
                        lo[i], hi[i] = min(lo[i], q[i]), max(hi[i], q[i])
        # floor-standing, not tiny, not hanging from the ceiling
        if lo[1] < 1.2 and hi[1] - lo[1] > 0.5 and (hi[0] - lo[0]) * (hi[2] - lo[2]) > 0.25:
            fixtures.append([round(v, 2) for v in lo + hi])

    def emit(mat, pos, idx):
        base = len(verts)
        for x, y, z in pos:
            verts.append((mat[0][0] * x + mat[0][1] * y + mat[0][2] * z + mat[0][3],
                          mat[1][0] * x + mat[1][1] * y + mat[1][2] * z + mat[1][3],
                          mat[2][0] * x + mat[2][1] * y + mat[2][2] * z + mat[2][3]))
        tris.extend(base + i for i in idx[: len(idx) // 3 * 3])

    def visit_scene(name, mat):
        if name in stack or len(stack) > 24:
            return
        root = scene(name)
        if root is None:
            return
        stack.add(name)
        geo = root["attrs"].get("GEOMETRY", "")
        geo = member(geo) if geo.upper().endswith(".GEOMETRY.MBIN") and not name.startswith(skip_own or SKIP_OWN_GEOMETRY) else None
        # coarsest LOD per mesh family within this scene file (family = name without its LODn suffix)
        best = {}
        def scan(n):
            if n["type"] == "MESH":
                fam, lod = mesh_lod(n)
                best[fam] = max(best.get(fam, -1), lod)
            for c in n["children"]:
                scan(c)
        scan(root)
        visit(root, mat, best, geo, is_root=True)
        stack.discard(name)

    def mesh_lod(n):
        m = LOD_RE.match(n["name"])
        fam = (m.group(1) if m else n["name"]).upper()
        try:
            lod = int(n["attrs"].get("LODLEVEL", m.group(2) if m else 0))
        except ValueError:
            lod = 0
        return fam, lod

    def visit(n, parent, best, geo, is_root=False):
        mat = parent if is_root else matmul(parent, trs(n["t"]))
        if n["type"] == "MESH" and geo:
            fam, lod = mesh_lod(n)
            if lod == min(lod_target, best.get(fam, -1)):
                s = geometry(geo).get(n["name"].upper())
                if s:
                    emit(mat, *s)
        elif n["type"] == "REFERENCE" and n["attrs"].get("SCENEGRAPH", "").upper().endswith(".SCENE.MBIN"):
            target = member(n["attrs"]["SCENEGRAPH"])
            if any(k in target for k in SKIP_REFS):
                for it in n["inst"] or [None]:
                    fixture(mat if it is None else matmul(mat, trs(it)), target)
                return
            for it in n["inst"] or [None]:
                visit_scene(target, mat if it is None else matmul(mat, trs(it)))
        if n["type"] in ("COLLISION", "LIGHT"):
            return
        for c in n["children"]:
            visit(c, mat, best, geo)

    visit_scene(scene_name, [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
    piece_mesh.last_fixtures = fixtures
    return verts, tris


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--generated", nargs="*", default=[str(p) for p in GENERATED])
    ap.add_argument("--rebuild", action="store_true", help="rebuild piece meshes even if index.json has them")
    ap.add_argument("--cluster", type=float, default=0.5, help="vertex clustering cell in layout units (0 = off)")
    a = ap.parse_args()
    (CACHE / "pieces").mkdir(parents=True, exist_ok=True)

    pieces = set()
    for root in map(Path, a.generated):
        for f in root.glob("*/derelict.json"):
            try:
                for i in json.loads(f.read_text(encoding="utf-8")).get("instances", []):
                    pieces.add(i["scene_resource"].upper())
            except (OSError, ValueError):
                pass
    print(len(pieces), "piece scenes in generated derelicts", flush=True)

    index = pak_index()
    todo, seen_scenes, geoms = {member(p) for p in pieces}, set(), set()
    while todo:  # scene-reference closure
        batch = sorted(todo - seen_scenes)
        seen_scenes |= set(batch)
        found = extract(batch, index)
        decompile(found)
        nxt = set()
        for n in found:
            root = scene(n)
            if root:
                walk_refs(root, nxt, geoms)
        todo = nxt - seen_scenes
        print(f"scenes {len(seen_scenes)}, geometry files {len(geoms)}", flush=True)
    data_files = [g.replace(".geometry.mbin.pc", ".geometry.data.mbin.pc") for g in geoms]
    found = extract(sorted(geoms) + sorted(data_files), index)
    decompile([g for g in found if g.endswith(".geometry.mbin.pc")])

    out_path = CACHE / "index.json"
    out = {} if a.rebuild or not out_path.exists() else json.loads(out_path.read_text(encoding="utf-8"))
    empty = 0
    for p in sorted(pieces):
        if p in out and out[p].get("walls_rule") == 9:
            continue
        verts, tris = piece_mesh(member(p))
        if a.cluster > 0:
            verts, tris = simplify(verts, tris, a.cluster)
        digest = hashlib.sha1(p.encode()).hexdigest()
        with open(CACHE / "pieces" / f"{digest}.bin", "wb") as fh:
            fh.write(struct.pack("<II", len(verts), len(tris)))
            fh.write(struct.pack(f"<{len(verts) * 3}f", *[c for v in verts for c in v]))
            fh.write(struct.pack(f"<{len(tris)}I", *tris))
        bbox = [[min(v[k] for v in verts) for k in range(3)], [max(v[k] for v in verts) for k in range(3)]] if verts else None
        fixtures = piece_mesh.last_fixtures
        name = p.rsplit("/", 1)[-1]
        walls = [] if name.startswith("DOOR_") else wall_footprint(member(p))
        out[p] = {"mesh": digest, "tris": len(tris) // 3, "bbox": bbox, "fixtures": fixtures, "walls": walls, "walls_rule": 9}
        empty += not tris
    out["_meta"] = {"pieces": len(pieces), "skipped_reference_paths": list(SKIP_REFS), "skipped_own_geometry": list(SKIP_OWN_GEOMETRY),
                    "walls": f"LOD{WALL_LOD} structure in y {WALL_BAND} rasterised at {WALL_RES} units, merged rects [x0,z0,x1,z1,deck offset]; bands at decks -1/0/+1 (ladders); 1-px gaps closed; all pieces except DOOR_, own geometry of dungeon wrapper scenes skipped, enclosed compact holes (< 16 sq units, <= 4.5 x 4.5) filled", "empty_pieces": sum(1 for k, v in out.items() if k != "_meta" and not v["tris"]),
                    "multi_axis_rotations_seen": ROT_MULTI[0], "lod": "coarsest per mesh family per scene file",
                    "euler": "R = Ry*Rx*Rz (degrees, column vectors; the game's order, research-output/container-orientation-20261021)",
                    "cluster_cell": a.cluster}
    out_path.write_text(json.dumps(out, indent=1), encoding="utf-8")
    total = sum(v["tris"] for k, v in out.items() if k != "_meta")
    print("most common multi-axis rotations (RotX, RotY, RotZ): count", sorted(ROT_SAMPLES.items(), key=lambda kv: -kv[1])[:12], flush=True)
    print(f"wrote {out_path}: {len(out) - 1} pieces, {total} triangles, {out['_meta']['empty_pieces']} empty, "
          f"multi-axis rotations {ROT_MULTI[0]}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
