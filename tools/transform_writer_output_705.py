#!/usr/bin/env python3
"""Apply the offline A4720 scene and authored-container transforms to a writer run."""
from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OFF = ROOT / "research-output/offline-layout-705-20261019"


def entrance_origin(preset_index: int) -> tuple[int, int, int]:
    path = ROOT / "research-output/exact705-dungeon-inputs-20261019/metadata/reality/tables/freighterdungeonstable.MXML"
    root = ET.parse(path).getroot()
    for node in root.iter("Property"):
        if node.get("name") == "Dungeons" and int(node.get("_index", "-1")) == preset_index:
            fields = {p.get("name"): p.get("value") for p in node.iter("Property")}
            return tuple(int(fields[f"Entrance{axis}"]) for axis in "XYZ")
    raise ValueError(f"preset index {preset_index} not found in exact-build preset MXML")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True, help="emulate_writer_705_assets.py output directory")
    parser.add_argument("--out", help="destination directory; defaults to --run-dir")
    args = parser.parse_args()
    run_dir = Path(args.run_dir).resolve()
    out_dir = Path(args.out).resolve() if args.out else run_dir
    summary = json.loads((run_dir / "last_run_summary.json").read_text(encoding="utf-8"))
    if summary.get("result", {}).get("ok") != "0x1":
        raise SystemExit("writer did not return normally; refusing to transform incomplete output")
    inputs = summary.get("inputs", {})
    if "preset_index" not in inputs:
        raise SystemExit("run summary lacks preset_index; rerun with the current emulator script")

    # Install the EC00-derived orientation-2 dimension correction used by the
    # asset-built source-row generator before materializing scene transforms.
    sys.path.insert(0, str(ROOT / "tools"))
    import build_source_rows_from_assets  # noqa: F401

    sys.path.insert(0, str(OFF))
    from nms_dungeon_a2780_search_705 import A2780Placement
    from nms_dungeon_instance_705 import build_scene_instance_transforms, transform_authored_containers
    from nms_dungeon_reference_closure_q4_705 import Q4SourceCatalog
    from nms_dungeon_variable_placement_705 import VariablePlacementAppendRecord

    placements_data = json.loads((run_dir / "emu_placements.json").read_text(encoding="utf-8"))
    placements = []
    for item in placements_data:
        row = int(item["row"])
        origin = (int(item["xy"][0]), int(item["xy"][1]), int(item["z"]))
        room = int(item["room"])
        record = VariablePlacementAppendRecord(row, origin, 0, 0, 0)
        placements.append(A2780Placement(record, room, bytes(16), "", 0, 0, "writer-output", "", row))

    catalog = Q4SourceCatalog.from_workspace(ROOT)
    transforms = build_scene_instance_transforms(
        placements, catalog=catalog, grid_origin_xyz=entrance_origin(int(inputs["preset_index"]))
    )
    index = ROOT / "research-output/exact705-generatedbase-scenes-20261019/authored_container_transform_index.csv"
    containers = transform_authored_containers(transforms, container_index_csv=index)
    scene_rows = [asdict(item) for item in transforms]
    container_rows = [asdict(item) for item in containers]
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "a4720_scene_transforms_candidate.json").write_text(json.dumps(scene_rows, indent=2), encoding="utf-8")
    (out_dir / "authored_containers_candidate.json").write_text(json.dumps(container_rows, indent=2), encoding="utf-8")
    report = {
        "status": "candidate-transforms-derived",
        "inputs": inputs,
        "writer_room_count": int(summary["result"]["rax"], 16),
        "scene_transform_count": len(scene_rows),
        "authored_container_count": len(container_rows),
        "container_counts": {
            kind: sum(row["container_kind"] == kind for row in container_rows)
            for kind in sorted({row["container_kind"] for row in container_rows})
        },
        "bounds_sources": sorted({row["bounds_source"] for row in scene_rows}),
        "callback_order_sources": sorted({row["callback_order_source"] for row in scene_rows}),
        "limitation": "Offline model output; authored bounds/callback order and recursive REFERENCE activation remain qualified assumptions where identified by the source catalog.",
    }
    (out_dir / "transform_summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
