"""Build the atlas's combined system list: every published system in one small gzip file.

  python -I tools/build_atlas_index.py [ATLAS_DIR]      (default D:/Orca/NMS-Derelict-Atlas)

Reads regions/g<GG>/<YY>/<ZZZ>/<REGION>.csv and writes index/systems.csv.gz with the columns the viewer's table
needs: glyphs, galaxy, preset, rooms, crates, footlockers, floors, stairs, hangars, map, briefcases, tall_lockers,
reward_name, reward_class, reward_ambiguous, reward_alt, frigate_modules, frigate_modules_ambiguous,
frigate_module_rooms, frigate_module_ids, frigate_module_alt_ids (empty until computed). map = 1 for the TOP_N best
systems, the ones with a full map in views/top100.json.gz (tools/build_top_bundle.py). Rank: total containers
(crates + footlockers), then crates, then the lower glyph code; the scanner's atlas.py uses the same rule.
Second list (2026-10-24): the MODULE_N systems with the most frigate_modules also have a map (top_modules(): modules
desc, then the same rank as above, so ties are deterministic). map column: 0 none, 1 top crates list, 2 top modules
list only, 3 both lists. Every system with map > 0 is in the bundle, each layout stored once.
room_detail and check stay in the region files, which remain the verified source; the index is a convenience copy
the viewer loads instead of every region file. Deterministic (no timestamps, gzip mtime 0): the same region files
give a byte-identical index, and an unchanged index is not rewritten.
Game build tag (2026-10-22): each region file's "# generator ...; NMS.exe <build> SHA-256 <sha>" header line names the
game build its rows were generated with (a file without one is 7.05 implicitly). When every region shares one build,
the index's first '#' line ends with "; game_build <build> <sha8>" (no column; INDEX_FORMAT stays 5). Only when builds
are mixed does the index get a per-row game_build column (INDEX_FORMAT_MIXED = 6).
"""
import csv
import gzip
import io
import re
import sys
from pathlib import Path

TOP_N = 100
MODULE_N = 100                  # top systems by frigate_modules that also get a map (map column 2 or 3)
COLUMNS = ["glyphs", "galaxy", "preset", "rooms", "crates", "footlockers", "floors", "stairs", "hangars", "map"]
# Extra loot containers (format 3), appended after map so earlier columns keep their place. Copied from the region
# rows when the region file has these columns (scanner side), else empty = not known yet (not zero). They are extra
# columns only: the rank (and map) stays crates + footlockers. See research-output/CONTAINER_TYPES_20261020.md.
EXTRA_COLUMNS = ["briefcases", "tall_lockers"]
REWARD_COLUMNS = ["reward_name", "reward_class", "reward_ambiguous", "reward_alt"]
FRIGATE_COLUMNS = ["frigate_modules", "frigate_modules_ambiguous", "frigate_module_rooms",
                   "frigate_module_ids", "frigate_module_alt_ids"]
INDEX_FORMAT = 5
INDEX_FORMAT_MIXED = 6          # only when region files of different game builds are mixed (per-row game_build column)
BUILD_LINE = re.compile(r"NMS\.exe (\S+) SHA-256 ([0-9A-Fa-f]{64})")
DEFAULT_BUILD = "7.05 13D5060D"  # region files without a build tag were all made by the 7.05 generator
REGION_FILE = re.compile(r"^[0-9A-F]{8}\.csv$")
INDEX = Path("index") / "systems.csv.gz"


def systems(atlas):
    """Every published system: dicts with the region-file columns plus galaxy (int); one row per (galaxy, glyphs)."""
    rows = {}
    for gdir in sorted((atlas / "regions").glob("g[0-9a-f][0-9a-f]")):
        galaxy = int(gdir.name[1:], 16)
        for p in sorted(gdir.rglob("*.csv")):
            if not REGION_FILE.match(p.name):
                continue
            text = p.read_text(encoding="utf-8").splitlines()
            lines = [l for l in text if l and not l.startswith("#")]
            m = next((m for m in (BUILD_LINE.search(l) for l in text if l.startswith("#")) if m), None)
            build_tag = f"{m.group(1)} {m.group(2)[:8].upper()}" if m else DEFAULT_BUILD
            for rec in csv.DictReader(lines):
                rec["glyphs"] = rec["glyphs"].upper()
                rec["galaxy"] = galaxy
                rec["game_build"] = build_tag
                rows[(galaxy, rec["glyphs"])] = rec
    return list(rows.values())


