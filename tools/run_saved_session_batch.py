#!/usr/bin/env python3
"""Run queued saved-session research concurrently with isolated reports.

Each session writes a distinct combined report below
research-output/automatic-session-batches/<batch-id>/runs. The only GitHub
upload is a single batch containing those immutable reports and an index.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "tools" / "test_parallel_research_actions.py"
UPLOADER = ROOT / "tools" / "github_integration.py"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def _safe_session(record: dict[str, Any]) -> tuple[str, str]:
    filename = str(record.get("session_file") or "")
    digest = str(record.get("session_sha256") or "").lower()
    if Path(filename).name != filename or not filename.lower().endswith(".json"):
        raise ValueError(f"Unsafe saved-session filename: {filename!r}")
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError(f"Invalid saved-session SHA-256 for {filename}")
    return filename, digest


def run_batch(spec_path: Path, output_dir: Path, max_sessions: int = 3,
              action_workers: int = 4, upload: bool = False) -> tuple[Path, int]:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if not isinstance(spec, dict) or not isinstance(spec.get("sessions"), list):
        raise ValueError("Batch specification must contain a sessions array.")
    batch_id = str(spec.get("batch_id") or "")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", batch_id):
        raise ValueError("Invalid batch id.")
    if max_sessions < 1 or action_workers < 1:
        raise ValueError("Concurrency limits must be positive.")
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    runs_dir = output_dir / "runs"
    logs_dir = output_dir / "logs"
    runs_dir.mkdir()
    logs_dir.mkdir()
    queue_path = output_dir / "queue.jsonl"
    result_path = output_dir / "batch-results.json"
    sessions: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in spec["sessions"]:
        if not isinstance(raw, dict):
            raise ValueError("Each batch session must be an object.")
        filename, digest = _safe_session(raw)
        if digest in seen:
            continue
        seen.add(digest)
        sessions.append({"session_file": filename, "session_sha256": digest})
    if not sessions:
        raise ValueError("There are no saved sessions in the batch.")

    results: list[dict[str, Any]] = []
    lock = threading.Lock()
    started = utc_now()
    _atomic_json(result_path, {
        "schema_version": 1, "batch_id": batch_id, "started_utc": started,
        "state": "running", "max_concurrent_sessions": max_sessions,
        "action_workers_per_session": action_workers, "session_count": len(sessions),
        "sessions": [], "reports": [],
    })

    def append_queue(payload: dict[str, Any]) -> None:
        with lock:
            with queue_path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps({"utc": utc_now(), **payload}, sort_keys=True) + "\n")
                stream.flush()
                os.fsync(stream.fileno())

    def update_index(state: str = "running") -> None:
        reports = [
            {key: item[key] for key in ("session_file", "session_sha256", "run_id", "report_path", "report_sha256", "status", "summary") if key in item}
            for item in sorted(results, key=lambda r: r["session_file"].casefold()) if item.get("report_path")
        ]
        _atomic_json(result_path, {
            "schema_version": 1, "batch_id": batch_id, "started_utc": started,
            "updated_utc": utc_now(), "state": state,
            "max_concurrent_sessions": max_sessions,
            "action_workers_per_session": action_workers, "session_count": len(sessions),
            "completed_count": len(results), "sessions": sorted(results, key=lambda r: r["session_file"].casefold()),
            "reports": reports,
        })

    def run_one(session: dict[str, str]) -> dict[str, Any]:
        filename = session["session_file"]
        digest = session["session_sha256"]
        localappdata = os.environ.get("LOCALAPPDATA")
        if not localappdata:
            return {**session, "status": "failed_to_start", "detail": "LOCALAPPDATA is not set."}
        source_path = Path(localappdata) / "NMSDerelictSurveyor" / "sessions" / filename
        try:
            actual = hashlib.sha256(source_path.read_bytes()).hexdigest()
        except OSError as exc:
            return {**session, "status": "failed_to_start", "detail": f"Could not read saved session: {exc}"}
        if actual != digest:
            return {**session, "status": "failed_to_start", "detail": "Saved-session SHA-256 changed before its batch task started."}
        stem = re.sub(r"[^A-Za-z0-9_.-]+", "-", Path(filename).stem).strip(".-")[:64] or "session"
        run_dir = runs_dir / f"{stem}-{digest[:10]}"
        log_path = logs_dir / f"{stem}-{digest[:10]}.log"
        command = [sys.executable, str(RUNNER), "--trigger", "automatic_saved_session",
                   "--session-file", filename, "--session-sha256", digest,
                   "--workers", str(action_workers), "--output-dir", str(run_dir), "--no-latest"]
        append_queue({"event": "session_started", "session_file": filename, "session_sha256": digest})
        try:
            completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, errors="replace", check=False)
            log_path.write_text(completed.stdout + ("\nSTDERR\n" + completed.stderr if completed.stderr else ""), encoding="utf-8")
            report_path = run_dir / "combined-results.json"
            result: dict[str, Any] = {**session, "status": "complete" if completed.returncode == 0 else "completed-with-errors",
                                      "return_code": completed.returncode, "log_path": log_path.relative_to(ROOT).as_posix()}
            if report_path.is_file():
                report_bytes = report_path.read_bytes()
                report = json.loads(report_bytes.decode("utf-8"))
                trigger = report.get("trigger") or {}
                if str(trigger.get("session_sha256") or "").lower() != digest:
                    result.update({"status": "failed", "detail": "Generated report does not match its saved-session hash."})
                else:
                    result.update({"run_id": str(report.get("run_id") or ""),
                                   "report_path": report_path.relative_to(ROOT).as_posix(),
                                   "report_sha256": hashlib.sha256(report_bytes).hexdigest(),
                                   "summary": report.get("summary") or {}})
            else:
                result.update({"status": "failed", "detail": f"Runner produced no combined report (exit {completed.returncode})."})
            append_queue({"event": "session_finished", "session_file": filename,
                          "session_sha256": digest, "status": result["status"],
                          "report_path": result.get("report_path", "")})
            return result
        except Exception as exc:
            return {**session, "status": "runner_error", "detail": f"{type(exc).__name__}: {exc}"}

    print(f"Batch {batch_id}: {len(sessions)} saved sessions; up to {max_sessions} sessions and {action_workers} research actions per session.", flush=True)
    failures = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_sessions) as pool:
        future_sessions = {pool.submit(run_one, item): item for item in sessions}
        for future in concurrent.futures.as_completed(future_sessions):
            session = future_sessions[future]
            try:
                item = future.result()
            except Exception as exc:
                item = {**session, "status": "runner_error", "detail": f"{type(exc).__name__}: {exc}"}
            with lock:
                results.append(item)
                if item.get("status") != "complete":
                    failures += 1
                update_index()
                done = len(results)
            print(f"NMSDS_BATCH_PROGRESS={done}/{len(sessions)} {item['session_file']} {item['status']}", flush=True)
    final_state = "complete" if not failures else "completed-with-errors"
    update_index(final_state)
    if upload and result_path.is_file() and any(item.get("report_path") for item in results):
        print("Publishing the batch index and each session report to GitHub…", flush=True)
        upload_result = subprocess.run([sys.executable, str(UPLOADER), "upload", "--action",
                                        "automatic-research-batch", "--batch-file", str(result_path)],
                                       cwd=ROOT, capture_output=True, text=True, errors="replace", check=False)
        print(upload_result.stdout, end="", flush=True)
        if upload_result.stderr:
            print(upload_result.stderr, file=sys.stderr, flush=True)
        if upload_result.returncode:
            failures += 1
            index_payload = json.loads(result_path.read_text(encoding="utf-8"))
            index_payload["github_upload"] = {"status": "failed", "return_code": upload_result.returncode,
                                               "updated_utc": utc_now()}
            _atomic_json(result_path, index_payload)
            print(f"NMSDS_BATCH_UPLOAD_FAILED=exit {upload_result.returncode}", flush=True)
        else:
            index_payload = json.loads(result_path.read_text(encoding="utf-8"))
            match = re.search(r"NMSDS_BATCH_UPLOAD_PATH=([^\r\n]+)", upload_result.stdout)
            index_payload["github_upload"] = {"status": "complete", "uploaded_utc": utc_now(),
                                               "repository_path": match.group(1).strip() if match else ""}
            _atomic_json(result_path, index_payload)
            print("NMSDS_BATCH_UPLOAD_COMPLETE=1", flush=True)
    print(f"NMSDS_BATCH_REPORT={result_path}", flush=True)
    print(f"NMSDS_STATUS=Saved-session batch {final_state}", flush=True)
    return result_path, (1 if failures else 0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-spec", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--max-concurrent-sessions", type=int, default=3)
    parser.add_argument("--action-workers", type=int, default=4)
    parser.add_argument("--upload", action="store_true")
    args = parser.parse_args()
    try:
        _path, code = run_batch(args.batch_spec, args.output_dir, args.max_concurrent_sessions,
                                args.action_workers, args.upload)
        return code
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"Saved-session batch failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
