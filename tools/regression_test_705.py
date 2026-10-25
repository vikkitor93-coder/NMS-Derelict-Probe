"""One-command regression test for the NMS 7.05 derelict generator, viewer packing and atlas tools.

  python -I tools/regression_test_705.py            fast mode (about 1-3 minutes)
  python -I tools/regression_test_705.py --full     also compares the fast generator with the slow Unicorn tool (few more minutes)
  python -I tools/regression_test_705.py --keep     keep the temporary folder (printed at the end)

Prints one PASS / FAIL / SKIP line per check and a summary. Exit code 0 = no FAIL, 1 = at least one FAIL.
Nothing real is overwritten: every generated layout, view and atlas copy goes to a temporary folder.
Never touches the game. The atlas clone is only read (copied).

Checks (letters as in STATUS.md / TESTING.md):
  a  five live-validated derelicts regenerate with the known preset/rooms/crates/footlockers (+ seeds, instances, fixture replay)
  b  fast generator == main Unicorn tool (--full only)
  c  derelict_view.py packing: Python == JS (model.js) on the layouts from (a)
  d  node build_views.js --check
  e  atlas index + top-100 bundle: deterministic, frigate fields kept (e1a), equal to the published files (e2, e5), top-100 set (e3, e6)
  f  viewer server API (only if the viewer is running)
  g  glyphs <-> address round trips
  h  system names: h1 upstream vectors, h2 address/glyph forms, h3 Python == JS, h4 viewer copies == tools copies,
     h5 NMS Almanac sample

REBUILT 2026-10-25 (recovery stage 2, task A2) from the Oct-20 recovered copy + the logged later edits
(mined-edits/_unverified) + the check descriptions in STATUS.md.  Because the game data / fast generator inputs, the
vector files and the viewer may be unavailable on the machine, every check that needs missing input reports SKIP with the
reason instead of FAIL (this is new; the original reported FAIL for missing data).  A SKIP is not a PASS.
Environment: NMS_ATLAS=<atlas clone> overrides the atlas location; TMPDIR/TEMP choose where the temporary folder goes.
"""
import concurrent.futures as cf
import csv
import gzip
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

PROBE = Path(__file__).resolve().parent.parent
TOOLS = PROBE / "tools"
FASTGEN = Path("D:/Orca/NMS-Derelict-Probe-fastgen")
FAST_GEN = FASTGEN / "fast_generate_705.py"
ANALYSIS = Path("D:/Orca/NMS-Derelict-Probe-analysis")
GENERATED = [ANALYSIS / "emu" / "fastgen" / "generated", ANALYSIS / "emu" / "generated"]
ATLAS = Path(os.environ["NMS_ATLAS"]) if os.environ.get("NMS_ATLAS") else next(
    (p for p in (Path("D:/Orca/NMS-Derelict-Atlas"), Path("D:/atlas-clone")) if (p / "regions").exists()), Path("D:/Orca/NMS-Derelict-Atlas"))
SERVER = "http://127.0.0.1:8765"
# Generator inputs that fast_generate_705.py needs (same files the atlas fingerprints, see app/atlas.py INPUT_FILES).
GEN_INPUTS = [ANALYSIS / "emu" / "asset_source_rows.bin",
              Path("D:/Orca/Temp/generatedbase-table-705-mbc707/generatedbasetemplatestable.mbin"),
              PROBE / "research-output" / "exact705-dungeon-inputs-20261019" / "metadata" / "reality" / "tables" / "freighterdungeonstable.mbin"]

