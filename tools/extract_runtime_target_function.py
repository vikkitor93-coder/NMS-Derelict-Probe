"""Append the runtime-correlated logical-entry function body to caller evidence.

This is an offline, read-only extractor.  It uses the exact-root capture's
logical_entry_rva_hex and the installed executable's PE .pdata table to bound
the target body.  The result is added to the existing supported
exact-root-caller-code-latest.json artifact so Upload all saved evidence can
publish it without a new upload contract.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

try:
    from . import analyze_nms_seed_function as analysis
    from . import extract_exact_root_caller_code as caller_code
    from . import extract_nms_caller_code as caller
except ImportError:
    import analyze_nms_seed_function as analysis
    import extract_exact_root_caller_code as caller_code
    import extract_nms_caller_code as caller


TOOL_VERSION = "0.3.39"
MAX_FUNCTION_BYTES = 1_048_576
MAX_DIRECT_CALL_CANDIDATES = 128
MAX_HELPER_FUNCTION_BYTES = 65_536
MAX_HELPER_BYTES_TOTAL = 524_288
MAX_HELPER_FUNCTIONS = 12


def _default_evidence() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "NMSDerelictSurveyor" / "asset-work-v1" / "exact-root-caller-latest.json"
    return Path.cwd() / "exact-root-caller-latest.json"


def _default_output() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "NMSDerelictSurveyor" / "asset-work-v1" / "exact-root-caller-code-latest.json"
    return Path.cwd() / "exact-root-caller-code-latest.json"


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path.name}")
    return value


def extract_direct_call_candidates(
    function_bytes: bytes,
    function_begin_rva: int,
    exe_path: Path,
    sections: list[dict[str, int | str]],
) -> list[dict[str, Any]]:
    """Extract bounded bodies for E8 candidates whose targets map to PE .pdata.

    This is deliberately a byte scan, not a disassembler: instruction boundaries
    are not proven, so every result remains a candidate even when its destination
    falls inside an executable .pdata function.
    """
    out: list[dict[str, Any]] = []
    seen_targets: set[int] = set()
    total_bytes = 0
    for offset in range(max(0, len(function_bytes) - 4)):
        if function_bytes[offset] != 0xE8:
            continue
        call_rva = function_begin_rva + offset
        displacement = int.from_bytes(function_bytes[offset + 1:offset + 5], "little", signed=True)
        target_rva = call_rva + 5 + displacement
        if target_rva < 0 or target_rva > 0xFFFFFFFF:
            continue
        target_section = next((
            section for section in sections
            if int(section["virtual_address"]) <= target_rva <
            int(section["virtual_address"]) + max(int(section["virtual_size"]), int(section["raw_size"]))
        ), None)
        if target_section is None or not (int(target_section.get("characteristics", 0)) & 0x20000000):
            continue
        target_function = analysis.find_runtime_function(exe_path, sections, target_rva)
        if target_function is None:
            continue

        row: dict[str, Any] = {
            "instruction_rva_hex": f"{call_rva:08X}",
            "instruction_bytes_hex": function_bytes[offset:offset + 5].hex().upper(),
            "target_rva_hex": f"{target_rva:08X}",
            "target_runtime_function": target_function,
            "instruction_boundary_verified": False,
            "classification": "heuristic-E8-byte-scan-candidate",
        }
        if target_rva not in seen_targets and len(seen_targets) < MAX_HELPER_FUNCTIONS:
            begin = int(target_function["begin_rva_hex"], 16)
            end = int(target_function["end_rva_exclusive_hex"], 16)
            size = end - begin
            if (
                0 < size <= MAX_HELPER_FUNCTION_BYTES
                and total_bytes + size <= MAX_HELPER_BYTES_TOTAL
            ):
                helper_bytes = analysis._read_rva(exe_path, sections, begin, size)
                if len(helper_bytes) == size:
                    row["target_function_body"] = {
                        "start_rva_hex": f"{begin:08X}",
                        "end_rva_exclusive_hex": f"{end:08X}",
                        "byte_count": size,
                        "sha256": hashlib.sha256(helper_bytes).hexdigest(),
                        "bytes_hex": helper_bytes.hex().upper(),
                    }
                    seen_targets.add(target_rva)
                    total_bytes += size
        out.append(row)
        if len(out) >= MAX_DIRECT_CALL_CANDIDATES:
            break
    return out


def extract_target_function(evidence: dict[str, Any], exe_path: Path) -> dict[str, Any]:
    """Read the .pdata-bounded function containing the observed logical entry."""
    target_raw = evidence.get("logical_entry_rva_hex")
    try:
        target_rva = int(str(target_raw), 16)
    except (TypeError, ValueError) as exc:
        raise ValueError("Exact-root evidence has no valid logical_entry_rva_hex") from exc

    timestamp, image_base, sections = analysis._parse_pe(exe_path)
    runtime_function = analysis.find_runtime_function(exe_path, sections, target_rva)
    if runtime_function is None:
        raise ValueError(f"PE .pdata has no runtime-function entry covering RVA 0x{target_rva:08X}")

    begin = int(runtime_function["begin_rva_hex"], 16)
    end = int(runtime_function["end_rva_exclusive_hex"], 16)
    size = end - begin
    if begin >= end or not begin <= target_rva < end:
        raise ValueError("PE .pdata returned an invalid range for the logical entry")
    if size > MAX_FUNCTION_BYTES:
        raise ValueError(f"Target function is {size} bytes; refusing to export more than {MAX_FUNCTION_BYTES}")

    code = analysis._read_rva(exe_path, sections, begin, size)
    if len(code) != size:
        raise ValueError(f"Could not read complete target function: expected {size} bytes, got {len(code)}")

    direct_calls = extract_direct_call_candidates(code, begin, exe_path, sections)
    return {
        "status": "captured",
        "tool_version": TOOL_VERSION,
        "target_function_rva_hex": f"{target_rva:08X}",
        "target_is_runtime_function_start": target_rva == begin,
        "runtime_function": runtime_function,
        "code_window": {
            "start_rva_hex": f"{begin:08X}",
            "end_rva_exclusive_hex": f"{end:08X}",
            "byte_count": size,
            "sha256": hashlib.sha256(code).hexdigest(),
            "bytes_hex": code.hex().upper(),
        },
        "direct_call_candidates": {
            "scan_method": "raw E8-byte scan; instruction boundaries are unverified",
            "candidate_count": len(direct_calls),
            "candidate_functions_with_bodies": sum("target_function_body" in item for item in direct_calls),
            "items": direct_calls,
        },
        "nms_exe": {
            "file_name": exe_path.name,
            "file_size": exe_path.stat().st_size,
            "sha256": caller.sha256_file(exe_path),
            "pe_timestamp_hex": f"{timestamp:08X}",
            "image_base_hex": f"{image_base:016X}",
        },
        "interpretation": (
            "PE .pdata-bounded bytes for the function reached by the exact-root logical-entry hook. "
            "The RVA is runtime-correlated; this artifact does not assign a source symbol or class name."
        ),
    }


def run(evidence_path: Path, exe_path: Path, output_path: Path) -> dict[str, Any]:
    evidence = _load_json(evidence_path)
    target = extract_target_function(evidence, exe_path)
    result = caller_code.extract(evidence_path, exe_path)
    result["runtime_target_function"] = target
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", help="exact-root-caller-latest.json; defaults to Surveyor asset-work-v1")
    parser.add_argument("--exe", help="NMS.exe; normally auto-detected")
    parser.add_argument("--out", help="output JSON path; defaults to supported exact-root caller code output")
    args = parser.parse_args(argv)

    evidence_path = Path(args.evidence).expanduser() if args.evidence else _default_evidence()
    if not evidence_path.is_file():
        raise FileNotFoundError(f"Exact-root evidence not found: {evidence_path}")
    exe_path = caller.find_nms_exe(args.exe)
    output_path = Path(args.out).expanduser() if args.out else _default_output()
    result = run(evidence_path, exe_path, output_path)

    target = result["runtime_target_function"]
    code = target["code_window"]
    print(f"NMS Derelict Surveyor v{TOOL_VERSION} - runtime target function extraction")
    print(f"Target RVA:       0x{target['target_function_rva_hex']}")
    print(f".pdata range:     0x{code['start_rva_hex']}..0x{code['end_rva_exclusive_hex']}")
    print(f"Function bytes:   {code['byte_count']}")
    print(f"NMS.exe SHA-256:  {target['nms_exe']['sha256']}")
    print(f"Created:          {output_path}")
    print("No NMS launch or derelict traversal is required. Upload all saved evidence to share the result.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
