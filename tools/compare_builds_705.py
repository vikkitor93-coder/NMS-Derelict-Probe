"""Old-vs-new game build comparison: is the published atlas still valid after an NMS update?

    python -I tools/compare_builds_705.py --old 7.05 --new <build_id | build.json> [--n 1000] [--workers 2]
           [--atlas D:/Orca/NMS-Derelict-Atlas] [--seed 705] [--out DIR] [--no-golden]
    python -I tools/compare_builds_705.py --make-perturbed-profile DIR      test profile with one changed table

Samples --n published systems stratified across regions and presets (round-robin over (region, preset) groups, a
fixed random order inside each), runs every one through BOTH builds' full chains (tools/compare_builds_worker_705.py:
fresh layout, space POI, crate/footlocker/briefcase/tall-locker loot, end reward, Salvaged Frigate Modules), and diffs
  layout: seed_preset, rooms, pieces, crates, footlockers, briefcases, tall_lockers
  loot:   crate_loot (crates + footlockers), case_lock_loot (briefcases + tall lockers), frigate_modules, end_reward, poi
Decision: "atlas valid for new build" (every sampled system identical, no errors), "rescan needed: <scope>" or
"inconclusive". The new side also runs the golden in-game cases (tools/golden_ingame_705.json).
--old 7.05 = shipped generator with the space-POI step pinned to the 7.05 exe + 7.05 game-data snapshot (so an
installed update cannot leak into the old side); --old stock = exactly what the scanner runs. --new 7.05 applies the
whole 7.05 profile (exercises the patch path a new build uses), so old=new=7.05 must give 100 % identical.
Output: <out>/compare_<old>_vs_<new>_<n>.json + .md (default research-output/compare-builds/). Workers run BelowNormal.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import os
import queue
import random
import shutil
import struct
import subprocess
import sys
import threading
import time
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import build_profile_705 as BP  # noqa: E402
import golden_ingame_705 as GI  # noqa: E402

ROOT = HERE.parent
ATLAS = Path("D:/Orca/NMS-Derelict-Atlas")
EMU_PY = os.environ.get("EMU_PYTHON", os.path.expandvars("%USERPROFILE%/tools/NMS-Shipwright/.venv/Scripts/python.exe"))
WORKER = HERE / "compare_builds_worker_705.py"
BELOW_NORMAL = 0x4000 if os.name == "nt" else 0
LAYOUT_FIELDS = ("seed_preset", "rooms", "pieces", "crates", "footlockers", "briefcases", "tall_lockers")
LOOT_FIELDS = ("crate_loot", "case_lock_loot", "frigate_modules", "end_reward", "poi")


def fields_of(r: dict) -> dict:
    loot = r.get("loot") or []
    return {"seed_preset": [r.get("seed"), r.get("preset")], "rooms": [r.get("rooms"), r.get("room_raw_sha")],
            "pieces": r.get("pieces"), "crates": r.get("crates"), "footlockers": r.get("footlockers"),
            "briefcases": r.get("briefcases"), "tall_lockers": r.get("tall_lockers"),
            "crate_loot": [x for x in loot if x[0] in ("salvage_crate", "crew_footlocker")],
            "case_lock_loot": [x for x in loot if x[0] in ("briefcase", "tall_locker")],
            "frigate_modules": r.get("frigate"), "end_reward": r.get("end_reward"), "poi": r.get("poi")}


def load_index(atlas: Path) -> list[dict]:
    raw = gzip.decompress((atlas / "index" / "systems.csv.gz").read_bytes()).decode("utf-8")
    rows = list(csv.DictReader(io.StringIO("\n".join(l for l in raw.splitlines() if l and not l.startswith("#")))))
    for r in rows:
        g = r["glyphs"].upper()
        r["address"] = f"000{g[1:4]}{int(r['galaxy']):02X}{g[4:]}"
        r["region"] = g[4:]
    return rows


def stratified(rows: list[dict], n: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    groups = defaultdict(list)
    for r in rows:
        groups[(r["region"], r["preset"])].append(r)
    keys = sorted(groups)
    rng.shuffle(keys)
    for k in keys:
        rng.shuffle(groups[k])
    out, i = [], 0
    while len(out) < min(n, len(rows)):
        progressed = False
        for k in keys:
            if i < len(groups[k]):
                out.append(groups[k][i])
                progressed = True
                if len(out) >= n:
                    break
        if not progressed:
            break
        i += 1
    return out


class Pool:
    """N persistent workers for one build side; run(addresses) -> {address: record}."""

    def __init__(self, side: str, profile: str, pin_only: bool, n: int, log_dir: Path):
        self.side, self.procs, self.logs = side, [], []
        log_dir.mkdir(parents=True, exist_ok=True)
        args = [EMU_PY, "-I", str(WORKER), "--profile", profile] + (["--pin-only"] if pin_only else [])
        for k in range(n):
            lf = open(log_dir / f"{side}-worker-{k}.log", "w", encoding="utf-8")
            p = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=lf, text=True, bufsize=1,
                                 creationflags=BELOW_NORMAL)
            ready = json.loads(p.stdout.readline() or "{}")
            if not ready.get("ready"):
                raise RuntimeError(f"{side} worker {k} did not start; see {lf.name}")
            self.ready = ready
            self.procs.append(p)
            self.logs.append(lf)

    def run(self, addresses, progress=None) -> dict:
        q, out, lock = queue.Queue(), {}, threading.Lock()
        for a in addresses:
            q.put(a)

        def loop(p):
            while True:
                try:
                    a = q.get_nowait()
                except queue.Empty:
                    return
                p.stdin.write(json.dumps({"address": a}) + "\n")
                p.stdin.flush()
                line = p.stdout.readline()
                rec = json.loads(line) if line else {"address": a, "error": "worker died"}
                with lock:
                    out[a] = rec
                    if progress:
                        progress(self.side, len(out))
        ts = [threading.Thread(target=loop, args=(p,), daemon=True) for p in self.procs]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        return out

    def close(self):
        for p in self.procs:
            try:
                p.stdin.close()
                p.wait(timeout=60)
            except Exception:
                p.kill()
        for lf in self.logs:
            lf.close()


def side_args(spec: str, side: str) -> tuple[str, bool]:
    if spec == "stock":
        return "stock", False
    if spec == BP.BASE_ID and side == "old":
        return BP.BASE_ID, True
    return spec, False


def atlas_check(rec: dict, row: dict) -> list[str]:
    """Old-side record vs the published atlas row (sanity: the old side must reproduce the atlas)."""
    bad = []
    pairs = [("preset", rec.get("preset"), row["preset"]), ("rooms", len(rec.get("rooms") or []), int(row["rooms"])),
             ("crates", len(rec.get("crates") or []), int(row["crates"])),
             ("footlockers", len(rec.get("footlockers") or []), int(row["footlockers"]))]
    for k, have in (("briefcases", len(rec.get("briefcases") or [])), ("tall_lockers", len(rec.get("tall_lockers") or []))):
        if row.get(k):
            pairs.append((k, have, int(row[k])))
    er = rec.get("end_reward") or ["", ""]
    if row.get("reward_name"):
        pairs.append(("end_reward", f"{er[0]} {er[1]}", f"{row['reward_name']} {row['reward_class']}"))
    fr = rec.get("frigate") or {}
    if row.get("frigate_modules") not in (None, "") and isinstance(fr, dict) and "frigate_modules" in fr:
        pairs.append(("frigate_modules", fr["frigate_modules"], int(row["frigate_modules"])))
    for k, a, b in pairs:
        if a != b:
            bad.append(f"{k}: generated {a!r} vs atlas {b!r}")
    return bad


def compare(old: dict, new: dict, sample: list[dict]) -> dict:
    by_field, examples, errors, differing, identical = Counter(), defaultdict(list), [], [], 0
    atlas_bad, presets_diff = [], Counter()
    for row in sample:
        a = row["address"]
        o, n = old.get(a, {"error": "missing"}), new.get(a, {"error": "missing"})
        if "error" in o or "error" in n:
            errors.append([a, o.get("error"), n.get("error")])
            continue
        fo, fn = fields_of(o), fields_of(n)
        diff = [k for k in fo if json.dumps(fo[k], sort_keys=True) != json.dumps(fn[k], sort_keys=True)]
        if diff:
            differing.append([a, row["preset"], diff])
            presets_diff[row["preset"]] += 1
            for k in diff:
                by_field[k] += 1
                if len(examples[k]) < 3:
                    examples[k].append({"address": a, "old": fo[k] if len(json.dumps(fo[k])) < 600 else "(long)",
                                        "new": fn[k] if len(json.dumps(fn[k])) < 600 else "(long)"})
        else:
            identical += 1
        bad = atlas_check(o, row)
        if bad:
            atlas_bad.append([a, bad])
    return {"identical": identical, "differing": len(differing), "errors": errors, "by_field": dict(by_field),
            "differing_by_preset": dict(presets_diff), "differing_systems": differing[:200],
            "examples": dict(examples), "old_vs_atlas_mismatches": len(atlas_bad), "old_vs_atlas_examples": atlas_bad[:10]}


def decide(c: dict, n: int, atlas_rows: int) -> str:
    if c["errors"] and not c["differing"]:
        return f"inconclusive: {len(c['errors'])} system(s) failed to run (see errors); nothing differed otherwise"
    if not c["differing"] and not c["errors"]:
        return "atlas valid for new build"
    lay = [k for k in LAYOUT_FIELDS if c["by_field"].get(k)]
    loot = [k for k in LOOT_FIELDS if c["by_field"].get(k)]
    share = c["differing"] / max(1, n)
    est = f"{c['differing']}/{n} sampled systems differ (about {share:.1%}, ~{round(share * atlas_rows):,} of {atlas_rows:,} atlas rows)"
    if lay:
        presets = ", ".join(sorted(c["differing_by_preset"]))
        return f"rescan needed: layouts ({', '.join(lay)}) and everything derived from them; {est}; presets affected: {presets}"
    return f"rescan needed: loot/rewards only ({', '.join(loot)}), layouts unchanged; re-run the end-reward / frigate-module backfills; {est}"


def make_perturbed(dest: Path) -> Path:
    """A test profile = 7.05 with (a) the writer's preset table changed (CARGO_BUGS StraightMultiplier 1.25 -> 1.5)
    and (b) the crate table's AMMO weight 65 -> 60 (predictor override). Both must show up as differences."""
    dest.mkdir(parents=True, exist_ok=True)
    prof = BP.builtin_705()
    src = Path(prof["preset_mbin"])
    data = bytearray(src.read_bytes())
    base = 0x30 + 7 * 0x90                      # preset index 7 = CARGO_BUGS (native_writer_705.build_inputs layout)
    name = bytes(data[base + 0x80:base + 0x90]).split(b"\0")[0]
    assert name == b"CARGO_BUGS", name
    k = data.find(struct.pack("<f", 1.25), base, base + 0x80)
    assert k > 0, "StraightMultiplier 1.25 not found in the CARGO_BUGS preset"
    struct.pack_into("<f", data, k, 1.5)
    (dest / "freighterdungeonstable.mbin").write_bytes(bytes(data))
    import predict_crate_loot_705 as C
    crate = [list(e) for e in C.TABLES["R_ABAND_CRATE"]]
    for e in crate:
        if e[1] == "AMMO":
            e[2] = 60
    prof.update(build_id="perturbed-test", label="7.05 with a perturbed preset table + crate table (TEST ONLY)",
                preset_mbin=str(dest / "freighterdungeonstable.mbin"), catalog_cache=str(dest / "cache"),
                fingerprints=BP.load_profile(BP.BASE_ID).get("fingerprints", {}),
                overrides={"LOOT_TABLES": {"R_ABAND_CRATE": crate}},
                perturbation={"preset_mbin": f"CARGO_BUGS StraightMultiplier 1.25 -> 1.5 at file offset {k:#x}",
                              "R_ABAND_CRATE": "AMMO weight 65 -> 60"})
    (dest / "build.json").write_text(json.dumps(prof, indent=1), encoding="utf-8")
    return dest / "build.json"


