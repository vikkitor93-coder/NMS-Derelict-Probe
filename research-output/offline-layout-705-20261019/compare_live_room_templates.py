"""Compare the live RoomTemplates rows (CDB r3 capture) with the static table.

Decodes each 0xA0-byte runtime row (Name NMSString0x10 @+0x70, MaxPathLength
@+0x80, MinPathLength @+0x90 per ROOM_WRITER_INPUT_MAPPING_20261019.md) and
checks its order and values against the static GcGeneratedBaseRoomTemplate rows
referenced by the corrected preset export.

Usage: python -I compare_live_room_templates.py <status.json> <presets.json>
"""
from __future__ import annotations

import json
import struct
import sys


def row_bytes(row: str) -> bytes:
    return b"".join(struct.pack("<Q", int(word, 16)) for word in row.split())


def decode(raw: bytes) -> dict[str, object]:
    name = raw[0x70:0x80].split(b"\0", 1)[0].decode("ascii", "replace")
    return {
        "name": name,
        "max_path_raw": struct.unpack_from("<i", raw, 0x80)[0],
        "min_path_raw": struct.unpack_from("<i", raw, 0x90)[0],
    }


def static_rows(presets: dict) -> dict[int, dict]:
    rows: dict[int, dict] = {}
    for preset in presets["presets"]:
        for template in preset.get("resolved", {}).get("room_templates", []):
            rows[int(template["_index"])] = template
    return rows


def main() -> int:
    status = json.load(open(sys.argv[1], encoding="utf-8-sig"))
    presets = json.load(open(sys.argv[2], encoding="utf-8-sig"))
    live = [decode(row_bytes(r)) for r in status["writer_inputs"]["templates_rows_qwords"]]
    known = static_rows(presets)
    order_mismatch = value_mismatch = 0
    for index, row in enumerate(live):
        ref = known.get(index)
        note = ""
        if ref is None:
            note = "(static row not referenced by any preset export)"
        elif ref["Name"] != row["name"]:
            order_mismatch += 1
            note = f"ORDER: static[{index}]={ref['Name']}"
        elif (int(ref["MaxPathLength"]), int(ref["MinPathLength"])) != (row["max_path_raw"], row["min_path_raw"]):
            value_mismatch += 1
            note = f"VALUES: static max/min={ref['MaxPathLength']}/{ref['MinPathLength']}"
        print(f"{index:2d} {row['name']:<18} max={row['max_path_raw']:<3} min={row['min_path_raw']:<3} {note}")
    print(f"live rows={len(live)} static rows known={len(known)} order_mismatches={order_mismatch} value_mismatches={value_mismatch}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
