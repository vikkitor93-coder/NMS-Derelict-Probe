"""Game-build profiles for the derelict generator, reward and loot predictors (stdlib only; read-only on game files).

A *build profile* says which game build the generator chain runs as: the pinned NMS.exe copy, every hard-coded code
address the native writer patches or calls, the extracted game tables / scene assets, and the game-data fingerprints.
The NMS 7.05 profile is built in (BUILTIN_705, mirrors the constants in the shared fast generator and the tools, which
are NOT changed by this module). A new build gets its own folder written by tools/relocate_generator_705.py:

    D:/Orca/NMS-Derelict-Probe-analysis/builds/<build_id>/build.json        the profile (paths, addresses, fingerprints)
                                                     /address_map.json  relocation report (confidence per address)
                                                     /data/research-output/...   re-extracted game data, same layout as
                                                                                 the 7.05 workspace (data_root)
                                                     /shipwright/{globals,metadata}   Shipwright game-data snapshot
                                                     /cache/              catalog pickles for this build

apply_profile(profile) patches the already-imported generator modules IN THIS PROCESS ONLY (module globals and
function defaults), so the unchanged 7.05 code runs with another build's exe, addresses and data. Nothing on disk is
changed. Used by tools/compare_builds_worker_705.py and tools/golden_ingame_705.py --profile.

    python -I tools/build_profile_705.py --show [7.05|<build_id>|path/to/build.json]
    python -I tools/build_profile_705.py --fingerprint-installed      game-table fingerprints of the installed game
    python -I tools/build_profile_705.py --write-705                  (re)write builds/7.05/build.json + snapshots
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ANALYSIS = Path("D:/Orca/NMS-Derelict-Probe-analysis")
FASTGEN = Path("D:/Orca/NMS-Derelict-Probe-fastgen")
BUILDS = ANALYSIS / "builds"
SHIPWRIGHT = Path("%USERPROFILE%/tools/NMS-Shipwright")
EXE_SHA_705 = "13D5060D4EFB9D2A6A6B1B349BC4257231056CC2A055DF4BB15D816262CC3499"
BASE_ID = "7.05"

# Every hard-coded NMS.exe address / immediate the generator chain depends on, by role.
#  native: executed or patched by native_writer_705.py (and the Unicorn emulator); a wrong value = wrong or crashed run
#  diag:   only entry counters in emulate_writer_705*.py --counters (diagnostics)
#  logic:  game functions re-implemented in Python (seed/preset, end reward, crate loot); their body must be unchanged
#          for the Python port to stay valid (relocate_generator_705.py compares the bodies)
#  site:   an instruction inside a logic function (documentation pointer), resolved through its function
#  poi:    Shipwright's star-system generator (found by Shipwright's own signatures at run time; listed for the report)
ADDRESSES_705 = {
    "writer":                         (0x14039E5E0, "native", "native_writer_705.WRITER; emulate_writer_705*.py call", "derelict room writer FUN_14039E5E0"),
    "hook.alloc_getter":              (0x142C1FE30, "native", "native_writer_705.HOOKS", "patched: returns the allocator object"),
    "hook.alloc":                     (0x142C20E80, "native", "native_writer_705.HOOKS", "patched: bump allocator"),
    "hook.A4400_handle":              (0x1403A4400, "native", "native_writer_705.HOOKS", "patched: ret 0"),
    "hook.A4720_instance":            (0x1403A4720, "native", "native_writer_705.HOOKS", "patched: captures the placement records"),
    "hook.A51B0_prune":               (0x1403A51B0, "native", "native_writer_705.HOOKS", "patched: ret 0"),
    "hook.timer":                     (0x142BFF9A0, "native", "native_writer_705.HOOKS", "patched: ret 0"),
    "hook.C090F0_engine":             (0x142C090F0, "native", "native_writer_705.HOOKS", "patched: ret 0"),
    "hook.BFA8F0_free":               (0x142BFA8F0, "native", "native_writer_705.HOOKS", "patched: ret 0"),
    "hook.C22170_allocator_restore":  (0x142C22170, "native", "native_writer_705.HOOKS", "patched: ret 0"),
    "data.generatedbase_global":      (0x145092FF0, "native", "native_writer_705.build_inputs G (+0x24, +0x28)", "global holding the GeneratedBase table + source rows"),
    "diag.A01F0": (0x1403A01F0, "diag", "emulate_writer_705*.py counters", ""), "diag.A03E0": (0x1403A03E0, "diag", "emulate_writer_705*.py counters", ""),
    "diag.A0580": (0x1403A0580, "diag", "emulate_writer_705*.py counters", ""), "diag.A06E0": (0x1403A06E0, "diag", "emulate_writer_705*.py counters", ""),
    "diag.A0850": (0x1403A0850, "diag", "emulate_writer_705*.py counters", ""), "diag.A0AD0": (0x1403A0AD0, "diag", "emulate_writer_705*.py counters", ""),
    "diag.A0FF0": (0x1403A0FF0, "diag", "emulate_writer_705*.py counters", ""), "diag.A15F0": (0x1403A15F0, "diag", "emulate_writer_705*.py counters", ""),
    "diag.A1A00": (0x1403A1A00, "diag", "emulate_writer_705*.py counters", ""), "diag.A1DA0": (0x1403A1DA0, "diag", "emulate_writer_705*.py counters", ""),
    "diag.A2120": (0x1403A2120, "diag", "emulate_writer_705*.py counters", ""), "diag.A2780": (0x1403A2780, "diag", "emulate_writer_705*.py counters", ""),
    "diag.A3270": (0x1403A3270, "diag", "emulate_writer_705*.py counters", ""), "diag.A3BC0": (0x1403A3BC0, "diag", "emulate_writer_705*.py counters", ""),
    "diag.A5480": (0x1403A5480, "diag", "emulate_writer_705*.py counters", ""),
    "logic.universe_pack":            (0x140583A90, "logic", "nms_universe_address_705.py", "address packing"),
    "logic.seed_component_init":      (0x1410FED60, "logic", "derelict_seed_preset_705.py", "address -> writer seed (component init)"),
    "logic.seed_worker":              (0x1411001D0, "logic", "derelict_seed_preset_705.py", "address -> writer seed (worker)"),
    "logic.preset_chooser":           (0x141100D40, "logic", "derelict_seed_preset_705.py", "weighted preset chooser"),
    "data.seed_override_global":      (0x14526D4F0, "logic", "derelict_seed_preset_705.py (override 0)", "global seed override"),
    "logic.position_hash":            (0x140504EB0, "logic", "predict_end_reward_705.position_seed", "world position -> interaction seed"),
    "logic.select_always":            (0x140F1AB90, "logic", "predict_end_reward_705.select_always", "SelectAlways weighted pick"),
    "logic.freighter_tech_seed":      (0x140F248B0, "logic", "predict_end_reward_705", "FreighterTech seed replacement"),
    "logic.freighter_tech_number":    (0x140EBF810, "logic", "predict_end_reward_705.freighter_tech_number_class", "FreighterTech number + class"),
    "site.freighter_tech_class_a":    (0x140EC0D5F, "site", "predict_end_reward_705 docstring", "class derivation site"),
    "site.freighter_tech_class_b":    (0x140EC87B0, "site", "predict_end_reward_705 docstring", "class derivation site"),
    "data.d2_32_double":              (0x144B282D8, "logic", "predict_end_reward_705.D2_32", "double 2^-32 used by the MWC draw"),
    "logic.try_first_select_always":  (0x140F19E90, "logic", "predict_crate_loot_705", "TryFirst_ThenSelectAlways"),
    "site.try_first_case7":           (0x140F1B15F, "site", "predict_crate_loot_705 docstring", "case 7"),
    "site.pick_loop_a":               (0x140F1B1D9, "site", "predict_crate_loot_705.pick_entry", "weighted pick loop"),
    "site.pick_loop_b":               (0x140F1B273, "site", "predict_crate_loot_705.pick_entry", "weighted pick loop end"),
    "logic.reward_amount_200B0":      (0x140F200B0, "logic", "predict_crate_loot_705.loot", "amount handler"),
    "logic.reward_sysprod_20290":     (0x140F20290, "logic", "predict_crate_loot_705.system_product", "system product handler"),
    "logic.reward_amount_203B0":      (0x140F203B0, "logic", "predict_crate_loot_705.loot", "amount handler"),
    "logic.tech_quality_20E20":       (0x140F20E20, "logic", "predict_crate_loot_705.loot", "tech quality roll"),
    "poi.galaxy_info":                (0x14132D5E0, "poi", "space_poi_position_705 (Shipwright signature 'info')", "galaxy info"),
    "poi.poi_list_a":                 (0x14132BF90, "poi", "space_poi_position_705 docstring", "POI list"),
    "poi.poi_list_b":                 (0x14132C660, "poi", "space_poi_position_705 docstring", "POI list"),
    "poi.system_generator":           (0x14164A4A0, "poi", "space_poi_position_705 (Shipwright signature 'gen')", "solar-system generator"),
    "site.poi_positions_write":       (0x14164F655, "site", "space_poi_position_705 docstring", "writes SpacePoiPositions"),
    "poi.spawner":                    (0x1416D6D70, "poi", "space_poi_position_705 docstring", "POI spawner"),
}
WRITER_ARG2_705 = 0x4951E1          # immediate 2nd argument of the writer call (native_writer_705.NativeSession.run)
HOOK_ORDER = ("alloc_getter", "alloc", "A4400_handle", "A4720_instance", "A51B0_prune", "timer", "C090F0_engine",
              "BFA8F0_free", "C22170_allocator_restore")
# Struct offsets the chain hard-codes (not code addresses; a relocation tool cannot find them; checked by golden runs)
STRUCT_OFFSETS_705 = {
    "space_poi_position_705: app+0x128 (cGcSpacePoiTable), info+0x748 (POI count), info+0xB0 (POI ids), owner+0x1CE0 (SpacePoiPositions)": "7.05",
    "native_writer_705.build_inputs: G+0x24 row count, G+0x28 rows, row size 0x2B0, descriptor ptr +0x2A0, descriptor 0x50": "7.05",
    "native_writer_705: preset base +0x30, stride 0x90, name +0x80; seed struct (u64 seed, u8 1)": "7.05",
    "live_position_705: Data+0x4CCF90 sim, sim offsets (live reader; see minimap/README.md)": "7.05",
}

# Game-data members the chain reads (archive, member). Their raw bytes are fingerprinted per build.
GAME_MEMBERS = {
    "rewardtable": ("NMSARC.Precache.pak", "metadata/reality/tables/rewardtable.mbin"),
    "freighterdungeonstable": ("NMSARC.Precache.pak", "metadata/reality/tables/freighterdungeonstable.mbin"),
    "generatedbasetemplatestable": ("NMSARC.Precache.pak", "metadata/reality/tables/generatedbasetemplatestable.mbin"),
    "spacepoitable": ("NMSARC.Precache.pak", "metadata/simulation/solarsystem/spacepoi/spacepoitable.mbin"),
    "dungeonentrance_entity": ("NMSARC.Precache.pak", "models/space/poi/parts/dungeon_entrance/entities/dungeonentrance.entity.mbin"),
    "dungeon_entity": ("NMSARC.Precache.pak", "models/space/poi/dungeon/entities/dungeon.entity.mbin"),
    "gameplayglobals": ("NMSARC.globals.pak", "gcgameplayglobals.global.mbin"),
    "dungeon_scene": ("NMSARC.EntitySceneMBIN.pak", "models/space/poi/dungeon.scene.mbin"),
}
SCENE_PAK = "NMSARC.EntitySceneMBIN.pak"
SCENE_MANIFEST_REL = "research-output/exact705-generatedbase-scenes-20261019/exact705-generatedbase-scene-members.sha256.json"


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def builtin_705() -> dict:
    """The 7.05 profile, from the constants the 7.05 code uses today (no file needed)."""
    dr = ROOT
    return {
        "schema": 1,
        "build_id": BASE_ID,
        "label": "NMS 7.05",
        "exe": str(ANALYSIS / "rea" / "NMS-13D5060D.exe"),
        "exe_sha256": EXE_SHA_705,
        "data_root": str(dr),
        "writer_table_mbin": "D:/Orca/Temp/generatedbase-table-705-mbc707/generatedbasetemplatestable.mbin",
        "writer_table_mxml": "D:/Orca/Temp/generatedbase-table-705-mbc707/generatedbasetemplatestable.MXML",
        "preset_mbin": str(dr / "research-output/exact705-dungeon-inputs-20261019/metadata/reality/tables/freighterdungeonstable.mbin"),
        "asset_rows": str(ANALYSIS / "emu" / "asset_source_rows.bin"),
        "spacepoi_dir": str(ANALYSIS / "end-reward-cache"),          # holds spacepoitable.mbin
        "shipwright_cache": str(BUILDS / BASE_ID / "shipwright"),   # globals/ + metadata/ snapshot (7.05)
        "catalog_cache": str(ANALYSIS / "emu" / "fastgen" / "cache"),
        "addresses": {k: hex(v[0]) for k, v in ADDRESSES_705.items()},
        "writer_arg2": hex(WRITER_ARG2_705),
        "fingerprints": {},       # filled by --write-705 from the installed (7.05) game; see game_fingerprints()
        "overrides": {},          # optional predictor constant overrides (tests / a re-derived new build)
    }


def load_profile(spec: str | dict | None) -> dict:
    """'7.05' (builtin, merged with builds/7.05/build.json fingerprints if present), a build id under BUILDS, or a path."""
    if isinstance(spec, dict):
        return spec
    spec = spec or BASE_ID
    p = Path(spec)
    if not p.suffix == ".json":
        p = BUILDS / spec / "build.json"
    if spec == BASE_ID:
        prof = builtin_705()
        if p.is_file():
            saved = json.loads(p.read_text(encoding="utf-8"))
            prof["fingerprints"] = saved.get("fingerprints", {})
        return prof
    if not p.is_file():
        raise FileNotFoundError(f"no build profile {spec} ({p})")
    prof = json.loads(p.read_text(encoding="utf-8"))
    base = builtin_705()
    for k, v in base.items():          # a new profile may leave out what did not change
        prof.setdefault(k, v)
    return prof


def addr(prof: dict, key: str) -> int:
    return int(prof["addresses"][key], 16)


# ---------------------------------------------------------------------------------------------- game-data fingerprints
def nms_install() -> Path | None:
    """The installed game folder (settings, then Steam), never the running process."""
    sys.path.insert(0, str(ROOT / "minimap"))
    import settings as ST  # noqa: E402
    exe = ST.find_nms_exe(None)
    return exe.parent.parent if exe else None


def scene_members(manifest: Path | None = None) -> list[str]:
    """The 319 generated-base scene members the generator reads (7.05 manifest)."""
    doc = json.loads((manifest or ROOT / SCENE_MANIFEST_REL).read_text(encoding="utf-8"))
    return sorted({a["archive_member"].lower() for a in doc["assets"]})


def scene_fingerprint(banks: Path, manifest: Path | None = None) -> str:
    """One SHA-256 over 'member:sha256' of every generated-base scene member (missing ones count as 'missing')."""
    from hgpaktool import HGPAKFile
    want = scene_members(manifest)
    with HGPAKFile(Path(banks) / SCENE_PAK) as a:
        names = {n.lower(): n for n in a.filenames}
        got = {n.lower(): hashlib.sha256(b).hexdigest().upper() for n, b in a.extract([names[m] for m in want if m in names])}
    return hashlib.sha256("\n".join(f"{m}:{got.get(m, 'missing')}" for m in want).encode()).hexdigest().upper()


def game_fingerprints(game_dir: Path | None = None, members=GAME_MEMBERS, scenes: bool = True,
                      scene_manifest: Path | None = None) -> dict:
    """{key: sha256 of the raw member bytes} read from the game's PAKs (hgpaktool; about 1 s), plus one hash over the
    319 generated-base scene members (scenes=True)."""
    from hgpaktool import HGPAKFile
    game_dir = Path(game_dir) if game_dir else nms_install()
    banks = game_dir / "GAMEDATA" / "PCBANKS"
    out, by_pak = {}, {}
    for key, (pak, member) in members.items():
        by_pak.setdefault(pak, []).append((key, member))
    for pak, items in by_pak.items():
        with HGPAKFile(banks / pak) as a:
            names = {n.lower(): n for n in a.filenames}
            want = [names[m] for _k, m in items if m in names]
            got = {n.lower(): b for n, b in a.extract(want)} if want else {}
        for key, member in items:
            b = got.get(member)
            out[key] = hashlib.sha256(b).hexdigest().upper() if b is not None else None
    if scenes:
        out["generatedbase_scenes"] = scene_fingerprint(banks, scene_manifest)
    return out


def extract_members(game_dir: Path, dest: Path, members=GAME_MEMBERS) -> dict:
    """Write each member's raw bytes to dest/<member path>; returns {key: path}."""
    from hgpaktool import HGPAKFile
    banks = Path(game_dir) / "GAMEDATA" / "PCBANKS"
    out = {}
    for key, (pak, member) in members.items():
        with HGPAKFile(banks / pak) as a:
            names = {n.lower(): n for n in a.filenames}
            if member not in names:
                out[key] = None
                continue
            for name, data in a.extract([names[member]]):
                p = dest / member
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(data)
                out[key] = str(p)
    return out


