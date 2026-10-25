# [G1 RECONSTRUCTION 2026-10-25] Original lines 1-219 are LOST (only the grep -n map survives: fit import at
# 24/26, the four fingerprint constants at 29-32, _scene_transform "rotation" at 171, a docstring line at 192).
# Lines from here to the end of the head of quantize_callback_position are NEW CODE written from the call
# sites in the logged lines 220-360 and in extract_build_data_705 / build_profile_705. The logged original
# resumes at "        if coordinate_index < 0 ..." inside quantize_callback_position; the tail of
# load_static_bundle after "theme_rows," (end of the logged text) and fits_room_piece_705 (logged at
# original line 507 only as "return fits_room_piece_705(*args, **kwargs)") are reconstructed too.
"""Static (no live game) loaders for the NMS 7.05 offline derelict layout port.

Reads the exact 7.05 preset table, the abandoned-freighter entrance entity, the generated-base templates
table and the 319-scene manifest, checks their fingerprints, and returns them as plain dict rows.
Scene callback nodes are read from the extracted scene MXML.
"""

from __future__ import annotations

import hashlib
import json
import math
import struct
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

try:  # direct module use with this directory on sys.path
    from nms_dungeon_fit_705 import fits_room_piece_705 as _fits_room_piece_705
except ImportError:  # pragma: no cover - package-style use
    from .nms_dungeon_fit_705 import fits_room_piece_705 as _fits_room_piece_705

NMS_EXE_SHA256 = "13D5060D4EFB9D2A6A6B1B349BC4257231056CC2A055DF4BB15D816262CC3499"
PRECACHE_PAK_SHA256 = "A6371A8B2F065ECA33FD306A16CBE2BACA9D4CE75806C71E42F74E1AB9295032"
ENTITY_SCENE_PAK_SHA256 = "58958536E58DFAEB81E0423B5508C7D3DBF3713BAC09E857577FEB275D9F2627"
GENERATEDBASE_MXML_SHA256 = "2C2714B4634C187BC65ACC9BBEB1C1CC2A62229C5644FC24A0BB187E1129B85D"

MAP_NODE_PREFIXES = ("CELL", "NOCELL", "PATH", "LAYER")
GRID_SPACING = (8.0, 8.0, 8.0)
GRID_LIMITS = (4, 2, 4)
IDENTITY_SCENE_MATRIX = (
    1.0, 0.0, 0.0, 0.0,
    0.0, 1.0, 0.0, 0.0,
    0.0, 0.0, 1.0, 0.0,
    0.0, 0.0, 0.0, 1.0,
)


@dataclass(frozen=True)
class StaticBundle:
    root: Path
    choices: list[dict[str, Any]]
    preset_rows: dict[str, dict[str, Any]]
    room_rows: dict[str, dict[str, Any]]
    theme_rows: dict[str, dict[str, Any]]
    decoration_rows: dict[str, dict[str, Any]]
    pruning_rows: dict[str, dict[str, Any]]
    scene_assets: dict[str, dict[str, Any]]
    source_hashes: dict[str, str]
    provenance: dict[str, Any]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _f32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", float(value)))[0]


def _property_children(node: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in list(node) if child.tag == "Property" and child.get("name") == name]


def _first(node: ET.Element, name: str) -> ET.Element | None:
    matches = _property_children(node, name)
    return matches[0] if matches else None


def _value(node: ET.Element) -> Any:
    """Parse one MXML Property: scalar -> str; list -> list; struct -> {"type", "fields"}."""
    children = [child for child in list(node) if child.tag == "Property"]
    if not children:
        return node.get("value", "")
    name = node.get("name")
    if all(child.get("name") == name for child in children):
        return [_value(child) for child in children]
    fields = _fields(node)
    if node.get("value") is None:
        return fields
    return {"type": node.get("value"), "fields": fields}


def _fields(node: ET.Element) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for child in list(node):
        if child.tag == "Property" and child.get("name") is not None:
            result[child.get("name")] = _value(child)
    return result


def _records(parent: ET.Element, list_name: str, struct_type: str) -> list[dict[str, Any]]:
    """Rows of a struct list: `<Property name=list_name>` holding `<Property name=list_name value=struct_type>`."""
    container = _first(parent, list_name)
    if container is None:
        raise ValueError(f"missing list {list_name}")
    rows = []
    for item in _property_children(container, list_name):
        if item.get("value") != struct_type:
            raise ValueError(f"unexpected {list_name} element type {item.get('value')!r}")
        rows.append(_fields(item))
    return rows


