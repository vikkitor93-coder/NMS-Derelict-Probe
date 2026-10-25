#!/usr/bin/env python3
"""NMS 7.05 (NMS.exe SHA-256 13D5060D...3499): system-generated space-POI positions, offline.

Runs the game's own galaxy-info + solar-system generator under Unicorn (Shipwright's SystemGen, MIT,
%USERPROFILE%/tools/NMS-Shipwright) with the space-POI table loaded, and prints the position of the
ABAND_FREIGHTER POI (the natural derelict freighter of the system) as exact float32 values.

Run with the Shipwright venv python (unicorn + pefile):
  %USERPROFILE%/tools/NMS-Shipwright/.venv/Scripts/python.exe -I tools/space_poi_position_705.py 0002250006607CAA [...]
Output: one JSON line per address: {"address", "poi_index", "poi_ids", "aband_freighter": [x, y, z] | null}

Native evidence (research-output/END_REWARD_PREDICTION_20261020.md):
- galaxy-info 0x14132D5E0 -> 0x14132BF90 -> 0x14132C660 builds the POI list from cGcSpacePoiTable at [app+0x128]
  (count at info+0x748, 16-byte IDs at info+0xB0). Without the table the list is empty (Shipwright default).
- the system generator 0x14164A4A0 (sub-step 0x14164F655) writes cGcSolarSystemData.SpacePoiPositions (+0x1CE0,
  16 bytes per POI, same index as the list); the spawner 0x1416D6D70 places each POI at that position.
- MBIN NMSTemplate fields are (rel64, class-hash u32, 0xEEEEEE01); in memory the game expects (ptr, hash).
The generator's tail (timers, after SpacePoiPositions are written) faults on a live-only global; that is
expected and does not affect the positions.
"""
import json
import os
import struct
import sys
from pathlib import Path

SHIPWRIGHT = os.path.expandvars("%USERPROFILE%/tools/NMS-Shipwright")
sys.path.insert(0, SHIPWRIGHT)
from nms_procgen.emu import APP, SENTINEL  # noqa: E402
from nms_procgen.systemgen import SystemGen  # noqa: E402

PCBANKS = Path("G:/SteamLibrary/steamapps/common/No Man's Sky/GAMEDATA/PCBANKS")
TABLE_MEMBER = "metadata/simulation/solarsystem/spacepoi/spacepoitable.mbin"
CACHE = Path("D:/Orca/NMS-Derelict-Probe-analysis/end-reward-cache")


def table_bytes() -> bytes:
    path = CACHE / "spacepoitable.mbin"
    if not path.exists():
        from hgpaktool import HGPAKFile  # system python package; copy the file into CACHE once if missing here
        CACHE.mkdir(parents=True, exist_ok=True)
        with HGPAKFile(PCBANKS / "NMSARC.Precache.pak") as a:
            for name, data in a.extract([TABLE_MEMBER]):
                path.write_bytes(data)
    return path.read_bytes()


