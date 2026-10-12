"""Verified, allowlisted runner update packages and safe staged installation."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import uuid
import zipfile
from datetime import datetime, timezone

MAX_MANIFEST = 128 * 1024
MAX_ARCHIVE = 8 * 1024 * 1024
MAX_EXPANDED = 32 * 1024 * 1024
POLL_SECONDS = 10
PARENT_EXIT_TIMEOUT_SECONDS = 120
INSTALLER_PROGRESS_SECONDS = 10
# The runner-updates branch keeps its feed files in the runner-updates/ folder.
UPDATE_ARCHIVE_BASE_URL = "https://raw.githubusercontent.com/vikkitor93-coder/NMS-Derelict-Probe/runner-updates/runner-updates/"
UPDATE_URL = UPDATE_ARCHIVE_BASE_URL + "latest.json"
LEGACY_UPDATE_URL = "https://raw.githubusercontent.com/vikkitor93-coder/NMS-Derelict-Probe/runner-updates/latest.json"


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def source_digest(files):
    result = hashlib.sha256()
    for name, raw in sorted(files.items()):
        key = name.encode("utf-8")
        result.update(len(key).to_bytes(8, "little") + key)
        result.update(len(raw).to_bytes(8, "little") + raw)
    return result.hexdigest()


def record_update_state(root, status, *, phase, version=None, source_sha256=None, **details):
    """Persist an updater phase and a concise local diagnostic line."""
    from .runner_protocol import atomic_json

    local = Path(root).resolve() / ".local"
    local.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    state = {"schema": 1, "status": status, "phase": phase, "updated_at": timestamp}
    if version is not None:
        state["version"] = version
    if source_sha256 is not None:
        state["source_sha256"] = source_sha256
    state.update(details)
    atomic_json(local / "update-state.json", state)
    line = timestamp + " " + phase
    if "elapsed_seconds" in details:
        line += " elapsed_seconds=" + str(details["elapsed_seconds"])
    if "error" in details:
        line += " error=" + str(details["error"])
    with (local / "update-installer.log").open("a", encoding="utf-8") as stream:
        stream.write(line + "\n")
        stream.flush()


def version_tuple(value):
    if not isinstance(value, str) or not value or len(value) > 32:
        raise ValueError("invalid-update-version")
    pieces = value.split(".")
    if len(pieces) != 3 or any(not part.isdigit() or (len(part) > 1 and part[0] == "0") for part in pieces):
        raise ValueError("invalid-update-version")
    return tuple(int(part) for part in pieces)


def validate_feed(value):
    required = {"schema", "version", "source_commit", "source_sha256", "archive_url", "archive_sha256",
                "archive_bytes", "files", "tests_status", "tests_count", "tests_output_sha256"}
    if not isinstance(value, dict) or set(value) != required or value["schema"] != 1 or type(value["schema"]) is not int:
        raise ValueError("invalid-update-feed")
    version_tuple(value["version"])
    for key in ("source_sha256", "archive_sha256"):
        if not isinstance(value[key], str) or len(value[key]) != 64 or any(c not in "0123456789abcdef" for c in value[key]):
            raise ValueError("invalid-update-feed")
    if not isinstance(value["source_commit"], str) or len(value["source_commit"]) != 40 or any(c not in "0123456789abcdef" for c in value["source_commit"]):
        raise ValueError("invalid-update-feed")
    if type(value["archive_bytes"]) is not int or not 1 <= value["archive_bytes"] <= MAX_ARCHIVE:
        raise ValueError("invalid-update-feed")
    if (value["tests_status"] != "passed" or type(value["tests_count"]) is not int or value["tests_count"] < 1
            or not isinstance(value["tests_output_sha256"], str) or len(value["tests_output_sha256"]) != 64
            or any(c not in "0123456789abcdef" for c in value["tests_output_sha256"])):
        raise ValueError("update-test-evidence-missing")
    if not isinstance(value["files"], dict) or not 1 <= len(value["files"]) <= 512:
        raise ValueError("invalid-update-file-list")
    from .package_experiment import members
    allowed = set(members()[0])
    for name, entry in value["files"].items():
        if (name not in allowed or not isinstance(entry, dict) or set(entry) != {"bytes", "sha256"}
                or type(entry["bytes"]) is not int or entry["bytes"] < 0
                or not isinstance(entry["sha256"], str) or len(entry["sha256"]) != 64
                or any(c not in "0123456789abcdef" for c in entry["sha256"])):
            raise ValueError("invalid-update-file-list")
    parsed = urllib.parse.urlparse(value["archive_url"])
    expected_archive_url = UPDATE_ARCHIVE_BASE_URL + "NMS-Runner-v" + value["version"] + ".zip"
    if (parsed.scheme != "https" or parsed.hostname != "raw.githubusercontent.com"
            or value["archive_url"] != expected_archive_url):
        raise ValueError("untrusted-update-host")
    return value


def _read_url(url, limit):
    request = urllib.request.Request(url, headers={"User-Agent": "NMS-Runner-Updater/1"})
    with urllib.request.urlopen(request, timeout=20) as response:
        if response.status != 200:
            raise ValueError("update-download-failed")
        if urllib.parse.urlparse(response.geturl()).hostname not in (
                "raw.githubusercontent.com", "github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com"):
            raise ValueError("untrusted-update-redirect")
        length = response.headers.get("Content-Length")
        if length and (not length.isdigit() or int(length) > limit):
            raise ValueError("update-download-too-large")
        raw = response.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("update-download-too-large")
    return raw


def fetch_package(feed_url=UPDATE_URL):
    manifest_raw = _read_url(feed_url, MAX_MANIFEST)
    try:
        feed = validate_feed(json.loads(manifest_raw.decode("utf-8")))
    except (UnicodeError, json.JSONDecodeError):
        raise ValueError("invalid-update-feed") from None
    archive = _read_url(feed["archive_url"], MAX_ARCHIVE)
    if len(archive) != feed["archive_bytes"] or sha256_bytes(archive) != feed["archive_sha256"]:
        raise ValueError("update-archive-hash-mismatch")
    return feed, archive


def _safe_members(archive):
    from .package_experiment import members
    allowed = set(members()[0])
    with zipfile.ZipFile(archive) as package:
        infos = package.infolist()
        if not infos or len(infos) > 512:
            raise ValueError("invalid-update-package-members")
        actual, total = {}, 0
        for info in infos:
            path = PurePosixPath(info.filename)
            if path.is_absolute() or ".." in path.parts or "\\" in info.filename or len(path.parts) < 2 or path.parts[0] != "derelict_offline":
                raise ValueError("unsafe-update-package-path")
            name = "/".join(path.parts[1:])
            if name not in allowed or name in actual or info.is_dir() or (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("unapproved-update-package-member")
            total += info.file_size
            if total > MAX_EXPANDED:
                raise ValueError("update-package-expanded-too-large")
            raw = package.read(info)
            if len(raw) != info.file_size:
                raise ValueError("update-package-size-mismatch")
            actual[name] = raw
    if not actual:
        raise ValueError("empty-update-package")
    return actual


def validate_package(archive, feed):
    feed = validate_feed(feed)
    archive = bytes(archive)
    if len(archive) != feed["archive_bytes"] or sha256_bytes(archive) != feed["archive_sha256"]:
        raise ValueError("update-archive-hash-mismatch")
    with tempfile.TemporaryDirectory(prefix="nms-update-verify-") as tmp:
        path = Path(tmp) / "update.zip"
        path.write_bytes(archive)
        files = _safe_members(path)
    expected = feed["files"]
    if set(files) != set(expected):
        raise ValueError("update-package-file-list-mismatch")
    for name, raw in files.items():
        if len(raw) != expected[name]["bytes"] or sha256_bytes(raw) != expected[name]["sha256"]:
            raise ValueError("update-file-hash-mismatch")
    if source_digest(files) != feed["source_sha256"]:
        raise ValueError("update-source-hash-mismatch")
    version_raw = files.get("__init__.py", b"").decode("utf-8", errors="strict")
    marker = 'VERSION = "' + feed["version"] + '"'
    if marker not in version_raw.splitlines():
        raise ValueError("update-version-mismatch")
    return files


def stage_update(root, archive, feed):
    files = validate_package(archive, feed)
    from . import VERSION
    if version_tuple(feed["version"]) <= version_tuple(VERSION):
        raise ValueError("update-not-newer")
    staging = Path(root) / ".local" / "updates" / (feed["version"] + "-" + uuid.uuid4().hex)
    staging.mkdir(parents=True, exist_ok=False)
    for name, raw in files.items():
        target = staging.joinpath(*PurePosixPath(name).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    manifest = {"schema": 1, "version": feed["version"], "source_sha256": feed["source_sha256"],
                "files": {name: {"bytes": len(raw), "sha256": sha256_bytes(raw)} for name, raw in sorted(files.items())}}
    staging.with_name(staging.name + ".json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return staging


def apply_staged(root, staging, wait_pid=None):
    root, staging = Path(root).resolve(), Path(staging).resolve()
    local = root / ".local"
    if staging.parent != (local / "updates").resolve() or staging.is_symlink() or not staging.is_dir():
        raise ValueError("staged-update-outside-approved-folder")
    metadata_path = staging.with_name(staging.name + ".json")
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ValueError("staged-update-manifest-missing") from None
    files = {}
    for path in staging.rglob("*"):
        if path.is_file():
            rel = path.relative_to(staging).as_posix()
            files[rel] = path
    if not files:
        raise ValueError("empty-staged-update")
    if (not isinstance(metadata, dict) or set(metadata) != {"schema", "version", "source_sha256", "files"}
            or metadata["schema"] != 1 or not isinstance(metadata["files"], dict) or set(metadata["files"]) != set(files)):
        raise ValueError("staged-update-manifest-invalid")
    from .package_experiment import members
    if not set(files).issubset(set(members()[0])):
        raise ValueError("staged-update-unapproved-files")
    checked = {}
    for name, path in files.items():
        raw = path.read_bytes()
        entry = metadata["files"][name]
        if (not isinstance(entry, dict) or set(entry) != {"bytes", "sha256"}
                or type(entry["bytes"]) is not int or entry["bytes"] != len(raw)
                or entry["sha256"] != sha256_bytes(raw)):
            raise ValueError("staged-update-hash-mismatch")
        checked[name] = raw
    if source_digest(checked) != metadata["source_sha256"]:
        raise ValueError("staged-update-source-hash-mismatch")
    version_raw = checked.get("__init__.py", b"").decode("utf-8", errors="strict")
    if ('VERSION = "' + metadata["version"] + '"') not in version_raw.splitlines():
        raise ValueError("staged-update-version-mismatch")
    from . import VERSION
    if version_tuple(metadata["version"]) <= version_tuple(VERSION):
        raise ValueError("update-not-newer")
    if wait_pid is not None:
        version = metadata["version"]
        source_sha256 = metadata["source_sha256"]
        record_update_state(root, "pending", phase="waiting-for-runner-exit", version=version,
                            source_sha256=source_sha256, elapsed_seconds=0)

        def progress(elapsed):
            record_update_state(root, "pending", phase="waiting-for-runner-exit", version=version,
                                source_sha256=source_sha256, elapsed_seconds=elapsed)

        _wait_for_process(wait_pid, progress=progress)
    record_update_state(root, "pending", phase="applying", version=metadata["version"],
                        source_sha256=metadata["source_sha256"])
    backup = local / "update-backups" / (uuid.uuid4().hex + ".zip")
    backup.parent.mkdir(parents=True, exist_ok=True)
    prior, replaced, created_dirs = {}, [], set()
    with zipfile.ZipFile(backup, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in files:
            target = root.joinpath(*PurePosixPath(name).parts)
            if target.is_symlink():
                raise ValueError("linked-installed-source-needs-review")
            if target.is_file():
                raw = target.read_bytes()
                prior[name] = raw
                archive.writestr("derelict_offline/" + name, raw)
    try:
        for name, source in files.items():
            target = root.joinpath(*PurePosixPath(name).parts)
            if target.is_symlink():
                raise ValueError("linked-installed-source-needs-review")
            for parent in target.parents:
                if parent == root:
                    break
                if not parent.exists():
                    created_dirs.add(parent)
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.name + ".update-" + uuid.uuid4().hex)
            shutil.copyfile(source, temporary)
            os.replace(temporary, target)
            replaced.append(name)
    except Exception:
        for name in reversed(replaced):
            target = root.joinpath(*PurePosixPath(name).parts)
            if name in prior:
                restore = target.with_name(target.name + ".restore-" + uuid.uuid4().hex)
                restore.write_bytes(prior[name])
                os.replace(restore, target)
            else:
                target.unlink(missing_ok=True)
        for directory in sorted(created_dirs, key=lambda p: len(p.parts), reverse=True):
            try:
                directory.rmdir()
            except OSError:
                pass
        raise
    shutil.rmtree(staging, ignore_errors=True)
    metadata_path.unlink(missing_ok=True)
    record_update_state(root, "applied", phase="complete", version=metadata["version"],
                        source_sha256=metadata["source_sha256"])
    return backup


def _wait_for_process(pid, progress=None, timeout=PARENT_EXIT_TIMEOUT_SECONDS):
    if type(pid) is not int or pid <= 0 or pid == os.getpid():
        raise ValueError("invalid-update-parent")
    started = time.monotonic()
    last_progress = -INSTALLER_PROGRESS_SECONDS
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel.CloseHandle.restype = wintypes.BOOL
        handle = kernel.OpenProcess(0x00100000, False, pid)
        if not handle:
            raise ValueError("update-parent-open-failed")
        try:
            while True:
                remaining = max(1, int((timeout - (time.monotonic() - started)) * 1000))
                result = kernel.WaitForSingleObject(handle, min(1000, remaining))
                if result == 0:
                    return
                if result != 0x00000102:
                    raise ValueError("update-parent-wait-failed")
                elapsed = int(time.monotonic() - started)
                if elapsed >= timeout:
                    raise ValueError("update-parent-exit-timeout")
                if progress is not None and elapsed - last_progress >= INSTALLER_PROGRESS_SECONDS:
                    progress(elapsed)
                    last_progress = elapsed
        finally:
            kernel.CloseHandle(handle)
    else:
        while True:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            except PermissionError:
                raise ValueError("update-parent-check-failed") from None
            elapsed = int(time.monotonic() - started)
            if elapsed >= timeout:
                raise ValueError("update-parent-exit-timeout")
            if progress is not None and elapsed - last_progress >= INSTALLER_PROGRESS_SECONDS:
                progress(elapsed)
                last_progress = elapsed
            time.sleep(.25)


def launch_update(root, staging):
    root = Path(root).resolve()
    argv = [sys.executable, str(root / "start.py"), "update", "--apply", str(staging), "--wait-pid", str(os.getpid())]
    local = root / ".local"
    local.mkdir(parents=True, exist_ok=True)
    log_path = local / "update-installer.log"
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    kwargs = {"cwd": str(root), "stdin": subprocess.DEVNULL}
    if os.name == "nt":
        kwargs["creationflags"] = (subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP |
                                   subprocess.CREATE_BREAKAWAY_FROM_JOB)
    else:
        kwargs["start_new_session"] = True
    with log_path.open("a", encoding="utf-8") as installer_log:
        installer_log.write(timestamp + " installer-process-launching\n")
        installer_log.flush()
        subprocess.Popen(argv, stdout=installer_log, stderr=installer_log, **kwargs)

