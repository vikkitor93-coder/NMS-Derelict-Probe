"""Minimap unit tests (stdlib): address helpers and the world -> layout model.

    python -I minimap/test_minimap.py
"""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import core as S  # noqa: E402


class AddressTests(unittest.TestCase):
    def test_planet_nibble_zeroed(self):
        self.assertEqual(S.derelict_address("00502F0006607CAA"), "00002F0006607CAA")
        self.assertEqual(S.derelict_address("00003B0006606CAA"), "00003B0006606CAA")

    def test_glyphs_roundtrip(self):
        self.assertEqual(S.glyphs_of("00002F0006607CAA"), "002F06607CAA")
        self.assertEqual(S.parse_input("002F06607CAA"), "00002F0006607CAA")
        self.assertEqual(S.parse_input("5 02F 06 607 CAA"), "00002F0006607CAA")  # planet glyph ignored
        self.assertEqual(S.parse_input("00502F0006607CAA"), "00002F0006607CAA")
        self.assertIsNone(S.parse_input("XYZ"))
        self.assertIsNone(S.parse_input(""))


class PlacementTests(unittest.TestCase):
    def test_live_entrance_sample(self):
        """Live 2026-10-21 at 002F: player standing at the entrance maps to ~(0.6, 1.9, 1.7) in layout space."""
        poi = (630135.8125, -69701.890625, 1007839.9375)
        origin = [poi[k] + S.PR.ENTRANCE_REF[k] + S.PR.DUNGEON_D[k] for k in range(3)]
        lay = [w - o for w, o in zip((630035.75, -69532.7890625, 1007859.5625), origin)]
        self.assertLess(abs(lay[0] - 0.57), 0.05)
        self.assertLess(abs(lay[1] - 1.85), 0.05)
        self.assertLess(abs(lay[2] - 1.70), 0.05)


class OverlayGeometryTests(unittest.TestCase):
    """The overlay's Python port of the viewer geometry, on the validated fixture 003B06606CAA (11 rooms)."""

    @classmethod
    def setUpClass(cls):
        import json
        import overlay as O
        cls.O = O
        cls.d = json.loads(Path("D:/Orca/NMS-Derelict-Probe-analysis/emu/generated/00003B0006606CAA/derelict.json").read_text(encoding="utf-8"))
        cls.m = O.build_model(cls.d)

    def test_rooms_and_decks(self):
        self.assertEqual(len(self.m["rooms"]), 11)
        self.assertEqual(len(self.m["levels"]), 2)   # the viewer shows 2 decks for this derelict

    def test_every_container_on_an_occupied_cell_of_its_deck(self):
        O, m = self.O, self.m
        n = 0
        for c in self.d["containers"]:
            u, v, level = O.to_grid(c["layout_local_xyz"], m["e"])
            self.assertIn((O.floor_(u), level, O.floor_(v)), m["owner"])
            n += 1
        self.assertEqual(n, 23)

    def test_doors_are_rooms_minus_one(self):
        self.assertEqual(sum(len(dk["doors"]) for dk in self.m["decks"].values()), len(self.m["rooms"]) - 1)

    def test_blend_and_keys(self):
        self.assertEqual(self.O.blend("#ffffff", "#000000", 0.5), "#808080")
        self.assertEqual(self.O.parse_key("F7"), 0x76)


