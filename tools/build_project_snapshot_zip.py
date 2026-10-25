"""Build a complete project snapshot ZIP from the local working tree.

Unlike tools/build_full_source_package.py (the Surveyor release packager owned
by the main compiler), this reads local files directly, because the git copy can
lag the working tree. It excludes runtime/user data, caches, archives, raw game
binaries and large generated outputs, and records every exclusion in
SNAPSHOT_EXCLUDED.json inside the ZIP.

Usage: python -I tools/build_project_snapshot_zip.py --label <short-label>
       [--out-dir DIR] [--skip-unchanged] [--keep N]
--skip-unchanged compares a path/size/mtime fingerprint with the newest ZIP in
--out-dir and builds nothing if the tree is unchanged. --keep N deletes all but
the newest N snapshot ZIPs in --out-dir (only files this tool names).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Runtime, user, upload and package data: not project source.
EXCLUDED_DIRS = {
    ".git", "__pycache__", ".pytest_cache", "research-uploads", "live-runtime",
    "session-backups", "user-data", "packages",
}
EXCLUDED_ROOT_FILES = {"filenames.txt"}
EXCLUDED_SUFFIXES = {".pyc", ".zip", ".bak", ".tmp", ".exe", ".mbin", ".pc", ".dmp"}
# In-game screenshot samples; the research reports summarize them.
EXCLUDED_RESEARCH_SUFFIXES = {".jpg", ".jpeg"}
MAX_FILE_BYTES = 20_000_000
MAX_EXCLUDED_HASH_BYTES = 2_000_000


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _exclusion_reason(rel: str, path: Path, size: int) -> str | None:
    parts = rel.split("/")
    if len(parts) == 1 and rel in EXCLUDED_ROOT_FILES:
        return "root listing dump"
    suffix = path.suffix.lower()
    if suffix in EXCLUDED_SUFFIXES or ".bak" in path.name.lower():
        return f"excluded type {suffix or path.name}"
    if parts[0] == "research-output" and suffix in EXCLUDED_RESEARCH_SUFFIXES:
        return "screenshot sample"
    if size > MAX_FILE_BYTES:
        return f"larger than {MAX_FILE_BYTES} bytes (generated output)"
    return None


SNAPSHOT_PREFIX = "NMS-Derelict-Probe-snapshot-"


def _fingerprint(included: list[str]) -> str:
    digest = hashlib.sha256()
    for rel in included:
        stat = (ROOT / rel).stat()
        digest.update(f"{rel}\0{stat.st_size}\0{stat.st_mtime_ns}\n".encode("utf-8"))
    return digest.hexdigest().upper()


def _snapshots(out_dir: Path) -> list[Path]:
    return sorted(out_dir.glob(SNAPSHOT_PREFIX + "*.zip"), key=lambda p: p.name)


def build(label: str, out_dir: Path = ROOT, skip_unchanged: bool = False, keep: int | None = None) -> dict[str, object]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir.mkdir(parents=True, exist_ok=True)
    archive = out_dir / f"{SNAPSHOT_PREFIX}{stamp}-{label}.zip"
    included: list[str] = []
    excluded_dirs: dict[str, int | None] = {}
    excluded_files: list[dict[str, object]] = []

    for current, dirs, files in os.walk(ROOT):
        current_path = Path(current)
        for name in sorted(dirs):
            if name in EXCLUDED_DIRS:
                rel_dir = (current_path / name).relative_to(ROOT).as_posix()
                # Do not descend excluded runtime/history trees just to count them. Some contain
                # huge Cloud Files logs and can stall the 30-minute snapshot task for hours.
                excluded_dirs[rel_dir] = None
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDED_DIRS)
        for name in sorted(files):
            path = current_path / name
            rel = path.relative_to(ROOT).as_posix()
            size = path.stat().st_size
            reason = _exclusion_reason(rel, path, size)
            if reason:
                record: dict[str, object] = {"path": rel, "bytes": size, "reason": reason}
                if rel.startswith("research-output/"):
                    if size <= MAX_EXCLUDED_HASH_BYTES:
                        record["sha256"] = _sha256(path)
                    else:
                        record["sha256_skipped"] = "large excluded file; not copied into snapshot"
                excluded_files.append(record)
            else:
                included.append(rel)

    fingerprint = _fingerprint(included)
    previous = _snapshots(out_dir)
    if skip_unchanged and previous:
        try:
            with zipfile.ZipFile(previous[-1]) as zf:
                prior = json.loads(zf.read("SNAPSHOT_EXCLUDED.json")).get("fingerprint")
        except (OSError, KeyError, ValueError, zipfile.BadZipFile):
            prior = None
        if prior == fingerprint:
            return {"skipped": "unchanged", "latest": str(previous[-1]), "fingerprint": fingerprint}

    manifest = {
        "schema_version": 1,
        "created_utc": stamp,
        "label": label,
        "source": "local working tree (not git)",
        "fingerprint": fingerprint,
        "included_files": len(included),
        "excluded_directories": excluded_dirs,
        "excluded_files": excluded_files,
    }
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for rel in included:
            zf.write(ROOT / rel, rel)
        zf.writestr("SNAPSHOT_EXCLUDED.json", json.dumps(manifest, indent=2))
    with zipfile.ZipFile(archive) as zf:
        names = zf.namelist()
        if zf.testzip() is not None or sorted(names) != sorted(included + ["SNAPSHOT_EXCLUDED.json"]):
            raise RuntimeError("Snapshot ZIP failed CRC or member-list verification")
        if "AI_HANDOFF.md" not in names:
            raise RuntimeError("Snapshot ZIP is missing AI_HANDOFF.md")
    removed: list[str] = []
    if keep is not None and keep > 0:
        for old in _snapshots(out_dir)[:-keep]:
            old.unlink()
            removed.append(old.name)
    return {
        "archive": str(archive),
        "removed_old_snapshots": removed,
        "sha256": _sha256(archive),
        "bytes": archive.stat().st_size,
        "included_files": len(included),
        "excluded_files": len(excluded_files),
        "excluded_directories": sorted(excluded_dirs),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--label", required=True, help="short label, e.g. cdb-r2")
    parser.add_argument("--out-dir", type=Path, default=ROOT, help="destination folder (default: repo root)")
    parser.add_argument("--skip-unchanged", action="store_true", help="build nothing if the tree matches the newest snapshot")
    parser.add_argument("--keep", type=int, default=None, help="keep only the newest N snapshots in --out-dir")
    args = parser.parse_args()
    print(json.dumps(build(args.label, args.out_dir.resolve(), args.skip_unchanged, args.keep), indent=2))


if __name__ == "__main__":
    main()
