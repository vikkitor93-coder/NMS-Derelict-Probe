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


TOOL_VERSION = "0.3.38"
MAX_FUNCTION_BYTES = 1_048_576


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
