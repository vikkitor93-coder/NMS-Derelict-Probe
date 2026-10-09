import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools" / "github_integration.py"
spec = importlib.util.spec_from_file_location("github_integration_batch_upload", SOURCE)
github = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = github
spec.loader.exec_module(github)


class AutomaticResearchBatchUploadTests(unittest.TestCase):
    def test_batch_upload_publishes_one_report_per_session_and_pointer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reports = []
            for i in range(2):
                report = root / "research-output" / "runs" / str(i) / "combined-results.json"
                report.parent.mkdir(parents=True)
                payload = {"run_id": f"run-{i}", "trigger": {"session_sha256": str(i) * 64},
                           "summary": {"completed": 8, "failed": 0}}
                raw = (json.dumps(payload) + "\n").encode()
                report.write_bytes(raw)
                reports.append({"session_file": f"session-{i}.json", "session_sha256": str(i) * 64,
                                "run_id": f"run-{i}", "status": "complete",
                                "summary": payload["summary"], "report_path": report.relative_to(root).as_posix(),
                                "report_sha256": hashlib.sha256(raw).hexdigest()})
            index = root / "research-output" / "batch-results.json"
            index.parent.mkdir(parents=True, exist_ok=True)
            index.write_text(json.dumps({"schema_version": 1, "batch_id": "batch-test",
                                         "state": "complete", "session_count": 2, "reports": reports}), encoding="utf-8")
            calls = []

            def api(_gh, method, endpoint, payload=None):
                calls.append((method, endpoint, payload))
                if method == "GET" and endpoint.endswith("git/ref/heads/main"):
                    return {"object": {"sha": "parent"}}
                if method == "GET" and endpoint.endswith("git/commits/parent"):
                    return {"tree": {"sha": "base-tree"}}
                if endpoint.endswith("/git/blobs") and method == "POST":
                    return {"sha": f"blob-{len(calls)}"}
                if endpoint.endswith("/git/trees") and method == "POST":
                    return {"sha": "new-tree"}
                if endpoint.endswith("/git/commits") and method == "POST":
                    return {"sha": "new-commit"}
                return {"ok": True}

            with patch.object(github, "project_root", return_value=root), patch.object(github, "_gh", return_value="gh"), \
                 patch.object(github, "_auth_status", return_value=type("Auth", (), {"returncode": 0})()), \
                 patch.object(github, "_api_json", side_effect=api):
                github.upload_automatic_research_batch(str(index))

            tree_call = next(row for row in calls if row[1].endswith("/git/trees"))
            paths = [row["path"] for row in tree_call[2]["tree"]]
            report_paths = [path for path in paths if path.endswith("/combined-results.json")]
            self.assertEqual(2, len(report_paths))
            self.assertEqual(2, len(set(report_paths)))
            self.assertIn("research/LATEST_AUTOMATIC_RESEARCH_BATCH.json", paths)
            self.assertTrue(any(path.endswith("/batch-results.json") for path in paths))

    def test_upload_rejects_report_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = root / "report.json"
            report.write_text(json.dumps({"trigger": {"session_sha256": "a" * 64}}), encoding="utf-8")
            index = root / "index.json"
            index.write_text(json.dumps({"schema_version": 1, "reports": [{
                "report_path": "report.json", "report_sha256": "0" * 64, "session_sha256": "a" * 64,
            }]}), encoding="utf-8")
            with patch.object(github, "project_root", return_value=root):
                with self.assertRaisesRegex(RuntimeError, "changed after the index"):
                    github.upload_automatic_research_batch(str(index))


if __name__ == "__main__":
    unittest.main()
