# [G1 2026-10-25] Lines 1-25 logged (sess 3bcdb12b L2849); the block marked 'G1 RECONSTRUCTED' below is new code; from 'class MaterializedSceneMap' to the end is the logged original (lines 140-410).
"""Static source-row catalog and A3BC0 group expansion for NMS 7.05.

This module connects the exact generated-base MXML tables to A2780's explicit
source-row filter. It models the native manager row order as orientation rows
with one row per reachable CELL*C selector value, then expands a room's themes
to distinct decoration IDs and source-map indices in native table order.

The source order is checked against the exact generated-base MBIN before the
catalog is built.

It does not claim that the scene maps are byte exact: map bytes are generated
on demand through ``scene_callback_matrix_705`` and retain that adapter's
explicit engine-bounds and callback-order candidate labels.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import struct
from pathlib import Path
from typing import Mapping, Sequence

try:  # direct module use with this directory on sys.path
    from nms_dungeon_offline import StaticBundle, load_scene_map_nodes, load_static_bundle
    from nms_dungeon_piece_selector_705 import GeneratedPieceSourceMetadata
    from nms_dungeon_topology_705 import native_room_key
except ImportError:  # pragma: no cover - package-style use
    from .nms_dungeon_offline import StaticBundle, load_scene_map_nodes, load_static_bundle
    from .nms_dungeon_piece_selector_705 import GeneratedPieceSourceMetadata
    from .nms_dungeon_topology_705 import native_room_key

# [G1 RECONSTRUCTED: original lines 26-139 are lost. Everything from here to the end of class A3BC0Group was
#  re-written on 2026-10-25 from the call sites in lines 140-410 (logged) and the grep -n line map in the logs
#  (NMS_EXE_SHA256 at 34, PIECE_MAP_DIMS_OFFSET at 49, _strings 52, _int_array 62, _float32 70,
#  DecorationSource 75, SceneMapVariant 96, A3BC0Group 112, a3bc0_words 120, initialized_a2780_words 127).
#  Line numbers below therefore do not match the original exactly.]

NMS_EXE_SHA256 = "13D5060D4EFB9D2A6A6B1B349BC4257231056CC2A055DF4BB15D816262CC3499"
# SHA-256 of research-output/generatedbase-table-705/generatedbasetemplatestable.mbin (exact 7.05, measured
# on the 2026-10-25 re-extraction and present in the logged 7.05 fingerprints as 74D66F13761E6DB7...).
GENERATEDBASE_MBIN_SHA256 = "74D66F13761E6DB71CD277772C346C9521EB7DE520AE9492B0202A0B47429EBE"

# GcGeneratedBaseDecorationTemplate.DecorationLayer -> the descriptor +0x40 integer (read from the MBIN).
DECORATION_LAYER_VALUES: Mapping[str, int] = {
    "Stairs": 0,
    "Corridor": 1,
    "Room": 2,
    "Door": 3,
    "Decoration1": 4,
    "Decoration2": 5,
    "Decoration3": 6,
    "DecorationCorridor": 7,
}
ORIENTATIONS_PER_TEMPLATE = 4
PIECE_MAP_DATA_SIZE = 600
PIECE_MAP_DIMS_OFFSET = 0x258
PIECE_MAP_ROW_SIZE = 0x2B0


def _strings(value: object) -> list[str]:
    """Ordered string list from a parsed MXML list (or a single value)."""
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        value = value.get("items", value.get("fields", []))
    return [str(item) for item in value if item is not None and str(item) != ""]


def _int_array(value: object) -> tuple[int, ...]:
    return tuple(int(item) for item in _strings(value))


def _float32(value: object) -> float:
    return struct.unpack("<f", struct.pack("<f", float(value)))[0]


@dataclass(frozen=True)
class DecorationSource:
    """One GcGeneratedBaseDecorationTemplate in exact MBIN table order."""

    table_index: int
    template_id: str
    key_pair: bytes
    decoration_layer: int
    max_per_room: int
    invalid_room_indexes: tuple[int, ...]
    probability: float
    scene_path: str
    scene_mxml: Path
    scene_mxml_sha256: str
    cell_c_marker_count: int
    cell_c_variant_count: int


@dataclass(frozen=True)
class SceneMapVariant:
    """One native 0x2B0 source row: template x orientation x CELL*C numerator."""

    map_index: int
    table_index: int
    template_id: str
    orientation: int
    cell_c_numerator: int
    cell_c_variant_count: int
    source: GeneratedPieceSourceMetadata
    scene_path: str
    scene_mxml: Path
    scene_mxml_sha256: str


@dataclass(frozen=True)
class A3BC0Group:
    """One deduplicated decoration ID of a room, with its matching source rows in table order."""

    decoration_id: str
    theme_ids: tuple[str, ...]
    source_row_indices: tuple[int, ...]

    def a3bc0_words(self) -> tuple[int, ...]:
        """Row indices as A3F00 appends them (u32 each). [G1: body reconstructed; no logged caller.]"""
        if any(not 0 <= index <= 0xFFFFFFFF for index in self.source_row_indices):
            raise ValueError("source-row index outside u32")
        return tuple(self.source_row_indices)

    def initialized_a2780_words(self) -> tuple[int, ...]:
        """A2780's per-group counter words start at zero. [G1: body reconstructed; no logged caller.]"""
        return tuple(0 for _ in self.source_row_indices)


