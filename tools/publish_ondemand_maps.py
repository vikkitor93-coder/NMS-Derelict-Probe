#!/usr/bin/env python3
"""Publish the maps that visitors asked the on-demand server for (2026-10-24), so they stay on the site when the PC is off.

    python -I tools/publish_ondemand_maps.py [--atlas D:/Orca/NMS-Derelict-Atlas] [--cache <ondemand cache sqlite>] [--dry]
    python -I tools/publish_ondemand_maps.py --push [--min-interval-min 30]     # build, commit, plain fast-forward push

Reads the on-demand server's result cache (ondemand/cache/ondemand-cache-v1.sqlite, read-only) and merges new maps into
views/ondemand/<REGION>.json.gz in the atlas clone: one gzip file per region (REGION = the last 8 hex digits of the address,
YYZZZXXX), each a compact format-4 bundle like views/top100 (compact v4):
    {"v":4, "t":<piece table of the maps in this file>, "s":{ADDRESS16: compact v4 view}, "m":{ADDRESS16: summary}}
Rules: deterministic (same cache -> identical bytes; sorted addresses, sorted piece names, gzip mtime 0), only ever adds or
replaces entries (nothing is deleted), and every map is re-checked before it is published: the view must decode, round-trip
and give the summary's room / crate / footlocker counts, and where the scanner DB knows the system its preset, rooms, crates
and footlockers must agree (read-only). Maps that are already in the top-100 bundles are skipped. Standard library only.

--push does the git work under atlas.repo_lock (the scanner's lock), never forces, and does nothing when it pushed less than
--min-interval-min minutes ago (state in ondemand/publish-state.json) or when no shard changed.
"""
from __future__ import annotations

import argparse
import gzip
import json
import sqlite3
import subprocess
import sys
import time
import zlib
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
PROBE = TOOLS.parent
sys.path.insert(0, str(TOOLS))
import derelict_view as V  # noqa: E402
import derelict_view_compact as C  # noqa: E402
import extra_containers_705 as EC  # noqa: E402

ATLAS = Path("D:/Orca/NMS-Derelict-Atlas")
CACHE = PROBE / "ondemand" / "cache" / "ondemand-cache-v1.sqlite"
SCANNER_DB = "D:/Orca/NMS-Derelict-Probe-analysis/emu/fastgen/app-data/derelicts.sqlite"
PIECE_INDEX = Path("D:/Orca/NMS-Derelict-Probe-analysis/meshcache/index.json")
STATE = PROBE / "ondemand" / "publish-state.json"
SHARD_DIR = "views/ondemand"
CACHE_VERSION = 1


def region_of(address: str) -> str:
    return address[8:16]


def dumps(o) -> bytes:
    return json.dumps(o, separators=(",", ":"), ensure_ascii=False, sort_keys=False).encode("utf-8")


def gz(raw: bytes) -> bytes:
    return gzip.compress(raw, 9, mtime=0)


def read_cache(path: Path) -> dict:
    """address -> {"n": scene names, "v": v4 view, "m": summary} for every cached map (read-only)."""
    out = {}
    db = sqlite3.connect(f"file:{Path(path).as_posix()}?mode=ro", uri=True, timeout=10)
    try:
        for address, blob in db.execute("SELECT address, data FROM maps WHERE v=? ORDER BY address", (CACHE_VERSION,)):
            out[address] = json.loads(zlib.decompress(blob))
    finally:
        db.close()
    return out


def top_addresses(atlas: Path) -> set:
    p = atlas / "views" / "top100.json.gz"
    try:
        return set(json.loads(gzip.decompress(p.read_bytes()))["s"])
    except (OSError, ValueError, KeyError):
        return set()


def scanner_row(db, address):
    if db is None:
        return None
    try:
        return db.execute("SELECT preset, rooms, crates, footlockers FROM systems WHERE address=?", (address,)).fetchone()
    except sqlite3.Error:
        return None


def counts_of(v3: dict):
    kinds = v3["c"][0]
    return len(v3["r"]), kinds.count(0), kinds.count(1)


def check_entry(address, names, v3, summary, row):
    """Re-check before publishing; returns an error string or ''."""
    if v3.get("a") != address or summary.get("address") != address:
        return "address mismatch"
    rooms, crates, lockers = counts_of(v3)
    if (rooms, crates, lockers) != (summary["rooms"], summary["crates"], summary["footlockers"]):
        return f"view counts {rooms}/{crates}/{lockers} != summary {summary['rooms']}/{summary['crates']}/{summary['footlockers']}"
    if row is not None and tuple(row) != (summary["preset"], rooms, crates, lockers):
        return f"scanner DB {tuple(row)} != {(summary['preset'], rooms, crates, lockers)}"
    return ""


