# [G1 2026-10-25] Fully recovered from logged tool output (no reconstructed lines): lines 1-120 sed a10afc4c L228, 120-160 sed a10afc4c L273, 160-546 sed a10afc4c L235. Only this comment line is new.
"""Static NMS 7.05 room-scene transform and map-callback adapter.

This module reconstructs one selected generated-base scene's callback map
when the upstream caller supplies its orientation, extent dimensions,
DecorationLayer, and current CELL*C numerator. It does not generate the room
graph or choose a scene. The initial transform basis is the exact 7.05 startup
initializer state documented in ROOM_MAP_CALLBACK_CONTEXT_20261019.md.

The returned raw_map is exactly 600 bytes (75 eight-byte cells). The three
u16 dimensions are returned separately, matching offsets +0x258/+0x25A/+0x25C.
"""

from __future__ import annotations

import hashlib
import math
import struct
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


_CODEC_DIR = Path(__file__).resolve().parents[1] / "offline-generator-assessment-20261019"
if str(_CODEC_DIR) not in sys.path:
    sys.path.insert(0, str(_CODEC_DIR))

from row_tag_codec import RowTagContext, encode_node_tag, lookup_layer_bytes  # noqa: E402


NMS_EXE_SHA256 = "13D5060D4EFB9D2A6A6B1B349BC4257231056CC2A055DF4BB15D816262CC3499"
MAP_BYTES = 600
CELL_BYTES = 8
GRID_DIMS = (5, 3, 5)
GRID_SPACING = (8.0, 8.0, 8.0)
MAP_PREFIXES = ("CELL", "NOCELL", "PATH", "LAYER")
BOUNDS_PREFIXES = ("CELL", "NOCELL")

# The raw initializer sequence is:
#   0x1400313C0: load 0x144B32300, store 0x14720BF80 (east)
#   0x1400313D0: load 0x144B32420, store 0x14720BC00 (north)
#   0x1400313E0: load 0x144B32960, store 0x14720BF10 (up)
#   0x140031340: load 0x144B32280, store 0x14720BD50 (origin)
# Each source and destination is a 16-byte float4. Their exact values are
# (1,0,0,1), (0,1,0,1), (0,0,1,1), and (0,0,0,1), respectively.
INITIAL_MATRIX_ROWS: tuple[tuple[float, float, float, float], ...] = (
    (1.0, 0.0, 0.0, 1.0),
    (0.0, 1.0, 0.0, 1.0),
    (0.0, 0.0, 1.0, 1.0),
    (0.0, 0.0, 0.0, 1.0),
)

# Exact constants read by the x86 scalar trig helpers and matrix writer.
_PI = 3.1415927410125732  # 0x144B29B34
_NEG_PI = -3.1415927410125732  # 0x144B2A184
_PI_OVER_2 = 1.5707963705062866  # 0x144B29950
_NEG_PI_OVER_2 = -1.5707963705062866  # 0x144B2A158
_TWO_PI = 6.2831854820251465  # 0x144B29C28
_INV_TWO_PI = 0.15915493667125702  # 0x144B285F4
_HALF = 0.5  # 0x144B29308


def _f32(value: float) -> float:
    """Round one operation result to the native scalar float width."""
    return struct.unpack("<f", struct.pack("<f", float(value)))[0]


def _add32(left: float, right: float) -> float:
    return _f32(_f32(left) + _f32(right))


def _sub32(left: float, right: float) -> float:
    return _f32(_f32(left) - _f32(right))


def _mul32(left: float, right: float) -> float:
    return _f32(_f32(left) * _f32(right))


def _round_angle_native(angle: float) -> float:
    """Mirror the shared x86 helper's nearest-turn reduction prelude."""
    angle = _f32(angle)
    turns = _mul32(angle, _INV_TWO_PI)
    turns = _add32(turns, _HALF) if angle >= 0.0 else _sub32(turns, _HALF)
    turns_i = int(turns)  # CVTTSS2SI: truncate toward zero.
    return _sub32(angle, _mul32(float(turns_i), _TWO_PI))


def _native_cos(angle: float) -> float:
    """Mirror the scalar polynomial at 0x140206D80, instruction for instruction."""
    x = _round_angle_native(angle)
    sign = 1.0
    if x > _PI_OVER_2:
        x = _sub32(_PI, x)
        sign = -1.0
    elif x < _NEG_PI_OVER_2:
        x = _sub32(_NEG_PI, x)
        sign = -1.0

    x2 = _mul32(x, x)
    p = _sub32(2.47604948526714e-5, _mul32(x2, 2.605161455448979e-7))
    p = _mul32(p, x2)
    p = _sub32(p, 0.0013888378161936998)
    p = _mul32(p, x2)
    p = _add32(p, 0.04166663810610771)
    p = _mul32(p, x2)
    p = _sub32(p, _HALF)
    p = _mul32(p, x2)
    p = _add32(p, 1.0)
    return _mul32(p, sign)


