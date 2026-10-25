#!/usr/bin/env python3
"""Persistent worker for crate/footlocker loot prediction (one JSON request per line)."""
from __future__ import annotations

import contextlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIVE_TOOLS = Path("D:/Orca/NMS-Derelict-Probe/tools")
sys.path.insert(0, str(HERE))
if HERE != LIVE_TOOLS:          # staging copy: unchanged tools come from the live folder
    sys.path.insert(1, str(LIVE_TOOLS))
sys.path.insert(0, os.environ.get("NMS_FASTGEN_DIR", "D:/Orca/NMS-Derelict-Probe-fastgen"))

import fast_generate_705 as fast  # noqa: E402
sys.path.insert(0, str(HERE))   # fast_generate puts the live tools folder first; this folder wins
import native_writer_705 as native  # noqa: E402
import predict_crate_loot_705 as crate  # noqa: E402
import predict_end_reward_705 as end_reward  # noqa: E402
from space_poi_position_705 import PoiGen  # noqa: E402
from nms_paths_705 import fix_enabled, out_path  # noqa: E402

CACHE_ROOT = out_path("D:/Orca/NMS-Derelict-Probe-analysis/crate-loot-cache")


def cached_layout(address: str) -> dict | None:
    for root in end_reward.LAYOUT_DIRS:
        path = root / address / "derelict.json"
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            if "instances" in data and data.get("address", address).upper() == address:
                return data
    return None


def summarize(address: str, layout: dict, prediction: dict) -> dict:
    """Return compact fields; ids index layout.containers, the same order packed for viewer views."""
    keys = {}
    for i, c in enumerate(layout.get("containers", [])):
        key = (c.get("room_index"), c.get("container_kind"), c.get("scene_node_name"),
               tuple(round(float(x), 3) for x in c["layout_local_xyz"]))
        keys.setdefault(key, []).append(i)
    module_ids, ambiguous_ids, rooms = set(), set(), set()
    ambiguous = 0
    for c in prediction.get("containers", []):
        key = (c.get("room"), c.get("kind"), c.get("node"), tuple(c.get("layout_xyz", ())))
        ids = keys.get(key)
        if not ids:
            # scene node labels are optional in older cached layouts; position/kind/room remain unique.
            key = (c.get("room"), c.get("kind"), None, tuple(c.get("layout_xyz", ())))
            ids = keys.get(key)
        if not ids:
            raise ValueError(f"{address}: predicted container has no matching layout index: {key!r}")
        index = ids.pop(0)
        base_module = c.get("loot", {}).get("key") == "FRIG_TOKEN"
        # The single-system tool serializes alternative loot as human-readable text.
        alt_modules = {str(a.get("loot", "")).startswith("Salvaged Frigate Module")
                       for a in c.get("alternatives", [])}
        differs = bool(alt_modules and any(value != base_module for value in alt_modules))
        if base_module:
            module_ids.add(index)
            if c.get("room") is not None:
                rooms.add(int(c["room"]))
        if differs:
            ambiguous += 1
            ambiguous_ids.add(index)
    encode = lambda xs: ".".join(str(i) for i in sorted(xs))
    return {
        "address": address,
        "frigate_modules": len(module_ids),
        "frigate_modules_ambiguous": ambiguous,
        "frigate_module_rooms": encode(rooms),
        "frigate_module_ids": encode(module_ids),
        # Ambiguous container indexes; viewer distinguishes possible-only ids by subtracting frigate_module_ids.
        "frigate_module_alt_ids": encode(ambiguous_ids),
    }


def main() -> None:
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    protocol = sys.stdout
    with contextlib.redirect_stdout(sys.stderr):
        session = native.NativeSession()
        fast.cached_catalog()
        poi = PoiGen()

    def writer(seed, preset_index, out, max_insns, counters=False):
        if counters or max_insns:
            return fast.run_writer(seed, preset_index, out, max_insns, counters)
        result, seconds, info = session.run(seed, preset_index)
        _, code = session.write_outputs(out, result, seconds, info)
        if code:
            raise RuntimeError(f"native writer returned {code}")
        fast._engine_used["engine"] = "native-crate-loot-worker"
        return 0, seconds

    print(json.dumps({"ready": True}), file=protocol, flush=True)
    for line in sys.stdin:
        if not line.strip():
            continue
        address = None
        try:
            request = json.loads(line)
            address = str(request["address"]).upper()
            if len(address) != 16 or any(c not in "0123456789ABCDEF" for c in address):
                raise ValueError("address must be 16 hex digits")
            start = time.monotonic()
            layout = request.get("layout") or cached_layout(address)
            reused = layout is not None
            if layout is None:
                with tempfile.TemporaryDirectory(prefix="nms_crate_worker_", dir=CACHE_ROOT) as directory:
                    with contextlib.redirect_stdout(sys.stderr):
                        code = fast.generate(["fast_generate_705.py", address, "--out", directory, "--override", "0"], writer=writer)
                    if code:
                        raise RuntimeError(f"fast generator returned {code}")
                    layout = json.loads((Path(directory) / "derelict.json").read_text(encoding="utf-8"))
            layout_seconds = time.monotonic() - start
            point = poi.positions(int(address, 16))
            prediction = crate.predict(address, point, layout, None, ("salvage_crate", "crew_footlocker"))
            summary = summarize(address, layout, prediction)
            reply = {"address": address, "summary": summary, "prediction": prediction,
                     "layout_reused": reused, "layout_seconds": round(layout_seconds, 4),
                     "total_seconds": round(time.monotonic() - start, 4)}
            if request.get("cache") and fix_enabled("scancache"):
                import scan_cache_705
                reply["scan_cache"] = scan_cache_705.encode(scan_cache_705.record(address, layout, point))
            print(json.dumps(reply, separators=(",", ":")), file=protocol, flush=True)
        except Exception as exc:
            print(json.dumps({"address": address, "error": f"{type(exc).__name__}: {exc}"}), file=protocol, flush=True)


if __name__ == "__main__":
    main()
