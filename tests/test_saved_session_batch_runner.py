import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools" / "run_saved_session_batch.py"
spec = importlib.util.spec_from_file_location("saved_session_batch_runner", SOURCE)
batch = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = batch
spec.loader.exec_module(batch)


class SavedSessionBatchTests(unittest.TestCase):
    def test_sessions_run_concurrently_with_independent_reports_and_no_latest_race(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            appdata = root / "appdata"
            session_dir = appdata / "NMSDerelictSurveyor" / "sessions"
            session_dir.mkdir(parents=True)
            sessions = []
            for i in range(4):
                path = session_dir / f"session-{i}.json"
                path.write_text(json.dumps({"ended_utc": f"2026-10-09T00:0{i}:00Z"}), encoding="utf-8")
                sessions.append({"session_file": path.name, "session_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
            spec_path = root / "batch-spec.json"
            spec_path.write_text(json.dumps({"batch_id": "parallel-test", "sessions": sessions}), encoding="utf-8")
            output = root / "research-output" / "automatic-session-batches" / "parallel-test"
            active = 0
            maximum = 0
            lock = threading.Lock()

            def fake_run(command, **kwargs):
                nonlocal active, maximum
                with lock:
                    active += 1
                    maximum = max(maximum, active)
                time.sleep(0.03)
                run_dir = Path(command[command.index("--output-dir") + 1])
                filename = command[command.index("--session-file") + 1]
                session_sha = command[command.index("--session-sha256") + 1]
                run_dir.mkdir(parents=True)
                (run_dir / "combined-results.json").write_text(json.dumps({
                    "run_id": filename, "trigger": {"session_sha256": session_sha},
                    "summary": {"completed": 8, "failed": 0},
                }), encoding="utf-8")
                self.assertIn("--no-latest", command)
                with lock:
                    active -= 1
                return type("Proc", (), {"returncode": 0, "stdout": "ok\n", "stderr": ""})()

            with patch.object(batch, "ROOT", root), patch.object(batch, "RUNNER", root / "runner.py"), \
                 patch.dict(os.environ, {"LOCALAPPDATA": str(appdata)}), patch.object(batch.subprocess, "run", side_effect=fake_run):
                result_path, code = batch.run_batch(spec_path, output, max_sessions=3, action_workers=4)

            self.assertEqual(0, code)
            self.assertEqual(3, maximum)
            result = json.loads(result_path.read_text(encoding="utf-8"))
            self.assertEqual(4, result["completed_count"])
            self.assertEqual(4, len(result["reports"]))
            self.assertEqual(4, len({item["report_path"] for item in result["reports"]}))

    def test_session_hash_change_is_rejected_before_worker_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            appdata = root / "appdata"
            sessions = appdata / "NMSDerelictSurveyor" / "sessions"
            sessions.mkdir(parents=True)
            session = sessions / "changed.json"
            session.write_text('{"ended_utc":"x"}', encoding="utf-8")
            spec_path = root / "spec.json"
            spec_path.write_text(json.dumps({"batch_id": "hash-test", "sessions": [
                {"session_file": session.name, "session_sha256": "0" * 64},
            ]}), encoding="utf-8")
            output = root / "output"
            with patch.object(batch, "ROOT", root), patch.object(batch, "RUNNER", root / "runner.py"), \
                 patch.dict(os.environ, {"LOCALAPPDATA": str(appdata)}), patch.object(batch.subprocess, "run") as run:
                result_path, code = batch.run_batch(spec_path, output)
            self.assertEqual(1, code)
            run.assert_not_called()
            result = json.loads(result_path.read_text(encoding="utf-8"))
            self.assertEqual("failed_to_start", result["sessions"][0]["status"])


if __name__ == "__main__":
    unittest.main()