def _native_sin(angle: float) -> float:
    """Mirror the scalar polynomial at 0x140206E60, instruction for instruction."""
    x = _round_angle_native(angle)
    if x > _PI_OVER_2:
        x = _sub32(_PI, x)
    elif x < _NEG_PI_OVER_2:
        x = _sub32(_NEG_PI, x)

    x2 = _mul32(x, x)
    p = _sub32(2.752155751295504e-6, _mul32(x2, 2.3828544470916313e-8))
    p = _mul32(p, x2)
    p = _sub32(p, 0.00019840782624669373)
    p = _mul32(p, x2)
    p = _add32(p, 0.008333330042660236)
    p = _mul32(p, x2)
    p = _sub32(p, 0.1666666716337204)
    p = _mul32(p, x2)
    p = _add32(p, 1.0)
    return _mul32(p, x)


def native_sin_cos_for_orientation(orientation: int) -> tuple[float, float]:
    """Return 7.05's scalar-helper sin/cos for orientation * pi/2."""
    if orientation not in (0, 1, 2, 3):
        raise ValueError("orientation must be 0, 1, 2, or 3")
    if orientation == 0:
        # FUN_14039EC00 skips both trig calls for orientation zero.
        return 0.0, 1.0
    angle = _mul32(float(orientation), _PI_OVER_2)
    # Native call order is cosine (0x140206D80), then sine (0x140206E60).
    cosine = _native_cos(angle)
    sine = _native_sin(angle)
    return sine, cosine


def _property_children(node: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in list(node) if child.tag == "Property" and child.get("name") == name]


def _first(node: ET.Element, name: str) -> ET.Element | None:
    matches = _property_children(node, name)
    return matches[0] if matches else None


def _float_property(node: ET.Element, name: str, default: float | None = None) -> float:
    item = _first(node, name)
    if item is None:
        if default is None:
            raise ValueError(f"missing required float property {name}")
        return _f32(default)
    value = item.get("value")
    if value is None:
        raise ValueError(f"float property {name} has no value")
    return _f32(float(value))


def _node_translation(node: ET.Element) -> tuple[float, float, float]:
    transform = _first(node, "Transform")
    if transform is None:
        return (0.0, 0.0, 0.0)
    return tuple(_float_property(transform, key, 0.0) for key in ("TransX", "TransY", "TransZ"))


def _root_is_identity(root: ET.Element, scene_mxml: Path) -> None:
    transform = _first(root, "Transform")
    if transform is None:
        return
    translation = tuple(_float_property(transform, key, 0.0) for key in ("TransX", "TransY", "TransZ"))
    rotation = tuple(_float_property(transform, key, 0.0) for key in ("RotX", "RotY", "RotZ"))
    scale = tuple(_float_property(transform, key, 1.0) for key in ("ScaleX", "ScaleY", "ScaleZ"))
    if translation != (0.0, 0.0, 0.0) or rotation != (0.0, 0.0, 0.0) or scale != (1.0, 1.0, 1.0):
        raise ValueError(f"scene root is not identity; unsupported root composition: {scene_mxml}")


def _children_nodes(node: ET.Element) -> list[ET.Element]:
    container = _first(node, "Children")
    if container is None:
        return []
    return [
        child
        for child in list(container)
        if child.tag == "Property" and child.get("value") == "TkSceneNodeData"
    ]


def _node_name(node: ET.Element) -> str:
    name = _first(node, "Name")
    return name.get("value", "") if name is not None else ""


def _attribute_values(node: ET.Element) -> dict[str, str]:
    result: dict[str, str] = {}
    for container in _property_children(node, "Attributes"):
        # Converted scene MXML stores TkSceneNodeAttributeData rows inside an
        # Attributes container, each also named "Attributes". Accept both the
        # nested list shape and a direct row shape used by some exports.
        rows = [
            child
            for child in list(container)
            if child.tag == "Property" and child.get("name") == "Attributes"
        ]
        for attribute in rows or [container]:
            name = _first(attribute, "Name")
            value = _first(attribute, "Value")
            if name is not None and value is not None:
                result[name.get("value", "")] = value.get("value", "")
    return result


