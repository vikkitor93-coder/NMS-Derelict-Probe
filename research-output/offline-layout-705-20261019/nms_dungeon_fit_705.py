"""Bounded offline ports of NMS 7.05 room-fit predicates.

``FUN_1403A3270`` answers whether one 5x3x5 room-piece map fits at a proposed
origin in an existing layout grid. ``FUN_1403A1DA0`` checks whether each
logical room's manager-map dimensions can occupy a fully owned rectangular
volume inside that room's A1A00 bounds. Neither helper produces the manager
maps or chooses a room.

The A1DA0 port uses the hash-matched NMS 7.05 executable
13D5060D4EFB9D2A6A6B1B349BC4257231056CC2A055DF4BB15D816262CC3499 and the
matching decompile/instruction evidence recorded in
``a1da0_evidence_assembly_20261019.txt``.

All coordinates and byte fields are explicit. The native ``[rsp+0x4d]`` read
aliases byte 5 of the current encoded candidate cell, not an independent
stack input. The current zero-init plus scene-callback producer leaves it zero.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


_CANDIDATE_DIMS = (5, 3, 5)
_DIRECTIONS = (
    (1, 0, 0),
    (-1, 0, 0),
    (0, 1, 0),
    (0, -1, 0),
    (0, 0, 1),
    (0, 0, -1),
)


def _u8(data: bytes | bytearray | memoryview, offset: int) -> int:
    return data[offset]


def _candidate_cell_index(x: int, y: int, z: int) -> int:
    # FUN_1403A3270 uses the fixed row stride x + 5*y + 15*z.
    return x + 5 * y + 15 * z


def _grid_cell_index(x: int, y: int, z: int, dims: tuple[int, int, int]) -> int:
    width, height, _depth = dims
    return (z * height + y) * width + x


def _candidate_neighbor_flag(
    candidate_map: bytes | bytearray | memoryview,
    local_xyz: tuple[int, int, int],
    direction: int,
    mask: int,
) -> bool:
    """Apply FUN_1403A4120's fixed 5x3x5 move, then test the neighbor byte."""

    dx, dy, dz = _DIRECTIONS[direction]
    x, y, z = local_xyz
    nx, ny, nz = x + dx, y + dy, z + dz
    if not (0 <= nx < 5 and 0 <= ny < 3 and 0 <= nz < 5):
        return False
    cell_offset = _candidate_cell_index(nx, ny, nz) * 8
    return bool(_u8(candidate_map, cell_offset) & mask)


def _current_neighbor(
    grid: bytes | bytearray | memoryview,
    xyz: tuple[int, int, int],
    direction: int,
    dims: tuple[int, int, int],
) -> tuple[int, int, int, int] | None:
    """Return (x, y, z, cell offset) for an in-bounds one-cell move."""

    dx, dy, dz = _DIRECTIONS[direction]
    x, y, z = xyz
    nx, ny, nz = x + dx, y + dy, z + dz
    width, height, depth = dims
    if not (0 <= nx < width and 0 <= ny < height and 0 <= nz < depth):
        return None
    offset = _grid_cell_index(nx, ny, nz, dims) * 5
    return nx, ny, nz, offset


def _opcode_accepts(opcode: int, current_byte0: int) -> bool:
    """The exact 0..22 opcode/current-cell-type dispatch at 0x1403A343A."""

    current_type = current_byte0 >> 5
    has_bit_1 = bool(current_byte0 & 0x02)

    if opcode == 0 or opcode == 2:
        return current_type <= 1
    if opcode == 1:
        return current_type == 6
    if 3 <= opcode <= 4:
        base = 2 if opcode == 3 else 4
        return base <= current_type <= base + 1
    if 5 <= opcode <= 7:
        if has_bit_1:
            return False
        base = {5: 0, 6: 2, 7: 4}[opcode]
        return base <= current_type <= base + 1
    if 8 <= opcode <= 13:
        return not has_bit_1 and current_type == opcode - 8
    if 14 <= opcode <= 16:
        if not has_bit_1:
            return False
        base = {14: 0, 15: 2, 16: 4}[opcode]
        return base <= current_type <= base + 1
    if 17 <= opcode <= 22:
        return has_bit_1 and current_type == opcode - 17
    return False