# [G1 RECONSTRUCTED region ends; the original text resumes below (logged lines 140-410).]


@dataclass(frozen=True)
class MaterializedSceneMap:
    """A callback map plus its index/metadata sidecar.

    ``native_map_prefix`` contains exactly bytes [0, 0x25E) from the 0x2B0
    row: 600 map bytes and three u16 dimensions. Pointer-bearing transform
    metadata at +0x260 and the native source pointer at +0x2A0 remain sidecar
    fields rather than fabricated process addresses. ``native_map_row_for_fit``
    zero-fills that unmodeled tail because the bounded A3270/A23B0 ports read
    only the map and dimensions.
    """

    variant: SceneMapVariant
    native_map_prefix: bytes
    native_map_row_for_fit: bytes
    transform: object
    bounds_source: str
    callback_order_source: str
    row_tail_source: str


class GeneratedBaseSourceCatalog:
    """Direct-MXML candidate rows for the A3BC0/A3F00/A2780 lookup path."""

    def __init__(self, bundle: StaticBundle):
        self.bundle = bundle
        ordered_rows = list(bundle.decoration_rows.values())
        if len(ordered_rows) != 319:
            raise ValueError(f"expected 319 exact decoration records, got {len(ordered_rows)}")

        mbin_path = bundle.root / "research-output/generatedbase-table-705/generatedbasetemplatestable.mbin"
        mbin = mbin_path.read_bytes()
        if hashlib.sha256(mbin).hexdigest().upper() != GENERATEDBASE_MBIN_SHA256:
            raise ValueError("generated-base MBIN does not match exact 7.05 table fingerprint")
        mbin_ids = tuple(
            mbin[0x80 + index * 0x50:0x80 + index * 0x50 + 16].split(bytes([0]), 1)[0].decode("ascii")
            for index in range(len(ordered_rows))
        )
        mxml_ids = tuple(str(row["Id"]) for row in ordered_rows)
        if mxml_ids != mbin_ids:
            raise ValueError("generated-base MXML decoration order differs from exact MBIN table order")

        root = bundle.root / "research-output/exact705-generatedbase-scenes-20261019"
        sources: list[DecorationSource] = []
        for expected_index, row in enumerate(ordered_rows):
            table_index = expected_index
            template_id = str(row["Id"])
            layer_name = str(row["DecorationLayer"])
            if layer_name not in DECORATION_LAYER_VALUES:
                raise ValueError(f"unknown exact DecorationLayer {layer_name!r} on {template_id}")
            asset = bundle.scene_assets[template_id]
            if int(asset.get("table_index", -1)) != table_index:
                raise ValueError(f"scene manifest table index mismatch for {template_id}")
            scene_mxml = root / str(asset["mxml_relative_path"])
            if not scene_mxml.is_file():
                raise FileNotFoundError(f"scene MXML absent for {template_id}: {scene_mxml}")
            callback_nodes = load_scene_map_nodes(
                scene_mxml,
                expected_mxml_sha256=str(asset["mxml_sha256"]),
            )
            cell_c_marker_count = sum(
                str(node["name"]).startswith("CELLC") for node in callback_nodes
            )
            cell_c_variant_count = 1 << cell_c_marker_count
            sources.append(
                DecorationSource(
                    table_index=table_index,
                    template_id=template_id,
                    key_pair=native_room_key(template_id),
                    decoration_layer=DECORATION_LAYER_VALUES[layer_name],
                    max_per_room=int(row["MaxPerRoom"]),
                    invalid_room_indexes=_int_array(row.get("InvalidRoomIndexes")),
                    probability=_float32(row["Probability"]),
                    scene_path=str(asset["resource_path"]),
                    scene_mxml=scene_mxml,
                    scene_mxml_sha256=str(asset["mxml_sha256"]),
                    cell_c_marker_count=cell_c_marker_count,
                    cell_c_variant_count=cell_c_variant_count,
                )
            )
        self.sources = tuple(sources)

        variants: list[SceneMapVariant] = []
        variants_by_id: dict[str, list[SceneMapVariant]] = {}
        map_index = 0
        for source in self.sources:
            for orientation in range(ORIENTATIONS_PER_TEMPLATE):
                for numerator in range(source.cell_c_variant_count):
                    metadata = GeneratedPieceSourceMetadata(
                        row_index=map_index,
                        key_pair=source.key_pair,
                        decoration_layer=source.decoration_layer,
                        max_per_room=source.max_per_room,
                        invalid_room_indexes=source.invalid_room_indexes,
                        probability=source.probability,
                    )
                    variant = SceneMapVariant(
                        map_index=map_index,
                        table_index=source.table_index,
                        template_id=source.template_id,
                        orientation=orientation,
                        cell_c_numerator=numerator,
                        cell_c_variant_count=source.cell_c_variant_count,
                        source=metadata,
                        scene_path=source.scene_path,
                        scene_mxml=source.scene_mxml,
                        scene_mxml_sha256=source.scene_mxml_sha256,
                    )
                    variants.append(variant)
                    variants_by_id.setdefault(source.template_id, []).append(variant)
                    map_index += 1
        self.variants = tuple(variants)
        self.rows_by_id: dict[str, tuple[SceneMapVariant, ...]] = {}
        rows_by_key: dict[bytes, list[SceneMapVariant]] = {}
        for source in self.sources:
            source_variants = tuple(variants_by_id[source.template_id])
            self.rows_by_id[source.template_id] = source_variants
            rows_by_key.setdefault(source.key_pair, []).extend(source_variants)
        self.rows_by_key = {key: tuple(rows) for key, rows in rows_by_key.items()}

    @classmethod
    def from_workspace(cls, root: Path | None = None) -> "GeneratedBaseSourceCatalog":
        return cls(load_static_bundle(root))

    def a3bc0_groups(self, room_id: str, layer: int) -> tuple[A3BC0Group, ...]:
        """Expand the room's ordered themes to A3F00 source-row groups.

        A3BC0 looks up the room template, walks its DecorationThemes in order,
        expands each theme's DecorationTemplates in order, deduplicates the
        16-byte decoration IDs across themes, and calls A3F00 for that ID and
        layer. A3F00 scans the native map-row table in order and returns only
        rows whose source metadata ID and layer match. Missing IDs and IDs with
        no rows in this layer both produce no output group.
        """
        if not 0 <= layer < 8:
            raise ValueError("A3BC0 layer must be in the native range 0..7")
        room = self.bundle.room_rows.get(room_id)
        if room is None:
            raise ValueError(f"no exact GeneratedBaseRoomTemplate for {room_id}")

        ordered_theme_ids = _strings(room.get("DecorationThemes", []))
        decoration_order: list[bytes] = []
        decoration_id_by_key: dict[bytes, str] = {}
        theme_by_decoration: dict[bytes, list[str]] = {}
        seen_decoration_keys: set[bytes] = set()
        for theme_id in ordered_theme_ids:
            theme = self.bundle.theme_rows.get(theme_id)
            if theme is None:
                raise ValueError(f"room {room_id} references missing theme {theme_id}")
            for decoration_id in _strings(theme.get("DecorationTemplates", [])):
                decoration_key = native_room_key(decoration_id)
                if decoration_key in seen_decoration_keys:
                    if theme_id not in theme_by_decoration[decoration_key]:
                        theme_by_decoration[decoration_key].append(theme_id)
                    continue
                seen_decoration_keys.add(decoration_key)
                decoration_order.append(decoration_key)
                decoration_id_by_key[decoration_key] = decoration_id
                theme_by_decoration[decoration_key] = [theme_id]

        groups: list[A3BC0Group] = []
        for decoration_key in decoration_order:
            candidates = self.rows_by_key.get(decoration_key, ())
            source_rows = tuple(
                variant.map_index
                for variant in candidates
                if variant.source.decoration_layer == layer
            )
            if source_rows:
                groups.append(
                    A3BC0Group(
                        decoration_id=decoration_id_by_key[decoration_key],
                        theme_ids=tuple(theme_by_decoration[decoration_key]),
                        source_row_indices=source_rows,
                    )
                )
        return tuple(groups)

    def source_metadata(self) -> tuple[GeneratedPieceSourceMetadata, ...]:
        """Return the candidate A3F00 rows in template/orientation/C order."""
        return tuple(variant.source for variant in self.variants)

    def materialize_scene_map(
        self,
        map_index: int,
        *,
        cell_c_numerator: int | None = None,
        manager_visitor_low_bounds: tuple[float, float, float] | None = None,
        callback_node_order: Sequence[tuple[int, ...]] | None = None,
    ) -> MaterializedSceneMap:
        """Build one 0x2B0 row prefix with explicit uncertain map inputs.

        Orientation zero first establishes the scene's authored callback map
        dimensions. The native writer expands each source template in table
        order, then orientation order, with a row for each CELL*C selector
        numerator. It uses the corresponding orientation-zero extents to
        offset rotated roots. The low bound and any special callback order
        remain caller supplied/evidence-labelled inputs.
        """
        try:
            from scene_callback_matrix_705 import build_scene_piece_map
        except ImportError:  # pragma: no cover - package-style use
            from .scene_callback_matrix_705 import build_scene_piece_map

        if not 0 <= map_index < len(self.variants):
            raise IndexError(f"map index {map_index} outside {len(self.variants)} native rows")
        variant = self.variants[map_index]
        if cell_c_numerator is None:
            cell_c_numerator = variant.cell_c_numerator
        if not 0 <= cell_c_numerator < variant.cell_c_variant_count:
            raise ValueError(
                f"CELL*C numerator {cell_c_numerator} outside the direct-scene range "
                f"0..{variant.cell_c_variant_count - 1} for {variant.template_id}"
            )
        base_map = build_scene_piece_map(
            variant.scene_mxml,
            orientation=0,
            extent_dimensions=(0, 0, 0),
            decoration_layer=variant.source.decoration_layer,
            cell_c_numerator=cell_c_numerator,
            manager_visitor_low_bounds=manager_visitor_low_bounds,
            callback_node_order=callback_node_order,
            expected_mxml_sha256=variant.scene_mxml_sha256,
        )
        result = base_map
        if variant.orientation != 0:
            result = build_scene_piece_map(
                variant.scene_mxml,
                orientation=variant.orientation,
                extent_dimensions=base_map.dimensions,
                decoration_layer=variant.source.decoration_layer,
                cell_c_numerator=cell_c_numerator,
                manager_visitor_low_bounds=manager_visitor_low_bounds,
                callback_node_order=callback_node_order,
                expected_mxml_sha256=variant.scene_mxml_sha256,
            )

        prefix = bytearray(PIECE_MAP_DIMS_OFFSET + 6)
        prefix[:PIECE_MAP_DATA_SIZE] = result.raw_map
        struct.pack_into("<HHH", prefix, PIECE_MAP_DIMS_OFFSET, *result.dimensions)
        if len(prefix) != 0x25E:
            raise AssertionError("native map prefix must end after the three u16 dimensions")
        row = bytearray(PIECE_MAP_ROW_SIZE)
        row[:len(prefix)] = prefix
        return MaterializedSceneMap(
            variant=variant,
            native_map_prefix=bytes(prefix),
            native_map_row_for_fit=bytes(row),
            transform=result.matrix,
            bounds_source=result.callback_bounds_source,
            callback_order_source=result.callback_order_source,
            row_tail_source="zero-filled adapter; native transform metadata/source pointer are not modeled",
        )


__all__ = [
    "A3BC0Group",
    "DECORATION_LAYER_VALUES",
    "DecorationSource",
    "GENERATEDBASE_MBIN_SHA256",
    "GeneratedBaseSourceCatalog",
    "MaterializedSceneMap",
    "ORIENTATIONS_PER_TEMPLATE",
    "PIECE_MAP_DATA_SIZE",
    "PIECE_MAP_DIMS_OFFSET",
    "PIECE_MAP_ROW_SIZE",
    "SceneMapVariant",
]
