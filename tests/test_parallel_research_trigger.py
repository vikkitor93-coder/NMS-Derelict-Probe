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
            {"kind": "manual_button", "session_file": None, "session_sha256": None,
             "session_input_verified": False},
            parallel._trigger_record("manual_button"),
        )

    def test_automatic_trigger_is_tied_to_saved_session_hash(self):
        record = parallel._trigger_record(
            "automatic_saved_session", "20261008T140041Z_example.json", "a" * 64,
            session_input_verified=True,
        )
        self.assertEqual("automatic_saved_session", record["kind"])
        self.assertEqual("20261008T140041Z_example.json", record["session_file"])
        self.assertEqual("a" * 64, record["session_sha256"])
        self.assertTrue(record["session_input_verified"])

    def test_worker_session_override_pins_verified_saved_session(self):
        import hashlib
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            local_data = root / "worker" / "NMSDerelictSurveyor"
            local_data.mkdir(parents=True)
            (local_data / "latest.json").write_text('{"session_id":"wrong"}', encoding="utf-8")
            session_path = root / "sessions" / "run.json"
            session_path.parent.mkdir()
            raw = json.dumps({"session_id": "right", "ended_utc": "2026-10-08T19:00:00Z"}).encode()
            session_path.write_bytes(raw)
            digest = hashlib.sha256(raw).hexdigest()
            self.assertEqual(digest, parallel._pin_session_as_latest(local_data, session_path, digest))
            self.assertEqual("right", json.loads((local_data / "latest.json").read_text())["session_id"])

    def test_worker_session_override_rejects_changed_session(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            local_data = root / "worker" / "NMSDerelictSurveyor"
            local_data.mkdir(parents=True)
            target = local_data / "latest.json"
            target.write_text('{"session_id":"unchanged"}', encoding="utf-8")
            session_path = root / "sessions" / "run.json"
            session_path.parent.mkdir()
            session_path.write_text('{"ended_utc":"2026-10-08T19:00:00Z"}', encoding="utf-8")
            with self.assertRaises(ValueError):
                parallel._pin_session_as_latest(local_data, session_path, "0" * 64)
            self.assertEqual('{"session_id":"unchanged"}', target.read_text(encoding="utf-8"))

    def test_unknown_trigger_is_rejected(self):
        with self.assertRaises(ValueError):
            parallel._trigger_record("unknown")


if __name__ == "__main__":
    unittest.main()
