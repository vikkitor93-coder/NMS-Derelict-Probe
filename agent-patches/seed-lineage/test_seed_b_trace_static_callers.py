"""Focused tests for Seed-B static xref boundary annotation."""
from __future__ import annotations

import importlib.util
import struct
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("seed_b_trace_static_callers.py")
spec = importlib.util.spec_from_file_location("seed_b_scanner", SCRIPT)
scanner = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(scanner)


class RuntimeFunctionBoundaryTests(unittest.TestCase):
    def fixture(self, with_pdata: bool = True):
        data = bytearray(0x100)
        # E8 at RVA 0x1008 calls RVA 0x1010.
        data[8] = 0xE8
        struct.pack_into("<i", data, 9, 3)
        sections = [
            {"name": ".text", "virtual_address": 0x1000,
             "virtual_size": 0x40, "raw_pointer": 0,
             "raw_size": 0x40, "characteristics": 0x20000000},
        ]
        if with_pdata:
            sections.append(
                {"name": ".pdata", "virtual_address": 0x2000,
                 "virtual_size": 12, "raw_pointer": 0x80,
                 "raw_size": 12, "characteristics": 0x40000040}
            )
            struct.pack_into("<III", data, 0x80, 0x1000, 0x1040, 0x3000)
        return bytes(data), {"image_base": 0x140000000, "sections": sections}

    def test_xref_gets_exact_pdata_function_bounds(self):
        data, pe = self.fixture()
        result = scanner.scan_references(data, pe, target_rvas=(0x1010,))
        xrefs = result[0x1010]["direct_xrefs"]
        self.assertEqual(len(xrefs), 1)
        self.assertEqual(xrefs[0]["instruction_rva_hex"], "00001008")
        self.assertEqual(
            xrefs[0]["containing_function"],
            {
                "begin_rva_hex": "00001000",
                "end_rva_exclusive_hex": "00001040",
                "unwind_info_rva_hex": "00003000",
            },
        )

    def test_missing_pdata_keeps_scanner_compatible(self):
        data, pe = self.fixture(with_pdata=False)
        result = scanner.scan_references(data, pe, target_rvas=(0x1010,))
        xref = result[0x1010]["direct_xrefs"][0]
        self.assertNotIn("containing_function", xref)


if __name__ == "__main__":
    unittest.main()
