#!/usr/bin/env python3
"""Validate and stage agent build requests into a disposable main-build tree."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


SCHEMA_VERSION = 1
LANE_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
REQUEST_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,95}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_FIELDS = {
    "schema_version", "request_id", "lane_id", "status", "base_commit",
    "summary", "files", "tests", "rollback",
}


class BuildRequestError(ValueError):
    """A request is incomplete, unsafe, conflicting, or stale."""


@dataclass(frozen=True)
class FileChange:
    lane_id: str
    request_id: str
    source: Path
    source_rel: str
    target_rel: str
    payload: bytes
    sha256: str
    base_sha256: str | None


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BuildRequestError(f"Cannot read valid UTF-8 JSON at {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise BuildRequestError(f"Request must be a JSON object: {path}")
    return value


def _relative_path(value: Any, label: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value:
        raise BuildRequestError(f"{label} must be a non-empty POSIX relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise BuildRequestError(f"Unsafe {label}: {value!r}")
    if path.parts and ":" in path.parts[0]:
        raise BuildRequestError(f"Unsafe {label}: {value!r}")
    return path


def _safe_file(root: Path, rel: PurePosixPath, label: str) -> Path:
    path = root.joinpath(*rel.parts)
    try:
        resolved_root = root.resolve(strict=True)
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise BuildRequestError(f"Missing {label}: {path}") from exc
    if resolved_root not in resolved.parents or path.is_symlink() or not resolved.is_file():
        raise BuildRequestError(f"Unsafe {label}: {path}")
    # Refuse symlinked parent directories too.
    cursor = root
    for part in rel.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise BuildRequestError(f"Symlinks are not allowed in {label}: {cursor}")
    return path


def _load_requests(requests_root: Path, source_root: Path) -> tuple[list[FileChange], list[dict[str, str]]]:
    if not requests_root.is_dir():
        return [], []
    if requests_root.is_symlink():
        raise BuildRequestError(f"Build request root cannot be a symlink: {requests_root}")
    changes: list[FileChange] = []
    ignored: list[dict[str, str]] = []
    seen_request_ids: set[tuple[str, str]] = set()
    request_files = sorted(requests_root.glob("*/*/request.json"))
    for request_path in request_files:
        if request_path.is_symlink():
            raise BuildRequestError(f"Request manifest cannot be a symlink: {request_path}")
        cursor = request_path.parent
        while cursor != requests_root and cursor != cursor.parent:
            if cursor.is_symlink():
                raise BuildRequestError(f"Request directories cannot be symlinks: {cursor}")
            cursor = cursor.parent
        relative = request_path.relative_to(requests_root)
        if len(relative.parts) != 3:
            raise BuildRequestError(f"Expected <lane>/<request-id>/request.json, got {relative}")
        lane_dir, request_dir = relative.parts[:2]
        data = _json(request_path)
        status = data.get("status")
        request_id = data.get("request_id", request_dir)
        if status in ("draft", "integrated", "cancelled"):
            ignored.append({"lane_id": lane_dir, "request_id": str(request_id), "status": str(status)})
            continue
        if status != "ready":
            raise BuildRequestError(f"Request {request_path} must have status ready, draft, integrated, or cancelled")
        if set(data) != REQUIRED_FIELDS:
            missing = sorted(REQUIRED_FIELDS - set(data))
            extra = sorted(set(data) - REQUIRED_FIELDS)
            raise BuildRequestError(f"{request_path}: missing fields {missing}; unsupported fields {extra}")
        if data["schema_version"] != SCHEMA_VERSION:
            raise BuildRequestError(f"Unsupported request schema in {request_path}")
        lane_id = data["lane_id"]
        if not isinstance(lane_id, str) or not LANE_RE.fullmatch(lane_id) or lane_id != lane_dir:
            raise BuildRequestError(f"lane_id must match request folder {lane_dir!r} in {request_path}")
        if not isinstance(request_id, str) or not REQUEST_RE.fullmatch(request_id) or request_id != request_dir:
            raise BuildRequestError(f"request_id must match request folder {request_dir!r} in {request_path}")
        key = (lane_id, request_id)
        if key in seen_request_ids:
            raise BuildRequestError(f"Duplicate request identity: {lane_id}/{request_id}")
        seen_request_ids.add(key)
        if not isinstance(data["base_commit"], str) or not data["base_commit"].strip():
            raise BuildRequestError(f"{request_path}: base_commit must identify the main commit used")
        if not isinstance(data["summary"], str) or not data["summary"].strip():
            raise BuildRequestError(f"{request_path}: summary is required")
        if not isinstance(data["rollback"], str) or not data["rollback"].strip():
            raise BuildRequestError(f"{request_path}: rollback instructions are required")
        if not isinstance(data["tests"], list) or not data["tests"] or any(not isinstance(t, str) or not t.strip() for t in data["tests"]):
            raise BuildRequestError(f"{request_path}: list the completed tests; use draft until the request is ready")
        if not isinstance(data["files"], list) or not data["files"]:
            raise BuildRequestError(f"{request_path}: ready request must contain at least one file")

        request_root = request_path.parent
        for item in data["files"]:
            if not isinstance(item, dict) or set(item) != {"source", "target", "sha256", "base_sha256"}:
                raise BuildRequestError(f"Each file entry needs source, target, sha256, and base_sha256 in {request_path}")
            src_rel = _relative_path(item["source"], "source path")
            target_rel = _relative_path(item["target"], "target path")
            src = _safe_file(request_root, src_rel, "request payload")
            payload = src.read_bytes()
            digest = hashlib.sha256(payload).hexdigest()
            if not isinstance(item["sha256"], str) or not SHA256_RE.fullmatch(item["sha256"]) or digest != item["sha256"]:
                raise BuildRequestError(f"SHA-256 mismatch for {request_path.parent}/{src_rel}")
            base_hash = item["base_sha256"]
            if base_hash is not None and (not isinstance(base_hash, str) or not SHA256_RE.fullmatch(base_hash)):
                raise BuildRequestError(f"base_sha256 must be null or a lowercase SHA-256 in {request_path}")
            target = source_root.joinpath(*target_rel.parts)
            try:
                target.resolve(strict=False).relative_to(source_root)
            except ValueError as exc:
                raise BuildRequestError(f"Target escapes source root: {target_rel}") from exc
            cursor = source_root
            for part in target_rel.parts[:-1]:
                cursor = cursor / part
                if cursor.is_symlink():
                    raise BuildRequestError(f"Symlinked target directory is not allowed: {cursor}")
            if target.exists() or target.is_symlink():
                if target.is_symlink() or not target.is_file():
                    raise BuildRequestError(f"Target is not a regular file: {target_rel}")
                current_hash = hashlib.sha256(target.read_bytes()).hexdigest()
                if current_hash != digest and (base_hash is None or current_hash != base_hash):
                    raise BuildRequestError(f"Stale target conflict at {target_rel}: current main file changed since request")
            elif base_hash is not None:
                raise BuildRequestError(f"Expected existing target is missing from main: {target_rel}")
            changes.append(FileChange(lane_id, request_id, src, src_rel.as_posix(), target_rel.as_posix(), payload, digest, base_hash))

    by_target: dict[str, FileChange] = {}
    for change in changes:
        previous = by_target.get(change.target_rel)
        if previous:
            raise BuildRequestError(
                f"Multiple build requests target {change.target_rel}; combine or coordinate them: "
                f"{previous.lane_id}/{previous.request_id} vs {change.lane_id}/{change.request_id}"
            )
        by_target[change.target_rel] = change
    return list(by_target.values()), ignored


def stage_requests(source_root: Path, stage_root: Path, requests_root: Path) -> dict[str, Any]:
    source_root = source_root.resolve(strict=True)
    stage_root = stage_root.resolve(strict=True)
    if source_root == stage_root or source_root in stage_root.parents or stage_root in source_root.parents:
        raise BuildRequestError("source-root and stage-root must be separate directories")
    changes, ignored = _load_requests(requests_root, source_root)

    # Validate the staging target before writing any payloads.
    for change in changes:
        rel = PurePosixPath(change.target_rel)
        target = stage_root.joinpath(*rel.parts)
        try:
            target.resolve(strict=False).relative_to(stage_root)
        except ValueError as exc:
            raise BuildRequestError(f"Target escapes stage root: {change.target_rel}") from exc
        cursor = stage_root
        for part in rel.parts[:-1]:
            cursor = cursor / part
            if cursor.is_symlink():
                raise BuildRequestError(f"Symlinked stage directory is not allowed: {cursor}")
        if target.is_symlink():
            raise BuildRequestError(f"Symlinked stage target is not allowed: {target}")
        source_target = source_root.joinpath(*rel.parts)
        if source_target.exists():
            if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != hashlib.sha256(source_target.read_bytes()).hexdigest():
                raise BuildRequestError(f"Staging tree does not match the source checkout at {change.target_rel}")
        elif target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() != change.sha256:
            raise BuildRequestError(f"Staging tree already has a different file at {change.target_rel}")

    applied: list[dict[str, str]] = []
    for change in changes:
        target = stage_root.joinpath(*PurePosixPath(change.target_rel).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix=f".{target.name}.", delete=False) as temp:
            temp.write(change.payload)
            temp_path = Path(temp.name)
        os.replace(temp_path, target)
        applied.append({
            "lane_id": change.lane_id,
            "request_id": change.request_id,
            "target": change.target_rel,
            "sha256": change.sha256,
        })
    return {"schema_version": 1, "applied": applied, "ignored": ignored}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path.cwd(), help="clean main checkout used for base-hash checks")
    parser.add_argument("--stage-root", type=Path, required=True, help="disposable copy of main used for packaging")
    parser.add_argument("--requests-root", type=Path, help="defaults to <source-root>/build-requests")
    parser.add_argument("--receipt", type=Path, required=True, help="write a JSON receipt outside the stage tree")
    args = parser.parse_args(argv)
    requests_root = args.requests_root or args.source_root / "build-requests"
    try:
        receipt = stage_requests(args.source_root, args.stage_root, requests_root)
        receipt_path = args.receipt.resolve()
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    except BuildRequestError as exc:
        print(f"BUILD REQUEST ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"Staged {len(receipt['applied'])} build-request file(s); ignored {len(receipt['ignored'])} non-ready request(s).")
    print(f"Receipt: {receipt_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
