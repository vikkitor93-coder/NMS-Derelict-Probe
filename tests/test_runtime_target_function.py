import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import extract_runtime_target_function as target_tool


class RuntimeTargetFunctionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.exe = Path(self.temp.name) / "NMS.exe"
        self.exe.write_bytes(b"test executable")
        self.evidence = {"logical_entry_rva_hex": "00634BC0"}
        self.pdata = {
            "begin_rva_hex": "00634BC0",
            "end_rva_exclusive_hex": "00634BC4",
            "byte_count": 4,
            "unwind_info_rva_hex": "00001000",
            "pdata_entry_rva_hex": "00002000",
        }

    def tearDown(self):
        self.temp.cleanup()

    def test_exports_complete_pdata_bounded_body_and_hash(self):
        with patch.object(target_tool.analysis, "_parse_pe", return_value=(123, 0x140000000, [])), \
             patch.object(target_tool.analysis, "find_runtime_function", return_value=self.pdata), \
             patch.object(target_tool.analysis, "_read_rva", return_value=b"\x55\x48\x89\xE5"), \
             patch.object(target_tool.caller, "sha256_file", return_value="exe-sha"):
            result = target_tool.extract_target_function(self.evidence, self.exe)

        self.assertEqual(result["target_function_rva_hex"], "00634BC0")
        self.assertTrue(result["target_is_runtime_function_start"])
        self.assertEqual(result["code_window"]["byte_count"], 4)
        self.assertEqual(result["code_window"]["bytes_hex"], "554889E5")
        self.assertEqual(result["nms_exe"]["sha256"], "exe-sha")

    def test_rejects_missing_target_rva(self):
        with self.assertRaisesRegex(ValueError, "logical_entry_rva_hex"):
            target_tool.extract_target_function({}, self.exe)

    def test_rejects_function_not_present_in_pdata(self):
        with patch.object(target_tool.analysis, "_parse_pe", return_value=(123, 0x140000000, [])), \
             patch.object(target_tool.analysis, "find_runtime_function", return_value=None):
            with self.assertRaisesRegex(ValueError, r"\.pdata"):
                target_tool.extract_target_function(self.evidence, self.exe)

    def test_rejects_short_code_read(self):
        with patch.object(target_tool.analysis, "_parse_pe", return_value=(123, 0x140000000, [])), \
             patch.object(target_tool.analysis, "find_runtime_function", return_value=self.pdata), \
             patch.object(target_tool.analysis, "_read_rva", return_value=b"\x55"):
            with self.assertRaisesRegex(ValueError, "complete target function"):
                target_tool.extract_target_function(self.evidence, self.exe)


if __name__ == "__main__":
    unittest.main()