def fits_room_piece_705(
    candidate_map: bytes | bytearray | memoryview,
    candidate_dims: Sequence[int],
    current_grid: bytes | bytearray | memoryview,
    current_grid_dims: Sequence[int],
    placement_xyz: Sequence[int],
    expected_neighbor_tag: int,
    range_min_xz: Sequence[int],
    range_max_xz: Sequence[int],
) -> bool:
    """Evaluate the 7.05 room-piece fit predicate over explicit buffers.

    ``candidate_map`` is the first 600 bytes of the native 0x2b0 room row:
    75 little-endian uint64 cells. ``candidate_dims`` is the three uint16s at
    row offset +0x258, ordered x/y/z. The map's fixed storage index is
    ``x + 5*y + 15*z``.

    ``current_grid`` stores five bytes per cell, in x-fastest order, with
    ``current_grid_dims`` ordered x/y/z. Bytes 0, 2, and 4 are consumed.
    ``placement_xyz`` is the candidate origin in the padded frame used by the
    native code. ``range_min_xz`` and ``range_max_xz`` are the two u16 pairs
    read from native arguments 8 and 9 (inclusive x/z limits).

    The native read at [rsp+0x4d] is byte 5 of the current packed candidate
    cell. The scene-callback producer starts each 600-byte map at zero and
    writes only bytes 0..4, so byte 5 is zero for maps from that path. For an
    in-bounds cell with byte 5 low bits set, native code takes an additional
    connection-validation path that is outside this bounded port; such input
    is rejected as unsupported instead of being guessed.
    """

    if len(candidate_map) < 600:
        raise ValueError("candidate_map must contain the native 600-byte row map")
    if len(current_grid_dims) != 3 or len(candidate_dims) != 3 or len(placement_xyz) != 3:
        raise ValueError("candidate dimensions, grid dimensions, and placement must be x/y/z triples")
    if len(range_min_xz) != 2 or len(range_max_xz) != 2:
        raise ValueError("range limits must be (x, z) pairs")

    piece_dims = tuple(int(v) for v in candidate_dims)
    grid_dims = tuple(int(v) for v in current_grid_dims)
    origin = tuple(int(v) for v in placement_xyz)
    low_xz = tuple(int(v) for v in range_min_xz)
    high_xz = tuple(int(v) for v in range_max_xz)

    if any(v < 0 or v > limit for v, limit in zip(piece_dims, _CANDIDATE_DIMS)):
        raise ValueError("candidate dimensions must fit within the native 5x3x5 row")
    if any(v < 0 or v > 0xFFFF for v in (*piece_dims, *grid_dims, *origin, *low_xz, *high_xz)):
        raise ValueError("dimension and coordinate inputs must fit native uint16 fields")
    if not 0 <= expected_neighbor_tag <= 0xFF:
        raise ValueError("expected_neighbor_tag must be a uint8 value")

    width, height, depth = grid_dims
    if len(current_grid) < width * height * depth * 5:
        raise ValueError("current_grid is shorter than its dimensions times the native 5-byte stride")

    for x in range(piece_dims[0]):
        for y in range(piece_dims[1]):
            for z in range(piece_dims[2]):
                piece_index = _candidate_cell_index(x, y, z)
                piece_offset = piece_index * 8
                packed = int.from_bytes(candidate_map[piece_offset : piece_offset + 8], "little")
                if packed == 0:
                    continue

                piece_byte0 = packed & 0xFF
                opcode = (packed >> 8) & 0xFF
                piece_byte2 = (packed >> 16) & 0xFF
                piece_byte3 = (packed >> 24) & 0xFF
                # The native [rsp+0x4d] byte read aliases byte 5 of the
                # qword saved at [rsp+0x48] for this candidate cell.
                piece_byte5 = _u8(candidate_map, piece_offset + 5)

                gx, gy, gz = origin[0] + x, origin[1] + y, origin[2] + z
                in_grid = (
                    gx >= 4
                    and gy >= 2
                    and gz >= 4
                    and gx < width + 4
                    and gy < height + 2
                    and gz < depth + 4
                )

                if not in_grid:
                    # The outer jump tables admit only opcodes 0/1 here.
                    if (
                        expected_neighbor_tag != 0
                        or opcode not in (0, 1)
                        or (piece_byte5 & 0x03) == 1
                        or (piece_byte0 & 0x02) == 0
                    ):
                        return False
                    continue

                if piece_byte5 & 0x03:
                    raise NotImplementedError(
                        "in-bounds candidate byte 5 low bits select an additional native "
                        "connection-validation path not covered by this port"
                    )

                grid_xyz = (gx - 4, gy - 2, gz - 4)
                grid_offset = _grid_cell_index(*grid_xyz, grid_dims) * 5
                grid_byte0 = _u8(current_grid, grid_offset)
                grid_byte2 = _u8(current_grid, grid_offset + 2)
                grid_byte4 = _u8(current_grid, grid_offset + 4)

                # The candidate byte 2 is a bit mask; byte 3 is its required
                # intersection with the current cell's compatibility byte.
                if (piece_byte2 & grid_byte4) != piece_byte3:
                    return False
                if opcode > 0x16 or not _opcode_accepts(opcode, grid_byte0):
                    return False

                same_tag = ((grid_byte2 - 1) & 0xFF) == expected_neighbor_tag
                if same_tag:
                    if grid_byte0 & 0x08:
                        required_piece_flag = 0x08
                    elif grid_byte0 & 0x04:
                        required_piece_flag = 0x10
                    else:
                        required_piece_flag = 0x04
                else:
                    required_piece_flag = 0
                    if grid_byte0 & 0x04:
                        direction = ((grid_byte0 ^ 0x20) >> 5) & 0xFF
                        if direction < 6:
                            neighbor = _current_neighbor(current_grid, grid_xyz, direction, grid_dims)
                            if neighbor is not None:
                                neighbor_offset = neighbor[3]
                                neighbor_tag_matches = (
                                    (_u8(current_grid, neighbor_offset + 2) - 1) & 0xFF
                                ) == expected_neighbor_tag
                                if neighbor_tag_matches and _candidate_neighbor_flag(
                                    candidate_map, (x, y, z), direction, 0x08
                                ):
                                    required_piece_flag = 0x40

                    # The second native scan resets the previous direction
                    # result when byte 0 carries the 0x08 connector family.
                    if grid_byte0 & 0x08:
                        required_piece_flag = 0
                        for direction in range(6):
                            neighbor = _current_neighbor(current_grid, grid_xyz, direction, grid_dims)
                            if neighbor is None:
                                continue
                            neighbor_offset = neighbor[3]
                            neighbor_tag_matches = (
                                (_u8(current_grid, neighbor_offset + 2) - 1) & 0xFF
                            ) == expected_neighbor_tag
                            neighbor_direction_matches = (
                                (_u8(current_grid, neighbor_offset) >> 5) == direction
                            )
                            if (
                                neighbor_tag_matches
                                and neighbor_direction_matches
                                and _candidate_neighbor_flag(candidate_map, (x, y, z), direction, 0x10)
                            ):
                                required_piece_flag = 0x20
                                break
                        if required_piece_flag == 0:
                            required_piece_flag = 0x01
                    elif required_piece_flag == 0 and (grid_byte0 & 0x04) == 0:
                        required_piece_flag = 0x01

                    if required_piece_flag == 0x01:
                        x_base, z_base = grid_xyz[0], grid_xyz[2]
                        inside_range = (
                            x_base >= low_xz[0]
                            and z_base >= low_xz[1]
                            and x_base <= high_xz[0]
                            and z_base <= high_xz[1]
                        )
                        if not inside_range:
                            required_piece_flag = 0x02

                if (piece_byte0 & required_piece_flag) == 0:
                    return False

    return True