def _scene_nodes(scene_mxml: Path) -> tuple[ET.Element, list[dict[str, Any]]]:
    root = ET.parse(scene_mxml).getroot()
    _root_is_identity(root, scene_mxml)
    result: list[dict[str, Any]] = []

    def walk(node: ET.Element, path: tuple[int, ...]) -> None:
        name = _node_name(node)
        if name.startswith(MAP_PREFIXES):
            if len(path) != 1:
                raise ValueError(f"callback tag has a parent transform: {scene_mxml} {path} {name}")
            transform = _first(node, "Transform")
            position = _node_translation(node)
            result.append({
                "name": name,
                "path": path,
                "position": position,
                "attributes": _attribute_values(node),
                "has_authored_transform": transform is not None,
            })
        for index, child in enumerate(_children_nodes(node)):
            walk(child, path + (index,))

    for index, child in enumerate(_children_nodes(root)):
        walk(child, (index,))
    return root, result


def authored_bounds_min_candidate(scene_mxml: Path) -> tuple[float, float, float]:
    """Estimate the bounds visitor's low xyz from authored MXML values.

    The actual visitor gets AABB vectors from engine resource-manager state
    through FUN_141845820, then adds the parent's manager translation. This
    helper reads AABBMIN* and Trans* from MXML as a candidate reconstruction;
    the exact type-specific factory method that fills manager-local bounds
    has not been identified, so equality with these authored fields is not
    established. The origin participates in the low bound because
    FUN_1403A8F60 initializes its accumulator to (0,0,0,1).
    """
    _, nodes = _scene_nodes(scene_mxml)
    low = [0.0, 0.0, 0.0]
    for node in nodes:
        if not node["name"].startswith(BOUNDS_PREFIXES):
            continue
        attrs = node["attributes"]
        mins = []
        for axis in "XYZ":
            key = f"AABBMIN{axis}"
            if key not in attrs:
                raise ValueError(f"missing {key} for bounds node {node['name']} in {scene_mxml}")
            mins.append(_f32(float(attrs[key])))
        world_min = tuple(_add32(mins[i], node["position"][i]) for i in range(3))
        low = [min(low[i], world_min[i]) for i in range(3)]
    return tuple(_f32(value) for value in low)


def scene_callback_bounds_min(scene_mxml: Path) -> tuple[float, float, float]:
    """Compatibility alias for :func:`authored_bounds_min_candidate`."""
    return authored_bounds_min_candidate(scene_mxml)


@dataclass(frozen=True)
class SceneCallbackMatrix:
    """Only the 3x3 and translation xyz consumed by the callback path."""

    axes: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]
    translation: tuple[float, float, float]
    orientation: int
    bounds_min: tuple[float, float, float]
    extent_dimensions: tuple[int, int, int]
    source_global_rows: tuple[tuple[float, float, float, float], ...]

    def transform_point(self, position: tuple[float, float, float]) -> tuple[float, float, float]:
        """Transform a local point with row-vector layout and native add order."""
        x, y, z = (_f32(value) for value in position)
        output = []
        for column in range(3):
            y_term = _mul32(y, self.axes[1][column])
            x_term = _mul32(x, self.axes[0][column])
            z_term = _mul32(z, self.axes[2][column])
            value = _add32(y_term, x_term)
            value = _add32(value, z_term)
            value = _add32(value, self.translation[column])
            output.append(value)
        return tuple(output)


