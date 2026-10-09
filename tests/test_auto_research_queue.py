import importlib.util
import json
import queue
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools" / "surveyor_controller.py"
sys.path.insert(0, str(SOURCE.parent))
try:
    import tkinter  # noqa: F401
except ImportError:
    tkinter = types.ModuleType("tkinter")
    tkinter.StringVar = type("StringVar", (), {})
    tkinter.ttk = types.ModuleType("tkinter.ttk")
    tkinter.ttk.Widget = type("Widget", (), {})
    tkinter.messagebox = types.ModuleType("tkinter.messagebox")
    sys.modules.update({"tkinter": tkinter, "tkinter.ttk": tkinter.ttk,
                        "tkinter.messagebox": tkinter.messagebox})
spec = importlib.util.spec_from_file_location("surveyor_controller_auto_queue", SOURCE)
controller_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(controller_module)


class Value:
    def __init__(self, value=None):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class AutoResearchQueueTests(unittest.TestCase):
    def test_interrupted_running_sessions_restore_in_fifo_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            sessions = Path(tmp) / "sessions"
            records = {
                "sha-1": {"session_file": "one.json", "state": "running"},
                "sha-2": {"session_file": "two.json", "state": "queued"},
                "sha-done": {"session_file": "done.json", "state": "complete"},
                "sha-bad": {"session_file": "../unsafe.json", "state": "queued"},
            }
            pending = controller_module._restore_pending_auto_research(records, sessions)
            self.assertEqual([("sha-1", sessions / "one.json"), ("sha-2", sessions / "two.json")], pending)
            self.assertEqual("queued", records["sha-1"]["state"])
            self.assertEqual("not-started", records["sha-bad"]["state"])

    def test_startup_backfills_unreported_saved_sessions_and_skips_existing_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sessions = root / "sessions"
            project = root / "project"
            report_dir = project / "parallel-action-tests" / "old-run"
            sessions.mkdir(parents=True)
            report_dir.mkdir(parents=True)
            items = []
            for name, ended in (("one.json", "2026-10-08T10:00:00Z"), ("two.json", "2026-10-08T11:00:00Z"), ("three.json", "2026-10-08T12:00:00Z")):
                path = sessions / name
                path.write_text(json.dumps({"ended_utc": ended, "session_id": name}), encoding="utf-8")
                signature = __import__("hashlib").sha256(path.read_bytes()).hexdigest()
                items.append((signature, path))
            report = {"run_id": "old-run", "report_path": "parallel-action-tests/old-run/combined-results.json",
                      "trigger": {"kind": "automatic_saved_session", "session_sha256": items[1][0]}}
            (report_dir / "combined-results.json").write_text(json.dumps(report), encoding="utf-8")
            records = {}
            pending = []
            added = controller_module._reconcile_saved_session_queue(
                records, pending, sessions, project, root / "latest.json",
            )
            self.assertEqual(2, added)
            self.assertEqual([("one.json", items[0][0]), ("three.json", items[2][0])],
                             [(path.name, signature) for signature, path in pending])
            self.assertEqual("already-reported", records[items[1][0]]["state"])
            self.assertEqual("old-run", records[items[1][0]]["run_id"])
            self.assertEqual(0, controller_module._reconcile_saved_session_queue(
                records, pending, sessions, project, root / "latest.json",
            ))
            self.assertEqual(2, len(pending))

    def test_persisted_queue_contains_each_session_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "auto-research-queue.json"
            controller = controller_module.SurveyorController.__new__(controller_module.SurveyorController)
            controller.auto_research_records = {"sha-1": {"session_file": "one.json", "state": "queued"}}
            with patch.object(controller_module, "AUTO_RESEARCH_QUEUE", path):
                controller._persist_auto_research_queue()
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual("queued", saved["sessions"]["sha-1"]["state"])

    def test_queued_saved_sessions_launch_one_parallel_batch_with_distinct_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            controller = controller_module.SurveyorController.__new__(controller_module.SurveyorController)
            controller.auto_research_enabled = Value(True)
            controller.auto_research_pending = []
            controller.auto_research_records = {}
            controller.auto_research_last_signature = ""
            controller.auto_research_running_signature = ""
            controller.auto_research_running_signatures = set()
            controller.auto_research_running_batch_id = ""
            controller.auto_research_state = Value("")
            controller.parallel_test_state = Value("")
            controller.workflow_running = True
            controller.project_root = root
            controller.python_exe = "python"
            controller.auto_upload_enabled = Value(False)
            (root / "tools").mkdir()
            (root / "tools" / "run_saved_session_batch.py").write_text("# test stub\n", encoding="utf-8")
            receipts = []
            starts = []
            controller._write_auto_research_receipt = lambda signature, path, state, **kwargs: receipts.append(
                (signature, path.name, state, kwargs.get("run_id"), kwargs.get("report_path"))
            )
            controller._persist_auto_research_queue = lambda: None

            def start_run(label, steps, **kwargs):
                starts.append((label, steps, kwargs))
                controller.workflow_running = True

            controller._run_steps = start_run
            sessions = [(f"sha-{i}", root / f"session-{i}.json") for i in range(1, 4)]
            snapshots = iter(sessions)
            with patch.object(controller_module, "_saved_session_snapshot", side_effect=lambda _live: next(snapshots)):
                for i in range(1, 4):
                    controller._maybe_auto_run_research_after_saved_session({"index": i})

            self.assertEqual(3, len(controller.auto_research_pending))
            controller.workflow_running = False
            controller._start_next_auto_research()
            self.assertEqual(1, len(starts))
            label, steps, _kwargs = starts[0]
            self.assertEqual("Parallel saved-session research batch", label)
            self.assertIn("run_saved_session_batch.py", steps[0][1][1])
            self.assertIn("--max-concurrent-sessions", steps[0][1])
            spec_arg = steps[0][1][steps[0][1].index("--batch-spec") + 1]
            spec = json.loads(Path(spec_arg).read_text(encoding="utf-8"))
            self.assertEqual([session[0] for session in sessions], [item["session_sha256"] for item in spec["sessions"]])
            self.assertEqual(3, len(controller.auto_research_running_signatures))
            self.assertEqual(0, len(controller.auto_research_pending))

    def test_batch_completion_updates_each_session_from_its_own_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            controller = controller_module.SurveyorController.__new__(controller_module.SurveyorController)
            controller.auto_research_records = {}
            controller.auto_research_running_signatures = {"sha-1", "sha-2"}
            controller.auto_research_running_signature = "sha-1"
            controller.auto_research_state = Value("")
            controller.auto_research_pending = []
            controller.auto_research_enabled = Value(True)
            controller.workflow_running = True
            controller._persist_auto_research_queue = lambda: None
            receipts = []
            controller._write_auto_research_receipt = lambda signature, path, state, **kwargs: receipts.append((signature, state, kwargs.get("report_path")))
            sessions = [("sha-1", root / "one.json"), ("sha-2", root / "two.json")]
            output = root / "batch-results.json"
            output.write_text(json.dumps({"sessions": [
                {"session_sha256": "sha-1", "session_file": "one.json", "status": "complete", "run_id": "run-1", "report_path": "research-output/batch/runs/one/combined-results.json"},
                {"session_sha256": "sha-2", "session_file": "two.json", "status": "complete", "run_id": "run-2", "report_path": "research-output/batch/runs/two/combined-results.json"},
            ]}), encoding="utf-8")
            controller._start_next_auto_research = lambda: None
            controller._finish_auto_research_batch(0, sessions, "batch", output, False)
            self.assertEqual({"sha-1", "sha-2"}, {row[0] for row in receipts if row[1] == "complete"})
            self.assertNotEqual(controller.auto_research_records["sha-1"]["report_path"], controller.auto_research_records["sha-2"]["report_path"])


if __name__ == "__main__":
    unittest.main()
