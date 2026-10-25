#!/usr/bin/env python3
"""Q4b diagnostic: CARGO_BUGS reconstruction using the *native* live A2780 source rows
(run 98a782a5, source-rows.bin) as A3270/A23B0 map input, rank-matched by descriptor key
(the key sequence is identical to the Q4 catalog, see Q4B_LIVE_ROW_COMPARE_20261020.json).

  --fit q4b       corrected A3270 (nms_dungeon_fit_705_q4b)   [default]
  --fit original  original nms_dungeon_fit_705
Output: CARGO_BUGS_ZERO_OVERRIDE_LAYOUT_Q4B_NATIVE_ROWS_<FIT>_20261020.json

Run:
  python -I -c "import sys,runpy; d=r'D:/Orca/NMS-Derelict-Probe/research-output/offline-layout-705-20261019'; sys.path.insert(0,d); sys.argv=['x','--fit','q4b']; runpy.run_path(d+'/reconstruct_cargo_bugs_candidate_705_q4b_native_rows.py', run_name='__main__')"
"""
from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

fit = "q4b"
if "--fit" in sys.argv:
    i = sys.argv.index("--fit"); fit = sys.argv[i + 1]; del sys.argv[i:i + 2]

import nms_dungeon_fit_705_q4b as q4b  # noqa: E402
import nms_dungeon_fit_705  # noqa: E402
import nms_dungeon_a2780_search_705  # noqa: E402
import nms_dungeon_variable_placement_705  # noqa: E402
import nms_dungeon_offline  # noqa: E402

if fit == "q4b":
    for _m in (nms_dungeon_fit_705, nms_dungeon_a2780_search_705, nms_dungeon_variable_placement_705, nms_dungeon_offline):
        if hasattr(_m, "fits_room_piece_705"):
            _m.fits_room_piece_705 = q4b.fits_room_piece_705

import reconstruct_cargo_bugs_candidate_705 as base  # noqa: E402
from nms_dungeon_reference_closure_q4_705 import Q4SourceCatalog  # noqa: E402
from q4b_compare_live_rows_705 import native_rows, build_mapping  # noqa: E402


class NativeRowCatalog(Q4SourceCatalog):
    _native_map = None

    def materialize_scene_map(self, map_index, **kw):
        m = super().materialize_scene_map(map_index, **kw)
        if NativeRowCatalog._native_map is None:
            NativeRowCatalog._native_map = build_mapping(self, native_rows())[3]
        raw = NativeRowCatalog._native_map[map_index]["raw"]
        prefix = raw[:0x25E]
        row = prefix + bytes(0x2B0 - 0x25E)
        return dataclasses.replace(m, native_map_prefix=prefix, native_map_row_for_fit=row,
                                   bounds_source="native live row 98a782a5")


base.GeneratedBaseSourceCatalog = NativeRowCatalog

if __name__ == "__main__":
    if "--output" not in sys.argv:
        sys.argv += ["--output", str(HERE / f"CARGO_BUGS_ZERO_OVERRIDE_LAYOUT_Q4B_NATIVE_ROWS_{fit.upper()}_20261020.json")]
    if "--root" not in sys.argv:
        sys.argv += ["--root", str(HERE.parents[1])]
    raise SystemExit(base.main())
