"""Persistent offline end-reward worker (one JSON request and response per line).

Run with the Shipwright Python environment and -I.  The native writer is
initialized before Unicorn, because it reserves fixed address ranges.
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
LIVE_TOOLS = Path("D:/Orca/NMS-Derelict-Probe/tools")
sys.path.insert(0, str(HERE))
if HERE != LIVE_TOOLS:          # staging copy: unchanged tools come from the live folder
    sys.path.insert(1, str(LIVE_TOOLS))
sys.path.insert(0, os.environ.get("NMS_FASTGEN_DIR", "D:/Orca/NMS-Derelict-Probe-fastgen"))

import fast_generate_705 as fast  # noqa: E402
sys.path.insert(0, str(HERE))   # fast_generate puts the live tools folder first; this folder wins
import native_writer_705 as native  # noqa: E402
import predict_end_reward_705 as predictor  # noqa: E402
from space_poi_position_705 import PoiGen  # noqa: E402
from nms_paths_705 import out_path  # noqa: E402

TEMP_ROOT = out_path("D:/Orca/NMS-Derelict-Probe-analysis/end-reward-cache")


def cached_layout(address: str) -> dict | None:
    for root in predictor.LAYOUT_DIRS:
        path = root / address / "derelict.json"
        if path.is_file():
            layout = json.loads(path.read_text(encoding="utf-8"))
            if "instances" in layout and layout.get("address", address).upper() == address:
                return layout
    return None


def main() -> None:
    protocol = sys.stdout
    TEMP_ROOT.mkdir(parents=True, exist_ok=True)
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
        fast._engine_used["engine"] = "native-reward-worker"
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
                with tempfile.TemporaryDirectory(prefix="nms_reward_worker_", dir=TEMP_ROOT) as directory:
                    with contextlib.redirect_stdout(sys.stderr):
                        code = fast.generate(["fast_generate_705.py", address, "--out", directory, "--override", "0"], writer=writer)
                    if code:
                        raise RuntimeError(f"fast generator returned {code}")
                    layout = json.loads((Path(directory) / "derelict.json").read_text(encoding="utf-8"))
            layout_seconds = time.monotonic() - start
            point = poi.positions(int(address, 16))
            result = predictor.predict(address, point, layout)
            print(json.dumps({"address": address, "result": result, "layout_reused": reused,
                              "layout_seconds": round(layout_seconds, 4),
                              "total_seconds": round(time.monotonic() - start, 4)}), file=protocol, flush=True)
        except Exception as exc:
            print(json.dumps({"address": address, "error": f"{type(exc).__name__}: {exc}"}), file=protocol, flush=True)


if __name__ == "__main__":
    main()
