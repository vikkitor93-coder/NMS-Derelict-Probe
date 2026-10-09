from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("github_integration_root_seed_batch", ROOT / "tools" / "github_integration.py")
integration = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(integration)


class RootSeedBatchUploadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        integration.ROOT = root
        integration.WORK = root / "asset-work-v1"
        integration.WORK.mkdir(parents=True)
        integration.ACTION_OUTPUTS["root-seed-batch"] = [integration.WORK / "root-seed-batch-latest.json"]

    def tearDown(self):
        self.temp.cleanup()

    def test_upload_set_contains_report_and_only_its_journals(self):
        journal = integration.ROOT / "capture-journal-20261008T200000Z-123.jsonl"
        journal.write_text('{"kind":"resource_add"}\n', encoding="utf-8")
        report = integration.WORK / "root-seed-batch-latest.json"
        report.write_text(json.dumps({
            "summary": {"root_event_observation_count": 5},
            "source_journals": [{"name": journal.name, "root_event_count": 5}],
        }), encoding="utf-8")

        paths, producers = integration.root_seed_batch_outputs()

        self.assertEqual([report, journal], paths)
        self.assertEqual(["research.analyze_root_seed_batch"], producers[os.path.normcase(str(report.resolve()))])
        self.assertEqual(["runtime-probe"], producers[os.path.normcase(str(journal.resolve()))])

    def test_upload_refuses_empty_capture_report(self):
        report = integration.WORK / "root-seed-batch-latest.json"
        report.write_text(json.dumps({"summary": {"root_event_observation_count": 0}}), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "No saved root-resource events"):
            integration.root_seed_batch_outputs()

    def test_report_cannot_select_files_outside_surveyor_data_root(self):
        report = integration.WORK / "root-seed-batch-latest.json"
        report.write_text(json.dumps({
            "summary": {"root_event_observation_count": 1},
            "source_journals": [{"name": "..\\outside.jsonl", "root_event_count": 1}],
        }), encoding="utf-8")

        paths, _producers = integration.root_seed_batch_outputs()

        self.assertEqual([report], paths)


if __name__ == "__main__":
    unittest.main()
