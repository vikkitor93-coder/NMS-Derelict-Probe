import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools" / "test_parallel_research_actions.py"
SPEC = importlib.util.spec_from_file_location("parallel_research_actions_trigger", SOURCE)
parallel = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(parallel)


class ParallelResearchTriggerTests(unittest.TestCase):
    def test_manual_report_trigger_is_explicit(self):
        self.assertEqual(
            {"kind": "manual_button", "session_file": None, "session_sha256": None},
            parallel._trigger_record("manual_button"),
        )

    def test_automatic_trigger_is_tied_to_saved_session_hash(self):
        record = parallel._trigger_record(
            "automatic_saved_session", "20261008T140041Z_example.json", "a" * 64,
        )
        self.assertEqual("automatic_saved_session", record["kind"])
        self.assertEqual("20261008T140041Z_example.json", record["session_file"])
        self.assertEqual("a" * 64, record["session_sha256"])

    def test_unknown_trigger_is_rejected(self):
        with self.assertRaises(ValueError):
            parallel._trigger_record("unknown")


if __name__ == "__main__":
    unittest.main()
