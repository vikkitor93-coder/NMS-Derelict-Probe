#!/usr/bin/env python3
"""Q4b diagnostic: replay the first A2780 call of the CARGO_BUGS candidate (same snapshot method as
q4_a2780_snapshot_diag_705.py) with the native live map rows (run 98a782a5). Every A3270 call is
evaluated with both the original port and the Q4b port. The run's control flow follows the Q4b result.
Writes Q4B_A2780_SNAPSHOT_DIAG_20261020.json.
"""
from __future__ import annotations
import copy, json, struct, sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

import nms_dungeon_writer_search_705 as ws  # noqa: E402
import nms_dungeon_a2780_search_705 as a27  # noqa: E402
import nms_dungeon_variable_placement_705 as vp  # noqa: E402
import nms_dungeon_fit_705 as orig  # noqa: E402
import nms_dungeon_fit_705_q4b as q4b  # noqa: E402
import reconstruct_cargo_bugs_candidate_705 as base  # noqa: E402
import reconstruct_cargo_bugs_candidate_705_q4b_native_rows as nr  # noqa: E402  (patches fit globally)

ORIG_FIT = orig.__dict__.get("_orig_fits", None)
import importlib.util
_spec = importlib.util.spec_from_file_location("_fit_orig_copy", HERE / "nms_dungeon_fit_705.py")
_fo = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_fo)

snapshot: dict = {}
_real = ws.run_a2780_search


class _Snap(Exception):
    pass


def _capture(**kw):
    snapshot.update({k: v for k, v in kw.items() if k not in ("rng", "grid", "catalog", "map_row_provider")})
    snapshot["rng_state"] = kw["rng"].state
    snapshot["grid"] = copy.deepcopy(kw["grid"])
    snapshot["rng_cls"] = type(kw["rng"])
    raise _Snap


stats = {"theme": defaultdict(Counter), "quest": defaultdict(Counter)}
reasons = {"theme": Counter(), "quest": Counter()}
mode = ["theme"]


def make_wrapper(kind):
    def w(**kw):
        try:
            o = _fo.fits_room_piece_705(**kw)
        except NotImplementedError:
            o = "NotImpl"
        r = q4b.fit_reason_705(**kw)
        room = kw["expected_neighbor_tag"]
        stats[kind][room]["calls"] += 1
        stats[kind][room]["orig_fit"] += (o is True)
        stats[kind][room]["q4b_fit"] += (r is None)
        if r is not None:
            reasons[kind][r] += 1
        return r is None
    return w


def main():
    ws.run_a2780_search = _capture
    try:
        base.build_candidate(ROOT, seed_u64=base.DEFAULT_WRITER_SEED, selection_limit=1000, tolerance=0.01)
    except _Snap:
        pass
    finally:
        ws.run_a2780_search = _real
    if not snapshot:
        raise SystemExit("writer never reached A2780")
    a27.fits_room_piece_705 = make_wrapper("theme")
    vp.fits_room_piece_705 = make_wrapper("quest")
    cat = nr.NativeRowCatalog.from_workspace(ROOT)
    cache = {}

    def provider(i):
        if i not in cache:
            cache[i] = cat.materialize_scene_map(i).native_map_row_for_fit
        return cache[i]

    kw = {k: v for k, v in snapshot.items() if k not in ("rng_state", "grid", "rng_cls")}
    res = _real(rng=snapshot["rng_cls"](snapshot["rng_state"]), catalog=cat, grid=copy.deepcopy(snapshot["grid"]),
                map_row_provider=provider, **kw)
    names = {m.row_index: m.key_pair.rstrip(b"\0").decode("latin1") for m in cat.source_metadata()}
    quest = [{"room": e.room_index, "layer": e.layer, "row": e.source_map_index, "name": names.get(e.source_map_index),
              "dims": struct.unpack_from("<HHH", provider(e.source_map_index), 0x258), "coord": e.coordinate,
              "detail": e.detail[-40:]} for e in res.events if e.kind == "quest-placement"]
    out = {"room_count": snapshot["room_count"], "fit_min": list(snapshot["fit_min_xyz"]), "fit_max": list(snapshot["fit_max_xyz"]),
           "success": res.success, "failure": res.failure_reason, "placements": len(res.placements),
           "per_room_placements": dict(sorted(Counter(p.room_index for p in res.placements).items())),
           "placement_names": dict(Counter(names.get(p.source_map_index) for p in res.placements).most_common()),
           "fit_calls": {k: {r: dict(c) for r, c in sorted(v.items())} for k, v in stats.items()},
           "q4b_reject_reasons": {k: dict(v) for k, v in reasons.items()},
           "quest_events": quest}
    (HERE / "Q4B_A2780_SNAPSHOT_DIAG_20261020.json").write_text(json.dumps(out, indent=1, default=str) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
