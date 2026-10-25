#!/usr/bin/env python3
"""Combined region-scan worker (speed fix 2, 2026-10-22): one persistent Shipwright-Python process per worker slot
does what fast_worker_705.py + RewardPool + CrateLootPool did for each scanned system:

  generate the layout (native writer, same code as fast_worker_705.py; writes <out>/derelict.json + generate.log)
  -> ONE space-POI computation -> end reward -> Salvaged Frigate Module summary -> scan-cache record (fix 4).

No second POI, and the layout is never sent through a pipe as JSON (the scanner still reads <out>/derelict.json once,
as before, for Store.add_layout). Run with the Shipwright venv python and -I.

Protocol (one JSON object per line), a superset of fast_worker_705.py:
  stdin : {"address": "<16 hex>", "out": "<dir>", "override": "0"}
  stdout: {"ready": true} once, then per request
          {"address", "code", "seconds",
           "reward": [name, class, ambiguous, alt] | null,      (null: no prediction; the scanner falls back)
           "frigate": [modules, ambiguous, rooms, ids, alt_ids] | null,
           "scan_cache": "<compact JSON record>" | null,
           "errors": {"reward"|"frigate"|"scan_cache"|"layout": "..."}}
"""
from __future__ import annotations

import contextlib
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIVE_TOOLS = Path("D:/Orca/NMS-Derelict-Probe/tools")
sys.path.insert(0, str(HERE))
if HERE != LIVE_TOOLS:          # staging copy: unchanged tools come from the live folder
    sys.path.insert(1, str(LIVE_TOOLS))
sys.path.insert(0, os.environ.get("NMS_FASTGEN_DIR", "D:/Orca/NMS-Derelict-Probe-fastgen"))

import fast_generate_705 as F  # noqa: E402
sys.path.insert(0, str(HERE))   # fast_generate puts the live tools folder first; this folder wins
import native_writer_705 as N  # noqa: E402
import predict_crate_loot_705 as crate  # noqa: E402
import predict_end_reward_705 as end_reward  # noqa: E402
from crate_loot_worker_705 import summarize  # noqa: E402
from end_reward_batch_705 import result_row  # noqa: E402
from space_poi_position_705 import PoiGen  # noqa: E402
from nms_paths_705 import fix_enabled  # noqa: E402

FRIGATE_KEYS = ("frigate_modules", "frigate_modules_ambiguous", "frigate_module_rooms", "frigate_module_ids",
                "frigate_module_alt_ids")


def main():
    proto = sys.stdout
    with contextlib.redirect_stdout(sys.stderr):
        sess = N.NativeSession()      # before Unicorn: the native writer reserves fixed address ranges
        F.cached_catalog()
        poi = PoiGen()
    want_cache = fix_enabled("scancache")
    if want_cache:
        import scan_cache_705 as SC

    def writer(seed, preset_index, out, max_insns, counters=False):     # == fast_worker_705.py
        if counters or max_insns:
            return F.run_writer(seed, preset_index, out, max_insns, counters)
        res, secs, info = sess.run(seed, preset_index)
        _, code = sess.write_outputs(out, res, secs, info)
        if code == 0:
            F._engine_used["engine"] = "native-worker"
            return 0, secs
        F._engine_used["native_failure"] = f"exit {code}"
        (Path(out) / "last_run_summary.json").unlink(missing_ok=True)
        F._engine_used["engine"] = "unicorn"
        return F.UNICORN_RUN_WRITER(seed, preset_index, out, max_insns, counters)

    print(json.dumps({"ready": True}), file=proto, flush=True)
    for line in sys.stdin:
        if not line.strip():
            continue
        job = json.loads(line)
        address = str(job["address"]).upper()
        out = Path(job["out"])
        out.mkdir(parents=True, exist_ok=True)
        t = time.time()
        with open(out / "generate.log", "w", encoding="utf-8") as log, contextlib.redirect_stdout(log):
            code = F.generate(["fast_generate_705.py", address, "--out", str(out),
                               "--override", job.get("override", "0")], writer=writer)
        reply = {"address": job["address"], "code": code, "reward": None, "frigate": None, "scan_cache": None,
                 "errors": {}}
        try:
            layout = json.loads((out / "derelict.json").read_text(encoding="utf-8"))
            if "instances" not in layout:
                layout = None
        except (OSError, ValueError) as exc:
            layout = None
            reply["errors"]["layout"] = f"{type(exc).__name__}: {exc}"
        if layout is not None:
            point = None
            try:
                point = poi.positions(int(address, 16))
            except Exception as exc:  # the scanner falls back to its pools for this system
                reply["errors"]["poi"] = f"{type(exc).__name__}: {exc}"
            if point is not None:
                try:
                    reply["reward"] = list(result_row(end_reward.predict(address, point, layout)))
                except Exception as exc:
                    reply["errors"]["reward"] = f"{type(exc).__name__}: {exc}"
                try:
                    prediction = crate.predict(address, point, layout, None, ("salvage_crate", "crew_footlocker"))
                    summary = summarize(address, layout, prediction)
                    reply["frigate"] = [summary[k] for k in FRIGATE_KEYS]
                except Exception as exc:
                    reply["errors"]["frigate"] = f"{type(exc).__name__}: {exc}"
                if want_cache:
                    try:
                        reply["scan_cache"] = SC.encode(SC.record(address, layout, point))
                    except Exception as exc:
                        reply["errors"]["scan_cache"] = f"{type(exc).__name__}: {exc}"
        reply["seconds"] = round(time.time() - t, 3)
        print(json.dumps(reply, separators=(",", ":")), file=proto, flush=True)


if __name__ == "__main__":
    main()
