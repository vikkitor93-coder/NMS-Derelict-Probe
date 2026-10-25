"""Re-extract every game table / scene asset the derelict chain reads, from ANY NMS install, into a build folder.

    python -I tools/extract_build_data_705.py <game folder (the one with Binaries/ and GAMEDATA/)> <out data dir>
        [--compiler MBINCompiler.exe] [--reproduce-705] [--check-against-705]

Writes <out>/ with the SAME relative layout the 7.05 workspace uses, so a build profile can point data_root at it:
  research-output/exact705-dungeon-inputs-20261019/   preset table + dungeon entities (MBIN + MXML + provenance.json)
  research-output/generatedbase-table-705/            GeneratedBaseTemplatesTable (MBIN + MXML)
  research-output/exact705-generatedbase-scenes-20261019/   the 319 decoration scenes + container indexes
                                                      (tools/extract_generatedbase_scene_assets.py, run unchanged with
                                                      its 7.05 hash pins replaced by this game's hashes in memory)
  writer-table/        MBIN + MXML the native writer loads    asset_source_rows.bin   writer source rows (rebuilt)
  spacepoi/spacepoitable.mbin    shipwright/{globals,metadata}  (space-POI step)    raw/  raw members
  fingerprints.json    member hashes + the archive / table hashes the offline catalog checks
  derived_checks.json  values the Python predictors hard-code, re-read from this game's data where possible
The 7.05 outputs in research-output/ are never written. Folder names keep the "705" in them on purpose (the code
looks them up by those names). Read-only on the game folder.
--reproduce-705 uses the compiler versions of the original 7.05 extraction (7.04.1.3 for the table and scenes,
7.07.0.1 for the rest) so a 7.05 re-extraction can be compared byte for byte (--check-against-705).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from importlib.metadata import version
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import build_profile_705 as BP  # noqa: E402

ROOT = HERE.parent
# stage3 (M1): MBINCompiler locations can be overridden with NMS_MBC_707 / NMS_MBC_704 (defaults unchanged).
MBC_707 = Path(os.environ.get("NMS_MBC_707", "D:/Orca/Temp/mbincompiler-7.07.0-pre1/MBINCompiler.exe"))
MBC_704 = Path(os.environ.get("NMS_MBC_704", "D:/Orca/Temp/mbincompiler-7.04.1-pre3/MBINCompiler.exe"))
DUNGEON = "research-output/exact705-dungeon-inputs-20261019"
TABLE = "research-output/generatedbase-table-705"
SCENES = "research-output/exact705-generatedbase-scenes-20261019"


def sha(p) -> str:
    return BP.sha256_file(p)


def convert(compiler: Path, mbin: Path) -> Path:
    """MBIN -> MXML next to it (MBINCompiler -y). Returns the MXML path."""
    p = subprocess.run([str(compiler), "--input-format=MBIN", "-y", str(mbin)], cwd=mbin.parent, capture_output=True,
                       text=True, timeout=300, creationflags=0x08000000)
    out = mbin.with_suffix(".MXML")
    if p.returncode or not out.exists():
        raise RuntimeError(f"MBINCompiler failed on {mbin.name}: {(p.stderr or p.stdout).strip()[-300:]}")
    return out


def presets_from_entrance(mxml: Path) -> list:
    root = ET.parse(mxml).getroot()
    out = []
    for node in root.iter("Property"):
        if node.get("value") == "GcFreighterDungeonChoice":
            f = {p.get("name"): p.get("value") for p in node if p.tag == "Property"}
            out.append([f.get("Name"), float(f.get("Weighting", "nan"))])
    return out


def ref_dungeon_entrance(mxml: Path):
    root = ET.parse(mxml).getroot()
    for node in root.iter("Property"):
        if node.get("value") == "TkSceneNodeData":
            name = next((p.get("value") for p in node if p.get("name") == "Name"), "")
            if "REFDUNGEONENTRANCE" in (name or "").upper().replace("_", ""):
                tr = next((p for p in node if p.get("name") == "Transform"), None)
                if tr is not None:
                    f = {p.get("name"): float(p.get("value")) for p in tr.iter("Property") if p.get("value") not in (None, "")
                         and p.get("name") in ("TransX", "TransY", "TransZ")}
                    return [f.get("TransX"), f.get("TransY"), f.get("TransZ")]
    return None


def extract(game: Path, out: Path, compiler: Path = MBC_707, table_compiler: Path | None = None,
            scene_compiler: Path | None = None, label: str = "new", log=print) -> dict:
    game, out = Path(game), Path(out)
    if out.resolve() in (ROOT.resolve(), (ROOT / "research-output").resolve()):
        raise SystemExit("refusing to write into the 7.05 workspace")
    table_compiler = table_compiler or compiler
    scene_compiler = scene_compiler or compiler
    banks = game / "GAMEDATA" / "PCBANKS"
    exe = game / "Binaries" / "NMS.exe"
    t0 = time.time()
    report = {"game": str(game), "exe_sha256": sha(exe), "out": str(out), "steps": []}
    step = lambda name, detail="": (report["steps"].append([name, detail]), log(f"[extract] {name} {detail}"))
    raw = BP.extract_members(game, out / "raw")
    step("raw members", f"{sum(1 for v in raw.values() if v)}/{len(raw)}")
    # 1. dungeon inputs (preset table + entities) with provenance, as the 7.05 extraction wrote it
    d = out / DUNGEON
    assets = []
    for key in ("freighterdungeonstable", "dungeon_entity", "dungeonentrance_entity"):
        member = BP.GAME_MEMBERS[key][1]
        dest = d / member
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(raw[key], dest)
        convert(compiler, dest)
        assets.append({"member": member, "relative_path": member, "size_bytes": dest.stat().st_size, "sha256": sha(dest)})
    pre_sha = sha(banks / "NMSARC.Precache.pak")
    (d / "provenance.json").write_text(json.dumps({
        "schema_version": 1, "build": f"NMS {label}; executable SHA-256 {report['exe_sha256']}",
        "source_archive": str(banks / "NMSARC.Precache.pak"), "source_archive_sha256": pre_sha,
        "extractor": "hgpaktool.HGPAKFile.extract(filters), full-member extraction (not extract_specific)",
        "hgpaktool_version": version("hgpaktool"), "assets": assets}, indent=2) + "\n", encoding="utf-8")
    step("dungeon inputs", str(d))
    # 2. generated-base table: catalog copy (research-output layout) and the writer's copy
    t = out / TABLE
    t.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(raw["generatedbasetemplatestable"], t / "generatedbasetemplatestable.mbin")
    table_mxml = convert(table_compiler, t / "generatedbasetemplatestable.mbin")
    w = out / "writer-table"
    w.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(raw["generatedbasetemplatestable"], w / "generatedbasetemplatestable.mbin")
    convert(compiler, w / "generatedbasetemplatestable.mbin")
    step("generated-base table", str(t))
    # 3. the 319 decoration scenes + container indexes: the existing extractor, hash pins replaced in memory
    import extract_generatedbase_scene_assets as XS
    probe = out / "raw" / "_compiler_header"
    probe.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(raw["dungeon_entity"], probe / "probe.mbin")
    header = convert(scene_compiler, probe / "probe.mbin").read_text(encoding="utf-8").splitlines()[1]
    XS.EXPECTED_PAK_SHA256 = sha(banks / "NMSARC.EntitySceneMBIN.pak")
    XS.EXPECTED_EXE_SHA256 = report["exe_sha256"]
    XS.EXPECTED_TABLE_SHA256 = sha(table_mxml)
    XS.EXPECTED_COMPILER_SHA256 = sha(scene_compiler)
    XS.EXPECTED_COMPILER_HEADER = header.replace("<!--File created using ", "").replace("-->", "").strip()
    XS.EXPECTED_HGPAKTOOL_VERSION = version("hgpaktool")
    s = out / SCENES
    base_args = ["--pak", str(banks / "NMSARC.EntitySceneMBIN.pak"), "--nms-exe", str(exe), "--table-mxml", str(table_mxml),
                 "--compiler", str(scene_compiler), "--output", str(s)]
    saved = sys.argv
    try:
        for extra in ([], ["--extra-only"]):
            sys.argv = ["extract_generatedbase_scene_assets.py", *base_args, *extra]
            XS.main()
    finally:
        sys.argv = saved
    step("scenes + container indexes", str(s))
    # 4. space POI table and the Shipwright game-data snapshot
    (out / "spacepoi").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(raw["spacepoitable"], out / "spacepoi" / "spacepoitable.mbin")
    from hgpaktool import HGPAKFile
    sw = out.parent / "shipwright" if out.name == "data" else out / "shipwright"
    (sw / "globals").mkdir(parents=True, exist_ok=True)
    (sw / "metadata").mkdir(parents=True, exist_ok=True)
    with HGPAKFile(banks / "NMSARC.globals.pak") as a:
        for name, blob in a.extract(filters=["*.global.mbin"]):
            (sw / "globals" / Path(name).name).write_bytes(blob)
    sys.path.insert(0, str(BP.SHIPWRIGHT))
    try:
        from nms_procgen.emu import METADATA_FILES
    except Exception:
        METADATA_FILES = ("aispaceshipmanager.mbin", "biomefilenames.mbin", "biomelistperstartype.mbin")
    need = set(METADATA_FILES)
    for pak in [banks / "NMSARC.Precache.pak"] + sorted(banks.glob("*.pak")):
        if not need:
            break
        if any(x in pak.name for x in ("Tex", "audio", "Mesh", "Shader")):
            continue
        with HGPAKFile(pak) as a:
            for name, blob in a.extract(filters=["*" + n for n in sorted(need)]):
                if Path(name).name.lower() in need:
                    (sw / "metadata" / Path(name).name.lower()).write_bytes(blob)
                    need.discard(Path(name).name.lower())
    step("space POI + Shipwright snapshot", f"{sw} (missing metadata: {sorted(need) or 'none'})")
    # 5. fingerprints (the offline catalog checks these) and the writer source rows rebuilt from this data
    fp = {"members": BP.game_fingerprints(game, scene_manifest=out / SCENES / "exact705-generatedbase-scene-members.sha256.json"), "generatedbase_mxml_sha256": sha(table_mxml),
          "precache_pak_sha256": pre_sha, "entity_scene_pak_sha256": XS.EXPECTED_PAK_SHA256, "exe_sha256": report["exe_sha256"]}
    (out / "fingerprints.json").write_text(json.dumps(fp, indent=1), encoding="utf-8")
    sys.path.insert(0, str(ROOT / "research-output/offline-layout-705-20261019"))
    import nms_dungeon_offline as OFF
    saved_fp = (OFF.GENERATEDBASE_MXML_SHA256, OFF.PRECACHE_PAK_SHA256, OFF.ENTITY_SCENE_PAK_SHA256, OFF.NMS_EXE_SHA256)
    OFF.GENERATEDBASE_MXML_SHA256, OFF.PRECACHE_PAK_SHA256 = fp["generatedbase_mxml_sha256"], pre_sha
    OFF.ENTITY_SCENE_PAK_SHA256, OFF.NMS_EXE_SHA256 = fp["entity_scene_pak_sha256"], report["exe_sha256"]
    try:
        import build_source_rows_from_assets as BS
        old_root = BS.ROOT
        BS.ROOT = out
        try:
            rows = BS.build_rows()
        finally:
            BS.ROOT = old_root
    finally:
        OFF.GENERATEDBASE_MXML_SHA256, OFF.PRECACHE_PAK_SHA256, OFF.ENTITY_SCENE_PAK_SHA256, OFF.NMS_EXE_SHA256 = saved_fp
    (out / "asset_source_rows.bin").write_bytes(rows)
    step("writer source rows", f"{len(rows) // 0x2B0} rows, sha256 {hashlib.sha256(rows).hexdigest()[:16]}")
    # 6. constants the predictors hard-code
    import derelict_seed_preset_705 as D
    import predict_end_reward_705 as P
    derived = {}
    try:
        pr = presets_from_entrance(d / BP.GAME_MEMBERS["dungeonentrance_entity"][1].replace(".mbin", ".MXML"))
        derived["PRESETS"] = {"game": pr, "code": [list(x) for x in D.PRESETS],
                              "same": [[a, round(b, 6)] for a, b in pr] == [[a, round(b, 6)] for a, b in D.PRESETS]}
    except Exception as exc:
        derived["PRESETS"] = {"error": repr(exc)}
    try:
        ds = out / "raw" / "dungeon_scene"
        ds.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(raw["dungeon_scene"], ds / "dungeon.scene.mbin")
        ref = ref_dungeon_entrance(convert(compiler, ds / "dungeon.scene.mbin"))
        derived["ENTRANCE_REF"] = {"game": ref, "code": list(P.ENTRANCE_REF),
                                   "same": ref is not None and all(abs(a - b) < 1e-5 for a, b in zip(ref, P.ENTRANCE_REF))}
    except Exception as exc:
        derived["ENTRANCE_REF"] = {"error": repr(exc)}
    want = BP.load_profile(BP.BASE_ID).get("fingerprints", {}).get("members", {})
    derived["tables_vs_705"] = {k: ("same" if fp["members"].get(k) == v else "CHANGED") for k, v in want.items()}
    derived["note"] = ("rewardtable / gameplayglobals CHANGED => the crate-loot and end-reward tables in "
                       "predict_crate_loot_705.TABLES / predict_end_reward_705 (R_FREI_TECH, QUALITY_WEIGHTS) must be "
                       "re-derived by hand and put into the build profile's overrides; DUNGEON_D and TERMINAL_LOCAL are "
                       "measured / scene values: a changed dungeon_scene or scenes fingerprint needs a re-measure")
    (out / "derived_checks.json").write_text(json.dumps(derived, indent=1), encoding="utf-8")
    step("derived checks", json.dumps({k: v.get("same") if isinstance(v, dict) and "same" in v else v
                                       for k, v in derived.items() if k != "note"})[:400])
    report["seconds"] = round(time.time() - t0, 1)
    (out / "extract_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    return report


def check_against_705(out: Path) -> dict:
    """Byte comparison of a 7.05 re-extraction with the 7.05 workspace files the chain reads."""
    pairs = [(ROOT / DUNGEON / BP.GAME_MEMBERS[k][1], out / DUNGEON / BP.GAME_MEMBERS[k][1])
             for k in ("freighterdungeonstable", "dungeon_entity", "dungeonentrance_entity")]
    pairs += [(a.with_suffix(".MXML"), b.with_suffix(".MXML")) for a, b in pairs]
    pairs += [(ROOT / TABLE / "generatedbasetemplatestable.mbin", out / TABLE / "generatedbasetemplatestable.mbin"),
              (ROOT / TABLE / "generatedbasetemplatestable.MXML", out / TABLE / "generatedbasetemplatestable.MXML"),
              (Path(BP.builtin_705()["writer_table_mbin"]), out / "writer-table/generatedbasetemplatestable.mbin"),
              (Path(BP.builtin_705()["writer_table_mxml"]), out / "writer-table/generatedbasetemplatestable.MXML"),
              (Path(BP.builtin_705()["asset_rows"]), out / "asset_source_rows.bin"),
              (Path(BP.builtin_705()["spacepoi_dir"]) / "spacepoitable.mbin", out / "spacepoi/spacepoitable.mbin")]
    for name in ("authored_container_transform_index.csv", "authored_extra_container_transform_index.csv"):
        pairs.append((ROOT / SCENES / name, out / SCENES / name))
    src = ROOT / SCENES / "members"
    pairs += [(f, out / SCENES / "members" / f.relative_to(src)) for f in sorted(src.rglob("*")) if f.is_file()]
    res = {"same": 0, "different": [], "missing": []}
    for a, b in pairs:
        if not b.exists():
            res["missing"].append(str(b))
        elif a.read_bytes() == b.read_bytes():
            res["same"] += 1
        else:
            res["different"].append(str(b.relative_to(out)))
    man = "exact705-generatedbase-scene-members.sha256.json"     # paths inside differ; the asset list must not
    strip = lambda doc: [{k: v for k, v in a.items()} for a in doc["assets"]]
    try:
        same_assets = strip(json.loads((ROOT / SCENES / man).read_text(encoding="utf-8"))) ==             strip(json.loads((out / SCENES / man).read_text(encoding="utf-8")))
    except OSError:
        same_assets = False
    res["same" if same_assets else "different"] = res["same"] + 1 if same_assets else res["different"] + [man + " (assets)"]
    res["compared"] = len(pairs) + 1
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    # stage3 (M1): the game folder may also come from NMS_GAME_DIR (read-only use; never written)
    ap.add_argument("game", type=Path, nargs="?", default=os.environ.get("NMS_GAME_DIR"))
    ap.add_argument("out", type=Path)
    ap.add_argument("--compiler", type=Path, default=MBC_707)
    ap.add_argument("--label", default="new")
    ap.add_argument("--reproduce-705", action="store_true")
    ap.add_argument("--check-against-705", action="store_true")
    a = ap.parse_args(argv)
    if not a.game:
        ap.error("game folder required (argument or NMS_GAME_DIR)")
    a.game = Path(a.game)
    kw = dict(table_compiler=MBC_704, scene_compiler=MBC_704) if a.reproduce_705 else {}
    rep = extract(a.game, a.out, a.compiler, label=a.label, **kw)
    print(json.dumps({k: v for k, v in rep.items() if k != "steps"}, indent=1))
    if a.check_against_705:
        c = check_against_705(a.out)
        print(json.dumps({**c, "different": c["different"][:20], "missing": c["missing"][:20]}, indent=1))
        return 0 if not c["different"] and not c["missing"] else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
