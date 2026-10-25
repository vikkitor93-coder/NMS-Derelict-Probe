"""Topology primitives for the NMS 7.05 offline dungeon port (RNG, grid, room keys).

RECOVERY STATUS (stage 2 / G2, 2026-10-25) -- read before trusting this file
----------------------------------------------------------------------------
The original module (about 450+ lines: A1A00/A1DA0 topology helpers, path
ranges, grid owner writes) is LOST. This is a minimal REBUILD of the names
the surviving modules import (a2780_search, variable_placement, source_catalog,
the q4 diagnostics). Provenance per region:

* ``NativeSeedRng`` class header, docstrings and the first body lines of
  ``from_tk_seed`` (original lines 89-114) and ``ProceduralGrid`` (original
  lines 424-443): VERBATIM from ``grep -A`` output in subagent log a10afc4c L362.
* ``NativeSeedRng.from_tk_seed`` final state packing, ``next_u32``,
  ``bounded_index``, ``unit_float32``: RECONSTRUCTED from the FUN_1403A2780 and
  FUN_1403A23B0 decompiles printed in logs a10afc4c L89 and a717a84b L347:
  ``u = low * 0x5A76F899 + high; low' = u mod 2**32; high' = u >> 32``;
  bounded draw ``(n * low') >> 32``; float draw ``(float)((double)low' * d)``
  with ``d`` = global 0x144B282D8 = bytes 000010000000F03D
  (2.3283064370807974e-10, value read from the exe in log 3bcdb12b L538).
* ``GridDimensions``, ``native_room_key``, ``GeneratedBaseRoomPathRange``:
  RECONSTRUCTED from their call sites (x-fastest index used by
  nms_dungeon_fit_705 and the verbatim A5480 port; 16-byte NUL-padded
  cTkFixedString keys compared against room records +0x28..+0x38 and the
  generated-base MBIN id fields).
* ``ProceduralGrid.set_owner`` (original line 444+) is NOT rebuilt: its byte
  layout is not in the logs and nothing in the surviving tree calls it.

Nothing here was compared against a native run. The layout path used by
generate_derelict_705/fast_generate_705 (native writer + derive()) does not
call any RNG or grid code in this file; it only needs it importable.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

NMS_EXE_SHA256 = "13D5060D4EFB9D2A6A6B1B349BC4257231056CC2A055DF4BB15D816262CC3499"

PROCEDURAL_GRID_CELL_BYTES = 5
NATIVE_LCG_MULTIPLIER = 0x5A76F899
ROOM_KEY_BYTES = 16
# _DAT_144B282D8 (double), the A2780/A3270 "unit float" scale. Exact bit pattern.
UNIT_FLOAT_SCALE = struct.unpack("<d", bytes.fromhex("000010000000f03d"))[0]

_MASK32 = 0xFFFFFFFF
_MASK64 = 0xFFFFFFFFFFFFFFFF


def _u64(value: int) -> int:
    return int(value) & _MASK64


def _f32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


@dataclass(frozen=True)
class GridDimensions:
    """x/y/z extents of the writer's five-byte procedural grid (x fastest)."""  # RECONSTRUCTED

    x: int
    y: int
    z: int

    def __post_init__(self) -> None:
        if any(not 0 <= int(v) <= 0xFFFF for v in (self.x, self.y, self.z)):
            raise ValueError("grid dimensions are native uint16 values")

    @property
    def cell_count(self) -> int:
        return self.x * self.y * self.z

    def contains(self, x: int, y: int, z: int) -> bool:
        return 0 <= x < self.x and 0 <= y < self.y and 0 <= z < self.z

    def index(self, x: int, y: int, z: int) -> int:
        if not self.contains(x, y, z):
            raise IndexError(f"grid cell {(x, y, z)} outside {(self.x, self.y, self.z)}")
        return (z * self.y + y) * self.x + x


