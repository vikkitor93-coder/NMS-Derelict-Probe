#!/usr/bin/env python3
"""Q4 diagnostic: replay the first A2780 call of the CARGO_BUGS candidate with both map providers.

Pre-A2780 writer stages never read 0x2B0 map rows (A1DA0 uses manager-map dimensions), so the
first A2780 call happens at the identical RNG/grid/room state for both providers. This script
snapshots that call (original provider, seed 7D7ED1B33E15365D, same limits as the candidate
driver), then re-runs A2780 from the snapshot with:
  A  original root-MXML provider            (expected: 59,606 placements, success)
  B  Q4 reference-aware provider            (as native would see it if REFERENCE import is active)
  C  Q4 provider, quest tags zeroed         (themes only; diagnostic of decoration volume)
and prints counts, zero-dimension usage and the first quest failure.
"""
from __future__ import annotations

import copy, json, struct, sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

import nms_dungeon_writer_search_705 as ws  # noqa: E402
import nms_dungeon_a2780_search_705 as a27  # noqa: E402
import reconstruct_cargo_bugs_candidate_705 as base  # noqa: E402
from nms_dungeon_source_catalog_705 import GeneratedBaseSourceCatalog  # noqa: E402
from nms_dungeon_reference_closure_q4_705 import Q4SourceCatalog  # noqa: E402


class _Snap(Exception):
    pass


snapshot: dict = {}
_real = ws.run_a2780_search


def _capture(**kw):
    snapshot.update({k: v for k, v in kw.items() if k not in ("rng", "grid", "catalog", "map_row_provider")})
    snapshot["rng_state"] = kw["rng"].state
    snapshot["grid"] = copy.deepcopy(kw["grid"])
    snapshot["rng_cls"] = type(kw["rng"])
    raise _Snap


def run(catalog, *, zero_quests=False):
    cache = {}

    def provider(i):
        if i not in cache:
            cache[i] = catalog.materialize_scene_map(i).native_map_row_for_fit
        return cache[i]

    records = list(snapshot["room_records"])
    if zero_quests:
        records = [r[:0x39] + b"\x00" + r[0x3A:] for r in records]
    kw = {k: v for k, v in snapshot.items() if k not in ("rng_state", "grid", "rng_cls", "room_records")}
    res = _real(rng=snapshot["rng_cls"](snapshot["rng_state"]), catalog=catalog, room_records=records,
                grid=copy.deepcopy(snapshot["grid"]), map_row_provider=provider, **kw)
    zero = sum(1 for p in res.placements
               if 0 in struct.unpack_from("<HHH", provider(p.source_map_index), 0x258))
    by_room = Counter(p.room_index for p in res.placements)
    quest = [e for e in res.events if e.kind == "quest-placement"]
    return {"success": res.success, "failure": res.failure_reason, "placements": len(res.placements),
            "zero_dimension_placements": zero, "per_room": dict(sorted(by_room.items())),
            "quest_events": [{"room": e.room_index, "layer": e.layer, "selector": e.selector,
                              "row": e.source_map_index,
                              "row_dims": struct.unpack_from("<HHH", provider(e.source_map_index), 0x258),
                              "coord": e.coordinate, "detail": e.detail[:160]} for e in quest]}


def main() -> int:
    ws.run_a2780_search = _capture
    try:
        base.build_candidate(ROOT, seed_u64=base.DEFAULT_WRITER_SEED, selection_limit=1000, tolerance=0.01)
    except _Snap:
        pass
    finally:
        ws.run_a2780_search = _real
    if not snapshot:
        raise SystemExit("writer never reached A2780")
    rooms = snapshot["room_records"]
    out = {"room_count": snapshot["room_count"],
           "room_quest_tag_counts": [r[0x39] for r in rooms],
           "fit_min": list(snapshot["fit_min_xyz"]), "fit_max": list(snapshot["fit_max_xyz"]),
           "A_original": run(GeneratedBaseSourceCatalog.from_workspace(ROOT))}
    q4 = Q4SourceCatalog.from_workspace(ROOT)
    out["B_q4"] = run(q4)
    out["C_q4_no_quests"] = run(q4, zero_quests=True)
    for key in ("A_original", "B_q4", "C_q4_no_quests"):
        out[key]["quest_events"] = out[key]["quest_events"][:12]
    text = json.dumps(out, indent=1, default=str)
    (HERE / "Q4_A2780_SNAPSHOT_DIAG_20261020.json").write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
