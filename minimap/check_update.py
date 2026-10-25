"""After an NMS update: does the minimap (and the generator behind it) still match the game?

    python -I minimap/check_update.py [--quick] [--save-baseline]

Checks, each PASS / FAIL / SKIP, about 30 s in all (read-only; nothing in the game or the atlas is touched):
  1. the installed NMS.exe (running process, settings, or a Steam library) and its SHA-256
  2. the live reader knows that build (tools/live_position_705.py KNOWN_BUILDS)
  3. the game file the generator reads (a pinned analysis copy) is the SAME build as the installed game
  4. the game's PAK files (names + sizes) match the baseline saved when the generator was last verified
  5. golden layouts: the generator still reproduces two user-verified derelicts (rooms, crates, footlockers, seed, preset)
  6. golden end reward: the user's in-game ground truth still comes out (0002250006607CAA = Fuel Unit, B-class)
  7. the live reader returns a sane address and position (only while NMS runs with a save loaded)
  8. the game tables the generator reads (raw-byte fingerprints of rewardtable, freighterdungeonstable,
     generatedbasetemplatestable, spacepoitable, dungeon entities/scene, gameplay globals, the 319 scenes) vs 7.05
  9. every user-confirmed in-game fact (tools/golden_ingame_705.json): --quick = the 54 captured-seed loot checks
     (pure Python); full = also the 13 layout / crate / end-reward checks through the whole chain (replaces 5 and 6)

--quick skips 5, 6 and the full part of 9.  --save-baseline records the PAK baseline (only when 1-3 pass), then run again.
After a FAIL: research-output/GAME_UPDATE_RESILIENCE_20261022.md, "After an NMS update" (relocate, re-extract, compare).
Exit code 0 = everything that ran passed.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(HERE))
import live_position_705 as LIVE  # noqa: E402
import settings as ST  # noqa: E402

BASELINE = HERE / "build_baseline.json"
# user-verified in the live game (STATUS.md, GENERATOR_VALIDATION_VS_LIVE_20261020.md): rooms / crates / footlockers
GOLDEN_LAYOUTS = [
    {"address": "00003B0006606CAA", "seed": "7D7ED1B33E15365D", "preset": "CARGO_BUGS", "rooms": 11, "crates": 17, "lockers": 6, "instances": 145},
    {"address": "0000750006606CAB", "seed": "A4391301293DA029", "preset": "CARGO_BUGS", "rooms": 9, "crates": 18, "lockers": 5, "instances": 121},
]
GOLDEN_REWARD = {"address": "0002250006607CAA", "name": "Salvaged Fleet Fuel Unit", "cls": "B"}   # user's screenshot, 2026-10-20

RESULTS: list[tuple[str, str, str]] = []


def add(status: str, name: str, detail: str = "") -> bool:
    RESULTS.append((status, name, detail))
    print(f"[{status}] {name}" + (f" - {detail}" if detail else ""), flush=True)
    return status == "PASS"


def pak_fingerprint(exe: Path) -> dict[str, int]:
    banks = exe.parent.parent / "GAMEDATA" / "PCBANKS"
    return {p.name: p.stat().st_size for p in sorted(banks.glob("*.pak"))} if banks.is_dir() else {}


def pinned_exe(paths: dict) -> Path | None:
    """The game file the generator maps: the EXE = Path(...) line in the fast generator's native_writer_705.py."""
    try:
        m = re.search(r'^EXE\s*=\s*Path\("([^"]+)"\)', paths["native_writer"].read_text(encoding="utf-8"), re.M)
        return Path(m.group(1)) if m else None
    except OSError:
        return None


def run_golden_layout(paths: dict, g: dict) -> None:
    name = f"golden layout {g['address']}"
    with tempfile.TemporaryDirectory(dir=str(paths["analysis"]) if paths["analysis"].is_dir() else None) as tmp:
        cp = subprocess.run([sys.executable, "-I", str(paths["fast_generate"]), g["address"], "--out", tmp],
                            capture_output=True, text=True, timeout=300)
        dj = Path(tmp) / "derelict.json"
        if cp.returncode != 0 or not dj.exists():
            add("FAIL", name, "generator did not finish: " + (cp.stderr.strip().splitlines() or cp.stdout.strip().splitlines() or ["no output"])[-1][:160])
            return
        d = json.loads(dj.read_text(encoding="utf-8"))
    kinds = d.get("container_kinds") or {}
    crates = sum(1 for c in d["containers"] if c["container_kind"] == "salvage_crate")
    got = {"seed": d.get("seed"), "preset": d.get("preset"), "rooms": len(d["rooms"]), "crates": crates,
           "lockers": len(d["containers"]) - crates, "instances": d.get("instance_count", len(d["instances"]))}
    want = {k: g[k] for k in got}
    if got == want:
        add("PASS", name, f"{got['rooms']} rooms, {got['crates']} crates, {got['lockers']} footlockers, seed {got['seed']}")
    else:
        diff = ", ".join(f"{k}: expected {want[k]}, got {got[k]}" for k in got if got[k] != want[k])
        add("FAIL", name, diff)


