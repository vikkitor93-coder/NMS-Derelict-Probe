"""Python vs JS parity for tools/system_names_705.py.  Run: python -I tests/test_system_names_705.py [index/systems.csv.gz]
Compares on atlas-index addresses (glyphs+galaxy) and the known in-game captures.  Needs node for the parity part."""
import csv, gzip, random, shutil, subprocess, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
sys.dont_write_bytecode = True
sys.path.insert(0, str(TOOLS))
import system_names_705 as N  # noqa: E402

INDEX = Path(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else Path("G:/NMS-Work/atlas-clone/index/systems.csv.gz")
sys.argv = sys.argv[:1]
CAPTURES = {"00006D0006606CAB": "Stlepiosc XIX", "0000750006606CAB": "Ruflas-Simly V", "0000790006606CAB": "Gersid XVI",
            "0001550006607CAC": "Uzawan XI", "0001680006607CAC": "Otsues", "0001BF0004E84EFD": "Angoto",
            "0000760006606CAB": "Irchol-Luhimo XVII"}      # last = override (game name, upstream data gives Irchol-Luhomo)


def glyph_to_addr(glyphs, galaxy):
    return f"000{glyphs[1:4]}{int(galaxy):02X}{glyphs[4:]}"


class T(unittest.TestCase):
    def test_captures(self):
        for a, n in CAPTURES.items():
            self.assertEqual(N.name(a), n, a)

    def test_override_only_affects_that_address(self):
        saved = dict(N.OVERRIDES)
        try:
            N.OVERRIDES.clear()
            self.assertEqual(N.name("0000760006606CAB"), "Irchol-Luhomo")   # raw upstream-data result
            self.assertEqual(N.name("0000750006606CAB"), "Ruflas-Simly V")
        finally:
            N.OVERRIDES.update(saved)

    def test_parse_forms(self):
        self.assertEqual(N.name("0000750006606CAB"), N.name(" 00007500:06606cab "))
        self.assertEqual(N.name("zzz"), "")
        self.assertEqual(N.name("0000750006606CAB", 5), "")        # galaxy mismatch
        self.assertEqual(N.name("0000750006606CAB", 0), "Ruflas-Simly V")
        self.assertEqual(N.name("00006606CAB"), "")                 # 11 digits
        self.assertEqual(N.name("050006606CAB"), "")                # glyphs without galaxy

    def test_glyph_form_matches_address_form(self):
        self.assertEqual(N.name("007506606CAB", 0), N.name("0000750006606CAB"))
        self.assertEqual(N.name(glyph_to_addr("007506606CAB", 0)), "Ruflas-Simly V")

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_parity_with_js(self):
        if not INDEX.exists():
            self.skipTest(f"no index at {INDEX}")
        with gzip.open(INDEX, "rt", encoding="utf-8") as fh:
            rows = list(csv.DictReader(l for l in fh if not l.startswith("#")))
        rnd = random.Random(705)
        sample = rnd.sample(rows, min(3000, len(rows)))
        cases = [(glyph_to_addr(r["glyphs"], r["galaxy"]), None) for r in sample[:2000]]
        cases += [(r["glyphs"], int(r["galaxy"])) for r in sample[2000:]]          # 12-digit form
        cases += [(a, None) for a in CAPTURES]
        stdin = "\n".join(a if g is None else f"{a} {g}" for a, g in cases) + "\n"
        js = ROOT / "tools" / "js" / "system_names_705.js"
        p = subprocess.run(["node", str(ROOT / "tests" / "names_js_runner.js"), str(js), str(TOOLS / "system_names_705_data.json.gz")],
                           input=stdin, capture_output=True, text=True, check=True)
        got = p.stdout.split("\n")[:-1]
        self.assertEqual(len(got), len(cases))
        bad = [(c, N.name(*c), j) for c, j in zip(cases, got) if N.name(*c) != j]
        print(f"parity: {len(cases)} cases, {len(bad)} mismatches, {sum(1 for j in got if not j)} empty")
        self.assertEqual(bad[:5], [])
        self.assertEqual(sum(1 for j in got if not j), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