# Live-validated derelicts (STATUS.md, research-output/GENERATOR_VALIDATION_VS_LIVE_20261020.md, BLIND_PREDICTION_*).
# address -> (preset, rooms, crates, footlockers, extra checks)
LIVE = {
    "00003B0006606CAA": ("CARGO_BUGS", 11, 17, 6, {"instances": 145, "fixture": True}),
    "0000750006606CAB": ("CARGO_BUGS", 9, 18, 5, {}),
    "0000320006606CAA": ("CARGO_FLOATERS", 9, 29, 18, {}),
    "0002250006607CAA": ("CARGO_FLOATERS", 12, 43, 31, {
        "seed": "0A94CF6386B356A4", "instances": 219,
        "rooms_cf": [(15, 7), (0, 0), (9, 5), (0, 0), (3, 6), (1, 0), (0, 4), (5, 0), (2, 0), (6, 3), (0, 0), (2, 6)],
        "templates": ["R_FLO_CARG", "B_FLO_BARR", "R_FLO_CARG", "B_FLO_BARR", "R_FLO_BARR", "B_FLO_BARR",
                      "R_S_FLO_BARR", "R_FLO_CARG", "B_FLO_CARG", "R_FLO_CARG", "B_FLO_BARR", "R_END"]}),
    "00002F0006607CAA": ("CARGO_FLOATERS", 12, 47, 19, {"seed": "09875D108A52CD96", "room0": ("R_FLO_CARG", 18, 2)}),
}
KNOWN_GLYPHS = {"122506607CAA": "0002250006607CAA", "002F06607CAA": "00002F0006607CAA", "003B06606CAA": "00003B0006606CAA"}

results = []


def report(name, ok, note="", skip=False):
    tag = "SKIP" if skip else ("PASS" if ok else "FAIL")
    results.append((tag, name))
    line = f"{tag}  {name}" + (f"  -- {note}" if note else "")
    print(line.encode("ascii", "replace").decode(), flush=True)


def run(cmd, timeout=900, cwd=None):
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, timeout=timeout, cwd=cwd,
                          encoding="utf-8", errors="replace")


def tail(p):
    return (p.stdout + p.stderr).strip().splitlines()[-3:]


def missing(paths):
    return [str(p) for p in paths if not Path(p).exists()]


def gen_unavailable():
    """Reason string when the fast generator cannot run here (missing inputs), else ''."""
    gone = missing([FAST_GEN, *GEN_INPUTS])
    return ("generator inputs missing: " + ", ".join(Path(g).name for g in gone)) if gone else ""


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def kinds(d):
    k = d.get("container_kinds") or {}
    return k.get("salvage_crate", 0), k.get("crew_footlocker", 0)


# ---------------------------------------------------------------- a) live-validated regeneration
def gen_one(addr, tmp):
    out = tmp / "gen" / addr
    cmd = [sys.executable, "-I", FAST_GEN, addr, "--out", out]
    if LIVE[addr][4].get("fixture"):
        cmd.append("--fixture-check")
    p = run(cmd, timeout=1200)
    return addr, p, out


def check_live(tmp):
    why = gen_unavailable()
    if why:
        for addr, (preset, rooms, crates, lockers, _) in LIVE.items():
            report(f"a) {addr} {preset} {rooms} rooms {crates} crates {lockers} footlockers", True, why, skip=True)
        return
    with cf.ThreadPoolExecutor(max_workers=5) as ex:
        runs = list(ex.map(lambda a: gen_one(a, tmp), LIVE))
    for addr, p, out in runs:
        preset, rooms, crates, lockers, extra = LIVE[addr]
        name = f"a) {addr} {preset} {rooms} rooms {crates} crates {lockers} footlockers"
        f = out / "derelict.json"
        if p.returncode != 0 or not f.exists():
            report(name, False, f"generator failed rc={p.returncode}: {tail(p)}")
            continue
        d = load(f)
        problems = []
        if d["preset"] != preset:
            problems.append(f"preset {d['preset']}")
        if len(d["rooms"]) != rooms:
            problems.append(f"rooms {len(d['rooms'])}")
        if kinds(d) != (crates, lockers):
            problems.append(f"containers {kinds(d)}")
        if "instances" in extra and len(d["instances"]) != extra["instances"]:
            problems.append(f"instances {len(d['instances'])} != {extra['instances']}")
        if "seed" in extra and d["seed"].upper() != extra["seed"]:
            problems.append(f"seed {d['seed']}")
        if extra.get("fixture") and "fixture check: {\"pass\": true" not in p.stdout:
            problems.append("fixture check (145/145 instances, 23/23 containers vs replay) not passed")
        per_room = {}
        for c in d["containers"]:
            k = per_room.setdefault(c["room_index"], [0, 0])
            k[0 if c["container_kind"] == "salvage_crate" else 1] += 1
        if "rooms_cf" in extra:
            got = [tuple(per_room.get(i, [0, 0])) for i in range(len(d["rooms"]))]
            if got != extra["rooms_cf"]:
                problems.append(f"per-room {got}")
            if [r["template_name"] for r in d["rooms"]] != extra["templates"]:
                problems.append("room templates differ")
        if "room0" in extra:
            t, c0, l0 = extra["room0"]
            got = (d["rooms"][0]["template_name"], *per_room.get(0, [0, 0]))
            if got != (t, c0, l0):
                problems.append(f"room 0 {got}")
        note = ("; ".join(problems)) or f"engine {d.get('writer_engine')}, {d.get('fast_total_seconds', 0):.1f}s"
        report(name, not problems, note)