@dataclass(frozen=True)
class RoomMapDimensions:
    """ID and dimension fields read from one native 0xa0 manager map row.

    ``dimension_84``, ``dimension_88``, and ``dimension_8c`` retain their
    native field offsets. A1DA0 tries extents (d8c,d88,d84), then (d84,d88,d8c)
    when the two outer dimensions differ.
    """

    room_id: bytes
    dimension_84: int
    dimension_88: int
    dimension_8c: int

    def __post_init__(self) -> None:
        if len(self.room_id) != 16:
            raise ValueError("native room IDs must be exactly 16 bytes")
        for value in (self.dimension_84, self.dimension_88, self.dimension_8c):
            if not 0 <= value <= 0x7FFFFFFF:
                raise ValueError("native map dimensions must be nonnegative int32 values")

    @classmethod
    def from_native_record(cls, record: bytes | bytearray | memoryview) -> "RoomMapDimensions":
        """Read a manager row's ID at +0x70 and dimensions at +0x84/+0x88/+0x8c."""
        if len(record) != 0xA0:
            raise ValueError("native manager map rows have a 0xa0-byte stride")
        return cls(
            room_id=bytes(record[0x70:0x80]),
            dimension_84=int.from_bytes(record[0x84:0x88], "little", signed=True),
            dimension_88=int.from_bytes(record[0x88:0x8C], "little", signed=True),
            dimension_8c=int.from_bytes(record[0x8C:0x90], "little", signed=True),
        )


