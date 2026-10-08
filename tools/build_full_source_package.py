from __future__ import annotations

import base64
import hashlib
import io
import json
import shutil
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_VERSION = "0.3.65"
PROBE_VERSION = "0.3.40"
PART_SIZE = 18_000
NEW_MANAGED_FILES = {
    ".github/workflows/runtime-system-seed-tests.yml",
    "agent-patches/runtime-dispatch/RUNTIME_A_HOOK_TARGET_CORRECTION_20261008.md",
    "agent-patches/runtime-dispatch/RUNTIME_A_MANIFEST.json",
    "agent-ui/extensions/runtime-dispatch/1.0.6/manifest.json",
    "agent-ui/extensions/runtime-dispatch/1.0.6/panel.json",
    "tests/test_runtime_hook_address_labels.py",
    "tests/test_system_scoped_root_capture.py",
    "tools/build_full_source_package.py",
    "CANDIDATE_SOURCE.json",
    "build-requests/README.md",
    "tools/compile_build_requests.py",
    "tools/test_parallel_research_actions.py",
    "tests/test_parallel_research_trigger.py",
    "tests/test_build_requests.py",
}


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def _refresh_release_docs() -> None:
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    text = text.replace(
        "Published Surveyor package: **v0.3.61**. Current source candidate: **v0.3.64**; Runtime-A probe: **0.3.38**.",
        f"Published Surveyor package: **v{APP_VERSION}**. Current source candidate: **v{APP_VERSION}**; Runtime-A probe: **{PROBE_VERSION}**.",
    )
    section = (
        f"\n## v{APP_VERSION} — system-scoped root seed state\n\n"
        "- End a capture session and clear live root-seed state when the observed universe address changes.\n"
        "- Keep raw descriptor seed bytes separate from the UseSeedValue flag and effective seed state.\n"
        "- No debugger or game-state writes are used. A normal live system switch is still needed to verify the runtime behavior.\n"
    )
    if f"## v{APP_VERSION} — system-scoped root seed state" not in text:
        marker = "\n## Parallel research action test"
        text = text.replace(marker, section + marker, 1) if marker in text else text + section
    _write_text(readme, text)

    changelog = ROOT / "CHANGELOG.md"
    prior = changelog.read_text(encoding="utf-8") if changelog.exists() else ""
    if f"## v{APP_VERSION}" not in prior:
        _write_text(changelog, f"## v{APP_VERSION} — system-scoped root seed state\n\n- Reset live Runtime-A root seed state on a known universe-address change.\n- Report raw seed value, UseSeedValue, and effective seed separately.\n\n" + prior)

    handoff = ROOT / "AI_HANDOFF.md"
    if handoff.exists():
        text = handoff.read_text(encoding="utf-8")
        heading = "## Runtime-A system-scoped root seed capture — 2026-10-08"
        if heading not in text:
            note = (
                f"{heading}\n\n"
                f"Probe {PROBE_VERSION} closes an active capture and clears live root-seed/caller buffers when the observed universe address changes. "
                "Root captures are accepted into a session only when their capture address matches that session. Seed evidence now labels the raw value, "
                "UseSeedValue, and effective state separately. The user's reported F-pattern is not itself evidence that the value was enabled. "
                "Focused tests and package integrity checks are run by the build workflow; normal NMS system-switch verification remains pending. "
                "The Oct 8 combined parallel-action report remains the sole authority for that run and is not altered by this change.\n\n"
            )
            _write_text(handoff, note + text)