def rank_key(r):
    crates, lockers = int(r["crates"]), int(r["footlockers"])
    return (-(crates + lockers), -crates, r["glyphs"], r["galaxy"])


def top(rows, n=TOP_N):
    return sorted(rows, key=rank_key)[:n]


def modules_of(r):
    try:
        return int(r.get("frigate_modules") or 0)
    except ValueError:
        return 0


def top_modules(rows, n=MODULE_N):
    """The n systems with the most frigate modules; ties by the crate rank (total, crates, glyphs, galaxy)."""
    return sorted((r for r in rows if modules_of(r) > 0), key=lambda r: (-modules_of(r),) + rank_key(r))[:n]


def map_kinds(rows):
    """{(galaxy, glyphs): 1|2|3}: 1 = top crates only, 2 = top modules only, 3 = both."""
    crates = {(r["galaxy"], r["glyphs"]) for r in top(rows)}
    mods = {(r["galaxy"], r["glyphs"]) for r in top_modules(rows)}
    return {k: (1 if k in crates else 0) + (2 if k in mods else 0) for k in crates | mods}


def map_rows(rows):
    """Rows that have a map (either list), in a stable order: crates list first, then the modules-only ones."""
    kinds = map_kinds(rows)
    return [r for r in sorted(rows, key=rank_key) if (r["galaxy"], r["glyphs"]) in kinds and kinds[(r["galaxy"], r["glyphs"])] & 1] +            [r for r in top_modules(rows) if kinds[(r["galaxy"], r["glyphs"])] == 2]


LAST = {}   # set by build(): the atlas folder and rows just indexed, so build_top_bundle can complete the second list


def address(r):
    """glyphs P SSS YY ZZZ XXX + galaxy -> universe address 000 SSS GG YY ZZZ XXX."""
    g = r["glyphs"]
    return f"000{g[1:4]}{r['galaxy']:02X}{g[4:]}"


def build(atlas):
    rows = systems(atlas)
    kinds = map_kinds(rows)
    LAST.clear()
    LAST.update(atlas=Path(atlas), rows=rows)
    builds = sorted({r.get("game_build") or DEFAULT_BUILD for r in rows})
    mixed = len(builds) > 1
    tag = (f"; game_build mixed ({', '.join(builds)}): see the game_build column" if mixed
           else f"; game_build {builds[0] if builds else DEFAULT_BUILD}")
    out = io.StringIO(newline="")
    out.write(f"# nms-derelict-atlas index format {INDEX_FORMAT_MIXED if mixed else INDEX_FORMAT}: {len(rows)} systems; "
              f"map 1/2/3 = top {TOP_N} by crates / top {MODULE_N} by frigate modules / both (full maps in views/top100.json.gz); built from regions/ (the verified source); empty "
              f"optional fields = not computed yet{tag}\n")
    w = csv.writer(out, lineterminator="\n")
    w.writerow(COLUMNS + EXTRA_COLUMNS + REWARD_COLUMNS + FRIGATE_COLUMNS + (["game_build"] if mixed else []))
    for r in sorted(rows, key=lambda r: (r["galaxy"], r["glyphs"])):
        w.writerow([r["glyphs"], r["galaxy"], *(r[c] for c in COLUMNS[2:-1]), kinds.get((r["galaxy"], r["glyphs"]), 0),
                    *((r.get(c) or "") for c in EXTRA_COLUMNS + REWARD_COLUMNS + FRIGATE_COLUMNS),
                    *([r.get("game_build") or DEFAULT_BUILD] if mixed else [])])
    data = gzip.compress(out.getvalue().encode("utf-8"), compresslevel=9, mtime=0)
    dest = atlas / INDEX
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists() or dest.read_bytes() != data:
        dest.write_bytes(data)
    return dest, len(rows), len(data)


if __name__ == "__main__":
    dest, n, size = build(Path(sys.argv[1] if len(sys.argv) > 1 else "D:/Orca/NMS-Derelict-Atlas"))
    print(f"{dest}: {n} systems, {size / 1024:.1f} KB")
