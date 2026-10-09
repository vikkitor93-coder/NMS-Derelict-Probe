import json
import importlib.util
import unittest
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("agent_ui_extensions", ROOT / "tools" / "agent_ui_extensions.py")
extensions = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(extensions)
GITHUB_SPEC = importlib.util.spec_from_file_location("github_integration", ROOT / "tools" / "github_integration.py")
github_integration = importlib.util.module_from_spec(GITHUB_SPEC)
assert GITHUB_SPEC.loader
GITHUB_SPEC.loader.exec_module(github_integration)


class SeedLineageUIExtensionTests(unittest.TestCase):
    def test_seed_lineage_extension_matches_host_api_and_lane_scope(self):
        folder = ROOT / "agent-ui" / "extensions" / "seed-lineage" / "1.0.6"
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        validated, panel = extensions.validate_manifest(
            manifest,
            "seed-lineage",
            "1.0.6",
            "0.3.43",
            lambda rel: (folder / rel).read_bytes(),
            extensions.HOST_ACTION_IDS,
        )
        source_panel = json.loads((folder / "panel.json").read_text(encoding="utf-8"))

        self.assertEqual("1.0", validated["compatible_surveyor_api_version"])
        self.assertEqual("seed-lineage", validated["extension_id"])
        self.assertTrue(source_panel["request_only"])
        self.assertLessEqual(len(source_panel["summary"]), 500)
        self.assertIn("20261009T163435Z-b91c6dbb", source_panel["summary"])
        self.assertIn("20261009T161852Z", source_panel["summary"])
        self.assertIn("00006D0006606CAB", source_panel["summary"])
        self.assertIn("43 CARGO targets are an asset prediction", source_panel["summary"])
        self.assertIn("FF 52 10 and separate resolver remain unresolved", source_panel["summary"])
        self.assertEqual(
            ["research.analyze_generation", "research.extract_caller_code", "research.extract_upstream_callers", "research.analyze_seed_function"],
            [action["action_id"] for action in panel["actions"]],
        )
        for action, source_action in zip(panel["actions"], source_panel["actions"]):
            self.assertEqual(["workflow.idle"], action["preconditions"])
            self.assertEqual("seed-lineage", action["evidence_namespace"])
            self.assertEqual({}, source_action["parameters"])
        previous_folder = ROOT / "agent-ui" / "extensions" / "seed-lineage" / "1.0.3"
        previous_panel = json.loads((previous_folder / "panel.json").read_text(encoding="utf-8"))
        self.assertEqual("research.extract_caller_code", previous_panel["actions"][0]["action_id"])
        self.assertTrue(previous_panel["request_only"])
        self.assertEqual(
            (False, "Needs: workflow.idle"),
            extensions.preconditions_met(["workflow.idle"], {"workflow_idle": False}),
        )
        self.assertEqual((True, ""), extensions.preconditions_met(["workflow.idle"], {"workflow_idle": True}))
        upload_path = github_integration.evidence_folder(
            "20261001T000000Z", "extract-caller", action["evidence_namespace"]
        )
        self.assertRegex(
            upload_path,
            r"^research-uploads/20261001T000000Z-seed-lineage-extract-caller-[0-9a-f]{8}$",
        )

        index = json.loads((ROOT / "agent-ui" / "extensions" / "index.json").read_text(encoding="utf-8"))
        self.assertIn(
            {
                "extension_id": "seed-lineage",
                "version": "1.0.6",
                "manifest_path": "seed-lineage/1.0.6/manifest.json",
            },
            index["extensions"],
        )
        entry = next(item for item in index["extensions"] if item["extension_id"] == "seed-lineage")
        with tempfile.TemporaryDirectory() as tmp:
            extension_state = Path(tmp)
            (extension_state / "active.json").write_text(
                json.dumps({"seed-lineage": "1.0.6"}), encoding="utf-8"
            )
            self.assertEqual([entry], extensions.update_candidates([entry], extension_state))
            (extension_state / "active.json").write_text(
                json.dumps({"seed-lineage": "1.0.3"}), encoding="utf-8"
            )
            self.assertEqual([], extensions.update_candidates([entry], extension_state))


if __name__ == "__main__":
    unittest.main()
