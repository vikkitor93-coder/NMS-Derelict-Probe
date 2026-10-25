"""Explicit-input orchestration port of NMS 7.05 FUN_1403A2780.

This connects the already-portable source selector, A23B0 coordinate search,
A3270 fit predicate, A5480 grid write, quest-tag decoder, and static A3BC0
catalog. It intentionally does not guess the ordered 0x2b0 manager rows,
visitor-derived fit bounds, or imported callback additions. Supply those as
inputs to :func:`run_a2780_search`.

Exact-build provenance
----------------------
NMS.exe SHA-256:
  13D5060D4EFB9D2A6A6B1B349BC4257231056CC2A055DF4BB15D816262CC3499
Evidence:
  D:\\Orca\\Temp\\nms-ghidra-targeted-20261019\\dungeon_writer_methods.txt
  D:\\Orca\\Temp\\nms-ghidra-targeted-20261019\\a2780_stack_disasm.txt
  D:\\Orca\\Temp\\nms-ghidra-targeted-20261019\\a23b0_recovery_assembly_20261019.txt

The A2780 call is made after A1DA0 accepts the proposed room grid. Its
required quest placements fail the whole call if A23B0 cannot place the first
shuffled source row. Theme placements are best-effort: A2780 scans each room's
expanded A3BC0 groups over every candidate origin, updating the shared grid
and per-group counters as it goes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

try:  # direct module use with this directory on sys.path
    from nms_dungeon_fit_705 import fits_room_piece_705
    from nms_dungeon_piece_selector_705 import (
        A2780Ordering,
        GeneratedPieceSourceMetadata,
        _native_fisher_yates_order,
        a2780_group_allows_candidate,
        a2780_probability_pass,
        filter_source_rows,
        order_source_rows_for_a2780,
    )
    from nms_dungeon_pregraph_705 import QuestOption
    from nms_dungeon_source_catalog_705 import A3BC0Group, GeneratedBaseSourceCatalog
    from nms_dungeon_topology_705 import NativeSeedRng, ProceduralGrid, native_room_key
    from nms_dungeon_variable_placement_705 import (
        PIECE_MAP_ROW_SIZE,
        VariablePlacementAppendRecord,
        VariablePlacementResult,
        or_piece_map_connections_5480,
        search_variable_placement_23b0,
    )
except ImportError:  # pragma: no cover - package-style use
    from .nms_dungeon_fit_705 import fits_room_piece_705
    from .nms_dungeon_piece_selector_705 import (
        A2780Ordering,
        GeneratedPieceSourceMetadata,
        _native_fisher_yates_order,
        a2780_group_allows_candidate,
        a2780_probability_pass,
        filter_source_rows,
        order_source_rows_for_a2780,
    )
    from .nms_dungeon_pregraph_705 import QuestOption
    from .nms_dungeon_source_catalog_705 import A3BC0Group, GeneratedBaseSourceCatalog
    from .nms_dungeon_topology_705 import NativeSeedRng, ProceduralGrid, native_room_key
    from .nms_dungeon_variable_placement_705 import (
        PIECE_MAP_ROW_SIZE,
        VariablePlacementAppendRecord,
        VariablePlacementResult,
        or_piece_map_connections_5480,
        search_variable_placement_23b0,
    )


NMS_EXE_SHA256 = "13D5060D4EFB9D2A6A6B1B349BC4257231056CC2A055DF4BB15D816262CC3499"
LOGICAL_ROOM_RECORD_SIZE = 0x40
QUEST_TAG_COUNT_OFFSET = 0x39
QUEST_TAGS_OFFSET = 0x3A
QUEST_TAG_CAPACITY = 5
A2780_GROUP_SLOT_COUNT = 16
A2780_GROUP_WORD_STRIDE = 17
MAX_A2780_GROUPS = 1016 // A2780_GROUP_WORD_STRIDE
MAX_ORIGIN_VISITS = 1_000_000


@dataclass(frozen=True)
class A2780Placement:
    """One accepted A6150 descriptor with only initialized bytes represented.

    A23B0 leaves bytes 16, 18, and 19 uninitialized. A2780 writes the path
    slot at byte 16 after A23B0 appends the descriptor, so only bytes 18 and
    19 remain unknown in the final placement record.
    """

    record: VariablePlacementAppendRecord
    room_index: int
    room_key: bytes
    room_id: str
    layer: int
    path_slot: int
    selection_kind: str
    selector: str
    source_map_index: int

    @property
    def known_segments(self) -> tuple[tuple[int, bytes], ...]:
        segments = list(self.record.known_segments)
        segments.append((16, bytes((self.path_slot & 0xFF,))))
        return tuple(sorted(segments, key=lambda item: item[0]))

    @property
    def uninitialized_offsets(self) -> tuple[int, int]:
        return (18, 19)


@dataclass(frozen=True)
class A2780SearchEvent:
    """Compact audit row for one selector, group, or accepted placement."""

    kind: str
    room_index: int
    layer: int
    selector: str
    source_map_index: int | None
    coordinate: tuple[int, int, int] | None
    rng_state_before: int
    rng_state_after: int
    detail: str


@dataclass(frozen=True)
class A2780SearchResult:
    """A2780 result plus deterministic state needed for the outer writer."""

    success: bool
    placements: tuple[A2780Placement, ...]
    events: tuple[A2780SearchEvent, ...]
    rng_state_before: int
    rng_state_after: int
    failure_reason: str | None


def _u16(value: int) -> int:
    return value & 0xFFFF


def _quest_item_for_tag(tag: int, quest_options: Sequence[QuestOption]) -> bytes:
    """Resolve A2780's packed quest tag through the ordered preset Quests."""
    option_index = tag & 0x0F
    item_index = (tag >> 4) & 0x0F
    if option_index >= len(quest_options):
        raise ValueError(
            f"quest tag 0x{tag:02X} selects absent Quests option {option_index}"
        )
    option = quest_options[option_index]
    if item_index >= len(option.quest_item_ids):
        raise ValueError(
            f"quest tag 0x{tag:02X} selects absent item {item_index} in option {option_index}"
        )
    return option.quest_item_ids[item_index]


