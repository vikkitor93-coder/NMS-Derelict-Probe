#!/usr/bin/env python3
"""Builds viewer/static/piece_props.json: what each placed scene piece carries besides its walls and fixtures.

  python -I viewer/build_piece_props.py [--check]

The browser needs this to find, from a layout's placed pieces alone (also the published top-100 views, which carry no
hazard data):
  x  extra loot containers (briefcase 2, tall locker 3): [[kind code, x, y, z]] in piece-local metres
     (tools/extra_containers_705.py catalog)
  h  hazards (enemy spawners, turrets, bug sacs, barrels): [[kind letter, x, y, z, mount]] in piece-local metres, mount
     "c" ceiling / "f" floor / "w" wall from the node's up vector (tools/derelict_hazards_705.py, same matrices)
  o  container rotations (all four kinds): [[kind code, RotX, RotY, RotZ]] in degrees, in the scene's own frame and in
     the order the generator lists them (tools/extra_containers_705.py authored_rotations(); model.js piecesTable()
     copies them into the compact piece table, unpack() turns them into each container's orientation)
  p  fixture boxes that are really a container or hazard prop: [[index into the piece index's "fixtures", code]] with
     code "t" tall locker (props/locker), "b" briefcase (props/interactive_case), "X" explosive barrel. They are drawn
     as their own markers, so the viewer leaves them out of the dark fixture blocks. The fixture traversal below is a
     copy of tools/build_piece_meshes_705.py piece_mesh() (fixtures only) and is checked against the index: a piece
     whose fixture list differs is reported and gets no "p".
Scenes are keyed by their upper case resource name, like the piece table. Only scenes with something to show are listed.
Read-only use of the tools modules; the output is deterministic. --check compares the file with a fresh build.
"""
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import derelict_hazards_705 as hz  # noqa: E402
import extra_containers_705 as ec  # noqa: E402
import build_piece_meshes_705 as bpm  # noqa: E402  (scene(), member(), trs(), matmul(), mesh_aabb(); read-only use)

OUT = Path(__file__).resolve().parent / "static" / "piece_props.json"
INDEX = Path("D:/Orca/NMS-Derelict-Probe-analysis/meshcache/index.json")
SHOWN = {"floater_spawner", "fast_floater_spawner", "drone_spawner", "bug_spawner", "turret", "hanging_sac", "pillar_sac",
         "fiend_egg", "explosive_barrel"}  # slime and slime doors are left out (doors are drawn from the pieces already)


PROP_CODES = (("/props/locker.scene.mbin", "t"), ("/props/interactive_case.scene.mbin", "b"), ("explodingbarrel.scene.mbin", "X"))
IDENT = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]


def fixture_sources(scene_name):
    """[(box, target scene)] in the order tools/build_piece_meshes_705.piece_mesh() lists the piece's fixtures."""
    out, stack = [], set()

    def fixture(mat, target):
        if not any(k in target for k in bpm.FIXTURE_REFS) or any(k in target for k in bpm.NOT_FIXTURES):
            return
        box = bpm.mesh_aabb(target)
        if not box:
            return
        lo, hi = [math.inf] * 3, [-math.inf] * 3
        for cx in (box[0][0], box[1][0]):
            for cy in (box[0][1], box[1][1]):
                for cz in (box[0][2], box[1][2]):
                    q = [mat[i][0] * cx + mat[i][1] * cy + mat[i][2] * cz + mat[i][3] for i in range(3)]
                    for i in range(3):
                        lo[i], hi[i] = min(lo[i], q[i]), max(hi[i], q[i])
        if lo[1] < 1.2 and hi[1] - lo[1] > 0.5 and (hi[0] - lo[0]) * (hi[2] - lo[2]) > 0.25:
            out.append(([round(v, 2) for v in lo + hi], target))

    def visit_scene(name, mat):
        root = None if name in stack or len(stack) > 24 else bpm.scene(name)
        if root is None:
            return
        stack.add(name)
        visit(root, mat, True)
        stack.discard(name)

    def visit(n, parent, is_root=False):
        mat = parent if is_root else bpm.matmul(parent, bpm.trs(n["t"]))
        if n["type"] == "REFERENCE" and n["attrs"].get("SCENEGRAPH", "").upper().endswith(".SCENE.MBIN"):
            target = bpm.member(n["attrs"]["SCENEGRAPH"])
            if any(k in target for k in bpm.SKIP_REFS):
                for it in n["inst"] or [None]:
                    fixture(mat if it is None else bpm.matmul(mat, bpm.trs(it)), target)
                return
            for it in n["inst"] or [None]:
                visit_scene(target, mat if it is None else bpm.matmul(mat, bpm.trs(it)))
        if n["type"] in ("COLLISION", "LIGHT"):
            return
        for c in n["children"]:
            visit(c, mat)

    visit_scene(scene_name, IDENT)
    return out


def build():
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    names = sorted(n for n in index if n != "_meta")
    props = {}
    for name in names:
        src = fixture_sources(bpm.member(name))
        if [b for b, _t in src] != index[name].get("fixtures", []):
            print(f"warning: {name}: fixture list differs from the index, no fixture tags", file=sys.stderr)
        else:
            p = [[k, code] for k, (_b, t) in enumerate(src) for key, code in PROP_CODES if key in t]
            if p:
                props.setdefault(name.upper(), {})["p"] = p
        found, _missing = hz.piece_hazards(name)
        h = []
        for target, _node, m in found:
            info = hz.CATALOG[target]
            if info["kind"] not in SHOWN:
                continue
            up_y = m[1][1]
            mount = "c" if up_y < -0.5 else ("f" if up_y > 0.5 else "w")
            h.append([hz.SYMBOL[info["kind"]], round(m[0][3], 5), round(m[1][3], 5), round(m[2][3], 5), mount])
        if h:
            props.setdefault(name.upper(), {})["h"] = h
    for scene, rows in ec._catalog(ec.EXTRA_INDEX, ec.EXTRA_KINDS).items():
        props.setdefault(scene.upper(), {})["x"] = [
            [ec.KIND_CODES[r["container_kind"]], float(r["direct_local_x"]), float(r["direct_local_y"]), float(r["direct_local_z"])] for r in rows]
    for scene, rows in ec.authored_rotations().items():
        props.setdefault(scene.upper(), {})["o"] = rows
    return {"v": 1, "scenes": dict(sorted(props.items()))}


def main():
    text = json.dumps(build(), separators=(",", ":"), sort_keys=False) + "\n"
    if "--check" in sys.argv:
        same = OUT.exists() and OUT.read_text(encoding="utf-8") == text
        print("piece_props.json is current" if same else "piece_props.json differs from a fresh build")
        return 0 if same else 1
    OUT.write_text(text, encoding="utf-8")
    d = json.loads(text)["scenes"]
    print(f"{OUT}: {len(d)} scenes, {sum(len(v.get('h', [])) for v in d.values())} hazards, "
          f"{sum(len(v.get('x', [])) for v in d.values())} extra containers, {sum(len(v.get('o', [])) for v in d.values())} container rotations, "
          f"{sum(len(v.get('p', [])) for v in d.values())} tagged fixtures, {len(text)} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
