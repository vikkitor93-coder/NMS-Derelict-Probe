#!/usr/bin/env python3
"""Extra loot containers in a generated NMS 7.05 derelict: the briefcase and the tall locker.

The generators list salvage crates and crew footlockers in derelict.json "containers" (live-validated; the atlas
ranks systems by them). Two more lootable props sit in the same generated-base scenes, referenced the same way
(direct REFERENCE children of identity scene roots):

  container_kind  prop scene                          entity                    reward table id
  briefcase       .../SPACEBASE/PROPS/INTERACTIVE_CASE   INTERACTIVE_CASE/SMALLCASE   R_ABAND_CASE
  tall_locker     .../SPACEBASE/PROPS/LOCKER             LOCKER/LOCKER                R_ABAND_LOCK

Their authored positions come from research-output/exact705-generatedbase-scenes-20261019/
authored_extra_container_transform_index.csv (tools/extract_generatedbase_scene_assets.py --extra-only). Each placed
scene instance's matrix moves them to layout space, with the same float32 arithmetic the generator uses for crates
(SceneInstanceTransform.transform_point). Because they only depend on d["instances"], this also works on any layout
stored before this tool existed. Evidence: research-output/CONTAINER_TYPES_20261020.md.

  extra_containers(d)  -> list of dicts, same fields as derelict.json "containers"
  extra_counts(d)      -> {"briefcase": n, "tall_locker": m}   (always both keys)
  python -I tools/extra_containers_705.py --check [ADDRESS ...]
      for every generated layout: the same code with the main crate/footlocker index must reproduce
      d["containers"] exactly (proves the instance -> container path), then prints the extra counts.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OFF = ROOT / "research-output/offline-layout-705-20261019"
SCENES = ROOT / "research-output/exact705-generatedbase-scenes-20261019"
EXTRA_INDEX = SCENES / "authored_extra_container_transform_index.csv"
MAIN_INDEX = SCENES / "authored_container_transform_index.csv"
EXTRA_KINDS = ("briefcase", "tall_locker")
# Kind codes shared by every compact form (viewer/static/model.js, tools/derelict_view.py): 0 and 1 in view "c",
# 2 and 3 in view "x".
KIND_CODES = {"salvage_crate": 0, "crew_footlocker": 1, "briefcase": 2, "tall_locker": 3}
GENERATED = Path("D:/Orca/NMS-Derelict-Probe-analysis/emu/fastgen/generated")

_catalogs: dict[tuple[str, tuple[str, ...]], dict[str, list[dict[str, str]]]] = {}


def _catalog(path: Path, kinds: tuple[str, ...]) -> dict[str, list[dict[str, str]]]:
    key = (str(path), kinds)
    if key not in _catalogs:
        by_scene: dict[str, list[dict[str, str]]] = {}
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                if row.get("container_kind", "") not in kinds:
                    continue
                if row.get("hierarchy_needs_composition", "").strip().lower() == "true":
                    raise NotImplementedError(f"{row.get('scene_node_name')} in {row.get('template_id')} needs ancestor composition")
                by_scene.setdefault(row["scene_resource"].replace("\\", "/").upper(), []).append(row)
        _catalogs[key] = by_scene
    return _catalogs[key]


def _transform():
    if str(OFF) not in sys.path:
        sys.path.insert(0, str(OFF))
    from nms_dungeon_instance_705 import SceneInstanceTransform
    return SceneInstanceTransform


def containers_from_instances(instances, index_csv: Path, kinds: tuple[str, ...]) -> list[dict]:
    """Same loop and output order as nms_dungeon_instance_705.transform_authored_containers (instance order, then
    index row order), for any set of kinds."""
    SceneInstanceTransform = _transform()
    by_scene = _catalog(index_csv, kinds)
    out = []
    for i in instances:
        rows = by_scene.get(i["scene_resource"], ())
        if not rows:
            continue
        t = SceneInstanceTransform(**{k: i[k] for k in SceneInstanceTransform.__dataclass_fields__})
        for row in rows:
            local = (float(row["direct_local_x"]), float(row["direct_local_y"]), float(row["direct_local_z"]))
            out.append({"room_index": i["room_index"], "source_map_index": i["source_map_index"], "template_id": i["template_id"],
                        "scene_resource": i["scene_resource"], "scene_node_name": row["scene_node_name"],
                        "container_kind": row["container_kind"], "target_scene_resource": row["target_scene_resource"],
                        "local_xyz": list(local), "layout_local_xyz": list(t.transform_point(local))})
    return out


def extra_containers(d: dict) -> list[dict]:
    """Briefcases and tall lockers of a generated derelict (dict with "instances")."""
    return containers_from_instances(d["instances"], EXTRA_INDEX, EXTRA_KINDS)


def extra_counts(d: dict) -> dict[str, int]:
    cs = d["extra_containers"] if "extra_containers" in d else extra_containers(d)
    return {k: sum(c["container_kind"] == k for c in cs) for k in EXTRA_KINDS}


def check(addresses, generated=GENERATED) -> bool:
    """Main-index reproduction of d["containers"] for every layout, plus extra counts and stored-key consistency."""
    bad, tot, n = [], {k: 0 for k in EXTRA_KINDS}, 0
    hist = {k: {} for k in EXTRA_KINDS}
    for a in addresses:
        p = generated / a / "derelict.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        if "instances" not in d:
            continue
        n += 1
        again = containers_from_instances(d["instances"], MAIN_INDEX, ("salvage_crate", "crew_footlocker"))
        if again != d["containers"]:
            bad.append((a, "main containers differ"))
        extra = extra_containers(d)
        if "extra_containers" in d and d["extra_containers"] != extra:
            bad.append((a, "stored extra_containers differ"))
        c = extra_counts({"extra_containers": extra})
        if "extra_container_kinds" in d and d["extra_container_kinds"] != c:
            bad.append((a, "stored extra_container_kinds differ"))
        for k in EXTRA_KINDS:
            tot[k] += c[k]
            hist[k][c[k]] = hist[k].get(c[k], 0) + 1
    print(f"{n} layouts: crate/footlocker containers reproduced from instances for {n - sum(m == 'main containers differ' for _, m in bad)}")
    for k in EXTRA_KINDS:
        h = hist[k]
        print(f"  {k}: total {tot[k]}, mean {tot[k] / max(n, 1):.2f}, per-derelict histogram {dict(sorted(h.items()))}")
    for a, m in bad[:20]:
        print("  MISMATCH", a, m)
    return not bad


if __name__ == "__main__" and sys.argv[1:2] == ["--check"]:
    picks = sys.argv[2:] or sorted(p.name for p in GENERATED.iterdir() if (p / "derelict.json").exists())
    sys.exit(0 if check(picks) else 1)