@dataclass
class NativeSeedRng:
    """The 64-bit state used by the 7.05 room writer's local LCG."""

    state: int

    @classmethod
    def from_tk_seed(cls, seed_u64: int, valid: bool) -> "NativeSeedRng":
        """Apply the exact ``FUN_14039E5E0`` seed normalization.

        Invalid seeds normalize to state 1.  For valid seeds the low word is
        incremented only when it is zero; the high word is
        ``ROL16(low) XOR original_high XOR low``.

        On the worker path, ``FUN_1411001D0`` writes its address-derived
        mixed qword and valid byte 1 to the ``cTkSeed`` object, then
        ``FUN_1411015D7`` forwards that pointer unchanged to the writer. This
        method represents the writer's local RNG-state initialization; it is
        distinct from the worker's earlier 64-bit address mixer.
        """
        seed_u64 = _u64(seed_u64)
        if not valid:
            return cls(1)
        low = seed_u64 & 0xFFFFFFFF
        high = seed_u64 >> 32
        normalized_low = low if low else 1
        normalized_high = (((low >> 16) | (low << 16)) & 0xFFFFFFFF) ^ high ^ low
        # --- RECONSTRUCTED below this line (state packing: dword[0] = low, dword[1] = high) ---
        return cls(((normalized_high & _MASK32) << 32) | (normalized_low & _MASK32))

    # --- RECONSTRUCTED: draw primitives (decompile of A2780/A23B0, see module header) ---
    @property
    def low(self) -> int:
        return self.state & _MASK32

    @property
    def high(self) -> int:
        return (self.state >> 32) & _MASK32

    def next_u32(self) -> int:
        """Advance once: ``u = low*0x5A76F899 + high``; return the new low dword."""
        value = self.low * NATIVE_LCG_MULTIPLIER + self.high
        self.state = value & _MASK64
        return value & _MASK32

    def bounded_index(self, count: int) -> int:
        """One draw in ``[0, count)``: ``(count * low') >> 32`` (signed count, as native)."""
        count = int(count)
        if count <= 0:
            raise ValueError("bounded_index needs a positive count")
        return (count * self.next_u32()) >> 32

    def unit_float32(self) -> float:
        """One draw as A2780's ``(float)((double)low' * _DAT_144B282D8)``."""
        return _f32(float(self.next_u32()) * UNIT_FLOAT_SCALE)


@dataclass
class ProceduralGrid:
    """Five-byte-per-cell scratch grid used by the topology helpers."""

    dimensions: GridDimensions
    cells: bytearray = field(default_factory=bytearray)

    def __post_init__(self) -> None:
        expected = self.dimensions.cell_count * PROCEDURAL_GRID_CELL_BYTES
        if not self.cells:
            self.cells = bytearray(expected)
        elif len(self.cells) != expected:
            raise ValueError(f"expected {expected} grid bytes, got {len(self.cells)}")

    def cell_offset(self, x: int, y: int, z: int) -> int:
        return self.dimensions.index(x, y, z) * PROCEDURAL_GRID_CELL_BYTES

    def cell(self, x: int, y: int, z: int) -> memoryview:
        offset = self.cell_offset(x, y, z)
        return memoryview(self.cells)[offset:offset + PROCEDURAL_GRID_CELL_BYTES]

    # set_owner(x, y, z, owner) existed in the original (line 444) but its body is lost; not rebuilt.


def native_room_key(room_id: str) -> bytes:
    """RECONSTRUCTED: the 16-byte cTkFixedString<0x10> key (ASCII, NUL padded)."""
    raw = str(room_id).encode("ascii")
    if len(raw) > ROOM_KEY_BYTES:
        raise ValueError(f"room/decoration id {room_id!r} exceeds the native 16-byte key")
    return raw.ljust(ROOM_KEY_BYTES, b"\0")


@dataclass(frozen=True)
class GeneratedBaseRoomPathRange:
    """RECONSTRUCTED: MinPathLength/MaxPathLength of one GcGeneratedBaseRoomTemplate."""

    room_id: str
    minimum: int
    maximum: int


PORT_STATUS = {
    "NativeSeedRng": "LCG step, bounded draw and unit-float draw rebuilt from the A2780/A23B0 decompile; not run against native",
    "ProceduralGrid": "storage and indexing only; owner/connection writers of the lost original are not rebuilt",
    "native_room_key": "16-byte NUL-padded ASCII key (rebuilt from call sites)",
}

__all__ = [
    "GeneratedBaseRoomPathRange",
    "GridDimensions",
    "NativeSeedRng",
    "NATIVE_LCG_MULTIPLIER",
    "PROCEDURAL_GRID_CELL_BYTES",
    "PORT_STATUS",
    "ProceduralGrid",
    "UNIT_FLOAT_SCALE",
    "native_room_key",
]