# ---------------------------------------------------------------- b) fast == main Unicorn tool (--full)
def check_fast_vs_main(tmp):
    why = gen_unavailable()
    if why:
        report("b) fast generator == main Unicorn tool on 0000750006606CAB", True, why, skip=True)
        return
    ignore = {"emulator_seconds", "wall_seconds", "writer_engine", "fast_total_seconds", "notes"}
    for addr in ["0000750006606CAB"]:
        name = f"b) fast generator == main Unicorn tool on {addr}"
        out = tmp / "main" / addr
        p = run([sys.executable, "-I", TOOLS / "generate_derelict_705.py", addr, "--out", out], timeout=1800)
        f_main, f_fast = out / "derelict.json", tmp / "gen" / addr / "derelict.json"
        if not f_fast.exists():  # --full without (a) result for this address
            q = run([sys.executable, "-I", FAST_GEN, addr, "--out", tmp / "gen" / addr])
        if p.returncode != 0 or not f_main.exists():
            report(name, False, f"main tool failed rc={p.returncode}: {tail(p)}")
            continue
        a, b = load(f_main), load(f_fast)
        diff = sorted(k for k in set(a) | set(b) if k not in ignore and a.get(k) != b.get(k))
        report(name, not diff, f"differing keys: {diff}" if diff else "derelict.json identical (timing/engine fields ignored)")


# ---------------------------------------------------------------- c) Python packing == JS packing
def check_verify(tmp):
    addrs = list(LIVE)[:3]
    name = f"c) derelict_view.py --verify (Python == JS packing) on {len(addrs)} addresses"
    if missing([tmp / "gen" / a / "derelict.json" for a in addrs]):
        report(name, True, "layouts from check (a) not available: " + (gen_unavailable() or "check a failed"), skip=True)
        return
    import contextlib
    import io
    sys.path.insert(0, str(TOOLS))
    import derelict_view  # noqa
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            ok = derelict_view.verify(addrs, tmp / "gen")  # the layouts generated in (a), not the real folders
    except Exception as e:  # noqa
        report(name, False, f"{type(e).__name__}: {str(e)[:200]}")
        return
    report(name, ok, buf.getvalue().strip())


# ---------------------------------------------------------------- d) build_views.js --check
def check_build_views(tmp):
    addrs = list(LIVE)[:3]
    name = f"d) node build_views.js --check {len(addrs)} addresses, mismatches 0"
    if missing([tmp / "gen" / a / "derelict.json" for a in addrs]):
        report(name, True, "layouts from check (a) not available: " + (gen_unavailable() or "check a failed"), skip=True)
        return
    out = tmp / "views_out"
    p = run(["node", TOOLS / "build_views.js", "--out", out, "--check", "--generated", tmp / "gen", *addrs])
    txt = p.stdout + p.stderr
    last = [l for l in txt.splitlines() if "mismatch" in l.lower()]
    ok = p.returncode == 0 and bool(last) and all(
        "mismatches 0" in l.lower() or "mismatches: 0" in l.lower() or "0 mismatch" in l.lower() for l in last)
    report(name, ok, (last[-1] if last else f"no mismatch line; rc={p.returncode}; {tail(p)}"))


