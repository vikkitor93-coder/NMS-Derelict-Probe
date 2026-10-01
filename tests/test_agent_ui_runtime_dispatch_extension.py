import copy
import hashlib
import json
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from tools import agent_ui_extensions as extensions
from tools import github_integration
from tools import surveyor_controller as controller

ROOT = Path(__file__).resolve().parents[1]
LANE = "runtime-dispatch"
VERSION = "1.0.0"
HOST_VERSION = "0.3.41"
EXTENSION_DIR = ROOT / "agent-ui" / "extensions" / LANE / VERSION


def read_extension():
    manifest = json.loads((EXTENSION_DIR / "manifest.json").read_text(encoding="utf-8"))
    panel = json.loads((EXTENSION_DIR / "panel.json").read_text(encoding="utf-8"))
    return manifest, panel


def remote_package(manifest, panel_bytes):
    base = extensions.REMOTE_BASE
    prefix = f"{LANE}/{manifest['version']}/"
    return {
        base + f"{LANE}/{manifest['version']}/manifest.json": (json.dumps(manifest) + "\n").encode(),
        base + prefix + "panel.json": panel_bytes,
    }


def build_manifest(version, panel_bytes):
    return {
        "schema_version": 1,
        "extension_id": LANE,
        "version": version,
        "compatible_surveyor_api_version": "1.0",
        "min_surveyor_version": HOST_VERSION,
        "dependencies": ["agent-console.ui.v1", "action.research.analyze_generation"],
        "entry_point": "panel.json",
        "files": [{"path": "panel.json", "sha256": hashlib.sha256(panel_bytes).hexdigest()}],
    }


