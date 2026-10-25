#!/usr/bin/env python3
"""Persistent, resumable Salvaged Frigate Module prediction for published atlas systems.

  python -I tools/crate_loot_batch_705.py --workers 6 [--limit 200]

The cache is local and never publishes from this CLI; the scanner imports it through its normal atlas publisher.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_atlas_index import address as atlas_address, systems  # noqa: E402
from nms_paths_705 import out_path  # noqa: E402

PYTHON = Path(os.environ.get("EMU_PYTHON", os.path.expandvars("%USERPROFILE%/tools/NMS-Shipwright/.venv/Scripts/python.exe")))
WORKER = HERE / "crate_loot_worker_705.py"
DEFAULT_CACHE = out_path("D:/Orca/NMS-Derelict-Probe-analysis/crate-loot-cache/predictions-v2.csv")
FIELDS = ("address", "frigate_modules", "frigate_modules_ambiguous", "frigate_module_rooms",
          "frigate_module_ids", "frigate_module_alt_ids")
BELOW_NORMAL_PRIORITY_CLASS = 0x4000 if os.name == "nt" else 0
MAX_WORKERS = 16      # 2026-10-22: was 10; the scanner applies its own cap


def normalize_address(address: str) -> str:
    address = str(address).upper()
    if len(address) != 16 or any(c not in "0123456789ABCDEF" for c in address):
        raise ValueError(f"expected a 16-digit universe address: {address!r}")
    return address


def normalize_summary(address: str, summary: dict) -> tuple:
    count = int(summary["frigate_modules"])
    ambiguous = int(summary["frigate_modules_ambiguous"])
    if count < 0 or ambiguous < 0:
        raise ValueError(f"negative frigate module result for {address}")
    return (address, count, ambiguous, str(summary.get("frigate_module_rooms", "")),
            str(summary.get("frigate_module_ids", "")), str(summary.get("frigate_module_alt_ids", "")))


class Worker:
    def __init__(self, number: int, log_dir: Path):
        log_dir.mkdir(parents=True, exist_ok=True)
        self.log = (log_dir / f"crate-worker-{os.getpid()}-{number}.log").open("a", encoding="utf-8")
        self.proc = subprocess.Popen([str(PYTHON), "-I", str(WORKER)], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=self.log, text=True, bufsize=1,
                                     creationflags=BELOW_NORMAL_PRIORITY_CLASS)
        line = self.proc.stdout.readline()
        if not line or json.loads(line).get("ready") is not True:
            self.close()
            raise RuntimeError(f"crate worker {number} did not become ready; see {self.log.name}")

    def request(self, address: str, layout: dict | None = None, extra: dict | None = None) -> dict:
        self.proc.stdin.write(json.dumps({"address": address, "layout": layout, **(extra or {})}, separators=(",", ":")) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            raise EOFError(f"crate worker died on {address}")
        reply = json.loads(line)
        if reply.get("address") != address:
            raise RuntimeError(f"crate worker reply address mismatch: {reply.get('address')} != {address}")
        if "error" in reply:
            raise RuntimeError(reply["error"])
        return reply

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.kill()
        self.proc.wait(timeout=30)
        self.log.close()


class CrateLootPool:
    def __init__(self, workers: int = 2, log_dir: Path | None = None):
        if not 1 <= workers <= MAX_WORKERS:
            raise ValueError(f"workers must be 1..{MAX_WORKERS}")
        self.count = workers
        self.log_dir = log_dir or DEFAULT_CACHE.parent / "worker-logs"
        self.available: queue.Queue[Worker] = queue.Queue()
        self.lock = threading.Lock()
        self.next_number = 0
        self.executor = ThreadPoolExecutor(max_workers=workers)
        try:
            futures = [self.executor.submit(self._new_worker) for _ in range(workers)]
            for future in futures:
                self.available.put(future.result())
        except Exception:
            self.close()
            raise

    def _new_worker(self) -> Worker:
        with self.lock:
            self.next_number += 1
            number = self.next_number
        return Worker(number, self.log_dir)

    def _one(self, address: str, layout: dict | None, extra: dict | None = None) -> dict:
        worker = self.available.get()
        try:
            try:
                return worker.request(address, layout, extra)
            except (EOFError, BrokenPipeError, OSError):
                worker.close()
                worker = self._new_worker()
                return worker.request(address, layout, extra)
        finally:
            self.available.put(worker)

    def submit(self, address: str, layout: dict | None = None, **extra):
        """Queue one request; returns a Future of the worker reply (streaming backlogs keep many in flight)."""
        return self.executor.submit(self._one, normalize_address(address), layout, extra or None)

    def raw_many(self, addresses, layouts=None) -> dict[str, dict]:
        ordered = list(dict.fromkeys(normalize_address(a) for a in addresses))
        layouts = layouts or {}
        futures = {a: self.executor.submit(self._one, a, layouts.get(a)) for a in ordered}
        return {a: futures[a].result() for a in ordered}

    def predict_many(self, addresses, layouts=None) -> dict[str, tuple]:
        return {a: normalize_summary(a, r["summary"]) for a, r in self.raw_many(addresses, layouts).items()}

    def close(self) -> None:
        self.executor.shutdown(wait=True, cancel_futures=True)
        while not self.available.empty():
            self.available.get_nowait().close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def predict_many(addresses, workers: int = 2, layouts=None) -> dict[str, tuple]:
    with CrateLootPool(workers) as pool:
        return pool.predict_many(addresses, layouts)


def cached_addresses(cache: Path) -> set[str]:
    if not cache.exists():
        return set()
    with cache.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != FIELDS:
            raise ValueError(f"unexpected crate cache columns in {cache}: {reader.fieldnames}")
        out = set()
        for row in reader:
            address = normalize_address(row["address"])
            if any(row.get(k) is None for k in FIELDS[1:]):
                raise ValueError(f"incomplete cache row for {address}")
            int(row["frigate_modules"])
            int(row["frigate_modules_ambiguous"])
            out.add(address)
        return out


def backup_cache(cache: Path) -> Path:
    tag = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = cache.with_name(f"{cache.name}.pre-resume-{tag}-{os.getpid()}")
    shutil.copy2(cache, backup)
    return backup


def load_addresses(args) -> list[str]:
    if args.addresses_file:
        addresses = [line.strip() for line in args.addresses_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    elif args.addresses:
        addresses = args.addresses
    else:
        addresses = [atlas_address(row) for row in systems(args.atlas)]
    return list(dict.fromkeys(normalize_address(a) for a in addresses))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("addresses", nargs="*")
    ap.add_argument("--addresses-file", type=Path)
    ap.add_argument("--atlas", type=Path, default=Path("D:/Orca/NMS-Derelict-Atlas"))
    ap.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--chunk", type=int, default=24)
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()
    if args.chunk < 1 or (args.limit is not None and args.limit < 0):
        ap.error("--chunk must be positive and --limit nonnegative")
    addresses = load_addresses(args)
    done = cached_addresses(args.cache)
    todo = [a for a in addresses if a not in done]
    if args.limit is not None:
        todo = todo[:args.limit]
    print(f"{len(addresses)} selected; {len(done)} cached; {len(todo)} pending this run", flush=True)
    args.cache.parent.mkdir(parents=True, exist_ok=True)
    fresh = not args.cache.exists()
    backup = backup_cache(args.cache) if not fresh else None
    if backup:
        print(f"backup: {backup}", flush=True)
    offset = 0
    started = time.monotonic()
    with args.cache.open("a", newline="", encoding="utf-8") as output, CrateLootPool(args.workers) as pool:
        writer = csv.writer(output, lineterminator="\n")
        if fresh:
            writer.writerow(FIELDS)
            output.flush()
            os.fsync(output.fileno())
        while offset < len(todo):
            chunk = todo[offset:offset + args.chunk]
            replies = pool.raw_many(chunk)
            if set(replies) != set(chunk):
                raise RuntimeError("crate workers returned an incomplete chunk; cache remains resumable")
            for address, reply in replies.items():
                writer.writerow(normalize_summary(address, reply["summary"]))
            output.flush()
            os.fsync(output.fileno())
            offset += len(chunk)
            elapsed = sum(replies[a]["total_seconds"] for a in replies)
            wall = max(0.001, time.monotonic() - started)
            rate = offset / wall
            eta = max(0, int((len(todo) - offset) / max(rate, 0.001)))
            print(f"{offset}/{len(todo)} written; worker time {elapsed:.2f}s; wall {wall:.1f}s "
                  f"({rate:.2f}/s, {wall / offset:.2f}s/system); ETA {eta // 3600:02d}:{eta % 3600 // 60:02d}; "
                  f"cache={args.cache}", flush=True)


if __name__ == "__main__":
    main()
