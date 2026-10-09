from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
import traceback
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = "vikkitor93-coder/NMS-Derelict-Probe"
BRANCH = "main"
RAW_BASE = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"
ROOT = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "NMSDerelictSurveyor"
WORK = ROOT / "asset-work-v1"
PROJECT_ROOT_FILE = ROOT / "project-root.txt"
LOG_DIR = ROOT / "gui-actions"
HELPER_LOG = LOG_DIR / "github-integration.log"
GITHUB_DIAGNOSTIC = LOG_DIR / "github-diagnostic-latest.txt"
ALL_EVIDENCE_UPLOAD_RECEIPT = ROOT / "all-saved-evidence-upload-receipt.json"

ACTION_OUTPUTS = {
    "all-saved-evidence": [],
    "parallel-action-test": [ROOT / "parallel-action-test-latest.json"],
    "automatic-research-batch": [],
    "measure": [WORK / "generation-baseline-latest.json", WORK / "generation-measurements-summary.json", WORK / "generation-measurements.csv", WORK / "seed-room-correlation.json"],
    "extract-caller": [WORK / "dungeon-caller-code-latest.json"],
    "extract-upstream": [WORK / "dungeon-upstream-callers-latest.json"],
    "extract-exact-root-caller": [WORK / "exact-root-caller-code-latest.json"],
    "resolve-root-vtable": [WORK / "exact-root-vtable-latest.json"],
    "analyze-seed-function": [WORK / "dungeon-seed-function-analysis-latest.json"],
    "prepare-assets": [WORK / "room-crate-index.json", WORK / "asset-calculation-latest.json", WORK / "crate-target-discovery.json"],
    "analyze-generation": [WORK / "generation-baseline-latest.json", WORK / "exact-root-caller-latest.json"],
    # Directly upload the probe's atomically saved root event after NMS exits.
    "upload-runtime-capture": [WORK / "exact-root-caller-latest.json"],
    "analyze-dungeon": [WORK / "dungeon-generation-table.json"],
    "analyze-crates": [ROOT / "crate-research-latest.json"],
    "analyze-correlation": [WORK / "seed-room-correlation.json"],
    "compare-measurements": [WORK / "generation-measurements-summary.json", WORK / "generation-measurements.csv"],
    "root-seed-batch": [WORK / "root-seed-batch-latest.json"],
}


def all_saved_evidence_outputs() -> tuple[list[Path], dict[str, list[str]]]:
    """Return existing action outputs once each, plus the actions that produce each path."""
    unique: dict[str, Path] = {}
    producers: dict[str, list[str]] = {}
    for action, paths in ACTION_OUTPUTS.items():
        if action in {"all-saved-evidence", "parallel-action-test", "automatic-research-batch"}:
            continue
        for path in paths:
            key = os.path.normcase(str(path.resolve()))
            unique.setdefault(key, path)
            producers.setdefault(key, []).append(action)
    for path in sorted(ROOT.glob("capture-journal-*.jsonl")):
        key = os.path.normcase(str(path.resolve()))
        unique.setdefault(key, path)
        producers.setdefault(key, []).append("runtime-probe")
    root_event = WORK / "root-event-latest.json"
    if root_event.is_file():
        key = os.path.normcase(str(root_event.resolve()))
        unique.setdefault(key, root_event)
        producers.setdefault(key, []).append("runtime-probe")
    return list(unique.values()), producers


def root_seed_batch_outputs() -> tuple[list[Path], dict[str, list[str]]]:
    """Return one batch report and the exact append-only journals it analyzed."""
    report_path = ACTION_OUTPUTS["root-seed-batch"][0]
    try:
        report = _read_json_file(report_path)
    except Exception as exc:
        raise RuntimeError("The root-seed batch report is missing or invalid JSON.") from exc
    summary = report.get("summary") if isinstance(report, dict) else None
    if not isinstance(summary, dict) or int(summary.get("root_event_observation_count") or 0) < 1:
        raise RuntimeError("No saved root-resource events were found; capture at least one root event first.")
    paths = [report_path]
    producers = {os.path.normcase(str(report_path.resolve())): ["research.analyze_root_seed_batch"]}
    for item in report.get("source_journals") or []:
        if not isinstance(item, dict):
            continue
        name = Path(str(item.get("name") or "")).name
        if not name.startswith("capture-journal-") or not name.endswith(".jsonl"):
            continue
        journal = ROOT / name
        if journal.is_file():
            paths.append(journal)
            producers[os.path.normcase(str(journal.resolve()))] = ["runtime-probe"]
    return paths, producers

