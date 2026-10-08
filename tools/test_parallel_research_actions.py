#!/usr/bin/env python3
"""Run Surveyor research commands concurrently in isolated test data roots.

This is a test harness, not the production Upload All workflow: it never uploads
to GitHub and it never writes to the user's normal Surveyor data directory.
Each worker receives a snapshot of existing inputs and a private LOCALAPPDATA.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ACTION_SPECS = [
    ("research.analyze_seed_function", "seed-lineage", "Analyze-Dungeon-Seed-Function.cmd"),
    ("research.extract_upstream_callers", "dungeon-decompile", "Extract-Dungeon-Upstream-Callers.cmd"),
    ("research.extract_exact_root_caller", "dungeon-decompile", "Extract-Exact-Root-Caller-Code.cmd"),
    ("research.resolve_root_vtable", "dungeon-decompile", "Resolve-Exact-Root-VTable.cmd"),
    ("research.extract_caller_code", "seed-lineage", "Extract-Dungeon-Caller-Code.cmd"),
    ("research.measure_generation", "seed-lineage", "Measure-Derelict-Generation.cmd"),
    ("research.prepare_assets", "metadata", "Prepare-Crate-Assets.cmd"),
    ("research.analyze_generation", "shared", "Analyze-Generation-Baseline.cmd"),
]
UPLOAD_ONLY_ACTIONS = [
    {"action_id": "research.upload_runtime_capture", "status": "not_run_upload_disabled",
     "reason": "This test harness never publishes evidence to GitHub."}
]
OUTPUTS_BY_ACTION = {
    "research.analyze_seed_function": ["dungeon-seed-function-analysis-latest.json"],
    "research.extract_upstream_callers": ["dungeon-upstream-callers-latest.json"],
    "research.extract_exact_root_caller": ["exact-root-caller-code-latest.json"],
    "research.resolve_root_vtable": ["exact-root-vtable-latest.json"],
    "research.extract_caller_code": ["dungeon-caller-code-latest.json"],
    "research.measure_generation": ["generation-baseline-latest.json", "generation-measurements-summary.json", "generation-measurements.csv", "seed-room-correlation.json"],
    "research.prepare_assets": ["room-crate-index.json", "asset-calculation-latest.json", "crate-target-discovery.json"],
    "research.analyze_generation": ["generation-baseline-latest.json", "exact-root-caller-latest.json"],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _redact_text(value: str, *paths: Path) -> str:
    for path in sorted((str(p) for p in paths if str(p)), key=len, reverse=True):
        value = value.replace(path, "<LOCAL_PATH>")
    return re.sub(r"(?i)\b[A-Z]:\\[^\r\n\"']+", "<LOCAL_PATH>", value)


def _redact_json_paths(value: Any) -> Any:
    """Remove absolute Windows paths from nested evidence before sharing it."""
    if isinstance(value, str):
        return re.sub(r"(?i)\b[A-Z]:\\[^\r\n\"']+", "<LOCAL_PATH>", value)
    if isinstance(value, list):
        return [_redact_json_paths(item) for item in value]
    if isinstance(value, dict):
        return {key: _redact_json_paths(item) for key, item in value.items()}
    return value


def append_queue(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


class ProgressDashboard:
    """Render one live progress row per action without interleaved child output."""
    def __init__(self, specs: list[tuple[str, str, str]]) -> None:
        self.rows = {spec[0]: {"state": "QUEUED", "percent": None, "stage": "Waiting to start"} for spec in specs}
        self.tty = bool(sys.stdout.isatty())
        self._vt_enabled = self._enable_windows_vt() if self.tty and os.name == "nt" else self.tty
        self._tick = 0

    @staticmethod
    def _enable_windows_vt() -> bool:
        try:
            import ctypes
            kernel = ctypes.windll.kernel32
            handle = kernel.GetStdHandle(-11)
            mode = ctypes.c_uint()
            if not kernel.GetConsoleMode(handle, ctypes.byref(mode)):
                return False
            return bool(kernel.SetConsoleMode(handle, mode.value | 0x0004))
        except Exception:
            return False

    def update(self, action_id: str, *, state: str | None = None,
               percent: int | None = None, stage: str | None = None,
               indeterminate: bool = False) -> None:
        row = self.rows[action_id]
        if state is not None:
            row["state"] = state
        if indeterminate:
            row["percent"] = None
        elif percent is not None:
            row["percent"] = max(0, min(100, percent))
        if stage is not None:
            row["stage"] = stage
        if not (self.tty and self._vt_enabled):
            value = row["percent"]
            bar = "|........." if value is None else "#" * round(value / 10) + "." * (10 - round(value / 10))
            pct = "--%" if value is None else f"{value}%"
            print(f"[{row['state']}] [{bar}] {pct} {action_id} — {row['stage']}", flush=True)

    def render(self) -> None:
        self._tick += 1
        lines = ["Parallel research actions — live progress",
                 "Phase bars are milestones; download stages show actual transfer percent. GitHub uploads: disabled"]
        for action_id, row in self.rows.items():
            pct = row["percent"]
            if pct is None:
                spin = "|/-\\"[self._tick % 4] if row["state"] == "RUNNING" else " "
                bar = spin + " " * 9
                ptxt = " --%"
            else:
                filled = round(pct / 10)
                bar = "#" * filled + "." * (10 - filled)
                ptxt = f" {pct:3d}%"
            stage = str(row["stage"]).replace("\r", " ").replace("\n", " ")[:60]
            lines.append(f"{row['state']:8} [{bar}]{ptxt} {action_id}: {stage}")
        if self.tty and self._vt_enabled:
            sys.stdout.write("\x1b[2J\x1b[H" + "\n".join(lines) + "\n")
            sys.stdout.flush()
        # Without ANSI support, update() prints only when a real state/stage changes.

    def close(self) -> None:
        if self.tty and self._vt_enabled:
            sys.stdout.write("\x1b[?25h")
            sys.stdout.flush()


def _execute_streaming(command: list[str], cwd: Path, env: dict[str, str], action_id: str,
                       progress_events: queue.Queue[dict[str, Any]], timeout_seconds: int = 7200
                       ) -> tuple[int, str, bool]:
    proc = subprocess.Popen(command, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, bufsize=1, errors="replace")
    lines: queue.Queue[str | None] = queue.Queue()

    def pump_output() -> None:
        assert proc.stdout is not None
        for output_line in proc.stdout:
            lines.put(output_line)
        lines.put(None)

    reader = threading.Thread(target=pump_output, name=f"output-{action_id}", daemon=True)
    reader.start()
    captured: list[str] = []
    eof = False
    timed_out = False
    started = time.monotonic()
    while not (eof and proc.poll() is not None):
        if not timed_out and time.monotonic() - started > timeout_seconds:
            timed_out = True
            proc.kill()
        try:
            line = lines.get(timeout=0.15)
        except queue.Empty:
            continue
        if line is None:
            eof = True
            continue
        marker = re.match(r"^\s*NMSDS_PROGRESS:(-1|\d{1,3})\|(.*)$", line.rstrip())
        if marker:
            value = int(marker.group(1))
            progress_events.put({"action_id": action_id, "percent": None if value < 0 else value,
                                 "indeterminate": value < 0, "stage": marker.group(2).strip()})
        else:
            captured.append(line)
    reader.join(timeout=2)
    if proc.stdout:
        proc.stdout.close()
    return proc.wait(), "".join(captured), timed_out


def _copy_input_snapshot(source: Path, destination: Path, *, link_extracted: bool) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for name in ("latest.json", "nms-executable.txt"):
        src = source / name
        if src.is_file():
            shutil.copy2(src, destination / name)
    src_work = source / "asset-work-v1"
    dst_work = destination / "asset-work-v1"
    if not src_work.is_dir():
        return
    dst_work.mkdir(parents=True, exist_ok=True)
    for src in src_work.iterdir():
        target = dst_work / src.name
        if src.is_file():
            shutil.copy2(src, target)
        elif src.name == "extracted" and link_extracted:
            if os.name == "nt":
                linked = subprocess.run(["cmd.exe", "/c", f'mklink /J "{target}" "{src}"'],
                                        text=True, capture_output=True, check=False)
                if linked.returncode == 0:
                    continue
            # Junction creation can fail on managed Windows machines even when
            # the source is readable (for example, endpoint policy or path
            # restrictions). These analysis workers only read extracted assets,
            # so make an isolated directory tree using same-volume hard links;
            # copy individual files when hard links are unavailable (including
            # cross-volume runs). This avoids requiring symlink privileges and
            # avoids duplicating the often-large asset payload in the common case.
            target.mkdir(parents=True, exist_ok=True)
            for root, dirs, files in os.walk(src):
                root_path = Path(root)
                relative = root_path.relative_to(src)
                dest_root = target / relative
                dest_root.mkdir(parents=True, exist_ok=True)
                for dirname in dirs:
                    (dest_root / dirname).mkdir(exist_ok=True)
                for filename in files:
                    source_file = root_path / filename
                    destination_file = dest_root / filename
                    try:
                        os.link(source_file, destination_file)
                    except OSError:
                        shutil.copy2(source_file, destination_file)


def _command(action_id: str, workflow: str, outdir: Path) -> list[str] | None:
    py = sys.executable
    tools = ROOT / "tools"
    direct = {
        "research.analyze_seed_function": [py, str(tools / "analyze_nms_seed_function.py"), "--out", str(outdir / "dungeon-seed-function-analysis-latest.json")],
        "research.extract_upstream_callers": [py, str(tools / "extract_nms_upstream_callers.py"), "--out", str(outdir / "dungeon-upstream-callers-latest.json")],
        "research.extract_exact_root_caller": [py, str(tools / "extract_exact_root_caller_code.py"), "--out", str(outdir / "exact-root-caller-code-latest.json")],
        "research.resolve_root_vtable": [py, str(tools / "resolve_exact_root_vtable.py"), "--out", str(outdir / "exact-root-vtable-latest.json")],
        "research.extract_caller_code": [py, str(tools / "extract_nms_caller_code.py"), "--out", str(outdir / "dungeon-caller-code-latest.json")],
    }
    if action_id in direct:
        return direct[action_id]
    if os.name != "nt":
        return None
    ps = shutil.which("powershell.exe") or shutil.which("pwsh.exe")
    if not ps:
        return None
    script = _powershell_script_name(workflow)
    return [ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / script)]


def _powershell_script_name(workflow: str) -> str:
    """Resolve the CMD-facing action name to the PowerShell script it wraps."""
    return workflow[:-4] + ".ps1" if workflow.lower().endswith(".cmd") else workflow


def _artifact_records(action_id: str, local_data: Path, outdir: Path, initial_state: dict[str, tuple[str, int]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    names = set(OUTPUTS_BY_ACTION[action_id])
    candidates = [p for root in (local_data, outdir) if root.exists() for p in root.rglob("*")
                  if p.is_file() and p.name in names]
    for path in sorted(candidates):
        raw = path.read_bytes()
        try:
            relative_path = path.relative_to(local_data)
        except ValueError:
            relative_path = Path("action-outputs") / path.name
        if relative_path.parts[:1] != ("action-outputs",):
            initial = initial_state.get(str(relative_path).replace("\\", "/"))
            current = (hashlib.sha256(raw).hexdigest(), path.stat().st_mtime_ns)
            if initial == current:
                continue
        item: dict[str, Any] = {
            "path": str(relative_path).replace("\\", "/"),
            "size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
        if path.suffix.lower() == ".json":
            try:
                item["data"] = _redact_json_paths(json.loads(raw.decode("utf-8-sig")))
            except (UnicodeDecodeError, json.JSONDecodeError):
                item["text"] = raw.decode("utf-8", errors="replace")
        elif path.suffix.lower() in {".csv", ".txt", ".jsonl"}:
            item["text"] = raw.decode("utf-8", errors="replace")
        records.append(item)
    return records


def _run_action(spec: tuple[str, str, str], run_dir: Path, input_root: Path,
                source_env: dict[str, str], progress_events: queue.Queue[dict[str, Any]]) -> dict[str, Any]:
    action_id, lane, workflow = spec
    worker = run_dir / "workers" / action_id.replace(".", "_")
    local = worker / "local-appdata"
    outdir = worker / "outputs"
    local_data = local / "NMSDerelictSurveyor"
    outdir.mkdir(parents=True, exist_ok=True)
    _copy_input_snapshot(
        input_root,
        local_data,
        link_extracted=action_id in {"research.measure_generation", "research.analyze_generation"},
    )
    initial_state: dict[str, tuple[str, int]] = {}
    for path in local_data.rglob("*"):
        if path.is_file():
            raw = path.read_bytes()
            initial_state[str(path.relative_to(local_data)).replace("\\", "/")] = (hashlib.sha256(raw).hexdigest(), path.stat().st_mtime_ns)
    command = _command(action_id, workflow, outdir)
    if command is None:
        return {"action_id": action_id, "lane": lane, "status": "unsupported_platform",
                "detail": "This action requires Windows PowerShell and is not executed on this platform.", "artifacts": []}
    env = source_env.copy()
    env.update({
        "LOCALAPPDATA": str(local),
        "APPDATA": str(worker / "roaming-appdata"),
        "NMSDS_NONINTERACTIVE": "1",
        "PIP_USER": "1",
        "PYTHONUSERBASE": str(worker / "python-user-base"),
        "NMSDS_PARALLEL_TEST": "1",
    })
    started = time.monotonic()
    try:
        returncode, output, timed_out = _execute_streaming(command, ROOT, env, action_id, progress_events)
        artifacts = _artifact_records(action_id, local_data, outdir, initial_state)
        status = "timed_out" if timed_out else ("complete" if returncode == 0 and artifacts else "failed")
        detail = "Timed out after two hours." if timed_out else ("" if returncode != 0 or artifacts else "Command returned success but wrote no declared result artifact.")
        return {
            "action_id": action_id, "lane": lane, "status": status, "return_code": returncode,
            "detail": detail,
            "duration_seconds": round(time.monotonic() - started, 3), "workflow": workflow,
            "executable": Path(command[0]).name,
            "output": _redact_text(output, ROOT, worker, local_data),
            "artifacts": artifacts,
        }
    except OSError as exc:
        return {"action_id": action_id, "lane": lane, "status": "failed_to_start", "detail": str(exc), "artifacts": _artifact_records(action_id, local_data, outdir, initial_state)}


def _trigger_record(kind: str, session_file: str | None = None,
                   session_sha256: str | None = None) -> dict[str, str | None]:
    allowed = {"manual_button", "automatic_saved_session", "command_line"}
    if kind not in allowed:
        raise ValueError(f"Unknown parallel research trigger: {kind}")
    return {
        "kind": kind,
        "session_file": Path(session_file).name if session_file else None,
        "session_sha256": session_sha256,
    }


def run_test(output_dir: Path | None = None, max_workers: int = 8, *,
             trigger_kind: str = "command_line", trigger_session_file: str | None = None,
             trigger_session_sha256: str | None = None) -> tuple[Path, Path, int]:
    localappdata = os.environ.get("LOCALAPPDATA")
    input_root = Path(localappdata) / "NMSDerelictSurveyor" if localappdata else Path("__no_localappdata__")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    run_dir = (output_dir or ROOT / "parallel-action-tests" / run_id).resolve()
    run_dir.mkdir(parents=True, exist_ok=False)
    queue_path = run_dir / "queue.jsonl"
    final_path = run_dir / "combined-results.json"
    started_utc = utc_now()
    trigger = _trigger_record(trigger_kind, trigger_session_file, trigger_session_sha256)
    append_queue(queue_path, {"event": "run_started", "run_id": run_id, "utc": started_utc, "workers": max_workers,
                              "actions": [s[0] for s in ACTION_SPECS], "trigger": trigger})
    results: list[dict[str, Any]] = []
    source_env = os.environ.copy()
    progress_events: queue.Queue[dict[str, Any]] = queue.Queue()
    dashboard = ProgressDashboard(ACTION_SPECS)
    dashboard.render()
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, max_workers)) as pool:
        future_specs = {}
        for spec in ACTION_SPECS:
            append_queue(queue_path, {"event": "action_started", "action_id": spec[0], "lane": spec[1], "utc": utc_now()})
            dashboard.update(spec[0], state="RUNNING", stage="Launching isolated action")
            future_specs[pool.submit(_run_action, spec, run_dir, input_root, source_env, progress_events)] = spec
        pending = set(future_specs)
        try:
            while pending:
                while True:
                    try:
                        event = progress_events.get_nowait()
                    except queue.Empty:
                        break
                    event["event"] = "action_progress"
                    event["utc"] = utc_now()
                    append_queue(queue_path, event)
                    dashboard.update(event["action_id"], percent=event["percent"], stage=event["stage"],
                                     indeterminate=event.get("indeterminate", False))
                done = {future for future in pending if future.done()}
                for future in done:
                    spec = future_specs[future]
                    try:
                        result = future.result()
                    except Exception as exc:  # Keep the queue/final result complete even if a worker has a bug.
                        result = {"action_id": spec[0], "lane": spec[1], "status": "runner_error", "detail": repr(exc), "artifacts": []}
                    result["finished_utc"] = utc_now()
                    results.append(result)
                    state = "DONE" if result["status"] == "complete" else result["status"].upper().replace("_", " ")
                    finish_stage = result.get("detail") or (
                        "Action finished" if state == "DONE" else
                        f"Exit {result.get('return_code', 'n/a')}; see combined-results.json"
                    )
                    dashboard.update(spec[0], state=state, percent=100 if state == "DONE" else None,
                                     stage=finish_stage)
                    append_queue(queue_path, {"event": "action_finished", "action_id": spec[0], "status": result["status"],
                                              "utc": result["finished_utc"], "artifact_count": len(result.get("artifacts", []))})
                    pending.remove(future)
                dashboard.render()
                if pending and not done:
                    time.sleep(0.15)
            while not progress_events.empty():
                event = progress_events.get_nowait()
                event["event"] = "action_progress"
                event["utc"] = utc_now()
                append_queue(queue_path, event)
                dashboard.update(event["action_id"], percent=event["percent"], stage=event["stage"],
                                 indeterminate=event.get("indeterminate", False))
            dashboard.render()
        finally:
            dashboard.close()
    results.sort(key=lambda item: item["action_id"])
    payload = {
        "schema_version": 1,
        "run_id": run_id,
        "started_utc": started_utc,
        "finished_utc": utc_now(),
        "trigger": trigger,
        "mode": "isolated_parallel_test_no_github_upload",
        "artifact_sha256_note": "Artifact SHA-256 values identify original generated files; nested absolute Windows paths are redacted in the embedded data copy.",
        "input_snapshot_available": input_root.is_dir(),
        "worker_data_retained": False,
        "queue_file": queue_path.name,
        "results": results + UPLOAD_ONLY_ACTIONS,
        "summary": {
            "total": len(results) + len(UPLOAD_ONLY_ACTIONS),
            "completed": sum(r.get("status") == "complete" for r in results),
            "failed": sum(r.get("status") in {"failed", "failed_to_start", "failed_no_outputs", "runner_error", "timed_out"} for r in results),
            "unsupported": sum(r.get("status") == "unsupported_platform" for r in results),
            "upload_actions_skipped": len(UPLOAD_ONLY_ACTIONS),
        },
    }
    temp = final_path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, final_path)
    # Keep immutable per-run outputs, plus one local handoff artifact for the
    # Surveyor's explicit shared-report upload action. The queue remains a
    # local diagnostic and is never part of that upload.
    if localappdata:
        app_root = Path(localappdata) / "NMSDerelictSurveyor"
        app_root.mkdir(parents=True, exist_ok=True)
        latest_report = app_root / "parallel-action-test-latest.json"
        latest_tmp = latest_report.with_suffix(".json.tmp")
        shutil.copyfile(final_path, latest_tmp)
        os.replace(latest_tmp, latest_report)
    try:
        report_relative = final_path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        report_relative = ""
    if report_relative:
        pointer = {
            "schema_version": 1,
            "run_id": run_id,
            "finished_utc": payload["finished_utc"],
            "report_path": report_relative,
            "sha256": hashlib.sha256(final_path.read_bytes()).hexdigest(),
            "summary": payload["summary"],
        }
        pointer_path = ROOT / "parallel-action-tests" / "LATEST.json"
        pointer_path.parent.mkdir(parents=True, exist_ok=True)
        pointer_tmp = pointer_path.with_suffix(".json.tmp")
        pointer_tmp.write_text(json.dumps(pointer, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(pointer_tmp, pointer_path)
    append_queue(queue_path, {"event": "run_finished", "utc": payload["finished_utc"], "summary": payload["summary"]})
    # Worker input snapshots can include the large extracted NMS asset tree. All
    # declared outputs and process logs are already embedded in combined-results.
    workers_dir = run_dir / "workers"
    junctions = workers_dir.rglob("extracted") if workers_dir.exists() else ()
    for junction in junctions:
        if getattr(os.path, "isjunction", lambda _p: False)(junction):
            try:
                os.rmdir(junction)
            except OSError:
                pass
        elif junction.is_symlink():
            try:
                junction.unlink()
            except OSError:
                pass
    shutil.rmtree(workers_dir, ignore_errors=True)
    failures = payload["summary"]["failed"]
    return queue_path, final_path, failures


def self_test() -> int:
    """Small portable check for concurrent completion, durable queue and JSON aggregation."""
    import tempfile
    assert _redact_json_paths({"path": r"C:\Users\Example\evidence.json"}) == {"path": "<LOCAL_PATH>"}
    for wrapped in ("Analyze-Generation-Baseline.cmd", "Measure-Derelict-Generation.cmd", "Prepare-Crate-Assets.cmd"):
        script = _powershell_script_name(wrapped)
        assert script == wrapped[:-4] + ".ps1"
        assert (ROOT / script).is_file(), f"Missing PowerShell workflow: {script}"
    with tempfile.TemporaryDirectory(prefix="nmsds-parallel-queue-test-") as temp:
        source = Path(temp) / "source"
        snapshot = Path(temp) / "snapshot"
        extracted = source / "asset-work-v1" / "extracted" / "nested"
        extracted.mkdir(parents=True)
        (extracted / "input.txt").write_text("read-only evidence", encoding="utf-8")
        _copy_input_snapshot(source, snapshot, link_extracted=True)
        assert (snapshot / "asset-work-v1" / "extracted" / "nested" / "input.txt").read_text(encoding="utf-8") == "read-only evidence"

        q = Path(temp) / "queue.jsonl"
        append_queue(q, {"event": "run_started"})
        barrier = threading.Barrier(4)
        def fake_action(action_id: str) -> dict[str, Any]:
            barrier.wait(timeout=2)
            return {"action_id": action_id, "status": "complete", "artifact": {"ok": True}}
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(fake_action, f"action-{i}") for i in range(4)]
            completed = [future.result() for future in concurrent.futures.as_completed(futures)]
        for result in completed:
            append_queue(q, {"event": "action_finished", **result})
        lines = [json.loads(line) for line in q.read_text(encoding="utf-8").splitlines()]
        assert len(lines) == 5 and lines[0]["event"] == "run_started"
        combined = {"schema_version": 1, "results": completed}
        target = Path(temp) / "combined.json"
        target.write_text(json.dumps(combined), encoding="utf-8")
        reread = json.loads(target.read_text(encoding="utf-8"))
        assert len(reread["results"]) == 4 and all(item["artifact"]["ok"] for item in reread["results"])
        events: queue.Queue[dict[str, Any]] = queue.Queue()
        rc, output, timed_out = _execute_streaming(
            [sys.executable, "-c", "print('NMSDS_PROGRESS:37|Downloading sample', flush=True); print('done')"],
            Path.cwd(), os.environ.copy(), "sample-progress-test", events, timeout_seconds=5,
        )
        progress = events.get_nowait()
        assert rc == 0 and not timed_out and "done" in output
        assert progress["percent"] == 37 and progress["stage"] == "Downloading sample"
        events = queue.Queue()
        rc, _output, timed_out = _execute_streaming(
            [sys.executable, "-c", "print('NMSDS_PROGRESS:-1|Working', flush=True)"],
            Path.cwd(), os.environ.copy(), "sample-indeterminate-test", events, timeout_seconds=5,
        )
        progress = events.get_nowait()
        assert rc == 0 and not timed_out and progress["indeterminate"] is True
    print("Parallel action queue self-test passed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", help="test queue and combined JSON behavior without running NMS research actions")
    parser.add_argument("--output-dir", type=Path, help="new output directory; must not already exist")
    parser.add_argument("--workers", type=int, default=len(ACTION_SPECS), help="maximum concurrent research actions")
    parser.add_argument("--trigger", choices=("manual_button", "automatic_saved_session", "command_line"),
                        default="command_line", help="what initiated this run")
    parser.add_argument("--session-file", help="saved session filename when auto-triggered")
    parser.add_argument("--session-sha256", help="saved session SHA-256 when auto-triggered")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    try:
        queue_path, final_path, failures = run_test(
            args.output_dir, args.workers, trigger_kind=args.trigger,
            trigger_session_file=args.session_file, trigger_session_sha256=args.session_sha256,
        )
    except FileExistsError as exc:
        print(f"Refusing to overwrite an existing test run: {exc}", file=sys.stderr)
        return 2
    print(f"Queue: {queue_path}")
    print(f"Combined results: {final_path}")
    print("GitHub uploads: disabled")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