# ---------------------------------------------------------------------------------------------------------- patching
def _set_defaults(fn, **values):
    """Replace keyword defaults of a plain function (defaults bound at def time do not follow module globals)."""
    code = fn.__code__
    names = code.co_varnames[:code.co_argcount]
    d = list(fn.__defaults__ or ())
    first = len(names) - len(d)
    for k, v in values.items():
        i = names.index(k) - first
        d[i] = v
    fn.__defaults__ = tuple(d)


def apply_profile(prof: dict, *, full: bool = True) -> dict:
    """Patch the imported generator chain to run as `prof`. Call BEFORE NativeSession() / PoiGen() are created.

    full=False patches only what keeps the run independent of the INSTALLED game (Shipwright exe + game data snapshot),
    leaving every generator constant as shipped (the 'stock' 7.05 path). Returns a dict of what was patched."""
    sys.path.insert(0, str(HERE))
    sys.path.insert(0, str(FASTGEN))
    import fast_generate_705 as F
    import native_writer_705 as N
    import transform_writer_output_705 as T
    import generate_derelict_705 as G
    import extra_containers_705 as X
    import predict_end_reward_705 as P
    import predict_crate_loot_705 as C
    import derelict_seed_preset_705 as D
    import space_poi_position_705 as SP
    done = {}

    # --- Shipwright (space POI positions): the profile's exe and its own game-data snapshot, never the installed game
    import nms_procgen.emu as SE
    import nms_procgen.systemgen as SS
    sw = Path(prof["shipwright_cache"])
    if (sw / "globals").is_dir() and (sw / "metadata").is_dir():
        SE.extract_globals = lambda dest=None, _d=str(sw / "globals"): _d
        SE.extract_metadata = lambda dest=None, _d=str(sw / "metadata"): _d
        SS.extract_metadata = SE.extract_metadata
        done["shipwright_data"] = str(sw)
    else:
        done["shipwright_data"] = "INSTALLED GAME (no snapshot at %s)" % sw
    exe = prof["exe"]
    SP.SystemGen = lambda exe_=None, _e=exe: SS.SystemGen(_e)
    SP.CACHE = Path(prof["spacepoi_dir"])
    done["poi_exe"] = exe
    if not full:
        return done

    dr = Path(prof["data_root"])
    a = {k: int(v, 16) for k, v in prof["addresses"].items()}
    # --- native writer (shared file; patched in memory only)
    N.EXE = Path(exe)
    N.ASSET_ROWS = Path(prof["asset_rows"])
    N.TABLE_MBIN = Path(prof["writer_table_mbin"])
    N.TABLE_MXML = Path(prof["writer_table_mxml"])
    N.PRESET_MBIN = Path(prof["preset_mbin"])
    N.WRITER = a["writer"]
    N.HOOKS = tuple((h, a["hook." + h]) for h in HOOK_ORDER)
    N._NAMES = None
    _set_defaults(N.Native.__init__, exe=N.EXE)
    _set_defaults(N.NativeSession.__init__, asset_rows=N.ASSET_ROWS)
    g_addr, arg2 = a["data.generatedbase_global"], int(prof.get("writer_arg2", hex(WRITER_ARG2_705)), 16)
    orig_build_inputs = getattr(N, "_orig_build_inputs", N.build_inputs)
    N._orig_build_inputs = orig_build_inputs

    def build_inputs(e, *, seed_value, preset_index, asset_rows=N.ASSET_ROWS):
        """native_writer_705.build_inputs with the profile's global G (the 7.05 function writes 0x145092FF0)."""
        import struct
        info = {}
        _, tbl = e.load_mbin(N.TABLE_MBIN)
        arr0 = e.rq(tbl)
        n0 = e.ri(tbl + 8)
        info["table_counts"] = [e.ri(tbl + 8), e.ri(tbl + 0x18), e.ri(tbl + 0x28)]
        blob = bytearray(Path(asset_rows).read_bytes())
        nrows = len(blob) // 0x2B0
        for i in range(nrows):
            p = struct.unpack_from("<Q", blob, i * 0x2B0 + 0x2A0)[0]
            assert p < n0, (i, hex(p))
            struct.pack_into("<Q", blob, i * 0x2B0 + 0x2A0, arr0 + p * 0x50)
        rows = e.alloc(len(blob), 0x100)
        e.mem_write(rows, bytes(blob))
        info["descriptors_overlaid"] = n0
        G_ = g_addr
        e.wq(G_, tbl)
        e.wi(G_ + 0x24, nrows)
        e.wq(G_ + 0x28, rows)
        info["nrows"] = nrows
        pbase, _ = e.load_mbin(N.PRESET_MBIN)
        if not 0 <= preset_index < 10:
            raise ValueError(f"preset index out of range: {preset_index}")
        preset = pbase + 0x30 + preset_index * 0x90
        info["preset_name"] = e.rd(preset + 0x80, 16).split(b"\0")[0].decode()
        info["preset_index"] = preset_index
        seed = e.alloc(0x20)
        e.wq(seed, seed_value)
        e.mem_write(seed + 8, b"\x01")
        info["writer_seed"] = f"{seed_value:016X}"
        outbuf = e.alloc(0x100000, 0x100)
        return dict(G=G_, seed=seed, preset=preset, outbuf=outbuf, info=info, tbl=tbl, rows=rows, preset_base=pbase)

    N.build_inputs = build_inputs
    done["native_writer"] = {"exe": exe, "writer": hex(N.WRITER), "G": hex(g_addr)}
    if arg2 != WRITER_ARG2_705:   # NativeSession.run passes the 7.05 immediate inline; a change needs a manual port
        raise NotImplementedError(f"writer 2nd argument {arg2:#x} != 0x4951E1: port NativeSession.run by hand "
                                  "(research-output/GAME_UPDATE_RESILIENCE_20261022.md)")

    # --- offline transforms / catalog: the profile's data root (same relative layout as the 7.05 workspace)
    def entrance_origin(preset_index: int, _p=dr / "research-output/exact705-dungeon-inputs-20261019/metadata/reality/tables/freighterdungeonstable.MXML"):
        import xml.etree.ElementTree as ET
        root = ET.parse(_p).getroot()
        for node in root.iter("Property"):
            if node.get("name") == "Dungeons" and int(node.get("_index", "-1")) == preset_index:
                fields = {p.get("name"): p.get("value") for p in node.iter("Property")}
                return tuple(int(fields[f"Entrance{axis}"]) for axis in "XYZ")
        raise ValueError(f"preset index {preset_index} not found in the profile's preset MXML")
    T.entrance_origin = entrance_origin
    G.CONT_INDEX = dr / "research-output/exact705-generatedbase-scenes-20261019/authored_container_transform_index.csv"
    X.SCENES = dr / "research-output/exact705-generatedbase-scenes-20261019"
    X.EXTRA_INDEX = X.SCENES / "authored_extra_container_transform_index.csv"
    X.MAIN_INDEX = X.SCENES / "authored_container_transform_index.csv"
    code_root = ROOT

    def catalog_key():
        h = hashlib.sha256(("profile:" + prof["build_id"] + "|" + str(dr)).encode())
        for rel in F.CATALOG_CODE:
            p = code_root / rel
            for f in sorted(p.glob("*.py")) if p.is_dir() else [p]:
                h.update(f.name.encode() + f.read_bytes())
        for rel in F.CATALOG_INPUTS:
            stack = [dr / rel]
            while stack:
                for ent in sorted(os.scandir(stack.pop()), key=lambda x: x.name):
                    if ent.is_dir():
                        stack.append(ent.path)
                    else:
                        st = ent.stat()
                        h.update(f"{ent.path}|{st.st_size}|{st.st_mtime_ns}\n".encode())
        return h.hexdigest()[:24]
    F._catalog_key = catalog_key
    F.ROOT = dr                                # Q4SourceCatalog.from_workspace(F.ROOT)
    F.CACHE = Path(prof["catalog_cache"])
    F._MEMO.clear()
    fp = prof.get("fingerprints", {})
    sys.path.insert(0, str(ROOT / "research-output/offline-layout-705-20261019"))
    import nms_dungeon_offline as OFF
    for name, key in (("GENERATEDBASE_MXML_SHA256", "generatedbase_mxml_sha256"), ("PRECACHE_PAK_SHA256", "precache_pak_sha256"),
                      ("ENTITY_SCENE_PAK_SHA256", "entity_scene_pak_sha256"), ("NMS_EXE_SHA256", "exe_sha256")):
        val = fp.get(key) or (prof["exe_sha256"] if key == "exe_sha256" else None)
        if val:
            setattr(OFF, name, val)
    done["data_root"] = str(dr)

    # --- predictor constants (only when the profile overrides them: a re-derived build or a perturbation test)
    ov = copy.deepcopy(prof.get("overrides") or {})
    if "R_FREI_TECH" in ov:
        P.R_FREI_TECH = [tuple(x) for x in ov["R_FREI_TECH"]]
    if "QUALITY_WEIGHTS" in ov:
        P.QUALITY_WEIGHTS = list(ov["QUALITY_WEIGHTS"])
    for k in ("ENTRANCE_REF", "DUNGEON_D", "TERMINAL_LOCAL"):
        if k in ov:
            setattr(P, k, tuple(ov[k]))
    if "PRESETS" in ov:
        D.PRESETS = [tuple(x) for x in ov["PRESETS"]]
    if "LOOT_TABLES" in ov:
        for tid, rows in ov["LOOT_TABLES"].items():
            fixed = []
            for kind, key, w, extra in rows:
                if kind == "sysprod":
                    extra = (list(extra[0]), extra[1], extra[2])
                elif extra is not None:
                    extra = tuple(extra)
                fixed.append((kind, key, w, extra))
            C.TABLES[tid] = fixed
    if ov:
        done["overrides"] = sorted(ov)
    return done


