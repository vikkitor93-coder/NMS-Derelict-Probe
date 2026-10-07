"""Map current abandoned-freighter entrance choices to dungeon table presets."""

from __future__ import annotations

import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

COMPONENT_PATH = (
    "MODELS/SPACE/POI/PARTS/DUNGEON_ENTRANCE/ENTITIES/"
    "DUNGEONENTRANCE.ENTITY.MBIN"
)
TABLE_PATH = "METADATA/REALITY/TABLES/FREIGHTERDUNGEONSTABLE.MBIN"


def prop(parent: ET.Element, name: str) -> ET.Element:
    found = parent.find(f"./Property[@name='{name}']")
    if found is None:
        raise ValueError(f"Missing {name} property")
    return found


def value(parent: ET.Element, name: str) -> str:
    result = prop(parent, name).get("value")
    if result is None:
        raise ValueError(f"Missing {name} value")
    return result


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_report(component_xml: Path, table_xml: Path,
                 component_mbin: Path, table_mbin: Path) -> dict:
    component = ET.parse(component_xml).getroot().find(
        ".//Property[@name='GcAbandonedFreighterComponentData']"
    )
    if component is None:
        raise ValueError("Abandoned freighter component not found")
    outpost = ET.parse(component_xml).getroot().find(
        ".//Property[@name='GcOutpostComponentData']"
    )
    if outpost is None or value(outpost, "AbandonedFreighter").lower() != "true":
        raise ValueError("Entity is not marked as an abandoned freighter")
    root_scene = value(prop(component, "DungeonRootScene"), "Filename")
    options_node = prop(component, "DungeonOptions")
    choices = options_node.findall("./Property[@name='DungeonOptions']")
    if not choices:
        raise ValueError("Selected component has no DungeonOptions")

    table_root = ET.parse(table_xml).getroot()
    table_entries = prop(table_root, "Dungeons").findall(
        "./Property[@name='Dungeons']"
    )
    table = {}
    for entry in table_entries:
        name = value(entry, "Name")
        if name in table:
            raise ValueError(f"Duplicate table preset: {name}")
        params = prop(entry, "DungeonParams")
        table[name] = {
            "rooms": int(value(params, "Rooms")),
            "size": [int(value(params, axis)) for axis in ("SizeX", "SizeY", "SizeZ")],
        }

    mapped = []
    seen = set()
    for index, choice in enumerate(choices):
        name = value(choice, "Name")
        if name in seen:
            raise ValueError(f"Duplicate component choice: {name}")
        if name not in table:
            raise ValueError(f"Component choice missing from table: {name}")
        seen.add(name)
        mapped.append({
            "index": index,
            "name": name,
            "weighting": value(choice, "Weighting"),
            "dungeon_params": table[name],
        })
    if seen != set(table):
        raise ValueError(f"Unreferenced table presets: {sorted(set(table) - seen)}")

    return {
        "schema_version": 1,
        "evidence_class": "measured-static-game-assets",
        "component_source": COMPONENT_PATH,
        "component_sha256": sha256(component_mbin),
        "table_source": TABLE_PATH,
        "table_sha256": sha256(table_mbin),
        "dungeon_root_scene": root_scene,
        "dungeon_options": mapped,
        "all_choices_match_table": True,
        "selection_algorithm_verified": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("component_xml", type=Path)
    parser.add_argument("table_xml", type=Path)
    parser.add_argument("component_mbin", type=Path)
    parser.add_argument("table_mbin", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = build_report(args.component_xml, args.table_xml,
                          args.component_mbin, args.table_mbin)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Mapped {len(report['dungeon_options'])} options: {args.output}")


if __name__ == "__main__":
    main()
