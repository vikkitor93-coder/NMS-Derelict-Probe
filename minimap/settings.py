"""Minimap settings: every machine-specific path in one editable file, minimap/settings.json (stdlib only).

The file is created with the defaults below on first use and never overwritten. Delete a key to get its default again.

    nms_exe       "" = find it: the running NMS.exe, then the Steam libraries
    analysis_dir  folder that holds rea/ (the pinned NMS.exe copy), emu/ (generated layouts), end-reward-cache/, meshcache/
    fastgen_dir   the fast generator (fast_generate_705.py)
    emu_python    python with unicorn + pefile (the space-POI step); the EMU_PYTHON environment variable also works

Defaults are siblings of the project folder (…/NMS-Derelict-Probe -> …/NMS-Derelict-Probe-analysis), so a copy of the
whole set of folders moved to another drive or PC works without edits except emu_python.
Paths used inside other tools (tools/*.py, the fast generator) are listed in minimap/README.md, 'Moving to another PC'.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FILE = HERE / "settings.json"


def defaults() -> dict:
    parent = ROOT.parent
    return {
        "nms_exe": "",
        "analysis_dir": str(parent / "NMS-Derelict-Probe-analysis"),
        "fastgen_dir": str(parent / "NMS-Derelict-Probe-fastgen"),
        "emu_python": os.environ.get("EMU_PYTHON", os.path.expandvars("%USERPROFILE%/tools/NMS-Shipwright/.venv/Scripts/python.exe")),
    }


def load() -> dict:
    cfg = defaults()
    if FILE.exists():
        try:
            data = json.loads(FILE.read_text(encoding="utf-8"))
            cfg.update({k: v for k, v in data.items() if k in cfg and isinstance(v, str) and (v or k == "nms_exe")})
        except (OSError, ValueError):
            pass
    else:
        try:
            FILE.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
        except OSError:
            pass
    return cfg


def paths() -> dict[str, Path]:
    """The settings plus the paths derived from them."""
    c = load()
    an = Path(c["analysis_dir"])
    fg = Path(c["fastgen_dir"])
    return {
        "analysis": an,
        "fastgen": fg,
        "fast_generate": fg / "fast_generate_705.py",
        "native_writer": fg / "native_writer_705.py",
        "rewards_csv": an / "end-reward-cache" / "rewards.csv",
        "mesh_index": an / "meshcache" / "index.json",
        "cache": an / "minimap-cache",
        "poi_cache": an / "minimap-cache" / "poi.json",
        "layout_dirs": [an / "emu" / "fastgen" / "generated", an / "emu" / "generated"],
        "emu_python": Path(c["emu_python"]),
        "nms_exe_setting": Path(c["nms_exe"]) if c["nms_exe"] else None,
    }


def find_nms_exe(running_path: str | None = None) -> Path | None:
    """The installed NMS.exe: the running process, then the settings, then every Steam library."""
    for cand in (running_path, load()["nms_exe"]):
        if cand and Path(cand).is_file():
            return Path(cand)
    libs: list[Path] = []
    steam = None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
            steam = Path(winreg.QueryValueEx(k, "SteamPath")[0])
    except OSError:
        pass
    for guess in (steam, Path("C:/Program Files (x86)/Steam")):
        if guess and guess.exists():
            libs.append(guess)
            vdf = guess / "steamapps" / "libraryfolders.vdf"
            try:
                libs += [Path(m.replace("\\\\", "\\")) for m in re.findall(r'"path"\s+"([^"]+)"', vdf.read_text(encoding="utf-8"))]
            except OSError:
                pass
    for lib in libs:
        exe = lib / "steamapps" / "common" / "No Man's Sky" / "Binaries" / "NMS.exe"
        if exe.is_file():
            return exe
    return None
