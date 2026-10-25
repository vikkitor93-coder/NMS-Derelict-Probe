"""Preset Quests rows for the NMS 7.05 A2780 quest-tag decoder.

RECOVERY STATUS (stage 2 / G2, 2026-10-25)
------------------------------------------
The original module (the dungeon pre-graph: quest options, A1A00 inputs) is
LOST and nothing of it survives in the logs (0 hits). Only ``QuestOption`` is
imported by surviving code (nms_dungeon_a2780_search_705), which reads
``option.quest_item_ids[item_index]`` as the 16-byte key compared with source
metadata +0x20/+0x28. This file is a RECONSTRUCTION of that one interface,
from the A2780 decompile (log a10afc4c L89): the options array is read at
``param_4 + 0x40`` with a 0x18 stride per option and 16 bytes per item
(``(tag & 0x0F) * 0x18`` selects the option, ``tag & 0xF0`` the item offset).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

try:
    from nms_dungeon_topology_705 import native_room_key
except ImportError:  # pragma: no cover - package-style use
    from .nms_dungeon_topology_705 import native_room_key


@dataclass(frozen=True)
class QuestOption:
    """One ordered GcFreighterDungeonParams Quests option."""

    name: str
    quest_item_ids: tuple[bytes, ...]

    def __post_init__(self) -> None:
        if len(self.quest_item_ids) > 16:
            raise ValueError("a packed quest tag addresses at most 16 items per option")
        if any(len(item) != 16 for item in self.quest_item_ids):
            raise ValueError("quest item ids are native 16-byte keys")

    @classmethod
    def from_ids(cls, name: str, item_ids: Iterable[str]) -> "QuestOption":
        return cls(str(name), tuple(native_room_key(item) for item in item_ids))


def quest_options_from_rows(rows: Sequence[tuple[str, Sequence[str]]]) -> tuple[QuestOption, ...]:
    """Build the ordered option list from (name, item ids) rows in preset source order."""
    options = tuple(QuestOption.from_ids(name, ids) for name, ids in rows)
    if len(options) > 16:
        raise ValueError("a packed quest tag addresses at most 16 options")
    return options


__all__ = ["QuestOption", "quest_options_from_rows"]
