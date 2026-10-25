#!/usr/bin/env python3
"""STUB generator for the on-demand map server (stage 2, A4). NOT the real generator.

The real layout generator (tools/scan_worker_705.py and what it imports) is partly lost and is being rebuilt elsewhere.
This file lets ondemand_server.py be run and tested without it: `--generator stub` (or "generator": "stub" in config.json).

What it provides (same line protocol as scan_worker_705.py, which the server drives):
  stdout  {"ready": true}                                   once at start
  stdin   {"address": "<ADDR16>", "out": "<dir>"}           one JSON line per job
  stdout  {"code": 0, "errors": {}, "frigate": [mods, amb]} one JSON line per job; <dir>/derelict.json holds the layout
and, for in-process use by the server: preset_of(), region_count(), layout_of().

Everything is deterministic from the address (sha256), so tests can predict it.  Environment knobs for tests:
  STUB_DELAY_S   base delay per job in seconds (default 0.3); presets ending in TURRETS take 8x that
  STUB_FAIL      "1": every job answers code 1 (generator failure)
  STUB_HANG_S    sleep this long before answering (tests the job timeout / kill)
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

PRESETS = ["CARGO_BUGS", "CARGO_FLOATERS", "CARGO_TURRETS", "MEDI_BUGS", "MEDI_FLOATERS", "MEDI_TURRETS",
           "SCI_BUGS", "SCI_FLOATERS", "SCI_TURRETS", "RES_BUGS"]


def _h(address: str, salt: str = "") -> int:
    return int.from_bytes(hashlib.sha256((salt + address.upper()).encode()).digest()[:8], "big")


def preset_of(address: str) -> str:
    return PRESETS[_h(address, "p") % len(PRESETS)]


def region_count(region: str) -> int:
    """System count of a region (stand-in for app/rc_worker.py): 400..1399."""
    return 400 + _h(region, "r") % 1000


def layout_of(address: str) -> dict:
    h = _h(address, "l")
    rooms = 6 + h % 8
    crates = 5 + (h >> 8) % 20
    foot = 2 + (h >> 16) % 12
    return {
        "address": address.upper(), "preset": preset_of(address), "stub": True,
        "rooms": [{"id": i, "kind": "STUB_ROOM"} for i in range(rooms)],
        "container_kinds": {"salvage_crate": crates, "crew_footlocker": foot},
        "instances": [{"scene_resource": f"STUB/PIECE{(h >> (i % 20)) % 6}.SCENE.MBIN", "index": i} for i in range(rooms * 3)],
        "frigate": [(h >> 24) % 9, (h >> 32) % 2],
    }


def _base_delay(address: str) -> float:
    d = float(os.environ.get("STUB_DELAY_S", "0.3"))
    return d * (8 if preset_of(address).endswith("TURRETS") else 1)


def main() -> int:
    print(json.dumps({"ready": True}), flush=True)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            address, out = str(req["address"]).upper(), Path(req["out"])
        except (ValueError, KeyError):
            print(json.dumps({"code": 2, "errors": {"request": "bad"}}), flush=True)
            continue
        hang = float(os.environ.get("STUB_HANG_S", "0") or 0)
        time.sleep(hang if hang else _base_delay(address))
        if os.environ.get("STUB_FAIL") == "1":
            print(json.dumps({"code": 1, "errors": {"layout": "stub failure"}}), flush=True)
            continue
        lay = layout_of(address)
        out.mkdir(parents=True, exist_ok=True)
        (out / "derelict.json").write_text(json.dumps(lay), encoding="utf-8")
        print(json.dumps({"code": 0, "errors": {}, "frigate": lay["frigate"]}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