def _room_path_slots(room_records: Sequence[bytes], room_count: int) -> tuple[int, ...]:
    """Port A2780's signed-char path counter across main/branch rows."""
    result: list[int] = []
    current = -1
    for index in range(room_count):
        if room_records[index][0x38] == 0:
            current = (current + 1) & 0xFF
            current_signed = current - 0x100 if current & 0x80 else current
            current = current_signed
        result.append(current & 0xFF)
    return tuple(result)


def _room_id_lookup(catalog: GeneratedBaseSourceCatalog) -> dict[bytes, str]:
    lookup: dict[bytes, str] = {}
    for room_id in catalog.bundle.room_rows:
        key = native_room_key(room_id)
        if key in lookup:
            raise ValueError(f"catalog room key collision for {room_id!r}")
        lookup[key] = room_id
    return lookup


def _validate_room_rows(room_records: Sequence[bytes], room_count: int) -> None:
    if not 0 <= room_count <= 0xFF:
        raise ValueError("A2780 receives the room count as a byte")
    if len(room_records) < room_count:
        raise ValueError(f"need {room_count} logical room rows, got {len(room_records)}")
    if any(len(room_records[index]) != LOGICAL_ROOM_RECORD_SIZE for index in range(room_count)):
        raise ValueError("each logical room row must be exactly 0x40 bytes")
    for index in range(room_count):
        count = room_records[index][QUEST_TAG_COUNT_OFFSET]
        if count > QUEST_TAG_CAPACITY:
            raise ValueError(f"room row {index} has {count} quest tags; native capacity is 5")


def _room_origin_bounds(room_record: bytes) -> tuple[range, range, range]:
    """Decode A2780's x/y/z origin loops from A1A00's six u16 bounds."""
    start_x = int.from_bytes(room_record[0:2], "little")
    start_y = int.from_bytes(room_record[2:4], "little")
    start_z = int.from_bytes(room_record[4:6], "little")
    end_x = _u16(int.from_bytes(room_record[6:8], "little") + 5)
    end_y = _u16(int.from_bytes(room_record[8:10], "little") + 3)
    end_z = _u16(int.from_bytes(room_record[10:12], "little") + 5)
    if end_x < start_x or end_y < start_y or end_z < start_z:
        raise NotImplementedError("A2780 wrapped/inverted origin bounds are not in the bounded port")
    return range(start_x, end_x + 1), range(start_y, end_y + 1), range(start_z, end_z + 1)