# ---------------------------------------------------------------- e) index + top bundle determinism on an atlas copy
def check_atlas(tmp):
    sys.path.insert(0, str(TOOLS))
    import build_atlas_index as bai  # noqa
    copy = tmp / "atlas_copy"
    published = ATLAS / "index" / "systems.csv.gz"
    pub_bundle = ATLAS / "views" / "top100.json.gz"
    if not (ATLAS / "regions").exists() or not published.exists():
        report("e) atlas index", True, f"no atlas clone with regions/ and index/systems.csv.gz at {ATLAS} (set NMS_ATLAS)", skip=True)
        return
    shutil.copytree(ATLAS / "regions", copy / "regions")
    shutil.copyfile(published, tmp / "published_index.csv.gz")
    if pub_bundle.exists():
        shutil.copyfile(pub_bundle, tmp / "published_top100.json.gz")
    # index twice
    dest, n, _ = bai.build(copy)
    first = dest.read_bytes()
    dest.unlink()
    dest, n2, _ = bai.build(copy)
    second = dest.read_bytes()
    report("e1) build_atlas_index: two builds byte-identical", first == second, f"{n} systems")
    rebuilt_rows = list(csv.DictReader(l for l in gzip.decompress(first).decode("utf-8").splitlines() if not l.startswith("#")))
    frigate_fields = {"frigate_modules", "frigate_modules_ambiguous", "frigate_module_rooms", "frigate_module_ids", "frigate_module_alt_ids"}
    frigate_header_ok = bool(rebuilt_rows) and frigate_fields.issubset(rebuilt_rows[0])
    source_by_key = {(int(r["galaxy"]), r["glyphs"]): r for r in bai.systems(copy)}
    frigate_source_match = frigate_header_ok and len(source_by_key) == len(rebuilt_rows)
    if frigate_source_match:
        for row in rebuilt_rows:
            source = source_by_key.get((int(row["galaxy"]), row["glyphs"]))
            if source is None or any((row[k] or "") != (source.get(k) or "") for k in frigate_fields):
                frigate_source_match = False
                break
    blank_module_rows = sum(not row.get("frigate_modules") for row in rebuilt_rows)
    frigate_ok = frigate_header_ok and frigate_source_match
    report("e1a) frigate module fields preserved; uncomputed values stay blank", frigate_ok,
           f"format {bai.INDEX_FORMAT}; {len(rebuilt_rows)} rows; {blank_module_rows} rows remain uncomputed" if frigate_ok else "missing fields or rebuilt values differ from source regions")

    def map1(data):
        rows = list(csv.DictReader(l for l in gzip.decompress(data).decode("utf-8").splitlines() if not l.startswith("#")))
        return {(r["galaxy"], r["glyphs"]) for r in rows if r["map"] in ("1", "3")}, len(rows)
    pub = (tmp / "published_index.csv.gz").read_bytes()
    pub_top, pub_n = map1(pub)
    new_top, new_n = map1(first)
    same_idx = pub == first
    if same_idx:
        idx_detail = ""
    else:
        pub_lines = gzip.decompress(pub).decode("utf-8").splitlines()
        new_lines = gzip.decompress(first).decode("utf-8").splitlines()
        if pub_lines[1:] == new_lines[1:]:
            idx_detail = f"{pub_n} systems; CSV body identical; header differs: published={pub_lines[0]!r}, rebuilt={new_lines[0]!r}"
        else:
            idx_detail = f"published {pub_n} systems, rebuilt {new_n}; CSV body differs"
    report("e2) rebuilt index == published index/systems.csv.gz", same_idx, idx_detail)
    report("e3) top-100 set (map=1 or 3 rows) equals the published index", pub_top == new_top and len(new_top) == 100,
           f"{len(new_top)} rebuilt, {len(pub_top)} published, {len(pub_top ^ new_top)} differ")

    # top bundle: layouts for the top 100 from the real folders, else generated here (parallel); never into real folders
    import build_top_bundle as btb
    rows = bai.top(bai.systems(copy))
    need = [bai.address(dict(r, galaxy=int(r['galaxy']))) for r in rows if btb.find_layout(bai.address(dict(r, galaxy=int(r['galaxy']))), btb.GENERATED) is None]
    if need and gen_unavailable():
        why = f"{len(need)} of the top-100 layouts are not in the generated folders and cannot be generated: {gen_unavailable()}"
        for nm in ("e4) build_top_bundle on the copy", "e5) rebuilt top100.json.gz == published views/top100.json.gz",
                   "e6) bundle holds exactly the 100 top systems"):
            report(nm, True, why, skip=True)
        return
    gen_root = tmp / "top_gen"
    if need:
        with cf.ThreadPoolExecutor(max_workers=8) as ex:
            list(ex.map(lambda a: run([sys.executable, "-I", FAST_GEN, a, "--out", gen_root / a], timeout=1200), need))
    argv = [sys.executable, "-I", TOOLS / "build_top_bundle.py", copy, "--generated", gen_root, "--no-generate"]
    p1 = run(argv)
    b = copy / "views" / "top100.json.gz"
    if p1.returncode != 0 or not b.exists():
        report("e4) build_top_bundle on the copy", False, f"rc={p1.returncode}: {tail(p1)}")
        return
    one = b.read_bytes()
    b.unlink()
    p2 = run(argv)
    two = b.read_bytes() if b.exists() else b""
    report("e4) build_top_bundle: two builds byte-identical, every layout matches its atlas row", one == two and p2.returncode == 0,
           f"{len(need)} layouts generated here, {len(one) / 1024:.1f} KB")
    pubb = tmp / "published_top100.json.gz"
    if pubb.exists():
        report("e5) rebuilt top100.json.gz == published views/top100.json.gz", pubb.read_bytes() == one,
               "" if pubb.read_bytes() == one else "differs (a published bundle built before newer scans, or a real change)")
    s = set(json.loads(gzip.decompress(one))["s"])
    want = {bai.address(dict(r, galaxy=int(r['galaxy']))) for r in rows}
    report("e6) bundle holds exactly the 100 top systems", s == want, f"{len(s)} in bundle")