class RuntimeDispatchExtensionTests(unittest.TestCase):
    def test_manifest_index_api_compatibility_and_hash(self):
        manifest, panel = read_extension()
        index = json.loads((ROOT / "agent-ui/extensions/index.json").read_text(encoding="utf-8"))
        entries = extensions.validate_index(index)
        entry = next(item for item in entries if item["extension_id"] == LANE)
        self.assertEqual(VERSION, entry["version"])
        self.assertEqual(f"{LANE}/{VERSION}/manifest.json", entry["manifest_path"])
        validated, normalized_panel = extensions.validate_manifest(
            manifest, LANE, VERSION, HOST_VERSION,
            lambda rel: (EXTENSION_DIR / rel).read_bytes(), extensions.HOST_ACTION_IDS,
        )
        self.assertEqual("1.0", validated["compatible_surveyor_api_version"])
        self.assertEqual(LANE, normalized_panel["actions"][0]["evidence_namespace"])

    def test_request_only_panel_uses_only_registered_empty_parameter_action(self):
        manifest, panel = read_extension()
        action = panel["actions"][0]
        self.assertTrue(panel["request_only"])
        self.assertIn("seed candidate 9256392A2F5A74AC", panel["summary"])
        self.assertIn("MEDI_FLOATERS is a high-confidence preset inference", panel["summary"])
        self.assertIn("10 modeled rooms (8 main + 2 dead-end; table Rooms=7)", panel["summary"])
        self.assertIn("16 analyzer-predicted targets (not verified physical count)", panel["summary"])
        self.assertIn("not verified physical count", panel["summary"])
        self.assertIn("historical", panel["summary"])
        self.assertEqual(["research.analyze_generation"], [a["action_id"] for a in panel["actions"]])
        self.assertIn(action["action_id"], extensions.HOST_ACTION_IDS)
        self.assertEqual({}, action["parameters"])
        self.assertEqual(LANE, action["evidence_namespace"])
        self.assertIn("action.research.analyze_generation", manifest["dependencies"])

    def test_action_preconditions_disable_until_workflow_nms_and_probe_are_ready(self):
        _manifest, panel = read_extension()
        preconditions = panel["actions"][0]["preconditions"]
        self.assertEqual(["workflow.idle", "nms.running", "probe.connected"], preconditions)
        states = [
            ({"workflow_idle": False, "nms_running": True, "probe_connected": True}, False),
            ({"workflow_idle": True, "nms_running": False, "probe_connected": True}, False),
            ({"workflow_idle": True, "nms_running": True, "probe_connected": False}, False),
            ({"workflow_idle": True, "nms_running": True, "probe_connected": True}, True),
        ]
        for state, expected in states:
            with self.subTest(state=state):
                self.assertEqual(expected, extensions.preconditions_met(preconditions, state)[0])

    def test_unknown_or_executable_action_content_and_bad_namespace_are_rejected(self):
        manifest, panel = read_extension()
        invalid_cases = []
        for mutate in (
            lambda action: action.update({"command": "powershell.exe"}),
            lambda action: action.update({"action_id": "research.run_arbitrary"}),
            lambda action: action.update({"parameters": {"path": "C:/"}}),
            lambda action: action.update({"evidence_namespace": "seed-lineage"}),
        ):
            broken = copy.deepcopy(panel)
            mutate(broken["actions"][0])
            payload = (json.dumps(broken) + "\n").encode()
            updated = copy.deepcopy(manifest)
            updated["files"] = [{"path": "panel.json", "sha256": hashlib.sha256(payload).hexdigest()}]
            invalid_cases.append((updated, payload))
        for broken_manifest, payload in invalid_cases:
            with self.subTest(manifest=broken_manifest["files"][0]["sha256"]):
                with self.assertRaises(extensions.ExtensionError):
                    extensions.validate_manifest(
                        broken_manifest, LANE, VERSION, HOST_VERSION,
                        lambda _rel, value=payload: value, extensions.HOST_ACTION_IDS,
                    )
        with self.assertRaisesRegex(extensions.ExtensionError, "SHA-256 mismatch"):
            extensions.validate_manifest(
                manifest, LANE, VERSION, HOST_VERSION,
                lambda _rel: b"tampered", extensions.HOST_ACTION_IDS,
            )

    def test_live_install_refresh_and_rollback_keep_old_version_available(self):
        manifest, panel = read_extension()
        panel_bytes = (json.dumps(panel, sort_keys=True) + "\n").encode()
        manifest = build_manifest(VERSION, panel_bytes)
        entry = {"extension_id": LANE, "version": VERSION, "manifest_path": f"{LANE}/{VERSION}/manifest.json"}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            extensions.install_extension(root, entry, HOST_VERSION, extensions.HOST_ACTION_IDS,
                                         remote_package(manifest, panel_bytes).__getitem__)
            self.assertEqual(VERSION, extensions.load_installed_extension(root, LANE, HOST_VERSION, extensions.HOST_ACTION_IDS)[0]["version"])

            refreshed_panel = copy.deepcopy(panel)
            refreshed_panel["summary"] = "Refreshed panel data"
            refreshed_bytes = (json.dumps(refreshed_panel, sort_keys=True) + "\n").encode()
            refreshed_manifest = build_manifest("1.0.1", refreshed_bytes)
            refreshed_entry = {"extension_id": LANE, "version": "1.0.1", "manifest_path": f"{LANE}/1.0.1/manifest.json"}
            extensions.install_extension(root, refreshed_entry, HOST_VERSION, extensions.HOST_ACTION_IDS,
                                         remote_package(refreshed_manifest, refreshed_bytes).__getitem__)
            active, active_panel = extensions.load_installed_extension(root, LANE, HOST_VERSION, extensions.HOST_ACTION_IDS)
            self.assertEqual("1.0.1", active["version"])
            self.assertEqual("Refreshed panel data", active_panel["summary"])
            extensions.activate_installed_extension(root, LANE, VERSION, HOST_VERSION, extensions.HOST_ACTION_IDS)
            rolled_back, _ = extensions.load_installed_extension(root, LANE, HOST_VERSION, extensions.HOST_ACTION_IDS)
            self.assertEqual(VERSION, rolled_back["version"])
            self.assertEqual(["1.0.1", VERSION], extensions.installed_versions(root, LANE))

    def test_lane_action_records_are_namespaced_and_collision_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = extensions.write_action_record(root, LANE, VERSION, "research.analyze_generation", "complete")
            second = extensions.write_action_record(root, LANE, VERSION, "research.analyze_generation", "complete")
            self.assertNotEqual(first, second)
            record = json.loads(first.read_text(encoding="utf-8"))
            self.assertEqual(LANE, record["extension_id"])
            self.assertEqual("research.analyze_generation", record["action_id"])

    def test_controller_live_refresh_rerenders_without_restart(self):
        class Notice:
            value = ""
            def set(self, value):
                self.value = value

        class FakeController(controller.SurveyorController):
            agent_ui_extension_installing = {LANE}
            agent_ui_extension_notice = Notice()
            agent_selected_lane = {"id": LANE}

        fake = FakeController.__new__(FakeController)
        with mock.patch.object(controller.SurveyorController, "_render_agent_ui_extension") as render, \
             mock.patch.object(controller, "_log"):
            controller.SurveyorController._finish_agent_ui_extension_update(fake, LANE, "")
        self.assertEqual(f"{LANE} UI extension refreshed without restarting Surveyor.", fake.agent_ui_extension_notice.value)
        self.assertNotIn(LANE, fake.agent_ui_extension_installing)
        render.assert_called_once_with(fake.agent_selected_lane)

    def test_uploaded_evidence_folder_uses_runtime_lane_namespace(self):
        folder = github_integration.evidence_folder("20261001T000000Z", "analyze-generation", LANE)
        self.assertRegex(folder, r"^research-uploads/20261001T000000Z-runtime-dispatch-analyze-generation-[0-9a-f]{8}$")


if __name__ == "__main__":
    unittest.main()
