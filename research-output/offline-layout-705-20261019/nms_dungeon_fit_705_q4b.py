"""Q4b corrected port of NMS 7.05 FUN_1403A3270 (RVA 0x3A3270), the room-piece fit predicate.

Replaces ``nms_dungeon_fit_705.fits_room_piece_705`` and keeps its signature. That file is
left unchanged. The audit is against raw iced-x86 disassembly of the hash-matched NMS.exe
(13D5060D...3499):
D:/Orca/Temp/nms-ghidra-q4b-20261020/a3270_disasm_20261020.txt (range 0x1403A3270..0x1403A3AD3,
plus the jump tables at 0x1403A3AD4, 0x1403A3B90 and 0x1403A3B9C).

Corrections (addresses are absolute VAs):
  D1 0x1403A39FF: an out-of-grid cell is rejected when candidate *byte 3* (BPL = qword>>0x18)
     is nonzero, not when the expected neighbor tag is nonzero.
  D2 jump table 0x1403A3AD4[0] = 0x1403A34F1: in-grid opcode 0 accepts any current cell type.
     Only opcode 2 (entry 0x1403A3458) requires type <= 1.
  D3 0x1403A34F7: in the not-same-tag path the required flag starts at 1 (SIL=1, saved at
     [rsp+24h]), not 0. When byte0 bit 0x04 is set and the directional neighbor does not
     match, the result stays 1 and falls through to the range check (0x1403A37A3). It is
     not 0, which would always reject.
  D4 0x1403A3785/0x1403A384C..0x1403A38AC: the 0x08 scan stops at the first direction whose
     neighbor has a matching tag and type == direction, whether or not A4120 or the candidate
     bit 0x10 succeed.
  D5 0x1403A379F: when the 0x08 scan finds nothing usable, the flag is restored from [rsp+24h]
     (1 or 0x40 from the first scan). It is not reset to 0 and then set to 1.
  D6 0x1403A37DD..0x1403A3A50: the in-grid byte-5 connection path is ported (it was
     NotImplementedError before).
"""

from __future__ import annotations

from typing import Sequence

_DIRS = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
# 0x144A588D8 = u16 (5, 3, 5): FUN_1403A4120's bounds (const_144A588D8.txt).
_A4120_BOUNDS = (5, 3, 5)


def _move(xyz, direction, bounds):
    """FUN_1403A4120-style one-step move with u16 lower bound 0 and exclusive upper bound."""
    if direction > 5:
        return None
    dx, dy, dz = _DIRS[direction]
    n = (xyz[0] + dx, xyz[1] + dy, xyz[2] + dz)
    if all(0 <= v < b for v, b in zip(n, bounds)):
        return n
    return None


def _gidx(xyz, dims):
    w, h, _d = dims
    # native: movzx after each 16-bit add/imul (0x1403A33FA..0x1403A341D)
    return ((((xyz[2] * h) & 0xFFFF) + xyz[1]) & 0xFFFF) * w + xyz[0] & 0xFFFF


def _cidx(xyz):
    return xyz[0] + 5 * xyz[1] + 15 * xyz[2]


def _opcode_accepts(opcode: int, byte0: int) -> bool:
    """Jump table 0x1403A3AD4 entries 0..22 (in-grid)."""
    t = byte0 >> 5
    bit1 = bool(byte0 & 2)
    if opcode == 0:
        return True                      # 0x1403A34F1
    if opcode == 1:
        return t == 6                    # 0x1403A34E8
    if opcode == 2:
        return t <= 1                    # 0x1403A3458
    if opcode in (3, 4):
        return 0 <= t - (2 if opcode == 3 else 4) <= 1
    if 5 <= opcode <= 7:
        return (not bit1) and 0 <= t - (opcode - 5) * 2 <= 1
    if 8 <= opcode <= 13:
        return (not bit1) and t == opcode - 8
    if 14 <= opcode <= 16:
        return bit1 and 0 <= t - (opcode - 14) * 2 <= 1
    if 17 <= opcode <= 22:
        return bit1 and t == opcode - 17
    return False


