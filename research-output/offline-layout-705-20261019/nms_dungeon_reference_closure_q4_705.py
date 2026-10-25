# [G1 2026-10-25] Final version from logged cat (a772d1f0 L44, 2026-10-20 01:28), i.e. with the a10afc4c L334 rotation-guard patch that the working-tree copy lacks. Only this comment line is new.
"""Q4 fix: reference-aware callback-map provider for the NMS 7.05 offline port.

The original provider (`scene_callback_matrix_705._scene_nodes` and
`nms_dungeon_offline.load_scene_map_nodes`) walks only each root scene MXML.
For 243 of the 319 generated-base templates every CELL/NOCELL/PATH/LAYER node
lives in a REFERENCE'd scene (e.g. ROOM_INCORNER_3 -> EMPTY/ROOM_INCORNER), so
those 1,068 of 1,292 rows came out with an all-zero map and (0,0,0) dimensions.
A3270 accepts such rows at every origin and A5480 writes nothing, so A2780 kept
placing them until each group's MaxPerRoom (100) was reached.

This module follows SCENEGRAPH references recursively, in manager preorder
(the referenced subtree appears at the REFERENCE node's child position, as in
the FUN_1418E3660 recursive import), composing parent translations. Every
reference edge reaching a callback tag in the exact 7.05 closure has identity
rotation and scale (checked at load time; anything else fails closed).

It does not edit the original modules. `Q4SourceCatalog` subclasses the
original catalog: CELL*C marker counts (row expansion) and materialized maps
both use the recursive node list. Everything downstream (writer search, A2780,
A3270, A5480, instance chain) is unchanged.

Assumption carried, not proven statically: the importer gates
(source type 3, manager +0x14448, reference +0x2C1 bit) are active in the
writer's scene-load context. See Q4_PLACEMENT_COUNT_20261020.md.
"""

from __future__ import annotations

import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Sequence

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import nms_dungeon_source_catalog_705 as base_catalog  # noqa: E402
import scene_callback_matrix_705 as scm  # noqa: E402
from row_tag_codec import RowTagContext, encode_node_tag, lookup_layer_bytes  # noqa: E402

CLOSURE_DIR = HERE / "q4-reference-closure-20261020"
CLOSURE_MANIFEST = CLOSURE_DIR / "reference_closure_manifest.json"


def _norm(resource: str) -> str:
    return resource.replace("\\", "/").strip("/").upper()


def _attrs_upper(node: ET.Element) -> dict[str, str]:
    return {k.upper(): v for k, v in scm._attribute_values(node).items()}


def _trs(node: ET.Element) -> tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]:
    t = scm._first(node, "Transform")
    if t is None:
        return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (1.0, 1.0, 1.0)
    f = scm._float_property
    return (
        tuple(f(t, k, 0.0) for k in ("TransX", "TransY", "TransZ")),
        tuple(f(t, k, 0.0) for k in ("RotX", "RotY", "RotZ")),
        tuple(f(t, k, 1.0) for k in ("ScaleX", "ScaleY", "ScaleZ")),
    )


class SceneResolver:
    """Maps normalized SCENE.MBIN resource paths to extracted MXML files."""

    def __init__(self, catalog_sources: Sequence[Any]):
        self.paths: dict[str, Path] = {}
        for source in catalog_sources:
            self.paths[_norm(source.scene_path)] = Path(source.scene_mxml)
        manifest = json.loads(CLOSURE_MANIFEST.read_text(encoding="utf-8"))
        for resource, record in manifest["targets"].items():
            if record.get("missing_from_archive"):
                continue
            path = CLOSURE_DIR / record["mxml_relative_path"]
            digest = hashlib.sha256(path.read_bytes()).hexdigest().upper()
            if digest != record["mxml_sha256"]:
                raise ValueError(f"closure MXML hash mismatch: {path}")
            self.paths.setdefault(_norm(resource), path)
        self._cache: dict[str, list[dict[str, Any]]] = {}

    def nodes(self, scene_mxml: Path) -> list[dict[str, Any]]:
        key = str(Path(scene_mxml).resolve())
        if key not in self._cache:
            self._cache[key] = recursive_scene_nodes(Path(scene_mxml), self)
        return self._cache[key]