def build_scene_callback_matrix(
    bounds_min: tuple[float, float, float],
    *,
    orientation: int,
    extent_dimensions: tuple[int, int, int],
    source_global_rows: tuple[tuple[float, float, float, float], ...] = INITIAL_MATRIX_ROWS,
) -> SceneCallbackMatrix:
    """Build the callback-relevant xyz transform from FUN_14039EC00.

    `extent_dimensions` are the selected source row's x/y/z u16s at +0x258,
    +0x25A, and +0x25C. The writer only uses x and z for orientation offsets.
    They are explicit because the upstream candidate-row producer must supply
    the correct source row. `source_global_rows` defaults to the exact startup
    basis/origin loaded from 7.05's initializer-pointer table.
    """
    if orientation not in (0, 1, 2, 3):
        raise ValueError("orientation must be 0, 1, 2, or 3")
    if len(bounds_min) != 3 or len(extent_dimensions) != 3 or len(source_global_rows) != 4:
        raise ValueError("expected xyz bounds, xyz dimensions, and four source float4 rows")
    if any(len(row) != 4 for row in source_global_rows):
        raise ValueError("every source global row must have four float32 lanes")
    if any(not isinstance(dimension, int) or not 0 <= dimension <= 0xFFFF for dimension in extent_dimensions):
        raise ValueError("extent dimensions must be u16 values")

    basis = tuple(tuple(_f32(value) for value in row) for row in source_global_rows)
    low = tuple(_f32(value) for value in bounds_min)
    spacing_x, _, spacing_z = GRID_SPACING
    tx = _sub32(_mul32(spacing_x, -0.5), low[0])
    ty = 0.0
    tz = _sub32(_mul32(spacing_z, -0.5), low[2])

    axes = tuple(tuple(basis[row][column] for column in range(3)) for row in range(3))
    translation = (tx, ty, tz)
    if orientation > 0:
        sine, cosine = native_sin_cos_for_orientation(orientation)
        rotation_x = (cosine, 0.0, sine)
        rotation_y = (0.0, 1.0, 0.0)
        rotation_z = (-sine, 0.0, cosine)
        rotated = []
        for row in axes:
            x, y, z = row
            result = []
            for column in range(3):
                # Match the native SIMD order: (y * Y-row + x * X-row) + z * Z-row.
                y_term = _mul32(y, rotation_y[column])
                x_term = _mul32(x, rotation_x[column])
                z_term = _mul32(z, rotation_z[column])
                value = _add32(y_term, x_term)
                result.append(_add32(value, z_term))
            rotated.append(tuple(result))
        axes = tuple(rotated)

        origin = basis[3]
        translation_values = []
        for column in range(3):
            y_term = _mul32(ty, axes[1][column])
            x_term = _mul32(tx, axes[0][column])
            z_term = _mul32(tz, axes[2][column])
            value = _add32(y_term, x_term)
            value = _add32(value, z_term)
            translation_values.append(_add32(value, origin[column]))
        translation = tuple(translation_values)

        dim_x, _, dim_z = extent_dimensions
        if orientation == 1:
            translation = (_add32(translation[0], _mul32(float(dim_z - 1), spacing_x)), translation[1], translation[2])
        elif orientation == 2:
            translation = (
                _add32(translation[0], _mul32(float(dim_z - 1), spacing_x)),
                translation[1],
                _add32(translation[2], _mul32(float(dim_x - 1), spacing_z)),
            )
        else:
            translation = (translation[0], translation[1], _add32(translation[2], _mul32(float(dim_x - 1), spacing_z)))

    return SceneCallbackMatrix(
        axes=axes,
        translation=translation,
        orientation=orientation,
        bounds_min=low,
        extent_dimensions=extent_dimensions,
        source_global_rows=basis,
    )


def quantize_callback_position(position: tuple[float, float, float]) -> dict[str, int] | None:
    """Port FA50's divide-by-8, signed-half rounding, and 5x3x5 range guard."""
    rounded: list[int] = []
    for coordinate, spacing, limit in zip(position, GRID_SPACING, (4, 2, 4), strict=True):
        scaled = _f32(_f32(coordinate) / _f32(spacing))
        half = _f32(math.copysign(0.5, scaled))
        cell_coordinate = int(_add32(scaled, half))
        if cell_coordinate < 0 or cell_coordinate > limit:
            return None
        rounded.append(cell_coordinate)
    x, y, z = rounded
    index = ((z * 3 + y) * 5 + x)
    return {"x": x, "y": y, "z": z, "cell_index": index, "byte_offset": index * CELL_BYTES}


@dataclass(frozen=True)
class SceneMapResult:
    raw_map: bytes
    dimensions: tuple[int, int, int]
    final_cell_c_divisor: int
    matrix: SceneCallbackMatrix
    callback_bounds_min: tuple[float, float, float]
    callback_bounds_source: str
    callback_order_source: str
    callback_order_is_explicit: bool
    callback_nodes: tuple[dict[str, Any], ...]


