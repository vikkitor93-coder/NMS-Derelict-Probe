"""A2780/A3F00 source-row selection helpers for the NMS 7.05 offline port.

RECOVERY STATUS (stage 2 / G2, 2026-10-25) -- read before trusting this file
----------------------------------------------------------------------------
The original module is LOST (it also held the A51B0 callback-pruning port,
``apply_a51b0_pruning`` and its record types, which nothing in the surviving
tree imports and which are NOT rebuilt). Provenance per region:

* ``GeneratedPieceSourceMetadata`` fields, docstring and the first checks of
  ``__post_init__`` (original lines 54-79): VERBATIM from log a717a84b L238.
* ``a2780_group_allows_candidate`` and ``a2780_probability_pass`` (original
  lines 261-292): VERBATIM from log a10afc4c L75.
* ``DECORATION_LAYER_COUNT``, ``A3F00Filter``/``filter_source_rows``,
  ``A2780Ordering``/``order_source_rows_for_a2780`` and
  ``_native_fisher_yates_order``: RECONSTRUCTED from the FUN_1403A2780
  decompile (log a10afc4c L89) and from how nms_dungeon_a2780_search_705 uses
  them. Native shuffle: ``for k in 0..n-2: j = k + bounded(n - k); swap``.

Native detail the surviving a2780_search port does not model (recorded, not
"fixed" here because it is outside the layout path): A2780 initialises its
16-slot array once per call and its group-order array once per room, then
shuffles them IN PLACE at every origin, so successive permutations compose.
``_native_fisher_yates_order`` therefore accepts an optional ``order`` to
shuffle in place; called without it, it shuffles the identity (what
a2780_search does). Also, native always consumes the 15 slot-shuffle draws for
a quest tag even when no source row matches; a2780_search ``continue``s first.

Nothing here was compared against a native run. The production layout path
(native writer + derive()) never calls these functions.
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from typing import MutableSequence, Sequence

try:
    from nms_dungeon_topology_705 import NativeSeedRng
except ImportError:  # pragma: no cover - package-style use
    from .nms_dungeon_topology_705 import NativeSeedRng


DECORATION_LAYER_COUNT = 8
A2780_SLOT_COUNT = 16


@dataclass(frozen=True)
class GeneratedPieceSourceMetadata:
    """The A2780/A3F00 metadata fields needed by the bounded filter.

    ``key_pair`` is the 16-byte value read from metadata +0x20/+0x28.
    ``decoration_layer`` is the numeric value read from metadata +0x40.
    The other fields preserve A2780's later per-group checks, but this helper
    does not apply them because their group/room context is caller-owned.
    """

    row_index: int
    key_pair: bytes
    decoration_layer: int
    max_per_room: int
    invalid_room_indexes: tuple[int, ...]
    probability: float

    def __post_init__(self) -> None:
        if self.row_index < 0:
            raise ValueError("generated source-row index must be nonnegative")
        if len(self.key_pair) != 16:
            raise ValueError("native metadata key pair must be exactly 16 bytes")
        if not 0 <= self.decoration_layer < DECORATION_LAYER_COUNT:
            raise ValueError("A2780 layer pass is in the range 0..7")
        if self.max_per_room < 0:
            raise ValueError("MaxPerRoom cannot be negative")
        if any(not 0 <= value <= 0xFFFFFFFF for value in self.invalid_room_indexes):
            # --- RECONSTRUCTED from here to the end of __post_init__ ---
            raise ValueError("InvalidRoomIndexes entries are native uint32 values")
        if not math.isfinite(float(self.probability)):
            raise ValueError("Probability must be a finite float32")


# --- RECONSTRUCTED: A3F00-style filter and the A2780 shuffles ---------------

@dataclass(frozen=True)
class A3F00Filter:
    """Rows matching one 16-byte key in one layer, in native table order.

    ``key_present`` mirrors A2780's separate "any row has this key" flag: when
    it is false the native candidate count is -1 instead of 0 (both place
    nothing).
    """

    row_indices: tuple[int, ...]
    key_present: bool


@dataclass(frozen=True)
class A2780Ordering:
    """Shuffled candidate rows plus the 16-slot order consumed after them."""

    source_row_indices: tuple[int, ...]
    slot_order: tuple[int, ...]


def filter_source_rows(
    metadata_rows: Sequence[GeneratedPieceSourceMetadata],
    item_key: bytes,
    layer: int,
) -> A3F00Filter:
    """Scan the source rows in order for ``item_key`` (+0x20/+0x28) and ``layer`` (+0x40)."""
    if len(item_key) != 16:
        raise ValueError("item key must be exactly 16 bytes")
    if not 0 <= layer < DECORATION_LAYER_COUNT:
        raise ValueError("A2780 layer pass is in the range 0..7")
    key = bytes(item_key)
    present = False
    rows: list[int] = []
    for row in metadata_rows:
        if row.key_pair == key:
            present = True
            if row.decoration_layer == layer:
                rows.append(row.row_index)
    return A3F00Filter(tuple(rows), present)


def _native_fisher_yates_order(
    rng: NativeSeedRng,
    count: int,
    order: MutableSequence[int] | None = None,
) -> tuple[int, ...]:
    """A2780's forward Fisher-Yates: ``count - 1`` draws, none for ``count <= 1``.

    With ``order`` the list is shuffled in place (native persistence across
    origins); otherwise the identity ``0..count-1`` is shuffled.
    """
    if count < 0:
        raise ValueError("shuffle length cannot be negative")
    values = list(range(count)) if order is None else order
    if len(values) != count:
        raise ValueError("order length must equal count")
    for k in range(count - 1):
        j = k + rng.bounded_index(count - k)
        values[k], values[j] = values[j], values[k]
    return tuple(values)


def order_source_rows_for_a2780(
    rng: NativeSeedRng,
    row_indices: Sequence[int],
    slot_order: MutableSequence[int] | None = None,
) -> A2780Ordering:
    """Shuffle the quest candidate rows, then the 16 slots (always 15 draws)."""
    rows = tuple(int(v) for v in row_indices)
    permutation = _native_fisher_yates_order(rng, len(rows))
    slots = _native_fisher_yates_order(rng, A2780_SLOT_COUNT, slot_order)
    return A2780Ordering(tuple(rows[i] for i in permutation), slots)


# --- VERBATIM (original lines 261-292) ---------------------------------------

def a2780_group_allows_candidate(
    current_count: int,
    group_metadata: GeneratedPieceSourceMetadata,
    selector_index: int,
) -> bool:
    """Port the MaxPerRoom and InvalidRoomIndexes gate in A2780.

    The native comparison sign-extends the selector byte but reads each
    invalid-index entry's low byte as unsigned. A negative selector therefore
    cannot match an invalid-index entry, matching the native mixed-signedness
    comparison.
    """
    if current_count < 0:
        raise ValueError("A2780 group count cannot be negative")
    selector_index &= 0xFF
    signed_selector = selector_index - 0x100 if selector_index & 0x80 else selector_index
    if current_count >= group_metadata.max_per_room:
        return False
    if signed_selector < 0:
        return True
    return not any((value & 0xFF) == signed_selector for value in group_metadata.invalid_room_indexes)


def a2780_probability_pass(rng: NativeSeedRng, probability: float) -> bool:
    """Consume one A2780 RNG draw and compare it with a native float field.

    Native code consumes this draw only after the current group passes its
    MaxPerRoom and InvalidRoomIndexes checks and the candidate row index is
    nonnegative. The row's +0x48 probability is a float32.
    """
    native_probability = struct.unpack("<f", struct.pack("<f", probability))[0]
    return rng.unit_float32() < native_probability


__all__ = [
    "A2780Ordering",
    "A2780_SLOT_COUNT",
    "A3F00Filter",
    "DECORATION_LAYER_COUNT",
    "GeneratedPieceSourceMetadata",
    "a2780_group_allows_candidate",
    "a2780_probability_pass",
    "filter_source_rows",
    "order_source_rows_for_a2780",
]