def recursive_scene_nodes(scene_mxml: Path, resolver: SceneResolver) -> list[dict[str, Any]]:
    """Callback-tag nodes in manager preorder, including referenced scenes."""
    result: list[dict[str, Any]] = []

    def walk_scene(path: Path, offset: tuple[float, float, float], path_prefix: tuple, stack: tuple[str, ...]) -> None:
        root = ET.parse(path).getroot()
        scm._root_is_identity(root, path)
        for index, child in enumerate(scm._children_nodes(root)):
            walk(child, offset, path_prefix + (index,), stack)

    def walk(node: ET.Element, parent_offset: tuple[float, float, float], path: tuple, stack: tuple[str, ...]) -> None:
        trans, rot, scale = _trs(node)
        name = scm._node_name(node)
        world = tuple(scm._add32(parent_offset[i], trans[i]) for i in range(3))
        if name.startswith(scm.MAP_PREFIXES):
            result.append({
                "name": name,
                "path": path,
                "position": world,
                "attributes": scm._attribute_values(node),
                "has_authored_transform": scm._first(node, "Transform") is not None,
                "via_reference": len(stack) > 1,
            })
        children = scm._children_nodes(node)
        target = _attrs_upper(node).get("SCENEGRAPH", "")
        nonidentity = rot != (0.0, 0.0, 0.0) or scale != (1.0, 1.0, 1.0)
        tags_before = len(result)
        for index, child in enumerate(children):
            walk(child, world, path + (index,), stack)
        if target.upper().endswith(".SCENE.MBIN"):
            resource = _norm(target)
            if resource in stack:
                raise ValueError(f"reference cycle at {resource}")
            target_path = resolver.paths.get(resource)
            if target_path is None:
                raise FileNotFoundError(f"referenced scene not extracted: {resource}")
            walk_scene(target_path, world, path + ("ref",), stack + (resource,))
        if nonidentity and len(result) > tags_before:
            raise NotImplementedError(f"callback tags under non-identity rotation/scale need matrix composition: {scene_mxml} {path} {name}")

    walk_scene(scene_mxml, (0.0, 0.0, 0.0), (), (_norm(str(scene_mxml)),))
    return result


def _bounds_min(nodes: Sequence[dict[str, Any]]) -> tuple[float, float, float]:
    """Same authored-AABB candidate as the original, over the recursive node set."""
    low = [0.0, 0.0, 0.0]
    for node in nodes:
        if not node["name"].startswith(scm.BOUNDS_PREFIXES):
            continue
        attrs = node["attributes"]
        mins = [scm._f32(float(attrs[f"AABBMIN{axis}"])) for axis in "XYZ"]
        world_min = tuple(scm._add32(mins[i], node["position"][i]) for i in range(3))
        low = [min(low[i], world_min[i]) for i in range(3)]
    return tuple(scm._f32(v) for v in low)


def build_scene_piece_map_q4(
    scene_mxml: Path,
    resolver: SceneResolver,
    *,
    orientation: int,
    extent_dimensions: tuple[int, int, int],
    decoration_layer: int,
    cell_c_numerator: int,
    manager_visitor_low_bounds: tuple[float, float, float] | None = None,
) -> scm.SceneMapResult:
    """Copy of scm.build_scene_piece_map's write loop over recursive nodes."""
    nodes = resolver.nodes(scene_mxml)
    if manager_visitor_low_bounds is None:
        bounds_min = _bounds_min(nodes)
        bounds_source = "authored-mxml-candidate incl. referenced scenes; local-bounds writer unresolved"
    else:
        bounds_min = tuple(scm._f32(v) for v in manager_visitor_low_bounds)
        bounds_source = "caller-supplied engine-manager visitor low bound"
    matrix = scm.build_scene_callback_matrix(bounds_min, orientation=orientation, extent_dimensions=extent_dimensions)
    layer_a, layer_b, layer_c = lookup_layer_bytes(decoration_layer)
    raw_map = bytearray(scm.MAP_BYTES)
    dimensions = [0, 0, 0]
    divisor = 1
    rows = []
    for node in nodes:
        coordinate = scm.quantize_callback_position(matrix.transform_point(node["position"]))
        if coordinate is None:
            continue
        offset = coordinate["byte_offset"]
        before = bytes(raw_map[offset:offset + scm.CELL_BYTES])
        encoded = encode_node_tag(node["name"], before, context=RowTagContext(
            layer_a=layer_a, layer_b=layer_b, layer_c=layer_c,
            cell_c_numerator=cell_c_numerator, cell_c_divisor=divisor,
            decoration_layer=decoration_layer, orientation=orientation))
        raw_map[offset:offset + scm.CELL_BYTES] = encoded.cell_bytes
        divisor = encoded.next_cell_c_divisor
        if encoded.grows_dimensions:
            dimensions[0] = max(dimensions[0], coordinate["x"] + 1)
            dimensions[1] = max(dimensions[1], coordinate["y"] + 1)
            dimensions[2] = max(dimensions[2], coordinate["z"] + 1)
        rows.append({"name": node["name"], "cell": coordinate, "via_reference": node["via_reference"]})
    return scm.SceneMapResult(
        raw_map=bytes(raw_map), dimensions=tuple(dimensions), final_cell_c_divisor=divisor,
        matrix=matrix, callback_bounds_min=bounds_min, callback_bounds_source=bounds_source,
        callback_order_source="manager preorder incl. recursive REFERENCE imports (Q4 assumption: gates active)",
        callback_order_is_explicit=False, callback_nodes=tuple(rows))


