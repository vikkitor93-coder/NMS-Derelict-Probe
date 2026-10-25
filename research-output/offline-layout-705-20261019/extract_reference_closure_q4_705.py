#!/usr/bin/env python3
"""Q4: extract the transitive SCENEGRAPH reference closure of the 319 generated-base scenes.

Read-only archive pass over the exact 7.05 NMSARC.EntitySceneMBIN.pak (hash-checked).
Each reachable *.SCENE.MBIN target is extracted under
q4-reference-closure-20261020/members/ and converted with the pinned MBINCompiler
7.04.1.3. A manifest records hashes, the reference edges, and the callback-tagged
(CELL/NOCELL/PATH/LAYER) node names found in each target. It does not decide whether
the native importer activates these references; see Q4_PLACEMENT_COUNT_20261020.md.

Run:  python -I -c "import sys,runpy; sys.path.insert(0,r'<this dir>'); runpy.run_path(r'<this file>', run_name='__main__')"
"""
from __future__ import annotations

import hashlib, json, subprocess, sys
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(HERE))
import extract_generatedbase_scene_assets as src  # noqa: E402

PAK = Path(r"G:\SteamLibrary\steamapps\common\No Man's Sky\GAMEDATA\PCBANKS\NMSARC.EntitySceneMBIN.pak")
COMPILER = Path(r"D:\Orca\Temp\mbincompiler-7.04.1-pre3\MBINCompiler.exe")
OUT = HERE / "q4-reference-closure-20261020"
MAP_PREFIXES = ("CELL", "NOCELL", "PATH", "LAYER")


def refs_and_tags(mxml: Path) -> tuple[list[dict], list[str]]:
    root = ET.parse(mxml).getroot()
    refs, tags = [], []
    for node, path in src.walk_scene(root):
        name = src.property_value(node, "Name") or ""
        if path and name.startswith(MAP_PREFIXES):
            tags.append(name)
        target = src.node_attributes(node).get("SCENEGRAPH", "")
        if target.upper().endswith(".SCENE.MBIN"):
            refs.append({"node_name": name, "type": src.property_value(node, "Type") or "",
                         "depth": len(path), "target": src.normalize_resource(target),
                         "transform": src.read_transform(node)})
    return refs, tags


def main() -> int:
    from hgpaktool import HGPAKFile
    if src.sha256_file(PAK) != src.EXPECTED_PAK_SHA256:
        raise SystemExit("EntitySceneMBIN archive hash changed")
    if src.sha256_file(COMPILER) != src.EXPECTED_COMPILER_SHA256:
        raise SystemExit("MBINCompiler hash changed")
    from nms_dungeon_source_catalog_705 import GeneratedBaseSourceCatalog
    catalog = GeneratedBaseSourceCatalog.from_workspace(ROOT)
    roots = {s.scene_path.replace("\\", "/").upper(): s.scene_mxml for s in catalog.sources}
    mxml_for = dict(roots)
    edges: dict[str, list[dict]] = {}
    tags: dict[str, list[str]] = {}
    queue = list(roots)
    extracted: dict[str, dict] = {}
    OUT.mkdir(parents=True, exist_ok=True)
    with HGPAKFile(PAK) as archive:
        names = {n.lower(): n for n in archive.filenames}
        while queue:
            batch = []
            for res in queue:
                if res in edges:
                    continue
                if res not in mxml_for:
                    key = src.archive_key(res)
                    if key not in names:
                        extracted[res] = {"missing_from_archive": True}
                        edges[res], tags[res] = [], []
                        continue
                    batch.append((res, names[key]))
                    continue
                edges[res], tags[res] = refs_and_tags(mxml_for[res])
            if batch:
                for member, payload in archive.extract([m for _, m in batch]):
                    res = next(r for r, m in batch if m.lower() == member.lower())
                    raw = OUT / "members" / Path(*src.safe_member_path(member).parts)
                    raw.parent.mkdir(parents=True, exist_ok=True)
                    raw.write_bytes(payload)
                    mx = raw.with_suffix(".MXML")
                    p = subprocess.run([str(COMPILER), "-y", str(raw)], cwd=raw.parent,
                                       capture_output=True, text=True, timeout=120)
                    if p.returncode != 0 or not mx.is_file():
                        raise SystemExit(f"MBINCompiler failed for {member}: {p.stderr[-800:]}")
                    if src.EXPECTED_COMPILER_HEADER not in mx.read_text(encoding="utf-8", errors="replace")[:240]:
                        raise SystemExit(f"unexpected compiler header {mx}")
                    mxml_for[res] = mx
                    extracted[res] = {"archive_member": member,
                                      "mbin_sha256": hashlib.sha256(payload).hexdigest().upper(),
                                      "mxml_relative_path": mx.relative_to(OUT).as_posix(),
                                      "mxml_sha256": src.sha256_file(mx)}
            queue = sorted({r["target"] for res in list(edges) for r in edges[res]} - set(edges)
                           | {r for r, _ in batch})
            queue = [q for q in queue if q not in edges]

    def closure_tags(res: str, seen=()) -> list[str]:
        out = list(tags.get(res, []))
        for r in edges.get(res, []):
            if r["target"] not in seen:
                out += closure_tags(r["target"], seen + (res,))
        return out

    root_summary = {}
    for res in sorted(roots):
        root_summary[res] = {"direct_tags": len(tags[res]),
                             "transitive_tags": len(closure_tags(res)),
                             "direct_refs": [r["target"] for r in edges[res]]}
    manifest = {
        "schema_version": 1,
        "status": "static closure; native activation of REFERENCE import inferred, not observed",
        "entity_scene_archive_sha256": src.EXPECTED_PAK_SHA256,
        "mbincompiler_sha256": src.EXPECTED_COMPILER_SHA256,
        "root_count": len(roots),
        "reachable_reference_targets": len(extracted),
        "targets": extracted,
        "edges": edges,
        "callback_tags": tags,
        "roots": root_summary,
    }
    (OUT / "reference_closure_manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    n0 = sum(1 for v in root_summary.values() if v["direct_tags"] == 0)
    n1 = sum(1 for v in root_summary.values() if v["direct_tags"] == 0 and v["transitive_tags"] > 0)
    print(json.dumps({"roots": len(roots), "targets": len(extracted),
                      "missing": [k for k, v in extracted.items() if v.get("missing_from_archive")],
                      "roots_without_direct_tags": n0,
                      "of_which_gain_tags_via_references": n1}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
