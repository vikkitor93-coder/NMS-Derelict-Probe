"""Build the atlas's top-100 maps bundle: one gzip file with full viewer maps for the best systems.

  python -I tools/build_top_bundle.py [ATLAS_DIR] [--generated DIR ...] [--no-generate]

Writes <atlas>/views/top100.json.gz = gzip(JSON {"v": 2, "t": piece table, "s": {ADDRESS16: view}}):
  - views: tools/derelict_view.py pack() of each system's derelict.json (rooms, containers, placed pieces, and "x":
    the briefcases and tall lockers, recomputed from the pieces by tools/extra_containers_705.py);
  - piece table: pieces_table() over the scenes those views use (ids are local to this file), with "o": each piece's
    container rotations, so the website draws every container with its game orientation (lying lockers etc.).
The website (viewer/static/model.js unpack + build) draws walls, doors, stairs and fixtures from it.
Systems: the top 100 by crates of tools/build_atlas_index.py (same rank as the scanner) plus the top 100 by frigate
modules (map column 2/3; build_atlas_index.map_rows()), each layout stored once. A layout missing from the generated
folders is made with the fast generator (seconds each) unless --no-generate. Each layout must match its published
atlas row (preset, crates, footlockers, rooms), otherwise nothing is written. Deterministic (gzip mtime 0); an
unchanged bundle is not rewritten.

For the scanner: build_bundle(layouts, piece_index) takes derelict dicts directly (e.g. its stored full layouts).
"""
import gzip
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I leaves the script folder off sys.path
from build_atlas_index import address, map_rows, top  # noqa: E402
from build_atlas_index import systems as atlas_systems  # noqa: E402
from derelict_view import VIEW_FORMAT, pack, pieces_table  # noqa: E402
from extra_containers_705 import extra_containers  # noqa: E402

GENERATED = [Path("D:/Orca/NMS-Derelict-Probe-analysis/emu/fastgen/generated"),
             Path("D:/Orca/NMS-Derelict-Probe-analysis/emu/generated")]
PIECE_INDEX = Path("D:/Orca/NMS-Derelict-Probe-analysis/meshcache/index.json")
FAST_GEN = Path("D:/Orca/NMS-Derelict-Probe-fastgen/fast_generate_705.py")
BUNDLE = Path("views") / "top100.json.gz"


def complete_layouts(layouts, atlas=None, rows=None, generate=True, roots=None):
    """layouts + the layouts of every other system that has a map (the top-modules list), looked up in the generated
    folders or made with the fast generator, each checked with matches(). Uses the atlas that build_atlas_index.build()
    indexed last when atlas/rows are not given (the scanner calls build() right before build_bundle()). Nothing to do
    (layouts returned unchanged) when no atlas is known."""
    import build_atlas_index as bai
    atlas = atlas or bai.LAST.get("atlas")
    rows = rows if rows is not None else bai.LAST.get("rows")
    if atlas is None or rows is None:
        return list(layouts)
    have = {d["address"]: d for d in layouts}
    out = dict(have)
    roots = list(roots or GENERATED)
    for row in bai.map_rows(rows):
        addr = bai.address(row)
        if addr in out:
            continue
        d = find_layout(addr, roots)
        if d is None and generate:
            subprocess.run([sys.executable, "-I", str(FAST_GEN), addr], check=True, capture_output=True, text=True, timeout=1800)
            d = find_layout(addr, roots)
        if d is None:
            raise RuntimeError(f"no layout for {addr} ({row['glyphs']})")
        if not matches(d, row):
            raise RuntimeError(f"{addr}: generated layout does not match its published row; nothing written")
        out[addr] = d
    return list(out.values())


def build_bundle(layouts, piece_index):
    """layouts: derelict.json dicts -> gzip bytes of the bundle (deterministic). Systems of the second map list
    (top by frigate modules) that are not in layouts are added by complete_layouts()."""
    layouts = complete_layouts(layouts)
    # extra loot containers (briefcases, tall lockers; view key "x") are always recomputed from the placed pieces, so
    # stored layouts made before they existed and new ones give the same bytes; the caller's dicts are not changed
    layouts = sorted(({**d, "extra_containers": extra_containers(d)} for d in layouts), key=lambda d: d["address"])
    names = sorted({i["scene_resource"].upper() for d in layouts for i in d["instances"]})
    ids = {n: k for k, n in enumerate(names)}
    doc = {"v": VIEW_FORMAT, "t": pieces_table(piece_index, names), "s": {d["address"]: pack(d, ids) for d in layouts}}
    import build_atlas_index as bai
    rows = bai.LAST.get("rows")
    if rows is not None:   # "k": which top lists each system is in (1 crates, 2 modules, 3 both); region files have no such column
        kinds = bai.map_kinds(rows)
        k = {bai.address(r): kinds[(r["galaxy"], r["glyphs"])] for r in bai.map_rows(rows)}
        doc["k"] = {a: k[a] for a in sorted(k) if a in doc["s"]}
    text = json.dumps(doc, separators=(",", ":"), ensure_ascii=False)
    return gzip.compress(text.encode("utf-8"), compresslevel=9, mtime=0), len(text)


def find_layout(addr, roots):
    for root in roots:
        p = root / addr / "derelict.json"
        if p.exists():
            d = json.loads(p.read_text(encoding="utf-8"))
            if "instances" in d:
                return d
    return None


def matches(d, row):
    kinds = d.get("container_kinds") or {}
    return (d["preset"] == row["preset"] and len(d["rooms"]) == int(row["rooms"])
            and kinds.get("salvage_crate", 0) == int(row["crates"]) and kinds.get("crew_footlocker", 0) == int(row["footlockers"]))


def main():
    args = sys.argv[1:]
    generate = "--no-generate" not in args
    args = [a for a in args if a != "--no-generate"]
    roots = list(GENERATED)
    while "--generated" in args:
        i = args.index("--generated")
        roots.insert(0, Path(args[i + 1]))
        del args[i:i + 2]
    atlas = Path(args[0] if args else "D:/Orca/NMS-Derelict-Atlas")
    all_rows = atlas_systems(atlas)
    best = map_rows(all_rows)
    layouts, made = [], 0
    for row in best:
        addr = address(row)
        d = find_layout(addr, roots)
        if d is None and generate:
            subprocess.run([sys.executable, "-I", str(FAST_GEN), addr], check=True, capture_output=True, text=True, timeout=1800)
            d, made = find_layout(addr, roots), made + 1
        if d is None:
            sys.exit(f"no layout for {addr} ({row['glyphs']}); run without --no-generate")
        if not matches(d, row):
            sys.exit(f"{addr}: generated layout does not match the published atlas row; nothing written")
        layouts.append(d)
    import build_atlas_index as bai
    bai.LAST.update(atlas=atlas, rows=all_rows)
    data, raw = build_bundle(layouts, json.loads(PIECE_INDEX.read_text(encoding="utf-8")))
    dest = atlas / BUNDLE
    dest.parent.mkdir(parents=True, exist_ok=True)
    changed = not dest.exists() or dest.read_bytes() != data
    if changed:
        dest.write_bytes(data)
    print(f"{dest}: {len(layouts)} systems ({made} generated now), {raw / 1024:.1f} KB JSON -> {len(data) / 1024:.1f} KB gzip"
          f"{'' if changed else ' (unchanged)'}")


if __name__ == "__main__":
    main()