def fits_room_piece_705(
    candidate_map,
    candidate_dims: Sequence[int],
    current_grid,
    current_grid_dims: Sequence[int],
    placement_xyz: Sequence[int],
    expected_neighbor_tag: int,
    range_min_xz: Sequence[int],
    range_max_xz: Sequence[int],
) -> bool:
    """Native arg mapping (A2780 call 0x1403A3073, A23B0 call): RDX=origin u16[3],
    R8=grid (5 B/cell), R9=DungeonParams (W/H/D at +0x60/+0x64/+0x68), arg5=row map,
    arg6=row+0x258 dims u16[3], arg7=tag byte, arg8/arg9=min/max u16[3] (only [0] and [2] read)."""
    if len(candidate_map) < 600:
        raise ValueError("candidate_map must be the 600-byte row map")
    pdx, pdy, pdz = (int(v) for v in candidate_dims)
    dims = tuple(int(v) for v in current_grid_dims)
    W, H, D = dims
    ox, oy, oz = (int(v) for v in placement_xyz)
    tag = int(expected_neighbor_tag) & 0xFF
    lo_x, lo_z = (int(v) for v in range_min_xz)
    hi_x, hi_z = (int(v) for v in range_max_xz)
    if len(current_grid) < W * H * D * 5:
        raise ValueError("current_grid shorter than dims*5")

    # loops: x outer ([r10]), y middle ([r10+2]), z inner ([r10+4]); map index x+5y+15z
    for x in range(pdx):
        for y in range(pdy):
            for z in range(pdz):
                off = _cidx((x, y, z)) * 8
                packed = int.from_bytes(candidate_map[off:off + 8], "little")
                if packed == 0:
                    continue                                   # 0x1403A3340
                b0 = packed & 0xFF
                opcode = (packed >> 8) & 0xFF
                b2 = (packed >> 16) & 0xFF
                b3 = (packed >> 24) & 0xFF
                b5 = (packed >> 40) & 0xFF                     # [rsp+4Dh]
                gx, gy, gz = ox + x, oy + y, oz + z            # 32-bit adds, unsigned compares
                in_grid = 4 <= gx < W + 4 and 2 <= gy < H + 2 and 4 <= gz < D + 4
                if not in_grid:                                # 0x1403A39FF
                    if b3 != 0 or opcode > 0x16:
                        return False
                    # 0x1403A3B9C index: opcodes 0,1 -> 0x3A3A3D; 8..13 -> 0x3A3A33 (needs
                    # opcode==14, impossible -> reject); all others -> 0x3A3461 reject.
                    if opcode not in (0, 1):
                        return False
                    if (b5 & 3) == 1 or (b0 & 2) == 0:
                        return False
                    continue
                c = ((gx - 4) & 0xFFFF, (gy - 2) & 0xFFFF, (gz - 4) & 0xFFFF)
                go = _gidx(c, dims) * 5
                g0 = current_grid[go]
                if (b2 & current_grid[go + 4]) != b3:          # 0x1403A3424
                    return False
                if opcode > 0x16 or not _opcode_accepts(opcode, g0):
                    return False
                if ((current_grid[go + 2] - 1) & 0xFF) == tag:  # 0x1403A3508
                    flag = 8 if g0 & 8 else (0x10 if g0 & 4 else 4)
                else:
                    flag = 1                                   # 0x1403A34F7 (D3)
                    if g0 & 0x0C:
                        if g0 & 4:                             # first scan
                            d = ((g0 ^ 0x20) >> 5) & 0xFF
                            n = _move(c, d, dims)
                            if n is not None:
                                no = _gidx(n, dims) * 5
                                if ((current_grid[no + 2] - 1) & 0xFF) == tag:
                                    m = _move((x, y, z), d, _A4120_BOUNDS)
                                    if m is not None and candidate_map[_cidx(m) * 8] & 8:
                                        flag = 0x40
                        if g0 & 8:                             # second scan (D4/D5)
                            saved = flag
                            for d in range(6):
                                n = _move(c, d, dims)
                                if n is None:
                                    continue
                                no = _gidx(n, dims) * 5
                                if ((current_grid[no + 2] - 1) & 0xFF) == tag and (current_grid[no] >> 5) == d:
                                    m = _move((x, y, z), d, _A4120_BOUNDS)
                                    if m is not None and candidate_map[_cidx(m) * 8] & 0x10:
                                        flag = 0x20
                                    else:
                                        flag = saved
                                    break
                    if flag == 1:                              # 0x1403A37A9
                        if not (c[0] >= lo_x and c[2] >= lo_z and c[0] <= hi_x and c[2] <= hi_z):
                            flag = 2
                if (flag & b0) == 0:                           # 0x1403A37D4
                    return False
                sel = b5 & 3
                if sel == 0:
                    continue
                # D6: byte-5 connection path 0x1403A37ED..0x1403A3A50
                t = ((ox - 3) & 0xFFFF, (oy - 2) & 0xFFFF, (oz - 3) & 0xFFFF)
                hit = False
                n = _move(c, ((g0 ^ 0x20) >> 5) & 0xFF, dims)
                if n is not None and n == t:
                    hit = True
                if not all(v < b for v, b in zip(t, dims)):
                    raise NotImplementedError("byte-5 target cell outside grid (native reads out of range)")
                t0 = current_grid[_gidx(t, dims) * 5]
                n2 = _move(t, ((t0 ^ 0x20) >> 5) & 0xFF, dims)
                if n2 is not None and n2 == c:
                    hit = True
                if sel == (2 if hit else 1):
                    return False
    return True


PORT_STATUS = {
    "FUN_1403A3270": "Q4b full port from raw disassembly incl. byte-5 path; corrections D1-D6 vs nms_dungeon_fit_705",
}

__all__ = ["fits_room_piece_705", "PORT_STATUS"]
