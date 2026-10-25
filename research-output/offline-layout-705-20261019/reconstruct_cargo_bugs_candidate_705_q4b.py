#!/usr/bin/env python3
"""Q4b rerun: the Q4 recursive map provider plus the corrected A3270 port (nms_dungeon_fit_705_q4b).

Identical to reconstruct_cargo_bugs_candidate_705_q4.py, except that fits_room_piece_705 is
replaced in every module that bound it at import time.
Default output: CARGO_BUGS_ZERO_OVERRIDE_LAYOUT_Q4B_20261020.json next to this file.

Run:
  python -I -c "import sys,runpy; d=r'D:/Orca/NMS-Derelict-Probe/research-output/offline-layout-705-20261019'; sys.path.insert(0,d); runpy.run_path(d+'/reconstruct_cargo_bugs_candidate_705_q4b.py', run_name='__main__')"
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import nms_dungeon_fit_705_q4b as q4b  # noqa: E402
import nms_dungeon_fit_705  # noqa: E402
import nms_dungeon_a2780_search_705  # noqa: E402
import nms_dungeon_variable_placement_705  # noqa: E402
import nms_dungeon_offline  # noqa: E402

for _m in (nms_dungeon_fit_705, nms_dungeon_a2780_search_705, nms_dungeon_variable_placement_705, nms_dungeon_offline):
    if hasattr(_m, "fits_room_piece_705"):
        _m.fits_room_piece_705 = q4b.fits_room_piece_705

import reconstruct_cargo_bugs_candidate_705 as base  # noqa: E402
from nms_dungeon_reference_closure_q4_705 import Q4SourceCatalog  # noqa: E402

base.GeneratedBaseSourceCatalog = Q4SourceCatalog

if __name__ == "__main__":
    if "--output" not in sys.argv:
        sys.argv += ["--output", str(HERE / "CARGO_BUGS_ZERO_OVERRIDE_LAYOUT_Q4B_20261020.json")]
    if "--root" not in sys.argv:
        sys.argv += ["--root", str(HERE.parents[1])]
    raise SystemExit(base.main())