class Builder:
    def __init__(self):
        self.index = json.loads(PIECE_INDEX.read_text(encoding="utf-8"))
        self.rotations = EC.authored_rotations()

    def table(self, names):
        return C.compact_table(V.pieces_table(self.index, list(names), self.rotations))

    def entry_v3(self, e):
        """cache entry (v4 view + its own table) -> (names, v3 view with ids into names)."""
        t4 = self.table(e["n"])
        return list(e["n"]), C.decode(e["v"], t4)

    def shard_systems(self, shard: dict):
        """published shard -> {address: (names, v3, summary)}"""
        t4 = shard["t"]
        names = list(t4["n"])
        return {a: (names, C.decode(v, t4), shard["m"][a]) for a, v in shard["s"].items()}

    def build_shard(self, systems: dict):
        """{address: (names, v3, summary)} -> (shard dict, bytes). Piece ids are remapped to this shard's own name list."""
        union = sorted({n for names, _v3, _m in systems.values() for n in names})
        ids = {n: k for k, n in enumerate(union)}
        t4 = self.table(union)
        views, sums = {}, {}
        for a in sorted(systems):
            names, v3, summary = systems[a]
            v3 = json.loads(json.dumps(v3))
            v3["i"][0] = [ids[names[k]] for k in v3["i"][0]]
            v4 = C.encode(v3, t4)
            back = C.decode(v4, t4)
            if C.dumps(back) != C.dumps(v3):
                raise RuntimeError(f"{a}: the view does not survive the shard round trip")
            views[a], sums[a] = v4, summary
        shard = {"v": 4, "t": t4, "s": views, "m": sums}
        return shard, gz(dumps(shard))


def build(atlas=ATLAS, cache=CACHE, dry=False, verbose=True):
    """-> {"changed": [relative paths], "added": n, "replaced": n, "skipped": {address: reason}, "shards": {path: bytes}}"""
    atlas, cache = Path(atlas), Path(cache)
    entries = read_cache(cache)
    top = top_addresses(atlas)
    try:
        sdb = sqlite3.connect(f"file:{Path(SCANNER_DB).as_posix()}?mode=ro", uri=True, timeout=10)
    except sqlite3.Error:
        sdb = None
    B = Builder()
    by_region, skipped = {}, {}
    for a, e in entries.items():
        if a in top:
            skipped[a] = "already in the top-100 bundle"
            continue
        if (e.get("m") or {}).get("source") != "generated":
            skipped[a] = "not generated by the on-demand server (stored layout)"
            continue
        try:
            names, v3 = B.entry_v3(e)
            err = check_entry(a, names, v3, e["m"], scanner_row(sdb, a))
        except Exception as ex:      # a broken entry never stops the others
            err = f"{type(ex).__name__}: {ex}"
        if err:
            skipped[a] = err
            continue
        by_region.setdefault(region_of(a), {})[a] = (names, v3, e["m"])
    changed, added, replaced, shards = [], 0, 0, {}
    for region, new in sorted(by_region.items()):
        rel = f"{SHARD_DIR}/{region}.json.gz"
        path = atlas / rel
        old_bytes = path.read_bytes() if path.is_file() else None
        merged = B.shard_systems(json.loads(gzip.decompress(old_bytes))) if old_bytes else {}
        for a, v in new.items():
            if a in merged:
                replaced += 1 if C.dumps(merged[a][1]) != C.dumps(v[1]) else 0
            else:
                added += 1
            merged[a] = v
        shard, data = B.build_shard(merged)
        shards[rel] = len(data)
        if data != old_bytes:
            changed.append(rel)
            if not dry:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
    if sdb is not None:
        sdb.close()
    if verbose:
        print(f"on-demand maps: {len(entries)} cached, {sum(len(v) for v in by_region.values())} publishable in {len(by_region)} region(s), "
              f"{added} added, {replaced} replaced, {len(skipped)} skipped, {len(changed)} shard file(s) {'would change' if dry else 'written'}")
        for a, why in skipped.items():
            print(f"  skipped {a}: {why}")
    return {"changed": changed, "added": added, "replaced": replaced, "skipped": skipped, "shards": shards}


def push(atlas=ATLAS, cache=CACHE, min_interval_min=30):
    sys.path.insert(0, "D:/Orca/NMS-Derelict-Probe-fastgen/app")
    import atlas as A
    state = {}
    try:
        state = json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    if time.time() - state.get("last_push", 0) < min_interval_min * 60:
        print(f"last push {int((time.time() - state['last_push']) / 60)} min ago (< {min_interval_min}): nothing done")
        return 0

    def git(*a, check=True):
        r = subprocess.run(["git", "-C", str(atlas), *a], capture_output=True, text=True)
        print("$ git", *a, "->", r.returncode, (r.stdout + r.stderr).strip()[-400:])
        if check and r.returncode:
            raise SystemExit("git failed")
        return r

    with A.repo_lock(Path(atlas)):
        git("fetch", "origin")
        st = git("status", "-sb").stdout.splitlines()[0]
        if "behind" in st:
            git("merge", "--ff-only", "origin/main")
        res = build(atlas, cache)
        if not res["changed"]:
            print("no shard changed: nothing to publish")
            return 0
        git("add", "--", SHARD_DIR)
        n = len(res["changed"])
        git("commit", "-m", f"On-demand maps: {res['added']} new, {res['replaced']} replaced in {n} region file(s)\n\n"
                            "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>")
        git("push", "origin", "HEAD")           # plain push: a non fast-forward is rejected, never forced
    state["last_push"] = time.time()
    STATE.write_text(json.dumps(state), encoding="utf-8")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--atlas", default=str(ATLAS))
    ap.add_argument("--cache", default=str(CACHE))
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--min-interval-min", type=int, default=30)
    a = ap.parse_args()
    if a.push:
        sys.exit(push(a.atlas, a.cache, a.min_interval_min))
    build(a.atlas, a.cache, dry=a.dry)
