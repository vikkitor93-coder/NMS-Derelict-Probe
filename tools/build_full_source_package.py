from __future__ import annotations

import base64
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_VERSION = "0.3.68"
PART_SIZE = 18_000
EXTRA_MANAGED_FILES = {
    "tools/build_full_source_package.py",
    "tests/test_auto_research_queue.py",
    "tests/test_runtime_hook_address_labels.py",
    "tests/test_system_scoped_root_capture.py",
    ".github/workflows/runtime-system-seed-tests.yml",
    "agent-ui/extensions/seed-lineage/1.0.3/manifest.json",
    "agent-ui/extensions/seed-lineage/1.0.3/panel.json",
    "agent-ui/extensions/runtime-dispatch/1.0.6/manifest.json",
    "agent-ui/extensions/runtime-dispatch/1.0.6/panel.json",
    "agent-patches/dungeon-decompile/NEW_ROOT_CAPTURE_REVIEW_20261007.json",
    "agent-patches/dungeon-decompile/ROOT_CALLBACK_CODE_20261007.json",
    "Analyze-Root-Seed-Batch.cmd",
    "Analyze-Root-Seed-Batch.ps1",
    "tools/analyze_root_seed_batch.py",
    "tests/test_root_seed_batch.py",
    "tests/test_root_seed_batch_upload.py",
}


def build() -> dict[str, object]:
    manifest_path = ROOT / "update-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("version") not in {"0.3.67", APP_VERSION}:
        raise RuntimeError(f"Expected v0.3.67 or current v{APP_VERSION} base manifest, got {manifest.get('version')!r}")

    files = set(manifest.get("managed_files", [])) | EXTRA_MANAGED_FILES
    # The updater manifest is fetched before installation. Packaging stale copies
    # would roll the local manifest backward, so keep both manifests out of the payload.
    files.discard("update-manifest.json")
    files.discard("update-manifest.remote.json")
    files = {p for p in files if p and not p.startswith("packages/")}
    missing = sorted(p for p in files if not (ROOT / p).is_file())
    if missing:
        raise RuntimeError("Refusing incomplete release; missing managed files:\n" + "\n".join(missing))

    (ROOT / "VERSION.txt").write_text(APP_VERSION + "\n", encoding="utf-8")
    ordered = sorted(files)
    archive_path = ROOT / f"NMS-Derelict-Probe-v{APP_VERSION}-source.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for rel in ordered:
            zf.write(ROOT / rel, rel)
    with zipfile.ZipFile(archive_path) as zf:
        if zf.testzip() is not None or sorted(zf.namelist()) != ordered:
            raise RuntimeError("Source ZIP failed CRC or member-list verification")

    payload = archive_path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    encoded = base64.b64encode(payload).decode("ascii")
    parts = [encoded[i:i + PART_SIZE] for i in range(0, len(encoded), PART_SIZE)]
    if base64.b64decode("".join(parts)) != payload:
        raise RuntimeError("Base64 chunk round-trip mismatch")
    part_dir = ROOT / "packages" / f"v{APP_VERSION}-full"
    shutil.rmtree(part_dir, ignore_errors=True)
    part_dir.mkdir(parents=True)
    for i, part in enumerate(parts):
        (part_dir / f"part-{i:03d}.b64").write_text(part, encoding="ascii")

    manifest.update({
        "version": APP_VERSION,
        "package_transport": "base64-chunks",
        "package_kind": "full",
        "package_parts": [f"packages/v{APP_VERSION}-full/part-{i:03d}.b64" for i in range(len(parts))],
        "package_sha256": digest,
        "package_size": len(payload),
        "managed_files": ordered,
    })
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (ROOT / "update-manifest.remote.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {"version": APP_VERSION, "package_sha256": digest, "package_size": len(payload), "parts": len(parts), "managed_files": len(ordered), "archive": archive_path.name}


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