class BuildAndSettingsTests(unittest.TestCase):
    def test_known_build_and_hash(self):
        import live_position_705 as L
        exe = "G:/SteamLibrary/steamapps/common/No Man's Sky/Binaries/NMS.exe"
        if not Path(exe).is_file():
            self.skipTest("installed NMS.exe not at the Steam path used when this was written")
        sha = L.file_sha256(exe)
        self.assertIn(sha, L.KNOWN_BUILDS)           # fails after an NMS update: that is the point
        self.assertEqual(L.KNOWN_BUILDS[sha]["app_rva"], L.APP_RVA)

    def test_unknown_build_is_refused(self):
        import live_position_705 as L
        r = L.LiveReader.__new__(L.LiveReader)       # no process needed: exercise the refusal path only
        r.build = L.KNOWN_BUILDS.get("0" * 64)
        self.assertIsNone(r.build)
        self.assertIsNone(L.LiveReader.sim_address(r))

    def test_settings_defaults_are_sibling_folders(self):
        import settings as ST
        d = ST.defaults()
        self.assertTrue(d["analysis_dir"].endswith("NMS-Derelict-Probe-analysis"))
        self.assertEqual(Path(d["analysis_dir"]).parent, ST.ROOT.parent)
        p = ST.paths()
        self.assertEqual(p["rewards_csv"], p["analysis"] / "end-reward-cache" / "rewards.csv")

    def test_pak_fingerprint_shape(self):
        import check_update as C
        exe = Path("G:/SteamLibrary/steamapps/common/No Man's Sky/Binaries/NMS.exe")
        if not exe.is_file():
            self.skipTest("installed NMS.exe not found")
        fp = C.pak_fingerprint(exe)
        self.assertTrue(fp and all(n.lower().endswith(".pak") and v > 0 for n, v in fp.items()))


PINNED = Path("D:/Orca/NMS-Derelict-Probe-analysis/rea/NMS-13D5060D.exe")


class AutoFindTests(unittest.TestCase):
    def test_finder_reproduces_the_hand_found_705_values(self):
        if not PINNED.is_file():
            self.skipTest("pinned 7.05 exe not found")
        import nms_find_addresses_705 as F
        r = F.find_app(F.Pe(PINNED))
        self.assertTrue(r["found"])
        self.assertEqual((r["app_rva"], r["data_ptr"], r["method"]), (0x6E8D6D0, 0x38, "signature"))

    def test_resolve_unknown_build_is_unverified_then_learnable(self):
        if not PINNED.is_file():
            self.skipTest("pinned 7.05 exe not found")
        import os
        import tempfile
        import live_position_705 as L
        fake = "AB" * 32
        old = L.LEARNED_FILE
        L.LEARNED_FILE = Path(tempfile.mkdtemp()) / "learned.json"
        try:
            b, err = L.resolve_build(str(PINNED), fake)
            self.assertIsNone(err)
            self.assertFalse(b["verified"])
            self.assertEqual((b["app_rva"], b["data_ptr"]), (0x6E8D6D0, 0x38))
            self.assertEqual(b["sim"], L.DATA_SIMULATION)         # offsets inside Data come from the latest known build
            self.assertIn(fake, L.load_learned())                  # remembered, so the finder runs once per build
            learned = L.load_learned()
            learned[fake]["verified"] = True
            L.save_learned(learned)
            self.assertTrue(L.resolve_build(str(PINNED), fake)[0]["verified"])
            b2, err2 = L.resolve_build(None, "CD" * 32)            # no exe to scan: refuse with the update hint
            self.assertIsNone(b2)
            self.assertIn("After an NMS update", err2)
        finally:
            L.LEARNED_FILE = old

    def test_force_auto_switch(self):
        import os
        import live_position_705 as L
        sha = next(iter(L.KNOWN_BUILDS))
        import tempfile
        old = L.LEARNED_FILE
        L.LEARNED_FILE = Path(tempfile.mkdtemp()) / "learned.json"     # never write into the real learned_builds.json
        os.environ["MINIMAP_FORCE_AUTO"] = "1"
        try:
            b, _ = L.resolve_build(str(PINNED) if PINNED.is_file() else None, sha)
        finally:
            del os.environ["MINIMAP_FORCE_AUTO"]
            L.LEARNED_FILE = old
        self.assertFalse(b and b.get("source") == "built-in")