def _native_a2780_append_record(
    base_record: VariablePlacementAppendRecord,
    *,
    room_index: int,
    room_key: bytes,
    room_id: str,
    layer: int,
    path_slot: int,
    selection_kind: str,
    selector: str,
) -> A2780Placement:
    return A2780Placement(
        record=base_record,
        room_index=room_index,
        room_key=room_key,
        room_id=room_id,
        layer=layer,
        path_slot=path_slot,
        selection_kind=selection_kind,
        selector=selector,
        source_map_index=base_record.map_index,
    )


def run_a2780_search(
    *,
    rng: NativeSeedRng,
    catalog: GeneratedBaseSourceCatalog,
    quest_options: Sequence[QuestOption],
    room_records: Sequence[bytes],
    room_count: int,
    grid: ProceduralGrid,
    fit_min_xyz: Sequence[int],
    fit_max_xyz: Sequence[int],
    map_row_provider: Callable[[int], bytes],
    source_metadata: Sequence[GeneratedPieceSourceMetadata] | None = None,
    room_id_by_key: Mapping[bytes, str] | None = None,
    max_origin_visits: int = MAX_ORIGIN_VISITS,
) -> A2780SearchResult:
    """Run the A2780 quest and A3BC0 placement loops over explicit inputs.

    ``room_records`` are the post-A1A00 0x40 logical rows. ``map_row_provider``
    must return the exact 0x2b0 row for a requested generated-base source index
    (or a clearly labelled candidate row for exploratory execution).
    ``fit_min_xyz``/``fit_max_xyz`` are the bounds passed to A2780/A23B0. The
    shared grid is mutated in place by accepted A23B0/A5480 placements.

    The function does not materialize static scene maps itself. In particular,
    it cannot infer the visitor manager's cached local AABB or synthesize
    imported/type-specific callback nodes. This keeps exact runtime map rows
    and static direct-MXML candidate rows distinguishable at the boundary.
    """
    _validate_room_rows(room_records, room_count)
    if len(fit_min_xyz) != 3 or len(fit_max_xyz) != 3:
        raise ValueError("fit_min_xyz and fit_max_xyz must each be XYZ triples")
    if any(not 0 <= int(value) <= 0xFFFF for value in (*fit_min_xyz, *fit_max_xyz)):
        raise ValueError("A2780 fit-bound coordinates must be uint16 values")
    if max_origin_visits <= 0:
        raise ValueError("max_origin_visits must be positive")

    metadata_rows = tuple(
        catalog.source_metadata() if source_metadata is None else source_metadata
    )
    metadata_by_index = {row.row_index: row for row in metadata_rows}
    if len(metadata_by_index) != len(metadata_rows):
        raise ValueError("source metadata contains duplicate generated-base row indexes")
    name_by_key = dict(room_id_by_key) if room_id_by_key is not None else _room_id_lookup(catalog)
    path_slots = _room_path_slots(room_records, room_count)
    rng_before = rng.state
    placements: list[A2780Placement] = []
    events: list[A2780SearchEvent] = []
    map_row_cache: dict[int, bytes] = {}

    def map_row(map_index: int) -> bytes:
        if map_index not in map_row_cache:
            row = bytes(map_row_provider(map_index))
            if len(row) != PIECE_MAP_ROW_SIZE:
                raise ValueError(
                    f"map row {map_index} must be 0x2b0 bytes, got 0x{len(row):X}"
                )
            if map_index not in metadata_by_index:
                raise ValueError(f"no source metadata for generated-base row {map_index}")
            if metadata_by_index[map_index].row_index != map_index:
                raise ValueError(f"source metadata index mismatch at map row {map_index}")
            map_row_cache[map_index] = row
        return map_row_cache[map_index]

    def room_identity(room_index: int) -> tuple[bytes, str]:
        key = bytes(room_records[room_index][0x28:0x38])
        room_id = name_by_key.get(key)
        if room_id is None:
            raise ValueError(f"room row {room_index} has no catalog RoomId for key {key.hex()}")
        return key, room_id

    def append_from_a23b0(
        *,
        room_index: int,
        room_key: bytes,
        room_id: str,
        layer: int,
        map_index: int,
        mode: int,
        selection_kind: str,
        selector: str,
    ) -> VariablePlacementResult:
        appended: list[VariablePlacementAppendRecord] = []
        result = search_variable_placement_23b0(
            rng=rng,
            source_row=room_records[room_index],
            piece_map_row=map_row(map_index),
            map_index=map_index,
            mode=mode,
            grid=grid,
            fit_min_xyz=fit_min_xyz,
            fit_max_xyz=fit_max_xyz,
            append_a6150=appended.append,
        )
        if result.success:
            if len(appended) != 1:
                raise RuntimeError("successful A23B0 must append exactly one placement record")
            placements.append(
                _native_a2780_append_record(
                    appended[0],
                    room_index=room_index,
                    room_key=room_key,
                    room_id=room_id,
                    layer=layer,
                    path_slot=path_slots[room_index],
                    selection_kind=selection_kind,
                    selector=selector,
                )
            )
        return result

    # Native A2780 processes layers outside rooms, and each room's required
    # quest placements before that room's optional theme decorations.
    for layer in range(8):
        for room_index in range(room_count):
            room = room_records[room_index]
            room_key, room_id = room_identity(room_index)
            path_slot = path_slots[room_index]

            tag_count = room[QUEST_TAG_COUNT_OFFSET]
            for tag_index in range(tag_count):
                tag = room[QUEST_TAGS_OFFSET + tag_index]
                item_key = _quest_item_for_tag(tag, quest_options)
                filtered = filter_source_rows(
                    metadata_rows,
                    item_key,
                    layer,
                )
                if not filtered.row_indices:
                    continue

                ordering: A2780Ordering = order_source_rows_for_a2780(
                    rng,
                    filtered.row_indices,
                )
                selected_map = ordering.source_row_indices[0]
                state_before = rng.state
                try:
                    placement = append_from_a23b0(
                        room_index=room_index,
                        room_key=room_key,
                        room_id=room_id,
                        layer=layer,
                        map_index=selected_map,
                        mode=room_index,
                        selection_kind="quest",
                        selector=f"quest-option-{tag & 0x0F}-item-{tag >> 4}",
                    )
                except (ValueError, NotImplementedError) as exc:
                    return A2780SearchResult(
                        False,
                        tuple(placements),
                        tuple(events),
                        rng_before,
                        rng.state,
                        f"required quest placement could not be evaluated: {exc}",
                    )
                events.append(
                    A2780SearchEvent(
                        kind="quest-placement",
                        room_index=room_index,
                        layer=layer,
                        selector=f"tag=0x{tag:02X};key={item_key.hex()}",
                        source_map_index=selected_map,
                        coordinate=placement.origin_xyz,
                        rng_state_before=state_before,
                        rng_state_after=rng.state,
                        detail=(
                            f"candidate_rows={len(filtered.row_indices)};"
                            f"source_order={ordering.source_row_indices};"
                            f"slot_order={ordering.slot_order};success={placement.success}"
                        ),
                    )
                )
                if not placement.success:
                    return A2780SearchResult(
                        False,
                        tuple(placements),
                        tuple(events),
                        rng_before,
                        rng.state,
                        f"A23B0 failed required quest tag 0x{tag:02X} in room {room_index}",
                    )

            groups: tuple[A3BC0Group, ...] = catalog.a3bc0_groups(room_id, layer)
            if len(groups) > MAX_A2780_GROUPS:
                raise ValueError(
                    f"room {room_id} layer {layer} has {len(groups)} A3BC0 groups; "
                    f"A2780's local group workspace holds {MAX_A2780_GROUPS}"
                )
            group_counts = [0] * len(groups)
            x_range, y_range, z_range = _room_origin_bounds(room)
            origin_count = len(x_range) * len(y_range) * len(z_range)
            if origin_count > max_origin_visits:
                raise ValueError(
                    f"room {room_index} has {origin_count} A2780 origin visits; "
                    f"configured ceiling is {max_origin_visits}"
                )

            for x in x_range:
                for y in y_range:
                    for z in z_range:
                        coordinate = (x, y, z)
                        state_before = rng.state
                        # Native code shuffles group order (when groups exist),
                        # then always shuffles the fixed 16 slots per origin.
                        group_order = _native_fisher_yates_order(rng, len(groups))
                        slot_order = _native_fisher_yates_order(rng, A2780_GROUP_SLOT_COUNT)

                        for group_index in group_order:
                            group = groups[group_index]
                            if len(group.source_row_indices) > A2780_GROUP_WORD_STRIDE:
                                raise ValueError("A3BC0 group exceeds its native 17-word stride")
                            # A2780 initializes word 17 as its mutable count,
                            # so only the first 16 A3BC0 candidates are usable.
                            candidates = tuple(group.source_row_indices[:A2780_GROUP_SLOT_COUNT])
                            if not candidates:
                                continue
                            first_metadata = metadata_by_index.get(candidates[0])
                            if first_metadata is None:
                                raise ValueError(f"no source metadata for A3BC0 group row {candidates[0]}")
                            if not a2780_group_allows_candidate(
                                group_counts[group_index],
                                first_metadata,
                                path_slot,
                            ):
                                continue

                            # The max/invalid gate occurs once before the
                            # native 16-slot scan for this group and origin.
                            for slot_position, candidate_slot in enumerate(slot_order):
                                if candidate_slot >= len(candidates):
                                    continue  # A3BC0's unused slots are -1.
                                selected_map = candidates[candidate_slot]
                                metadata = metadata_by_index.get(selected_map)
                                if metadata is None:
                                    raise ValueError(f"no source metadata for A3BC0 row {selected_map}")
                                if not a2780_probability_pass(rng, metadata.probability):
                                    continue

                                native_row = map_row(selected_map)
                                dimensions = tuple(
                                    int.from_bytes(native_row[offset:offset + 2], "little")
                                    for offset in (0x258, 0x25A, 0x25C)
                                )
                                fits = fits_room_piece_705(
                                    candidate_map=native_row[:600],
                                    candidate_dims=dimensions,
                                    current_grid=grid.cells,
                                    current_grid_dims=(
                                        grid.dimensions.x,
                                        grid.dimensions.y,
                                        grid.dimensions.z,
                                    ),
                                    placement_xyz=coordinate,
                                    expected_neighbor_tag=room_index,
                                    range_min_xz=(int(fit_min_xyz[0]), int(fit_min_xyz[2])),
                                    range_max_xz=(int(fit_max_xyz[0]), int(fit_max_xyz[2])),
                                )
                                if not fits:
                                    continue

                                record = VariablePlacementAppendRecord(
                                    map_index=selected_map,
                                    origin_xyz=coordinate,
                                    mode=room_index,
                                    source_byte_20=room[0x20],
                                    source_byte_38=room[0x38],
                                )
                                placements.append(
                                    _native_a2780_append_record(
                                        record,
                                        room_index=room_index,
                                        room_key=room_key,
                                        room_id=room_id,
                                        layer=layer,
                                        path_slot=path_slot,
                                        selection_kind="theme",
                                        selector=group.decoration_id,
                                    )
                                )
                                or_piece_map_connections_5480(grid, native_row, coordinate)
                                group_counts[group_index] += 1
                                events.append(
                                    A2780SearchEvent(
                                        kind="theme-placement",
                                        room_index=room_index,
                                        layer=layer,
                                        selector=group.decoration_id,
                                        source_map_index=selected_map,
                                        coordinate=coordinate,
                                        rng_state_before=state_before,
                                        rng_state_after=rng.state,
                                        detail=(
                                            f"slot_position={slot_position};"
                                            f"group_count={group_counts[group_index]}"
                                        ),
                                    )
                                )

            events.append(
                A2780SearchEvent(
                    kind="room-layer-complete",
                    room_index=room_index,
                    layer=layer,
                    selector="",
                    source_map_index=None,
                    coordinate=None,
                    rng_state_before=rng.state,
                    rng_state_after=rng.state,
                    detail=f"theme_groups={len(groups)};placements={sum(group_counts)}",
                )
            )

    return A2780SearchResult(
        True,
        tuple(placements),
        tuple(events),
        rng_before,
        rng.state,
        None,
    )


__all__ = [
    "A2780Placement",
    "A2780SearchEvent",
    "A2780SearchResult",
    "MAX_A2780_GROUPS",
    "MAX_ORIGIN_VISITS",
    "NMS_EXE_SHA256",
    "run_a2780_search",
]
