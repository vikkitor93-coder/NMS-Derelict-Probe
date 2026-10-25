"""Offline A4720 instance transforms and authored container positions.

The source-row transform comes from the callback map materializer; A4720 adds
the 8-unit grid offset. Descriptor byte +0x0E identifies its logical room, and
byte +0x04 identifies the source row/template. Container reference positions
are read from the exact generated-base scene index and transformed by that
instance matrix.

The returned transforms retain the source map's bounds/order provenance. If
the caller used authored AABB or callback-order candidates, the result is a
candidate placement, not an exact runtime claim.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

try:  # direct module use with this directory on sys.path
    from nms_dungeon_a2780_search_705 import A2780Placement
    from nms_dungeon_source_catalog_705 import GeneratedBaseSourceCatalog, MaterializedSceneMap
except ImportError:  # pragma: no cover - package-style use
    from .nms_dungeon_a2780_search_705 import A2780Placement
    from .nms_dungeon_source_catalog_705 import GeneratedBaseSourceCatalog, MaterializedSceneMap


NMS_EXE_SHA256 = "13D5060D4EFB9D2A6A6B1B349BC4257231056CC2A055DF4BB15D816262CC3499"
GRID_SPACING = 8.0


def _f32(value: float) -> float:
    import struct

    return struct.unpack("<f", struct.pack("<f", value))[0]


def _add32(left: float, right: float) -> float:
    return _f32(_f32(left) + _f32(right))


@dataclass(frozen=True)
class SceneInstanceTransform:
    """One A4720-style scene instance in layout-local coordinates."""

    room_index: int
    source_map_index: int
    template_id: str
    scene_resource: str
    origin_xyz: tuple[int, int, int]
    source_axes: tuple[tuple[float, float, float], ...]
    source_translation: tuple[float, float, float]
    grid_translation: tuple[float, float, float]
    translation: tuple[float, float, float]
    bounds_source: str
    callback_order_source: str

    def transform_point(self, local_xyz: Sequence[float]) -> tuple[float, float, float]:
        """Transform one authored scene-local point into layout-local space."""
        if len(local_xyz) != 3:
            raise ValueError("local_xyz must be an XYZ triple")
        x, y, z = (_f32(float(value)) for value in local_xyz)
        point: list[float] = []
        for column in range(3):
            y_term = _f32(y * self.source_axes[1][column])
            x_term = _f32(x * self.source_axes[0][column])
            z_term = _f32(z * self.source_axes[2][column])
            value = _add32(y_term, x_term)
            value = _add32(value, z_term)
            value = _add32(value, self.translation[column])
            point.append(value)
        return tuple(point)

    @property
    def transform_basis(self) -> dict[str, dict[str, float]]:
        """Expose the replay's right/up/at/pos transform shape."""
        axes = self.source_axes
        return {
            "right": {axis: axes[0][index] for index, axis in enumerate(("x", "y", "z"))},
            "up": {axis: axes[1][index] for index, axis in enumerate(("x", "y", "z"))},
            "at": {axis: axes[2][index] for index, axis in enumerate(("x", "y", "z"))},
            "pos": {axis: self.translation[index] for index, axis in enumerate(("x", "y", "z"))},
        }


@dataclass(frozen=True)
class ContainerInstancePlacement:
    """One authored crate/footlocker reference after A4720's instance transform."""

    room_index: int
    source_map_index: int
    template_id: str
    scene_resource: str
    scene_node_name: str
    container_kind: str
    target_scene_resource: str
    local_xyz: tuple[float, float, float]
    layout_local_xyz: tuple[float, float, float]


def _grid_translation(
    origin_xyz: tuple[int, int, int],
    grid_origin_xyz: tuple[int, int, int],
) -> tuple[float, float, float]:
    if len(origin_xyz) != 3 or len(grid_origin_xyz) != 3:
        raise ValueError("grid origins must be XYZ triples")
    # A4720 places the 5x3x5 scene lattice around the context origin.
    constants = (-4, -2, -4)
    result = []
    for coordinate, origin, center in zip(origin_xyz, grid_origin_xyz, constants, strict=True):
        offset_cells = int(coordinate) - int(origin) + center
        result.append(_f32(float(offset_cells * GRID_SPACING)))
    return tuple(result)