def install_fast_stub_hook() -> bool:
    """Speed fix 1 (2026-10-22): fast paths for the two imports the POI step calls ~3,650 times each per system,
    powf and frexp. Same arithmetic, struct packing and register side effects as Shipwright's Emu._on_stub
    (xmm0 written as a 128-bit value with zero upper bits, RAX = 0, NaN in xmm0 on ValueError/OverflowError/
    ZeroDivisionError); registers are read/written through uclib directly instead of the unicorn-py3 wrapper.
    Every other import goes to the original handler. Must run before SystemGen() builds its Emu (the code hook binds
    the method at construction). Disabled with NMS_SPEED_FIXES (see nms_paths_705.fix_enabled). Returns True if active.
    Validated: POI output byte-identical for 150/150 systems (GENERATOR_PROFILE_20261022.md) and the staging tests."""
    import ctypes
    import math
    import nms_procgen.emu as E
    if getattr(E.Emu._on_stub, "_fast_powf_frexp", False):
        return True
    try:
        from nms_paths_705 import fix_enabled
    except ImportError:
        fix_enabled = lambda name: True  # noqa: E731
    if not fix_enabled("poi"):
        return False
    try:
        from unicorn import x86_const as X
        from unicorn.unicorn_py3.unicorn import uclib
    except ImportError:          # another unicorn layout: keep the original handler
        return False
    orig = E.Emu._on_stub
    XMM0, XMM1, RDX, RAX = X.UC_X86_REG_XMM0, X.UC_X86_REG_XMM1, X.UC_X86_REG_RDX, X.UC_X86_REG_RAX
    rd, wr = uclib.uc_reg_read, uclib.uc_reg_write
    x0, x1, g, out = (ctypes.c_uint64 * 2)(), (ctypes.c_uint64 * 2)(), ctypes.c_uint64(), (ctypes.c_uint64 * 2)()
    zero = ctypes.c_uint64(0)
    bx0, bx1, bg, bout, bzero = (ctypes.byref(v) for v in (x0, x1, g, out, zero))
    unpack_f, unpack_d = struct.Struct("<f").unpack, struct.Struct("<d").unpack
    pack_f, pack_d, pack_i = struct.Struct("<f").pack, struct.Struct("<d").pack, struct.Struct("<i").pack
    pack_I, pack_Q = struct.Struct("<I").pack, struct.Struct("<Q").pack
    unpack_I, unpack_Q = struct.Struct("<I").unpack, struct.Struct("<Q").unpack
    mpow, mfrexp = math.pow, math.frexp

    def set_xmm0(h, val, f32):          # == Emu._set_xmm(0, val, f32)
        out[0] = unpack_I(pack_f(val))[0] if f32 else unpack_Q(pack_d(val))[0]
        out[1] = 0
        wr(h, XMM0, bout)

    def fast(self, mu, addr, size, user):
        fn = self.imports.get(addr)
        if fn == "powf":
            h = mu._uch
            try:
                rd(h, XMM0, bx0)
                rd(h, XMM1, bx1)
                set_xmm0(h, mpow(unpack_f(pack_I(x0[0] & 0xFFFFFFFF))[0], unpack_f(pack_I(x1[0] & 0xFFFFFFFF))[0]), True)
            except (ValueError, OverflowError, ZeroDivisionError):
                set_xmm0(h, float("nan"), False)
            wr(h, RAX, bzero)
            return
        if fn == "frexp":
            h = mu._uch
            try:
                rd(h, RDX, bg)
                rd(h, XMM0, bx0)
                m, ex = mfrexp(unpack_d(pack_Q(x0[0]))[0])
                set_xmm0(h, m, False)
                mu.mem_write(g.value, pack_i(ex))
            except (ValueError, OverflowError, ZeroDivisionError):
                set_xmm0(h, float("nan"), False)
            wr(h, RAX, bzero)
            return
        return orig(self, mu, addr, size, user)

    fast._fast_powf_frexp = True
    E.Emu._on_stub = fast
    return True


class PoiGen:
    def __init__(self):
        self.fast_hook = install_fast_stub_hook()
        self.g = g = SystemGen()
        e = g.e
        raw = table_bytes()
        tmp = CACHE / "spacepoitable.mbin"
        self.tbl = e.load_mbin(str(tmp))
        h = self.tbl - 0x20
        for i in range(0x20, len(raw) - 15, 8):  # NMSTemplate fixups
            if struct.unpack_from("<I", raw, i + 12)[0] == 0xEEEEEE01:
                rel = struct.unpack_from("<q", raw, i)[0]
                e.wq(h + i, (h + i + rel) if rel else 0)
        g.mark = e.heap  # keep the table out of SystemGen's per-system heap reset

    def positions(self, ua: int) -> dict:
        g = self.g
        e, o = g.e, g.owner
        info = o + g.a["info_off"]
        g._reset()
        e.wq(APP + 0x128, self.tbl)
        r = e.call(g.a["info"], info, ua)
        if not r["ok"]:
            raise RuntimeError(f"galaxy info failed: {r}")
        n = e.ri(info + 0x748)
        ids = [bytes(e.mu.mem_read(info + 0xB0 + 16 * i, 16)).split(bytes(1))[0].decode("latin1") for i in range(min(n, 32))]
        e.wq(g.seed, ua)
        e.mu.mem_write(g.seed + 8, b"\x01")
        e.wq(g.ctx, o)
        e.wq(g.ctx + 8, o)
        e.wq(g.ctx + 0x10, o + 0x25E0)
        e.call(g.a["gen"], g.gen, g.seed, info, g.ctx, until=SENTINEL, count=400_000_000)
        raw = bytes(e.mu.mem_read(o + 0x1CE0, 32 * 16))
        pos = [list(struct.unpack_from("<3f", raw, 16 * i)) for i in range(len(ids))]
        k = ids.index("ABAND_FREIGHTER") if "ABAND_FREIGHTER" in ids else None
        return {"poi_index": k, "poi_ids": ids, "aband_freighter": pos[k] if k is not None else None}


def main():
    pg = PoiGen()
    for a in sys.argv[1:]:
        res = pg.positions(int(a, 16))
        print(json.dumps({"address": a.upper(), **res}))


if __name__ == "__main__":
    main()