class GeomRenderTests(unittest.TestCase):
    """The real-geometry top-down render, on the validated fixture 003B06606CAA."""

    @classmethod
    def setUpClass(cls):
        import json
        import tempfile
        import geomrender as G
        import layoutmodel as LM
        analysis = Path("D:/Orca/NMS-Derelict-Probe-analysis")
        if not (analysis / "meshcache" / "index.json").is_file():
            raise unittest.SkipTest("mesh cache not found")
        cls.G, cls.LM = G, LM
        cls.d = json.loads((analysis / "emu/generated/00003B0006606CAA/derelict.json").read_text(encoding="utf-8"))
        cls.out = Path(tempfile.mkdtemp())
        cls.meta = G.render_derelict(cls.d, G.Pieces(analysis / "meshcache"), cls.out, zooms=[16], log=lambda *_: None)

    def test_files_and_format(self):
        self.assertEqual(self.meta["levels"], sorted(self.meta["levels"], reverse=True))
        self.assertEqual(len(self.meta["levels"]), 2)
        for lv in self.meta["levels"]:
            b = (self.out / f"deck{lv}_z16.ppm").read_bytes()
            self.assertTrue(b.startswith(b"P6\n208 208\n255\n"))          # 13 cells x 16 px
            self.assertEqual(len(b), len(b"P6\n208 208\n255\n") + 208 * 208 * 3)
        self.assertTrue((self.out / "meta.json").is_file())

    def test_containers_land_on_drawn_geometry(self):
        """Position/orientation check: nearly every crate and footlocker must sit on a drawn (non-background) pixel of its deck."""
        G, LM, e = self.G, self.LM, self.d["entrance_origin"]
        images = {}
        for lv in self.meta["levels"]:
            b = (self.out / f"deck{lv}_z16.ppm").read_bytes()
            images[lv] = b[len(b"P6\n208 208\n255\n"):]
        hit = 0
        for c in self.d["containers"]:
            u, v, level = LM.to_grid(c["layout_local_xyz"], e)
            col, row = int((G.GRID - u) * 16), int((G.GRID - v) * 16)
            px = images[level][(row * 208 + col) * 3:(row * 208 + col) * 3 + 3]
            hit += tuple(px) != G.BG
        self.assertGreaterEqual(hit, 0.9 * len(self.d["containers"]))

    def test_lower_deck_roofs_are_not_drawn(self):
        """Rooms one cell tall: a lower room's ceiling sits at the deck above's floor; it must not appear outside the rooms."""
        G, LM = self.G, self.LM
        m = LM.build_model(self.d)
        e = m["e"]
        lv = self.meta["levels"][0]
        cells = {(x, z) for (x, z, _r) in m["decks"][lv]["cells"]}
        b = (self.out / f"deck{lv}_z16.ppm").read_bytes()[len(b"P6\n208 208\n255\n"):]
        outside = sum(1 for r in range(208) for c in range(208)
                      if (int(G.GRID - c / 16 - 0.0001), int(G.GRID - r / 16 - 0.0001)) not in cells
                      and tuple(b[(r * 208 + c) * 3:(r * 208 + c) * 3 + 3]) != G.BG)
        self.assertLess(outside, 0.06 * 208 * 208)    # only the outer-wall margin and overhangs may spill out


class FrigateModuleTests(unittest.TestCase):
    """Which containers hold a Salvaged Frigate Module: the minimap must agree with the scanner's published predictions."""

    def test_matches_published_predictions(self):
        import csv
        import json
        import core
        import predict_end_reward_705 as PR
        an = Path("D:/Orca/NMS-Derelict-Probe-analysis")
        pred, poi_cache = an / "crate-loot-cache/predictions-v2.csv", an / "minimap-cache/poi.json"
        if not (pred.is_file() and poi_cache.is_file()):
            self.skipTest("prediction cache or POI cache not found")
        pois = json.loads(poi_cache.read_text(encoding="utf-8"))
        rows = {r["address"]: r for r in csv.DictReader(pred.open(encoding="utf-8"))}
        checked = 0
        for addr, poi in pois.items():
            if addr not in rows or rows[addr]["frigate_modules"] == "" or not poi.get("aband_freighter"):
                continue
            mods = core.State.frigate_modules(addr, poi, PR.load_layout(addr))
            mine = sum(1 for m in mods if m["state"] in ("certain", "likely"))
            self.assertEqual(mine, int(rows[addr]["frigate_modules"]), addr)
            for m in mods:
                self.assertTrue(m["state"] in ("certain", "likely", "possible") and isinstance(m["level"], int))
            checked += 1
        if not checked:
            self.skipTest("no overlapping systems")


if __name__ == "__main__":
    unittest.main(verbosity=2)