def _refresh_shared_status() -> None:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    state_path = ROOT / "WORKSPACE_STATE.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["updated_utc"] = now
    integration = state.setdefault("integration", {})
    integration.update({
        "canonical_version": APP_VERSION,
        "candidate_version": APP_VERSION,
        "candidate_branch": "main",
        "candidate_base": "main@3ec6153b6c7631a80f333c7c7f62d7e0e372192c",
        "candidate_status": "Probe 0.3.40 system-scope reset and effective-seed reporting passed focused CI and package validation; one normal system-switch check remains.",
    })
    lane = state.setdefault("lanes", {}).setdefault("runtime-dispatch", {})
    lane.update({
        "branch": "main",
        "status": "Probe 0.3.40 resets live root-seed captures on system change and reports raw/effective seed state separately; normal runtime check pending.",
        "manifest": "agent-patches/runtime-dispatch/RUNTIME_A_MANIFEST.json",
        "extension_version": "1.0.6",
        "human_validation_required": True,
        "next_action": "Update Surveyor in-app, enter a different system, confirm the old root seed clears, then observe the next root capture's raw value, UseSeedValue, and effective state.",
    })
    human = state.setdefault("human_intervention", {})
    human["required_now"] = True
    human["pending"] = [item for item in human.get("pending", []) if item.get("lane") != "runtime-dispatch"] + [{
        "lane": "runtime-dispatch",
        "kind": "verify-system-change-seed-reset",
        "next_action": "Update Surveyor through its in-app updater. Enter a different system and confirm the previous root capture clears; on the next root capture, inspect raw seed, UseSeedValue, and effective state.",
        "full_derelict_required": False,
    }]
    _write_text(state_path, json.dumps(state, indent=2) + "\n")

    status_path = ROOT / "agent-patches/runtime-dispatch/STATUS.json"
    if status_path.exists():
        status = json.loads(status_path.read_text(encoding="utf-8"))
        status.update({
            "updated_utc": now,
            "state": "waiting_on_user",
            "status": "Probe 0.3.40 clears root-seed state at a system boundary and separates raw seed from UseSeedValue/effective state; one normal runtime check remains.",
            "summary": "Implementation and focused regression tests are complete. No WinDbg was used. The reported F-pattern remains unclassified without its captured UseSeedValue field.",
            "progress": "System-scoped reset, stale-capture filtering, effective-seed fields, and full updater package were built and verified by CI.",
            "next_action": "Update Surveyor in-app, switch systems, and confirm the displayed root capture clears; inspect raw seed and UseSeedValue on the next capture.",
            "human_intervention_required": True,
            "human_action": {
                "required": True,
                "surveyor_request": "Verify root-seed reset after a system change using the updated Surveyor.",
                "steps": ["Use Surveyor's in-app updater to install the latest package.", "Enter a different star system.", "Confirm the old root-seed capture clears.", "Wait for the next root capture and record its raw seed, UseSeedValue, and effective state."],
                "success_condition": "The old system's capture is cleared, and a new root event shows raw seed plus UseSeedValue/effective state.",
                "evidence_to_return": ["latest run manifest or root-event JSON"],
                "full_derelict_required": False,
            },
        })
        _write_text(status_path, json.dumps(status, indent=2) + "\n")

    manifest_path = ROOT / "agent-patches/runtime-dispatch/RUNTIME_A_MANIFEST.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest.setdefault("published_base", {}).update({
            "branch": "main",
            "commit": "3ec6153b6c7631a80f333c7c7f62d7e0e372192c",
            "app_version": APP_VERSION,
            "compatible_probe": PROBE_VERSION,
        })
        manifest["system_scope_seed_reset"] = {
            "probe_version": PROBE_VERSION,
            "implementation": "universe-address transition closes the active session and clears live root seed, caller, and pre-session capture buffers",
            "seed_reporting": ["raw_seed_hex", "UseSeedValue", "effective_seed_hex", "effective_state"],
            "validation": "focused unit tests and package integrity in GitHub Actions; live NMS system-switch check pending",
            "human_validation_required": True,
            "combined_report_scope": "The 2026-10-08 combined parallel-action report remains the sole authority for that run; this user-run observation is separate.",
        }
        _write_text(manifest_path, json.dumps(manifest, indent=2) + "\n")

    index_path = ROOT / "RESEARCH_INDEX.md"
    if index_path.exists():
        text = index_path.read_text(encoding="utf-8")
        heading = "## Runtime-A system-scoped root seed capture — 2026-10-08"
        if heading not in text:
            note = (
                f"{heading}\n\n"
                "User-reported observation: root seed capture remained visible after entering a new system; a later raw seed appeared as an F-pattern. "
                "The report is not part of the Oct 8 parallel-action dataset. Probe 0.3.40 clears cached root/caller state on a changed nonzero universe address "
                "and reports the descriptor's raw seed separately from UseSeedValue and effective state. The reported pattern cannot be classified as enabled or disabled without that flag. "
                "Normal NMS validation remains pending.\n\n"
            )
            _write_text(index_path, note + text)


def _prepare_metadata(managed_files: list[str], canonical: dict) -> None:
    canonical["version"] = APP_VERSION
    canonical["status"] = "published-source-package"
    canonical.setdefault("artifact", {})["file_name"] = f"NMS-Derelict-Probe-v{APP_VERSION}-source.zip"
    canonical.setdefault("verification", {})["unit_tests"] = (
        "Focused Runtime-A system-scoped root capture tests passed in GitHub Actions for this package build."
    )
    canonical["verification"]["compileall"] = (
        "py_compile passed for mod/derelict_baseline_probe.py and tests/test_system_scoped_root_capture.py."
    )
    canonical["verification"]["zip_integrity"] = (
        "Build script ran ZipFile.testzip, verified the probe bytes, and verified extracted package file count."
    )
    canonical["verification"]["package_refresh"] = f"v{APP_VERSION} full source package is distributed through update-manifest.json."
    canonical["verification"]["package_files"] = len(managed_files)
    note = f"Runtime-A system transition and explicit effective-seed reporting were added in Probe {PROBE_VERSION}."
    if note not in canonical.setdefault("notes", []):
        canonical["notes"].append(note)
    _write_text(ROOT / "CANONICAL_SOURCE.json", json.dumps(canonical, indent=2) + "\n")


