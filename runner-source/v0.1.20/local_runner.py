"""Offline worker: immutable snapshots, fixed jobs, optional GitHub evidence upload."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import zipfile
from datetime import datetime, timezone
from . import VERSION
from .common import HERE
from .package_experiment import members
from .runner_protocol import atomic_json, digest, publish_request, validate_request


def source_files(root=HERE):
    files, _ = members()
    return {name: Path(root) / name for name in files}


@contextmanager
def instance_lock(local):
    local.mkdir(parents=True, exist_ok=True)
    stream = (local / "runner.lock").open("a+b")
    acquired = False
    try:
        if os.name == "nt":
            import msvcrt
            stream.seek(0)
            stream.write(b"0")
            stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        acquired = True
        yield
    finally:
        if acquired:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        stream.close()


def capture_snapshot(files, destination, expected):
    for name, source in files.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    copied = {name: destination / name for name in files}
    if digest(copied) != expected or digest(files) != expected:
        raise ValueError("source-changed-during-snapshot")


def run_command(argv, cwd, timeout=600, show_output=True):
    """Kill owned process trees on timeout/cancel. No shell command requests."""
    job = None
    with subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          start_new_session=os.name != "nt") as process:
        def drain():
            for raw in iter(process.stdout.readline, b""):
                if show_output:
                    text = raw.decode("utf-8", errors="replace")
                    try:
                        print(text, end="", flush=True)
                    except UnicodeEncodeError:
                        print(text.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(
                              sys.stdout.encoding or "utf-8"), end="", flush=True)
            process.stdout.close()
        reader = threading.Thread(target=drain, daemon=True)
        reader.start()
        try:
            if os.name == "nt":
                from .windows_job import OwnedJob
                job = OwnedJob(process)
            code = process.wait(timeout=timeout)
        except BaseException:
            if job is not None:
                job.close()
                job = None
            elif os.name != "nt":
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            else:
                process.kill()
            process.wait()
            raise
        finally:
            if job is not None:
                job.close()
            reader.join(timeout=5)
        # Raw output is live console/UI only, never added to a log/ZIP.
        return code


def record(local, stage, status, **fields):
    event = {"schema_version": 1, "prototype_version": VERSION,
             "stage": stage, "status": status, **fields}
    with (local / "latest.log").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event) + "\n")
    atomic_json(local / "status.json", event)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{timestamp}] [{stage}] {status}", flush=True)


def healthy_python(root):
    from .install_unicorn import environment_python
    candidate = environment_python(root)
    if not candidate.is_file():
        candidate = Path(sys.executable)
    fingerprint = unicorn_health_fingerprint(root, candidate)
    if fingerprint is not None:
        try:
            cached = json.loads((Path(root) / ".local/unicorn-health.json").read_text(encoding="utf-8"))
            if (set(cached) == {"schema", "status", "fingerprint"}
                    and type(cached["schema"]) is int and cached["schema"] == 1
                    and cached["status"] == "passed" and cached["fingerprint"] == fingerprint):
                return str(candidate)
        except (OSError, ValueError, TypeError):
            pass
    code = run_command([str(candidate), "-c",
        "from unicorn import Uc,UC_ARCH_X86,UC_MODE_64; import unicorn; "
        "assert unicorn.__version__=='2.1.4'; "
        "u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(0x1000,4096); "
        "u.mem_write(0x1000,bytes.fromhex('b82a000000')); "
        "u.emu_start(0x1000,0x1005,count=1)"], root, 30, show_output=False)
    if code:
        print("Unicorn is not ready in this Python environment. Installing/repairing it automatically...", flush=True)
        if run_command([sys.executable, "-u", str(root / "install_unicorn.py")], root, 600):
            raise ValueError("unicorn-setup-failed")
        candidate = environment_python(root)
        fingerprint = unicorn_health_fingerprint(root, candidate)
    if fingerprint is not None and not code:
        fingerprint = unicorn_health_fingerprint(root, candidate)
    if fingerprint is not None:
        atomic_json(Path(root) / ".local/unicorn-health.json",
                    {"schema": 1, "status": "passed", "fingerprint": fingerprint})
    return str(candidate)


def unicorn_health_fingerprint(root, candidate):
    """Hash the pinned local Unicorn package so its successful smoke test is reusable."""
    root, candidate = Path(root), Path(candidate)
    if candidate.parent.name.casefold() != "scripts" and candidate.parent.name.casefold() != "bin":
        return None
    environment = candidate.parent.parent
    if os.name == "nt":
        site_roots = [environment / "Lib/site-packages"]
    else:
        site_roots = list((environment / "lib").glob("python*/site-packages"))
    package_dirs = []
    for site in site_roots:
        package_dirs.extend(path for path in (site / "unicorn",) if path.is_dir())
        package_dirs.extend(path for path in site.glob("unicorn-*.dist-info") if path.is_dir())
    if not package_dirs:
        return None
    files = {"python": candidate}
    for directory in package_dirs:
        for path in directory.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                files[str(path.relative_to(environment)).replace("\\", "/")] = path
    if "python" not in files:
        return None
    return digest(files)


def set_paused(root, value):
    if type(value) is not bool:
        raise ValueError("invalid-runner-control")
    atomic_json(root / ".local/runner-control.json", {"schema": 1, "paused": value})


def is_paused(root):
    path = root / ".local/runner-control.json"
    if not path.exists():
        return False
    try:
        value = json.loads(path.read_text())
        if (set(value) != {"schema", "paused"} or type(value["schema"]) is not int
                or value["schema"] != 1 or type(value["paused"]) is not bool):
            raise ValueError()
        return value["paused"]
    except (ValueError, TypeError):
        raise ValueError("invalid-runner-control") from None


def file_sha256(path):
    with Path(path).open("rb") as stream:
        if hasattr(hashlib, "file_digest"):
            return hashlib.file_digest(stream, "sha256").hexdigest()
        result = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
        return result.hexdigest()


def save_executable_selection(root, path):
    candidate = Path(path)
    if candidate.name.casefold() != "nms.exe":
        raise ValueError("selected-file-not-nms-exe")
    selected = candidate.resolve(strict=True)
    if not selected.is_file():
        raise ValueError("selected-file-not-nms-exe")
    value = {"schema": 1, "path": str(selected), "sha256": file_sha256(selected)}
    atomic_json(Path(root) / ".local/nms-exe.json", value)
    return selected


def load_executable_selection(root):
    config_path = Path(root) / ".local/nms-exe.json"
    if not config_path.is_file():
        return None
    try:
        value = json.loads(config_path.read_text(encoding="utf-8"))
        if (not isinstance(value, dict) or set(value) != {"schema", "path", "sha256"}
                or type(value["schema"]) is not int or value["schema"] != 1
                or not isinstance(value["path"], str)
                or not isinstance(value["sha256"], str)
                or len(value["sha256"]) != 64
                or any(character not in "0123456789abcdef" for character in value["sha256"])):
            raise ValueError()
        selected = Path(value["path"])
        if (not selected.is_absolute() or selected.name.casefold() != "nms.exe"
                or not selected.is_file() or file_sha256(selected) != value["sha256"]):
            raise ValueError()
        return selected.resolve()
    except (OSError, ValueError, TypeError, KeyError):
        raise ValueError("nms-exe-selection-missing-or-changed") from None


def automatic_check_key(source_sha256, action, exe):
    return {"source_sha256": source_sha256, "action": action,
            "exe_sha256": file_sha256(exe) if exe is not None else None}


def has_completed_automatic_check(root, key):
    path = Path(root) / ".local/automatic-check.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return (set(value) == {"schema", "key", "status"}
                and type(value["schema"]) is int and value["schema"] == 1
                and value["key"] == key and value["status"] in ("passed", "failed"))
    except (OSError, ValueError, TypeError, KeyError):
        return False


def record_automatic_check(root, key, status):
    if status in ("passed", "failed"):
        atomic_json(Path(root) / ".local/automatic-check.json",
                    {"schema": 1, "key": key, "status": status})


def load_update_channel(local, update_url):
    path = Path(local) / "update-channel.json"
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if (not isinstance(value, dict) or set(value) != {"schema", "enabled", "feed_url"}
                or type(value["schema"]) is not int or value["schema"] != 1
                or type(value["enabled"]) is not bool):
            raise ValueError()
        from .update_protocol import LEGACY_UPDATE_URL
        if value["feed_url"] == LEGACY_UPDATE_URL:
            value["feed_url"] = update_url
            atomic_json(path, value)
        elif value["feed_url"] != update_url:
            raise ValueError()
        return value
    except (OSError, ValueError, TypeError):
        raise ValueError("invalid-update-channel") from None


def bundle(folder):
    allowed = ("result.json", "latest.log", "diagnose.json", "code.json", "emulate.json",
               "offline-evidence.zip", "AI_HANDOFF.md", "GITHUB_CHECK_PROMPT.md")
    target = folder / "runner-evidence.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in allowed:
            path = folder / name
            if path.is_file():
                archive.write(path, name)
    return target


def export_key(snapshot, exe):
    names = ("export_evidence.py", "build_corpus.py", "common.py", "__init__.py")
    files = {name: snapshot / name for name in names}
    for directory in ("fixtures", "tools"):
        for path in (snapshot / directory).glob("*"):
            if path.is_file():
                files[directory + "/" + path.name] = path
    with Path(exe).open("rb") as stream:
        exe_hash = hashlib.file_digest(stream, "sha256").hexdigest() if hasattr(hashlib, "file_digest") else None
    if exe_hash is None:  # Python 3.10 compatibility.
        from .common import sha256
        exe_hash = sha256(exe)
    return {"code_sha256": digest(files), "exe_sha256": exe_hash}


def cached_export(local, key, target):
    from .common import sha256
    metadata = local / "export-cache.json"
    cached = local / "cached-offline-evidence.zip"
    try:
        value = json.loads(metadata.read_text())
        if value["key"] != key or value["zip_sha256"] != sha256(cached):
            return False
        shutil.copyfile(cached, target)
        return True
    except (OSError, ValueError, KeyError):
        return False


def execute(root, request, python, exe=None):
    local = root / ".local"
    files = source_files(root)
    expected = digest(files)
    request = validate_request(request)
    if request["source_sha256"] != expected:
        raise ValueError("stale-request-source")
    if sum(1 for path in (root / "reports").glob("*") if path.is_dir()) >= 100:
        raise ValueError("report-limit-review-required")
    folder = root / "reports" / request["request_id"]
    folder.mkdir(parents=True, exist_ok=False)  # A run ID is never reused.
    (local / "latest.log").write_text("", encoding="utf-8")
    result = {"schema_version": 1, "prototype_version": VERSION, **request,
              "status": "running", "stages": [], "root_generation_verified": False,
              "execution_location": "local", "local_only": not (local / "github-config.json").is_file(),
              "errors": [], "source_zip": "source.zip",
              "evidence_zip": "runner-evidence.zip"}
    record(local, "snapshot", "running", request_id=request["request_id"], source_sha256=expected)
    try:
        with tempfile.TemporaryDirectory(prefix="nms-offline-") as tmp:
            snapshot = Path(tmp) / "derelict_offline"
            capture_snapshot(files, snapshot, expected)
            # Make the exact tested handoff readable to scheduled reviewers
            # without requiring them to unpack the source archive.
            for name in ("AI_HANDOFF.md", "GITHUB_CHECK_PROMPT.md"):
                if (snapshot / name).is_file():
                    shutil.copyfile(snapshot / name, folder / name)
            tasks = [("source-package", ["package", "--out", str(folder / "source.zip")]),
                     ("tests", ["test"]),
                     ("diagnose", ["diagnose", "--out", str(folder / "diagnose.json")]),
                     ("code", ["code", "--out", str(folder / "code.json")]),
                     ("emulate", ["emulate", "--repetitions", "1000", "--out", str(folder / "emulate.json")])]
            if request["action"] == "offline-check-and-export":
                tasks.append(("export", ["export", "--exe", str(exe), "--out", str(folder / "offline-evidence.zip")]))
            for stage, args in tasks:
                record(local, stage, "running")
                key = None
                if stage == "export":
                    if exe is None:
                        raise ValueError("nms-exe-not-selected")
                    key = export_key(snapshot, exe)
                    if cached_export(local, key, folder / "offline-evidence.zip"):
                        result["stages"].append({"stage": stage, "returncode": 0, "reused": True})
                        record(local, stage, "reused-verified-export")
                        continue
                try:
                    code = run_command([python, "-u", str(snapshot / "start.py"), *args], snapshot)
                except subprocess.TimeoutExpired:
                    code = 124
                result["stages"].append({"stage": stage, "returncode": code})
                record(local, stage, "passed" if code == 0 else "failed", returncode=code)
                if code:
                    raise ValueError(stage + ("-timeout" if code == 124 else "-failed"))
                if key is not None:
                    from .common import sha256
                    cached = local / "cached-offline-evidence.zip"
                    shutil.copyfile(folder / "offline-evidence.zip", cached)
                    atomic_json(local / "export-cache.json", {"schema_version": 1,
                        "key": key, "zip_sha256": sha256(cached)})
            result["status"] = "passed"
    except KeyboardInterrupt:
        result["status"] = "cancelled"
        result["errors"].append("user-stopped")
    except (ValueError, OSError) as error:
        result["status"] = "failed"
        # Known codes only; filesystem exception messages may include usernames.
        reason = str(error) if isinstance(error, ValueError) else "filesystem-or-process-error"
        result["errors"].append(reason)
    try:
        changed = digest(source_files(root)) != expected
    except OSError:
        changed = True
    if changed:
        result["status"] = "stale"
        result["errors"].append("source-changed-during-run")
    result["source_zip_available"] = (folder / "source.zip").is_file()
    record(local, "complete", result["status"], errors=result["errors"], request_id=request["request_id"],
           source_sha256=expected)
    shutil.copyfile(local / "latest.log", folder / "latest.log")
    atomic_json(folder / "result.json", result)
    bundle(folder)
    atomic_json(local / "latest-result.json", result)
    return result


def claim(root):
    ready = root / "requests" / "ready.json"
    claimed = root / ".local" / "claimed-request.json"
    if claimed.exists():
        raise ValueError("interrupted-request-needs-review")
    if not ready.is_file():
        return None
    os.replace(ready, claimed)
    try:
        if claimed.stat().st_size > 4096:
            raise ValueError("request-too-large")
        return validate_request(json.loads(claimed.read_text(encoding="utf-8")))
    except (ValueError, OSError):
        os.replace(claimed, claimed.with_name("rejected-request.json"))
        raise ValueError("invalid-request") from None


def watch(root, once=False, exe=None, interval=5):
    local = root / ".local"
    with instance_lock(local):
        print(f"NMS Offline runner {VERSION}. Ctrl+C stops. NMS can stay closed.", flush=True)
        if exe is not None:
            exe = save_executable_selection(root, exe)
        elif (local / "nms-exe.json").is_file():
            exe = load_executable_selection(root)
        from .github_exchange import config, Uploader, TransportError
        try:
            settings = config(root)
        except TransportError as error:
            print("[github-upload] " + str(error), flush=True)
            return 2
        uploader = Uploader(root, settings) if settings else None
        print("GitHub uploads: " + ("enabled" if uploader else "off (run Setup-GitHub.cmd to enable)"), flush=True)
        from .update_protocol import (POLL_SECONDS, UPDATE_URL, fetch_package, launch_update,
                                      record_update_state, stage_update)
        (local / "latest.log").write_text("", encoding="utf-8")
        record(local, "setup", "running")
        try:
            python = healthy_python(root)
        except (ValueError, OSError, subprocess.TimeoutExpired):
            record(local, "setup", "failed", errors=["unicorn-setup-failed"])
            return 2
        last = None
        candidate = None
        startup_cache_checked = False
        pause_recorded = False
        last_update_check = 0.0
        while True:
            try:
                if time.monotonic() - last_update_check >= POLL_SECONDS:
                    last_update_check = time.monotonic()
                    if (local / "update-channel.json").is_file():
                        try:
                            channel = load_update_channel(local, UPDATE_URL)
                            if channel["enabled"]:
                                feed, archive = fetch_package(channel["feed_url"])
                                from .update_protocol import version_tuple
                                if version_tuple(feed["version"]) > version_tuple(VERSION):
                                    staging = stage_update(root, archive, feed)
                                    atomic_json(local / "update-requested.json", {
                                        "schema": 1, "version": feed["version"], "source_sha256": feed["source_sha256"]})
                                    record_update_state(root, "pending", phase="installer-starting",
                                                        version=feed["version"],
                                                        source_sha256=feed["source_sha256"])
                                    record(local, "update", "verified-restart-pending", version=feed["version"])
                                    try:
                                        launch_update(root, staging)
                                    except OSError:
                                        record_update_state(root, "failed", phase="installer-launch-failed",
                                                            version=feed["version"],
                                                            source_sha256=feed["source_sha256"],
                                                            error="installer-process-launch-failed")
                                        raise
                                    return 75
                                else:
                                    record(local, "update", "current")
                        except (ValueError, OSError):
                            record(local, "update", "check-failed", errors=["feed-or-package-verification-failed"])
                if not once and is_paused(root):
                    if uploader:
                        uploader.poll()
                    if not pause_recorded:
                        record(local, "runner", "paused")
                        pause_recorded = True
                    candidate = None
                    time.sleep(interval)
                    continue
                pause_recorded = False
                current = digest(source_files(root))
                if not startup_cache_checked:
                    initial_action = "offline-check-and-export" if exe is not None else "offline-check"
                    initial_key = automatic_check_key(current, initial_action, exe)
                    if has_completed_automatic_check(root, initial_key):
                        last = candidate = current
                    startup_cache_checked = True
                request = claim(root)
                if uploader:
                    uploader.poll()
                if request is None and (once or current != last and current == candidate):
                    request = {"schema": 1, "request_id": uuid.uuid4().hex,
                               "source_sha256": current,
                               "action": "offline-check-and-export" if exe is not None else "offline-check"}
                if request is not None:
                    check_key = automatic_check_key(current, request["action"], exe)
                    try:
                        result = execute(root, request, python, exe)
                    except (ValueError, OSError) as error:
                        reason = str(error) if isinstance(error, ValueError) else "reused-id-or-filesystem-error"
                        record(local, "request", "rejected", errors=[reason])
                        result = {"status": "failed"}
                        if reason == "report-limit-review-required":
                            return 2
                    (local / "claimed-request.json").unlink(missing_ok=True)
                    last = current
                    if result.get("request_id") == request.get("request_id"):
                        record_automatic_check(root, check_key, result.get("status"))
                    uploaded = uploader.poll(force=True) if uploader and result["status"] != "cancelled" else True
                    if once or result["status"] == "cancelled":
                        return 0 if result["status"] == "passed" and uploaded else 1
                    record(local, "watching", "waiting-for-source-change")
                candidate = current
                time.sleep(interval)
            except KeyboardInterrupt:
                record(local, "runner", "stopped")
                return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--watch", action="store_true", help="Explicit console watcher (default worker behavior)")
    controls = parser.add_mutually_exclusive_group()
    controls.add_argument("--pause", action="store_true")
    controls.add_argument("--resume", action="store_true")
    parser.add_argument("--exe", type=Path, help="Read-only NMS.exe selection for automatic bounded exports")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--request", choices=("offline-check", "offline-check-and-export"))
    args = parser.parse_args(argv)
    root = HERE.resolve()
    if args.pause or args.resume:
        set_paused(root, args.pause)
        return 0
    if args.status:
        for name in ("status.json", "latest-result.json", "github-status.json"):
            path = root / ".local" / name
            print(path.read_text() if path.is_file() else name + ": not recorded")
        return 0
    if args.request:
        print(json.dumps(publish_request(root, digest(source_files(root)), args.request), indent=2))
        return 0
    try:
        if os.name == "nt":
            def stop_signal(signum, frame):
                raise KeyboardInterrupt()
            signal.signal(signal.SIGBREAK, stop_signal)
        return watch(root, args.once, args.exe.resolve() if args.exe else None)
    except KeyboardInterrupt:
        record(root / ".local", "runner", "stopped")
        return 0
    except ValueError as error:
        record(root / ".local", "runner", "blocked", errors=[str(error)])
        print("Review the blocked request and RUNNER.md before restarting.", flush=True)
        return 2
    except OSError:
        print("Runner could not start. Check that another instance is not running and the folder is writable.", flush=True)
        return 2
