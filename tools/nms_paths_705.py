"""Output-path override for staging / test copies of the scanner pipeline.

NMS_STAGING_ROOT unset (the live setup): out_path(p) returns p unchanged, so live behaviour is identical.
NMS_STAGING_ROOT=<dir>: every OUTPUT path under the live analysis or backup folders is moved below <dir>:
  D:/Orca/NMS-Derelict-Probe-analysis/<rest>  ->  <dir>/analysis/<rest>
  D:/Orca/NMS-Derelict-Probe-backups/<rest>   ->  <dir>/backups/<rest>
Read-only inputs (NMS.exe copy, asset rows, catalog pickles, meshcache, spacepoitable.mbin, cached layouts) keep
their live paths; only files a run writes go through out_path().
"""
from __future__ import annotations

import os
from pathlib import Path

LIVE_ANALYSIS = Path("D:/Orca/NMS-Derelict-Probe-analysis")
LIVE_BACKUPS = Path("D:/Orca/NMS-Derelict-Probe-backups")


def staging_root() -> Path | None:
    root = os.environ.get("NMS_STAGING_ROOT")
    return Path(root) if root else None


def out_path(path) -> Path:
    path = Path(path)
    root = staging_root()
    if root is None:
        return path
    for base, name in ((LIVE_ANALYSIS, "analysis"), (LIVE_BACKUPS, "backups")):
        try:
            return root / name / path.relative_to(base)
        except ValueError:
            continue
    raise ValueError(f"NMS_STAGING_ROOT is set but {path} has no staging mapping")


def fix_enabled(name: str) -> bool:
    """Speed fixes 2026-10-22 (all on by default). NMS_SPEED_FIXES=none disables all; a comma list enables only those:
    poi (fast powf/frexp stub hook), combined (one region-scan worker), stream (streaming backlogs),
    scancache (per-system container + POI cache)."""
    value = os.environ.get("NMS_SPEED_FIXES", "all").strip().lower()
    if value in ("", "all"):
        return True
    if value == "none":
        return False
    return name in {v.strip() for v in value.split(",")}
