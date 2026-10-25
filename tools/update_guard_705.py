"""Fast "was No Man's Sky updated?" guard for the scanner (stdlib only, read-only; never opens the game process).

    python -I tools/update_guard_705.py [--mode start|publish] [--json]     exit 0 = ok / warning, 2 = blocked
    python -I tools/update_guard_705.py --selftest                          fake-update tests in a temp folder
    python -I tools/update_guard_705.py --accept --report <compare.json>    accept the installed build as equivalent

The generator, reward and loot predictors produce NMS 7.05 data: they read a pinned copy of the 7.05 NMS.exe and
7.05 game tables (minimap/README.md, "After an NMS update"). After a Steam update the installed game differs, and
the space-POI step (Shipwright) would even read the NEW exe, so new atlas rows could silently mix builds.
check() compares, in a few milliseconds once the exe hash is cached:
  1. installed NMS.exe SHA-256 (settings / Steam libraries, NOT the running process) vs the generator's pinned copy
     (the EXE = Path(...) line of the fast generator's native_writer_705.py)
  2. PAK names + sizes vs minimap/build_baseline.json (the baseline saved when the generator was verified)
  mode "start" adds (about 1 s): 3. raw-byte fingerprints of the game tables the chain reads (rewardtable,
  freighterdungeonstable, generatedbasetemplatestable, spacepoitable, dungeon entities, gameplay globals) vs the
  7.05 profile, and 4. the pure-Python golden loot checks of tools/golden_ingame_705.py (54 user-confirmed seeds).
Result: blocked=True when the game changed (or a golden check fails); "no game install found" only warns.
A build accepted with --accept (after tools/compare_builds_705.py decided "atlas valid for new build") passes.

Test hooks (environment): NMS_UPDATE_GUARD=off (never block), NMS_UPDATE_GUARD_EXE=<path> | none (pretend the
installed exe is that file / not installed), NMS_UPDATE_GUARD_BASELINE=<json>, NMS_UPDATE_GUARD_ACCEPTED=<json>,
NMS_UPDATE_GUARD_PINNED=<path> (pretend the generator pins that exe).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
NATIVE_WRITER = Path("D:/Orca/NMS-Derelict-Probe-fastgen/native_writer_705.py")
BASELINE = ROOT / "minimap" / "build_baseline.json"
ACCEPTED = Path("D:/Orca/NMS-Derelict-Probe-analysis/builds/accepted-builds.json")
GENERATOR_BUILD = "7.05"
MESSAGE = ("NMS was updated: generator data is {gen}; run the update check (tools/Check-After-NMS-Update.cmd, then "
           "research-output/GAME_UPDATE_RESILIENCE_20261022.md). Scanning and publishing are paused.")


class UpdateBlocked(Exception):
    """Raised by the scanner hook when the game changed (deliberately not a RuntimeError: the scanner's network
    retry wrapper must not swallow it)."""


_HASH: dict = {}


def file_sha256(path) -> str:
    """SHA-256 (upper hex), cached by path + size + mtime (the 88 MB exe takes about 0.5 s once)."""
    st = os.stat(path)
    key = (str(path), st.st_size, st.st_mtime_ns)
    if key not in _HASH:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        _HASH[key] = h.hexdigest().upper()
    return _HASH[key]


def installed_exe() -> Path | None:
    env = os.environ.get("NMS_UPDATE_GUARD_EXE")
    if env:
        return None if env.lower() == "none" or not Path(env).is_file() else Path(env)
    sys.path.insert(0, str(ROOT / "minimap"))
    import settings as ST  # noqa: E402
    return ST.find_nms_exe(None)          # settings, then Steam; never the running process


def pinned_exe() -> Path | None:
    env = os.environ.get("NMS_UPDATE_GUARD_PINNED")
    if env:
        return Path(env)
    try:
        m = re.search(r'^EXE\s*=\s*Path\("([^"]+)"\)', NATIVE_WRITER.read_text(encoding="utf-8"), re.M)
        return Path(m.group(1)) if m else None
    except OSError:
        return None


def pak_fingerprint(exe: Path) -> dict[str, int]:
    banks = exe.parent.parent / "GAMEDATA" / "PCBANKS"
    return {p.name: p.stat().st_size for p in sorted(banks.glob("*.pak"))} if banks.is_dir() else {}


def _load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def accepted_builds() -> dict:
    return _load(Path(os.environ.get("NMS_UPDATE_GUARD_ACCEPTED") or ACCEPTED), {})


def check(mode: str = "publish") -> dict:
    """mode 'publish' (milliseconds; exe hash cached) or 'start' (+ table fingerprints + quick golden, about 1 s)."""
    t0 = time.perf_counter()
    res = {"status": "ok", "blocked": False, "message": "", "mode": mode, "generator_build": GENERATOR_BUILD,
           "checks": [], "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    add = lambda st, name, detail="": res["checks"].append([st, name, detail])
    if os.environ.get("NMS_UPDATE_GUARD", "").lower() in ("off", "0", "disabled"):
        res.update(status="disabled", message="update guard disabled by NMS_UPDATE_GUARD=off")
        return res
    exe = installed_exe()
    pin = pinned_exe()
    pin_sha = file_sha256(pin) if pin and pin.is_file() else None
    res["pinned_sha"] = pin_sha
    if not pin_sha:
        add("WARN", "generator pinned exe", f"not found ({pin})")
    if not exe:
        add("WARN", "installed NMS.exe", "not found (minimap/settings.json nms_exe or Steam)")
        res.update(status="no_game", message="No Man's Sky install not found: update check skipped (warning only)")
        res["seconds"] = round(time.perf_counter() - t0, 3)
        return res
    sha = file_sha256(exe)
    res.update(installed_exe=str(exe), installed_sha=sha)
    acc = accepted_builds().get(sha)
    changed = []
    if pin_sha and sha == pin_sha:
        add("PASS", "installed NMS.exe = generator's pinned copy", sha[:8])
    elif acc:
        add("PASS", "installed NMS.exe accepted as equivalent", f"{sha[:8]} accepted {acc.get('accepted_utc')} ({acc.get('reason', '')})")
    else:
        changed.append(f"NMS.exe {sha[:8]} != generator {str(pin_sha)[:8]}")
        add("FAIL", "installed NMS.exe = generator's pinned copy", changed[-1])
    base = (acc or {}).get("paks") or _load(Path(os.environ.get("NMS_UPDATE_GUARD_BASELINE") or BASELINE), {}).get("paks")
    now = pak_fingerprint(exe)
    if base and now:
        diff = [n for n in base if now.get(n) != base[n]] + [n for n in now if n not in base]
        if diff:
            changed.append(f"{len(diff)} PAK file(s) changed (e.g. {', '.join(diff[:3])})")
            add("FAIL", "game PAK files unchanged", changed[-1])
        else:
            add("PASS", "game PAK files unchanged", f"{len(now)} files")
    else:
        add("WARN", "game PAK files unchanged", "no baseline or no PCBANKS folder")
    if mode == "start":
        try:
            import build_profile_705 as BP
            want = ((acc or {}).get("fingerprints") or BP.load_profile(BP.BASE_ID).get("fingerprints", {})).get("members", {})
            if want:
                got = BP.game_fingerprints(exe.parent.parent)
                bad = [k for k in want if got.get(k) != want[k]]
                if bad:
                    changed.append("game tables changed: " + ", ".join(bad))
                    add("FAIL", "game tables the generator reads", changed[-1])
                else:
                    add("PASS", "game tables the generator reads", f"{len(want)} tables identical")
        except Exception as exc:  # hgpaktool missing, PAK locked...: not a reason to block
            add("WARN", "game tables the generator reads", f"not checked: {exc!r}"[:200])
        try:
            import golden_ingame_705 as GI
            q = GI.quick_checks()
            if q["failed"]:
                changed.append(f"golden loot checks failed {q['failed']}/{q['total']}")
                add("FAIL", "golden loot seeds (pure Python)", changed[-1])
            else:
                add("PASS", "golden loot seeds (pure Python)", f"{q['passed']}/{q['total']}")
        except Exception as exc:
            add("WARN", "golden loot seeds (pure Python)", f"not run: {exc!r}"[:200])
    if changed:
        res.update(status="changed", blocked=True, message=MESSAGE.format(gen=GENERATOR_BUILD), reasons=changed)
    res["seconds"] = round(time.perf_counter() - t0, 3)
    return res


def accept(report: Path) -> dict:
    """Record the installed build as equivalent to the generator data, from a compare_builds_705.py report whose
    decision is 'atlas valid for new build'. Only then does the guard let the scanner publish on that build."""
    rep = json.loads(Path(report).read_text(encoding="utf-8"))
    if not str(rep.get("decision", "")).startswith("atlas valid"):
        raise SystemExit(f"report decision is {rep.get('decision')!r}: not accepting")
    exe = installed_exe()
    if not exe:
        raise SystemExit("installed NMS.exe not found")
    sha = file_sha256(exe)
    if rep.get("new_exe_sha256") and rep["new_exe_sha256"] != sha:
        raise SystemExit("the report was made for another exe than the installed one")
    import build_profile_705 as BP
    path = Path(os.environ.get("NMS_UPDATE_GUARD_ACCEPTED") or ACCEPTED)
    data = _load(path, {})
    data[sha] = {"accepted_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "as": GENERATOR_BUILD,
                 "reason": f"compare_builds_705: {rep.get('decision')} ({rep.get('systems')} systems)",
                 "report": str(report), "paks": pak_fingerprint(exe),
                 "fingerprints": {"members": BP.game_fingerprints(exe.parent.parent)}}
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.with_name(path.name + ".bak").write_bytes(path.read_bytes())
    path.write_text(json.dumps(data, indent=1), encoding="utf-8")
    return data[sha]


def selftest() -> int:
    """Fake updates without touching the game: a temp 'game' folder with a fake exe and PAKs."""
    ok = True
    saved = {k: os.environ.get(k) for k in ("NMS_UPDATE_GUARD", "NMS_UPDATE_GUARD_EXE", "NMS_UPDATE_GUARD_BASELINE",
                                            "NMS_UPDATE_GUARD_ACCEPTED", "NMS_UPDATE_GUARD_PINNED")}

    def case(name, want_blocked, want_status, mode="publish"):
        nonlocal ok
        t = time.perf_counter()
        r = check(mode)
        good = r["blocked"] == want_blocked and r["status"] == want_status
        ok &= good
        print(f"[{'PASS' if good else 'FAIL'}] {name}: status={r['status']} blocked={r['blocked']} "
              f"({(time.perf_counter() - t) * 1000:.0f} ms) {r.get('message', '')[:90]}")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            game = Path(tmp) / "No Man's Sky"
            (game / "Binaries").mkdir(parents=True)
            (game / "GAMEDATA" / "PCBANKS").mkdir(parents=True)
            fake_exe = game / "Binaries" / "NMS.exe"
            fake_exe.write_bytes(b"MZ fake NMS.exe for the update-guard self test")
            (game / "GAMEDATA" / "PCBANKS" / "NMSARC.Precache.pak").write_bytes(b"x" * 100)
            pin = Path(tmp) / "pinned.exe"
            pin.write_bytes(fake_exe.read_bytes())
            base = Path(tmp) / "baseline.json"
            base.write_text(json.dumps({"paks": {"NMSARC.Precache.pak": 100}}))
            os.environ.update(NMS_UPDATE_GUARD_EXE=str(fake_exe), NMS_UPDATE_GUARD_PINNED=str(pin),
                              NMS_UPDATE_GUARD_BASELINE=str(base), NMS_UPDATE_GUARD_ACCEPTED=str(Path(tmp) / "acc.json"))
            case("same exe + same PAKs", False, "ok")
            (game / "GAMEDATA" / "PCBANKS" / "NMSARC.Precache.pak").write_bytes(b"x" * 101)
            case("PAK size changed (game data update)", True, "changed")
            (game / "GAMEDATA" / "PCBANKS" / "NMSARC.Precache.pak").write_bytes(b"x" * 100)
            fake_exe.write_bytes(b"MZ fake NMS.exe, NEW build")
            case("exe changed (game update)", True, "changed")
            acc = {file_sha256(fake_exe): {"accepted_utc": "test", "reason": "selftest", "paks": {"NMSARC.Precache.pak": 100}}}
            (Path(tmp) / "acc.json").write_text(json.dumps(acc))
            case("exe changed but accepted after a comparison", False, "ok")
            os.environ["NMS_UPDATE_GUARD"] = "off"
            (Path(tmp) / "acc.json").write_text("{}")
            case("guard disabled by environment", False, "disabled")
            del os.environ["NMS_UPDATE_GUARD"]
            os.environ["NMS_UPDATE_GUARD_EXE"] = "none"
            case("no game install found (warn only)", False, "no_game")
        for k in ("NMS_UPDATE_GUARD", "NMS_UPDATE_GUARD_EXE", "NMS_UPDATE_GUARD_BASELINE", "NMS_UPDATE_GUARD_ACCEPTED",
                  "NMS_UPDATE_GUARD_PINNED"):
            os.environ.pop(k, None)
        case("the real installed game (start mode)", False, "ok", mode="start")
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    print("SELFTEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mode", choices=("start", "publish"), default="start")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--accept", action="store_true")
    ap.add_argument("--report", type=Path)
    a = ap.parse_args(argv)
    sys.path.insert(0, str(HERE))
    if a.selftest:
        return selftest()
    if a.accept:
        if not a.report:
            ap.error("--accept needs --report <compare_builds report json>")
        print(json.dumps(accept(a.report), indent=1)[:2000])
        return 0
    r = check(a.mode)
    if a.json:
        print(json.dumps(r, indent=1))
    else:
        for st, name, detail in r["checks"]:
            print(f"[{st}] {name}" + (f" - {detail}" if detail else ""))
        print(f"RESULT: {r['status']}{' (BLOCKED)' if r['blocked'] else ''} in {r['seconds']} s" + (f": {r['message']}" if r["message"] else ""))
    return 2 if r["blocked"] else 0


if __name__ == "__main__":
    sys.exit(main())
