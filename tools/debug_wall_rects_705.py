"""Top-down image of the stored wall footprints (meshcache/index.json "walls") for one deck of a derelict (debug aid).

  python -I tools/debug_wall_rects_705.py <ADDRESS16> <level> <out.png> [rooms, e.g. 0,1]

White = wall rectangles placed with each instance's matrix; red = door opening (dark red where a wall still covers it); brown = cells of the selected rooms; grey = other rooms.
Orientation like the viewer: +x to the left, entrance at the bottom. 0.25 layout units per pixel, scaled x3.
"""
import json
import math
import struct
import subprocess
import sys
from pathlib import Path

GEN = Path("D:/Orca/NMS-Derelict-Probe-analysis/emu/fastgen/generated")
INDEX = Path("D:/Orca/NMS-Derelict-Probe-analysis/meshcache/index.json")


def cells(raw):
    x0, y0, z0, x1, y1, z1 = raw[:6]
    X, Y, Z = x1 - x0 + 1, y1 - y0 + 1, z1 - z0 + 1
    m = raw[12] | raw[13] << 16 | raw[14] << 32 | raw[15] << 48
    return {(x0 + x, y0 + y, z0 + z) for x in range(X) for y in range(Y) for z in range(Z) if m >> (z + Z * (y + Y * x)) & 1}


def main():
    address, LV, out = sys.argv[1], int(sys.argv[2]), Path(sys.argv[3])
    sel = {int(v) for v in sys.argv[4].split(",")} if len(sys.argv) > 4 else None
    ix = json.loads(INDEX.read_text(encoding="utf-8"))
    d = json.loads((GEN / address / "derelict.json").read_text(encoding="utf-8"))
    e = d["entrance_origin"]
    base = (LV - e[1]) * 8
    owner = {c: r["room_index"] for r in d["rooms"] for c in cells(r["raw_u16_0x00_0x1F"])}
    rects = []
    for ins in d["instances"]:
        t, A = ins["translation"], ins["source_axes"]
        for x0, z0, x1, z1, *rest in ix.get(ins["scene_resource"].upper(), {}).get("walls", []):
            if abs(t[1] + 8 * (rest[0] if rest else 0) - base) > 4.5:
                continue
            xs = [x * A[0][0] + z * A[2][0] + t[0] for x in (x0, x1) for z in (z0, z1)]
            zs = [x * A[0][2] + z * A[2][2] + t[2] for x in (x0, x1) for z in (z0, z1)]
            rects.append((min(xs), min(zs), max(xs), max(zs)))
    shown = [c for c, r in owner.items() if c[1] == LV and (sel is None or r in sel)]
    xs, zs = [c[0] for c in shown], [c[2] for c in shown]
    X0, X1 = (min(xs) - e[0] - 1.5) * 8, (max(xs) - e[0] + 1.5) * 8
    Z0, Z1 = (min(zs) - e[2] - 1.5) * 8, (max(zs) - e[2] + 1.5) * 8
    R, S = 0.25, 3
    W, H = int((X1 - X0) / R), int((Z1 - Z0) / R)
    grid = {(gx, gz) for a, b, c, dd in rects for gx in range(math.floor(a / R), math.ceil(c / R)) for gz in range(math.floor(b / R), math.ceil(dd / R))}
    # doors (red: 0.5 x 0.7 cell opening box) and their piece scene names, in layout units
    doorpx, doors = set(), []
    for ins in d["instances"]:
        sc = ins["scene_resource"].upper()
        if "/DOOR_" not in sc:
            continue
        A, t = ins["source_axes"], ins["translation"]
        p = [t[k] + 4 * A[2][k] for k in range(3)]
        if round(p[1] / 8) + e[1] != LV:
            continue
        nx, nz = round(A[2][0]), round(A[2][2])
        hx, hz = (2.8, 2.0) if nx else (2.0, 2.8)
        doors.append((sc.split("/")[-1].replace(".SCENE.MBIN", ""), ins["room_index"], round(p[0], 1), round(p[2], 1), nx, nz))
        doorpx |= {(gx, gz) for gx in range(math.floor((p[0] - hx) / R), math.ceil((p[0] + hx) / R)) for gz in range(math.floor((p[2] - hz) / R), math.ceil((p[2] + hz) / R))}
    # stairwell cells (a room's cells shared with the deck above or below) are cut open, as in the viewer
    room_cells = {}
    for c, r in owner.items():
        room_cells.setdefault(r, set()).add(c)
    link_cells = {(c[0], c[2]) for r, cs in room_cells.items() for c in cs if c[1] == LV and ((c[0], LV + 1, c[2]) in cs or (c[0], LV - 1, c[2]) in cs)}

    def cellx_in_link(lx, lz):
        u, v = lx / 8 + e[0] + 0.5, lz / 8 + e[2] + 0.5
        cx, cz = math.floor(u), math.floor(v)
        return (cx, cz) in link_cells and 0.06 < u - cx < 0.94 and 0.06 < v - cz < 0.94
    rows = []
    for py in range(H * S):
        gz = math.floor((Z1 - (py / S) * R) / R)
        row = bytearray()
        for pxl in range(W * S):
            gx = math.floor((X1 - (pxl / S) * R) / R)
            own = owner.get((math.floor(gx * R / 8 + e[0] + 0.5), LV, math.floor(gz * R / 8 + e[2] + 0.5)))
            col = (70, 55, 40) if own is not None and (sel is None or own in sel) else ((45, 45, 55) if own is not None else (14, 17, 22))
            if (gx, gz) in grid:
                col = (235, 235, 235)
            if (gx, gz) in doorpx:
                col = (220, 60, 60) if (gx, gz) in grid else (240, 140, 140)
            row += bytes((col[2], col[1], col[0]))
        while len(row) % 4:
            row += b"\0"
        rows.append(bytes(row))
    data = b"".join(reversed(rows))
    bmp = out.with_suffix(".bmp")
    with open(bmp, "wb") as fh:
        fh.write(b"BM" + struct.pack("<IHHI", 54 + len(data), 0, 0, 54))
        fh.write(struct.pack("<IiiHHIIiiII", 40, W * S, H * S, 1, 24, 0, len(data), 2835, 2835, 0, 0))
        fh.write(data)
    if out.suffix.lower() == ".png":  # Windows imaging converts; keeps this script dependency-free
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        f"Add-Type -AssemblyName System.Drawing; $i=[System.Drawing.Image]::FromFile('{bmp}'); "
                        f"$i.Save('{out}',[System.Drawing.Imaging.ImageFormat]::Png); $i.Dispose()"], check=True)
        bmp.unlink()
    print("wrote", out, len(rects), "rects")
    for row in doors:
        print("  door", row)


if __name__ == "__main__":
    main()
