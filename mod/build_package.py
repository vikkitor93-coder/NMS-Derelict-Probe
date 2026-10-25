"""Build the portable minimap package from the live project folders (read-only on them; stdlib only).

    python -I mod/build_package.py [--out DIR] [--shipwright DIR] [--with-mbincompiler] [--no-runtime]

Output (default D:/Orca/NMS-Derelict-Minimap-dist/NMS-Derelict-Minimap): a folder that runs from anywhere:
    python/                  trimmed copy of the Python.org runtime (tkinter included) + unicorn, pefile, hgpaktool, lz4, zstandard
    NMS-Derelict-Probe/      minimap/, tools/, research-output/offline-layout-705-20261019/*.py   (our code only)
    NMS-Derelict-Probe-fastgen/  fast_generate_705.py   (the native engine is NOT shipped, see below)
    NMS-Shipwright/          nms_procgen + nms_save (MIT)
    third-party/             MBINCompiler, only with --with-mbincompiler (used once on first run, then not needed)
    Install.cmd, Uninstall.cmd, Start-Minimap.cmd, Start-With-NMS.cmd, First-Run-Setup.cmd, README.txt, LICENSES/, MANIFEST.json

What is NOT in it: any file from the game (meshes, tables, scenes, NMS.exe). The first-run setup builds those from the
user's own install (minimap/first_run.py).

The shipped copies differ from the project's files in exactly these ways (nothing in the project is edited):
  1. machine-specific path literals (D:/Orca/..., C:/Users/<name>/..., G:/SteamLibrary/...) become `nmshome` lookups
  2. `sys.executable` for child processes becomes the package's console python
  3. layouts are generated with the Unicorn engine only (identical output, ~25 s instead of ~2 s per new derelict). The
     native engine runs the game's code in executable memory (VirtualAlloc RWX), which antivirus heuristics flag, so
     native_writer_705.py is not shipped and build_package fails if any shipped file contains such code.
Build fails if a path literal, RWX memory use or an unparsable file is left.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import closure as CL  # noqa: E402

FASTGEN_SRC = ROOT.parent / "NMS-Derelict-Probe-fastgen"
OFFLINE = "research-output/offline-layout-705-20261019"
VERSION = "0.4.0"
MARKER = ".nmsmm-home"

# entry points on top of closure.ENTRY: scripts that are run by path or import modules lazily
EXTRA_ENTRY = ["tools/extract_build_data_705.py", "tools/extract_generatedbase_scene_assets.py", "tools/emulate_writer_705_assets.py",
               "tools/relocate_generator_705.py", "tools/build_profile_705.py", "tools/predict_crate_loot_705.py",
               "tools/predict_end_reward_705.py", "minimap/first_run.py", "mod/nmshome.py"]
EXCLUDE_NAMES = {"native_writer_705.py"}          # RWX native engine: never shipped
SKIP_SUFFIX = (".pre-", ".bak", ".orig")

# ---------------------------------------------------------------- path rewriting
RULES = [   # (normalised literal prefix, replacement expression) - first match wins, longest first
    ("D:/Orca/Temp/mbincompiler-7.04.1-pre3/MBINCompiler.exe", "_NH.MBC_704"),
    ("D:/Orca/Temp/mbincompiler-7.07.0-pre1/MBINCompiler.exe", "_NH.MBC_707"),
    ("D:/Orca/Temp/generatedbase-table-705-mbc707", "_NH.GAMEDATA / 'writer-table'"),
    ("D:/Orca/NMS-Derelict-Probe-analysis", "_NH.ANALYSIS"),
    ("D:/Orca/NMS-Derelict-Probe-fastgen", "_NH.FASTGEN"),
    ("D:/Orca/NMS-Derelict-Atlas", "_NH.HOME / 'atlas'"),
    ("D:/Orca/NMS-Derelict-Probe", "_NH.PROBE"),
    ("%USERPROFILE%/tools/NMS-Shipwright/.venv/Scripts/python.exe", "_NH.PYTHON"),
    ("%USERPROFILE%/tools/NMS-Shipwright", "_NH.SHIPWRIGHT"),
    ("G:/SteamLibrary/steamapps/common/No Man's Sky/GAMEDATA/PCBANKS", "_NH.PCBANKS"),
    ("G:/SteamLibrary/steamapps/common/No Man's Sky/Binaries/NMS.exe", "_NH.NMS_EXE"),
]
LITERAL = re.compile(r'''(?P<pre>[rRuU]?)(?:"(?P<b1>[A-Za-z]:[^"\n]*)"|'(?P<b2>[A-Za-z]:[^'\n]*)')''')
SUSPECT = re.compile(r"(?i)^[a-z]:[\\/]+.*(orca|users[\\/]+[^\\/]+[\\/]|steamlibrary)|^%USERPROFILE%")
# project code spells a path under the user profile as os.path.expandvars("%USERPROFILE%/...") (no user name in the source)
EXPAND = re.compile(r'''(?:_?os)\.path\.expandvars\(\s*(?:"(?P<b1>%USERPROFILE%[^"\n]*)"|'(?P<b2>%USERPROFILE%[^'\n]*)')\s*\)''')
RWX = re.compile(r"VirtualAlloc|PAGE_EXECUTE|VirtualProtect|CreateRemoteThread|WriteProcessMemory|NtWriteVirtualMemory")


def rewrite_text(text: str, name: str) -> tuple[str, int]:
    n = 0

    def sub(m: re.Match) -> str:
        nonlocal n
        body = (m.group("b1") if m.group("b1") is not None else m.group("b2")).replace("\\\\", "/").replace("\\", "/")
        if not SUSPECT.match(body):
            return m.group(0)
        for prefix, expr in RULES:
            if body.lower().startswith(prefix.lower()):
                rest = body[len(prefix):]
                n += 1
                return f"(str({expr})" + (f" + {rest!r}" if rest else "") + ")"
        raise SystemExit(f"{name}: no rewrite rule for path literal {body!r}")

    out = LITERAL.sub(sub, EXPAND.sub(sub, text))
    if "_NH." in out and "import nmshome as _NH" not in out:
        out = insert_import(out, name)
    return out, n


def insert_import(text: str, name: str) -> str:
    tree = ast.parse(text.lstrip("\ufeff"))
    line = 0
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(getattr(node, "value", None), ast.Constant) and isinstance(node.value.value, str):
            line = node.end_lineno
        elif isinstance(node, ast.ImportFrom) and node.module == "__future__":
            line = node.end_lineno
        else:
            break
    lines = text.lstrip("\ufeff").splitlines(keepends=True)
    lines.insert(line, "import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); "
                       "import nmshome as _NH  # noqa: E402  (portable package: locations come from nmshome.py)\n")
    return "".join(lines)


def transform(path: Path, rel: str) -> str:
    text = path.read_text(encoding="utf-8-sig")
    if rel not in ("NMS-Derelict-Probe/minimap/lifecycle.py", "NMS-Derelict-Probe/minimap/overlay.py", "NMS-Derelict-Probe/minimap/core.py",
                   "NMS-Derelict-Probe/mod/nmshome.py"):
        text = re.sub(r"\bsys\.executable\b", "str(_NH.PYTHON)", text)
    if rel.endswith("tools/predict_end_reward_705.py"):
        old = "str(FASTGEN), address]"
        if old not in text:
            raise SystemExit("predict_end_reward_705.py: the fast_generate call changed; update build_package.py")
        text = text.replace(old, 'str(FASTGEN), address, "--engine", "unicorn"]')
    text, _ = rewrite_text(text, rel)
    return text


# ---------------------------------------------------------------- collecting
def project_files() -> dict[str, Path]:
    """published relative path -> source file"""
    CL.SEARCH[:] = [ROOT / "minimap", ROOT / "tools", ROOT / OFFLINE, ROOT / "research-output/offline-generator-assessment-20261019", FASTGEN_SRC, ROOT / "mod"]
    files, _ = CL.closure(CL.ENTRY + EXTRA_ENTRY)
    out: dict[str, Path] = {}
    for f in files:
        if f.name in EXCLUDE_NAMES or any(s in f.name for s in SKIP_SUFFIX) or f.name.startswith("test_"):
            continue
        try:
            rel = f.relative_to(ROOT)
            top = "NMS-Derelict-Probe/" + rel.as_posix()
        except ValueError:
            top = "NMS-Derelict-Probe-fastgen/" + f.relative_to(FASTGEN_SRC).as_posix()
        if top.startswith("NMS-Derelict-Probe/mod/"):
            continue          # nmshome.py is placed separately
        out[top] = f
    out["NMS-Derelict-Probe/minimap/test_minimap.py"] = ROOT / "minimap/test_minimap.py"
    for extra in ("minimap/build_baseline.json", "minimap/README.md"):
        out["NMS-Derelict-Probe/" + extra] = ROOT / extra
    return out


# ---------------------------------------------------------------- runtime
def copy_runtime(dst: Path, packages_from: Path) -> None:
    src = Path(sys.base_prefix)
    dst.mkdir(parents=True)
    for pat in ("python.exe", "pythonw.exe", "python3*.dll", "vcruntime*.dll", "LICENSE.txt", "msvcp*.dll"):
        for f in src.glob(pat):
            shutil.copy2(f, dst / f.name)
    shutil.copytree(src / "DLLs", dst / "DLLs", ignore=shutil.ignore_patterns("*.lib", "__pycache__"))
    skip = shutil.ignore_patterns("site-packages", "test", "tests", "idlelib", "turtledemo", "ensurepip", "__pycache__", "lib2to3",
                                  "pydoc_data", "*.pyc", "turtle.py", "distutils")
    shutil.copytree(src / "Lib", dst / "Lib", ignore=skip)
    shutil.copytree(src / "tcl", dst / "tcl", ignore=shutil.ignore_patterns("demos", "*.lib", "__pycache__"))
    (dst / "Lib" / "site-packages").mkdir()
    for name in ("unicorn", "pefile.py", "peutils.py", "ordlookup", "hgpaktool", "lz4", "zstandard"):
        s = packages_from / name
        if not s.exists():
            raise SystemExit(f"package missing in {packages_from}: {name}")
        if s.is_dir():
            shutil.copytree(s, dst / "Lib" / "site-packages" / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copy2(s, dst / "Lib" / "site-packages" / name)
    for d in packages_from.glob("*.dist-info"):
        if re.match(r"(?i)(unicorn|pefile|hgpaktool|lz4|zstandard)-", d.name):
            shutil.copytree(d, dst / "Lib" / "site-packages" / d.name)


# ---------------------------------------------------------------- guard + manifest
def guard(pkg: Path) -> list[str]:
    problems: list[str] = []
    for f in pkg.rglob("*.py"):
        if "python" in f.relative_to(pkg).parts[:1]:
            continue
        rel = f.relative_to(pkg).as_posix()
        text = f.read_text(encoding="utf-8-sig", errors="replace")
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            problems.append(f"{rel}: does not parse ({exc})")
            continue
        docs = {id(n.body[0]) for n in ast.walk(tree) if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef))
                and n.body and isinstance(n.body[0], ast.Expr)}
        for n in ast.walk(tree):
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and SUSPECT.match(n.value.strip()):
                if id(n) in {id(x.value) for x in ast.walk(tree) if isinstance(x, ast.Expr)}:
                    continue    # a bare string statement = docstring
                problems.append(f"{rel}:{n.lineno}: machine path left: {n.value[:70]!r}")
        if RWX.search(text):
            problems.append(f"{rel}: executable-memory / injection API name found: {RWX.search(text).group(0)}")
    return problems


def manifest(pkg: Path) -> dict:
    files = {}
    for f in sorted(pkg.rglob("*")):
        if f.is_file() and f.name != "MANIFEST.json":
            files[f.relative_to(pkg).as_posix()] = hashlib.sha256(f.read_bytes()).hexdigest()
    return {"name": "NMS Derelict Minimap", "version": VERSION, "built_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "files": len(files), "sha256": files}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="D:/Orca/NMS-Derelict-Minimap-dist/NMS-Derelict-Minimap")
    ap.add_argument("--shipwright", default=os.path.expandvars("%USERPROFILE%/tools/NMS-Shipwright"))
    ap.add_argument("--with-mbincompiler", action="store_true")
    ap.add_argument("--no-runtime", action="store_true", help="skip the Python runtime copy (fast, for testing the code layout)")
    a = ap.parse_args()
    out, sw = Path(a.out), Path(a.shipwright)
    if out.exists():
        if not (out / MARKER).is_file():
            raise SystemExit(f"{out} exists and is not a minimap package; refusing to delete it")
        shutil.rmtree(out)
    out.mkdir(parents=True)
    (out / MARKER).write_text("NMS Derelict Minimap portable package\n", encoding="utf-8")

    # code
    n_rewritten = 0
    for rel, src in sorted(project_files().items()):
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix == ".py":
            text = transform(src, rel)
            n_rewritten += text != src.read_text(encoding="utf-8-sig")
            dst.write_text(text, encoding="utf-8")
        else:
            shutil.copy2(src, dst)
    # nmshome next to every shipped script folder
    for d in {p.parent for p in out.rglob("*.py") if "python" not in p.relative_to(out).parts[:1]}:
        shutil.copy2(HERE / "nmshome.py", d / "nmshome.py")
    # Shipwright (MIT): the two packages the POI step imports, plus the licence
    for pkg in ("nms_procgen", "nms_save"):
        shutil.copytree(sw / pkg, out / "NMS-Shipwright" / pkg, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "test_vectors.json"))
    shutil.copy2(sw / "LICENSE", out / "NMS-Shipwright" / "LICENSE")
    # launchers, docs
    for f in sorted((HERE / "launchers").glob("*")):
        data = f.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\n", "\r\n")
        (out / f.name).write_bytes(data.encode("utf-8"))
    # third-party
    if a.with_mbincompiler:
        for ver in ("mbincompiler-7.07.0-pre1", "mbincompiler-7.04.1-pre3"):
            s = Path("D:/Orca/Temp") / ver
            if s.is_dir():
                shutil.copytree(s, out / "third-party" / ver, ignore=shutil.ignore_patterns("*.log"))
    # runtime
    if not a.no_runtime:
        venv_pkgs = sw / ".venv" / "Lib" / "site-packages"
        copy_runtime(out / "python", venv_pkgs)
        lic = out / "LICENSES"
        lic.mkdir(exist_ok=True)
        shutil.copy2(out / "python" / "LICENSE.txt", lic / "Python-PSF-LICENSE.txt")
        for d in (venv_pkgs).glob("*.dist-info"):
            for lf in list(d.glob("LICENSE*")) + list(d.glob("licenses/*")) + list(d.glob("COPYING*")):
                if re.match(r"(?i)(unicorn|pefile|hgpaktool|lz4|zstandard)-", d.name) and lf.is_file():
                    shutil.copy2(lf, lic / f"{d.name.split('-')[0]}-{lf.name}")
        shutil.copy2(sw / "LICENSE", lic / "NMS-Shipwright-MIT-LICENSE.txt")
    problems = guard(out)
    (out / "MANIFEST.json").write_text(json.dumps(manifest(out), indent=1) + "\n", encoding="utf-8")
    print(f"package: {out}\n  files: {sum(1 for _ in out.rglob('*') if _.is_file())}  rewritten python files: {n_rewritten}")
    if problems:
        print("GUARD FAILED:")
        for p in problems:
            print("  -", p)
        return 1
    print("guard: no machine paths, no executable-memory API, every .py parses")
    return 0


if __name__ == "__main__":
    sys.exit(main())