def _scene_transform(node: ET.Element) -> dict[str, tuple[float, float, float]]:
    """Authored local TRS of a TkSceneNodeData (float32 values; identity when absent)."""
    transform = _first(node, "Transform")

    def triple(keys: tuple[str, str, str], default: tuple[float, float, float]) -> tuple[float, float, float]:
        if transform is None:
            return default
        out = []
        for key, fallback in zip(keys, default):
            item = _first(transform, key)
            out.append(_f32(float(item.get("value"))) if item is not None and item.get("value") not in (None, "")
                       else fallback)
        return tuple(out)

    return {
        "translation": triple(("TransX", "TransY", "TransZ"), (0.0, 0.0, 0.0)),
        "rotation": triple(("RotX", "RotY", "RotZ"), (0.0, 0.0, 0.0)),
        "scale": triple(("ScaleX", "ScaleY", "ScaleZ"), (1.0, 1.0, 1.0)),
    }


def transform_scene_position(matrix: tuple[float, ...] | list[float], position: tuple[float, float, float]
                             ) -> tuple[float, float, float]:
    """Row-vector float32 transform of a point by a caller-supplied 4x4 (16 floats, row-major).

    Only an explicit matrix is accepted; it does not guess how to build a matrix from Euler angles.
    """
    if len(matrix) != 16:
        raise ValueError("scene instance matrix needs 16 floats")
    x, y, z = (_f32(v) for v in position)
    out = []
    for column in range(3):
        value = _f32(_f32(y * _f32(matrix[4 + column])) + _f32(x * _f32(matrix[column])))
        value = _f32(value + _f32(z * _f32(matrix[8 + column])))
        out.append(_f32(value + _f32(matrix[12 + column])))
    return tuple(out)


def quantize_callback_position(position: tuple[float, float, float]) -> dict[str, int] | None:
    """FA50's divide by 8, signed-half rounding (cvttss2si) and 5x3x5 guard."""
    rounded: list[int] = []
    for coordinate, spacing, limit in zip(position, GRID_SPACING, GRID_LIMITS):
        scaled = _f32(_f32(coordinate) / _f32(spacing))
        coordinate_index = int(_f32(scaled + _f32(math.copysign(0.5, scaled))))
        if coordinate_index < 0 or coordinate_index > limit:
            return None
        rounded.append(coordinate_index)
    x, y, z = rounded
    index = ((z * 3 + y) * 5 + x)
    return {"x": x, "y": y, "z": z, "cell_index": index, "byte_offset": index * 8}


def load_scene_map_nodes(
    scene_mxml: Path,
    *,
    expected_mxml_sha256: str | None = None,
    scene_instance_matrix: tuple[float, ...] | list[float] = IDENTITY_SCENE_MATRIX,
) -> list[dict[str, Any]]:
    """Return authored callback nodes and their exact callback coordinates.

    All callback-tagged nodes in the exact 319-scene set are direct children
    of identity scene roots. Their authored `TransX/Y/Z` is therefore the
    callback point before the selected piece matrix is applied. For the exact
    writer-built matrix and 600-byte map, use
    `scene_callback_matrix_705.build_scene_piece_map`.
    """
    if expected_mxml_sha256 is not None and sha256_file(scene_mxml) != expected_mxml_sha256.upper():
        raise ValueError(f"scene MXML hash mismatch: {scene_mxml}")
    root = ET.parse(scene_mxml).getroot()
    root_transform = _scene_transform(root)["translation"]
    root_rotation = _scene_transform(root)["rotation"]
    root_scale = _scene_transform(root)["scale"]
    if root_transform != (0.0, 0.0, 0.0) or root_rotation != (0.0, 0.0, 0.0) or root_scale != (1.0, 1.0, 1.0):
        raise ValueError(f"nonidentity scene root requires matrix composition: {scene_mxml}")

    result: list[dict[str, Any]] = []

    def visit(node: ET.Element, path: tuple[int, ...]) -> None:
        name_node = _first(node, "Name")
        name = name_node.get("value", "") if name_node is not None else ""
        if name.startswith(MAP_NODE_PREFIXES):
            if len(path) != 1:
                raise ValueError(f"nested callback node needs parent-matrix support: {scene_mxml} {path} {name}")
            authored = _scene_transform(node)
            result.append({
                "name": name,
                "callback_class": next(prefix for prefix in MAP_NODE_PREFIXES if name.startswith(prefix)),
                "node_path_indices": list(path),
                "node_type": (_first(node, "Type").get("value") if _first(node, "Type") is not None else None),
                "authored_local_transform": authored,
                "callback_template_position": authored["translation"],
                "callback_instance_position": transform_scene_position(scene_instance_matrix, authored["translation"]),
                "template_cell": quantize_callback_position(authored["translation"]),
                "instance_cell": quantize_callback_position(transform_scene_position(scene_instance_matrix, authored["translation"])),
                "position_evidence": "FUN_141844C30 returns the node matrix; the scene root is identity and the tag node is direct-child, so its template-local position equals authored translation. The optional instance matrix is caller-supplied.",
            })
        children = _first(node, "Children")
        if children is None:
            return
        child_nodes = [
            item for item in list(children)
            if item.tag == "Property" and item.get("value") == "TkSceneNodeData"
        ]
        for index, child_node in enumerate(child_nodes):
            visit(child_node, path + (index,))

    visit(root, ())
    return result