def build_scene_piece_map(
    scene_mxml: Path,
    *,
    orientation: int,
    extent_dimensions: tuple[int, int, int],
    decoration_layer: int,
    cell_c_numerator: int,
    cell_c_divisor: int = 1,
    manager_visitor_low_bounds: tuple[float, float, float] | None = None,
    callback_node_order: Sequence[tuple[int, ...]] | None = None,
    expected_mxml_sha256: str | None = None,
    source_global_rows: tuple[tuple[float, float, float, float], ...] = INITIAL_MATRIX_ROWS,
) -> SceneMapResult:
    """Produce one scene's raw 600-byte map and separate dimensions.

    Parameters `orientation`, `extent_dimensions`, `decoration_layer`, and
    `cell_c_numerator` are upstream writer state. `cell_c_divisor=1` matches
    FUN_14039EC00's per-callback local initialization; the caller may pass the
    live value for a captured continuation. `manager_visitor_low_bounds`, when
    supplied, is the low xyz vector produced by the engine-manager bounds
    visitor. Otherwise the authored MXML AABB values provide an explicitly
    provisional candidate. `callback_node_order` is the sequence of MXML paths
    in actual callback invocation order. If omitted, authored depth-first
    order is used as a candidate: exact source-child loops and manager sibling
    append behavior preserve ordinary imported child order, but type-specific
    hooks and special resource branches have not been excluded as sources of
    extra callback nodes. The new output row starts with a zeroed 600-byte map
    and zero dimensions, matching its native row setup.
    """
    if expected_mxml_sha256 is not None:
        digest = hashlib.sha256(scene_mxml.read_bytes()).hexdigest().upper()
        if digest != expected_mxml_sha256.upper():
            raise ValueError(f"scene MXML hash mismatch: {scene_mxml}")

    root, nodes = _scene_nodes(scene_mxml)
    del root
    if manager_visitor_low_bounds is None:
        bounds_min = authored_bounds_min_candidate(scene_mxml)
        bounds_source = "authored-mxml-candidate; type-specific local-bounds writer unresolved"
    else:
        if len(manager_visitor_low_bounds) != 3:
            raise ValueError("manager_visitor_low_bounds must contain xyz")
        bounds_min = tuple(_f32(value) for value in manager_visitor_low_bounds)
        bounds_source = "caller-supplied engine-manager visitor low bound"

    if callback_node_order is None:
        order_source = "MXML source-child depth-first candidate; sibling append proven, type-hook insertions unresolved"
        order_is_explicit = False
    else:
        requested_paths = [tuple(path) for path in callback_node_order]
        known_paths = [tuple(node["path"]) for node in nodes]
        if len(requested_paths) != len(set(requested_paths)):
            raise ValueError("callback_node_order contains duplicate node paths")
        if set(requested_paths) != set(known_paths):
            missing = sorted(set(known_paths) - set(requested_paths))
            extra = sorted(set(requested_paths) - set(known_paths))
            raise ValueError(f"callback_node_order must cover each callback tag once; missing={missing}, extra={extra}")
        by_path = {tuple(node["path"]): node for node in nodes}
        nodes = [by_path[path] for path in requested_paths]
        order_source = "caller-supplied sequence; provenance not validated here"
        order_is_explicit = True

    matrix = build_scene_callback_matrix(
        bounds_min,
        orientation=orientation,
        extent_dimensions=extent_dimensions,
        source_global_rows=source_global_rows,
    )
    layer_a, layer_b, layer_c = lookup_layer_bytes(decoration_layer)
    raw_map = bytearray(MAP_BYTES)
    dimensions = [0, 0, 0]
    current_divisor = cell_c_divisor
    node_results: list[dict[str, Any]] = []

    for node in nodes:
        local_position = node["position"]
        world_position = matrix.transform_point(local_position)
        coordinate = quantize_callback_position(world_position)
        result_row: dict[str, Any] = {
            "name": node["name"],
            "path": list(node["path"]),
            "local_position": local_position,
            "callback_position": world_position,
            "cell": coordinate,
            "write": None,
        }
        if coordinate is not None:
            offset = coordinate["byte_offset"]
            before = bytes(raw_map[offset:offset + CELL_BYTES])
            context = RowTagContext(
                layer_a=layer_a,
                layer_b=layer_b,
                layer_c=layer_c,
                cell_c_numerator=cell_c_numerator,
                cell_c_divisor=current_divisor,
                decoration_layer=decoration_layer,
                orientation=orientation,
            )
            encoded = encode_node_tag(node["name"], before, context=context)
            raw_map[offset:offset + CELL_BYTES] = encoded.cell_bytes
            current_divisor = encoded.next_cell_c_divisor
            if encoded.grows_dimensions:
                dimensions[0] = max(dimensions[0], coordinate["x"] + 1)
                dimensions[1] = max(dimensions[1], coordinate["y"] + 1)
                dimensions[2] = max(dimensions[2], coordinate["z"] + 1)
            result_row["write"] = {
                "tag_kind": encoded.tag_kind,
                "before": before.hex().upper(),
                "after": encoded.cell_bytes.hex().upper(),
                "grows_dimensions": encoded.grows_dimensions,
                "dimensions_after": tuple(dimensions),
            }
        node_results.append(result_row)

    return SceneMapResult(
        raw_map=bytes(raw_map),
        dimensions=tuple(dimensions),
        final_cell_c_divisor=current_divisor,
        matrix=matrix,
        callback_bounds_min=bounds_min,
        callback_bounds_source=bounds_source,
        callback_order_source=order_source,
        callback_order_is_explicit=order_is_explicit,
        callback_nodes=tuple(node_results),
    )
