import json
import importlib.util
import unittest
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
        folder = ROOT / "agent-ui" / "extensions" / "seed-lineage" / "1.0.0"
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        validated, panel = extensions.validate_manifest(
            manifest,
            "seed-lineage",
            "1.0.0",
            "0.3.41",
            lambda rel: (folder / rel).read_bytes(),
            extensions.HOST_ACTION_IDS,
        )
        source_panel = json.loads((folder / "panel.json").read_text(encoding="utf-8"))

        self.assertEqual("1.0", validated["compatible_surveyor_api_version"])
        self.assertEqual("seed-lineage", validated["extension_id"])
        self.assertFalse(source_panel["request_only"])
        self.assertIn("root seed 9256392A2F5A74AC, MEDI_FLOATERS, 10 rooms, 16 containers", source_panel["summary"])
        self.assertIn("CARGO_FLOATERS, 8-room, 35-container layout is historical", source_panel["summary"])
        action = panel["actions"][0]
        source_action = source_panel["actions"][0]
        self.assertEqual("research.analyze_seed_function", action["action_id"])
        self.assertEqual(["workflow.idle"], action["preconditions"])
        self.assertEqual("seed-lineage", action["evidence_namespace"])
        self.assertEqual({}, source_action["parameters"])
        self.assertEqual(
            (False, "Needs: workflow.idle"),
            extensions.preconditions_met(["workflow.idle"], {"workflow_idle": False}),
        )
        self.assertEqual((True, ""), extensions.preconditions_met(["workflow.idle"], {"workflow_idle": True}))
        upload_path = github_integration.evidence_folder(
            "20261001T000000Z", "analyze-seed-function", action["evidence_namespace"]
        )
        self.assertRegex(
            upload_path,
            r"^research-uploads/20261001T000000Z-seed-lineage-analyze-seed-function-[0-9a-f]{8}$",
        )

        index = json.loads((ROOT / "agent-ui" / "extensions" / "index.json").read_text(encoding="utf-8"))
        self.assertIn(
            {
                "extension_id": "seed-lineage",
                "version": "1.0.0",
                "manifest_path": "seed-lineage/1.0.0/manifest.json",
            },
            index["extensions"],
        )


if __name__ == "__main__":
    unittest.main()