# --------------------------------------------------------------------------------------------------------------- CLI
def write_705() -> Path:
    """builds/7.05/build.json (reference, from the built-in constants + installed-game fingerprints) and the Shipwright
    game-data snapshot. Refuses unless the installed game IS 7.05 (so the snapshot really is 7.05 data)."""
    game = nms_install()
    exe = game / "Binaries" / "NMS.exe" if game else None
    if not exe or sha256_file(exe) != EXE_SHA_705:
        raise SystemExit("the installed NMS.exe is not 7.05: cannot take the 7.05 fingerprints/snapshot now")
    prof = builtin_705()
    dest = BUILDS / BASE_ID
    dest.mkdir(parents=True, exist_ok=True)
    sw_src = SHIPWRIGHT / "data" / "gamecache"
    for sub in ("globals", "metadata"):
        if not (dest / "shipwright" / sub).is_dir():
            shutil.copytree(sw_src / sub, dest / "shipwright" / sub)
    fp = {"members": game_fingerprints(game)}
    sys.path.insert(0, str(ROOT / "research-output/offline-layout-705-20261019"))
    import nms_dungeon_offline as OFF
    fp.update(generatedbase_mxml_sha256=OFF.GENERATEDBASE_MXML_SHA256, precache_pak_sha256=OFF.PRECACHE_PAK_SHA256,
              entity_scene_pak_sha256=OFF.ENTITY_SCENE_PAK_SHA256)
    prof["fingerprints"] = fp
    prof["note"] = ("Reference profile of the shipped 7.05 generator (constants in native_writer_705.py and the tools). "
                    "This file is informational: the 7.05 profile is built in (build_profile_705.builtin_705); only its "
                    "fingerprints are read from here. Never overwritten by relocate_generator_705.py.")
    out = dest / "build.json"
    if out.exists():
        shutil.copyfile(out, out.with_name("build.json.pre-update-guard-20261022"))
    out.write_text(json.dumps(prof, indent=1), encoding="utf-8")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--show", nargs="?", const=BASE_ID)
    ap.add_argument("--fingerprint-installed", action="store_true")
    ap.add_argument("--write-705", action="store_true")
    a = ap.parse_args(argv)
    if a.write_705:
        print("wrote", write_705())
    if a.fingerprint_installed:
        print(json.dumps(game_fingerprints(), indent=1))
    if a.show:
        print(json.dumps(load_profile(a.show), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
