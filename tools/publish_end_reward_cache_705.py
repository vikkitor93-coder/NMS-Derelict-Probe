"""Import the resumable end-reward cache into the local scanner DB and publish it.

Run with Python isolated mode. SQLite and existing atlas files are snapshotted before mutation.

REBUILT 2026-10-25 (recovery stage 2, task A2): only lines 1-25 of the original survived in the logs.  The body of
main() is a reconstruction from the callers (tools/end_reward_batch_705.py runs it as
``python -I publish_end_reward_cache_705.py --cache <rewards.csv>`` every --upload-every rows and once at start) and
from app/scanner.py, whose ``Scanner._backup_reward_publish`` / ``Scanner.sync_rewards_from_cache`` already implement
the snapshot / import / region-rewrite / publish steps.  This tool drives exactly those two methods, so the two
publishing paths cannot disagree, and holds the atlas repo lock (A.repo_lock) around the whole sequence.

Cache format (rewards.csv, written by end_reward_batch_705.py and Scanner._backfill_rewards):
  header  address,reward_name,reward_class,reward_ambiguous,reward_alt
  address 16 upper-case hex digits; reward_class one of C/B/A/S; reward_ambiguous 0/1;
  reward_alt '|'-joined "Name Class" alternatives (empty unless ambiguous); no commas or newlines in values.
A final line without a newline is a half-written row and is ignored.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import shutil
import sys
import time
from pathlib import Path

APP = Path("D:/Orca/NMS-Derelict-Probe-fastgen/app")
DEFAULT_CACHE = Path("D:/Orca/NMS-Derelict-Probe-analysis/end-reward-cache/rewards.csv")
BACKUPS = Path("D:/Orca/NMS-Derelict-Probe-backups/reward-publish")
FIELDS = ("address", "reward_name", "reward_class", "reward_ambiguous", "reward_alt")
HEX = frozenset("0123456789ABCDEF")


def load_cache(cache: Path) -> dict[str, tuple[str, str, str, str]]:
    """Validate the cache and return {address: (name, class, ambiguous, alt)}.

    Raises ValueError for a missing complete line, wrong columns, a bad address, an invalid reward value, or two
    different rows for one address.  Mirrors Scanner.sync_rewards_from_cache and store.checked_reward."""
    raw = Path(cache).read_bytes()
    end = raw.rfind(b"\n")
    if end < 0:
        raise ValueError(f"reward cache has no complete CSV line: {cache}")
    reader = csv.DictReader(io.StringIO(raw[:end + 1].decode("utf-8")))
    if tuple(reader.fieldnames or ()) != FIELDS:
        raise ValueError(f"unexpected reward cache columns: {reader.fieldnames}")
    rows: dict[str, tuple[str, str, str, str]] = {}
    for row in reader:
        address = row["address"]
        if len(address) != 16 or not set(address) <= HEX:
            raise ValueError(f"invalid reward cache address: {address!r}")
        if any(row[k] is None for k in FIELDS[1:]):
            raise ValueError(f"incomplete reward cache row for {address}")
        name, cls, amb, alt = (row[k] for k in FIELDS[1:])
        if not name or cls not in ("C", "B", "A", "S") or amb not in ("0", "1"):
            raise ValueError(f"invalid reward row for {address}: {(name, cls, amb, alt)!r}")
        if any("," in v or "\r" in v or "\n" in v for v in (name, cls, amb, alt)):
            raise ValueError(f"reward values may not contain commas or newlines ({address})")
        values = (name, cls, amb, alt)
        if rows.get(address, values) != values:
            raise ValueError(f"conflicting reward cache rows for {address}")
        rows[address] = values
    return rows


def snapshot_cache(cache: Path, backups: Path = BACKUPS) -> Path:
    """Copy the cache file itself next to the other pre-publish snapshots (the scanner backs up DB + atlas files)."""
    dest = Path(backups) / "cache-copies"
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{os.getpid()}-{Path(cache).name}"
    shutil.copy2(cache, target)
    return target


def publish(cache: Path, scanner, atlas_module, *, do_publish: bool = True) -> dict:
    """Snapshot, import and (optionally) publish through an app Scanner.  Returns the scanner's result dict."""
    cache = Path(cache)
    if not cache.exists():
        return {"cache_rows": 0, "imported": 0, "regions_pending": 0, "published": 0}
    rows = load_cache(cache)              # fail before touching anything
    with atlas_module.repo_lock(scanner.atlas.path):
        scanner._backup_reward_publish(cache)
        result = scanner._net("reward cache upload", scanner.sync_rewards_from_cache, cache, publish=do_publish)
    if result is None:
        raise RuntimeError("reward publish was interrupted")
    result = dict(result)
    result["validated_rows"] = len(rows)
    return result


def open_scanner(app: Path):
    """Import the scanner app from `app` and build a Scanner on the live DB (no worker or scan is started)."""
    sys.path.insert(0, str(app))
    import config as C
    import store as S
    import engine as E
    import atlas as A
    import scanner as SC
    cfg = C.load_cfg()
    store = S.Store(Path(cfg["db"]))
    mgr = E.Manager(cfg, store)
    return SC.Scanner(mgr, "reward-cache-publisher"), A, mgr


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--app", type=Path, default=APP, help="scanner app directory (default %(default)s)")
    parser.add_argument("--no-publish", action="store_true",
                        help="snapshot and import into the local DB only; do not rewrite/push atlas region files")
    args = parser.parse_args(argv)
    if not args.cache.exists():
        print(f"no reward cache at {args.cache}; nothing to publish", flush=True)
        return 0
    snapshot_cache(args.cache)
    scanner, atlas_module, mgr = open_scanner(args.app)
    try:
        result = publish(args.cache, scanner, atlas_module, do_publish=not args.no_publish)
    finally:
        for closer in (getattr(scanner, "close_reward_pool", None), getattr(scanner, "close_frigate_pool", None)):
            if closer:
                try:
                    closer()
                except Exception:
                    pass
        try:
            mgr.regions.close()
        except Exception:
            pass
    print(json.dumps(result, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
