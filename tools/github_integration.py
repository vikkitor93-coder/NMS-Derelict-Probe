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
}


def all_saved_evidence_outputs() -> tuple[list[Path], dict[str, list[str]]]:
    """Return existing action outputs once each, plus the actions that produce each path."""
    unique: dict[str, Path] = {}
    producers: dict[str, list[str]] = {}
    for action, paths in ACTION_OUTPUTS.items():
        if action == "all-saved-evidence":
            continue
        for path in paths:
            key = os.path.normcase(str(path.resolve()))
            unique.setdefault(key, path)
            producers.setdefault(key, []).append(action)
    return list(unique.values()), producers

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


def upload_action(action: str, capture_file: str | None = None, only_if_changed: bool = False) -> None:
    _log("upload_start", action=action)
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
        name = p.name
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
        manifest["files"].append(record)
    mbytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    mblob = _api_json(gh, "POST", f"repos/{REPO}/git/blobs", {"content": base64.b64encode(mbytes).decode("ascii"), "encoding": "base64"})
    entries.append({"path": f"{folder}/run-manifest.json", "mode": "100644", "type": "blob", "sha": mblob["sha"]})
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
            upload_action(args.action, args.capture_file, args.only_if_changed)
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
