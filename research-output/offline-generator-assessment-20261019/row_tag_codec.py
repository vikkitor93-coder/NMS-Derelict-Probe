"""Port of the NMS 7.05 room-map tag callback FUN_14039FA50 (one node -> one 8-byte map cell).

RECONSTRUCTION NOTICE (stage2/G1, 2026-10-25): the original row_tag_codec.py is lost; no line of its body
survives in the logs. Only the `RowTagContext` field list/docstring (orig. lines 57-72, a10afc4c L312) and the
call sites in scene_callback_matrix_705 / nms_dungeon_reference_closure_q4_705 are logged. This whole file is
NEW CODE written from a read-only static disassembly of the exact 7.05 NMS.exe
(SHA-256 13D5060D...3499) with pefile + iced-x86:
  FUN_14039FA50  0x14039FA50..0x1403A00A7 (callback), jump tables 0x1403A00A8..0x1403A01EF,
  FUN_14039EC00  0x14039F80B..0x14039F8E6 (functor setup: layer byte tables, CELL*C num/div, orientation).
The interface (names, fields, return attributes) is inferred from the call sites. `tag_kind` strings are
descriptive labels chosen here, not original text.

Callback context (functor + 8, pointers): [0] row, [1] &layer_a, [2] &layer_b, [3] &layer_c,
[4] &{&cell_c_numerator, &cell_c_divisor}, [5] &decoration_layer (descriptor +0x40), [6] &orientation.
The position quantization (divide by 8, signed 0.5, cvttss2si, 5x3x5 guard) lives in
scene_callback_matrix_705.quantize_callback_position; out-of-range nodes never reach this codec.
"""

from __future__ import annotations

from dataclasses import dataclass

CELL_BYTES = 8

# EC00 0x14039F812..0x14039F840: three 8-byte stack tables indexed by the source descriptor's
# DecorationLayer (+0x40). esi == 0 at that point (xor esi,esi at 0x14039F28F).
LAYER_A_TABLE = (0x01, 0x01, 0x01, 0x08, 0x13, 0x23, 0x43, 0x17)
LAYER_B_TABLE = (0x00, 0x00, 0x00, 0x00, 0x01, 0x01, 0x01, 0x03)
LAYER_C_TABLE = (0x07, 0x03, 0x01, 0x08, 0x10, 0x20, 0x40, 0x10)

# GcGeneratedBaseDecorationTemplate.DecorationLayer numeric values, read from the exact 7.05 MBIN
# (generatedbasetemplatestable.mbin, consistent over all 319 rows).
DECORATION_LAYER_NAMES = ("Stairs", "Corridor", "Room", "Door", "Decoration1", "Decoration2", "Decoration3",
                          "DecorationCorridor")

# PATH codes before rotation: axis X/Y/Z plain = 2/3/4; 'M' prefix: 5/6/7, MxN 9/0xB/0xD, MxP 8/0xA/0xC;
# 'B' prefix: 0xE/0xF/0x10, BxN 0x12/0x14/0x16, BxP 0x11/0x13/0x15.
_PATH_CODES = {
    0: {"X": (2, 2, 2), "Y": (3, 3, 3), "Z": (4, 4, 4)},          # (other, 'N', 'P') with no M/B prefix
    1: {"X": (5, 9, 8), "Y": (6, 0xB, 0xA), "Z": (7, 0xD, 0xC)},  # 'M'
    2: {"X": (0xE, 0x12, 0x11), "Y": (0xF, 0x14, 0x13), "Z": (0x10, 0x16, 0x15)},  # 'B'
}

# Rotation of PATH codes for orientation 1/2/3 (jump tables at 0x1403A019C, 0x1403A0160, 0x1403A010C).
# Codes not listed (0, 1, the Y codes, and >0x16) are kept.
_PATH_ROTATE = {
    1: {2: 4, 4: 2, 5: 7, 7: 5, 8: 0xC, 9: 0xD, 12: 9, 13: 8, 14: 0x10, 16: 0xE, 17: 0x15, 18: 0x16,
        21: 0x12, 22: 0x11},
    2: {8: 9, 9: 8, 12: 0xD, 13: 0xC, 17: 0x12, 18: 0x11, 21: 0x16, 22: 0x15},
    3: {2: 4, 4: 2, 5: 7, 7: 5, 8: 0xD, 9: 0xC, 12: 8, 13: 9, 14: 0x10, 16: 0xE, 17: 0x16, 18: 0x15,
        21: 0x11, 22: 0x12},
}


@dataclass(frozen=True)
class RowTagContext:
    """The six values reachable through FUN_14039FA50 param1[1..6].

    `cell_c_numerator` and `cell_c_divisor` are signed 32-bit values. The
    returned result carries the next divisor because CELL*C doubles it in the
    original callback. `layer_a/b/c` are the already-selected table bytes.
    """

    layer_a: int
    layer_b: int
    layer_c: int
    cell_c_numerator: int
    cell_c_divisor: int
    decoration_layer: int
    orientation: int


@dataclass(frozen=True)
class EncodedTag:
    tag_kind: str
    cell_bytes: bytes
    next_cell_c_divisor: int
    grows_dimensions: bool


