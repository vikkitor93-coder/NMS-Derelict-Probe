"""Bounded port of NMS 7.05 FUN_1403A23B0 (variable placement search) and FUN_1403A5480.

RECOVERY STATUS (stage 2 / G2, 2026-10-25) -- read before trusting this file
----------------------------------------------------------------------------
Original: 334 lines (end confirmed by ``grep -n ... -A120`` reaching line 334
in log a10afc4c L354). Provenance per region of THIS file:

* imports: VERBATIM content of original lines 31-42 (log a717a84b L175 grep).
* this docstring, constants, ``_u16``/``_read_u16``: RECONSTRUCTED.
* ``VariableSearchBounds`` and the field list of
  ``VariablePlacementAppendRecord`` (original lines 77-123): VERBATIM (log
  a717a84b L347, ``grep -A45``).
* rest of ``VariablePlacementAppendRecord`` (validation, ``known_segments``),
  ``VariablePlacementResult``, ``_random_unique_limit``,
  ``_linear_index_from_offsets``, ``_xyz_from_linear_index`` and the header of
  ``or_piece_map_connections_5480`` (original lines 124-199): RECONSTRUCTED
  from the A23B0 decompile (logs a717a84b L147/L347) and the verbatim callers.
  The 0x14 descriptor A23B0 builds: +0 u32 0x7FFFF, +4 i32 map index,
  +8/+10/+12 u16 origin, +14 mode, +15 source row +0x20, +17 source row
  +0x38; +16/+18/+19 are uninitialised stack bytes.
  ``_random_unique_limit`` uses float32 ``(float)volume * 0.9f`` rounded half
  away from zero (``_DAT_144B29780`` = 0.9f and ``_DAT_144B29308`` = 0.5f are
  ASSUMED from the original docstring "float32 90-percent"; the values were not
  read from the exe in this recovery).
* from the A5480 grid loop (original line 200) to the end: VERBATIM (logs
  a717a84b L293/L154, a10afc4c L354).

Nothing here was compared against a native run. The production layout path
(native writer + generate_derelict_705.derive) only constructs
``VariablePlacementAppendRecord(row, (x, y, z), 0, 0, 0)``.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import struct
from typing import Callable, Sequence

try:  # direct module use with this directory on sys.path
    from nms_dungeon_fit_705 import fits_room_piece_705
    from nms_dungeon_topology_705 import NativeSeedRng, ProceduralGrid
except ImportError:  # pragma: no cover - package-style use
    from .nms_dungeon_fit_705 import fits_room_piece_705
    from .nms_dungeon_topology_705 import NativeSeedRng, ProceduralGrid


# --- RECONSTRUCTED constants/helpers ---------------------------------------
NMS_EXE_SHA256 = "13D5060D4EFB9D2A6A6B1B349BC4257231056CC2A055DF4BB15D816262CC3499"
SOURCE_ROW_SIZE = 0x40
PIECE_MAP_ROW_SIZE = 0x2B0
PIECE_MAP_DATA_SIZE = 600
PIECE_MAP_DIMS_OFFSET = 0x258
APPEND_RECORD_SIZE = 0x14
APPEND_RECORD_TAG = 0x7FFFF
MAX_TRACKED_POSITIONS = 12 * 64  # A23B0's 12-qword tried-position bitmap
RANDOM_UNIQUE_FRACTION_F32 = struct.unpack("<f", struct.pack("<f", 0.9))[0]  # ASSUMED _DAT_144B29780
ROUNDING_HALF_F32 = 0.5  # ASSUMED _DAT_144B29308


def _u16(value: int) -> int:
    return value & 0xFFFF


def _read_u16(data: bytes | bytearray | memoryview, offset: int) -> int:
    return int.from_bytes(bytes(data[offset:offset + 2]), "little")


def _f32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


# --- VERBATIM (original lines 77-123) ---------------------------------------
@dataclass(frozen=True)
class VariableSearchBounds:
    """The candidate origin box decoded from A23B0's 0x40 source row.

    A23B0 reads start XYZ from offsets 0, 2, and 4.  It reads the three
    unsigned words at offsets 6, 8, and 10, adds (5, 3, 5), then computes
    inclusive spans from the start.  All intermediate stored spans are
    uint16 values, matching the native word operations.
    """

    start_xyz: tuple[int, int, int]
    upper_xyz: tuple[int, int, int]
    spans_xyz: tuple[int, int, int]
    volume_u16: int

    @classmethod
    def from_source_row(cls, source_row: bytes | bytearray | memoryview) -> "VariableSearchBounds":
        if len(source_row) != SOURCE_ROW_SIZE:
            raise ValueError("A23B0 source rows must be exactly 0x40 bytes")
        start = tuple(_read_u16(source_row, offset) for offset in (0, 2, 4))
        padded = tuple(_u16(_read_u16(source_row, offset) + pad) for offset, pad in (
            (6, 5), (8, 3), (10, 5)
        ))
        spans = tuple(_u16(high - low + 1) for low, high in zip(start, padded))
        mathematical_volume = math.prod(spans)
        volume = _u16(mathematical_volume)
        return cls(start, padded, spans, volume)


@dataclass(frozen=True)
class VariablePlacementAppendRecord:
    """Fields A23B0 writes into the 0x14 row passed to FUN_1403A6150.

    ``known_segments`` gives exact ``(row_offset, bytes)`` runs.  Native local
    stack bytes at offsets 16, 18, and 19 are not initialized in A23B0 and are
    therefore deliberately absent.  An append adapter that needs the whole
    raw row must obtain those bytes from matching runtime evidence.
    """

    map_index: int
    origin_xyz: tuple[int, int, int]
    mode: int
    source_byte_20: int
    source_byte_38: int

    def __post_init__(self) -> None:
        if not -(1 << 31) <= self.map_index < (1 << 31):
            # --- RECONSTRUCTED from here to the A5480 grid loop ---
            raise ValueError("map_index must fit a signed int32")
        if len(self.origin_xyz) != 3 or any(not 0 <= int(v) <= 0xFFFF for v in self.origin_xyz):
            raise ValueError("origin_xyz must be three uint16 values")
        for name in ("mode", "source_byte_20", "source_byte_38"):
            if not 0 <= getattr(self, name) <= 0xFF:
                raise ValueError(f"{name} is a native byte")

    @property
    def known_segments(self) -> tuple[tuple[int, bytes], ...]:
        head = struct.pack(
            "<IiHHHBB",
            APPEND_RECORD_TAG,
            self.map_index,
            *(int(v) for v in self.origin_xyz),
            self.mode,
            self.source_byte_20,
        )
        return ((0, head), (17, bytes((self.source_byte_38,))))

    @property
    def uninitialized_offsets(self) -> tuple[int, int, int]:
        return (16, 18, 19)


@dataclass(frozen=True)
class VariablePlacementResult:
    """Outcome of one A23B0 call (positional order used by the verbatim body)."""

    success: bool
    origin_xyz: tuple[int, int, int] | None
    linear_index: int | None
    tried_linear_indices: tuple[int, ...]
    random_unique_limit: int
    rng_state_before: int
    rng_state_after: int


def _random_unique_limit(volume_u16: int) -> int:
    """Unique positions drawn randomly before the lowest-untried fallback."""
    scaled = _f32(_f32(float(volume_u16)) * RANDOM_UNIQUE_FRACTION_F32)
    return int(_f32(scaled + math.copysign(ROUNDING_HALF_F32, scaled)))


def _linear_index_from_offsets(dx: int, dy: int, dz: int, spans_xyz: Sequence[int]) -> int:
    """A23B0's u16 bitmap index, X fastest: ``(dz*spanY + dy)*spanX + dx``."""
    return _u16((dz * spans_xyz[1] + dy) * spans_xyz[0] + dx)


