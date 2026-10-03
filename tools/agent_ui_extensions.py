"""Verified, data-only UI extensions for Surveyor's Agent Console.

Extensions are JSON manifests and JSON panels. They cannot ship Python code,
shell commands, executable paths, or URLs. The host maps stable action IDs to
its own reviewed handlers.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Callable

API_VERSION = "1.0"
INDEX_SCHEMA_VERSION = 1
MANIFEST_SCHEMA_VERSION = 1
PANEL_SCHEMA_VERSION = 1
MAX_JSON_BYTES = 1_000_000
MAX_FILES = 32
MAX_TOTAL_BYTES = 4_000_000
REPOSITORY = "vikkitor93-coder/NMS-Derelict-Probe"
REMOTE_BASE = f"https://raw.githubusercontent.com/{REPOSITORY}/main/agent-ui/extensions/"
EXTENSION_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,47}$")
SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
ALLOWED_PRECONDITIONS = frozenset({"workflow.idle", "nms.running", "probe.connected", "runtime.capture_saved"})
HOST_ACTION_IDS = frozenset({
    "research.analyze_seed_function",
    "research.extract_upstream_callers",
    "research.extract_exact_root_caller",
    "research.resolve_root_vtable",
    "research.extract_caller_code",
    "research.measure_generation",
    "research.prepare_assets",
    "research.analyze_generation",
    "research.upload_runtime_capture",
})
_ACTIVE_LOCK = threading.Lock()


class ExtensionError(ValueError):
    """An extension is invalid, incompatible, or failed integrity checks."""


def _version(value: object) -> tuple[int, int, int]:
    if not isinstance(value, str) or not SEMVER_RE.fullmatch(value):
        raise ExtensionError(f"Invalid semantic version: {value!r}")
    return tuple(int(part) for part in value.split("."))  # type: ignore[return-value]


def _json_bytes(raw: bytes, what: str) -> dict:
    if len(raw) > MAX_JSON_BYTES:
        raise ExtensionError(f"{what} exceeds the size limit")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExtensionError(f"{what} is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ExtensionError(f"{what} must be a JSON object")
    return value


def _relative_json_path(value: object) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ExtensionError("Extension file paths must be non-empty relative POSIX paths")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*", value):
        raise ExtensionError("Extension file path contains unsupported characters")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts) or path.suffix.lower() != ".json":
        raise ExtensionError(f"Unsafe extension file path: {value!r}")
    return path.as_posix()


def validate_index(index: dict) -> list[dict]:
    if index.get("schema_version") != INDEX_SCHEMA_VERSION or not isinstance(index.get("extensions"), list):
        raise ExtensionError("Unsupported extension index schema")
    seen: set[str] = set()
    result = []
    for item in index["extensions"]:
        if not isinstance(item, dict):
            raise ExtensionError("Extension index entries must be objects")
        if set(item) != {"extension_id", "version", "manifest_path"}:
            raise ExtensionError("Extension index entry contains unsupported fields")
        extension_id = item.get("extension_id")
        if not isinstance(extension_id, str) or not EXTENSION_ID_RE.fullmatch(extension_id) or extension_id in seen:
            raise ExtensionError("Invalid or duplicate extension identity")
        _version(item.get("version"))
        manifest_path = _relative_json_path(item.get("manifest_path"))
        if manifest_path != f"{extension_id}/{item['version']}/manifest.json":
            raise ExtensionError("Manifest path must match its extension identity and version")
        seen.add(extension_id)
        result.append({"extension_id": extension_id, "version": item["version"], "manifest_path": manifest_path})
    return result


def validate_manifest(
    manifest: dict,
    extension_id: str,
    version: str,
    host_version: str,
    read_file: Callable[[str], bytes],
    allowed_action_ids: set[str] | frozenset[str],
) -> tuple[dict, dict]:
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise ExtensionError("Unsupported extension manifest schema")
    if set(manifest) != {
        "schema_version", "extension_id", "version", "compatible_surveyor_api_version",
        "min_surveyor_version", "entry_point", "files", "dependencies",
    }:
        raise ExtensionError("Extension manifest contains unsupported fields")
    if manifest.get("extension_id") != extension_id or manifest.get("version") != version:
        raise ExtensionError("Extension identity/version does not match the update index")
    if not EXTENSION_ID_RE.fullmatch(extension_id):
        raise ExtensionError("Invalid extension identity")
    if manifest.get("compatible_surveyor_api_version") != API_VERSION:
        raise ExtensionError("Extension requires a different Surveyor UI API version")
    if _version(host_version) < _version(manifest.get("min_surveyor_version")):
        raise ExtensionError("Extension requires a newer Surveyor version")
    dependencies = manifest.get("dependencies")
    if not isinstance(dependencies, list) or any(not isinstance(item, str) for item in dependencies):
        raise ExtensionError("Extension dependencies must be a list of capability IDs")
    supported_dependencies = {"agent-console.ui.v1"}
    supported_dependencies.update(f"action.{action_id}" for action_id in allowed_action_ids)
    if len(dependencies) != len(set(dependencies)) or any(item not in supported_dependencies for item in dependencies):
        raise ExtensionError("Extension declares an unsupported or duplicate dependency")
    if "agent-console.ui.v1" not in dependencies:
        raise ExtensionError("Extension must declare the Agent Console UI dependency")

    files = manifest.get("files")
    if not isinstance(files, list) or not files or len(files) > MAX_FILES:
        raise ExtensionError("Extension must list between 1 and 32 hashed JSON files")
    hashed: dict[str, str] = {}
    total = 0
    for record in files:
        if not isinstance(record, dict):
            raise ExtensionError("Invalid hashed file record")
        if set(record) != {"path", "sha256"}:
            raise ExtensionError("Hashed file record contains unsupported fields")
        rel = _relative_json_path(record.get("path"))
        digest = record.get("sha256")
        if rel in hashed or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ExtensionError("Duplicate path or invalid SHA-256 in file list")
        data = read_file(rel)
        total += len(data)
        if total > MAX_TOTAL_BYTES:
            raise ExtensionError("Extension exceeds the total size limit")
        if hashlib.sha256(data).hexdigest() != digest:
            raise ExtensionError(f"SHA-256 mismatch for {rel}")
        hashed[rel] = digest

    entry = _relative_json_path(manifest.get("entry_point"))
    if entry not in hashed:
        raise ExtensionError("The entry point must be included in the hashed file list")
    panel = _json_bytes(read_file(entry), "Extension entry point")
    if panel.get("schema_version") != PANEL_SCHEMA_VERSION:
        raise ExtensionError("Unsupported extension panel schema")
    if set(panel) - {"schema_version", "title", "summary", "actions", "request_only"}:
        raise ExtensionError("Extension panel contains unsupported fields")
    if not isinstance(panel.get("request_only", False), bool):
        raise ExtensionError("request_only must be a boolean")
    if not isinstance(panel.get("title"), str) or not panel["title"].strip() or len(panel["title"]) > 100:
        raise ExtensionError("Extension panel needs a short title")
    if not isinstance(panel.get("summary", ""), str) or len(panel.get("summary", "")) > 500:
        raise ExtensionError("Invalid extension panel summary")
    actions = panel.get("actions", [])
    if not isinstance(actions, list) or len(actions) > 24:
        raise ExtensionError("Extension panel actions must be a list of at most 24 actions")
    action_ids: set[str] = set()
    normalized_actions = []
    for action in actions:
        if not isinstance(action, dict):
            raise ExtensionError("Extension actions must be objects")
        if set(action) - {"action_id", "label", "preconditions", "evidence_namespace", "description", "parameters"}:
            raise ExtensionError("Extension action contains unsupported fields")
        action_id = action.get("action_id")
        label = action.get("label")
        preconditions = action.get("preconditions", [])
        namespace = action.get("evidence_namespace")
        if action_id not in allowed_action_ids or action_id in action_ids:
            raise ExtensionError(f"Unsupported or duplicate host action ID: {action_id!r}")
        if not isinstance(label, str) or not label.strip() or len(label) > 80:
            raise ExtensionError("Extension actions need short labels")
        if not isinstance(preconditions, list) or any(item not in ALLOWED_PRECONDITIONS for item in preconditions):
            raise ExtensionError("Action contains an unsupported precondition")
        if not isinstance(namespace, str) or namespace != extension_id:
            raise ExtensionError("Action evidence_namespace must match its extension identity")
        if action.get("parameters", {}) != {}:
            raise ExtensionError("This host API version does not accept extension-supplied parameters")
        action_ids.add(action_id)
        normalized_actions.append({
            "action_id": action_id,
            "label": label.strip(),
            "preconditions": list(preconditions),
            "evidence_namespace": namespace,
            "description": str(action.get("description", ""))[:300],
        })
    panel["actions"] = normalized_actions
    return manifest, panel


def remote_url(relative_path: str) -> str:
    rel = _relative_json_path(relative_path)
    return REMOTE_BASE + rel


def fetch_bytes(url: str, timeout: float = 6.0) -> bytes:
    """Fetch only JSON extension data from this repository's pinned directory."""
    from urllib.parse import urlparse
    import urllib.request

    parsed = urlparse(url)
    prefix = f"/{REPOSITORY}/main/agent-ui/extensions/"
    if parsed.scheme != "https" or parsed.hostname != "raw.githubusercontent.com" or not parsed.path.startswith(prefix):
        raise ExtensionError("Extension URL is outside the trusted repository path")
    request = urllib.request.Request(url, headers={"User-Agent": "NMS-Derelict-Surveyor"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(MAX_JSON_BYTES + 1)
    except Exception as exc:
        raise ExtensionError(f"Could not fetch extension data: {type(exc).__name__}") from exc
    if len(raw) > MAX_JSON_BYTES:
        raise ExtensionError("Remote extension file exceeds the size limit")
    return raw


def load_index(fetch: Callable[[str], bytes] = fetch_bytes) -> list[dict]:
    return validate_index(_json_bytes(fetch(REMOTE_BASE + "index.json"), "Extension index"))


def _safe_local_file(root: Path, relative_path: str) -> Path:
    rel = _relative_json_path(relative_path)
    base = root.resolve()
    path = base.joinpath(*PurePosixPath(rel).parts)
    if path.is_symlink() or base not in path.resolve().parents:
        raise ExtensionError("Extension file resolves outside its version folder")
    return path


def load_installed_extension(
    extensions_root: Path,
    extension_id: str,
    host_version: str,
    allowed_action_ids: set[str] | frozenset[str],
) -> tuple[dict, dict] | None:
    active_file = extensions_root / "active.json"
    try:
        active = json.loads(active_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    version = active.get(extension_id) if isinstance(active, dict) else None
    if not isinstance(version, str):
        return None
    _version(version)
    root = extensions_root.resolve()
    folder = extensions_root / extension_id / version
    if folder.is_symlink() or root not in folder.resolve().parents:
        raise ExtensionError("Installed extension folder resolves outside its root")
    manifest = _json_bytes(_safe_local_file(folder, "manifest.json").read_bytes(), "Installed extension manifest")
    return validate_manifest(
        manifest,
        extension_id,
        version,
        host_version,
        lambda rel: _safe_local_file(folder, rel).read_bytes(),
        allowed_action_ids,
    )


def installed_versions(extensions_root: Path, extension_id: str) -> list[str]:
    folder = extensions_root / extension_id
    if not folder.is_dir():
        return []
    versions = []
    for child in folder.iterdir():
        if child.is_dir() and SEMVER_RE.fullmatch(child.name):
            versions.append(child.name)
    return sorted(versions, key=_version, reverse=True)


def set_active_version(extensions_root: Path, extension_id: str, version: str) -> None:
    if not EXTENSION_ID_RE.fullmatch(extension_id):
        raise ExtensionError("Invalid extension identity")
    _version(version)
    root = extensions_root.resolve()
    folder = extensions_root / extension_id / version
    if folder.is_symlink() or root not in folder.resolve().parents or not (folder / "manifest.json").is_file():
        raise ExtensionError("Cannot activate an extension version that is not installed")
    active_file = extensions_root / "active.json"
    with _ACTIVE_LOCK:
        current = {}
        try:
            candidate = json.loads(active_file.read_text(encoding="utf-8"))
            if isinstance(candidate, dict):
                current = {str(k): str(v) for k, v in candidate.items()}
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            pass
        current[extension_id] = version
        active_file.parent.mkdir(parents=True, exist_ok=True)
        temp = active_file.with_suffix(".tmp")
        temp.write_text(json.dumps(current, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        os.replace(temp, active_file)


def activate_installed_extension(
    extensions_root: Path,
    extension_id: str,
    version: str,
    host_version: str,
    allowed_action_ids: set[str] | frozenset[str],
) -> tuple[dict, dict]:
    folder = extensions_root / extension_id / version
    root = extensions_root.resolve()
    if folder.is_symlink() or root not in folder.resolve().parents:
        raise ExtensionError("Installed extension folder resolves outside its root")
    manifest = _json_bytes(_safe_local_file(folder, "manifest.json").read_bytes(), "Installed extension manifest")
    validated = validate_manifest(
        manifest,
        extension_id,
        version,
        host_version,
        lambda rel: _safe_local_file(folder, rel).read_bytes(),
        allowed_action_ids,
    )
    set_active_version(extensions_root, extension_id, version)
    return validated


def install_extension(
    extensions_root: Path,
    index_entry: dict,
    host_version: str,
    allowed_action_ids: set[str] | frozenset[str],
    fetch: Callable[[str], bytes] = fetch_bytes,
) -> tuple[dict, dict]:
    entry = validate_index({"schema_version": INDEX_SCHEMA_VERSION, "extensions": [index_entry]})[0]
    manifest_path = entry["manifest_path"]
    raw_manifest = _json_bytes(fetch(remote_url(manifest_path)), "Extension manifest")
    if raw_manifest.get("extension_id") != entry["extension_id"] or raw_manifest.get("version") != entry["version"]:
        raise ExtensionError("Manifest does not match the extension index")
    files = raw_manifest.get("files")
    if not isinstance(files, list):
        raise ExtensionError("Extension file list is missing")
    extensions_root.mkdir(parents=True, exist_ok=True)
    extension_dir = extensions_root / entry["extension_id"]
    extension_dir.mkdir(parents=True, exist_ok=True)
    destination = extension_dir / entry["version"]
    if destination.exists():
        manifest = _json_bytes(_safe_local_file(destination, "manifest.json").read_bytes(), "Installed extension manifest")
        validated = validate_manifest(manifest, entry["extension_id"], entry["version"], host_version,
                                      lambda rel: _safe_local_file(destination, rel).read_bytes(), allowed_action_ids)
        set_active_version(extensions_root, entry["extension_id"], entry["version"])
        return validated

    stage = Path(tempfile.mkdtemp(prefix=f".{entry['extension_id']}-", dir=str(extension_dir)))
    try:
        (stage / "manifest.json").write_text(json.dumps(raw_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        total = len(json.dumps(raw_manifest).encode("utf-8"))
        if len(files) > MAX_FILES:
            raise ExtensionError("Too many files in extension")
        for record in files:
            rel = _relative_json_path(record.get("path") if isinstance(record, dict) else None)
            data = fetch(remote_url(f"{entry['extension_id']}/{entry['version']}/{rel}"))
            total += len(data)
            if total > MAX_TOTAL_BYTES:
                raise ExtensionError("Extension exceeds the total size limit")
            target = _safe_local_file(stage, rel)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        validated = validate_manifest(raw_manifest, entry["extension_id"], entry["version"], host_version,
                                      lambda rel: _safe_local_file(stage, rel).read_bytes(), allowed_action_ids)
        os.replace(stage, destination)
        set_active_version(extensions_root, entry["extension_id"], entry["version"])
        return validated
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def update_candidates(index_entries: list[dict], extensions_root: Path) -> list[dict]:
    updates = []
    for entry in index_entries:
        active = None
        try:
            value = json.loads((extensions_root / "active.json").read_text(encoding="utf-8"))
            active = value.get(entry["extension_id"]) if isinstance(value, dict) else None
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            pass
        if active is None or _version(entry["version"]) > _version(active):
            updates.append(entry)
    return updates


def preconditions_met(preconditions: list[str], state: dict) -> tuple[bool, str]:
    checks = {
        "workflow.idle": bool(state.get("workflow_idle")),
        "nms.running": bool(state.get("nms_running")),
        "probe.connected": bool(state.get("probe_connected")),
        "runtime.capture_saved": bool(state.get("runtime_capture_saved")),
    }
    failed = [condition for condition in preconditions if not checks.get(condition, False)]
    return (not failed, "" if not failed else "Needs: " + ", ".join(failed))


def action_button_enabled(
    preconditions: list[str],
    state: dict,
    *,
    request_only: bool = False,
    requested: bool = False,
) -> bool:
    """Keep a published human request clickable so unmet live prerequisites can be explained.

    The action handler still rechecks every precondition before running. Upload
    receipt state is intentionally absent from this decision.
    """
    if not state.get("workflow_idle"):
        return False
    if request_only and requested:
        return True
    allowed, _reason = preconditions_met(preconditions, state)
    return allowed and (not request_only or requested)


def write_action_record(
    extensions_root: Path,
    extension_id: str,
    version: str,
    action_id: str,
    status: str,
    detail: str = "",
    upload_path: str = "",
) -> Path:
    """Write collision-safe local action metadata under the lane namespace."""
    if not EXTENSION_ID_RE.fullmatch(extension_id):
        raise ExtensionError("Invalid evidence namespace")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    safe_action = re.sub(r"[^a-z0-9.-]+", "-", action_id.lower()).strip("-")[:64]
    folder = extensions_root / extension_id / "runs"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{stamp}-{safe_action}-{uuid.uuid4().hex[:8]}.json"
    target.write_text(json.dumps({
        "schema_version": 1,
        "utc": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "extension_id": extension_id,
        "extension_version": version,
        "action_id": action_id,
        "status": status,
        "detail": detail[:500],
        "upload_path": upload_path[:240],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def latest_action_record(extensions_root: Path, extension_id: str) -> dict | None:
    """Return the newest valid local lane action record, if one exists."""
    if not EXTENSION_ID_RE.fullmatch(extension_id):
        raise ExtensionError("Invalid evidence namespace")
    folder = extensions_root / extension_id / "runs"
    try:
        candidates = sorted(folder.glob("*.json"), key=lambda item: item.name, reverse=True)
    except OSError:
        return None
    for path in candidates:
        try:
            record = _json_bytes(path.read_bytes(), "Local action record")
        except (OSError, ExtensionError):
            continue
        if record.get("schema_version") != 1 or record.get("extension_id") != extension_id:
            continue
        return record
    return None


def action_record_confirms_upload(record: dict | None) -> bool:
    """Require both workflow success and the GitHub research folder receipt."""
    return bool(
        isinstance(record, dict)
        and record.get("status") == "complete"
        and isinstance(record.get("upload_path"), str)
        and record["upload_path"].startswith("research-uploads/")
    )


def latest_upload_record(extensions_root: Path, extension_id: str) -> dict | None:
    """Return the newest successful upload receipt, even if a later run failed."""
    if not EXTENSION_ID_RE.fullmatch(extension_id):
        raise ExtensionError("Invalid evidence namespace")
    folder = extensions_root / extension_id / "runs"
    try:
        candidates = sorted(folder.glob("*.json"), key=lambda item: item.name, reverse=True)
    except OSError:
        return None
    for path in candidates:
        try:
            record = _json_bytes(path.read_bytes(), "Local action record")
        except (OSError, ExtensionError):
            continue
        if record.get("schema_version") == 1 and record.get("extension_id") == extension_id and action_record_confirms_upload(record):
            return record
    return None
