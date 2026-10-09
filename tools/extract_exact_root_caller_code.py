#!/usr/bin/env python3
"""Offline extractor for the runtime-correlated exact derelict root caller.

Reads exact-root-caller-latest.json produced by the live probe, maps the captured
return RVA into the installed NMS.exe, and writes a bounded static code window
around that caller. This is read-only and does not launch NMS.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

try:
    import extract_nms_caller_code as caller
except ModuleNotFoundError:
    import importlib.util
    _spec = importlib.util.spec_from_file_location(
        "extract_nms_caller_code", Path(__file__).with_name("extract_nms_caller_code.py")
    )
    if _spec is None or _spec.loader is None:
        raise
    caller = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(caller)

TOOL_VERSION = "0.3.37"
DEFAULT_BEFORE = 16 * 1024
DEFAULT_AFTER = 4 * 1024


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _hex(value: int) -> str:
    return f"{value:08X}"


def find_evidence(explicit: str | None = None) -> Path:
    if explicit:
        p = Path(explicit).expanduser()
        if p.is_file():
            return p
        raise FileNotFoundError(f"Exact-root evidence not found: {p}")
    local = os.environ.get("LOCALAPPDATA")
    if local:
        p = Path(local) / "NMSDerelictSurveyor" / "asset-work-v1" / "exact-root-caller-latest.json"
        if p.is_file():
            return p
    raise FileNotFoundError(
        "exact-root-caller-latest.json was not found. Capture a known derelict root once, then run Analyze generation + upload."
    )


def _read_section(path: Path, section: dict[str, int | str]) -> bytes:
    with path.open("rb") as fh:
        fh.seek(int(section["raw_offset"]))
        raw = fh.read(int(section["raw_size"]))
    if len(raw) != int(section["raw_size"]):
        raise ValueError("Could not read complete PE section")
    return raw


def _capture(section_raw: bytes, section_rva: int, center_rva: int, before: int, after: int) -> dict[str, Any]:
    idx = center_rva - section_rva
    a = max(0, idx - max(0, before))
    b = min(len(section_raw), idx + max(1, after))
    raw = section_raw[a:b]
    return {
        "start_rva_hex": _hex(section_rva + a),
        "center_return_rva_hex": _hex(center_rva),
        "center_index": idx - a,
        "end_rva_exclusive_hex": _hex(section_rva + b),
        "byte_count": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes_hex": raw.hex().upper(),
    }


def _parse_ff_call_length(raw: bytes, start: int) -> tuple[int, dict[str, Any]] | None:
    """Parse enough x64 encoding to recognize FF /2 CALL instructions.

    Returns (length, details) only when the instruction beginning at ``start`` is
    a near CALL r/m64. This deliberately does not attempt to be a full decoder.
    """
    i = start
    prefixes: list[int] = []
    while i < len(raw):
        b = raw[i]
        if b in (0x66, 0x67, 0xF2, 0xF3, 0x2E, 0x36, 0x3E, 0x26, 0x64, 0x65) or 0x40 <= b <= 0x4F:
            prefixes.append(b)
            i += 1
            if len(prefixes) > 6:
                return None
            continue
        break
    if i >= len(raw) or raw[i] != 0xFF:
        return None
    i += 1
    if i >= len(raw):
        return None
    modrm = raw[i]
    i += 1
    reg = (modrm >> 3) & 7
    mod = (modrm >> 6) & 3
    rm = modrm & 7
    if reg != 2:  # FF /2 = near call
        return None

    sib = None
    disp_size = 0
    rip_relative = False
    if mod != 3 and rm == 4:
        if i >= len(raw):
            return None
        sib = raw[i]
        i += 1
        base = sib & 7
        if mod == 0 and base == 5:
            disp_size = 4
    elif mod == 0 and rm == 5:
        disp_size = 4
        rip_relative = True
    if mod == 1:
        disp_size = 1
    elif mod == 2:
        disp_size = 4
    if i + disp_size > len(raw):
        return None
    disp = None
    if disp_size:
        disp = int.from_bytes(raw[i:i + disp_size], "little", signed=True)
        i += disp_size

    return i - start, {
        "kind": "call-indirect-ff2",
        "prefix_hex": bytes(prefixes).hex().upper(),
        "modrm_hex": f"{modrm:02X}",
        "sib_hex": f"{sib:02X}" if sib is not None else None,
        "displacement": disp,
        "rip_relative": rip_relative,
    }


def decode_call_ending_at(section_raw: bytes, section_rva: int, return_rva: int) -> dict[str, Any]:
    idx = return_rva - section_rva
    if not (0 < idx <= len(section_raw)):
        raise ValueError("Return RVA lies outside its PE section")

    # Direct E8 rel32.
    if idx >= 5 and section_raw[idx - 5] == 0xE8:
        disp = int.from_bytes(section_raw[idx - 4:idx], "little", signed=True)
        call_rva = return_rva - 5
        return {
            "status": "decoded",
            "kind": "call-rel32",
            "instruction_rva_hex": _hex(call_rva),
            "return_rva_hex": _hex(return_rva),
            "instruction_hex": section_raw[idx - 5:idx].hex().upper(),
            "target_rva_hex": _hex((return_rva + disp) & 0xFFFFFFFFFFFFFFFF),
        }

    # Variable-length FF /2 indirect call. Search only plausible x64 max-instruction span.
    candidates: list[dict[str, Any]] = []
    for start in range(max(0, idx - 15), idx):
        parsed = _parse_ff_call_length(section_raw, start)
        if not parsed:
            continue
        length, details = parsed
        if start + length != idx:
            continue
        call_rva = section_rva + start
        item = {
            "status": "decoded",
            **details,
            "instruction_rva_hex": _hex(call_rva),
            "return_rva_hex": _hex(return_rva),
            "instruction_hex": section_raw[start:idx].hex().upper(),
            "target_rva_hex": None,
            "pointer_slot_rva_hex": None,
        }
        if details.get("rip_relative") and details.get("displacement") is not None:
            slot = return_rva + int(details["displacement"])
            item["pointer_slot_rva_hex"] = _hex(slot)
        candidates.append(item)

    if len(candidates) == 1:
        return candidates[0]
    if candidates:
        return {"status": "ambiguous", "return_rva_hex": _hex(return_rva), "candidates": candidates}
    return {
        "status": "not-decoded",
        "return_rva_hex": _hex(return_rva),
        "preceding_15_bytes_hex": section_raw[max(0, idx - 15):idx].hex().upper(),
    }


def find_padding_boundaries(section_raw: bytes, section_rva: int, return_rva: int, search_before: int = 0x8000) -> list[dict[str, Any]]:
    """List nearby compiler-padding candidates without claiming symbol boundaries."""
    idx = return_rva - section_rva
    lo = max(0, idx - search_before)
    out: list[dict[str, Any]] = []
    i = lo
    while i < idx:
        if section_raw[i] not in (0xCC, 0x90):
            i += 1
            continue
        fill = section_raw[i]
        j = i
        while j < idx and section_raw[j] == fill:
            j += 1
        if j - i >= 3 and j < idx:
            out.append({
                "padding_byte_hex": f"{fill:02X}",
                "padding_start_rva_hex": _hex(section_rva + i),
                "padding_byte_count": j - i,
                "next_rva_hex": _hex(section_rva + j),
                "distance_to_return": return_rva - (section_rva + j),
                "next_32_bytes_hex": section_raw[j:min(len(section_raw), j + 32)].hex().upper(),
            })
        i = max(j, i + 1)
    out.sort(key=lambda x: int(x["distance_to_return"]))
    return out[:16]


def extract(evidence_path: Path, exe_path: Path, before: int = DEFAULT_BEFORE, after: int = DEFAULT_AFTER) -> dict[str, Any]:
    evidence = _read_json(evidence_path)
    exact = evidence.get("exact_external_caller") or {}
    raw_return = (
        evidence.get("exact_external_caller_return_offset_hex")
        or exact.get("resolved_external_caller_return_offset_hex")
        or exact.get("external_origin_caller_return_offset_hex")
        or exact.get("caller_return_offset_hex")
    )
    if not raw_return:
        raise ValueError("Exact-root evidence has no external caller return RVA")
    return_rva = int(str(raw_return), 16)

    timestamp, sections = caller.parse_pe_sections(exe_path)
    section = caller.section_for_rva(sections, return_rva)
    section_raw = _read_section(exe_path, section)
    section_rva = int(section["virtual_address"])

    call = decode_call_ending_at(section_raw, section_rva, return_rva)
    window = _capture(section_raw, section_rva, return_rva, before, after)
    boundaries = find_padding_boundaries(section_raw, section_rva, return_rva)

    return {
        "version": 1,
        "tool_version": TOOL_VERSION,
        "source_evidence": evidence_path.name,
        "source_probe_version": evidence.get("probe_version"),
        "method": evidence.get("method"),
        "logical_entry_rva_hex": evidence.get("logical_entry_rva_hex"),
        "root_resource": evidence.get("root_resource"),
        "root_seed_hex": evidence.get("root_seed_hex"),
        "root_descriptor_pointer_hex": evidence.get("root_descriptor_pointer_hex"),
        "exact_external_caller_return_rva_hex": _hex(return_rva),
        "exact_runtime_match": exact,
        "nms_exe": {
            "file_name": exe_path.name,
            "file_size": exe_path.stat().st_size,
            "sha256": caller.sha256_file(exe_path),
            "pe_timestamp_hex": f"{timestamp:08X}",
        },
        "mapped_section": {
            "name": section.get("name"),
            "virtual_address_hex": _hex(section_rva),
            "virtual_size": int(section["virtual_size"]),
            "raw_size": int(section["raw_size"]),
        },
        "call_instruction": call,
        "nearby_padding_boundaries": boundaries,
        "code_window": window,
        "interpretation": (
            "Offline bytes around the exact runtime-correlated derelict caller. "
            "The call decoder only recognizes direct E8 rel32 and x64 FF /2 indirect calls; "
            "padding boundaries are heuristic evidence, not named-symbol claims."
        ),
    }


def default_output() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "NMSDerelictSurveyor" / "asset-work-v1" / "exact-root-caller-code-latest.json"
    return Path.cwd() / "exact-root-caller-code-latest.json"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", help="exact-root-caller-latest.json; defaults to Surveyor asset-work-v1")
    ap.add_argument("--exe", help="NMS.exe; normally auto-detected")
    ap.add_argument("--before", type=int, default=DEFAULT_BEFORE)
    ap.add_argument("--after", type=int, default=DEFAULT_AFTER)
    ap.add_argument("--out", help="output JSON path")
    args = ap.parse_args(argv)

    evidence = find_evidence(args.evidence)
    exe = caller.find_nms_exe(args.exe)
    out = Path(args.out).expanduser() if args.out else default_output()
    out.parent.mkdir(parents=True, exist_ok=True)
    result = extract(evidence, exe, max(512, args.before), max(512, args.after))
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print("NMS Derelict Surveyor v0.3.37 - exact root caller static extraction")
    print(f"Exact return RVA: 0x{result['exact_external_caller_return_rva_hex']}")
    ci = result.get("call_instruction") or {}
    print(f"Call decode:      {ci.get('status')} / {ci.get('kind')}")
    if ci.get("instruction_rva_hex"):
        print(f"Instruction RVA:  0x{ci.get('instruction_rva_hex')}")
    if ci.get("pointer_slot_rva_hex"):
        print(f"Pointer slot RVA: 0x{ci.get('pointer_slot_rva_hex')}")
    print(f"Section:          {result['mapped_section']['name']}")
    print(f"Code bytes:       {result['code_window']['byte_count']}")
    print(f"Created:          {out}")
    print("No NMS run is needed. Upload this result and tell ChatGPT 'check'.")
    caller.open_output_in_explorer(out)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=os.sys.stderr)
        raise SystemExit(2)
