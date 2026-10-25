"""Synthetic-data test for tools/publish_end_reward_cache_705.py.  Run: python -I tests/test_publish_end_reward_cache_705.py"""
import contextlib, sys, tempfile, unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
import publish_end_reward_cache_705 as P  # noqa: E402

HEAD = "address,reward_name,reward_class,reward_ambiguous,reward_alt\n"
A1, A2 = "0000750006606CAB", "00003B0006606CAA"


def write(text, tmp, name="rewards.csv"):
    p = Path(tmp) / name
    p.write_bytes(text.encode())
    return p


class Fake:
    def __init__(self):
        self.calls, self.atlas = [], type("A", (), {"path": Path(".")})()

    def _backup_reward_publish(self, cache):
        self.calls.append(("backup", Path(cache)))

    def _net(self, what, fn, *a, **kw):
        return fn(*a, **kw)

    def sync_rewards_from_cache(self, cache, publish=False):
        self.calls.append(("sync", Path(cache), publish))
        return {"cache_rows": 2, "imported": 2, "regions_pending": 1, "published": 1 if publish else 0}


class FakeAtlas:
    events = []

    @staticmethod
    @contextlib.contextmanager
    def repo_lock(path):
        FakeAtlas.events.append("lock")
        yield
        FakeAtlas.events.append("unlock")


class T(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.tmp = self.td.name

    def tearDown(self):
        self.td.cleanup()

    def test_load_ok_and_partial_last_line_ignored(self):
        p = write(HEAD + f"{A1},C-Class Reactor,C,0,\n{A2},Salvaged Fleet Beacon,A,1,Salvaged Fleet Fuel Unit A|X B\n"
                  f"0000320006606CAA,Half Writ", self.tmp)
        rows = P.load_cache(p)
        self.assertEqual(rows, {A1: ("C-Class Reactor", "C", "0", ""),
                                A2: ("Salvaged Fleet Beacon", "A", "1", "Salvaged Fleet Fuel Unit A|X B")})

    def test_rejects(self):
        for text in (HEAD.replace("reward_alt", "x") + f"{A1},n,C,0,\n",         # columns
                     HEAD + "123,n,C,0,\n",                                        # address
                     HEAD + f"{A1.lower()},n,C,0,\n",                              # lower case
                     HEAD + f"{A1},n,Z,0,\n", HEAD + f"{A1},n,C,2,\n", HEAD + f"{A1},,C,0,\n",
                     HEAD + f"{A1},n,C,0,\n{A1},n,B,0,\n",                          # conflict
                     "no newline at all"):
            with self.subTest(text=text[:60]):
                with self.assertRaises(ValueError):
                    P.load_cache(write(text, self.tmp))

    def test_header_plus_partial_row_is_empty(self):
        self.assertEqual(P.load_cache(write(HEAD + f"{A1},n,C,0", self.tmp)), {})

    def test_duplicate_identical_ok(self):
        self.assertEqual(len(P.load_cache(write(HEAD + f"{A1},n,S,0,\n{A1},n,S,0,\n", self.tmp))), 1)

    def test_publish_order_and_lock(self):
        p = write(HEAD + f"{A1},n,S,0,\n", self.tmp)
        f = Fake()
        r = P.publish(p, f, FakeAtlas)
        self.assertEqual([c[0] for c in f.calls], ["backup", "sync"])
        self.assertTrue(f.calls[1][2])
        self.assertEqual(FakeAtlas.events[-2:], ["lock", "unlock"])
        self.assertEqual(r["published"], 1)
        self.assertEqual(r["validated_rows"], 1)
        f = Fake()
        self.assertEqual(P.publish(p, f, FakeAtlas, do_publish=False)["published"], 0)

    def test_invalid_cache_touches_nothing(self):
        f = Fake()
        with self.assertRaises(ValueError):
            P.publish(write(HEAD + f"{A1},n,Q,0,\n", self.tmp), f, FakeAtlas)
        self.assertEqual(f.calls, [])

    def test_missing_cache(self):
        f = Fake()
        self.assertEqual(P.publish(Path(self.tmp) / "none.csv", f, FakeAtlas)["cache_rows"], 0)
        self.assertEqual(f.calls, [])

    def test_snapshot(self):
        p = write(HEAD, self.tmp)
        out = P.snapshot_cache(p, Path(self.tmp) / "bk")
        self.assertEqual(out.read_text(), HEAD)

    def test_main_missing_cache_exit0(self):
        self.assertEqual(P.main(["--cache", str(Path(self.tmp) / "nope.csv")]), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