# ---------------------------------------------------------------- f) viewer server API
def get(path, timeout=10):
    with urllib.request.urlopen(SERVER + path, timeout=timeout) as r:
        return r.status, r.read()


def check_server():
    try:
        get("/api/regions")
    except Exception as e:  # noqa
        report("f) viewer server API", True, f"viewer not running at {SERVER} ({type(e).__name__}); start tools/Derelict-Viewer.cmd", skip=True)
        return
    try:
        st, body = get("/api/regions")
        regs = json.loads(body)
        report("f1) GET /api/regions", st == 200 and isinstance(regs, list) and len(regs) > 0, f"{len(regs)} regions")
        addr = next((a for a in LIVE if any((g / a / "derelict.json").exists() for g in GENERATED)), None)
        if addr:
            st, body = get(f"/api/derelict/{addr}")
            d = json.loads(body)
            ok = st == 200 and d.get("address") == addr and d["preset"] == LIVE[addr][0] and len(d["rooms"]) == LIVE[addr][1]
            report(f"f2) GET /api/derelict/{addr}", ok, f"{d.get('preset')} {len(d.get('rooms', []))} rooms")
        else:
            report("f2) GET /api/derelict/<addr>", True, "none of the live addresses is generated yet", skip=True)
        try:
            get("/api/derelict/FFFFFFFFFFFFFFFF")
            report("f3) unknown derelict returns 404", False, "got 200")
        except urllib.error.HTTPError as e:
            report("f3) unknown derelict returns 404", e.code == 404, f"HTTP {e.code}")
        st, body = get("/model.js")
        report("f4) GET /model.js", st == 200 and b"pack" in body and len(body) > 1000, f"{len(body)} bytes")
    except Exception as e:  # noqa
        report("f) viewer server API", False, f"{type(e).__name__}: {e}")


