#!/usr/bin/env python3
"""Per-system scan cache (speed fix 4, 2026-10-22): everything the loot / end-reward predictors read from a generated
derelict, plus the system's space-POI result, so a future backlog for a new derived field costs ~15 ms per system
instead of a full regeneration (~1.5-2 s). LOCAL ONLY: never published, never inside the atlas clone.

File: <analysis>/scan-cache/scan-cache-v1.sqlite (live: D:/Orca/NMS-Derelict-Probe-analysis/scan-cache/; staging via
NMS_STAGING_ROOT, see nms_paths_705.py). One table:
  systems(address TEXT PRIMARY KEY, v INTEGER, data BLOB)      data = zlib(level 6) of the compact JSON record below.

Record v1 (JSON object, short keys; every float is the exact double from derelict.json / the POI step, written with
Python's shortest round-trip repr, so decoding gives bit-identical values):
  "v": 1, "a": address (16 hex), "p": preset name, "eo": entrance_origin [x, y, z],
  "poi": {"poi_index": int | null, "poi_ids": [str], "aband_freighter": [x, y, z] float32 values | null},
  "r": [[room_index, template_name, raw_u16_0x00_0x1F (16 ints)], ...]           (layout "rooms", in order)
  "c": [[room_index, kind, scene_node_name, x, y, z], ...]                        (layout "containers", in order;
        the frigate_module_ids of the atlas index this list)
  "x": [[room_index, kind, scene_node_name, x, y, z], ...]                        (extra_containers(layout): briefcases
        and tall lockers, in the order the predictor sees them)
  "t": [[scene_resource, source_axes 3x3, translation 3], ...]                   (instances whose scene_resource
        contains ROOM_WALL_FINALTERMINAL: the end-reward terminal; normally exactly one)
  kind codes: 0 salvage_crate, 1 crew_footlocker, 2 briefcase, 3 tall_locker (extra_containers_705.KIND_CODES).

  python -I tools/scan_cache_705.py --stats [--db PATH]
  python -I tools/scan_cache_705.py --replay [--db PATH] [--limit N]    (prints reward + frigate rows, ms/system)
"""
from __future__ import annotations

import argparse
import contextlib
import json
import sqlite3
import sys
import threading
import time
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from nms_paths_705 import out_path  # noqa: E402

VERSION = 1
DEFAULT_DB = out_path("D:/Orca/NMS-Derelict-Probe-analysis/scan-cache/scan-cache-v1.sqlite")
KINDS = ("salvage_crate", "crew_footlocker", "briefcase", "tall_locker")
CODE = {k: i for i, k in enumerate(KINDS)}
TERMINAL = "ROOM_WALL_FINALTERMINAL"


def _cont(c: dict) -> list:
    x, y, z = c["layout_local_xyz"]
    return [c.get("room_index"), CODE[c["container_kind"]], c.get("scene_node_name"), x, y, z]


def record(address: str, layout: dict, poi: dict | None) -> dict:
    """The cache record for one generated layout (derelict.json dict) and its POI result."""
    from extra_containers_705 import extra_containers
    extras = extra_containers(layout)      # exactly what predict_crate_loot_705.predict appends
    poi = poi or {}
    return {"v": VERSION, "a": address.upper(), "p": layout.get("preset"), "eo": layout.get("entrance_origin"),
            "poi": {"poi_index": poi.get("poi_index"), "poi_ids": poi.get("poi_ids", []),
                    "aband_freighter": poi.get("aband_freighter")},
            "r": [[r["room_index"], r["template_name"], r["raw_u16_0x00_0x1F"]] for r in layout["rooms"]],
            "c": [_cont(c) for c in layout["containers"]],
            "x": [_cont(c) for c in extras],
            "t": [[i["scene_resource"], i["source_axes"], i["translation"]] for i in layout["instances"]
                  if TERMINAL in i["scene_resource"].upper()]}


def encode(rec: dict) -> str:
    return json.dumps(rec, separators=(",", ":"))


def compress(text: str) -> bytes:
    return zlib.compress(text.encode("utf-8"), 6)


def decode(blob: bytes | str) -> dict:
    if isinstance(blob, (bytes, bytearray)):
        blob = zlib.decompress(blob).decode("utf-8")
    rec = json.loads(blob)
    if rec.get("v") != VERSION:
        raise ValueError(f"unsupported scan-cache record version {rec.get('v')}")
    return rec


def _layout_container(c: list) -> dict:
    return {"room_index": c[0], "container_kind": KINDS[c[1]], "scene_node_name": c[2],
            "layout_local_xyz": [c[3], c[4], c[5]]}


