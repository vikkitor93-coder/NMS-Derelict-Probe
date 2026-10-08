import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.compile_build_requests import BuildRequestError, stage_requests


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class BuildRequestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "main"
        self.stage = self.root / "stage"
        self.requests = self.source / "build-requests"
        self.source.mkdir()
        self.stage.mkdir()
        (self.source / "tools").mkdir()
        (self.stage / "tools").mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def request(self, lane="runtime-dispatch", rid="sample-1", *, status="ready", files=None, tests=None):
        folder = self.requests / lane / rid
        payload = folder / "files" / "tools" / "new.py"
        payload.parent.mkdir(parents=True)
        payload.write_bytes(b"print('new')\n")
        data = {
            "schema_version": 1,
            "request_id": rid,
            "lane_id": lane,
            "status": status,
            "base_commit": "0123456789abcdef0123456789abcdef01234567",
            "summary": "Add a tested tool.",
            "files": files if files is not None else [{
                "source": "files/tools/new.py",
                "target": "tools/new.py",
                "sha256": sha(b"print('new')\n"),
                "base_sha256": None,
            }],
            "tests": tests if tests is not None else ["python -m unittest"],
            "rollback": "Remove tools/new.py.",
        }
        (folder / "request.json").write_text(json.dumps(data), encoding="utf-8")
        return folder

    def test_stages_ready_file_and_records_request(self):
        self.request()
        receipt = stage_requests(self.source, self.stage, self.requests)
        self.assertEqual((self.stage / "tools/new.py").read_bytes(), b"print('new')\n")
        self.assertEqual(receipt["applied"][0]["request_id"], "sample-1")

    def test_draft_is_skipped(self):
        self.request(status="draft")
        receipt = stage_requests(self.source, self.stage, self.requests)
        self.assertEqual(receipt["applied"], [])
        self.assertEqual(receipt["ignored"][0]["status"], "draft")

    def test_payload_hash_mismatch_fails_before_staging(self):
        folder = self.request()
        data = json.loads((folder / "request.json").read_text())
        data["files"][0]["sha256"] = "0" * 64
        (folder / "request.json").write_text(json.dumps(data))
        with self.assertRaisesRegex(BuildRequestError, "SHA-256 mismatch"):
            stage_requests(self.source, self.stage, self.requests)
        self.assertFalse((self.stage / "tools/new.py").exists())

    def test_stale_replacement_fails(self):
        (self.source / "tools/old.py").write_bytes(b"changed main")
        folder = self.request()
        data = json.loads((folder / "request.json").read_text())
        data["files"][0].update({"target": "tools/old.py", "base_sha256": sha(b"old main")})
        (folder / "request.json").write_text(json.dumps(data))
        with self.assertRaisesRegex(BuildRequestError, "Stale target conflict"):
            stage_requests(self.source, self.stage, self.requests)
        self.assertFalse((self.stage / "tools/old.py").exists())

    def test_path_traversal_is_rejected(self):
        folder = self.request()
        data = json.loads((folder / "request.json").read_text())
        data["files"][0]["target"] = "../escape.py"
        (folder / "request.json").write_text(json.dumps(data))
        with self.assertRaisesRegex(BuildRequestError, "Unsafe target path"):
            stage_requests(self.source, self.stage, self.requests)

    def test_conflicting_requests_fail_before_either_is_staged(self):
        self.request("runtime-dispatch", "request-a")
        self.request("seed-lineage", "request-b")
        second = self.requests / "seed-lineage/request-b"
        replacement = second / "files/tools/new.py"
        replacement.write_bytes(b"different content")
        data = json.loads((second / "request.json").read_text())
        data["files"][0]["sha256"] = sha(replacement.read_bytes())
        (second / "request.json").write_text(json.dumps(data))
        with self.assertRaisesRegex(BuildRequestError, "Multiple build requests target"):
            stage_requests(self.source, self.stage, self.requests)
        self.assertFalse((self.stage / "tools/new.py").exists())

    def test_stage_tree_must_match_source_before_applying_request(self):
        self.request()
        (self.stage / "tools/new.py").write_bytes(b"untracked stage edit")
        with self.assertRaisesRegex(BuildRequestError, "Staging tree already has a different file"):
            stage_requests(self.source, self.stage, self.requests)


if __name__ == "__main__":
    unittest.main()
