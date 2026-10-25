#!/usr/bin/env python3
"""Persistent worker for tools/frigate_search_705.py (one JSON request per line on stdin, one reply per line).

2026-10-23: ported to the live fast pipeline. The worker loads the combined region-scan worker module
(tools/scan_worker_705.py: same sys.path set-up, the same fast generator, native writer, fast-POI PoiGen,
crate.predict and summarize the live scanner uses) and adds the searcher's stage B in front of it:

Request: {"address": "<16 hex>", "min_containers": <int or null>}
Stages inside the worker, each timed:
  writer  : native layout writer (NativeSession, in memory) -> room count + placement records. With env
            NMS_WRITER_CACHE=<sqlite> (set by the driver unless --writer-cache off) a cached writer result is
            restored instead of rerunning the game's writer (exact; see native_writer_705.WriterCache).
  cfilter : (only if min_containers is set) crate+footlocker count predicted from the placement records with the
            per-template table research-output/FRIGATE_SEARCH_CONTAINER_TABLE_20261022.json; below -> rejected
            without transforms/POI/loot
  layout  : fast_generate_705.generate reusing the writer result already in memory (same writer wrapper as
            scan_worker_705.py, incl. its Unicorn fallback) -> transforms + containers
  poi     : ONE ABAND_FREIGHTER space-POI computation (PoiGen with the fast powf/frexp hook)
  loot    : predict_crate_loot_705.predict + crate_loot_worker_705.summarize (same code as the scanner)
Read-only reuse of fastgen + tools modules; nothing in them is modified. Scratch files go to a temp dir.
"""
from __future__ import annotations

import contextlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scan_worker_705 as SW  # noqa: E402  (sets up sys.path and imports the live generator chain)

F, N, crate, summarize, PoiGen = SW.F, SW.N, SW.crate, SW.summarize, SW.PoiGen
from derelict_seed_preset_705 import derelict_seed_preset  # noqa: E402

TABLE = HERE.parent / "research-output" / "FRIGATE_SEARCH_CONTAINER_TABLE_20261022.json"
SCRATCH = Path(os.environ.get("FRIGATE_SEARCH_SCRATCH", "D:/Orca/Temp/claude/frigate-search-20261022/work"))


def main() -> None:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    protocol = sys.stdout
    with contextlib.redirect_stdout(sys.stderr):
        session = N.NativeSession()   # before Unicorn: the native writer reserves fixed address ranges
        F.cached_catalog()
        poi = PoiGen()
    table = json.loads(TABLE.read_text(encoding="utf-8"))["containers_per_placement"] if TABLE.exists() else None
    state = {}

    def writer(seed, preset_index, out, max_insns, counters=False):
        """scan_worker_705's writer, reusing the run already done in stage 'writer' (same seed/preset)."""
        if counters or max_insns:
            return F.run_writer(seed, preset_index, out, max_insns, counters)
        if state.get("key") != (seed, preset_index):
            state["key"] = (seed, preset_index)
            state["run"] = session.run(seed, preset_index)
        res, secs, info = state.pop("run")
        state.pop("key")
        _, code = session.write_outputs(out, res, secs, info)
        if code == 0:
            F._engine_used["engine"] = "native-worker"
            return 0, secs
        F._engine_used["native_failure"] = f"exit {code}"
        (Path(out) / "last_run_summary.json").unlink(missing_ok=True)
        F._engine_used["engine"] = "unicorn"
        return F.UNICORN_RUN_WRITER(seed, preset_index, out, max_insns, counters)

    cache = getattr(session, "cache", None)
    print(json.dumps({"ready": True, "table": table is not None, "fast_poi": bool(getattr(poi, "fast_hook", False)),
                      "writer_cache": cache.path if cache is not None else None}), file=protocol, flush=True)
    timing = {}
    for line in sys.stdin:
        if not line.strip():
            continue
        address = None
        try:
            request = json.loads(line)
            address = str(request["address"]).upper()
            if len(address) != 16 or any(c not in "0123456789ABCDEF" for c in address):
                raise ValueError("address must be 16 hex digits")
            min_c = request.get("min_containers")
            timing.clear()
            t0 = time.perf_counter()
            seed, preset, pidx = derelict_seed_preset(address)
            state["key"] = (seed, pidx)
            state["run"] = session.run(seed, pidx)
            hit = bool(getattr(session, "last_cache_hit", False))
            res = state["run"][0]
            rooms = int(res["rax"]) if res.get("ok") == 1 else None
            reply = {"address": address, "preset": preset, "rooms": rooms, "cache_hit": hit}
            t1 = time.perf_counter()
            timing["writer"] = t1 - t0
            est = None
            if min_c is not None and table is not None and session.e.rq(session.e.cap) != N.M64:
                e = session.e
                n = e.ri(e.cap)
                recs = N.placements_json(e, session.inp, e.rd(e.cap + 0x10, n * 20), n)
                est = sum(table.get(r["id"], 0) for r in recs)
                reply["containers_est"] = est
            timing["cfilter"] = time.perf_counter() - t1
            if est is not None and est < int(min_c):
                state.clear()
                reply.update(stage="rejected-containers", timing={k: round(v, 5) for k, v in timing.items()})
                print(json.dumps(reply, separators=(",", ":")), file=protocol, flush=True)
                continue
            t2 = time.perf_counter()
            with tempfile.TemporaryDirectory(prefix="fs_", dir=SCRATCH) as directory:
                with contextlib.redirect_stdout(sys.stderr):
                    code = F.generate(["fast_generate_705.py", address, "--out", directory, "--override", "0"],
                                      writer=writer)
                if code:
                    raise RuntimeError(f"fast generator returned {code}")
                layout = json.loads((Path(directory) / "derelict.json").read_text(encoding="utf-8"))
            state.clear()
            t3 = time.perf_counter()
            timing["layout"] = t3 - t2
            point = poi.positions(int(address, 16))
            t4 = time.perf_counter()
            timing["poi"] = t4 - t3
            prediction = crate.predict(address, point, layout, None, ("salvage_crate", "crew_footlocker"))
            summary = summarize(address, layout, prediction)
            timing["loot"] = time.perf_counter() - t4
            kinds = layout.get("container_kinds", {})
            reply.update(stage="full", rooms=layout.get("room_count"),
                         crates=kinds.get("salvage_crate", 0), footlockers=kinds.get("crew_footlocker", 0),
                         poi_found=bool(point and point.get("aband_freighter") is not None),
                         summary=summary, timing={k: round(v, 5) for k, v in timing.items()})
            print(json.dumps(reply, separators=(",", ":")), file=protocol, flush=True)
        except Exception as exc:
            state.clear()
            print(json.dumps({"address": address, "error": f"{type(exc).__name__}: {exc}"}), file=protocol, flush=True)
    if cache is not None:
        cache.flush()


if __name__ == "__main__":
    main()
