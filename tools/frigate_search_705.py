#!/usr/bin/env python3
"""Search derelict freighters with many Salvaged Frigate Modules, rejecting hopeless systems early.

  python -I tools/frigate_search_705.py --list-profiles                      (what each mode keeps, recall, speed)
  python -I tools/frigate_search_705.py --region 05605CAA [--systems 001-22F] --min-modules 3 --workers 8
  python -I tools/frigate_search_705.py --region 05605CAA --profile no-filter      (baseline: full pipeline for all)
  python -I tools/frigate_search_705.py 0001056005605CAA ... | --addresses-file FILE

Stages (cheapest first; a system leaves at the first stage that rejects it):
  A  seed -> preset (derelict_seed_preset_705, microseconds, in this process). Rejected if the preset is not in
     the profile's preset set (or --presets).
  B  native layout writer in a persistent worker: placement records -> exact crate+footlocker count via
     research-output/FRIGATE_SEARCH_CONTAINER_TABLE_20261022.json. Rejected if < --min-containers.
  C  the live fast pipeline of the scanner's combined worker (tools/scan_worker_705.py): fast generator reusing the
     writer result, ONE fast-hook ABAND_FREIGHTER POI, crate loot -> frigate_modules (crate_loot_worker_705.summarize).
Writer-result cache: with --writer-cache (default: the shared scanner cache file, see native_writer_705.WriterCache)
a writer result computed before by the scanner, a backlog or an earlier search is restored exactly instead of
rerunning the game's writer; '--writer-cache off' always runs the writer.
Outputs (default under D:/Orca/Temp/claude/frigate-search-20261022/): hits CSV (frigate_modules >= --min-modules),
all-results CSV (every system that reached the worker) and a JSON run log with per-stage counters and timings.
Workers run at BelowNormal priority. Nothing is written to the atlas, the scanner DB or the fastgen tree.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import queue
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from derelict_seed_preset_705 import derelict_seed_preset  # noqa: E402

PYTHON = Path(os.environ.get("EMU_PYTHON", "%USERPROFILE%/tools/NMS-Shipwright/.venv/Scripts/python.exe"))
WORKER = HERE / "frigate_search_worker_705.py"
ATLAS = Path("D:/Orca/NMS-Derelict-Atlas")
OUT_DIR = Path("D:/Orca/Temp/claude/frigate-search-20261022")
WRITER_CACHE = Path("D:/Orca/NMS-Derelict-Probe-analysis/writer-cache/writer-cache-v1.sqlite")
PROFILE_INFO = HERE / "frigate_search_profiles_705.json"   # the numbers shown for each profile (edit after re-measuring)
BELOW_NORMAL = 0x4000 if os.name == "nt" else 0
P_MODULE = 5 / 198          # Salvaged Frigate Module odds per salvage crate / crew footlocker (R_ABAND_CRATE)
ALL_PRESETS = ("MEDI_TURRETS", "MEDI_FLOATERS", "MEDI_BUGS", "MEDI_SLIME", "MEDI_MAZE",
               "CARGO_TURRETS", "CARGO_FLOATERS", "CARGO_BUGS", "CARGO_SLIME", "CARGO_MAZE")
# Mean native-writer seconds per preset, region 05605CAA, 8 workers (research-output/FRIGATE_SEARCH_20261022.md);
# used only to submit the slowest jobs first.
WRITER_SECONDS = {"MEDI_TURRETS": 6.89, "CARGO_TURRETS": 3.08, "MEDI_FLOATERS": 2.32, "CARGO_FLOATERS": 0.89,
                  "MEDI_SLIME": 0.72, "CARGO_SLIME": 0.62, "CARGO_BUGS": 0.60, "MEDI_MAZE": 0.49, "MEDI_BUGS": 0.48,
                  "CARGO_MAZE": 0.44}
PROFILE_ORDER = ("no-filter", "all", "balanced", "fast")
_MAX_FILE = HERE.parent / "research-output" / "FRIGATE_SEARCH_CONTAINER_TABLE_20261022.json"


def load_profile_info() -> dict:
    try:
        return json.loads(PROFILE_INFO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"profiles": {}}


INFO = load_profile_info()
PROFILES = {}
for _name in PROFILE_ORDER:
    _p = (INFO.get("profiles") or {}).get(_name, {}).get("presets", "all")
    PROFILES[_name] = ALL_PRESETS if _p == "all" else tuple(_p)
if INFO.get("profiles", {}).get("balanced") is None:     # profile file missing: built-in preset sets
    PROFILES.update(balanced=("CARGO_FLOATERS", "CARGO_MAZE", "CARGO_BUGS", "CARGO_TURRETS"),
                    fast=("CARGO_FLOATERS", "CARGO_MAZE", "CARGO_BUGS"))


def binom_tail(n: int, k: int, p: float = P_MODULE) -> float:
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1)) if n >= k else 0.0


def auto_min_containers(min_modules: int, tail: float) -> int:
    """Smallest container count whose chance of >= min_modules modules is at least `tail`."""
    n = min_modules
    while binom_tail(n, min_modules) < tail:
        n += 1
    return n


def _pct(v):
    return "?" if v is None else f"{v:g}%"


def profile_text(selected: str | None = None, min_modules: int = 3) -> str:
    """The profile table (from frigate_search_profiles_705.json) for --help, --list-profiles and the start banner."""
    info, reg = INFO, INFO.get("region") or {}
    mm = str(min_modules if str(min_modules) in (info.get("thresholds") or {}) else 3)
    lines = [f"SEARCH PROFILES (--profile); figures for --min-modules {mm}"
             f" (stage-B threshold auto = {(info.get('thresholds') or {}).get(mm, '?')} crates+footlockers;"
             f" the thresholds are {', '.join(f'{v} for {k}' for k, v in (info.get('thresholds') or {}).items())} modules)",
             f"measured {info.get('updated', '?')}. 'atlas' = {info.get('atlas_systems', '?'):,} scanner-DB systems"
             f" (exact, computed from their preset + container counts); '{reg.get('name', 'region')}' = a real run on"
             f" {reg.get('systems', '?')} systems ({reg.get('truth_ge2', '?')} with >=2, {reg.get('truth_ge3', '?')}"
             f" with >=3, {reg.get('truth_ge4', '?')} with >=4 modules).", ""]
    ref = info.get("scanner_reference") or {}
    for name in PROFILE_ORDER:
        p = (info.get("profiles") or {}).get(name)
        if p is None:
            continue
        mark = "  <== selected" if name == selected else ""
        pres = p.get("presets")
        pres = "all 10" if pres == "all" else f"{len(pres)}: {', '.join(pres)}"
        a = (p.get("atlas") or {}).get(mm) or {}
        r = p.get("region_m3") or {}
        lines.append(f"{name:<10} {p.get('summary', '')}{mark}")
        lines.append(f"  presets kept    : {pres}")
        lines.append(f"  stage B         : {'containers >= threshold (exact count after the writer)' if p.get('stage_b') else 'off'}")
        ful = f"  fully computed  : atlas {_pct(a.get('full_pct'))}"
        if r:
            ful += (f" | {reg.get('name')}: {r.get('full')}/{reg.get('systems')} ({r.get('full_pct')}%);"
                    f" writer run for {r.get('writer_pct')}%")
        lines.append(ful)
        rec = f"  recall >=2/>=3/>=4: atlas {_pct(a.get('r2'))} / {_pct(a.get('r3'))} / {_pct(a.get('r4'))}"
        if r:
            rec += (f" | {reg.get('name')} (min-modules 3): {r.get('ge2')}/{reg.get('truth_ge2')}, "
                    f"{r.get('ge3')}/{reg.get('truth_ge3')}, {r.get('ge4')}/{reg.get('truth_ge4')}")
        lines.append(rec)
        sp = p.get("speed") or {}
        if sp:
            parts = []
            for w in ("3", "8"):
                s = sp.get(w)
                if s:
                    parts.append(f"{w} workers {s['sys_s']:.2f} systems/s = {s['vs_scanner']:.2f}x scanner"
                                 + (f" (cached writer {s['warm_sys_s']:.1f}/s = {s['warm_vs_scanner']:.1f}x)"
                                    if s.get("warm_sys_s") else ""))
            lines.append("  speed (region)  : " + "; ".join(parts))
        else:
            lines.append("  speed           : not measured yet")
        lines.append("")
    if ref:
        lines.append("Scanner reference (same workers, same systems, combined scan worker, cache off): "
                     + "; ".join(f"{w} workers {v:.2f} systems/s" for w, v in sorted(ref.items(), key=lambda x: int(x[0]))))
    lines.append("CAVEAT: " + info.get("caveat", "recall comes from limited samples."))
    return "\n".join(lines)


def region_systems(region: str, galaxy: int, spec: str | None) -> list[str]:
    region = region.upper()
    if not re.fullmatch(r"[0-9A-F]{8}", region):
        raise SystemExit("--region must be 8 hex digits (YY ZZZ XXX of the glyph code)")
    if spec is None:
        f = ATLAS / "regions" / f"g{galaxy:02x}" / region[:2] / region[2:5] / f"{region}.csv"
        m = None
        if f.exists():
            for line in f.read_text(encoding="utf-8").splitlines()[:4]:
                m = m or re.search(r"scanned ([0-9A-F]{3})-([0-9A-F]{3})", line)
        if not m:
            raise SystemExit("region not in the atlas: give --systems FIRST-LAST (hex, e.g. 001-21B)")
        lo, hi = int(m.group(1), 16), int(m.group(2), 16)
    else:
        lo, hi = (int(x, 16) for x in spec.split("-"))
    return [f"000{s:03X}{galaxy:02X}{region}" for s in range(lo, hi + 1)]


def glyphs(address: str) -> str:
    return "0" + address[3:6] + address[8:]


class Worker:
    def __init__(self, number: int, log_dir: Path):
        log_dir.mkdir(parents=True, exist_ok=True)
        self.log = (log_dir / f"frigate-worker-{os.getpid()}-{number}.log").open("a", encoding="utf-8")
        self.proc = subprocess.Popen([str(PYTHON), "-I", str(WORKER)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=self.log, text=True, bufsize=1, creationflags=BELOW_NORMAL)
        line = self.proc.stdout.readline()
        self.ready = json.loads(line) if line else {}
        if self.ready.get("ready") is not True:
            self.close()
            raise RuntimeError(f"worker {number} did not start; see {self.log.name}")

    def request(self, address: str, min_containers) -> dict:
        self.proc.stdin.write(json.dumps({"address": address, "min_containers": min_containers}) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            raise EOFError(f"worker died on {address}")
        reply = json.loads(line)
        if reply.get("address") != address:
            raise RuntimeError(f"reply mismatch {reply.get('address')} != {address}")
        return reply

    def close(self) -> None:
        if self.proc.poll() is None:
            try:   # closing stdin lets the worker flush its writer-cache hit/miss counts
                self.proc.stdin.close()
                self.proc.wait(timeout=10)
            except Exception:
                self.proc.kill()
        self.proc.wait(timeout=30)
        self.log.close()


class Pool:
    """Persistent workers; jobs are streamed (every job queued at once, each free worker takes the next one)."""

    def __init__(self, workers: int, log_dir: Path):
        self.log_dir, self.n, self.lock = log_dir, 0, threading.Lock()
        self.available: queue.Queue[Worker] = queue.Queue()
        self.executor = ThreadPoolExecutor(max_workers=workers)
        started = [f.result() for f in [self.executor.submit(self._new) for _ in range(workers)]]
        self.ready = started[0].ready if started else {}
        for w in started:
            self.available.put(w)

    def _new(self) -> Worker:
        with self.lock:
            self.n += 1
            n = self.n
        return Worker(n, self.log_dir)

    def _one(self, address, min_c):
        w = self.available.get()
        try:
            try:
                return w.request(address, min_c)
            except (EOFError, BrokenPipeError, OSError):
                w.close()
                w = self._new()
                return w.request(address, min_c)
        finally:
            self.available.put(w)

    def submit(self, address, min_c):
        return self.executor.submit(self._one, address, min_c)

    def close(self):
        self.executor.shutdown(wait=True, cancel_futures=True)
        while not self.available.empty():
            self.available.get_nowait().close()


HIT_FIELDS = ("address", "glyphs", "preset", "rooms", "crates", "footlockers", "containers", "frigate_modules",
              "frigate_modules_ambiguous", "frigate_module_rooms", "frigate_module_ids", "frigate_module_alt_ids")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, epilog=profile_text(None, 3),
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("addresses", nargs="*")
    ap.add_argument("--list-profiles", action="store_true", help="print the profile table (keeps, recall, speed) and exit")
    ap.add_argument("--addresses-file", type=Path)
    ap.add_argument("--region", help="8 hex digits YYZZZXXX (glyph digits 5-12)")
    ap.add_argument("--galaxy", type=lambda v: int(v, 0), default=0)
    ap.add_argument("--systems", help="FIRST-LAST system index range in hex (default: the atlas region's scanned range)")
    ap.add_argument("--min-modules", type=int, default=3)
    ap.add_argument("--min-containers", default="auto",
                    help="stage-B threshold on crates+footlockers; 'auto' = smallest count with P(>= min-modules) "
                         ">= --tail (7 for 2, 19 for 3, 34 for 4 modules); 0 disables stage B rejection")
    ap.add_argument("--tail", type=float, default=0.01, help="probability floor used by --min-containers auto")
    ap.add_argument("--profile", choices=PROFILE_ORDER, default="balanced",
                    help="no-filter = full pipeline for every system (finds everything); all = every preset, stage B "
                         "only; balanced (default) = 4 CARGO presets + stage B; fast = 3 CARGO presets (no TURRETS) "
                         "+ stage B. See the table below / --list-profiles")
    ap.add_argument("--presets", help="comma list kept at stage A (overrides --profile's preset set)")
    ap.add_argument("--no-filter", action="store_true", help="same as --profile no-filter")
    ap.add_argument("--writer-cache", default=str(WRITER_CACHE),
                    help=f"writer-result cache file shared with the scanner (default {WRITER_CACHE}); 'off' = always "
                         "run the game's writer (use for cold timing)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--tag", default=None, help="output file name tag")
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    a = ap.parse_args()
    if a.no_filter:
        a.profile = "no-filter"
    if a.list_profiles:
        print(profile_text(a.profile if "--profile" in sys.argv else None, a.min_modules))
        return

    if a.addresses_file:
        addrs = [l.strip().upper() for l in a.addresses_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    elif a.region:
        addrs = region_systems(a.region, a.galaxy, a.systems)
    else:
        addrs = [x.upper() for x in a.addresses]
    if not addrs:
        ap.error("give --region, addresses or --addresses-file (or --list-profiles)")
    addrs = list(dict.fromkeys(addrs))

    maxc = json.loads(_MAX_FILE.read_text(encoding="utf-8")).get("atlas_max_containers_per_preset", {})
    no_filter = a.profile == "no-filter"
    if no_filter:
        min_c, presets = None, set(ALL_PRESETS)
    else:
        min_c = auto_min_containers(a.min_modules, a.tail) if a.min_containers == "auto" else int(a.min_containers)
        if a.presets:
            presets = set(a.presets.upper().split(","))
        else:   # never keep a preset whose atlas maximum is below the container threshold
            presets = {p for p in PROFILES[a.profile] if maxc.get(p, 10 ** 6) >= min_c}
        if min_c <= 0:
            min_c = None
    cache_on = a.writer_cache.strip().lower() not in ("", "0", "off", "none", "false")
    if cache_on:
        os.environ["NMS_WRITER_CACHE"] = a.writer_cache
    else:
        os.environ["NMS_WRITER_CACHE"] = "off"
    tag = a.tag or f"{a.region or 'list'}-{'nofilter' if no_filter else f'm{a.min_modules}'}"
    a.out_dir.mkdir(parents=True, exist_ok=True)
    print(profile_text(a.profile, a.min_modules), flush=True)
    print("", flush=True)
    print(f"RUN: profile {a.profile}{' (custom --presets)' if a.presets else ''}; {len(addrs)} systems; "
          f"min_modules {a.min_modules}; stage A presets "
          f"{'all' if len(presets) == len(ALL_PRESETS) else sorted(presets)}; stage B min_containers {min_c}; "
          f"{a.workers} workers; writer cache {a.writer_cache if cache_on else 'off'}", flush=True)

    counters = {"systems": len(addrs), "rejected_A_preset": 0, "rejected_B_containers": 0, "full": 0, "errors": 0,
                "hits": 0, "writer_cache_hits": 0}
    stage_time = {"A": 0.0, "writer": 0.0, "cfilter": 0.0, "layout": 0.0, "poi": 0.0, "loot": 0.0}
    t_start = time.perf_counter()
    survivors = []
    for addr in addrs:
        t = time.perf_counter()
        _, preset, _ = derelict_seed_preset(addr)
        stage_time["A"] += time.perf_counter() - t
        if preset in presets:
            survivors.append(addr)
        else:
            counters["rejected_A_preset"] += 1
    # Longest jobs first (the writer is slowest for the TURRETS / MEDI_FLOATERS presets), so no worker is left
    # running a 10-30 s writer at the end while the others are idle.
    survivors.sort(key=lambda x: -WRITER_SECONDS.get(derelict_seed_preset(x)[1], 1.0))
    t_pool = time.perf_counter()
    pool = Pool(a.workers, a.out_dir / "worker-logs") if survivors else None
    startup = time.perf_counter() - t_pool
    if pool is not None:
        print(f"workers ready in {startup:.1f}s: fast POI {pool.ready.get('fast_poi')}, "
              f"writer cache {pool.ready.get('writer_cache')}", flush=True)
    t_work = time.perf_counter()
    results: list[dict | None] = [None] * len(survivors)
    try:
        futures = {pool.submit(addr, min_c): i for i, addr in enumerate(survivors)} if pool else {}
        for done, fut in enumerate(as_completed(futures), 1):
            i = futures[fut]
            r = fut.result()
            results[i] = r
            for k, v in r.get("timing", {}).items():
                stage_time[k] = stage_time.get(k, 0.0) + v
            if r.get("cache_hit"):
                counters["writer_cache_hits"] += 1
            if "error" in r:
                counters["errors"] += 1
                print(f"ERROR {survivors[i]}: {r['error']}", flush=True)
            elif r["stage"] == "rejected-containers":
                counters["rejected_B_containers"] += 1
            else:
                counters["full"] += 1
                if r["summary"]["frigate_modules"] >= a.min_modules:
                    counters["hits"] += 1
            if done % 50 == 0 or done == len(futures):
                wall = time.perf_counter() - t_work
                print(f"{done}/{len(futures)} worker jobs; {wall:.1f}s; {done / wall:.2f} jobs/s; {counters}", flush=True)
    finally:
        if pool is not None:
            pool.close()
    work_wall = time.perf_counter() - t_work
    total_wall = time.perf_counter() - t_start
    results = [r for r in results if r is not None]

    all_path = a.out_dir / f"frigate-search-{tag}-all.csv"
    hits_path = a.out_dir / f"frigate-search-{tag}-hits.csv"
    with all_path.open("w", newline="", encoding="utf-8") as fa, hits_path.open("w", newline="", encoding="utf-8") as fh:
        wa, wh = csv.writer(fa, lineterminator="\n"), csv.writer(fh, lineterminator="\n")
        wa.writerow(HIT_FIELDS + ("stage", "containers_est", "writer_s", "worker_s"))
        wh.writerow(HIT_FIELDS)
        for r in sorted(results, key=lambda r: -(r.get("summary") or {}).get("frigate_modules", -1)):
            if "error" in r:
                continue
            s = r.get("summary") or {}
            cont = r["crates"] + r["footlockers"] if "crates" in r else ""
            row = (r["address"], glyphs(r["address"]), r["preset"], r["rooms"], r.get("crates", ""),
                   r.get("footlockers", ""), cont, s.get("frigate_modules", ""), s.get("frigate_modules_ambiguous", ""),
                   s.get("frigate_module_rooms", ""), s.get("frigate_module_ids", ""), s.get("frigate_module_alt_ids", ""))
            tm = r.get("timing", {})
            wa.writerow(row + (r["stage"], r.get("containers_est", ""), tm.get("writer", ""),
                               round(sum(v for k, v in tm.items() if k != "derive"), 4)))
            if s and s["frigate_modules"] >= a.min_modules:
                wh.writerow(row)
    n = len(addrs)
    log = {"args": {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(a).items()},
           "profile": a.profile, "min_containers": min_c, "presets_kept": sorted(presets), "counters": counters,
           "kept_after_A_pct": round(100 * len(survivors) / n, 1),
           "fully_computed_pct": round(100 * counters["full"] / n, 1),
           "worker_startup_s": round(startup, 2), "work_wall_s": round(work_wall, 2), "total_wall_s": round(total_wall, 2),
           "systems_per_s_total": round(n / total_wall, 3),
           "systems_per_s_excl_startup": round(n / max(1e-9, total_wall - startup), 3),
           "stage_cpu_s": {k: round(v, 3) for k, v in stage_time.items()},
           "hits_csv": str(hits_path), "all_csv": str(all_path)}
    (a.out_dir / f"frigate-search-{tag}-log.json").write_text(json.dumps(log, indent=1), encoding="utf-8")
    print(json.dumps(log, indent=1), flush=True)
    print(f"\nRESULT ({a.profile}, min-modules {a.min_modules}): {n} systems -> stage A kept {len(survivors)} "
          f"({log['kept_after_A_pct']}%; {counters['rejected_A_preset']} rejected by preset) -> stage B rejected "
          f"{counters['rejected_B_containers']} -> fully computed {counters['full']} ({log['fully_computed_pct']}%); "
          f"errors {counters['errors']}; hits >= {a.min_modules}: {counters['hits']}; writer cache hits "
          f"{counters['writer_cache_hits']}/{len(survivors)}.\n"
          f"Wall {total_wall:.1f} s ({startup:.1f} s worker start) = {log['systems_per_s_total']:.2f} systems/s "
          f"({log['systems_per_s_excl_startup']:.2f} without start-up) with {a.workers} workers. Hits: {hits_path}",
          flush=True)


if __name__ == "__main__":
    main()