def run_golden_reward(paths: dict) -> None:
    g = GOLDEN_REWARD
    name = f"golden end reward {g['address']}"
    try:
        import end_reward_batch_705 as RB
        import predict_end_reward_705 as PR
        PR.EMU_PY, PR.FASTGEN, PR.LAYOUT_DIRS = str(paths["emu_python"]), paths["fast_generate"], paths["layout_dirs"]
        poi = PR.poi_positions([g["address"]]).get(g["address"])
        res = PR.predict(g["address"], poi, PR.load_layout(g["address"]))
        nm, cls, _amb, _alt = RB.result_row(res)
    except Exception as exc:
        add("FAIL", name, f"predictor failed: {exc!r}"[:200])
        return
    if (nm, cls) == (g["name"], g["cls"]):
        add("PASS", name, f"{nm}, {cls}-class (matches the in-game screenshot)")
    else:
        add("FAIL", name, f"expected {g['name']} {g['cls']}, got {nm} {cls}")


def run_table_check(exe: Path) -> None:
    """8. raw-byte fingerprints of the game tables the chain reads, vs the 7.05 profile (about 1 s)."""
    name = "game tables the generator reads"
    try:
        import build_profile_705 as BP
        want = BP.load_profile(BP.BASE_ID).get("fingerprints", {}).get("members", {})
        if not want:
            add("SKIP", name, "no 7.05 fingerprints (python -I tools/build_profile_705.py --write-705 on a 7.05 install)")
            return
        got = BP.game_fingerprints(exe.parent.parent)
    except Exception as exc:
        add("WARN", name, f"not checked: {exc!r}"[:200])
        return
    bad = [k for k in want if got.get(k) != want[k]]
    if bad:
        add("FAIL", name, f"changed since 7.05: {', '.join(bad)} (re-extract + compare: see GAME_UPDATE_RESILIENCE_20261022.md)")
    else:
        add("PASS", name, f"{len(want)} tables/scene sets identical to 7.05")