def write_md(rep: dict, path: Path):
    c = rep["comparison"]
    lines = [f"# Build comparison {rep['old']} vs {rep['new']} ({rep['systems']} systems)", "",
             f"- Decision: **{rep['decision']}**",
             f"- Identical: {c['identical']}/{rep['systems']}; differing: {c['differing']}; errors: {len(c['errors'])}",
             f"- Fields that differ (systems): {json.dumps(c['by_field']) if c['by_field'] else 'none'}",
             f"- Differing by preset: {json.dumps(c['differing_by_preset']) if c['differing_by_preset'] else 'none'}",
             f"- Old side vs published atlas rows: {c['old_vs_atlas_mismatches']} mismatching systems",
             f"- Sample: {rep['sample']['regions']} regions, presets {json.dumps(rep['sample']['presets'])}",
             f"- Old exe {rep['old_exe'][:8]}, new exe {rep['new_exe'][:8]}; {rep['workers']} workers per side; {rep['seconds']} s"]
    if rep.get("golden_new"):
        g = rep["golden_new"]
        lines.append(f"- Golden in-game cases on the new build: {g['passed']}/{g['total']} passed")
    lines += ["", "JSON with examples: " + rep["json"], ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--old", default=BP.BASE_ID)
    ap.add_argument("--new")
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--atlas", type=Path, default=ATLAS)
    ap.add_argument("--seed", type=int, default=705)
    ap.add_argument("--out", type=Path, default=ROOT / "research-output" / "compare-builds")
    ap.add_argument("--no-golden", action="store_true")
    ap.add_argument("--make-perturbed-profile", type=Path)
    a = ap.parse_args(argv)
    if a.make_perturbed_profile:
        print("wrote", make_perturbed(a.make_perturbed_profile))
        return 0
    if not a.new:
        ap.error("--new is required")
    t0 = time.time()
    rows = load_index(a.atlas)
    sample = stratified(rows, a.n, a.seed)
    golden = [] if a.no_golden else GI.full_addresses()
    addrs = list(dict.fromkeys([r["address"] for r in sample] + golden))
    a.out.mkdir(parents=True, exist_ok=True)
    tag = f"{Path(a.old).stem if a.old.endswith('.json') else a.old}_vs_{Path(a.new).parent.name if a.new.endswith('.json') else a.new}_{len(sample)}"
    logs = a.out / f"logs-{tag}"
    print(f"{len(sample)} systems ({len({r['region'] for r in sample})} regions, {len({r['preset'] for r in sample})} presets) "
          f"+ {len(golden)} golden; {a.workers} workers per side", flush=True)
    last = [0.0]

    def progress(side, k):
        if time.time() - last[0] > 30:
            last[0] = time.time()
            print(f"  {side}: {k}/{len(addrs)}  ({time.time() - t0:.0f} s)", flush=True)
    pools = {}
    res = {}
    try:
        for side, spec in (("old", a.old), ("new", a.new)):
            prof, pin = side_args(spec, side)
            pools[side] = Pool(side, prof, pin, a.workers, logs)
        th = {s: threading.Thread(target=lambda s=s: res.__setitem__(s, pools[s].run(addrs, progress))) for s in pools}
        for t in th.values():
            t.start()
        for t in th.values():
            t.join()
    finally:
        for p in pools.values():
            p.close()
    c = compare(res["old"], res["new"], sample)
    old_exe = BP.load_profile(a.old if a.old != "stock" else BP.BASE_ID)["exe_sha256"]
    new_exe = BP.load_profile(a.new if a.new != "stock" else BP.BASE_ID)["exe_sha256"]
    rep = {"old": a.old, "new": a.new, "old_exe": old_exe, "new_exe_sha256": new_exe, "new_exe": new_exe,
           "systems": len(sample), "workers": a.workers, "seed": a.seed,
           "sample": {"regions": len({r["region"] for r in sample}), "presets": dict(Counter(r["preset"] for r in sample))},
           "comparison": c, "decision": decide(c, len(sample), len(rows)), "seconds": round(time.time() - t0, 1),
           "worker_ready": {s: p.ready for s, p in pools.items()},
           "mean_seconds_per_system": {s: round(sum((r.get("seconds") or {}).get("total", 0) for r in res[s].values()) / max(1, len(res[s])), 3) for s in res}}
    if golden:
        rep["golden_new"] = {k: v for k, v in GI.evaluate({k: res["new"][k] for k in golden}).items()}
        rep["golden_old"] = {k: v for k, v in GI.evaluate({k: res["old"][k] for k in golden}).items() if k != "checks"}
    jp = a.out / f"compare_{tag}.json"
    rep["json"] = str(jp)
    jp.write_text(json.dumps(rep, indent=1), encoding="utf-8")
    write_md(rep, jp.with_suffix(".md"))
    print(jp.with_suffix(".md").read_text(encoding="utf-8"))
    return 0 if rep["decision"] == "atlas valid for new build" else 3


if __name__ == "__main__":
    sys.exit(main())
