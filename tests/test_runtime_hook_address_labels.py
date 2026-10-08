import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def constant(source: str, name: str) -> int:
    match = re.search(rf"^{name} = 0x([0-9A-Fa-f]+)$", source, re.MULTILINE)
    if match is None:
        raise AssertionError(f"Missing constant: {name}")
    return int(match.group(1), 16)


class RuntimeHookAddressLabelTests(unittest.TestCase):
    def test_probe_labels_match_hash_verified_current_build_evidence(self):
        source = (ROOT / "mod" / "derelict_baseline_probe.py").read_text(encoding="utf-8")
        review = json.loads((ROOT / "agent-patches/dungeon-decompile/NEW_ROOT_CAPTURE_REVIEW_20261007.json").read_text(encoding="utf-8"))
        code = json.loads((ROOT / "agent-patches/dungeon-decompile/ROOT_CALLBACK_CODE_20261007.json").read_text(encoding="utf-8"))

        target = constant(source, "CURRENT_BUILD_LOGICAL_ENTRY_RVA")
        recursive_return = constant(source, "CURRENT_BUILD_RECURSIVE_CALL_RETURN_RVA")
        self.assertEqual(target, int(review["current_exe"]["unique_full_hook_signature_match_rva"], 16))
        self.assertEqual(target, int(code["runtime_target_function"]["target_function_rva_hex"], 16))
        self.assertEqual(recursive_return, int(review["validation"]["observed_recursive_like_return_rva"], 16))
        self.assertEqual(review["current_exe"]["sha256"], code["nms_exe"]["sha256"])
        self.assertEqual(review["current_exe"]["hook_function_bounded_sha256"], code["runtime_target_function"]["code_window"]["sha256"])


if __name__ == "__main__":
    unittest.main()