def lookup_layer_bytes(decoration_layer: int) -> tuple[int, int, int]:
    if not 0 <= decoration_layer < 8:
        raise ValueError("DecorationLayer must be in the native range 0..7")
    return LAYER_A_TABLE[decoration_layer], LAYER_B_TABLE[decoration_layer], LAYER_C_TABLE[decoration_layer]


def _i32(value: int) -> int:
    value &= 0xFFFFFFFF
    return value - 0x100000000 if value & 0x80000000 else value


def _c_div(a: int, b: int) -> int:
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q


def _char(name: bytes, index: int) -> int:
    return name[index] if index < len(name) else 0


def _layer_or(cell: bytearray, ctx: RowTagContext) -> None:
    cell[2] |= (ctx.layer_a | ctx.layer_b) & 0xFF
    cell[3] |= ctx.layer_b & 0xFF
    cell[4] |= ctx.layer_c & 0xFF


def encode_node_tag(name: str, before: bytes, *, context: RowTagContext) -> EncodedTag:
    """Apply FA50's write for one in-range callback node to the 8 cell bytes `before`."""
    if len(before) != CELL_BYTES:
        raise ValueError("a map cell is 8 bytes")
    ctx = context
    cell = bytearray(before)
    raw = name.encode("ascii", "replace")
    divisor = _i32(ctx.cell_c_divisor)

    if raw.startswith(b"CELL"):
        c4 = _char(raw, 4)
        if c4 in (0x30, 0x31, 0x32):  # CELL0 / CELL1 / CELL2
            c5 = _char(raw, 5)
            if c5 == 0x4E:  # 'N'
                cell[0] |= 0x40 if c4 == 0x32 else 0x10
                _layer_or(cell, ctx)
                kind = "CELLdN"
            elif c5 == 0x55:  # 'U'
                cell[2] |= 3
                cell[0] |= 0x7C
                cell[3] |= 1
                kind = "CELLdU"
            elif c5 == 0x58:  # 'X'
                cell[0] |= 0x20 if c4 == 0x30 else 0x08
                _layer_or(cell, ctx)
                kind = "CELLdX"
            else:
                cell[0] |= 0x1C
                _layer_or(cell, ctx)
                kind = "CELLd"
        elif c4 == 0x43:  # CELLC: selector bit (numerator / divisor) % 2, divisor doubles
            if divisor == 0:
                raise ZeroDivisionError("CELL*C divisor is zero (native idiv would fault)")
            q = _c_div(_i32(ctx.cell_c_numerator), divisor)
            bit = abs(q) % 2 * (1 if q >= 0 else -1)
            divisor = _i32(divisor * 2)
            if bit == 0:
                cell[0] |= 0x1C
                cell[2] |= 2
                cell[3] |= 2
            elif bit == 1:
                cell[0] |= 0x60
            kind = f"CELLC{bit}"
        elif c4 == 0x52:  # CELLR
            if ctx.decoration_layer in (1, 7):
                cell[0] |= 0x7C
            else:
                cell[0] |= 0x1C
                cell[2] |= 2
            kind = "CELLR"
        else:  # plain CELL, CELL_..., anything else after CELL
            cell[0] |= 0x1C
            _layer_or(cell, ctx)
            kind = "CELL"
        return EncodedTag(kind, bytes(cell), divisor, True)

    if raw.startswith(b"NOCELL"):
        c6 = _char(raw, 6)
        if c6 == 0x45:  # 'E'
            cell[0] |= 2
        elif c6 == 0x49:  # 'I'
            cell[0] |= 1
        else:
            cell[0] |= 3
        return EncodedTag("NOCELL", bytes(cell), divisor, True)

    if raw.startswith(b"PATH"):
        pos = 4
        prefix = 0
        if _char(raw, 4) == 0x42:  # 'B'
            prefix, pos = 2, 5
        elif _char(raw, 4) == 0x4D:  # 'M'
            prefix, pos = 1, 5
        axis = chr(_char(raw, pos))
        code = 0
        if axis in "XYZ" and axis != "\0":
            if prefix == 0:
                code = _PATH_CODES[0][axis][0]
            else:
                sign = _char(raw, pos + 1)
                variants = _PATH_CODES[prefix][axis]
                code = variants[1] if sign == 0x4E else variants[2] if sign == 0x50 else variants[0]
        orientation = ctx.orientation & 3
        if orientation:
            code = _PATH_ROTATE[orientation].get(code, code)
        cell[1] = code  # plain store, not OR
        return EncodedTag("PATH", bytes(cell), divisor, True)

    if raw.startswith(b"LAYER"):
        bit = {0x31: 0x10, 0x32: 0x20, 0x33: 0x40}.get(_char(raw, 5))
        if bit is not None:
            cell[4] |= bit
        # LAYER returns before the dimension update at 0x14039FFC6
        return EncodedTag("LAYER", bytes(cell), divisor, False)

    return EncodedTag("none", bytes(cell), divisor, False)


__all__ = ["RowTagContext", "EncodedTag", "encode_node_tag", "lookup_layer_bytes", "LAYER_A_TABLE",
           "LAYER_B_TABLE", "LAYER_C_TABLE", "DECORATION_LAYER_NAMES"]
