import copy
import hashlib
import json
import os
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from tools import agent_ui_extensions as extensions
from tools import github_integration
from tools import surveyor_controller as controller

ROOT = Path(__file__).resolve().parents[1]
LANE = "runtime-dispatch"
VERSION = "1.0.4"
HOST_VERSION = "0.3.53"
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
        "dependencies": ["agent-console.ui.v1", "action.research.analyze_generation", "action.research.upload_runtime_capture"],
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
        self.assertIn("Latest combined report 20261008T163756Z-cd3dbef7", panel["summary"])
        self.assertIn("correlates entry 00634BC0 with return 02C0860A", panel["summary"])
        self.assertIn("The +0x10 zero is post-call and not a target", panel["summary"])
        self.assertIn("02C04977 resolver is separate", panel["summary"])
        self.assertIn("Do not use WinDbg", panel["summary"])
        self.assertIn("not a physical count", panel["summary"])
        self.assertIn("prior asset-derived 43 remains separate", panel["summary"])
        self.assertEqual(["research.analyze_generation", "research.upload_runtime_capture"], [a["action_id"] for a in panel["actions"]])
        self.assertIn(action["action_id"], extensions.HOST_ACTION_IDS)
        self.assertEqual({}, action["parameters"])
        self.assertEqual(LANE, action["evidence_namespace"])
        self.assertIn("action.research.analyze_generation", manifest["dependencies"])

    def test_saved_capture_upload_is_available_after_game_closes(self):
        _manifest, panel = read_extension()
        action = panel["actions"][1]
        self.assertEqual(["workflow.idle", "runtime.capture_saved"], action["preconditions"])
        self.assertIn("action.research.upload_runtime_capture", _manifest["dependencies"])
        self.assertIn(action["action_id"], extensions.HOST_ACTION_IDS)
        self.assertEqual(
            (False, "Needs: runtime.capture_saved"),
            extensions.preconditions_met(action["preconditions"], {"workflow_idle": True, "runtime_capture_saved": False}),
        )
        self.assertEqual(
            (True, ""),
            extensions.preconditions_met(action["preconditions"], {"workflow_idle": True, "runtime_capture_saved": True, "nms_running": False, "probe_connected": False}),
        )

    def test_runtime_capture_saved_requires_a_valid_persisted_capture(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "capture.json"
            self.assertFalse(controller._runtime_capture_saved(path))
            path.write_text(json.dumps({"schema_version": 1, "owner_plus_0x10_capture": {"read_status": "captured"}}), encoding="utf-8")
            self.assertTrue(controller._runtime_capture_saved(path))
            path.write_text(json.dumps({"schema_version": 1, "owner_plus_0x10_capture": {"read_status": "pending"}}), encoding="utf-8")
            self.assertFalse(controller._runtime_capture_saved(path))

    def test_all_saved_evidence_upload_is_deduplicated_and_marks_producers(self):
        paths, producers = github_integration.all_saved_evidence_outputs()
        self.assertEqual(len(paths), len({str(p.resolve()) for p in paths}))
        baseline_key = os.path.normcase(str((github_integration.WORK / "generation-baseline-latest.json").resolve()))
        self.assertIn("measure", producers[baseline_key])
        self.assertIn("analyze-generation", producers[baseline_key])
        summary_key = os.path.normcase(str((github_integration.WORK / "generation-measurements-summary.json").resolve()))
        self.assertIn("compare-measurements", producers[summary_key])
        corr_key = os.path.normcase(str((github_integration.WORK / "seed-room-correlation.json").resolve()))
        self.assertIn("analyze-correlation", producers[corr_key])
        self.assertIn("measure", producers[corr_key])
        exact_key = os.path.normcase(str((github_integration.WORK / "exact-root-caller-latest.json").resolve()))
        self.assertIn("analyze-generation", producers[exact_key])
        self.assertIn("upload-runtime-capture", producers[exact_key])
        self.assertEqual(["exact-root-caller-latest.json"], [p.name for p in github_integration.ACTION_OUTPUTS["upload-runtime-capture"]])

    def test_all_saved_evidence_fingerprint_tracks_contents_and_ignores_input_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "first.json"
            second = Path(tmp) / "second.json"
            first.write_text("one", encoding="utf-8")
            second.write_text("two", encoding="utf-8")
            initial = github_integration._fingerprint_upload_files([first, second])
            self.assertEqual(initial, github_integration._fingerprint_upload_files([second, first]))
            second.write_text("changed", encoding="utf-8")
            self.assertNotEqual(initial, github_integration._fingerprint_upload_files([first, second]))

    def test_auto_upload_preference_defaults_on_and_can_be_disabled_persistently(self):
        with tempfile.TemporaryDirectory() as tmp:
            setting = Path(tmp) / "auto-upload-settings.json"
            with mock.patch.object(controller, "AUTO_UPLOAD_SETTINGS", setting):
                self.assertTrue(controller._load_auto_upload_setting())
                setting.write_text(json.dumps({"schema_version": 1, "enabled": False}), encoding="utf-8")
                self.assertFalse(controller._load_auto_upload_setting())

    def test_controller_exposes_and_checks_the_auto_upload_toggle(self):
        source = (ROOT / "tools" / "surveyor_controller.py").read_text(encoding="utf-8")
        self.assertIn('text="Automatically upload new probe captures and share updated evidence with all lanes"', source)
        self.assertIn('if not self.auto_upload_enabled.get():', source)
        self.assertIn('"--only-if-changed"', source)

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

    def test_published_human_action_remains_clickable_without_a_prior_upload_receipt(self):
        _manifest, panel = read_extension()
        action = panel["actions"][0]
        idle_without_nms = {"workflow_idle": True, "nms_running": False, "probe_connected": False, "upload_confirmed": True}
        self.assertTrue(extensions.action_button_enabled(
            action["preconditions"], idle_without_nms, request_only=True, requested=True,
        ))
        self.assertFalse(extensions.action_button_enabled(
            action["preconditions"], idle_without_nms, request_only=True, requested=False,
        ))
        self.assertFalse(extensions.action_button_enabled(
            action["preconditions"], {**idle_without_nms, "workflow_idle": False}, request_only=True, requested=True,
        ))
        # A previous receipt is informational; toggling it never changes readiness.
        self.assertEqual(
            extensions.action_button_enabled(action["preconditions"], idle_without_nms, request_only=True, requested=True),
            extensions.action_button_enabled(action["preconditions"], {**idle_without_nms, "upload_confirmed": False}, request_only=True, requested=True),
        )

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
            refreshed_panel["summary"] = "Panel refreshed test summary"
            refreshed_bytes = (json.dumps(refreshed_panel, sort_keys=True) + "\n").encode()
            refreshed_manifest = build_manifest("1.0.4", refreshed_bytes)
            refreshed_entry = {"extension_id": LANE, "version": "1.0.4", "manifest_path": f"{LANE}/1.0.4/manifest.json"}
            extensions.install_extension(root, refreshed_entry, HOST_VERSION, extensions.HOST_ACTION_IDS,
                                         remote_package(refreshed_manifest, refreshed_bytes).__getitem__)
            active, active_panel = extensions.load_installed_extension(root, LANE, HOST_VERSION, extensions.HOST_ACTION_IDS)
            self.assertEqual("1.0.4", active["version"])
            self.assertEqual("Panel refreshed test summary", active_panel["summary"])
            extensions.activate_installed_extension(root, LANE, VERSION, HOST_VERSION, extensions.HOST_ACTION_IDS)
            rolled_back, _ = extensions.load_installed_extension(root, LANE, HOST_VERSION, extensions.HOST_ACTION_IDS)
            self.assertEqual(VERSION, rolled_back["version"])
            self.assertEqual(["1.0.4", VERSION], extensions.installed_versions(root, LANE))

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
            def _update_agent_extension_summary(self):
                self.summary_refreshed = True

        fake = FakeController.__new__(FakeController)
        with mock.patch.object(controller.SurveyorController, "_render_agent_ui_extension") as render, \
             mock.patch.object(controller, "_log"):
            controller.SurveyorController._finish_agent_ui_extension_update(fake, LANE, "")
        self.assertEqual(f"{LANE} UI extension refreshed without restarting Surveyor.", fake.agent_ui_extension_notice.value)
        self.assertNotIn(LANE, fake.agent_ui_extension_installing)
        self.assertTrue(fake.summary_refreshed)
        render.assert_called_once_with(fake.agent_selected_lane)

    def test_uploaded_evidence_folder_uses_runtime_lane_namespace(self):
        folder = github_integration.evidence_folder("20261001T000000Z", "analyze-generation", LANE)
        self.assertRegex(folder, r"^research-uploads/20261001T000000Z-runtime-dispatch-analyze-generation-[0-9a-f]{8}$")


if __name__ == "__main__":
    unittest.main()
