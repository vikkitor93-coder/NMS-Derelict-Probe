"""Live self-test of the auto-detected address path (needs NMS running with a save loaded; read-only).

    python -I minimap/selftest_autofind_live.py

Reads the player's address and position twice, back to back: once with the built-in 7.05 chain and once with the chain the
address finder derives from the installed NMS.exe as if the build were unknown (MINIMAP_FORCE_AUTO). They must agree. This is
the closest test of "the minimap survives a game update" that is possible without a second game build.
Uses a scratch learned-builds file, so nothing in the minimap folder changes.
"""
from __future__ import annotations

import math
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
os.environ["MINIMAP_LEARNED_FILE"] = str(Path(tempfile.mkdtemp()) / "learned.json")
import live_position_705 as L  # noqa: E402


def main() -> int:
    pid = L.find_pid()
    if not pid:
        print("SKIP: NMS is not running")
        return 0
    os.environ.pop("MINIMAP_FORCE_AUTO", None)
    known = L.LiveReader(pid)
    if known.build_error or not known.verified:
        print("SKIP: the built-in chain does not apply to this build:", known.build_error or "unverified")
        return 0
    a = known.sample()
    os.environ["MINIMAP_FORCE_AUTO"] = "1"
    auto = L.LiveReader(pid)
    b = auto.sample()
    if auto.build_error:
        print("FAIL: auto path:", auto.build_error)
        return 1
    print(f"known chain : app_rva {known.build['app_rva']:#x} data_ptr {known.build['data_ptr']:#x} -> {a and a['address']}")
    print(f"auto chain  : app_rva {auto.build['app_rva']:#x} data_ptr {auto.build['data_ptr']:#x} -> {b and b['address']}  "
          f"(verified={auto.verified}, {auto.build.get('source')})")
    known.close()
    auto.close()
    if a is None or b is None:
        print("SKIP: no reading yet (load a save first)" + (f"; {auto.sanity_error}" if auto.sanity_error else ""))
        return 0
    if a["address"] != b["address"]:
        print("FAIL: addresses differ")
        return 1
    d = math.dist((a["x"], a["y"], a["z"]), (b["x"], b["y"], b["z"]))
    if d > 5:
        print(f"FAIL: positions differ by {d:.1f}")
        return 1
    print(f"PASS: same address and position (distance {d:.2f}) through the auto-detected addresses")
    return 0


if __name__ == "__main__":
    sys.exit(main())