def _i32(value: int) -> int:
    value &= 0xFFFFFFFF
    return value - 0x100000000 if value & 0x80000000 else value


def _read_u16(record: bytes | bytearray | memoryview, offset: int) -> int:
    return int.from_bytes(record[offset:offset + 2], "little")


def _room_box_contains_map_orientation(
    owner_grid: bytes | bytearray | memoryview,
    grid_dims: tuple[int, int, int],
    row_index: int,
    bounds: tuple[int, int, int, int, int, int],
    origin: tuple[int, int, int],
    extents: tuple[int, int, int],
) -> bool:
    min_x, min_y, min_z, max_x, max_y, max_z = bounds
    start_x, start_y, start_z = origin
    extent_x, extent_y, extent_z = extents
    if (
        start_x + extent_x - 1 > 0xFFFF
        or start_y + extent_y - 1 > 0xFFFF
        or start_z + extent_z - 1 > 0xFFFF
    ):
        raise NotImplementedError(
            "A1DA0 uses uint16 extent arithmetic; coordinate-wrap cases are outside the valid-map port"
        )
    last_x = start_x + extent_x - 1
    last_y = start_y + extent_y - 1
    last_z = start_z + extent_z - 1
    if last_x > max_x or last_y > max_y or last_z > max_z:
        return False

    size_x, size_y, _size_z = grid_dims
    expected_owner = (row_index + 1) & 0xFF
    for x in range(start_x, last_x + 1):
        for y in range(start_y, last_y + 1):
            for z in range(start_z, last_z + 1):
                cell_index = (z * size_y + y) * size_x + x
                if owner_grid[cell_index * 5 + 2] != expected_owner:
                    return False
    return True


