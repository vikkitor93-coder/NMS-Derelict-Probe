"""Predict end rewards with persistent offline workers; resumable atlas CSV cache.

  python -I tools/end_reward_batch_705.py --workers 2 [--limit 100]

The scanner can retain RewardPool and call pool.predict_many(addresses, layouts)
with already generated derelict.json dictionaries.  No game process is used.
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
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_atlas_index import address as atlas_address, systems  # noqa: E402
from nms_paths_705 import out_path  # noqa: E402
import predict_end_reward_705 as predictor  # noqa: E402

PYTHON = Path(os.environ.get("EMU_PYTHON", os.path.expandvars("%USERPROFILE%/tools/NMS-Shipwright/.venv/Scripts/python.exe")))
WORKER = HERE / "end_reward_worker_705.py"
DEFAULT_CACHE = out_path("D:/Orca/NMS-Derelict-Probe-analysis/end-reward-cache/rewards.csv")
FIELDS = ("address", "reward_name", "reward_class", "reward_ambiguous", "reward_alt")
BELOW_NORMAL_PRIORITY_CLASS = 0x4000 if os.name == "nt" else 0
MAX_WORKERS = 16      # 2026-10-22: was 8; the scanner applies its own cap

# English display names from the 7.05 product/language tables.  The predictor's
# pick IDs remain the authority for selection; these labels are display only.
DISPLAY = {
    "SHIP_CORE_C": "C-Class Reactor", "SHIP_CORE_B": "B-Class Reactor",
    "SHIP_CORE_A": "A-Class Reactor", "SHIP_CORE_S": "S-Class Reactor",
    "FreighterTechHyp": "Salvaged Hyperdrive Upgrade",
    "FreighterTechSpeed": "Salvaged Fleet Beacon",
    "FreighterTechFuel": "Salvaged Fleet Fuel Unit",
    "FreighterTechTrade": "Salvaged Fleet Trade Unit",
    "FreighterTechCombat": "Salvaged Fleet Combat Unit",
    "FreighterTechMine": "Salvaged Fleet Mining Unit",
    "FreighterTechExp": "Salvaged Fleet Exploration Unit",
}


def normalize_address(address: str) -> str:
    address = str(address).upper()
    if len(address) != 16 or any(c not in "0123456789ABCDEF" for c in address):
        raise ValueError(f"expected a 16-digit universe address: {address!r}")
    return address


def display_pick(pick: str, tech_class: str) -> tuple[str, str]:
    name = DISPLAY[pick]
    cls = pick[-1] if pick.startswith("SHIP_CORE_") else tech_class
    if cls not in "CBAS":
        raise ValueError(f"invalid class {cls!r} for {pick}")
    return name, cls


def result_row(result: dict) -> tuple[str, str, str, str]:
    if "pick" not in result:
        raise ValueError(f"no end reward for {result.get('address')}: {result.get('status', 'unknown')}")
    tech_class = result["freighter_tech_if_picked"]["class"]
    name, cls = display_pick(result["pick"], tech_class)
    ambiguous = result.get("confidence", "").startswith("AMBIGUOUS")
    alternatives = []
    if ambiguous:
        for alt in result.get("alternatives", []):
            other_name, other_class = display_pick(alt["pick"], tech_class)
            other = f"{other_name} {other_class}"
            if (other_name, other_class) != (name, cls) and other not in alternatives:
                alternatives.append(other)
    return name, cls, "1" if ambiguous else "0", "|".join(alternatives)


class Worker:
    def __init__(self, number: int, log_dir: Path):
        log_dir.mkdir(parents=True, exist_ok=True)
        self.log = (log_dir / f"reward-worker-{os.getpid()}-{number}.log").open("a", encoding="utf-8")
        self.proc = subprocess.Popen([str(PYTHON), "-I", str(WORKER)], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=self.log, text=True, bufsize=1,
                                     creationflags=BELOW_NORMAL_PRIORITY_CLASS)
        line = self.proc.stdout.readline()
        if not line or json.loads(line).get("ready") is not True:
            self.close()
            raise RuntimeError(f"reward worker {number} did not become ready; see {self.log.name}")

    def request(self, address: str, layout: dict | None = None, extra: dict | None = None) -> dict:
        self.proc.stdin.write(json.dumps({"address": address, "layout": layout, **(extra or {})}, separators=(",", ":")) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            raise EOFError(f"reward worker died on {address}")
        reply = json.loads(line)
        if reply.get("address") != address:
            raise RuntimeError(f"reward worker reply address mismatch: {reply.get('address')} != {address}")
        if "error" in reply:
            raise RuntimeError(reply["error"])
        return reply

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.kill()
        self.proc.wait(timeout=30)
        self.log.close()


class RewardPool:
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

    def predict_many(self, addresses, layouts=None) -> dict[str, tuple[str, str, str, str]]:
        return {address: result_row(reply["result"]) for address, reply in self.raw_many(addresses, layouts).items()}

    def predict(self, addresses, layouts=None):
        return self.predict_many(addresses, layouts)

    def close(self) -> None:
        self.executor.shutdown(wait=True, cancel_futures=True)
        while not self.available.empty():
            self.available.get_nowait().close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def predict_many(addresses, workers: int = 2, layouts=None) -> dict[str, tuple[str, str, str, str]]:
    with RewardPool(workers) as pool:
        return pool.predict_many(addresses, layouts)


def cached_addresses(cache: Path) -> set[str]:
    if not cache.exists():
        return set()
    with cache.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != list(FIELDS):
            raise ValueError(f"unexpected cache columns in {cache}: {reader.fieldnames}")
        return {normalize_address(row["address"]) for row in reader if row["reward_name"]}


def backup_cache(cache: Path) -> Path:
    tag = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = cache.with_name(f"{cache.name}.pre-reward-resume-{tag}-{os.getpid()}")
    shutil.copy2(cache, backup)
    return backup


def publish_cache(cache: Path) -> None:
    subprocess.run([sys.executable, "-I", str(HERE / "publish_end_reward_cache_705.py"),
                    "--cache", str(cache)], check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("addresses", nargs="*", help="16-digit addresses; omitted = all published atlas systems")
    parser.add_argument("--atlas", type=Path, default=Path("D:/Orca/NMS-Derelict-Atlas"))
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--limit", type=int, help="new rows to compute in this run")
    parser.add_argument("--chunk", type=int, default=24)
    parser.add_argument("--upload-every", type=int, default=500,
                        help="import and publish after this many new rows (0 disables; final remainder still publishes)")
    args = parser.parse_args()
    if args.chunk < 1 or args.limit is not None and args.limit < 0 or args.upload_every < 0:
        parser.error("--chunk must be positive; --limit and --upload-every must be nonnegative")
    backup = None
    if args.cache.exists():
        raw = args.cache.read_bytes()
        if raw and not raw.endswith(b"\n"):
            backup = backup_cache(args.cache)
            end = raw.rfind(b"\n")
            if end < 0:
                raise ValueError(f"cache has no complete CSV line: {args.cache}")
            with args.cache.open("r+b") as stream:
                stream.truncate(end + 1)
    addresses = [normalize_address(a) for a in args.addresses] if args.addresses else [atlas_address(r) for r in systems(args.atlas)]
    addresses = list(dict.fromkeys(addresses))
    done = cached_addresses(args.cache)
    todo = [a for a in addresses if a not in done]
    if args.limit is not None:
        todo = todo[:args.limit]
    print(f"{len(addresses)} selected; {len(done)} cached; {len(todo)} pending this run", flush=True)
    # Reconcile any completed rows left by a previous stop or failed upload before doing new work.
    if args.upload_every:
        publish_cache(args.cache)
    if not todo:
        return
    args.cache.parent.mkdir(parents=True, exist_ok=True)
    fresh = not args.cache.exists()
    if not fresh and backup is None:
        backup = backup_cache(args.cache)
    if backup:
        print(f"backup: {backup}", flush=True)
    with args.cache.open("a", newline="", encoding="utf-8") as output, RewardPool(args.workers) as pool:
        writer = csv.writer(output, lineterminator="\n")
        if fresh:
            writer.writerow(FIELDS)
            output.flush()
            os.fsync(output.fileno())
        offset = since_upload = 0
        while offset < len(todo):
            size = min(args.chunk, len(todo) - offset)
            if args.upload_every:
                size = min(size, args.upload_every - since_upload)
            chunk = todo[offset:offset + size]
            replies = pool.raw_many(chunk)
            for address, reply in replies.items():
                name, cls, amb, alt = result_row(reply["result"])
                writer.writerow((address, name, cls, amb, alt))
            output.flush()
            os.fsync(output.fileno())
            offset += len(chunk)
            since_upload += len(replies)
            print(f"{offset}/{len(todo)} written to {args.cache}", flush=True)
            if args.upload_every and since_upload >= args.upload_every:
                publish_cache(args.cache)
                since_upload = 0
        if since_upload:
            publish_cache(args.cache)


if __name__ == "__main__":
    main()