def _xyz_from_linear_index(linear_index: int, bounds: VariableSearchBounds) -> tuple[int, int, int]:
    """Inverse used by the deterministic fallback (native div/mod per axis)."""
    sx, sy, sz = bounds.spans_xyz
    x = linear_index % sx
    y = (linear_index // sx) % sy
    z = (linear_index // (sx * sy)) % sz
    return tuple(_u16(start + delta) for start, delta in zip(bounds.start_xyz, (x, y, z)))


def or_piece_map_connections_5480(
    grid: ProceduralGrid,
    piece_map_row: bytes | bytearray | memoryview,
    origin_xyz: Sequence[int],
) -> None:
    """OR each piece cell's byte +4 into grid byte +4 (A5480's map write).

    The piece lattice is centred on the origin with the native (-4, -2, -4)
    offset; cells outside the grid are skipped.
    """
    if len(piece_map_row) < PIECE_MAP_DIMS_OFFSET + 6:
        raise ValueError("piece map row is shorter than its dimension words")
    origin_x, origin_y, origin_z = (int(v) for v in origin_xyz)
    size_x, size_y, size_z = grid.dimensions.x, grid.dimensions.y, grid.dimensions.z
    piece_dims = struct.unpack_from("<HHH", piece_map_row, PIECE_MAP_DIMS_OFFSET)
    # --- VERBATIM from here to the end of the file (original lines 200-334) ---
    for x in range(piece_dims[0]):
        grid_x = origin_x - 4 + x
        for y in range(piece_dims[1]):
            grid_y = origin_y - 2 + y
            for z in range(piece_dims[2]):
                grid_z = origin_z - 4 + z
                if not (0 <= grid_x < size_x and 0 <= grid_y < size_y and 0 <= grid_z < size_z):
                    continue
                piece_cell = (z * 3 + y) * 5 + x
                grid_index = ((grid_z * size_y + grid_y) * size_x + grid_x) & 0xFFFF
                grid_offset = grid_index * 5 + 4
                grid.cells[grid_offset] |= piece_map_row[piece_cell * 8 + 4]


def search_variable_placement_23b0(
    *,
    rng: NativeSeedRng,
    source_row: bytes | bytearray | memoryview,
    piece_map_row: bytes | bytearray | memoryview,
    map_index: int,
    mode: int,
    grid: ProceduralGrid,
    fit_min_xyz: Sequence[int],
    fit_max_xyz: Sequence[int],
    append_a6150: Callable[[VariablePlacementAppendRecord], None],
) -> VariablePlacementResult:
    """Search candidate origins and commit the first A3270-fit placement.

    ``fit_min_xyz`` and ``fit_max_xyz`` are the three-u16 rows passed through
    A23B0 to A3270. A3270 constrains their X and Z components; its existing
    bounded port receives the corresponding X/Z pairs. The source row is the
    exact 0x40-byte A2780 candidate row, while ``piece_map_row`` is the
    already-resolved 0x2b0-byte manager piece row.

    Each random candidate consumes three native LCG advances in X/Y/Z order.
    Duplicate coordinates consume RNG but are neither marked nor fitted.
    Unique positions are marked before fit. After the float32 90-percent
    unique-position threshold, A23B0 takes the lowest untried linear index
    (X fastest) without consuming more RNG. On a fit, the append callback is
    invoked first, then A5480's byte +4 map write is applied to ``grid``.
    """

    if len(source_row) != SOURCE_ROW_SIZE:
        raise ValueError("A23B0 source rows must be exactly 0x40 bytes")
    if len(piece_map_row) != PIECE_MAP_ROW_SIZE:
        raise ValueError("native piece-map rows must be exactly 0x2b0 bytes")
    if not -(1 << 31) <= map_index < (1 << 31):
        raise ValueError("map_index must fit a signed int32")
    if not 0 <= mode <= 0xFF:
        raise ValueError("A23B0 mode/expected-neighbor tag is a uint8")
    if len(fit_min_xyz) != 3 or len(fit_max_xyz) != 3:
        raise ValueError("A3270 fit bounds must be three-coordinate XYZ rows")
    fit_min = tuple(int(v) for v in fit_min_xyz)
    fit_max = tuple(int(v) for v in fit_max_xyz)
    if any(not 0 <= v <= 0xFFFF for v in (*fit_min, *fit_max)):
        raise ValueError("A3270 fit bounds are uint16 XYZ values")

    bounds = VariableSearchBounds.from_source_row(source_row)
    before = rng.state & 0xFFFFFFFFFFFFFFFF
    if bounds.volume_u16 == 0:
        return VariablePlacementResult(False, None, None, (), 0, before, rng.state)
    if any(high < low for low, high in zip(bounds.start_xyz, bounds.upper_xyz)):
        raise NotImplementedError("wrapped or inverted A23B0 search bounds are outside the valid-map port")

    mathematical_volume = math.prod(bounds.spans_xyz)
    if mathematical_volume != bounds.volume_u16:
        raise NotImplementedError("A23B0 uint16 volume wrap is outside the bounded valid-map port")
    if mathematical_volume > MAX_TRACKED_POSITIONS:
        raise NotImplementedError(
            "A23B0's 12-qword tried-position bitmap supports at most 768 candidate origins"
        )
    if any(span == 0 for span in bounds.spans_xyz):
        return VariablePlacementResult(False, None, None, (), 0, before, rng.state)

    random_limit = _random_unique_limit(bounds.volume_u16)
    piece_dims = struct.unpack_from("<HHH", piece_map_row, PIECE_MAP_DIMS_OFFSET)
    if any(value > limit for value, limit in zip(piece_dims, (5, 3, 5))):
        raise ValueError("piece dimensions exceed the native 5x3x5 map")
    used = 0
    tried: list[int] = []
    grid_dims = (grid.dimensions.x, grid.dimensions.y, grid.dimensions.z)

    while len(tried) < bounds.volume_u16:
        if len(tried) < random_limit:
            dx = rng.bounded_index(bounds.spans_xyz[0])
            dy = rng.bounded_index(bounds.spans_xyz[1])
            dz = rng.bounded_index(bounds.spans_xyz[2])
            linear_index = _linear_index_from_offsets(dx, dy, dz, bounds.spans_xyz)
            origin = tuple(
                _u16(start + delta)
                for start, delta in zip(bounds.start_xyz, (dx, dy, dz))
            )
        else:
            free = (~used) & ((1 << MAX_TRACKED_POSITIONS) - 1)
            if free == 0:
                return VariablePlacementResult(
                    False, None, None, tuple(tried), random_limit, before, rng.state
                )
            linear_index = (free & -free).bit_length() - 1
            origin = _xyz_from_linear_index(linear_index, bounds)

        bit = 1 << linear_index
        if used & bit:
            continue
        used |= bit
        tried.append(linear_index)

        fits = fits_room_piece_705(
            candidate_map=piece_map_row[:PIECE_MAP_DATA_SIZE],
            candidate_dims=piece_dims,
            current_grid=grid.cells,
            current_grid_dims=grid_dims,
            placement_xyz=origin,
            expected_neighbor_tag=mode,
            range_min_xz=(fit_min[0], fit_min[2]),
            range_max_xz=(fit_max[0], fit_max[2]),
        )
        if fits:
            record = VariablePlacementAppendRecord(
                map_index=map_index,
                origin_xyz=origin,
                mode=mode,
                source_byte_20=source_row[0x20],
                source_byte_38=source_row[0x38],
            )
            append_a6150(record)
            or_piece_map_connections_5480(grid, piece_map_row, origin)
            return VariablePlacementResult(
                True, origin, linear_index, tuple(tried), random_limit, before, rng.state
            )

    return VariablePlacementResult(
        False, None, None, tuple(tried), random_limit, before, rng.state
    )

