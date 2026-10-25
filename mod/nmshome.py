"""Where things are inside the portable minimap package (stdlib only). Copied next to every shipped script by build_package.py.

The package root is the folder that contains the marker file ".nmsmm-home"; everything is found relative to it, so the
folder can be moved or copied anywhere. The folder names mirror the development layout on purpose, so the unchanged
generator code finds its inputs:

    HOME/NMS-Derelict-Probe/            minimap/, tools/, research-output/ (game data extracted on first run)
    HOME/NMS-Derelict-Probe-fastgen/    fast_generate_705.py
    HOME/NMS-Derelict-Probe-analysis/   caches: generated layouts, POI results, meshes, pinned game copy
    HOME/NMS-Shipwright/                nms_procgen (MIT) - the space-POI generator; it finds the game itself
    HOME/game-data/                     raw first-run extraction
    HOME/python/                        the Python runtime
    HOME/third-party/                   MBINCompiler (used once, on first run)
"""
from __future__ import annotations

import os
from pathlib import Path

MARKER = ".nmsmm-home"


def _find_home() -> Path:
    here = Path(__file__).resolve()
    for d in (here.parent, *here.parents):
        if (d / MARKER).is_file():
            return d
    raise RuntimeError(f"not inside a minimap package folder (no {MARKER} above {here})")


HOME = _find_home()
PROBE = HOME / "NMS-Derelict-Probe"
FASTGEN = HOME / "NMS-Derelict-Probe-fastgen"
ANALYSIS = HOME / "NMS-Derelict-Probe-analysis"
SHIPWRIGHT = HOME / "NMS-Shipwright"
GAMEDATA = HOME / "game-data"
THIRD = HOME / "third-party"
MBC_707 = THIRD / "mbincompiler-7.07.0-pre1" / "MBINCompiler.exe"
MBC_704 = THIRD / "mbincompiler-7.04.1-pre3" / "MBINCompiler.exe"


def _python() -> Path:
    exe = Path(os.environ.get("NMSMM_PYTHON", "") or HOME / "python" / "python.exe")
    return exe if exe.is_file() else Path(__import__("sys").executable)   # a console python: children need real stdout


PYTHON = _python()


def game_dir() -> Path | None:
    """The user's NMS folder (the one with Binaries/ and GAMEDATA/): settings.json, then the minimap's own finder."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("_nmsmm_settings", PROBE / "minimap" / "settings.py")
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    exe = mod.find_nms_exe()
    return exe.parent.parent if exe else None


_GAME = game_dir()
NMS_EXE = (_GAME / "Binaries" / "NMS.exe") if _GAME else HOME / "NMS-not-found" / "Binaries" / "NMS.exe"
PCBANKS = (_GAME / "GAMEDATA" / "PCBANKS") if _GAME else HOME / "NMS-not-found" / "GAMEDATA" / "PCBANKS"