# ---------------------------------------------------------------- g) glyph <-> address
def check_glyphs():
    sys.path.insert(0, str(TOOLS))
    sys.path.insert(0, str(FASTGEN))
    import build_atlas_index as bai  # noqa
    import generate_derelict_705 as gd  # noqa
    if not hasattr(gd, "glyphs_to_address"):
        report("g) glyphs -> address", True, "tools/generate_derelict_705.py has no glyphs_to_address (stale copy: the Oct-20 version; "
               "the logged later edit is in mined-edits/_unverified)", skip=True)
        return

    def inv(addr):  # address -> glyph code with planet digit 1 (any value is ignored)
        return "1" + addr[3:6] + addr[8:10] + addr[10:13] + addr[13:16]

    bad = []
    for g, a in KNOWN_GLYPHS.items():
        if gd.glyphs_to_address(g) != a:
            bad.append((g, a, gd.glyphs_to_address(g)))
    rnd = random.Random(705)
    for _ in range(2000):
        g = "".join(rnd.choice("0123456789ABCDEF") for _ in range(12))
        gal = rnd.randrange(256)
        a = gd.glyphs_to_address(g, gal)
        b = bai.address({"glyphs": g, "galaxy": gal})
        c = f"000{g[1:4]}{gal:02X}{g[4:6]}{g[6:9]}{g[9:12]}"  # viewer/server.py formula
        if not (a == b == c) or len(a) != 16 or a[:3] != "000" or int(a[6:8], 16) != gal or inv(a)[1:] != g[1:]:
            bad.append((g, gal, a, b, c))
            break
    report("g1) glyphs -> address: known codes + 2000 random round trips, tool == index builder == viewer formula", not bad, str(bad[:1]) if bad else "")
    # every published row maps to an address whose decoded fields give the same row back
    if not (ATLAS / "index" / "systems.csv.gz").exists():
        report("g2) every published atlas row round-trips glyphs -> address -> glyphs", True, f"no index at {ATLAS}", skip=True)
        rows = None
    else:
        rows = list(csv.DictReader(l for l in gzip.decompress((ATLAS / "index" / "systems.csv.gz").read_bytes()).decode().splitlines()
                                   if not l.startswith("#")))
    bad = [] if rows is None else [r["glyphs"] for r in rows if inv(bai.address(dict(r, galaxy=int(r['galaxy']))))[1:] != r["glyphs"][1:] or int(bai.address(dict(r, galaxy=int(r['galaxy'])))[6:8], 16) != int(r["galaxy"])]
    if rows is not None:
        report("g2) every published atlas row round-trips glyphs -> address -> glyphs", not bad, f"{len(rows)} rows" + (f", bad {bad[:3]}" if bad else ""))
    try:
        gd.glyphs_to_address("12345")
        report("g3) bad glyph code is rejected", False, "accepted a 5-digit code")
    except SystemExit:
        report("g3) bad glyph code is rejected", True)