def load_static_bundle(root: Path | None = None) -> StaticBundle:
    root = root or Path(__file__).resolve().parents[2]
    exact = root / "research-output/exact705-dungeon-inputs-20261019"
    generated = root / "research-output/generatedbase-table-705/generatedbasetemplatestable.MXML"
    scene_manifest_path = root / "research-output/exact705-generatedbase-scenes-20261019/exact705-generatedbase-scene-members.sha256.json"
    preset_mxml = exact / "metadata/reality/tables/freighterdungeonstable.MXML"
    entrance_mxml = exact / "models/space/poi/parts/dungeon_entrance/entities/dungeonentrance.entity.MXML"
    provenance_path = exact / "provenance.json"

    files = {
        "preset_mxml": preset_mxml,
        "entrance_mxml": entrance_mxml,
        "generatedbase_mxml": generated,
        "scene_manifest": scene_manifest_path,
    }
    for label, path in files.items():
        if not path.is_file():
            raise FileNotFoundError(f"missing {label}: {path}")
    source_hashes = {label: sha256_file(path) for label, path in files.items()}
    if source_hashes["generatedbase_mxml"] != GENERATEDBASE_MXML_SHA256:
        raise ValueError("generated-base MXML does not match exact 7.05 table fingerprint")

    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    if provenance.get("source_archive_sha256") != PRECACHE_PAK_SHA256:
        raise ValueError("exact preset/entity source archive fingerprint mismatch")
    if provenance.get("build", "").find(NMS_EXE_SHA256) < 0:
        raise ValueError("exact NMS executable fingerprint mismatch")

    p_root = ET.parse(preset_mxml).getroot()
    e_root = ET.parse(entrance_mxml).getroot()
    g_root = ET.parse(generated).getroot()

    component = next(
        (
            prop
            for prop in e_root.iter("Property")
            if prop.get("name") == "Components" and prop.get("value") == "GcAbandonedFreighterComponentData"
        ),
        None,
    )
    if component is None:
        raise ValueError("entrance component not found")
    component_data = _first(component, "GcAbandonedFreighterComponentData")
    if component_data is None:
        raise ValueError("nested entrance component data not found")
    choices = _records(component_data, "DungeonOptions", "GcFreighterDungeonChoice")

    p_rows = _records(p_root, "Dungeons", "GcFreighterDungeonParams")
    preset_rows = {row["Name"]: row for row in p_rows}
    room_rows = {row["Name"]: row for row in _records(g_root, "RoomTemplates", "GcGeneratedBaseRoomTemplate")}
    theme_rows = {row["Name"]: row for row in _records(g_root, "ThemeTemplates", "GcGeneratedBaseThemeTemplate")}
    decoration_rows = {row["Id"]: row for row in _records(g_root, "DecorationTemplates", "GcGeneratedBaseDecorationTemplate")}
    pruning_rows = {row["RuleId"]: row for row in _records(g_root, "PruningRules", "GcGeneratedBasePruningRule")}

    scene_doc = json.loads(scene_manifest_path.read_text(encoding="utf-8"))
    if scene_doc.get("source_archive", {}).get("sha256") != ENTITY_SCENE_PAK_SHA256:
        raise ValueError("generated-base scene archive fingerprint mismatch")
    scene_assets = {row["template_id"]: row for row in scene_doc.get("assets", [])}
    if len(scene_assets) != 319:
        raise ValueError(f"expected 319 scene assets, found {len(scene_assets)}")
    for template_id, row in decoration_rows.items():
        if template_id not in scene_assets:
            raise ValueError(f"decoration scene asset absent from manifest: {template_id}")
        asset = scene_assets[template_id]
        scene = row.get("TemplateScene", {}).get("fields", {})
        expected_path = str(scene.get("Filename", "")).replace("\\", "/").upper()
        if expected_path != asset["resource_path"].upper():
            raise ValueError(f"scene path mismatch for decoration {template_id}")

    return StaticBundle(
        root=root,
        choices=choices,
        preset_rows=preset_rows,
        room_rows=room_rows,
        theme_rows=theme_rows,
        # [G1 RECONSTRUCTED from here to end of file]
        decoration_rows=decoration_rows,
        pruning_rows=pruning_rows,
        scene_assets=scene_assets,
        source_hashes=source_hashes,
        provenance=provenance,
    )


def fits_room_piece_705(*args, **kwargs):
    """Delegate to nms_dungeon_fit_705 (module attribute so q4b scripts can patch it)."""
    return _fits_room_piece_705(*args, **kwargs)
