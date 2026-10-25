#!/usr/bin/env python3
"""Build the 1,876 x 0x2B0 A2780 source rows (writer global +0x28) from game assets only.

Asset path: Q4 reference-closure provider (scene MXML closure extracted from game PCBANKS) + the
FUN_14039EC00 transform tail (+0x260..+0x29F) re-derived from its decompile.  No live capture is read
except by --compare.  Descriptor pointer (+0x2A0) is written as the descriptor *index* (table array 0,
0x50 stride); emulate_writer_705_assets.py rebases it to the loaded table.

Fixes over the Q4 provider's matrix (EC00 decompile, lines ~790-815 of dungeon_writer_methods.txt):
  orientation 2 offset is x += (dimX-1)*8, z += (dimZ-1)*8 (the old port had dimX/dimZ swapped).
Tail w lane: orientation 0 -> -1 - min over CELL*/NOCELL* nodes of (AABBMIN.xyz + node pos).sum (clamped at 0);
             orientation>0 -> tx0 + tz0 + 2 (unrotated translation + two 1.0 constants).
"""
import argparse, hashlib, json, struct, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OFF = ROOT / "research-output/offline-layout-705-20261019"
sys.path.insert(0, str(OFF))
import nms_dungeon_reference_closure_q4_705 as r  # noqa: E402
scm = r.scm
LIVE = ROOT / "live-runtime/NMSDerelictSurveyor/layout-cdb-r3/98a782a55ef44aec88142de0ce5e8e6a/source-rows.bin"
OUT = Path("D:/Orca/NMS-Derelict-Probe-analysis/emu")
ROW = 0x2B0

_orig = scm.build_scene_callback_matrix


def _fixed(bounds_min, *, orientation, extent_dimensions, **kw):
    if orientation == 2:  # swap so the (buggy) port applies x+=(dx-1)*8, z+=(dz-1)*8
        dx, dy, dz = extent_dimensions
        extent_dimensions = (dz, dy, dx)
    return _orig(bounds_min, orientation=orientation, extent_dimensions=extent_dimensions, **kw)


scm.build_scene_callback_matrix = _fixed


def minsum(nodes):
    s = 0.0
    for nd in nodes:
        if not nd["name"].startswith(scm.BOUNDS_PREFIXES):
            continue
        a = nd["attributes"]
        c = [scm._add32(scm._f32(float(a[f"AABBMIN{ax}"])), nd["position"][i]) for i, ax in enumerate("XYZ")]
        s = min(s, scm._add32(scm._add32(c[0], c[1]), c[2]))
    return s


def build_rows():
    cat = r.Q4SourceCatalog.from_workspace(ROOT)
    rows = bytearray()
    f32 = scm._f32
    for i, v in enumerate(cat.variants):
        assert v.map_index == i
        m = cat.materialize_scene_map(i)
        row = bytearray(ROW)
        row[:0x25E] = m.native_map_prefix
        nodes = cat.resolver.nodes(v.scene_mxml)
        t = m.transform
        if v.orientation == 0:
            w = scm._sub32(-1.0, minsum(nodes)) if hasattr(scm, "_sub32") else f32(-1.0 - minsum(nodes))
        else:
            t0 = _orig(r._bounds_min(nodes), orientation=0, extent_dimensions=(0, 0, 0)).translation
            w = scm._add32(scm._add32(scm._add32(scm._add32(0.0, t0[0]), t0[2]), 1.0), 1.0)
        vals = []
        for ax in t.axes:
            vals += [ax[0], ax[1], ax[2], 1.0]
        vals += [t.translation[0], t.translation[1], t.translation[2], w]
        struct.pack_into("<16f", row, 0x260, *vals)
        struct.pack_into("<Q", row, 0x2A0, v.table_index)
        rows += row
    return bytes(rows)


def compare(rows, live):
    mism, ptr = [], 0
    for i in range(len(rows) // ROW):
        a, b = rows[i * ROW:(i + 1) * ROW], live[i * ROW:(i + 1) * ROW]
        a, b = a[:0x2A0] + a[0x2A8:], b[:0x2A0] + b[0x2A8:]  # mask pointer
        if a != b:
            diff = [k for k in range(len(a)) if a[k] != b[k]]
            mism.append({"row": i, "first_diff": diff[0], "n_diff": len(diff)})
    return mism


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT / "asset_source_rows.bin"))
    ap.add_argument("--compare", action="store_true")
    a = ap.parse_args()
    rows = build_rows()
    Path(a.out).write_bytes(rows)
    res = {"rows": len(rows) // ROW, "sha256": hashlib.sha256(rows).hexdigest()}
    if a.compare:
        live = LIVE.read_bytes()
        mm = compare(rows, live)
        res.update(live_rows=len(live) // ROW, mismatching_rows=len(mm), mismatches=mm[:40],
                   descriptor_index_ok=None)
        # descriptor index check vs live pointers
        ptrs = [struct.unpack_from("<Q", live, i * ROW + 0x2A0)[0] for i in range(len(live) // ROW)]
        lo = min(ptrs)
        res["descriptor_index_ok"] = all((p - lo) % 0x50 == 0 and (p - lo) // 0x50 == struct.unpack_from("<Q", rows, i * ROW + 0x2A0)[0]
                                         for i, p in enumerate(ptrs))
        (OUT / "asset_rows_vs_live.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
