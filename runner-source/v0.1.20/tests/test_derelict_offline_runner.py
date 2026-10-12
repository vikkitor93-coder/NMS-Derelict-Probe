import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from derelict_offline import local_runner as worker
from derelict_offline.runner_protocol import digest, publish_request, validate_request


class RunnerTests(unittest.TestCase):
    def fixture(self, root):
        (root / ".local").mkdir()
        path = root / "source.py"
        path.write_text("version=1\n")
        files = {"source.py": path}
        request = {"schema": 1, "request_id": "a" * 32, "action": "offline-check", "source_sha256": digest(files)}
        return files, request

    def test_schema_rejects_other_runner_and_arbitrary_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            files, request = self.fixture(Path(tmp))
            for value in ({**request, "action": "build-and-h2"}, {**request, "command": "echo test"},
                          {**request, "schema": True}, {**request, "request_id": "../other"}):
                with self.assertRaises(ValueError):
                    validate_request(value)

    def test_pending_request_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = publish_request(root, "f" * 64)
            with self.assertRaises(FileExistsError):
                publish_request(root, "e" * 64)
            self.assertEqual(first, json.loads((root / "requests/ready.json").read_text()))

    def test_claim_survives_restart_and_invalid_request_quarantined(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".local").mkdir()
            first = publish_request(root, "f" * 64)
            self.assertEqual(first, worker.claim(root))
            with self.assertRaisesRegex(ValueError, "interrupted-request"):
                worker.claim(root)
            (root / ".local/claimed-request.json").unlink()
            (root / "requests/ready.json").write_text('{"command":"bad"}')
            with self.assertRaisesRegex(ValueError, "invalid-request"):
                worker.claim(root)
            self.assertTrue((root / ".local/rejected-request.json").is_file())

    def test_snapshot_detects_edits_and_preserves_copied_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files, request = self.fixture(root)
            destination = root / "snapshot"
            worker.capture_snapshot(files, destination, request["source_sha256"])
            files["source.py"].write_text("version=2\n")
            self.assertEqual("version=1\n", (destination / "source.py").read_text())
            with self.assertRaisesRegex(ValueError, "source-changed"):
                worker.capture_snapshot(files, destination, request["source_sha256"])

    def run_fixture(self, root, fail=None, edit=False, cancel=False, export=False):
        files, request = self.fixture(root)
        if export:
            request["action"] = "offline-check-and-export"
        calls = []
        def fake(argv, cwd, timeout=600):
            command = argv[3]
            calls.append(command)
            if command == "package":
                with zipfile.ZipFile(argv[-1], "w") as archive:
                    archive.writestr("source.py", "version=1\n")
            elif "--out" in argv:
                Path(argv[-1]).write_text('{"errors":[]}')
            if edit:
                files["source.py"].write_text("version=2\n")
            if cancel:
                raise KeyboardInterrupt()
            return 7 if command == fail else 0
        with patch.object(worker, "source_files", return_value=files), patch.object(worker, "run_command", side_effect=fake):
            result = worker.execute(root, request, sys.executable)
        return result, calls, request

    def test_fixed_pipeline_pins_outputs_and_produces_complete_artifact_paths(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            root = Path(tmp)
            result, calls, request = self.run_fixture(root)
            self.assertEqual(["package", "test", "diagnose", "code", "emulate"], calls)
            self.assertEqual("passed", result["status"])
            self.assertFalse(result["root_generation_verified"])
            self.assertEqual(result, json.loads((root / ".local/latest-result.json").read_text()))
            folder = root / "reports" / request["request_id"]
            self.assertTrue((folder / "source.zip").is_file())
            with zipfile.ZipFile(folder / "runner-evidence.zip") as archive:
                self.assertIn("result.json", archive.namelist())
                self.assertNotIn("source.zip", archive.namelist())
            self.assertNotIn(str(root), (root / ".local/latest.log").read_text())

    def test_report_contains_exact_tested_ai_handoff_and_scheduled_prompt(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            root = Path(tmp)
            files, request = self.fixture(root)
            handoff = root / "AI_HANDOFF.md"
            prompt = root / "GITHUB_CHECK_PROMPT.md"
            handoff.write_text("handoff from pinned snapshot\n")
            prompt.write_text("scheduled instructions from pinned snapshot\n")
            files.update({"AI_HANDOFF.md": handoff, "GITHUB_CHECK_PROMPT.md": prompt})
            request["source_sha256"] = digest(files)
            def fake(argv, cwd, timeout=600):
                command = argv[3]
                if command == "package":
                    with zipfile.ZipFile(argv[-1], "w") as archive:
                        archive.writestr("AI_HANDOFF.md", handoff.read_text())
                        archive.writestr("GITHUB_CHECK_PROMPT.md", prompt.read_text())
                elif "--out" in argv:
                    Path(argv[-1]).write_text('{"errors":[]}')
                return 0
            with patch.object(worker, "source_files", return_value=files), \
                 patch.object(worker, "run_command", side_effect=fake):
                worker.execute(root, request, sys.executable)
            report = root / "reports" / request["request_id"]
            self.assertEqual(handoff.read_text(), (report / "AI_HANDOFF.md").read_text())
            self.assertEqual(prompt.read_text(), (report / "GITHUB_CHECK_PROMPT.md").read_text())
            with zipfile.ZipFile(report / "runner-evidence.zip") as archive:
                self.assertEqual(handoff.read_bytes(), archive.read("AI_HANDOFF.md"))
                self.assertEqual(prompt.read_bytes(), archive.read("GITHUB_CHECK_PROMPT.md"))

    def test_failure_stops_later_stages_and_keeps_source_zip(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            result, calls, _ = self.run_fixture(Path(tmp), fail="test")
            self.assertEqual(["package", "test"], calls)
            self.assertEqual("failed", result["status"])
            self.assertEqual(["tests-failed"], result["errors"])
            self.assertTrue(result["source_zip_available"])

    def test_changed_sources_never_claim_passed(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            result, _, _ = self.run_fixture(Path(tmp), edit=True)
            self.assertEqual("stale", result["status"])
            self.assertIn("source-changed-during-run", result["errors"])

    def test_cancel_is_recorded_and_artifacts_remain_reviewable(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            result, calls, _ = self.run_fixture(Path(tmp), cancel=True)
            self.assertEqual("cancelled", result["status"])
            self.assertEqual(["package"], calls)
            self.assertIn("user-stopped", result["errors"])

    def test_export_requires_explicit_exe_without_game_probe(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            result, calls, _ = self.run_fixture(Path(tmp), export=True)
            self.assertEqual("failed", result["status"])
            self.assertIn("nms-exe-not-selected", result["errors"])
            self.assertNotIn("export", calls)

    def test_stale_request_and_reused_id_do_not_execute(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files, request = self.fixture(root)
            with patch.object(worker, "source_files", return_value=files), patch.object(worker, "run_command") as run:
                with self.assertRaisesRegex(ValueError, "stale-request"):
                    worker.execute(root, {**request, "source_sha256": "b" * 64}, sys.executable)
                (root / "reports" / request["request_id"]).mkdir(parents=True)
                with self.assertRaises(FileExistsError):
                    worker.execute(root, request, sys.executable)
                run.assert_not_called()

    def test_report_limit_stops_without_deleting_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files, request = self.fixture(root)
            for index in range(100):
                (root / "reports" / str(index)).mkdir(parents=True)
            with patch.object(worker, "source_files", return_value=files):
                with self.assertRaisesRegex(ValueError, "report-limit"):
                    worker.execute(root, request, sys.executable)
            self.assertEqual(100, len(list((root / "reports").iterdir())))

    def test_export_cache_rejects_wrong_inputs_and_tampering(self):
        from derelict_offline.common import sha256
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp)
            cached = local / "cached-offline-evidence.zip"
            cached.write_bytes(b"valid-export")
            key = {"code_sha256": "a", "exe_sha256": "b"}
            (local / "export-cache.json").write_text(json.dumps({"key": key, "zip_sha256": sha256(cached)}))
            target = local / "target.zip"
            self.assertTrue(worker.cached_export(local, key, target))
            self.assertFalse(worker.cached_export(local, {**key, "exe_sha256": "c"}, target))
            cached.write_bytes(b"tampered")
            self.assertFalse(worker.cached_export(local, key, target))

    def test_completed_check_cache_is_pinned_to_source_action_and_executable_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            key = {"source_sha256": "a" * 64, "action": "offline-check", "exe_sha256": None}
            self.assertFalse(worker.has_completed_automatic_check(root, key))
            worker.record_automatic_check(root, key, "passed")
            self.assertTrue(worker.has_completed_automatic_check(root, key))
            self.assertFalse(worker.has_completed_automatic_check(root, {**key, "source_sha256": "b" * 64}))
            self.assertFalse(worker.has_completed_automatic_check(root, {**key, "action": "offline-check-and-export"}))
            (root / ".local/automatic-check.json").unlink()
            worker.record_automatic_check(root, key, "cancelled")
            self.assertFalse(worker.has_completed_automatic_check(root, key))

    def test_update_feed_urls_match_nested_published_branch_layout(self):
        from derelict_offline.update_protocol import UPDATE_ARCHIVE_BASE_URL, UPDATE_URL, validate_feed
        self.assertEqual(UPDATE_ARCHIVE_BASE_URL + "latest.json", UPDATE_URL)
        feed = {"schema": 1, "version": "0.1.12", "source_commit": "a" * 40,
                "source_sha256": "b" * 64, "archive_url": UPDATE_ARCHIVE_BASE_URL + "NMS-Runner-v0.1.12.zip",
                "archive_sha256": "c" * 64, "archive_bytes": 1,
                "files": {"__init__.py": {"bytes": 1, "sha256": "d" * 64}},
                "tests_status": "passed", "tests_count": 1, "tests_output_sha256": "e" * 64}
        self.assertIs(validate_feed(feed), feed)
        with self.assertRaisesRegex(ValueError, "untrusted-update-host"):
            validate_feed({**feed, "archive_url": UPDATE_ARCHIVE_BASE_URL.replace("/runner-updates/runner-updates/", "/runner-updates/") + "NMS-Runner-v0.1.12.zip"})

    def test_update_feed_poll_interval_is_ten_seconds(self):
        from derelict_offline.update_protocol import POLL_SECONDS
        self.assertEqual(10, POLL_SECONDS)

    def test_updater_records_phase_and_local_diagnostic_log(self):
        from derelict_offline.update_protocol import record_update_state
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record_update_state(root, "pending", phase="waiting-for-runner-exit", version="0.1.20",
                                source_sha256="a" * 64, elapsed_seconds=10)
            state = json.loads((root / ".local/update-state.json").read_text())
            self.assertEqual("pending", state["status"])
            self.assertEqual("waiting-for-runner-exit", state["phase"])
            self.assertEqual("0.1.20", state["version"])
            self.assertEqual("a" * 64, state["source_sha256"])
            self.assertTrue(state["updated_at"].endswith("Z"))
            log = (root / ".local/update-installer.log").read_text()
            self.assertIn("waiting-for-runner-exit", log)
            self.assertIn("elapsed_seconds=10", log)

    def test_updater_breaks_away_from_worker_cleanup_job(self):
        from derelict_offline import update_protocol
        from derelict_offline.windows_job import JOB_OBJECT_LIMIT_BREAKAWAY_OK, JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staging = root / ".local/updates/staged"
            staging.mkdir(parents=True)
            with patch.object(update_protocol.subprocess, "Popen") as launch:
                update_protocol.launch_update(root, staging)
            kwargs = launch.call_args.kwargs
            self.assertTrue(kwargs["stdout"].name.endswith("update-installer.log"))
            self.assertEqual(kwargs["stdout"], kwargs["stderr"])
            if os.name == "nt":
                self.assertTrue(kwargs["creationflags"] & subprocess.CREATE_BREAKAWAY_FROM_JOB)
            limits = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | JOB_OBJECT_LIMIT_BREAKAWAY_OK
            self.assertTrue(limits & JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE)
            self.assertTrue(limits & JOB_OBJECT_LIMIT_BREAKAWAY_OK)
            self.assertTrue((root / ".local/update-installer.log").is_file())

    def test_updater_parent_wait_times_out_instead_of_waiting_forever(self):
        from derelict_offline.update_protocol import _wait_for_process
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(5)"])
        try:
            with self.assertRaisesRegex(ValueError, "update-parent-exit-timeout"):
                _wait_for_process(child.pid, timeout=0.05)
        finally:
            child.kill()
            child.wait(timeout=5)

    def test_legacy_update_channel_is_repaired_to_nested_published_feed(self):
        from derelict_offline.update_protocol import LEGACY_UPDATE_URL, UPDATE_URL
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp)
            worker.atomic_json(local / "update-channel.json",
                               {"schema": 1, "enabled": True, "feed_url": LEGACY_UPDATE_URL})
            channel = worker.load_update_channel(local, UPDATE_URL)
            self.assertEqual(UPDATE_URL, channel["feed_url"])
            self.assertEqual(channel, json.loads((local / "update-channel.json").read_text()))
            worker.atomic_json(local / "update-channel.json",
                               {"schema": 1, "enabled": True, "feed_url": "https://example.com/feed.json"})
            with self.assertRaisesRegex(ValueError, "invalid-update-channel"):
                worker.load_update_channel(local, UPDATE_URL)

    def test_nms_executable_selection_is_persisted_and_hash_locked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            selected = root / "NMS.exe"
            selected.write_bytes(b"pinned executable bytes")
            self.assertEqual(selected.resolve(), worker.save_executable_selection(root, selected))
            self.assertEqual(selected.resolve(), worker.load_executable_selection(root))
            selected.write_bytes(b"changed executable bytes")
            with self.assertRaisesRegex(ValueError, "nms-exe-selection-missing-or-changed"):
                worker.load_executable_selection(root)
            with self.assertRaisesRegex(ValueError, "selected-file-not-nms-exe"):
                worker.save_executable_selection(root, root / "other.exe")

    def test_second_instance_cannot_overlap(self):
        with tempfile.TemporaryDirectory() as tmp:
            with worker.instance_lock(Path(tmp)):
                with self.assertRaises(OSError):
                    with worker.instance_lock(Path(tmp)):
                        self.fail("second worker acquired lock")
            with worker.instance_lock(Path(tmp)):
                pass

    def test_timeout_kills_owned_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(subprocess.TimeoutExpired):
                worker.run_command([sys.executable, "-c", "import time;time.sleep(10)"], Path(tmp), timeout=0.1)

    def test_watch_runs_stable_source_once_and_is_idle_afterwards(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            root = Path(tmp)
            files, _ = self.fixture(root)
            with patch.object(worker, "source_files", return_value=files), \
                 patch.object(worker, "healthy_python", return_value=sys.executable), \
                 patch.object(worker, "execute", return_value={"status":"passed"}) as run, \
                 patch.object(worker.time, "sleep", side_effect=[None, None, KeyboardInterrupt()]):
                self.assertEqual(0, worker.watch(root))
            self.assertEqual(1, run.call_count)

    def test_watch_skips_identical_completed_job_after_restart(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            root = Path(tmp)
            files, request = self.fixture(root)
            key = worker.automatic_check_key(request["source_sha256"], "offline-check", None)
            worker.record_automatic_check(root, key, "passed")
            with patch.object(worker, "source_files", return_value=files), \
                 patch.object(worker, "healthy_python", return_value=sys.executable), \
                 patch("derelict_offline.github_exchange.config", return_value=None), \
                 patch.object(worker.time, "sleep", side_effect=[None, KeyboardInterrupt()]), \
                 patch.object(worker, "execute") as run:
                self.assertEqual(0, worker.watch(root))
            run.assert_not_called()

    def test_bundle_allowlist_excludes_private_and_unrelated_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "result.json").write_text('{}')
            (root / "private.txt").write_text('secret')
            (root / "NMS.exe").write_bytes(b'not-exportable')
            with zipfile.ZipFile(worker.bundle(root)) as archive:
                self.assertEqual(["result.json"], archive.namelist())

    def test_healthy_dependency_is_not_reinstalled(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(worker, "run_command", return_value=0) as run:
                python = worker.healthy_python(Path(tmp))
            self.assertEqual(sys.executable, python)
            self.assertEqual(1, run.call_count)

    def test_healthy_unicorn_smoke_result_is_reused_only_for_identical_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            environment = root / ".unicorn-venv"
            candidate = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            candidate.parent.mkdir(parents=True)
            candidate.write_bytes(b"python")
            site = (environment / "Lib/site-packages" if os.name == "nt"
                    else environment / "lib/python3.13/site-packages")
            package = site / "unicorn"
            package.mkdir(parents=True)
            (package / "__init__.py").write_bytes(b"version='2.1.4'")
            fingerprint = worker.unicorn_health_fingerprint(root, candidate)
            worker.atomic_json(root / ".local/unicorn-health.json",
                               {"schema": 1, "status": "passed", "fingerprint": fingerprint})
            with patch.object(worker, "run_command") as run:
                self.assertEqual(str(candidate), worker.healthy_python(root))
            run.assert_not_called()
            (package / "__init__.py").write_bytes(b"version='changed'")
            with patch.object(worker, "run_command", return_value=0) as run:
                worker.healthy_python(root)
            run.assert_called_once()

    def test_missing_dependency_installs_once_and_failures_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(worker, "run_command", side_effect=[1, 0]) as run:
                python = worker.healthy_python(root)
            self.assertIn(".unicorn-venv", python)
            self.assertEqual(2, run.call_count)
            with patch.object(worker, "run_command", side_effect=[1, 8]):
                with self.assertRaisesRegex(ValueError, "unicorn-setup-failed"):
                    worker.healthy_python(root)


if __name__ == "__main__":
    unittest.main()