class Q4SourceCatalog(base_catalog.GeneratedBaseSourceCatalog):
    """Original catalog with reference-aware CELL*C counting and map rows."""

    def __init__(self, bundle):
        original = base_catalog.load_scene_map_nodes
        holder: dict[str, SceneResolver] = {}

        def recursive_loader(scene_mxml, *, expected_mxml_sha256=None, **_):
            if expected_mxml_sha256 is not None:
                digest = hashlib.sha256(Path(scene_mxml).read_bytes()).hexdigest().upper()
                if digest != expected_mxml_sha256.upper():
                    raise ValueError(f"scene MXML hash mismatch: {scene_mxml}")
            return holder["resolver"].nodes(Path(scene_mxml))

        class _Src:  # resolver needs root scene paths before sources exist
            def __init__(self, scene_path, scene_mxml):
                self.scene_path, self.scene_mxml = scene_path, scene_mxml

        root = bundle.root / "research-output/exact705-generatedbase-scenes-20261019"
        holder["resolver"] = SceneResolver([
            _Src(str(asset["resource_path"]), root / str(asset["mxml_relative_path"]))
            for asset in bundle.scene_assets.values()
        ])
        base_catalog.load_scene_map_nodes = recursive_loader
        try:
            super().__init__(bundle)
        finally:
            base_catalog.load_scene_map_nodes = original
        self.resolver = holder["resolver"]

    def materialize_scene_map(self, map_index, *, cell_c_numerator=None,
                              manager_visitor_low_bounds=None, callback_node_order=None):
        if callback_node_order is not None:
            raise NotImplementedError("explicit callback order is not supported by the Q4 provider")
        variant = self.variants[map_index]
        numerator = variant.cell_c_numerator if cell_c_numerator is None else cell_c_numerator
        kwargs = dict(decoration_layer=variant.source.decoration_layer, cell_c_numerator=numerator,
                      manager_visitor_low_bounds=manager_visitor_low_bounds)
        result = build_scene_piece_map_q4(variant.scene_mxml, self.resolver, orientation=0,
                                          extent_dimensions=(0, 0, 0), **kwargs)
        if variant.orientation:
            result = build_scene_piece_map_q4(variant.scene_mxml, self.resolver, orientation=variant.orientation,
                                              extent_dimensions=result.dimensions, **kwargs)
        import struct
        prefix = bytearray(base_catalog.PIECE_MAP_DIMS_OFFSET + 6)
        prefix[:base_catalog.PIECE_MAP_DATA_SIZE] = result.raw_map
        struct.pack_into("<HHH", prefix, base_catalog.PIECE_MAP_DIMS_OFFSET, *result.dimensions)
        row = bytearray(base_catalog.PIECE_MAP_ROW_SIZE)
        row[:len(prefix)] = prefix
        return base_catalog.MaterializedSceneMap(
            variant=variant, native_map_prefix=bytes(prefix), native_map_row_for_fit=bytes(row),
            transform=result.matrix, bounds_source=result.callback_bounds_source,
            callback_order_source=result.callback_order_source,
            row_tail_source="zero-filled adapter; native transform metadata/source pointer are not modeled")
