"""Contract and lifecycle checks for the DUNGEON-C Surveyor extension.

Run from a Surveyor 0.3.41+ source tree with:
  python -m unittest tests.test_dungeon_decompile_extension -v
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("agent_ui_extensions", ROOT / "tools" / "agent_ui_extensions.py")
ui = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(ui)

sys.path.insert(0, str(ROOT))
from tools import github_integration  # noqa: E402
from tools import surveyor_controller  # noqa: E402

EXTENSION = ROOT / "agent-ui" / "extensions" / "dungeon-decompile"
CURRENT = EXTENSION / "1.0.2"
PREVIOUS = EXTENSION / "1.0.1"


def published_entry(version: str) -> dict:
    return {
        "extension_id": "dungeon-decompile",
        "version": version,
        "manifest_path": f"dungeon-decompile/{version}/manifest.json",
    }


def remote_for(version: str) -> dict[str, bytes]:
    folder = EXTENSION / version
    return {
        ui.REMOTE_BASE + f"dungeon-decompile/{version}/manifest.json": (folder / "manifest.json").read_bytes(),
        ui.REMOTE_BASE + f"dungeon-decompile/{version}/panel.json": (folder / "panel.json").read_bytes(),
    }


class DungeonDecompileExtensionTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((CURRENT / "manifest.json").read_text(encoding="utf-8"))
        self.panel = json.loads((CURRENT / "panel.json").read_text(encoding="utf-8"))
        self.index = json.loads((ROOT / "agent-ui/extensions/index.json").read_text(encoding="utf-8"))

    def test_api_compatibility_versioned_index_and_every_panel_hash(self):
        entries = ui.validate_index(self.index)
        self.assertIn(published_entry("1.0.2"), entries)
        manifest, panel = ui.validate_manifest(
            self.manifest, "dungeon-decompile", "1.0.2", "0.3.41",
            lambda rel: (CURRENT / rel).read_bytes(), ui.HOST_ACTION_IDS,
        )
        self.assertEqual("1.0", manifest["compatible_surveyor_api_version"])
        self.assertEqual("1.0.2", manifest["version"])
        self.assertEqual("research.analyze_generation", panel["actions"][0]["action_id"])
        with self.assertRaisesRegex(ui.ExtensionError, "newer Surveyor"):
            ui.validate_manifest(self.manifest, "dungeon-decompile", "1.0.2", "0.3.40", lambda rel: (CURRENT / rel).read_bytes(), ui.HOST_ACTION_IDS)
        for item in self.manifest["files"]:
            data = (CURRENT / item["path"]).read_bytes()
            self.assertEqual(item["sha256"], hashlib.sha256(data).hexdigest())
            self.assertRegex(item["sha256"], r"^[0-9a-f]{64}$")

    def test_invalid_actions_parameters_and_unsafe_content_are_rejected(self):
        raw_panel = (CURRENT / "panel.json").read_bytes()
        for invalid_action, error in [
            ({**self.panel["actions"][0], "action_id": "research.run_shell"}, "Unsupported or duplicate"),
            ({**self.panel["actions"][0], "parameters": {"command": "whoami"}}, "does not accept"),
            ({**self.panel["actions"][0], "preconditions": ["workflow.idle", "filesystem.write"]}, "unsupported precondition"),
            ({**self.panel["actions"][0], "evidence_namespace": "shared"}, "must match"),
            ({**self.panel["actions"][0], "command": "powershell.exe"}, "unsupported fields"),
        ]:
            bad_panel = {**self.panel, "actions": [invalid_action]}
            encoded = (json.dumps(bad_panel, ensure_ascii=False) + "\n").encode()
            bad_manifest = {**self.manifest, "files": [{"path": "panel.json", "sha256": hashlib.sha256(encoded).hexdigest()}]}
            with self.subTest(invalid_action=invalid_action), self.assertRaisesRegex(ui.ExtensionError, error):
                ui.validate_manifest(bad_manifest, "dungeon-decompile", "1.0.2", "0.3.41", lambda _rel: encoded, ui.HOST_ACTION_IDS)
        with self.assertRaisesRegex(ui.ExtensionError, "SHA-256 mismatch"):
            ui.validate_manifest(self.manifest, "dungeon-decompile", "1.0.2", "0.3.41", lambda _rel: raw_panel + b"tampered", ui.HOST_ACTION_IDS)

    def test_request_only_panel_uses_exact_live_action_preconditions(self):
        action = self.panel["actions"][0]
        self.assertTrue(self.panel["request_only"])
        self.assertEqual(["workflow.idle", "nms.running", "probe.connected"], action["preconditions"])
        self.assertEqual({}, action["parameters"])
        self.assertEqual("dungeon-decompile", action["evidence_namespace"])
        allowed, reason = ui.preconditions_met(action["preconditions"], {
            "workflow_idle": True, "nms_running": True, "probe_connected": True,
        })
        self.assertTrue(allowed, reason)
        for missing, key in [("workflow.idle", "workflow_idle"), ("nms.running", "nms_running"), ("probe.connected", "probe_connected")]:
            state = {"workflow_idle": True, "nms_running": True, "probe_connected": True}
            state[key] = False
            allowed, reason = ui.preconditions_met(action["preconditions"], state)
            self.assertFalse(allowed)
            self.assertIn(missing, reason)

    def test_live_update_completion_rerenders_selected_lane_without_restart(self):
        class Notice:
            value = ""
            def set(self, value): self.value = value
        class FakeController:
            agent_ui_extension_installing = {"dungeon-decompile"}
            agent_ui_extension_notice = Notice()
            agent_selected_lane = {"id": "dungeon-decompile"}
            rendered = []
            summary_refreshed = False
            def _render_agent_ui_extension(self, lane): self.rendered.append(lane)
            def _update_agent_extension_summary(self): self.summary_refreshed = True
        fake = FakeController()
        with mock.patch.object(surveyor_controller, "_log"):
            surveyor_controller.SurveyorController._finish_agent_ui_extension_update(fake, "dungeon-decompile", "")
        self.assertEqual(set(), fake.agent_ui_extension_installing)
        self.assertIn("without restarting Surveyor", fake.agent_ui_extension_notice.value)
        self.assertTrue(fake.summary_refreshed)
        self.assertEqual([fake.agent_selected_lane], fake.rendered)

    def test_update_preserves_published_101_and_rolls_back(self):
        self.assertTrue((PREVIOUS / "manifest.json").is_file(), "published v1.0.1 must remain present")
        self.assertTrue((EXTENSION / "1.0.0" / "manifest.json").is_file(), "published v1.0.0 must remain present")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ui.install_extension(root, published_entry("1.0.1"), "0.3.41", ui.HOST_ACTION_IDS, remote_for("1.0.1").__getitem__)
            ui.install_extension(root, published_entry("1.0.2"), "0.3.41", ui.HOST_ACTION_IDS, remote_for("1.0.2").__getitem__)
            active, _panel = ui.load_installed_extension(root, "dungeon-decompile", "0.3.41", ui.HOST_ACTION_IDS)
            self.assertEqual("1.0.2", active["version"])
            old, _ = ui.activate_installed_extension(root, "dungeon-decompile", "1.0.1", "0.3.41", ui.HOST_ACTION_IDS)
            self.assertEqual("1.0.1", old["version"])
            self.assertEqual(["1.0.2", "1.0.1"], ui.installed_versions(root, "dungeon-decompile"))

    def test_evidence_is_written_inside_lane_namespace(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = ui.write_action_record(Path(tmp), "dungeon-decompile", "1.0.2", "research.analyze_generation", "complete")
            contents = json.loads(record.read_text(encoding="utf-8"))
            self.assertEqual("dungeon-decompile", contents["extension_id"])
        folder = github_integration.evidence_folder("20261001T120000Z", "analyze-generation", "dungeon-decompile")
        self.assertRegex(folder, r"^research-uploads/20261001T120000Z-dungeon-decompile-analyze-generation-[0-9a-f]{8}$")
        with self.assertRaisesRegex(RuntimeError, "Invalid agent evidence namespace"):
            github_integration.evidence_folder("20261001T120000Z", "analyze-generation", "../shared")


if __name__ == "__main__":
    unittest.main()
