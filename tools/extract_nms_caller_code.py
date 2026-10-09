#!/usr/bin/env python3
"""Extract a larger static NMS.exe code window around the captured dungeon caller.

This is intentionally offline/read-only.  It consumes the latest analyzed
baseline to obtain the Engine::AddResource caller return RVA, maps that RVA into
NMS.exe's PE section table, and writes only a small code window plus build
fingerprints.  It does not launch NMS and does not record usernames, machine
names, network data, or the full executable path in the JSON output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
from pathlib import Path
from typing import Any

DEFAULT_BEFORE = 16 * 1024
DEFAULT_AFTER = 4 * 1024
DUNGEON_ROOT_SCENE = "MODELS/SPACE/POI/DUNGEON.SCENE.MBIN"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def open_output_in_explorer(path: Path) -> bool:
    """Select an output for interactive runs, never from background research."""
    if os.name != "nt" or os.environ.get("NMSDS_NONINTERACTIVE") == "1":
        return False
    try:
        subprocess.Popen(["explorer", f"/select,{path}"])
        return True
    except Exception:
        return False


def _hex_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(str(value), 16)
    except Exception:
        return None


def decode_rel32_call(window: dict[str, Any] | None) -> dict[str, int] | None:
    """Decode E8 rel32 immediately before a pyMHF caller return RVA."""
    if not isinstance(window, dict):
        return None
    try:
        raw = bytes.fromhex(str(window.get("bytes_hex") or ""))
        idx = int(window.get("return_index"))
        ret = int(str(window.get("return_offset_hex") or "0"), 16)
    except Exception:
        return None
    if idx < 5 or idx > len(raw) or raw[idx - 5] != 0xE8:
        return None
    disp = int.from_bytes(raw[idx - 4:idx], "little", signed=True)
    return {
        "return_rva": ret,
        "call_rva": ret - 5,
        "target_rva": (ret + disp) & 0xFFFFFFFFFFFFFFFF,
    }


def find_baseline(explicit: str | None = None) -> Path:
    if explicit:
        p = Path(explicit).expanduser()
        if p.is_file():
            return p
        raise FileNotFoundError(f"Baseline not found: {p}")
    local = os.environ.get("LOCALAPPDATA")
    if local:
        p = Path(local) / "NMSDerelictSurveyor" / "asset-work-v1" / "generation-baseline-latest.json"
        if p.is_file():
            return p
    raise FileNotFoundError(
        "generation-baseline-latest.json was not found. Run Measure-Derelict-Generation.cmd once, "
        "or pass --baseline <path>."
    )


def _steam_roots() -> list[Path]:
    roots: list[Path] = []
    if os.name == "nt":
        try:
            import winreg  # type: ignore

            probes = [
                (winreg.HKEY_CURRENT_USER, r"Software\\Valve\\Steam"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\\WOW6432Node\\Valve\\Steam"),
            ]
            for hive, key_name in probes:
                try:
                    with winreg.OpenKey(hive, key_name) as key:
                        for value_name in ("SteamPath", "InstallPath"):
                            try:
                                raw, _ = winreg.QueryValueEx(key, value_name)
                                if raw:
                                    roots.append(Path(str(raw)))
                            except OSError:
                                pass
                except OSError:
                    pass
        except Exception:
            pass
    for raw in (r"C:\\Program Files (x86)\\Steam", r"C:\\Program Files\\Steam"):
        p = Path(raw)
        if p.exists():
            roots.append(p)
    out: list[Path] = []
    seen: set[str] = set()
    for p in roots:
        key = str(p).lower()
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def _steam_libraries() -> list[Path]:
    libs: list[Path] = []
    for root in _steam_roots():
        if root.exists():
            libs.append(root)
        vdf = root / "steamapps" / "libraryfolders.vdf"
        if not vdf.is_file():
            continue
        try:
            text = vdf.read_text(encoding="utf-8", errors="ignore")
            for m in re.finditer(r'"path"\s+"([^"]+)"', text):
                libs.append(Path(m.group(1).replace(r"\\", "\\")))
        except Exception:
            pass
    out: list[Path] = []
    seen: set[str] = set()
    for p in libs:
        key = str(p).lower()
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def find_nms_exe(explicit: str | None = None) -> Path:
    if explicit:
        p = Path(explicit).expanduser()
        if p.is_file():
            return p
        raise FileNotFoundError(f"NMS.exe not found: {p}")
    env = os.environ.get("NMS_EXE")
    if env and Path(env).is_file():
        return Path(env)
    for lib in _steam_libraries():
        p = lib / "steamapps" / "common" / "No Man's Sky" / "Binaries" / "NMS.exe"
        if p.is_file():
            return p
    for raw in (
        r"C:\\Program Files (x86)\\GOG Galaxy\\Games\\No Man's Sky\\Binaries\\NMS.exe",
        r"C:\\GOG Games\\No Man's Sky\\Binaries\\NMS.exe",
    ):
        p = Path(raw)
        if p.is_file():
            return p
    if os.name == "nt":
        try:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            chosen = filedialog.askopenfilename(
                title="Select No Man's Sky NMS.exe",
                filetypes=[("NMS.exe", "NMS.exe"), ("Executables", "*.exe")],
            )
            root.destroy()
            if chosen and Path(chosen).is_file():
                return Path(chosen)
        except Exception:
            pass
    raise FileNotFoundError("NMS.exe could not be found automatically. Pass --exe <path>.")


def parse_pe_sections(path: Path) -> tuple[int, list[dict[str, int | str]]]:
    """Return PE timestamp and section table fields needed for RVA mapping."""
    with path.open("rb") as f:
        dos = f.read(0x40)
        if len(dos) < 0x40 or dos[:2] != b"MZ":
            raise ValueError("Not a PE executable (missing MZ header)")
        pe_off = struct.unpack_from("<I", dos, 0x3C)[0]
        f.seek(pe_off)
        hdr = f.read(24)
        if len(hdr) != 24 or hdr[:4] != b"PE\0\0":
            raise ValueError("Not a PE executable (missing PE signature)")
        _, section_count, timestamp, _, _, opt_size, _ = struct.unpack("<HHIIIHH", hdr[4:24])
        f.seek(pe_off + 24 + opt_size)
        sections: list[dict[str, int | str]] = []
        for _ in range(section_count):
            sh = f.read(40)
            if len(sh) != 40:
                raise ValueError("Truncated PE section table")
            name = sh[:8].split(b"\0", 1)[0].decode("ascii", errors="replace")
            virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from("<IIII", sh, 8)
            sections.append(
                {
                    "name": name,
                    "virtual_size": virtual_size,
                    "virtual_address": virtual_address,
                    "raw_size": raw_size,
                    "raw_offset": raw_offset,
                }
            )
    return timestamp, sections


def section_for_rva(sections: list[dict[str, int | str]], rva: int) -> dict[str, int | str]:
    for s in sections:
        va = int(s["virtual_address"])
        span = max(int(s["virtual_size"]), int(s["raw_size"]))
        if va <= rva < va + span:
            return s
    raise ValueError(f"RVA 0x{rva:X} does not map to a PE section")


def read_rva_window(path: Path, sections: list[dict[str, int | str]], center_rva: int, before: int, after: int) -> dict[str, Any]:
    s = section_for_rva(sections, center_rva)
    va = int(s["virtual_address"])
    raw_size = int(s["raw_size"])
    raw_offset = int(s["raw_offset"])
    section_raw_end_rva = va + raw_size
    start_rva = max(va, center_rva - max(0, before))
    end_rva = min(section_raw_end_rva, center_rva + max(0, after))
    if end_rva <= start_rva:
        raise ValueError("Requested code window is empty")
    file_offset = raw_offset + (start_rva - va)
    size = end_rva - start_rva
    with path.open("rb") as f:
        f.seek(file_offset)
        raw = f.read(size)
    if len(raw) != size:
        raise ValueError("Could not read the complete code window from NMS.exe")
    return {
        "section_name": s["name"],
        "start_rva_hex": f"{start_rva:08X}",
        "center_call_rva_hex": f"{center_rva:08X}",
        "center_index": center_rva - start_rva,
        "end_rva_exclusive_hex": f"{end_rva:08X}",
        "byte_count": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes_hex": raw.hex().upper(),
    }


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def extract(baseline_path: Path, exe_path: Path, before: int = DEFAULT_BEFORE, after: int = DEFAULT_AFTER) -> dict[str, Any]:
    baseline = _read_json(baseline_path)
    trace = baseline.get("poi_generation_trace") or {}
    roots = trace.get("dungeon_root_resource_events") or []
    root = next((x for x in roots if str(x.get("resource_name") or "").replace("\\", "/").upper() == DUNGEON_ROOT_SCENE), None)
    if not root:
        raise ValueError("The baseline has no captured dungeon-root Engine resource event")
    decoded = decode_rel32_call(root.get("caller_code_window"))
    if decoded is None:
        ret = _hex_int(root.get("caller_return_offset_hex"))
        if ret is None or ret < 5:
            raise ValueError("The baseline has no usable Engine caller return RVA")
        decoded = {"return_rva": ret, "call_rva": ret - 5, "target_rva": 0}

    timestamp, sections = parse_pe_sections(exe_path)
    code = read_rva_window(exe_path, sections, decoded["call_rva"], before, after)

    baseline_window_match = None
    baseline_window = root.get("caller_code_window")
    if isinstance(baseline_window, dict):
        try:
            bw_raw = bytes.fromhex(str(baseline_window.get("bytes_hex") or ""))
            bw_start = int(str(baseline_window.get("start_offset_hex") or "0"), 16)
            bw_section = section_for_rva(sections, bw_start)
            va = int(bw_section["virtual_address"])
            off = int(bw_section["raw_offset"]) + (bw_start - va)
            with exe_path.open("rb") as f:
                f.seek(off)
                disk_raw = f.read(len(bw_raw))
            baseline_window_match = disk_raw == bw_raw
        except Exception:
            baseline_window_match = None

    return {
        "version": 1,
        "tool_version": "0.3.24",
        "source_session_id": baseline.get("session_id"),
        "source_probe_version": baseline.get("probe_version"),
        "universe_address_hex": baseline.get("universe_address_hex"),
        "dungeon_root_seed_hex": root.get("primary_seed_hex"),
        "descriptor_pointer_hex_from_runtime": root.get("descriptor_pointer_hex"),
        "caller_return_rva_hex": f"{decoded['return_rva']:08X}",
        "call_instruction_rva_hex": f"{decoded['call_rva']:08X}",
        "call_target_rva_hex": f"{decoded['target_rva']:08X}" if decoded.get("target_rva") else None,
        "baseline_window_matches_exe": baseline_window_match,
        "nms_exe": {
            "file_name": exe_path.name,
            "file_size": exe_path.stat().st_size,
            "sha256": sha256_file(exe_path),
            "pe_timestamp_hex": f"{timestamp:08X}",
        },
        "code_window": code,
        "interpretation": "offline static code around the runtime-captured Engine::AddResource call site; no game launch required",
    }


def default_output() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "NMSDerelictSurveyor" / "asset-work-v1" / "dungeon-caller-code-latest.json"
    return Path.cwd() / "dungeon-caller-code-latest.json"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", help="generation-baseline-latest.json; defaults to Surveyor asset-work-v1")
    ap.add_argument("--exe", help="NMS.exe; normally auto-detected")
    ap.add_argument("--before", type=int, default=DEFAULT_BEFORE)
    ap.add_argument("--after", type=int, default=DEFAULT_AFTER)
    ap.add_argument("--out", help="output JSON path")
    args = ap.parse_args(argv)
    baseline = find_baseline(args.baseline)
    exe = find_nms_exe(args.exe)
    out = Path(args.out).expanduser() if args.out else default_output()
    out.parent.mkdir(parents=True, exist_ok=True)
    result = extract(baseline, exe, max(256, args.before), max(256, args.after))
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("NMS Derelict Surveyor v0.3.24 - offline dungeon caller extraction")
    print(f"Source session: {result.get('source_session_id')}")
    print(f"Dungeon seed:   {result.get('dungeon_root_seed_hex')}")
    print(f"CALL RVA:       0x{result.get('call_instruction_rva_hex')}")
    print(f"CALL target:    0x{result.get('call_target_rva_hex')}")
    print(f"Code bytes:     {result['code_window']['byte_count']}")
    print(f"Baseline bytes match installed EXE: {result.get('baseline_window_matches_exe')}")
    print(f"\nCreated: {out}")
    print("Send dungeon-caller-code-latest.json back to ChatGPT. No NMS run is needed.")
    open_output_in_explorer(out)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
