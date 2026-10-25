#!/usr/bin/env python3
"""Derive A4720 instance transforms + authored containers from emulator run B, compare to replay (new file)."""
import csv, json, sys, math
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools")); sys.path.insert(0, str(ROOT / "tools"))
import transform_writer_output_705 as T
import build_source_rows_from_assets  # orientation-2 fix
OFF = ROOT / "research-output/offline-layout-705-20261019"
sys.path.insert(0, str(OFF))
from nms_dungeon_a2780_search_705 import A2780Placement
from nms_dungeon_instance_705 import build_scene_instance_transforms, transform_authored_containers
from nms_dungeon_reference_closure_q4_705 import Q4SourceCatalog
from nms_dungeon_variable_placement_705 import VariablePlacementAppendRecord
RUN = Path("D:/Orca/NMS-Derelict-Probe-analysis/emu/assets_run_B")
OUT = Path("D:/Orca/NMS-Derelict-Probe-analysis/emu/positions"); OUT.mkdir(parents=True, exist_ok=True)
REP = ROOT / "research-output/known-derelict-replay-20261019"
TOL = 1e-4
items = json.loads((RUN / "emu_placements.json").read_text())
pl = [A2780Placement(VariablePlacementAppendRecord(int(i["row"]), (int(i["xy"][0]), int(i["xy"][1]), int(i["z"])), 0, 0, 0),
      int(i["room"]), bytes(16), "", 0, 0, "writer-output", "", int(i["row"])) for i in items]
org = T.entrance_origin(7)
tr = build_scene_instance_transforms(pl, catalog=Q4SourceCatalog.from_workspace(ROOT), grid_origin_xyz=org)
cont = transform_authored_containers(tr, container_index_csv=ROOT/"research-output/exact705-generatedbase-scenes-20261019/authored_container_transform_index.csv")
(OUT/"scene_transforms.json").write_text(json.dumps([asdict(t) for t in tr], indent=1))
(OUT/"containers.json").write_text(json.dumps([asdict(c) for c in cont], indent=1))
print("fields", list(asdict(tr[0]).keys())); print("cfields", list(asdict(cont[0]).keys())); print("origin", org)