def build_scene_instance_transforms(
    placements: Sequence[A2780Placement],
    *,
    catalog: GeneratedBaseSourceCatalog,
    grid_origin_xyz: tuple[int, int, int],
    manager_visitor_low_bounds_by_template: Mapping[str, tuple[float, float, float]] | None = None,
    callback_node_order_by_template: Mapping[str, Sequence[tuple[int, ...]]] | None = None,
    materialized_maps: dict[int, MaterializedSceneMap] | None = None,
) -> tuple[SceneInstanceTransform, ...]:
    """Resolve accepted A2780 descriptors into A4720 scene-instance transforms.

    Exact-build startup initializes A4720's three rotation-angle globals to
    zero, so the global A4720 rotation is identity. The callback-built source
    row still supplies the orientation matrix and translation for its selected
    map variant. ``grid_origin_xyz`` is the native generator-context origin
    read at +0x50/+0x54/+0x58; for the standard preset path it is the explicit
    EntranceX/Y/Z tuple from DungeonParams.
    """
    bounds_by_template = manager_visitor_low_bounds_by_template or {}
    order_by_template = callback_node_order_by_template or {}
    cache = materialized_maps if materialized_maps is not None else {}
    results: list[SceneInstanceTransform] = []

    for placement in placements:
        placement_origin = placement.record.origin_xyz
        map_index = placement.source_map_index
        materialized = cache.get(map_index)
        if materialized is None:
            variant = catalog.variants[map_index]
            materialized = catalog.materialize_scene_map(
                map_index,
                manager_visitor_low_bounds=bounds_by_template.get(variant.template_id),
                callback_node_order=order_by_template.get(variant.template_id),
            )
            cache[map_index] = materialized

        matrix = materialized.transform
        axes = tuple(tuple(_f32(value) for value in row) for row in matrix.axes)
        source_translation = tuple(_f32(value) for value in matrix.translation)
        grid_delta = _grid_translation(placement_origin, grid_origin_xyz)
        translation = tuple(
            _add32(source_translation[axis], grid_delta[axis])
            for axis in range(3)
        )
        results.append(
            SceneInstanceTransform(
                room_index=placement.room_index,
                source_map_index=map_index,
                template_id=materialized.variant.template_id,
                scene_resource=materialized.variant.scene_path.replace("\\", "/").upper(),
                origin_xyz=placement_origin,
                source_axes=axes,
                source_translation=source_translation,
                grid_translation=grid_delta,
                translation=translation,
                bounds_source=materialized.bounds_source,
                callback_order_source=materialized.callback_order_source,
            )
        )

    return tuple(results)


def transform_authored_containers(
    instances: Sequence[SceneInstanceTransform],
    *,
    container_index_csv: Path,
) -> tuple[ContainerInstancePlacement, ...]:
    """Apply each selected scene transform to its indexed direct containers.

    The index records the exact generated-base scene node path and its authored
    transform. Relevant fixture container references are direct children of
    identity roots. If a selected scene requires ancestor composition, this
    bounded function fails closed instead of treating that node-local point as
    a root-local position.
    """
    by_scene: dict[str, list[dict[str, str]]] = {}
    with container_index_csv.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            kind = row.get("container_kind", "")
            if kind not in ("salvage_crate", "crew_footlocker"):
                continue
            scene = row.get("scene_resource", "").replace("\\", "/").upper()
            by_scene.setdefault(scene, []).append(row)

    output: list[ContainerInstancePlacement] = []
    for instance in instances:
        for row in by_scene.get(instance.scene_resource, ()):
            if row.get("hierarchy_needs_composition", "").strip().lower() == "true":
                raise NotImplementedError(
                    f"container {row.get('scene_node_name')} in {instance.template_id} "
                    "requires ancestor-transform composition"
                )
            local = (
                float(row["direct_local_x"]),
                float(row["direct_local_y"]),
                float(row["direct_local_z"]),
            )
            output.append(
                ContainerInstancePlacement(
                    room_index=instance.room_index,
                    source_map_index=instance.source_map_index,
                    template_id=instance.template_id,
                    scene_resource=instance.scene_resource,
                    scene_node_name=row["scene_node_name"],
                    container_kind=row["container_kind"],
                    target_scene_resource=row["target_scene_resource"],
                    local_xyz=local,
                    layout_local_xyz=instance.transform_point(local),
                )
            )
    return tuple(output)


PORT_STATUS = {
    "FUN_1403A4720": "source-row matrix plus native eight-unit grid translation composed over explicit accepted A2780 descriptors; startup-global rotation is identity",
    "authored crate/footlocker instances": "direct identity-root scene references transformed by their selected map-instance matrix; nested ancestry fails closed",
    "input limits": "exact row metadata/transform tails and manager visitor low bounds are represented by the scene catalog sidecar; authored AABB fallback remains a labeled candidate",
}


__all__ = [
    "ContainerInstancePlacement",
    "SceneInstanceTransform",
    "build_scene_instance_transforms",
    "transform_authored_containers",
    "PORT_STATUS",
]
