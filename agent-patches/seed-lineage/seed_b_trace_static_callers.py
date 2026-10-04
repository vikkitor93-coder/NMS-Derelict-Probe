"""Create a small, read-only PE reference report for Seed-B.

Double-click this file on the Windows machine that has NMS installed. It opens a
file picker for NMS.exe and writes a JSON report next to the selected executable.
It does not launch or modify NMS.
"""

from __future__ import annotations

import hashlib
import json
import struct
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox


TARGET_RVAS = (0x00637660, 0x006377E0, 0x00637DB0, 0x006388A0, 0x00227A40)
WINDOW_BEFORE = 160
WINDOW_AFTER = 160
IMAGE_SCN_MEM_EXECUTE = 0x20000000


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def parse_pe(data: bytes) -> dict:
    """Return PE32+ identity and sections; reject malformed/non-PE files."""
    if len(data) < 0x40 or data[:2] != b"MZ":
        raise ValueError("Selected file does not have a DOS/PE header")
    pe_offset = _u32(data, 0x3C)
    if pe_offset + 24 > len(data) or data[pe_offset : pe_offset + 4] != b"PE\0\0":
        raise ValueError("Selected file has no valid PE signature")

    section_count = _u16(data, pe_offset + 6)
    timestamp = _u32(data, pe_offset + 8)
    optional_size = _u16(data, pe_offset + 20)
    optional = pe_offset + 24
    if optional + optional_size > len(data) or _u16(data, optional) != 0x20B:
        raise ValueError("NMS.exe must be a valid 64-bit PE32+ executable")
    image_base = struct.unpack_from("<Q", data, optional + 24)[0]
    section_table = optional + optional_size

    sections = []
    for index in range(section_count):
        entry = section_table + index * 40
        if entry + 40 > len(data):
            raise ValueError("Truncated PE section table")
        name = data[entry : entry + 8].split(b"\0", 1)[0].decode("ascii", "replace")
        virtual_size, virtual_address, raw_size, raw_pointer = struct.unpack_from(
            "<IIII", data, entry + 8
        )
        characteristics = _u32(data, entry + 36)
        if raw_pointer + raw_size > len(data):
            raise ValueError(f"Truncated section data: {name}")
        sections.append(
            {
                "name": name,
                "virtual_address": virtual_address,
                "virtual_size": virtual_size,
                "raw_pointer": raw_pointer,
                "raw_size": raw_size,
                "characteristics": characteristics,
            }
        )
    return {
        "timestamp": timestamp,
        "image_base": image_base,
        "sections": sections,
    }


def scan_references(data: bytes, pe: dict, target_rvas=TARGET_RVAS) -> dict:
    """Find direct E8/E9 rel32 refs in executable sections and VA slots elsewhere."""
    targets = {int(rva): {"direct_xrefs": [], "pointer_slots": []} for rva in target_rvas}
    image_base = pe["image_base"]

    for section in pe["sections"]:
        raw_start = section["raw_pointer"]
        raw_end = raw_start + section["raw_size"]
        va_start = section["virtual_address"]
        chunk = data[raw_start:raw_end]
        if section["characteristics"] & IMAGE_SCN_MEM_EXECUTE:
            for index in range(max(0, len(chunk) - 4)):
                opcode = chunk[index]
                if opcode not in (0xE8, 0xE9):
                    continue
                displacement = struct.unpack_from("<i", chunk, index + 1)[0]
                instruction_rva = va_start + index
                target_rva = instruction_rva + 5 + displacement
                if target_rva not in targets:
                    continue
                win_start = max(0, index - WINDOW_BEFORE)
                win_end = min(len(chunk), index + 5 + WINDOW_AFTER)
                code_window = chunk[win_start:win_end]
                targets[target_rva]["direct_xrefs"].append(
                    {
                        "kind": "call-rel32" if opcode == 0xE8 else "jump-rel32",
                        "instruction_rva_hex": f"{instruction_rva:08X}",
                        "return_or_next_rva_hex": f"{instruction_rva + 5:08X}",
                        "section": section["name"],
                        "window_start_rva_hex": f"{va_start + win_start:08X}",
                        "window_sha256": hashlib.sha256(code_window).hexdigest(),
                        "window_bytes_hex": code_window.hex().upper(),
                    }
                )
        else:
            for target_rva in targets:
                needle = struct.pack("<Q", image_base + target_rva)
                offset = 0
                while True:
                    found = chunk.find(needle, offset)
                    if found < 0:
                        break
                    targets[target_rva]["pointer_slots"].append(
                        {
                            "section": section["name"],
                            "slot_rva_hex": f"{va_start + found:08X}",
                            "target_va_hex": f"{image_base + target_rva:016X}",
                        }
                    )
                    offset = found + 1
    return targets


def build_report(exe_path: Path) -> dict:
    data = exe_path.read_bytes()
    pe = parse_pe(data)
    refs = scan_references(data, pe)
    return {
        "schema_version": 1,
        "tool": "seed-b-trace-static-callers",
        "nms_exe": {
            "file_name": exe_path.name,
            "file_size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "pe_timestamp_hex": f"{pe['timestamp']:08X}",
            "image_base_hex": f"{pe['image_base']:016X}",
        },
        "targets": {f"{target:08X}": result for target, result in refs.items()},
        "interpretation": (
            "Static file scan only. Direct rel32 references and matching absolute VA slots are "
            "reported as byte evidence; they do not by themselves prove runtime dispatch or semantics."
        ),
    }


def main() -> None:
    root = tk.Tk()
    root.withdraw()
    selected = filedialog.askopenfilename(
        title="Select the installed NMS.exe (no game launch required)",
        filetypes=[("No Man's Sky executable", "NMS.exe"), ("Executable files", "*.exe")],
    )
    if not selected:
        root.destroy()
        return
    exe_path = Path(selected)
    try:
        report = build_report(exe_path)
        output_dir = Path.home() / "Downloads"
        if not output_dir.is_dir():
            output_dir = exe_path.parent
        output_path = output_dir / "seed-b-static-callers-00637660.json"
        output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        messagebox.showinfo(
            "Seed-B scan complete",
            f"Saved the read-only report here:\n{output_path}\n\n"
            f"Executable SHA-256: {report['nms_exe']['sha256']}\n"
            "Attach that JSON report in this chat so I can continue tracing.",
        )
    except Exception as exc:
        messagebox.showerror("Seed-B scan failed", f"{exc}\n\n{traceback.format_exc()}")
    finally:
        root.destroy()


if __name__ == "__main__":
    main()
