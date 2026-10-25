"""First-run setup of the portable minimap: build everything that comes from the user's own game, once. Safe to re-run.

    python -I minimap/first_run.py [--force]

Nothing from the game is shipped with the minimap. This reads the installed game (read-only) and writes into the minimap's own
folders:
  1. finds NMS and checks the build against the one the minimap supports (an unsupported build is reported, not guessed at)
  2. copies NMS.exe into NMS-Derelict-Probe-analysis/rea/ (the generator reads this pinned copy, never the live game)
  3. extracts the game tables / scenes the layout generator needs (tools/extract_build_data_705.py, MBINCompiler, ~minutes)
  4. puts them where the generator looks and runs the golden checks (a known derelict must come out exactly as validated)
Map meshes are built on demand, per derelict, the first time its map is drawn.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tools"))
import settings as ST  # noqa: E402

PKG = ROOT.parent
STATE = "first_run.json"
SUPPORTED_SHA = "13D5060D4EFB9D2A6A6B1B349BC4257231056CC2A055DF4BB15D816262CC3499"
BUILD = "7.05"


def say(msg: str) -> None:
    print(msg, flush=True)


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def remove_link_or_dir(p: Path) -> None:
    """Delete a folder junction (the link only) or a real folder."""
    import os
    if os.path.isjunction(p):
        os.rmdir(p)
    elif p.is_dir():
        shutil.rmtree(p)


def python_exe() -> str:
    cand = PKG / "python" / "python.exe"
    return str(cand if cand.is_file() else sys.executable)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--force", action="store_true", help="redo every step")
    a = ap.parse_args(argv)
    if not (PKG / ".nmsmm-home").is_file():       # this step replaces the generator's input folders: never in the development tree
        say("first_run.py only runs inside the portable package (no .nmsmm-home marker found). Nothing was changed.")
        return 1
    p = ST.paths()
    analysis = p["analysis"]
    state_file = analysis / STATE
    exe = ST.find_nms_exe()
    if exe is None:
        say("No Man's Sky was not found. Start the game once, or put the path to its NMS.exe into minimap/settings.json (nms_exe).")
        return 1
    game = exe.parent.parent
    sha = sha256(exe)
    say(f"Game: {game}\nNMS.exe SHA-256: {sha}")
    if sha != SUPPORTED_SHA:
        say(f"This minimap supports NMS {BUILD} (SHA-256 {SUPPORTED_SHA[:8]}...). Your game is a different build.\n"
            "The overlay will say 'unsupported NMS version' instead of showing a wrong map. Check for a minimap update after a game patch.")
        return 2
    done = {}
    try:
        done = json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    if done.get("exe_sha256") == sha and done.get("complete") and not a.force:
        say("Already set up for this game build. Nothing to do (use --force to redo).")
        return 0

    t0 = time.time()
    if done.get("exe_sha256") == sha and done.get("extracted") and not a.force:
        say("[1-3/3] game data already extracted for this build; re-running the checks only")
        return finish(state_file, analysis, sha, t0)
    # 2. pinned copy of the exe
    pinned = analysis / "rea" / f"NMS-{sha[:8]}.exe"
    pinned.parent.mkdir(parents=True, exist_ok=True)
    if not pinned.is_file() or sha256(pinned) != sha:
        say(f"[1/3] copying NMS.exe to {pinned} (the generator reads this copy)")
        shutil.copy2(exe, pinned)
    else:
        say("[1/3] pinned game copy present")

    # 3. extraction
    raw = PKG / "game-data"
    say("[2/3] extracting the game tables and scenes the generator needs (this takes a few minutes, once)")
    if raw.exists():
        shutil.rmtree(raw)
    # The last extraction step reads the generator's inputs from NMS-Derelict-Probe/research-output (where the development
    # copy keeps the validated 7.05 data). Here they do not exist yet, so link those folders to what is being extracted.
    names = ("exact705-dungeon-inputs-20261019", "generatedbase-table-705", "exact705-generatedbase-scenes-20261019")
    links = []
    for n in names:
        (raw / "research-output" / n).mkdir(parents=True)
        link = ROOT / "research-output" / n
        remove_link_or_dir(link)
        link.parent.mkdir(parents=True, exist_ok=True)
        j = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(raw / "research-output" / n)], capture_output=True,
                           text=True, creationflags=0x08000000)
        if j.returncode:
            say(f"Could not link {link}: {(j.stderr or j.stdout).strip()}")
            return 3
        links.append(link)
    cmd = [python_exe(), "-I", str(HERE / "first_run_driver.py"), str(game), str(raw)]
    r = subprocess.run(cmd, capture_output=True, text=True, creationflags=0x08000000)
    for link in links:
        remove_link_or_dir(link)
    (analysis / "first_run.log").write_text((r.stdout or "") + "\n--- stderr ---\n" + (r.stderr or ""), encoding="utf-8")
    if r.returncode:
        say(f"Extraction failed (exit {r.returncode}). Details: {analysis / 'first_run.log'}\n{(r.stderr or r.stdout)[-600:]}")
        return 3
    # 4. install where the generator looks
    say("[3/3] installing the extracted data and running the checks")
    for sub in ("research-output",):
        src = raw / sub
        if src.is_dir():
            for d in src.iterdir():
                dst = ROOT / sub / d.name
                remove_link_or_dir(dst)
                shutil.copytree(d, dst)
    (analysis / "emu").mkdir(parents=True, exist_ok=True)
    shutil.copy2(raw / "asset_source_rows.bin", analysis / "emu" / "asset_source_rows.bin")
    (analysis / "end-reward-cache").mkdir(parents=True, exist_ok=True)
    shutil.copy2(raw / "spacepoi" / "spacepoitable.mbin", analysis / "end-reward-cache" / "spacepoitable.mbin")

    return finish(state_file, analysis, sha, t0)


def finish(state_file: Path, analysis: Path, sha: str, t0: float) -> int:
    """Golden checks (a known derelict must come out exactly as validated), then record the result."""
    say("verifying the generator against the validated in-game facts (a few minutes; each new layout takes ~25 s)")
    chk = subprocess.run([python_exe(), "-I", str(HERE / "check_update.py")], capture_output=True, text=True, creationflags=0x08000000)
    (analysis / "first_run_check.log").write_text(chk.stdout + "\n" + chk.stderr, encoding="utf-8")
    ok = chk.returncode == 0
    say(chk.stdout.strip()[-1500:])
    state_file.write_text(json.dumps({"exe_sha256": sha, "build": BUILD, "extracted": True, "complete": ok, "seconds": round(time.time() - t0, 1),
                                      "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, indent=2) + "\n", encoding="utf-8")
    say("Setup finished." if ok else f"Setup finished, but a check failed. See {analysis / 'first_run_check.log'}.")
    return 0 if ok else 4


if __name__ == "__main__":
    sys.exit(main())