def room_map_placement_accepts_1da0(
    logical_room_records: Sequence[bytes | bytearray | memoryview],
    room_count: int,
    owner_grid: bytes | bytearray | memoryview,
    grid_dims: Sequence[int],
    manager_maps: Sequence[RoomMapDimensions],
) -> bool:
    """Port FUN_1403A1DA0's room-map placement predicate over explicit data.

    Each selected logical row must resolve to the first matching manager map
    record, as in the native ordered 0xa0-byte table. For maps whose signed
    int32 dimension product exceeds one, the helper searches the row's A1A00
    bounds for a fully owned axis-aligned volume. It tries native extent order
    ``(d8c, d88, d84)`` and, when ``d8c != d84``, the X/Z-swapped order.

    The predicate reads only owner-grid byte +2, six u16 bounds at logical-row
    +0x00, the room ID at +0x28, manager-map IDs/dimensions, and grid SizeX /
    SizeY. It consumes no RNG and writes nothing. A1DA0 dereferences a null map
    pointer when a selected ID has no manager entry; this port raises
    ``ValueError`` so callers must supply the exact map table instead of
    silently treating a missing map as a failed fit.
    """
    if not 0 <= room_count <= 0xFF:
        raise ValueError("FUN_1403A1DA0 receives a byte room count")
    if room_count == 0:
        return True
    if len(logical_room_records) < room_count:
        raise ValueError(f"need {room_count} logical rows, got {len(logical_room_records)}")
    if any(len(logical_room_records[i]) != 0x40 for i in range(room_count)):
        raise ValueError("each logical room row must be exactly 0x40 bytes")
    if len(grid_dims) != 3:
        raise ValueError("grid_dims must be an x/y/z triple")
    dims = tuple(int(value) for value in grid_dims)
    if any(value <= 0 or value > 0xFFFF for value in dims):
        raise ValueError("DungeonParams grid dimensions must be positive uint16 values")
    size_x, size_y, size_z = dims
    if size_x * size_y * size_z > 0xFFFF:
        raise ValueError("native flattened grid index must fit its uint16 range")
    if len(owner_grid) < size_x * size_y * size_z * 5:
        raise ValueError("owner_grid is shorter than SizeX*SizeY*SizeZ five-byte cells")

    for row_index in range(room_count):
        row = logical_room_records[row_index]
        room_id = bytes(row[0x28:0x38])
        if room_id == bytes(16):
            raise ValueError("native A1DA0 skips map lookup for a zero ID then dereferences null")
        piece = next((candidate for candidate in manager_maps if candidate.room_id == room_id), None)
        if piece is None:
            raise ValueError(f"no native manager-map row for room ID {room_id.hex()}")

        d84, d88, d8c = (
            piece.dimension_84,
            piece.dimension_88,
            piece.dimension_8c,
        )
        volume = _i32(_i32(d84 * d8c) * d88)
        if volume <= 1:
            continue

        word_d84, word_d88, word_d8c = d84 & 0xFFFF, d88 & 0xFFFF, d8c & 0xFFFF
        if 0 in (word_d84, word_d88, word_d8c):
            raise NotImplementedError(
                "A1DA0's valid manager-map dimensions have nonzero low words; "
                "zero low-word dimensions require separate wrap-loop recovery"
            )

        bounds = tuple(_read_u16(row, offset) for offset in (0, 2, 4, 6, 8, 10))
        min_x, min_y, min_z, max_x, max_y, max_z = bounds
        if min_x > max_x:
            return False  # native A1DA0 fails immediately at its first X origin
        if max_x >= size_x or max_y >= size_y or max_z >= size_z:
            raise ValueError("A1DA0 expects A1A00 bounds to lie inside the supplied owner grid")
        if min_y > max_y or min_z > max_z:
            return False

        orientations = [(word_d8c, word_d88, word_d84)]
        if d8c != d84:
            orientations.append((word_d84, word_d88, word_d8c))

        found = False
        for start_x in range(min_x, max_x + 1):
            for start_y in range(min_y, max_y + 1):
                for start_z in range(min_z, max_z + 1):
                    for extents in orientations:
                        if _room_box_contains_map_orientation(
                            owner_grid,
                            dims,
                            row_index,
                            bounds,
                            (start_x, start_y, start_z),
                            extents,
                        ):
                            found = True
                            break
                    if found:
                        break
                if found:
                    break
            if found:
                break
        if not found:
            return False
    return True


PORT_STATUS = {
    "FUN_1403A3270": "bounded candidate-piece fit predicate ported for supported byte-5-zero callback maps; nonzero in-bounds byte-5 path remains unsupported",
    "FUN_1403A1DA0": "room-map volume placement predicate ported from explicit ordered manager-map IDs/dimensions, logical A1A00 bounds, and owner grid; map provider/table capture remains an input boundary",
}


__all__ = ["RoomMapDimensions", "fits_room_piece_705", "room_map_placement_accepts_1da0", "PORT_STATUS"]
