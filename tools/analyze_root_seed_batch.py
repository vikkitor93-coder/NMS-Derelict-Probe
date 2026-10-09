#!/usr/bin/env python3
"""Correlate every saved derelict-root seed event in capture journals.

The probe's append-only capture journals retain each root-resource event even
though root-event-latest.json is a compatibility pointer to only the newest
event. This tool reports observations grouped by game-process journal and
universe address; it does not claim a seed derivation from correlation alone.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

DUNGEON_ROOT_SCENE = "MODELS/SPACE/POI/DUNGEON.SCENE.MBIN"
DEFAULT_ROOT = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "NMSDerelictSurveyor"


def _normalise_resource(value: Any) -> str:
    return str(value or "").replace("\\", "/").upper()


def _normalise_address(value: Any) -> str | None:
    text = str(value or "").strip().upper().removeprefix("0X")
    if not text:
        return None
    try:
        number = int(text, 16)
    except ValueError:
        return None
    if number <= 0 or number >= 1 << 64:
        return None
    return f"{number:016X}"


def _normalise_seed(value: Any) -> str | None:
    text = str(value or "").strip().upper().removeprefix("0X")
    if not text:
        return None
    try:
        number = int(text, 16)
    except ValueError:
        return None
    if number < 0 or number >= 1 << 64:
        return None
    return f"{number:016X}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _journal_pid(name: str) -> int | None:
    match = re.search(r"-(\d+)\.jsonl$", name, re.IGNORECASE)
    return int(match.group(1)) if match else None


def _root_event_rows(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    malformed = 0
    total_lines = 0
    with path.open("r", encoding="utf-8-sig") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            total_lines += 1
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                malformed += 1
                continue
            if not isinstance(event, dict) or event.get("kind") != "resource_add":
                continue
            if _normalise_resource(event.get("resource_name")) != DUNGEON_ROOT_SCENE:
                continue

            runtime = event.get("runtime_metadata_at_capture")
            runtime = runtime if isinstance(runtime, dict) else {}
            primary = event.get("primary_seed")
            primary = primary if isinstance(primary, dict) else {}
            secondary = event.get("secondary_seed")
            secondary = secondary if isinstance(secondary, dict) else {}
            address = _normalise_address(
                event.get("universe_address_hex_at_capture") or runtime.get("universe_address_hex")
            )
            seed = _normalise_seed(primary.get("seed_hex"))
            trace_sequence = event.get("trace_sequence")
            event_time = str(event.get("utc") or "")
            descriptor = str(event.get("descriptor_pointer_hex") or "").upper() or None
            identity = f"{path.name}\n{line_number}\n{trace_sequence}\n{event_time}\n{descriptor}\n{address}\n{seed}"
            rows.append({
                "event_id": hashlib.sha256(identity.encode("utf-8")).hexdigest(),
                "event_utc": event_time or None,
                "source_journal": path.name,
                "source_line": line_number,
                "trace_sequence": trace_sequence,
                "process_id": _journal_pid(path.name),
                "system_name": runtime.get("system_name"),
                "reality_index": runtime.get("reality_index"),
                "universe_address_hex": address,
                "root_resource": DUNGEON_ROOT_SCENE,
                "root_seed_candidate_hex": seed,
                "use_seed_value": primary.get("use_seed_value") if isinstance(primary.get("use_seed_value"), bool) else None,
                "seed_signed": primary.get("seed_signed"),
                "secondary_seed_hex": _normalise_seed(secondary.get("seed_hex")),
                "descriptor_pointer_hex": descriptor,
                "caller_return_rva_hex": event.get("caller_return_offset_hex"),
                "probe_version": event.get("probe_version"),
                "evidence_status": "captured" if address and seed else "incomplete",
            })
    return rows, {
        "name": path.name,
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "lines": total_lines,
        "malformed_lines": malformed,
        "root_event_count": len(rows),
        "process_id": _journal_pid(path.name),
    }


def _address_group(rows: list[dict[str, Any]]) -> dict[str, Any]:
    seeds = sorted({row["root_seed_candidate_hex"] for row in rows if row.get("root_seed_candidate_hex")})
    return {
        "universe_address_hex": rows[0].get("universe_address_hex"),
        "system_names": sorted({str(row["system_name"]) for row in rows if row.get("system_name")}),
        "observation_count": len(rows),
        "root_seed_candidates_hex": seeds,
        "repeatability": (len(seeds) == 1) if len(rows) > 1 and all(row.get("root_seed_candidate_hex") for row in rows) else None,
        "use_seed_value_states": sorted({row["use_seed_value"] for row in rows if row.get("use_seed_value") is not None}),
        "events": rows,
    }


def build_report(journals: Iterable[Path], *, generated_utc: str | None = None) -> dict[str, Any]:
    files = sorted({Path(path) for path in journals if Path(path).is_file()}, key=lambda p: (p.stat().st_mtime_ns, p.name))
    all_rows: list[dict[str, Any]] = []
    file_records: list[dict[str, Any]] = []
    cohorts: list[dict[str, Any]] = []
    for path in files:
        rows, file_record = _root_event_rows(path)
        file_records.append(file_record)
        if not rows:
            continue
        by_address: dict[str, list[dict[str, Any]]] = defaultdict(list)
        incomplete: list[dict[str, Any]] = []
        for row in rows:
            all_rows.append(row)
            if row.get("universe_address_hex"):
                by_address[row["universe_address_hex"]].append(row)
            else:
                incomplete.append(row)
        groups = [_address_group(group_rows) for _, group_rows in sorted(by_address.items())]
        seed_addresses: dict[str, set[str]] = defaultdict(set)
        for group in groups:
            for seed in group["root_seed_candidates_hex"]:
                seed_addresses[seed].add(group["universe_address_hex"])
        collisions = [
            {"root_seed_candidate_hex": seed, "universe_addresses_hex": sorted(addresses)}
            for seed, addresses in sorted(seed_addresses.items()) if len(addresses) > 1
        ]
        address_count = len(by_address)
        cohorts.append({
            "cohort_id": path.stem,
            "source_journal": path.name,
            "process_id": file_record["process_id"],
            "observation_count": len(rows),
            "distinct_address_count": address_count,
            "ready_for_three_address_comparison": address_count >= 3,
            "address_groups": groups,
            "same_seed_seen_at_multiple_addresses": collisions,
            "incomplete_events": incomplete,
        })

    distinct_addresses = sorted({row["universe_address_hex"] for row in all_rows if row.get("universe_address_hex")})
    ready_cohort_count = sum(1 for cohort in cohorts if cohort["ready_for_three_address_comparison"])
    return {
        "schema_version": 1,
        "report_type": "root-seed-multi-system-correlation",
        "generated_utc": generated_utc or datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "source_policy": "Append-only capture journals are authoritative for multiple root events. Events are grouped by journal/process so separate game launches are never silently merged into one cohort.",
        "analysis_policy": "This reports observed address/seed repetition and collisions only. It does not infer or claim a universe-address-to-root-seed formula.",
        "summary": {
            "source_journal_count": sum(1 for item in file_records if item["root_event_count"]),
            "scanned_journal_count": len(file_records),
            "journal_count_with_root_events": len(cohorts),
            "root_event_observation_count": len(all_rows),
            "distinct_universe_address_count_overall": len(distinct_addresses),
            "distinct_universe_addresses_hex_overall": distinct_addresses,
            "cohorts_ready_for_three_address_comparison": ready_cohort_count,
            "incomplete_root_event_count": sum(1 for row in all_rows if row.get("evidence_status") != "captured"),
            "minimum_distinct_addresses_for_initial_comparison": 3,
            "overall_status": "multi-address-samples-available" if ready_cohort_count else "more-distinct-addresses-needed-in-one-process",
        },
        "source_journals": [item for item in file_records if item["root_event_count"]],
        "process_cohorts": cohorts,
        "all_root_event_observations": all_rows,
        "limitations": [
            "A repeated address is a repeat observation, not a new independent address sample.",
            "Events without both a universe address and root seed remain visible as incomplete evidence.",
            "Probe version is included when the journal records it; the current journal schema may omit it.",
            "Multiple process journals are reported as separate cohorts because the journal does not prove that different launches used the same executable build.",
            "Three or more addresses support an initial correlation check, not proof of a general seed derivation.",
        ],
    }


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    finally:
        try:
            Path(temp_name).unlink(missing_ok=True)
        except OSError:
            pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="Surveyor data root (defaults to LOCALAPPDATA/NMSDerelictSurveyor).")
    parser.add_argument("--journal", type=Path, action="append", help="Analyze a specific capture journal; repeat to include multiple journals as separate cohorts.")
    parser.add_argument("--out", type=Path, help="Report output path; defaults to asset-work-v1/root-seed-batch-latest.json under --root.")
    args = parser.parse_args(argv)
    journal_paths = args.journal if args.journal else sorted(args.root.glob("capture-journal-*.jsonl"))
    output = args.out or (args.root / "asset-work-v1" / "root-seed-batch-latest.json")
    report = build_report(journal_paths)
    write_report(output, report)
    print(f"Root events: {report['summary']['root_event_observation_count']}")
    print(f"Distinct universe addresses: {report['summary']['distinct_universe_address_count_overall']}")
    print(f"Cohorts with root events: {report['summary']['journal_count_with_root_events']}")
    print(f"Status: {report['summary']['overall_status']}")
    print(f"Report: {output}")
    print("NMSDS_STATUS=Root seed batch analysis complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