def layout_view(rec: dict) -> tuple[dict, list[dict]]:
    """(minimal layout dict the predictors accept, extra containers) rebuilt from a record."""
    lay = {"address": rec["a"], "preset": rec["p"], "entrance_origin": rec["eo"],
           "rooms": [{"room_index": r[0], "template_name": r[1], "raw_u16_0x00_0x1F": r[2]} for r in rec["r"]],
           "containers": [_layout_container(c) for c in rec["c"]],
           "instances": [{"scene_resource": t[0], "source_axes": t[1], "translation": t[2]} for t in rec["t"]]}
    return lay, [_layout_container(c) for c in rec["x"]]


_PATCH = threading.Lock()


@contextlib.contextmanager
def _extras_from_record(crate, extras):
    """predict_crate_loot_705.predict appends extra_containers(layout) (computed from all instances, which the cache
    does not keep); during a replay it gets the cached list instead (same values, same order)."""
    with _PATCH:
        saved = crate.extra_containers
        crate.extra_containers = lambda _lay: [dict(c) for c in extras]
        try:
            yield
        finally:
            crate.extra_containers = saved


def replay(rec: dict, kinds=("salvage_crate", "crew_footlocker")):
    """(end-reward row (name, class, ambiguous, alt) or None, frigate summary dict, crate prediction) from a record,
    with the same predictor code the scan uses."""
    import crate_loot_worker_705 as W
    import predict_crate_loot_705 as crate
    import predict_end_reward_705 as end_reward
    from end_reward_batch_705 import result_row
    lay, extras = layout_view(rec)
    poi = rec["poi"]          # same dict shape as PoiGen.positions(); the predictors handle aband_freighter None
    reward_result = end_reward.predict(rec["a"], poi, lay)
    reward = result_row(reward_result) if "pick" in reward_result else None
    with _extras_from_record(crate, extras):
        prediction = crate.predict(rec["a"], poi, lay, None, kinds)
    return reward, W.summarize(rec["a"], lay, prediction), prediction


class ScanCache:
    """Thread-safe writer/reader for the cache file (one connection, WAL)."""

    def __init__(self, path: Path | str = DEFAULT_DB):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.db = sqlite3.connect(str(self.path), check_same_thread=False, timeout=30)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS systems(address TEXT PRIMARY KEY, v INTEGER NOT NULL, data BLOB NOT NULL)")
        self.db.commit()

    def put(self, address: str, rec: dict | str) -> None:
        text = rec if isinstance(rec, str) else encode(rec)
        with self.lock, self.db:
            self.db.execute("INSERT OR REPLACE INTO systems VALUES(?,?,?)", (address.upper(), VERSION, compress(text)))

    def put_many(self, items) -> int:
        rows = [(a.upper(), VERSION, compress(r if isinstance(r, str) else encode(r))) for a, r in items]
        with self.lock, self.db:
            self.db.executemany("INSERT OR REPLACE INTO systems VALUES(?,?,?)", rows)
        return len(rows)

    def get(self, address: str) -> dict | None:
        with self.lock:
            row = self.db.execute("SELECT data FROM systems WHERE address=?", (address.upper(),)).fetchone()
        return decode(row[0]) if row else None

    def addresses(self) -> set[str]:
        with self.lock:
            return {r[0] for r in self.db.execute("SELECT address FROM systems")}

    def iter(self, limit: int | None = None):
        q = "SELECT data FROM systems ORDER BY address" + (f" LIMIT {int(limit)}" if limit else "")
        with self.lock:
            blobs = [r[0] for r in self.db.execute(q)]
        for b in blobs:
            yield decode(b)

    def stats(self) -> dict:
        with self.lock:
            n, size = self.db.execute("SELECT COUNT(*), COALESCE(SUM(LENGTH(data)),0) FROM systems").fetchone()
        return {"systems": n, "blob_bytes": size, "bytes_per_system": round(size / n, 1) if n else 0,
                "file_bytes": self.path.stat().st_size if self.path.exists() else 0}

    def close(self) -> None:
        with self.lock:
            self.db.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--replay", action="store_true")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    cache = ScanCache(a.db)
    if a.stats:
        print(json.dumps(cache.stats()))
    if a.replay:
        n, t0 = 0, time.perf_counter()
        for rec in cache.iter(a.limit):
            reward, summary, _ = replay(rec)
            print(json.dumps({"address": rec["a"], "reward": reward, "frigate": summary}))
            n += 1
        dt = time.perf_counter() - t0
        print(f"# {n} systems replayed in {dt:.2f}s ({1000 * dt / max(1, n):.1f} ms/system)", file=sys.stderr)


if __name__ == "__main__":
    main()
