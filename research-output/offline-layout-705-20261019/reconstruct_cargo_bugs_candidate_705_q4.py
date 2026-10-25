#!/usr/bin/env python3
"""Q4 rerun of reconstruct_cargo_bugs_candidate_705.py with the reference-aware map provider.

Identical inputs, seed, retry limits, writer search, A2780 and comparison code; only the
catalog/map-row provider is swapped for nms_dungeon_reference_closure_q4_705.Q4SourceCatalog.
Default output: CARGO_BUGS_ZERO_OVERRIDE_LAYOUT_Q4_20261020.json next to this file.

Run (from any cwd):
  python -I -c "import sys,runpy; d=r'D:/Orca/NMS-Derelict-Probe/research-output/offline-layout-705-20261019'; sys.path.insert(0,d); runpy.run_path(d+'/reconstruct_cargo_bugs_candidate_705_q4.py', run_name='__main__')"
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import reconstruct_cargo_bugs_candidate_705 as base  # noqa: E402
from nms_dungeon_reference_closure_q4_705 import Q4SourceCatalog  # noqa: E402

base.GeneratedBaseSourceCatalog = Q4SourceCatalog

if __name__ == "__main__":
    if "--output" not in sys.argv:
        sys.argv += ["--output", str(HERE / "CARGO_BUGS_ZERO_OVERRIDE_LAYOUT_Q4_20261020.json")]
    if "--root" not in sys.argv:
        sys.argv += ["--root", str(HERE.parents[1])]
    raise SystemExit(base.main())
