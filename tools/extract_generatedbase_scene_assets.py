#!/usr/bin/env python3
"""Extract and index NMS 7.05 generated-base scene assets.

The script reads scene paths from the exact GeneratedBaseTemplatesTable MXML,
extracts the matching members from EntitySceneMBIN.pak, converts them with the
pinned MBINCompiler, and indexes authored CRATEM/FOOT_LOCKER scene references.
It keeps every source MBIN and records archive/member/compiler hashes.

--extra-only (offline, from the extracted members) indexes the INTERACTIVE_CASE (briefcase) and LOCKER (tall
locker) references into authored_extra_container_transform_index.csv; the main index keeps CRATEM/FOOT_LOCKER only.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
import sys
import xml.etree.ElementTree as ET
from importlib.metadata import version
from pathlib import Path, PurePosixPath
from typing import Any, Iterator


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PAK = Path(r"G:\SteamLibrary\steamapps\common\No Man's Sky\GAMEDATA\PCBANKS\NMSARC.EntitySceneMBIN.pak")
DEFAULT_EXE = Path(r"G:\SteamLibrary\steamapps\common\No Man's Sky\Binaries\NMS.exe")
DEFAULT_TABLE = ROOT / "research-output/generatedbase-table-705/generatedbasetemplatestable.MXML"
DEFAULT_COMPILER = Path(r"D:\Orca\Temp\mbincompiler-7.04.1-pre3\MBINCompiler.exe")
DEFAULT_OUTPUT = ROOT / "research-output/exact705-generatedbase-scenes-20261019"

EXPECTED_PAK_SHA256 = "58958536E58DFAEB81E0423B5508C7D3DBF3713BAC09E857577FEB275D9F2627"
EXPECTED_EXE_SHA256 = "13D5060D4EFB9D2A6A6B1B349BC4257231056CC2A055DF4BB15D816262CC3499"
EXPECTED_TABLE_SHA256 = "2C2714B4634C187BC65ACC9BBEB1C1CC2A62229C5644FC24A0BB187E1129B85D"
EXPECTED_COMPILER_SHA256 = "4179DDDB665F7CDDBE9DDDDDF6E529172ABDD98B0097F65FDD224467D5BB3EA4"
EXPECTED_HGPAKTOOL_VERSION = "1.1.3"
EXPECTED_COMPILER_HEADER = "MBINCompiler version (7.04.1.3)"

# Loot containers referenced by generated-base scenes (SCENEGRAPH target suffix -> container_kind).
# The main index (authored_container_transform_index.*) keeps exactly the two live-validated kinds; the generators
# and the published atlas columns rely on it. The briefcase and tall locker go to a separate extra index
# (--extra-only, authored_extra_container_transform_index.csv) so the main outputs stay byte-identical.
# Evidence (entities, reward ids, images): research-output/CONTAINER_TYPES_20261020.md.
CONTAINER_KIND_BY_TARGET = {
    "/CRATEM.SCENE.MBIN": "salvage_crate",          # CRATEM.ENTITY: GenericReward R_ABAND_CRATE
    "/FOOT_LOCKER.SCENE.MBIN": "crew_footlocker",   # FOOTLOCKER.ENTITY: GenericReward R_ABAND_CRATE
}
EXTRA_CONTAINER_KIND_BY_TARGET = {
    "/INTERACTIVE_CASE.SCENE.MBIN": "briefcase",    # SMALLCASE.ENTITY: GenericReward R_ABAND_CASE
    "/LOCKER.SCENE.MBIN": "tall_locker",            # LOCKER.ENTITY: GenericReward R_ABAND_LOCK
}
EXTRA_INDEX_NAME = "authored_extra_container_transform_index.csv"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def child_property(node: ET.Element, name: str) -> ET.Element | None:
    for child in list(node):
        if child.tag == "Property" and child.get("name") == name:
            return child
    return None


def property_value(node: ET.Element, name: str) -> str | None:
    child = child_property(node, name)
    return child.get("value") if child is not None else None


def read_transform(node: ET.Element) -> dict[str, float]:
    transform = child_property(node, "Transform")
    result: dict[str, float] = {}
    for key in ("TransX", "TransY", "TransZ", "RotX", "RotY", "RotZ", "ScaleX", "ScaleY", "ScaleZ"):
        value = child_property(transform, key) if transform is not None else None
        default = 1.0 if key.startswith("Scale") else 0.0
        result[key] = float(value.get("value")) if value is not None else default
    return result


def is_identity_transform(transform: dict[str, float], tolerance: float = 1e-6) -> bool:
    expected = {
        "TransX": 0.0,
        "TransY": 0.0,
        "TransZ": 0.0,
        "RotX": 0.0,
        "RotY": 0.0,
        "RotZ": 0.0,
        "ScaleX": 1.0,
        "ScaleY": 1.0,
        "ScaleZ": 1.0,
    }
    return all(math.isfinite(transform[key]) and abs(transform[key] - expected[key]) <= tolerance for key in expected)


def scene_children(node: ET.Element) -> list[ET.Element]:
    children = child_property(node, "Children")
    if children is None:
        return []
    return children.findall("Property[@name='Children'][@value='TkSceneNodeData']")


def node_attributes(node: ET.Element) -> dict[str, str]:
    attributes = child_property(node, "Attributes")
    result: dict[str, str] = {}
    if attributes is None:
        return result
    for item in attributes.findall("Property[@name='Attributes']"):
        name = property_value(item, "Name")
        value = property_value(item, "Value")
        if name:
            result[name.upper()] = value or ""
    return result


def walk_scene(node: ET.Element, path: list[dict[str, Any]] | None = None) -> Iterator[tuple[ET.Element, list[dict[str, Any]]]]:
    path = [] if path is None else path
    yield node, path
    for child_index, child in enumerate(scene_children(node)):
        record = {
            "child_index": child_index,
            "name": property_value(child, "Name") or "",
            "type": property_value(child, "Type") or "",
            "authored_transform": read_transform(child),
        }
        yield from walk_scene(child, path + [record])


def normalize_resource(path: str) -> str:
    return path.replace("\\", "/").strip("/").upper()


def archive_key(resource_path: str) -> str:
    normalized = resource_path.replace("\\", "/").strip("/").lower()
    return normalized if normalized.endswith(".mbin") else normalized + ".mbin"


def parse_table(table_path: Path) -> list[dict[str, Any]]:
    root = ET.parse(table_path).getroot()
    decoration_list = child_property(root, "DecorationTemplates")
    if decoration_list is None:
        raise ValueError("GeneratedBaseTemplatesTable has no DecorationTemplates list")

    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for table_index, item in enumerate(decoration_list.findall("Property[@name='DecorationTemplates'][@value='GcGeneratedBaseDecorationTemplate']")):
        template_id = property_value(item, "Id") or ""
        template_scene = child_property(item, "TemplateScene")
        resource_path = property_value(template_scene, "Filename") if template_scene is not None else None
        if not resource_path:
            raise ValueError(f"Decoration template {template_id or table_index} has no scene filename")
        normalized = normalize_resource(resource_path)
        if not normalized.startswith("MODELS/SPACE/POI/DUNGEON/") or not normalized.endswith(".SCENE.MBIN"):
            raise ValueError(f"Unexpected generated-base scene path: {resource_path}")
        key = normalized.casefold()
        if key in seen:
            raise ValueError(f"Duplicate scene filename in decoration table: {resource_path}")
        seen.add(key)
        invalid_room_indexes_node = child_property(item, "InvalidRoomIndexes")
        invalid_room_indexes = (
            []
            if invalid_room_indexes_node is None
            else [
                int(child.get("value", "0"))
                for child in invalid_room_indexes_node.findall("Property[@name='InvalidRoomIndexes']")
            ]
        )
        records.append(
            {
                "table_index": table_index,
                "template_id": template_id,
                "resource_path": normalized,
                "probability": float(property_value(item, "Probability") or 0.0),
                "max_per_room": int(property_value(item, "MaxPerRoom") or 0),
                "decoration_layer": property_value(item, "DecorationLayer") or "",
                "invalid_room_indexes": invalid_room_indexes,
            }
        )
    return records


def safe_member_path(member: str) -> PurePosixPath:
    path = PurePosixPath(member.replace("\\", "/").lower())
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"Unsafe archive member path: {member}")
    return path


def index_scene_asset(record: dict[str, Any], mxml_path: Path, mxml_hash: str, mbin_hash: str, mbin_size: int,
                      kinds: dict[str, str] = CONTAINER_KIND_BY_TARGET) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    root = ET.parse(mxml_path).getroot()
    root_transform = read_transform(root)
    root_identity = is_identity_transform(root_transform)
    containers: list[dict[str, Any]] = []

    for node, ancestor_path in walk_scene(root):
        target = normalize_resource(node_attributes(node).get("SCENEGRAPH", ""))
        kind = next((k for suffix, k in kinds.items() if target.endswith(suffix)), None)
        if kind is None:
            continue

        node_transform = read_transform(node)
        node_depth = len(ancestor_path)
        parent_path = ancestor_path[:-1] if ancestor_path else []
        hierarchy_needs_composition = (not root_identity) or bool(parent_path)
        node_path = ancestor_path or [
            {
                "child_index": None,
                "name": property_value(node, "Name") or "",
                "type": property_value(node, "Type") or "",
                "authored_transform": node_transform,
            }
        ]
        containers.append(
            {
                "template_id": record["template_id"],
                "table_index": record["table_index"],
                "scene_resource": record["resource_path"],
                "scene_mbin_member_sha256": mbin_hash,
                "scene_mxml_sha256": mxml_hash,
                "container_kind": kind,
                "scene_node_name": property_value(node, "Name") or "",
                "node_type": property_value(node, "Type") or "",
                "target_scene_resource": target,
                "node_depth": node_depth,
                "node_path": node_path,
                "parent_chain": parent_path,
                "scene_root_transform": root_transform,
                "authored_node_transform": node_transform,
                "direct_scene_local_position": None
                if hierarchy_needs_composition
                else {axis.lower(): node_transform[f"Trans{axis}"] for axis in ("X", "Y", "Z")},
                "hierarchy_needs_composition": hierarchy_needs_composition,
            }
        )

    inventory = {
        **record,
        "scene_mbin_relative_path": str(safe_member_path(record["resource_path"]).with_suffix(".mbin")),
        "scene_mbin_sha256": mbin_hash,
        "scene_mbin_size_bytes": mbin_size,
        "scene_mxml_relative_path": str(safe_member_path(record["resource_path"]).with_suffix(".MXML")),
        "scene_mxml_sha256": mxml_hash,
        "scene_root_transform": root_transform,
        "scene_root_is_identity": root_identity,
        "authored_salvage_crate_refs": sum(entry["container_kind"] == "salvage_crate" for entry in containers),
        "authored_footlocker_refs": sum(entry["container_kind"] == "crew_footlocker" for entry in containers),
        "requires_hierarchy_composition": (not root_identity)
        or any(entry["hierarchy_needs_composition"] for entry in containers),
    }
    return inventory, containers


def write_container_csv(path: Path, container_index: list[dict[str, Any]]) -> None:
    """Write the per-reference container CSV (column layout shared by the main and the extra index)."""
    with path.open("w", newline="", encoding="utf-8") as stream:
        fields = [
            "table_index",
            "template_id",
            "scene_resource",
            "scene_mbin_member_sha256",
            "scene_mxml_sha256",
            "container_kind",
            "scene_node_name",
            "node_type",
            "target_scene_resource",
            "node_depth",
            "hierarchy_needs_composition",
            "direct_local_x",
            "direct_local_y",
            "direct_local_z",
            "node_path_json",
            "authored_transform_json",
        ]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for entry in container_index:
            direct = entry["direct_scene_local_position"] or {}
            writer.writerow(
                {
                    "table_index": entry["table_index"],
                    "template_id": entry["template_id"],
                    "scene_resource": entry["scene_resource"],
                    "scene_mbin_member_sha256": entry["scene_mbin_member_sha256"],
                    "scene_mxml_sha256": entry["scene_mxml_sha256"],
                    "container_kind": entry["container_kind"],
                    "scene_node_name": entry["scene_node_name"],
                    "node_type": entry["node_type"],
                    "target_scene_resource": entry["target_scene_resource"],
                    "node_depth": entry["node_depth"],
                    "hierarchy_needs_composition": entry["hierarchy_needs_composition"],
                    "direct_local_x": direct.get("x", ""),
                    "direct_local_y": direct.get("y", ""),
                    "direct_local_z": direct.get("z", ""),
                    "node_path_json": json.dumps(entry["node_path"], separators=(",", ":")),
                    "authored_transform_json": json.dumps(entry["authored_node_transform"], separators=(",", ":")),
                }
            )


def write_extra_index(output: Path, table_mxml: Path) -> int:
    """Index the briefcase / tall locker references from the already extracted, hash-recorded member MXMLs.

    Offline: reads only <output>/members and the member manifest (no archive, no game executable). Each MBIN and MXML
    must match the SHA-256 recorded in exact705-generatedbase-scene-members.sha256.json. Writes EXTRA_INDEX_NAME with
    the same columns as the main index; the main index files are not touched.
    """
    manifest = json.loads((output / "exact705-generatedbase-scene-members.sha256.json").read_text(encoding="utf-8"))
    if sha256_file(table_mxml) != manifest["source_table"]["sha256"]:
        raise SystemExit("generated-base table MXML does not match the member manifest")
    by_index = {asset["table_index"]: asset for asset in manifest["assets"]}
    records = parse_table(table_mxml)
    if len(records) != len(by_index):
        raise SystemExit(f"table has {len(records)} templates, manifest {len(by_index)}")
    refs: list[dict[str, Any]] = []
    for record in records:
        asset = by_index[record["table_index"]]
        mbin, mxml = output / asset["mbin_relative_path"], output / asset["mxml_relative_path"]
        mbin_hash, mxml_hash = sha256_file(mbin), sha256_file(mxml)
        if mbin_hash != asset["mbin_sha256"] or mxml_hash != asset["mxml_sha256"]:
            raise SystemExit(f"member hash mismatch for {record['resource_path']}")
        _, found = index_scene_asset(record, mxml, mxml_hash, mbin_hash, mbin.stat().st_size, kinds=EXTRA_CONTAINER_KIND_BY_TARGET)
        refs.extend(found)
    if any(ref["hierarchy_needs_composition"] for ref in refs):
        raise SystemExit("an extra container reference needs ancestor composition; not supported")
    write_container_csv(output / EXTRA_INDEX_NAME, refs)
    totals = {kind: sum(ref["container_kind"] == kind for ref in refs) for kind in EXTRA_CONTAINER_KIND_BY_TARGET.values()}
    scenes = len({ref["scene_resource"] for ref in refs})
    print(json.dumps({"output": str(output / EXTRA_INDEX_NAME), "references": totals, "scenes": scenes}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pak", type=Path, default=DEFAULT_PAK)
    parser.add_argument("--nms-exe", type=Path, default=DEFAULT_EXE)
    parser.add_argument("--table-mxml", type=Path, default=DEFAULT_TABLE)
    parser.add_argument("--compiler", type=Path, default=DEFAULT_COMPILER)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--skip-convert", action="store_true", help="Reuse existing MXML files in the output folder.")
    parser.add_argument("--extra-only", action="store_true",
                        help=f"Only write {EXTRA_INDEX_NAME} (briefcase, tall locker) from the extracted members; offline.")
    args = parser.parse_args()
    if args.extra_only:
        return write_extra_index(args.output, args.table_mxml)

    try:
        from hgpaktool import HGPAKFile
    except ImportError as exc:
        raise SystemExit("Install the pinned HGPAKtool 1.1.3 package before running this extractor") from exc

    exe_hash = sha256_file(args.nms_exe)
    pak_hash = sha256_file(args.pak)
    table_hash = sha256_file(args.table_mxml)
    compiler_hash = sha256_file(args.compiler)
    hgpaktool_version = version("hgpaktool")
    if exe_hash != EXPECTED_EXE_SHA256:
        raise SystemExit(f"Wrong NMS executable hash: {exe_hash}")
    if pak_hash != EXPECTED_PAK_SHA256:
        raise SystemExit(f"Wrong EntitySceneMBIN archive hash: {pak_hash}")
    if table_hash != EXPECTED_TABLE_SHA256:
        raise SystemExit(f"Wrong generated-base table MXML hash: {table_hash}")
    if compiler_hash != EXPECTED_COMPILER_SHA256:
        raise SystemExit(f"Wrong MBINCompiler hash: {compiler_hash}")
    if hgpaktool_version != EXPECTED_HGPAKTOOL_VERSION:
        raise SystemExit(f"Expected HGPAKtool {EXPECTED_HGPAKTOOL_VERSION}; got {hgpaktool_version}")

    records = parse_table(args.table_mxml)
    if len(records) != 319:
        raise SystemExit(f"Expected 319 generated-base DecorationTemplates; found {len(records)}")

    args.output.mkdir(parents=True, exist_ok=True)
    member_root = args.output / "members"
    member_root.mkdir(parents=True, exist_ok=True)
    with HGPAKFile(args.pak) as archive:
        actual_names = {name.lower(): name for name in archive.filenames}
        selected: list[str] = []
        for record in records:
            path = record["resource_path"].lower()
            key = archive_key(path)
            try:
                selected.append(actual_names[key])
            except KeyError as exc:
                raise SystemExit(f"Exact archive does not contain table scene member {record['resource_path']}") from exc

        extracted: dict[str, dict[str, Any]] = {}
        for member, payload in archive.extract(selected):
            rel = safe_member_path(member)
            destination = member_root.joinpath(*rel.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            member_hash = hashlib.sha256(payload).hexdigest().upper()
            if destination.exists():
                existing_hash = sha256_file(destination)
                if existing_hash != member_hash:
                    raise SystemExit(f"Refusing to overwrite mismatched existing extracted file: {destination}")
            else:
                destination.write_bytes(payload)
            extracted[member.lower()] = {
                "archive_member": member,
                "relative_path": destination.relative_to(args.output).as_posix(),
                "size_bytes": len(payload),
                "sha256": member_hash,
                "path": destination,
            }

    if len(extracted) != len(records):
        raise SystemExit(f"Expected {len(records)} extracted members; got {len(extracted)}")

    compiler_errors: list[dict[str, str]] = []
    assets: list[dict[str, Any]] = []
    container_index: list[dict[str, Any]] = []
    compiler_version = "7.04.1.3"
    for position, record in enumerate(records, 1):
        member_key = archive_key(record["resource_path"])
        raw = extracted.get(member_key)
        if raw is None:
            raise SystemExit(f"No extracted MBIN for table entry {record['resource_path']}")
        raw_path: Path = raw["path"]
        mxml_path = raw_path.with_suffix(".MXML")
        if not args.skip_convert:
            command = [str(args.compiler), "-y", str(raw_path)]
            process = subprocess.run(command, cwd=raw_path.parent, capture_output=True, text=True, timeout=120)
            if process.returncode != 0:
                compiler_errors.append(
                    {
                        "resource_path": record["resource_path"],
                        "returncode": str(process.returncode),
                        "stdout": process.stdout[-3000:],
                        "stderr": process.stderr[-3000:],
                    }
                )
                continue
        if not mxml_path.is_file():
            compiler_errors.append(
                {
                    "resource_path": record["resource_path"],
                    "returncode": "no-output",
                    "stdout": "",
                    "stderr": f"Compiler did not create {mxml_path}",
                }
            )
            continue
        header = mxml_path.read_text(encoding="utf-8", errors="replace")[:240]
        if EXPECTED_COMPILER_HEADER not in header:
            raise SystemExit(f"Unexpected compiler header in {mxml_path}")
        mxml_hash = sha256_file(mxml_path)
        inventory, refs = index_scene_asset(record, mxml_path, mxml_hash, raw["sha256"], raw["size_bytes"])
        inventory["scene_mxml_relative_path"] = mxml_path.relative_to(args.output).as_posix()
        inventory["scene_mbin_relative_path"] = raw["relative_path"]
        assets.append(inventory)
        container_index.extend(refs)
        if position % 25 == 0 or position == len(records):
            print(f"Indexed {position}/{len(records)} generated-base scenes", flush=True)

    if compiler_errors:
        (args.output / "conversion_errors.json").write_text(json.dumps(compiler_errors, indent=2) + "\n", encoding="utf-8")
        raise SystemExit(f"MBIN conversion had {len(compiler_errors)} errors; see {args.output / 'conversion_errors.json'}")
    if len(assets) != len(records):
        raise SystemExit(f"Expected {len(records)} indexed MXML files; found {len(assets)}")

    member_manifest = {
        "schema_version": 1,
        "target": "NMS 7.05 generated-base DecorationTemplates scene assets",
        "build": {"nms_executable": str(args.nms_exe), "nms_executable_sha256": exe_hash},
        "source_archive": {
            "path": str(args.pak),
            "sha256": pak_hash,
            "size_bytes": args.pak.stat().st_size,
            "filter_count": len(records),
            "extractor": "HGPAKtool HGPAKFile.extract(member_names); full-member extraction, not extract_specific",
            "hgpaktool_version": hgpaktool_version,
        },
        "source_table": {"path": str(args.table_mxml), "sha256": table_hash, "entries": len(records)},
        "converter": {
            "name": "MBINCompiler",
            "version": compiler_version,
            "path": str(args.compiler),
            "sha256": compiler_hash,
            "output_header": EXPECTED_COMPILER_HEADER,
        },
        "assets": [
            {
                "table_index": record["table_index"],
                "template_id": record["template_id"],
                "resource_path": record["resource_path"],
                "archive_member": extracted[archive_key(record["resource_path"])]["archive_member"],
                "mbin_relative_path": next(asset["scene_mbin_relative_path"] for asset in assets if asset["table_index"] == record["table_index"]),
                "mbin_size_bytes": next(asset["scene_mbin_size_bytes"] for asset in assets if asset["table_index"] == record["table_index"]),
                "mbin_sha256": next(asset["scene_mbin_sha256"] for asset in assets if asset["table_index"] == record["table_index"]),
                "mxml_relative_path": next(asset["scene_mxml_relative_path"] for asset in assets if asset["table_index"] == record["table_index"]),
                "mxml_sha256": next(asset["scene_mxml_sha256"] for asset in assets if asset["table_index"] == record["table_index"]),
            }
            for record in records
        ],
    }
    manifest_path = args.output / "exact705-generatedbase-scene-members.sha256.json"
    manifest_path.write_text(json.dumps(member_manifest, indent=2) + "\n", encoding="utf-8")
    manifest_hash = sha256_file(manifest_path)

    totals = {
        "scene_assets": len(assets),
        "authored_salvage_crate_refs": sum(asset["authored_salvage_crate_refs"] for asset in assets),
        "authored_footlocker_refs": sum(asset["authored_footlocker_refs"] for asset in assets),
        "container_refs_needing_hierarchy_composition": sum(ref["hierarchy_needs_composition"] for ref in container_index),
        "nonidentity_scene_roots": sum(not asset["scene_root_is_identity"] for asset in assets),
    }
    index = {
        "schema_version": 1,
        "artifact": "authored crate and footlocker transforms in exact 7.05 generated-base scene assets",
        "scope_note": "These are local scene-reference transforms; compose scene hierarchy, generated piece matrix, and optional generated-base root transform to obtain layout/world positions. Looted decorative crate references are excluded.",
        "source_manifest": manifest_path.name,
        "source_manifest_sha256": manifest_hash,
        "source_table_sha256": table_hash,
        "source_archive_sha256": pak_hash,
        "totals": totals,
        "assets": [
            {
                "table_index": asset["table_index"],
                "template_id": asset["template_id"],
                "resource_path": asset["resource_path"],
                "scene_mbin_sha256": asset["scene_mbin_sha256"],
                "scene_mxml_sha256": asset["scene_mxml_sha256"],
                "scene_root_transform": asset["scene_root_transform"],
                "scene_root_is_identity": asset["scene_root_is_identity"],
                "authored_salvage_crate_refs": asset["authored_salvage_crate_refs"],
                "authored_footlocker_refs": asset["authored_footlocker_refs"],
                "requires_hierarchy_composition": asset["requires_hierarchy_composition"],
            }
            for asset in assets
        ],
        "container_references": container_index,
    }
    index_path = args.output / "authored_container_transform_index.json"
    index_path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")

    write_container_csv(args.output / "authored_container_transform_index.csv", container_index)

    inventory_path = args.output / "generatedbase_scene_asset_inventory.csv"
    with inventory_path.open("w", newline="", encoding="utf-8") as stream:
        fields = [
            "table_index",
            "template_id",
            "resource_path",
            "probability",
            "max_per_room",
            "decoration_layer",
            "invalid_room_indexes_json",
            "scene_mbin_sha256",
            "scene_mxml_sha256",
            "authored_salvage_crate_refs",
            "authored_footlocker_refs",
            "scene_root_is_identity",
            "requires_hierarchy_composition",
        ]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for asset in assets:
            writer.writerow(
                {
                    key: json.dumps(asset[key], separators=(",", ":")) if key == "invalid_room_indexes" else asset[key]
                    for key in fields
                    if key in asset
                }
                | {"invalid_room_indexes_json": json.dumps(asset["invalid_room_indexes"], separators=(",", ":"))}
            )

    print(json.dumps({"output": str(args.output), "member_manifest_sha256": manifest_hash, "index": str(index_path), "totals": totals}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