# ---------------------------------------------------------------- h) system names (Python port + JS twin)
def check_names():
    sys.path.insert(0, str(TOOLS))
    import system_names_705 as sn  # noqa
    vec_file = TOOLS / "system_names_705_vectors.json"
    vec = json.loads(vec_file.read_text(encoding="utf-8"))["vectors"] if vec_file.exists() else []
    if vec:
        bad = [(n, c, sn.name(c, g)) for n, c, g in vec if sn.name(c, g) != n]
        report("h1) system names: Python port == %d upstream vectors (in-game names, nms_namegen)" % len(vec), not bad, str(bad[:2]) if bad else "")
    else:
        report("h1) system names: Python port == upstream vectors (nms_namegen)", True, f"{vec_file.name} missing (562 AGT + 6 unit-test vectors "
               "from hadsh/nms_namegen test/fixtures are not recoverable here)", skip=True)
    same = sn.name("03E9F3545C3E", 0) == sn.name("0003E900F3545C3E") == "Abarof-Dulin"
    report("h2) system names: address16 and glyph forms agree (Abarof-Dulin)", same, sn.name("03E9F3545C3E", 0))
    index = ATLAS / "index" / "systems.csv.gz"
    if not shutil.which("node") or not index.exists():
        report("h3) system names: JS twin == Python on 300 random atlas addresses + 100 vectors", True,
               "node not installed" if not shutil.which("node") else f"no atlas index at {index}", skip=True)
    else:
        rows = list(csv.DictReader(l for l in gzip.decompress(index.read_bytes()).decode().splitlines()
                                   if not l.startswith("#")))
        rnd = random.Random(7050)
        cases = [[f"000{r['glyphs'][1:4]}{int(r['galaxy']):02X}{r['glyphs'][4:]}", None] for r in rnd.sample(rows, 300)]
        cases += [[c, g] for _, c, g in vec[:100]]
        exp = [sn.name(a, g) for a, g in cases]
        empty = [a for (a, g), e in zip(cases, exp) if not e]
        f = Path(tempfile.gettempdir()) / "nms_names_cases.json"
        f.write_text(json.dumps({"cases": cases, "exp": exp}), encoding="utf-8")
        r = run(["node", TOOLS / "system_names_705_parity.js", f], timeout=120)
        f.unlink(missing_ok=True)
        report("h3) system names: JS twin == Python on 300 random atlas addresses + 100 vectors, none empty"
               if vec else "h3) system names: JS twin == Python on 300 random atlas addresses (no vectors), none empty",
               r.returncode == 0 and not empty, (r.stdout + r.stderr).strip()[:200])
    sample_file = TOOLS / "system_names_almanac_sample.json"
    if sample_file.exists():
        sm = json.loads(sample_file.read_text(encoding="utf-8"))["systems"]
        bad5 = [(x["glyphs"], sn.name(x["glyphs"], x["galaxy"]), x["almanac"]) for x in sm if sn.name(x["glyphs"], x["galaxy"]) != x["almanac"]]
        report("h5) system names: Python port == NMS Almanac names for the %d-system sample (incl. suffix)" % len(sm), not bad5, str(bad5[:2]) if bad5 else "")
    else:
        report("h5) system names: Python port == NMS Almanac names for the 20-system sample", True,
               f"{sample_file.name} missing (raw Almanac answers were in D:/Orca/Temp/claude/namecheck-20261024, not recovered)", skip=True)
    st = PROBE / "viewer" / "static"
    if missing([st / "names.js", st / "names-data.json.gz"]):
        report("h4) viewer copies of the names module/data == tools copies; published site has them", True,
               "viewer/static/names.js or names-data.json.gz missing in this tree", skip=True)
    else:
        same_files = ((st / "names.js").read_bytes() == (TOOLS / "js" / "system_names_705.js").read_bytes()
                      and (st / "names-data.json.gz").read_bytes() == (TOOLS / "system_names_705_data.json.gz").read_bytes())
        pub = ATLAS / "names.js"
        report("h4) viewer copies of the names module/data == tools copies; published site has them",
               same_files and (not pub.exists() or pub.read_bytes() == (st / "names.js").read_bytes()), "" if same_files else "static copy differs")


def main():
    full = "--full" in sys.argv
    keep = "--keep" in sys.argv
    t0 = time.time()
    tmp = Path(tempfile.mkdtemp(prefix="nms_regression_"))
    print(f"NMS 7.05 derelict regression test ({'full' if full else 'fast'} mode), temp folder {tmp}\n", flush=True)
    steps = [("a", lambda: check_live(tmp)), ("c", lambda: check_verify(tmp)), ("d", lambda: check_build_views(tmp)),
             ("e", lambda: check_atlas(tmp)), ("f", check_server), ("g", check_glyphs), ("h", check_names)]
    if full:
        steps.insert(1, ("b", lambda: check_fast_vs_main(tmp)))
    else:
        report("b) fast generator == main Unicorn tool", True, "only with --full", skip=True)
    for key, fn in steps:
        try:
            fn()
        except Exception as e:  # noqa
            import traceback
            report(f"{key}) check crashed", False, f"{type(e).__name__}: {e}")
            traceback.print_exc()
    n = {t: sum(1 for r in results if r[0] == t) for t in ("PASS", "FAIL", "SKIP")}
    print(f"\n{n['PASS']} passed, {n['FAIL']} failed, {n['SKIP']} skipped in {time.time() - t0:.0f}s")
    if n["FAIL"]:
        print("FAILED: " + "; ".join(r[1] for r in results if r[0] == "FAIL"))
    if keep:
        print(f"temp folder kept: {tmp}")
    else:
        shutil.rmtree(tmp, ignore_errors=True)
    sys.exit(1 if n["FAIL"] else 0)


if __name__ == "__main__":
    main()