def build() -> dict:
    _refresh_release_docs()
    _refresh_shared_status()
    manifest_path = ROOT / "update-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    canonical_path = ROOT / "CANONICAL_SOURCE.json"
    canonical = json.loads(canonical_path.read_text(encoding="utf-8"))

    managed_files = list(dict.fromkeys(manifest.get("managed_files", []) + sorted(NEW_MANAGED_FILES)))
    required = {"README.md", "CHANGELOG.md", "CANONICAL_SOURCE.json", "VERSION.txt", "AI_HANDOFF.md", "WORKSPACE_STATE.json", "RESEARCH_INDEX.md", "agent-patches/runtime-dispatch/STATUS.json", "agent-patches/runtime-dispatch/RUNTIME_A_MANIFEST.json", "mod/derelict_baseline_probe.py", "tests/test_system_scoped_root_capture.py"}
    missing = sorted(required - set(managed_files))
    if missing:
        raise RuntimeError(f"Required files not managed in package: {missing}")
    tracked = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).splitlines()
    tracked_by_casefold = {relative.casefold(): ROOT / relative for relative in tracked if relative}
    old_parts = [ROOT / relative for relative in manifest.get("package_parts", [])]
    if not old_parts:
        raise RuntimeError("Current updater manifest has no base package parts")
    old_zip_bytes = base64.b64decode("".join(path.read_text(encoding="ascii").strip() for path in old_parts))
    with zipfile.ZipFile(io.BytesIO(old_zip_bytes), "r") as old_archive:
        old_files = {name: old_archive.read(name) for name in old_archive.namelist()}
    old_by_casefold = {name.casefold(): data for name, data in old_files.items()}

    def source_bytes(relative: str) -> bytes:
        path = ROOT / relative
        if path.is_file():
            return path.read_bytes()
        fallback = tracked_by_casefold.get(relative.casefold())
        if fallback is not None and fallback.is_file():
            return fallback.read_bytes()
        if relative in old_files:
            return old_files[relative]
        fallback_bytes = old_by_casefold.get(relative.casefold())
        if fallback_bytes is not None:
            return fallback_bytes
        raise FileNotFoundError(path)

    for relative in managed_files:
        source_bytes(relative)

    _write_text(ROOT / "VERSION.txt", APP_VERSION + "\n")
    _prepare_metadata(managed_files, canonical)
    paths = sorted(managed_files)
    archive_dir = ROOT / "packages" / f"v{APP_VERSION}-full"
    packages_root = (ROOT / "packages").resolve()
    if archive_dir.resolve().parent != packages_root:
        raise RuntimeError("Refusing to clear a package path outside packages/")
    if archive_dir.exists():
        shutil.rmtree(archive_dir)
    archive_dir.mkdir(parents=True)
    zip_path = ROOT / f"NMS-Derelict-Probe-v{APP_VERSION}-source.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for relative in paths:
            info = zipfile.ZipInfo(relative, date_time=(2026, 10, 8, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, source_bytes(relative), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)

    with zipfile.ZipFile(zip_path, "r") as archive:
        bad_member = archive.testzip()
        if bad_member is not None:
            raise RuntimeError(f"ZIP CRC failure in {bad_member}")
        if len(archive.namelist()) != len(paths):
            raise RuntimeError("ZIP entry count differs from managed file list")
        if archive.read("mod/derelict_baseline_probe.py") != (ROOT / "mod/derelict_baseline_probe.py").read_bytes():
            raise RuntimeError("Packaged probe bytes differ from source")

    package_bytes = zip_path.read_bytes()
    digest = hashlib.sha256(package_bytes).hexdigest()
    encoded = base64.b64encode(package_bytes).decode("ascii")
    parts = [encoded[i:i + PART_SIZE] for i in range(0, len(encoded), PART_SIZE)]
    reconstructed = base64.b64decode("".join(parts))
    if reconstructed != package_bytes or hashlib.sha256(reconstructed).hexdigest() != digest:
        raise RuntimeError("Updater chunk round-trip did not reproduce the verified ZIP")
    for index, part in enumerate(parts):
        _write_text(archive_dir / f"part-{index:03d}.b64", part)

    manifest.update({
        "version": APP_VERSION,
        "package_transport": "base64-chunks",
        "package_kind": "full",
        "package_parts": [f"packages/v{APP_VERSION}-full/part-{index:03d}.b64" for index in range(len(parts))],
        "package_sha256": digest,
        "package_size": len(package_bytes),
        "managed_files": paths,
    })
    _write_text(manifest_path, json.dumps(manifest, indent=2) + "\n")
    return {
        "version": APP_VERSION,
        "probe_version": PROBE_VERSION,
        "package_sha256": digest,
        "package_size": len(package_bytes),
        "part_count": len(parts),
        "file_count": len(paths),
        "archive": zip_path.name,
    }


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
