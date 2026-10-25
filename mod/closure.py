"""Which of the project's own .py files does the minimap need? (static import closure, stdlib only)

    python -I mod/closure.py            # print the closure of the minimap entry points
Used by build_package.py; run by hand to see what a change pulled in.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEARCH = [ROOT / "minimap", ROOT / "tools"]
ENTRY = ["minimap/overlay.py", "minimap/core.py", "minimap/check_update.py", "minimap/geomrender.py", "minimap/lifecycle.py",
         "minimap/selftest_autofind_live.py", "tools/space_poi_position_705.py", "tools/build_piece_meshes_705.py",
         "tools/live_position_705.py", "tools/nms_find_addresses_705.py"]


def local_module(name: str) -> Path | None:
    for d in SEARCH:
        p = d / (name.split(".")[0] + ".py")
        if p.is_file():
            return p
    return None


def imports_of(path: Path) -> set[str]:
    out: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
        if isinstance(node, ast.Import):
            out.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            out.add(node.module)
    return out


def closure(entries: list[str] = ENTRY) -> tuple[list[Path], dict[str, set[str]]]:
    todo = [ROOT / e for e in entries]
    seen: dict[Path, None] = {}
    external: dict[str, set[str]] = {}
    while todo:
        p = todo.pop()
        if p in seen or not p.is_file():
            continue
        seen[p] = None
        for name in imports_of(p):
            local = local_module(name)
            if local:
                todo.append(local)
            else:
                external.setdefault(name.split(".")[0], set()).add(p.name)
    return sorted(seen), external


if __name__ == "__main__":
    files, ext = closure()
    for f in files:
        print(f.relative_to(ROOT).as_posix())
    std = set(sys.stdlib_module_names)
    print("\nthird-party / non-stdlib imports:")
    for name, who in sorted(ext.items()):
        if name not in std:
            print(f"  {name}: {', '.join(sorted(who))}")