def run_golden_ingame(quick: bool) -> None:
    """9. tools/golden_ingame_705.py: every user-confirmed in-game fact (quick = pure-Python seed checks only)."""
    tool = ROOT / "tools" / "golden_ingame_705.py"
    try:
        cp = subprocess.run([sys.executable, "-I", str(tool), "--json"] + (["--quick"] if quick else []),
                            capture_output=True, text=True, timeout=900)
        doc = json.loads(cp.stdout)
    except Exception as exc:
        add("FAIL", "golden in-game facts", f"could not run {tool.name}: {exc!r}"[:200])
        return
    for part, p in doc["parts"].items():
        fails = [f"{n}: {d}" for st, n, d in p["checks"] if st != "PASS"]
        add("PASS" if not fails else "FAIL", f"golden in-game facts, {part}",
            f"{p['passed']}/{p['total']}" + (f"; e.g. {fails[0]}" if fails else ""))
    if quick:
        add("SKIP", "golden layouts, crates and end rewards (full chain)", "--quick")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--quick", action="store_true", help="skip the golden layout and reward runs")
    ap.add_argument("--save-baseline", action="store_true", help="record the PAK baseline (needs checks 1-3 to pass)")
    a = ap.parse_args(argv)
    paths = ST.paths()

    # 1. installed exe
    pid = LIVE.find_pid()
    running = LIVE.process_path(pid) if pid else None
    exe = ST.find_nms_exe(running)
    if not exe:
        add("FAIL", "installed NMS.exe", "not found (set nms_exe in minimap/settings.json)")
        sha = None
    else:
        sha = LIVE.file_sha256(str(exe))
        add("PASS", "installed NMS.exe", f"{exe}  SHA-256 {sha[:8]}...")
    # 2. reader knows the build
    if sha:
        b = LIVE.KNOWN_BUILDS.get(sha)
        learned = LIVE.load_learned().get(sha)
        if b:
            add("PASS", "live reader supports this build", b["name"])
        elif learned and learned.get("verified"):
            add("PASS", "live reader supports this build", f"learned and verified in game ({learned.get('source')})")
        else:
            try:
                import nms_find_addresses_705 as FIND
                r = FIND.find_app(FIND.Pe(str(exe)))
            except Exception as exc:
                r = {"found": False, "notes": [repr(exc)]}
            if r.get("found"):
                add("WARN", "live reader supports this build",
                    f"new build: the address finder proposes the application object at RVA {r['app_rva']:#x}, Data pointer +{r['data_ptr']:#x} "
                    f"({r['method']}). The overlay will use it marked 'unverified'. Verify it in the game: "
                    "python -I tools/live_position_705.py --verify-glyphs <12 glyph hex of the system you are in>")
            else:
                add("FAIL", "live reader supports this build",
                    "unknown build and the address finder found nothing: the minimap shows 'unsupported NMS version' until the addresses are found by hand")
    # 3. generator pinned exe
    pin = pinned_exe(paths)
    pin_sha = None
    if not pin or not pin.is_file():
        add("FAIL", "generator game file", f"pinned copy not found ({pin})")
    else:
        pin_sha = LIVE.file_sha256(str(pin))
        if sha and pin_sha == sha:
            add("PASS", "generator uses the installed build", f"pinned copy {pin.name} is identical")
        elif sha:
            add("FAIL", "generator uses the installed build",
                f"the generator reads a pinned copy ({pin_sha[:8]}...) but the installed game is {sha[:8]}...: layouts and rewards are still "
                "for the OLD build until the generator is re-verified on the new one (do not publish new atlas data)")
    # 4. pak baseline
    base_ok = bool(sha and pin_sha == sha and sha in LIVE.KNOWN_BUILDS)
    if exe:
        now = pak_fingerprint(exe)
        if a.save_baseline:
            if base_ok and now:
                BASELINE.write_text(json.dumps({"exe_sha256": sha, "paks": now}, indent=1), encoding="utf-8")
                add("PASS", "PAK baseline saved", f"{len(now)} files -> {BASELINE.name}")
            else:
                add("FAIL", "PAK baseline", "not saved: checks 1-3 must pass first")
        elif not BASELINE.exists():
            add("SKIP", "game data files (PAK) unchanged", "no baseline yet; run with --save-baseline after verifying a build")
        else:
            saved = json.loads(BASELINE.read_text(encoding="utf-8"))["paks"]
            changed = [f"{n}: {saved[n]} -> {now[n]}" for n in saved if n in now and saved[n] != now[n]]
            changed += [f"{n}: removed" for n in saved if n not in now] + [f"{n}: new" for n in now if n not in saved]
            if not changed:
                add("PASS", "game data files (PAK) unchanged", f"{len(now)} files, same names and sizes as the baseline")
            else:
                add("FAIL", "game data files (PAK) unchanged", f"{len(changed)} differ (e.g. {'; '.join(changed[:3])}): templates or presets may have changed")
    # 8. game tables the generator reads
    if exe:
        run_table_check(exe)
    # 5/6/9. golden in-game facts (tools/golden_ingame_705.py: includes GOLDEN_LAYOUTS and GOLDEN_REWARD below)
    if not a.quick and not paths["fast_generate"].is_file():
        add("FAIL", "golden layouts", f"fast generator not found ({paths['fast_generate']})")
    else:
        run_golden_ingame(a.quick)
    # 7. live reader sanity
    if not pid:
        add("SKIP", "live reader sanity", "NMS is not running")
    else:
        try:
            r = LIVE.LiveReader(pid)
            s = r.sample()
            r.close()
            if r.build_error:
                add("FAIL", "live reader sanity", "unsupported build")
            elif s is None:
                add("SKIP", "live reader sanity", "no save loaded yet")
            elif re.fullmatch(r"[0-9A-F]{16}", s["address"]) and all(math.isfinite(s[k]) for k in "xyz"):
                add("PASS", "live reader sanity", f"address {s['address']}, position {s['x']:.0f}, {s['y']:.0f}, {s['z']:.0f}")
            else:
                add("FAIL", "live reader sanity", f"implausible values: {s}")
        except Exception as exc:
            add("FAIL", "live reader sanity", repr(exc)[:160])

    bad = [r for r in RESULTS if r[0] == "FAIL"]
    warn = [r for r in RESULTS if r[0] == "WARN"]
    print()
    if not bad:
        print("RESULT: everything that ran passed" + (f", with {len(warn)} warning(s) to act on." if warn else "."))
        return 0
    print(f"RESULT: {len(bad)} check(s) FAILED.")
    if any("reader supports" in r[1] or "live reader sanity" in r[1] for r in bad):
        print(" - The in-game map cannot read the game until its memory addresses are updated for this build.")
    if any(k in r[1] for r in bad for k in ("generator", "golden", "PAK")):
        print(" - Generated layouts / rewards may be wrong for this build. Don't trust or publish them until re-verified.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