DERELICT_FARMING_FILES = {
    "METADATA/REALITY/TABLES/REWARDTABLE.EXML",
    "METADATA/SIMULATION/MISSIONS/TABLES/SPACEPOIMISSIONTABLE.EXML",
    "METADATA/SIMULATION/SCENE/EXPERIENCESPAWNTABLE.EXML",
}


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _read_json_file(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _validated_parallel_action_report(path: Path) -> dict:
    """Load the local combined report before publishing it to all lanes."""
    report = _read_json_file(path)
    if report.get("schema_version") != 1 or not report.get("run_id") or not isinstance(report.get("results"), list):
        raise RuntimeError("The latest combined parallel research report is missing or invalid. Run the test first.")
    summary = report.get("summary")
    if not isinstance(summary, dict) or int(summary.get("failed", 0)) != 0:
        raise RuntimeError("The parallel research report has failed actions; review it before sharing.")
    return report


def _fingerprint_upload_files(files: list[Path]) -> str:
    return _fingerprint_upload_snapshots([(path, path.read_bytes()) for path in files])


def _fingerprint_upload_snapshots(snapshots: list[tuple[Path, bytes]]) -> str:
    digest = hashlib.sha256()
    for path, data in sorted(snapshots, key=lambda item: (item[0].name.lower(), str(item[0]).lower())):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(data)
        digest.update(b"\0")
    return digest.hexdigest()


def _safe(value: object) -> str:
    text = str(value if value is not None else "")
    for env_name, token in (("USERPROFILE", "%USERPROFILE%"), ("LOCALAPPDATA", "%LOCALAPPDATA%")):
        raw = os.environ.get(env_name)
        if raw:
            text = text.replace(raw, token).replace(raw.replace("\\", "/"), token)
    return text


def _log(event: str, **fields: object) -> None:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        record = {"utc": _utc(), "event": event, **{k: _safe(v) for k, v in fields.items()}}
        with HELPER_LOG.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    except Exception:
        pass


def _tail(text: str, limit: int = 1200) -> str:
    text = _safe(text or "").strip()
    return text[-limit:]


def _display_cmd(cmd: list[str]) -> str:
    return " ".join(_safe(x) for x in cmd)


def _run(cmd: list[str], *, input_text: str | None = None, check: bool = True, log_output: bool = True) -> subprocess.CompletedProcess[str]:
    _log("command_start", command=_display_cmd(cmd))
    try:
        result = subprocess.run(cmd, input=input_text, text=True, capture_output=True, check=False)
    except Exception as exc:
        _log("command_exception", command=_display_cmd(cmd), error=f"{type(exc).__name__}: {exc}")
        raise
    fields: dict[str, object] = {"command": _display_cmd(cmd), "returncode": result.returncode}
    if log_output and result.returncode != 0:
        fields["stdout_tail"] = _tail(result.stdout)
        fields["stderr_tail"] = _tail(result.stderr)
    _log("command_end", **fields)
    if check and result.returncode != 0:
        last = _tail(result.stderr or result.stdout or "command failed", 500)
        raise RuntimeError(f"Command failed ({result.returncode}): {last}")
    return result


def _gh() -> str | None:
    found = shutil.which("gh")
    if found:
        _log("gh_discovery", method="PATH", found=True, executable=found)
        return found
    if os.name == "nt":
        for base_name, base in (("ProgramFiles", os.environ.get("ProgramFiles")), ("LOCALAPPDATA", os.environ.get("LOCALAPPDATA"))):
            if not base:
                continue
            for rel in ("GitHub CLI\\gh.exe", "Programs\\GitHub CLI\\gh.exe"):
                candidate = Path(base) / rel
                if candidate.is_file():
                    _log("gh_discovery", method=base_name, found=True, executable=candidate)
                    return str(candidate)
    _log("gh_discovery", found=False)
    return None


def _auth_status(gh: str) -> subprocess.CompletedProcess[str]:
    # Do not persist the normal successful auth output because it may include the
    # GitHub account name. Return code is enough for diagnostics.
    return _run([gh, "auth", "status", "--hostname", "github.com"], check=False, log_output=False)


def _interactive_auth(gh: str) -> None:
    cmd = [gh, "auth", "login", "--hostname", "github.com", "--git-protocol", "https", "--web"]
    _log("auth_login_start", command=_display_cmd(cmd), mode="visible-console" if os.name == "nt" else "terminal")
    if os.name == "nt":
        flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
        result = subprocess.run(cmd, creationflags=flags, check=False)
    else:
        result = subprocess.run(cmd, check=False)
    _log("auth_login_end", returncode=result.returncode)
    if result.returncode != 0:
        raise RuntimeError(f"GitHub CLI authentication exited with code {result.returncode}.")


def setup_github() -> None:
    _log("setup_start", python=sys.version.split()[0])
    gh = _gh()
    if not gh and os.name == "nt" and shutil.which("winget"):
        _log("winget_install_start", package="GitHub.cli")
        install = _run([
            "winget", "install", "--id", "GitHub.cli", "-e", "--source", "winget",
            "--accept-package-agreements", "--accept-source-agreements",
        ], check=False)
        _log("winget_install_end", returncode=install.returncode, stderr_tail=_tail(install.stderr, 600))
        gh = _gh()
    if not gh:
        raise RuntimeError("GitHub CLI (gh) is not installed. The diagnostic log records whether Winget was available.")
    status = _auth_status(gh)
    _log("auth_status", phase="before", returncode=status.returncode)
    if status.returncode != 0:
        _interactive_auth(gh)
    status = _auth_status(gh)
    _log("auth_status", phase="after", returncode=status.returncode)
    if status.returncode != 0:
        raise RuntimeError("GitHub CLI authentication did not complete.")
    print("GitHub uploads ready.")
    _log("setup_complete")


def _json_cmd(cmd: list[str]) -> object:
    p = _run(cmd)
    try:
        return json.loads(p.stdout)
    except Exception as exc:
        _log("json_parse_failure", command=_display_cmd(cmd), stdout_tail=_tail(p.stdout, 1200), error=repr(exc))
        raise RuntimeError("GitHub CLI returned data that was not valid JSON.") from exc


def _api_json(gh: str, method: str, endpoint: str, payload: object | None = None) -> object:
    _log("github_api_start", method=method, endpoint=endpoint)
    cmd = [gh, "api", "--method", method, endpoint]
    try:
        if payload is None:
            result = _json_cmd(cmd)
        else:
            p = _run(cmd + ["--input", "-"], input_text=json.dumps(payload))
            result = json.loads(p.stdout)
        _log("github_api_complete", method=method, endpoint=endpoint)
        return result
    except Exception as exc:
        _log("github_api_failure", method=method, endpoint=endpoint, error=f"{type(exc).__name__}: {exc}")
        raise


def upload_automatic_research_batch(batch_file: str) -> None:
    """Publish a batch index and every per-session report as one Git commit."""
    root = project_root()
    index_path = Path(batch_file).resolve()
    try:
        index_path.relative_to(root.resolve())
    except ValueError as exc:
        raise RuntimeError("Batch index must be inside the Surveyor project folder.") from exc
    index = _read_json_file(index_path)
    if index.get("schema_version") != 1 or not isinstance(index.get("reports"), list):
        raise RuntimeError("The selected batch index is not a valid saved-session research batch.")
    report_snapshots: list[tuple[dict[str, Any], bytes, dict[str, Any]]] = []
    for item in index["reports"]:
        if not isinstance(item, dict):
            raise RuntimeError("Batch index contains an invalid report entry.")
        relative = str(item.get("report_path") or "")
        rel_path = Path(relative)
        if rel_path.is_absolute() or ".." in rel_path.parts:
            raise RuntimeError("Batch report path is unsafe.")
        report_path = (root / rel_path).resolve()
        try:
            report_path.relative_to(root.resolve())
            raw = report_path.read_bytes()
            report = json.loads(raw.decode("utf-8"))
        except (ValueError, OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"A referenced batch report is missing or invalid: {relative}") from exc
        digest = hashlib.sha256(raw).hexdigest()
        if digest != str(item.get("report_sha256") or "").lower():
            raise RuntimeError(f"A referenced batch report changed after the index was written: {relative}")
        expected_session_sha = str(item.get("session_sha256") or "").lower()
        actual_session_sha = str((report.get("trigger") or {}).get("session_sha256") or "").lower()
        if not expected_session_sha or expected_session_sha != actual_session_sha:
            raise RuntimeError(f"A batch report does not match its saved-session hash: {relative}")
        report_snapshots.append((item, raw, report))
    if not report_snapshots:
        raise RuntimeError("The saved-session batch contains no completed reports to publish.")

    gh = _gh()
    if not gh:
        raise RuntimeError("GitHub CLI is missing. Use Set up GitHub uploads first.")
    auth = _auth_status(gh)
    if auth.returncode != 0:
        raise RuntimeError("GitHub CLI is not authenticated. Use Set up GitHub uploads first.")
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    batch_id = str(index.get("batch_id") or "batch")
    safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "-", batch_id)[:64] or "batch"
    folder = evidence_folder(now, "automatic-research-batch") + f"-{safe_id}-{uuid.uuid4().hex[:6]}"
    lanes = ["runtime-dispatch", "seed-lineage", "dungeon-decompile", "metadata"]
    entries: list[dict[str, str]] = []
    published_reports: list[dict[str, Any]] = []
    for item, raw, report in report_snapshots:
        run_id = str(report.get("run_id") or item.get("run_id") or "run")
        safe_run = re.sub(r"[^A-Za-z0-9_.-]+", "-", run_id)[:80] or "run"
        remote_path = f"{folder}/reports/{safe_run}/combined-results.json"
        blob = _api_json(gh, "POST", f"repos/{REPO}/git/blobs", {
            "content": base64.b64encode(raw).decode("ascii"), "encoding": "base64"})
        entries.append({"path": remote_path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        published_reports.append({
            "session_file": str(item.get("session_file") or ""),
            "session_sha256": str(item.get("session_sha256") or ""),
            "run_id": run_id,
            "status": str(item.get("status") or "complete"),
            "summary": item.get("summary") or report.get("summary") or {},
            "report_path": remote_path,
            "report_sha256": hashlib.sha256(raw).hexdigest(),
        })
    batch_payload = {
        "schema_version": 1, "batch_id": batch_id, "uploaded_utc": now,
        "started_utc": index.get("started_utc"), "state": index.get("state"),
        "session_count": index.get("session_count", len(index.get("sessions", []))),
        "published_report_count": len(published_reports),
        "max_concurrent_sessions": index.get("max_concurrent_sessions"),
        "action_workers_per_session": index.get("action_workers_per_session"),
        "visible_to_lanes": lanes, "reports": published_reports,
    }
    batch_bytes = (json.dumps(batch_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    batch_blob = _api_json(gh, "POST", f"repos/{REPO}/git/blobs", {
        "content": base64.b64encode(batch_bytes).decode("ascii"), "encoding": "base64"})
    batch_remote_path = f"{folder}/batch-results.json"
    entries.append({"path": batch_remote_path, "mode": "100644", "type": "blob", "sha": batch_blob["sha"]})
    manifest = {
        "version": 1, "utc": now, "action": "automatic-research-batch",
        "batch_id": batch_id, "visible_to_lanes": lanes,
        "selection": "One immutable combined-results report per saved session; report paths and session hashes are indexed in batch-results.json.",
        "batch_results_path": batch_remote_path,
        "files": [{"name": report["report_path"], "sha256": report["report_sha256"],
                   "session_sha256": report["session_sha256"]} for report in published_reports],
    }
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    manifest_blob = _api_json(gh, "POST", f"repos/{REPO}/git/blobs", {
        "content": base64.b64encode(manifest_bytes).decode("ascii"), "encoding": "base64"})
    entries.append({"path": f"{folder}/run-manifest.json", "mode": "100644", "type": "blob", "sha": manifest_blob["sha"]})
    pointer = {
        "schema_version": 1, "batch_id": batch_id, "uploaded_utc": now,
        "report_path": batch_remote_path, "report_sha256": hashlib.sha256(batch_bytes).hexdigest(),
        "published_report_count": len(published_reports), "visible_to_lanes": lanes,
    }
    pointer_bytes = (json.dumps(pointer, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    pointer_blob = _api_json(gh, "POST", f"repos/{REPO}/git/blobs", {
        "content": base64.b64encode(pointer_bytes).decode("ascii"), "encoding": "base64"})
    entries.append({"path": "research/LATEST_AUTOMATIC_RESEARCH_BATCH.json", "mode": "100644", "type": "blob", "sha": pointer_blob["sha"]})
    ref = _api_json(gh, "GET", f"repos/{REPO}/git/ref/heads/{BRANCH}")
    parent = ref["object"]["sha"]
    base_commit = _api_json(gh, "GET", f"repos/{REPO}/git/commits/{parent}")
    tree = _api_json(gh, "POST", f"repos/{REPO}/git/trees", {"base_tree": base_commit["tree"]["sha"], "tree": entries})
    commit = _api_json(gh, "POST", f"repos/{REPO}/git/commits", {
        "message": f"Add saved-session research batch {batch_id}", "tree": tree["sha"], "parents": [parent]})
    _api_json(gh, "PATCH", f"repos/{REPO}/git/refs/heads/{BRANCH}", {"sha": commit["sha"], "force": False})
    print(f"Complete + uploaded: https://github.com/{REPO}/tree/{BRANCH}/{folder}")
    print(f"Latest saved-session batch pointer: https://github.com/{REPO}/blob/{BRANCH}/research/LATEST_AUTOMATIC_RESEARCH_BATCH.json")
    print(f"NMSDS_BATCH_UPLOAD_PATH={folder}")
    _log("upload_complete", action="automatic-research-batch", folder=folder,
         batch_id=batch_id, report_count=len(published_reports), commit=commit["sha"])


def upload_action(action: str, capture_file: str | None = None, only_if_changed: bool = False,
                  batch_file: str | None = None) -> None:
    _log("upload_start", action=action)
    if action == "automatic-research-batch":
        if not batch_file:
            raise RuntimeError("Automatic research batch upload requires --batch-file.")
        upload_automatic_research_batch(batch_file)
        return
    gh = _gh()
    if not gh:
        raise RuntimeError("GitHub CLI is missing. Use Set up GitHub uploads first.")
    auth = _auth_status(gh)
    _log("auth_status", phase="upload", returncode=auth.returncode)
    if auth.returncode != 0:
        raise RuntimeError("GitHub CLI is not authenticated. Use Set up GitHub uploads first.")
    expected = ACTION_OUTPUTS.get(action)
    producers: dict[str, list[str]] = {}
    if capture_file:
        if action != "upload-runtime-capture":
            raise RuntimeError("--capture-file is supported only for upload-runtime-capture.")
        capture_path = Path(capture_file)
        try:
            captured = json.loads(capture_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("The saved runtime capture file is missing or invalid JSON.") from exc
        slot = captured.get("owner_plus_0x10_capture") if isinstance(captured, dict) else None
        if not isinstance(captured, dict) or captured.get("schema_version") != 1 or not isinstance(slot, dict):
            raise RuntimeError("The selected file is not a valid saved root-event capture.")
        expected = [capture_path]
    if action == "all-saved-evidence":
        expected, producers = all_saved_evidence_outputs()
    if action == "parallel-action-test":
        report_path = expected[0]
        report = _validated_parallel_action_report(report_path)
    if action == "root-seed-batch":
        expected, producers = root_seed_batch_outputs()
        report = _read_json_file(expected[0])
    if not expected:
        raise RuntimeError(f"Unknown action: {action}")
    files = [p for p in expected if p.is_file()]
    _log("upload_outputs", action=action, expected=len(expected), found=len(files), files=",".join(p.name for p in files))
    if not files:
        raise RuntimeError("The action completed but none of its expected research outputs exist.")
    snapshots = [(path, path.read_bytes()) for path in files]
    evidence_sha = _fingerprint_upload_snapshots(snapshots) if action == "all-saved-evidence" else ""
    if only_if_changed:
        if action != "all-saved-evidence":
            raise RuntimeError("--only-if-changed is supported only for all-saved-evidence.")
        last_receipt = _read_json_file(ALL_EVIDENCE_UPLOAD_RECEIPT)
        if last_receipt.get("sha256") == evidence_sha:
            print("Saved evidence has not changed since the last shared upload; skipping duplicate batch.")
            if last_receipt.get("folder"):
                print(f"Latest shared upload: https://github.com/{REPO}/tree/{BRANCH}/{last_receipt['folder']}")
            print("NMSDS_STATUS=Evidence unchanged")
            return
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    namespace = os.environ.get("NMSDS_EVIDENCE_NAMESPACE", "").strip()
    folder = evidence_folder(now, action, namespace)
    if action == "all-saved-evidence":
        # This action creates a single deduplicated snapshot for all lanes.
        folder += "-" + uuid.uuid4().hex[:8]
    manifest = {"version": 1, "utc": now, "action": action, "files": []}
    if action == "all-saved-evidence":
        manifest["uploaded_for_lanes"] = ["runtime-dispatch", "seed-lineage", "dungeon-decompile", "metadata"]
        manifest["selection"] = "All existing unique files declared by ACTION_OUTPUTS; overlapping outputs are included once."
    if action == "parallel-action-test":
        manifest["uploaded_for_lanes"] = ["runtime-dispatch", "seed-lineage", "dungeon-decompile", "metadata"]
        manifest["selection"] = "Only the latest combined parallel research report; per-action files and queue are intentionally excluded."
        manifest["run_id"] = report["run_id"]
    if action == "root-seed-batch":
        manifest["uploaded_for_lanes"] = ["runtime-dispatch", "seed-lineage", "dungeon-decompile", "metadata"]
        manifest["selection"] = "The multi-system root-seed correlation report and the exact append-only capture journals it analyzed. Each journal/process remains a separate cohort."
        manifest["run_id"] = f"root-seed-batch-{now}"
    if namespace:
        manifest["evidence_namespace"] = namespace
    ref = _api_json(gh, "GET", f"repos/{REPO}/git/ref/heads/{BRANCH}")
    parent = ref["object"]["sha"]
    commit = _api_json(gh, "GET", f"repos/{REPO}/git/commits/{parent}")
    base_tree = commit["tree"]["sha"]
    entries = []
    used: dict[str, int] = {}
    for p, data in snapshots:
        digest = hashlib.sha256(data).hexdigest()
        name = "combined-results.json" if action == "parallel-action-test" else p.name
        n = used.get(name, 0)
        used[name] = n + 1
        if n:
            name = f"{p.stem}-{n + 1}{p.suffix}"
        _log("upload_blob_start", file=name, size=len(data), sha256=digest)
        blob = _api_json(gh, "POST", f"repos/{REPO}/git/blobs", {"content": base64.b64encode(data).decode("ascii"), "encoding": "base64"})
        entries.append({"path": f"{folder}/{name}", "mode": "100644", "type": "blob", "sha": blob["sha"]})
        record = {"name": name, "size": len(data), "sha256": digest}
        if action == "all-saved-evidence":
            record["produced_by"] = producers.get(os.path.normcase(str(p.resolve())), [])
            record["visible_to_lanes"] = manifest["uploaded_for_lanes"]
        elif action in {"parallel-action-test", "root-seed-batch"}:
            record["visible_to_lanes"] = manifest["uploaded_for_lanes"]
        manifest["files"].append(record)
    mbytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    mblob = _api_json(gh, "POST", f"repos/{REPO}/git/blobs", {"content": base64.b64encode(mbytes).decode("ascii"), "encoding": "base64"})
    entries.append({"path": f"{folder}/run-manifest.json", "mode": "100644", "type": "blob", "sha": mblob["sha"]})
    if action == "parallel-action-test":
        latest_pointer = {
            "schema_version": 1,
            "run_id": report["run_id"],
            "uploaded_utc": now,
            "report_path": f"{folder}/combined-results.json",
            "report_sha256": hashlib.sha256(snapshots[0][1]).hexdigest(),
            "visible_to_lanes": manifest["uploaded_for_lanes"],
        }
        pointer_blob = _api_json(gh, "POST", f"repos/{REPO}/git/blobs", {
            "content": base64.b64encode((json.dumps(latest_pointer, indent=2, sort_keys=True) + "\n").encode()).decode("ascii"),
            "encoding": "base64",
        })
        entries.append({"path": "research/LATEST_PARALLEL_ACTION_TEST.json", "mode": "100644", "type": "blob", "sha": pointer_blob["sha"]})
    if action == "root-seed-batch":
        report_digest = hashlib.sha256(snapshots[0][1]).hexdigest()
        latest_pointer = {
            "schema_version": 1,
            "run_id": manifest["run_id"],
            "uploaded_utc": now,
            "report_path": f"{folder}/root-seed-batch-latest.json",
            "report_sha256": report_digest,
            "root_event_observation_count": report["summary"]["root_event_observation_count"],
            "distinct_universe_address_count": report["summary"]["distinct_universe_address_count_overall"],
            "visible_to_lanes": manifest["uploaded_for_lanes"],
            "source_journals": [
                {"name": item["name"], "sha256": item["sha256"], "root_event_count": item["root_event_count"]}
                for item in report.get("source_journals", []) if isinstance(item, dict)
            ],
        }
        pointer_blob = _api_json(gh, "POST", f"repos/{REPO}/git/blobs", {
            "content": base64.b64encode((json.dumps(latest_pointer, indent=2, sort_keys=True) + "\n").encode()).decode("ascii"),
            "encoding": "base64",
        })
        entries.append({"path": "research/LATEST_ROOT_SEED_BATCH.json", "mode": "100644", "type": "blob", "sha": pointer_blob["sha"]})
    tree = _api_json(gh, "POST", f"repos/{REPO}/git/trees", {"base_tree": base_tree, "tree": entries})
    new_commit = _api_json(gh, "POST", f"repos/{REPO}/git/commits", {"message": f"Add {action} research evidence {now}", "tree": tree["sha"], "parents": [parent]})
    _api_json(gh, "PATCH", f"repos/{REPO}/git/refs/heads/{BRANCH}", {"sha": new_commit["sha"], "force": False})
    if action == "all-saved-evidence":
        try:
            ALL_EVIDENCE_UPLOAD_RECEIPT.parent.mkdir(parents=True, exist_ok=True)
            tmp = ALL_EVIDENCE_UPLOAD_RECEIPT.with_suffix(".json.tmp")
            tmp.write_text(json.dumps({"schema_version": 1, "sha256": evidence_sha, "uploaded_utc": now, "folder": folder}, indent=2) + "\n", encoding="utf-8")
            os.replace(tmp, ALL_EVIDENCE_UPLOAD_RECEIPT)
        except OSError as exc:
            _log("all_evidence_receipt_write_failed", error=repr(exc))
    print(f"Complete + uploaded: https://github.com/{REPO}/tree/{BRANCH}/{folder}")
    if action == "parallel-action-test":
        print(f"Latest combined research pointer: https://github.com/{REPO}/blob/{BRANCH}/research/LATEST_PARALLEL_ACTION_TEST.json")
    if action == "root-seed-batch":
        print(f"Latest root-seed batch pointer: https://github.com/{REPO}/blob/{BRANCH}/research/LATEST_ROOT_SEED_BATCH.json")
    _log("upload_complete", action=action, folder=folder, commit=new_commit["sha"])


def evidence_folder(timestamp: str, action: str, namespace: str = "") -> str:
    """Return a safe, backwards-compatible evidence folder for an upload."""
    if namespace and not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,47}", namespace):
        raise RuntimeError("Invalid agent evidence namespace.")
    suffix = f"{namespace}-{action}-{uuid.uuid4().hex[:8]}" if namespace else action
    return f"research-uploads/{timestamp}-{suffix}"


def _fetch_json(url: str) -> object:
    _log("http_json_start", url=url)
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            result = json.load(response)
        _log("http_json_complete", url=url)
        return result
    except urllib.error.HTTPError as exc:
        _log("http_json_failure", url=url, status=exc.code, reason=exc.reason)
        raise RuntimeError(f"HTTP {exc.code} while reading the update manifest.") from exc
    except Exception as exc:
        _log("http_json_failure", url=url, error=f"{type(exc).__name__}: {exc}")
        raise


def project_root() -> Path:
    if PROJECT_ROOT_FILE.is_file():
        p = Path(PROJECT_ROOT_FILE.read_text(encoding="utf-8-sig").strip())
        if p.is_dir() and (p / "VERSION.txt").is_file():
            return p
    raise RuntimeError("Source project folder is unknown. Relaunch using Start-Surveyor.cmd from the extracted project once.")


def check_update() -> None:
    root = project_root()
    local = (root / "VERSION.txt").read_text(encoding="utf-8-sig").strip()
    remote = _fetch_json(f"{RAW_BASE}/update-manifest.json")
    remote_version = str(remote.get("version") or "unknown")
    available = local != remote_version
    print(json.dumps({"local": local, "remote": remote_version, "update_available": available}, indent=2))
    print(f"NMSDS_REMOTE_VERSION={remote_version}")
    if available:
        print(f"NMSDS_STATUS=Update: {local} -> {remote_version}")
        print(f"NMSDS_DETAIL=Available {remote_version}. Loaded/source currently {local}.")
    else:
        print(f"NMSDS_STATUS=Up to date: {local}")
        print(f"NMSDS_DETAIL=Installed and remote version are both {local}.")
    _log("check_update_complete", local=local, remote=remote_version, update_available=available)


def _stage_installed_mod(root: Path) -> tuple[bool, str]:
    """Copy the updated probe into the pyMHF MODS location when known."""
    source = root / "mod" / "derelict_baseline_probe.py"
    installed_file = ROOT / "installed-mod-file.txt"
    if not source.is_file():
        return False, "updated mod source missing"
    if not installed_file.is_file():
        return False, "installed mod path not recorded yet"
    try:
        dest = Path(installed_file.read_text(encoding="utf-8-sig").strip())
        if not dest.parent.is_dir():
            return False, "recorded installed mod folder no longer exists"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        return True, str(dest)
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _stage_derelict_farming_mod(root: Path, mods_root: Path) -> tuple[bool, str]:
    """Install a user-supplied loose-file mod, keeping existing files recoverable."""
    payload_root = root / "user-mods" / "DerelictFreighterFarming" / "payload"
    state_path = root / "data" / "optional-mods" / "DerelictFreighterFarming.json"
    backup_root = root / "data" / "optional-mod-backups" / "DerelictFreighterFarming"
    if not payload_root.is_dir():
        return False, "user-supplied DerelictFreighterFarming archive has not been imported"
    files = sorted(p for p in payload_root.rglob("*") if p.is_file())
    if not files:
        return False, "user-supplied DerelictFreighterFarming payload is empty"
    relative_files = {p.relative_to(payload_root).as_posix() for p in files}
    if relative_files != DERELICT_FARMING_FILES or any(p.is_symlink() for p in files):
        return False, "user-supplied payload must contain only the three expected regular EXML files"
    try:
        import xml.etree.ElementTree as ET
        for source in files:
            if source.stat().st_size > 2_000_000:
                return False, f"mod file exceeds size limit: {source.name}"
            ET.parse(source)
        state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {"files": {}}
        previous = state.get("files", {}) if isinstance(state, dict) else {}
        installed: dict[str, dict[str, str | None]] = {}
        for source in files:
            rel = source.relative_to(payload_root)
            rel_key = rel.as_posix()
            destination = mods_root / "DerelictFreighterFarming" / Path(*rel.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            source_hash = _sha256_file(source)
            old = previous.get(rel_key, {}) if isinstance(previous, dict) else {}
            backup_rel = old.get("backup") if isinstance(old, dict) else None
            if destination.is_file():
                destination_hash = _sha256_file(destination)
                prior_hash = old.get("sha256") if isinstance(old, dict) else None
                if (prior_hash is None or destination_hash not in (source_hash, prior_hash)) and not backup_rel:
                    backup = backup_root / Path(*rel.parts)
                    if not backup.exists():
                        backup.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(destination, backup)
                    backup_rel = backup.relative_to(root).as_posix()
            shutil.copy2(source, destination)
            installed[rel_key] = {"sha256": source_hash, "backup": backup_rel}
        state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"version": 1, "files": installed}, indent=2) + "\n", encoding="utf-8")
        temporary.replace(state_path)
        return True, f"installed {len(installed)} files to {mods_root / 'DerelictFreighterFarming'}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def _import_derelict_farming_archive(root: Path, mods_root: Path, archive_path: Path) -> tuple[bool, str]:
    """Accept the user's own archive, validating expected filenames without extracting arbitrary paths."""
    expected = DERELICT_FARMING_FILES
    archive_path = archive_path.expanduser().resolve()
    payload_root = root / "user-mods" / "DerelictFreighterFarming" / "payload"
    try:
        with zipfile.ZipFile(archive_path) as archive:
            selected: dict[str, bytes] = {}
            for entry in archive.infolist():
                if entry.is_dir():
                    continue
                parts = Path(entry.filename.replace("\\", "/")).parts
                if len(parts) < 2 or parts[0].casefold() != "derelictfreighterfarming":
                    continue
                rel = Path(*parts[1:]).as_posix()
                if rel not in expected:
                    continue
                if entry.file_size > 2_000_000:
                    return False, f"mod file exceeds size limit: {rel}"
                if rel in selected:
                    return False, f"archive contains duplicate file: {rel}"
                with archive.open(entry) as stream:
                    content = stream.read(2_000_001)
                if len(content) > 2_000_000:
                    return False, f"mod file exceeds size limit: {rel}"
                import xml.etree.ElementTree as ET
                ET.fromstring(content)
                selected[rel] = content
        missing = sorted(expected - selected.keys())
        if missing:
            return False, "archive is missing required EXML files: " + ", ".join(missing)
        for rel, content in selected.items():
            destination = payload_root / Path(*Path(rel).parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
        return _stage_derelict_farming_mod(root, mods_root)
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def _remove_bundled_derelict_payload(root: Path) -> None:
    """Remove the 0.3.50 bundled copy; user-imported files live under user-mods."""
    bundled = root / "optional-mods" / "DerelictFreighterFarming" / "payload"
    if bundled.is_dir():
        shutil.rmtree(bundled)
    metadata = root / "optional-mods" / "DerelictFreighterFarming" / "manifest.json"
    if metadata.is_file():
        metadata.unlink()


def _rollback_derelict_farming_mod(root: Path, mods_root: Path) -> tuple[bool, str]:
    """Restore pre-install files, or remove only unchanged files we installed."""
    state_path = root / "data" / "optional-mods" / "DerelictFreighterFarming.json"
    if not state_path.is_file():
        return False, "no DerelictFreighterFarming install record"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        restored = removed = preserved = 0
        for rel_key, info in state.get("files", {}).items():
            rel = Path(*Path(rel_key).parts)
            destination = mods_root / "DerelictFreighterFarming" / rel
            backup_rel = info.get("backup")
            backup = root / Path(*Path(backup_rel).parts) if backup_rel else None
            if backup and backup.is_file():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup, destination)
                restored += 1
            elif destination.is_file() and _sha256_file(destination) == info.get("sha256"):
                destination.unlink()
                removed += 1
            elif destination.exists():
                preserved += 1
        state_path.unlink()
        return True, f"rollback complete: restored {restored}, removed {removed}, preserved user-modified {preserved}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def _installed_mods_root() -> Path | None:
    installed_file = ROOT / "installed-mod-file.txt"
    if not installed_file.is_file():
        return None
    try:
        probe = Path(installed_file.read_text(encoding="utf-8-sig").strip())
        return probe.parent.parent if probe.parent.name == "DerelictBaselineProbe" else None
    except Exception:
        return None


def install_update() -> None:
    root = project_root()
    manifest = _fetch_json(f"{RAW_BASE}/update-manifest.json")
    version = manifest["version"]
    parts = manifest.get("package_parts") or []
    if not parts:
        raise RuntimeError("Update manifest has no package_parts.")
    encoded: list[str] = []
    for rel in parts:
        _log("update_part_start", part=rel)
        with urllib.request.urlopen(f"{RAW_BASE}/{rel}", timeout=30) as response:
            encoded.append(response.read().decode("ascii").strip())
        _log("update_part_complete", part=rel)
    payload = base64.b64decode("".join(encoded))
    got = hashlib.sha256(payload).hexdigest()
    expected = str(manifest.get("package_sha256", ""))
    _log("update_package_hash", expected=expected, actual=got, size=len(payload))
    if got.lower() != expected.lower():
        raise RuntimeError(f"Package SHA-256 mismatch: {got}")
    with tempfile.TemporaryDirectory(prefix="nmsds-update-") as td:
        z = Path(td) / "pkg.zip"
        z.write_bytes(payload)
        with zipfile.ZipFile(z) as xf:
            xf.extractall(Path(td) / "x")
        xroot = Path(td) / "x"
        roots = [p for p in xroot.iterdir() if p.is_dir()]
        src = roots[0] if len(roots) == 1 else xroot
        for rel in manifest.get("managed_files", []):
            source = src / rel
            if not source.is_file():
                raise RuntimeError(f"Package is missing managed file: {rel}")
        for rel in manifest.get("managed_files", []):
            source = src / rel
            dest = root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
    _remove_bundled_derelict_payload(root)
    staged, stage_detail = _stage_installed_mod(root)
    mods_root = _installed_mods_root()
    farming_staged, farming_detail = (False, "installed NMS MODS path is not recorded")
    if mods_root is not None:
        farming_staged, farming_detail = _stage_derelict_farming_mod(root, mods_root)
    if staged:
        print(f"Installed Surveyor {version} and staged the live probe.")
    else:
        print(f"Installed Surveyor {version} source files. Probe staging: {stage_detail}.")
    print(f"DerelictFreighterFarming staging: {farming_detail}.")
    print(f"NMSDS_STATUS=Installed Surveyor {version}")
    print("NMSDS_DETAIL=Restart Surveyor to load the standalone controller update. For DerelictFreighterFarming, use Install mod archive and fully restart NMS.")
    _log("install_update_complete", version=version, managed_files=len(manifest.get("managed_files", [])), live_mod_staged=staged, stage_detail=stage_detail, farming_mod_staged=farming_staged, farming_mod_detail=farming_detail)


def install_derelict_farming_archive(archive_path: str) -> None:
    root = project_root()
    mods_root = _installed_mods_root()
    if mods_root is None:
        raise RuntimeError("The installed NMS MODS path is unknown. Run Start NMS once, then try again.")
    success, detail = _import_derelict_farming_archive(root, mods_root, Path(archive_path))
    print(detail)
    if not success:
        raise RuntimeError(detail)
    print("NMSDS_STATUS=DerelictFreighterFarming installed")
    print("NMSDS_DETAIL=Fully close and restart NMS before testing. The mod consumes the Emergency Signal Scanner on activation.")


def diagnose() -> None:
    lines = [
        "NMS Derelict Surveyor GitHub diagnostic",
        f"UTC: {_utc()}",
        f"Python: {sys.version.split()[0]}",
        f"Project root recorded: {PROJECT_ROOT_FILE.is_file()}",
    ]
    gh = _gh()
    lines.append(f"GitHub CLI found: {bool(gh)}")
    if gh:
        version = _run([gh, "--version"], check=False, log_output=False)
        lines.append(f"GitHub CLI version command: exit {version.returncode}")
        auth = _auth_status(gh)
        lines.append(f"GitHub authentication: {'OK' if auth.returncode == 0 else 'NOT READY'} (exit {auth.returncode})")
        if auth.returncode == 0:
            repo = _run([gh, "api", f"repos/{REPO}", "--jq", "{push: .permissions.push, default_branch: .default_branch}"], check=False)
            lines.append(f"Repository API access: {'OK' if repo.returncode == 0 else 'FAILED'} (exit {repo.returncode})")
            if repo.returncode == 0:
                # This jq output has no account identity or token data.
                lines.append("Repository permissions: " + _tail(repo.stdout, 300))
            else:
                lines.append("Repository error: " + _tail(repo.stderr or repo.stdout, 500))
    try:
        root = project_root()
        lines.append("Source project: OK")
        lines.append("Local version: " + (root / "VERSION.txt").read_text(encoding="utf-8-sig").strip())
    except Exception as exc:
        lines.append("Source project: FAILED - " + _safe(exc))
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    GITHUB_DIAGNOSTIC.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for line in lines:
        print(line)
    print("Diagnostic written to gui-actions/github-diagnostic-latest.txt")
    _log("diagnose_complete")


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("setup")
    up = sub.add_parser("upload")
    up.add_argument("--action", required=True, choices=sorted(ACTION_OUTPUTS))
    up.add_argument("--capture-file", help="Upload this immutable saved root-event JSON snapshot.")
    up.add_argument("--only-if-changed", action="store_true", help="Skip all-saved-evidence upload when its content matches the last successful batch.")
    up.add_argument("--batch-file", help="Publish a saved-session batch index and its isolated per-session reports.")
    sub.add_parser("check-update")
    sub.add_parser("install-update")
    farming = sub.add_parser("install-derelict-farming")
    farming.add_argument("--archive", required=True)
    sub.add_parser("rollback-derelict-farming")
    sub.add_parser("diagnose")
    args = ap.parse_args()
    _log("helper_start", command=args.cmd, parent_action=os.environ.get("NMSDS_PARENT_ACTION", ""), python=sys.version.split()[0])
    try:
        if args.cmd == "setup":
            setup_github()
        elif args.cmd == "upload":
            upload_action(args.action, args.capture_file, args.only_if_changed, args.batch_file)
        elif args.cmd == "check-update":
            check_update()
        elif args.cmd == "install-update":
            install_update()
        elif args.cmd == "install-derelict-farming":
            install_derelict_farming_archive(args.archive)
        elif args.cmd == "rollback-derelict-farming":
            mods_root = _installed_mods_root()
            if mods_root is None:
                raise RuntimeError("The installed NMS MODS path is not recorded; no rollback was attempted.")
            success, detail = _rollback_derelict_farming_mod(project_root(), mods_root)
            print(detail)
            if not success:
                raise RuntimeError(detail)
        elif args.cmd == "diagnose":
            diagnose()
        _log("helper_complete", command=args.cmd)
        return 0
    except Exception as exc:
        tb = _safe(traceback.format_exc())
        _log("helper_failure", command=args.cmd, error=f"{type(exc).__name__}: {exc}", traceback=tb)
        print(f"FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        print("Detailed GitHub integration log: gui-actions/github-integration.log", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
