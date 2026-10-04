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

    def test_rejects_invalid_pdata_bounds(self):
        invalid = dict(self.pdata, end_rva_exclusive_hex="00634BBF")
        with patch.object(target_tool.analysis, "_parse_pe", return_value=(123, 0x140000000, [])), \
             patch.object(target_tool.analysis, "find_runtime_function", return_value=invalid):
            with self.assertRaisesRegex(ValueError, "invalid range"):
                target_tool.extract_target_function(self.evidence, self.exe)

    def test_direct_call_scan_exports_pdata_bounded_candidate_body(self):
        raw = b"\xE8\xFB\x0F\x00\x00"
        section = {
            "name": ".text", "virtual_address": 0x2000, "virtual_size": 0x100,
            "raw_size": 0x100, "raw_offset": 0x400, "characteristics": 0x60000020,
        }
        helper_range = dict(self.pdata, begin_rva_hex="00002000", end_rva_exclusive_hex="00002004")
        with patch.object(target_tool.analysis, "find_runtime_function", return_value=helper_range), \
             patch.object(target_tool.analysis, "_read_rva", return_value=b"\xC3\x90\x90\x90"):
            candidates = target_tool.extract_direct_call_candidates(raw, 0x1000, self.exe, [section])

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["instruction_rva_hex"], "00001000")
        self.assertEqual(candidates[0]["target_rva_hex"], "00002000")
        self.assertFalse(candidates[0]["instruction_boundary_verified"])
        self.assertEqual(candidates[0]["target_function_body"]["bytes_hex"], "C3909090")

    def test_direct_call_scan_omits_nonexecutable_or_unbounded_targets(self):
        raw = b"\xE8\xFB\x0F\x00\x00"
        section = {
            "name": ".text", "virtual_address": 0x2000, "virtual_size": 0x100,
            "raw_size": 0x100, "raw_offset": 0x400, "characteristics": 0x40000040,
        }
        with patch.object(target_tool.analysis, "find_runtime_function", return_value=None):
            candidates = target_tool.extract_direct_call_candidates(raw, 0x1000, self.exe, [section])
        self.assertEqual(candidates, [])

    def test_run_preserves_supported_caller_artifact_fields(self):
        evidence_path = Path(self.temp.name) / "exact-root-caller-latest.json"
        output_path = Path(self.temp.name) / "exact-root-caller-code-latest.json"
        evidence_path.write_text('{"logical_entry_rva_hex":"00634BC0"}', encoding="utf-8")
        target = {"status": "captured", "target_function_rva_hex": "00634BC0"}
        caller_result = {"root_resource": "MODELS/SPACE/POI/DUNGEON.SCENE.MBIN", "code_window": {"byte_count": 224}}
        with patch.object(target_tool, "extract_target_function", return_value=target), \
             patch.object(target_tool.caller_code, "extract", return_value=caller_result):
            result = target_tool.run(evidence_path, self.exe, output_path)

        saved = __import__("json").loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual(result["root_resource"], caller_result["root_resource"])
        self.assertEqual(saved["code_window"], caller_result["code_window"])
        self.assertEqual(saved["runtime_target_function"], target)


if __name__ == "__main__":
    unittest.main()
