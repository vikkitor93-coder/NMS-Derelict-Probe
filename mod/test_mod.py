"""Tests for the package builder's rewriting and guard (no game, no network). python -I mod/test_mod.py"""
import ast
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_package as B  # noqa: E402


class RewriteTests(unittest.TestCase):
    def test_paths_become_nmshome_lookups(self):
        src = ('"""doc mentions D:/Orca/x"""\nfrom __future__ import annotations\nimport os\n'
               'A = Path("D:/Orca/NMS-Derelict-Probe-analysis/emu/generated")\n'
               'E = os.environ.get("EMU_PYTHON", os.path.expandvars("%USERPROFILE%/tools/NMS-Shipwright/.venv/Scripts/python.exe"))\n'
               'P = Path(r"G:\\SteamLibrary\\steamapps\\common\\No Man\'s Sky\\GAMEDATA\\PCBANKS\\NMSARC.Precache.pak")\n')
        out, n = B.rewrite_text(src, "x.py")
        self.assertEqual(n, 3)
        ast.parse(out)
        self.assertNotIn("USERPROFILE", out)
        self.assertIn("_NH.ANALYSIS", out)
        self.assertIn("_NH.PYTHON", out)
        self.assertIn("_NH.PCBANKS", out)
        self.assertIn("'/NMSARC.Precache.pak'", out)
        # import goes after the docstring and the __future__ line
        lines = out.splitlines()
        self.assertTrue(lines[2].startswith("import os as _os, sys as _sys"))

    def test_unknown_machine_path_is_an_error(self):
        with self.assertRaises(SystemExit):
            B.rewrite_text('X = "D:/Orca/Somewhere/else.txt"\n', "x.py")

    def test_ordinary_strings_untouched(self):
        src = 'X = "C:/Program Files (x86)/Steam"\nY = "a:b"\n'
        out, n = B.rewrite_text(src, "x.py")
        self.assertEqual((out, n), (src, 0))

    def test_rwx_guard_pattern(self):
        for word in ("VirtualAlloc", "PAGE_EXECUTE_READWRITE", "WriteProcessMemory"):
            self.assertTrue(B.RWX.search(f"k32.{word}(x)"))
        self.assertFalse(B.RWX.search("ReadProcessMemory VirtualQueryEx OpenProcess"))

    def test_native_engine_never_shipped(self):
        files = B.project_files()
        self.assertFalse([k for k in files if k.endswith("native_writer_705.py")])
        for need in ("NMS-Derelict-Probe/minimap/overlay.py", "NMS-Derelict-Probe/minimap/first_run.py",
                     "NMS-Derelict-Probe/tools/extract_build_data_705.py", "NMS-Derelict-Probe-fastgen/fast_generate_705.py"):
            self.assertIn(need, files)


if __name__ == "__main__":
    unittest.main(verbosity=2)
