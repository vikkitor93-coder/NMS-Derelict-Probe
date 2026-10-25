"""Decode the native A2780 source-map rows captured by the CDB r3 observer.

The observer `.writemem`s the writer global's row array ([RCX+0x28], count at
[RCX+0x24], 0x2B0-byte rows) to source-rows.bin and dumps each row's 0x80-byte
source descriptor (row+0x2A0) into status.json. This decoder reports, per row:
the three u16 map dimensions at +0x258, the SHA-256 of the native prefix
(600 map bytes + dimensions, the bytes the port's catalog materializes), map
occupancy, the descriptor pointer and the descriptor fields A2780 matches on
(+0x20/+0x28 key, +0x40 int).

Usage: python -I decode_live_source_rows.py <run-folder> [--json out.json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

ROW_STRIDE = 0x2B0
MAP_BYTES = 0x258
DIMS_OFFSET = 0x258
PREFIX_BYTES = 0x25E
DESCRIPTOR_POINTER_OFFSET = 0x2A0


def descriptor_fields(qwords: list[int]) -> dict[str, object]:
    raw = b"".join(struct.pack("<Q", q) for q in qwords)
    return {
        "key_lo_0x20": f"{qwords[4]:016X}",
        "key_hi_0x28": f"{qwords[5]:016X}",
        "int_0x40": struct.unpack_from("<i", raw, 0x40)[0],
    }


def descriptors_from_log(text: str) -> list[list[int]]:
    """Descriptor qwords between the SOURCE_ROWS_WRITTEN and SOURCE_DESCRIPTORS_END markers.

    Used when status.json lacks them (for example, a run marked error_review_required
    whose dump completed after the observer's detach deadline).
    """
    lines = text.splitlines()
    try:
        start = next(i for i, l in enumerate(lines) if l.strip() == "SOURCE_ROWS_WRITTEN")
        end = next(i for i, l in enumerate(lines) if i > start and l.strip() == "SOURCE_DESCRIPTORS_END")
    except StopIteration:
        return []
    words: list[int] = []
    for line in lines[start + 1:end]:
        fields = line.split()
        if len(fields) >= 3 and all(all(c in "0123456789abcdefABCDEF`" for c in f) for f in fields[:3]):
            words.extend(int(f.replace("`", ""), 16) for f in fields[1:3])
    return [words[i:i + 16] for i in range(0, len(words) - 15, 16)]


def decode(run: Path) -> dict[str, object]:
    status = json.loads((run / "status.json").read_text(encoding="utf-8-sig"))
    inputs = status.get("writer_inputs") or {}
    blob = (run / "source-rows.bin").read_bytes()
    if len(blob) % ROW_STRIDE:
        raise SystemExit(f"source-rows.bin is {len(blob)} bytes, not a whole number of 0x2B0 rows")
    descriptors = [[int(w, 16) for w in row.split()] for row in inputs.get("source_descriptors_qwords") or []]
    if not descriptors and (run / "cdb.log").exists():
        descriptors = descriptors_from_log((run / "cdb.log").read_text(encoding="utf-8", errors="replace"))
    rows = []
    for index in range(len(blob) // ROW_STRIDE):
        row = blob[index * ROW_STRIDE:(index + 1) * ROW_STRIDE]
        dims = struct.unpack_from("<HHH", row, DIMS_OFFSET)
        record: dict[str, object] = {
            "index": index,
            "dims": list(dims),
            "prefix_sha256": hashlib.sha256(row[:PREFIX_BYTES]).hexdigest().upper(),
            "map_nonzero_bytes": sum(1 for b in row[:MAP_BYTES] if b),
            "descriptor_pointer": f"{struct.unpack_from('<Q', row, DESCRIPTOR_POINTER_OFFSET)[0]:016X}",
        }
        if index < len(descriptors) and len(descriptors[index]) == 16:
            record.update(descriptor_fields(descriptors[index]))
        rows.append(record)
    zero_dim = sum(1 for r in rows if 0 in r["dims"])
    return {
        "run_id": status.get("run_id"),
        "declared_row_count": inputs.get("source_row_count"),
        "decoded_rows": len(rows),
        "descriptors": len(descriptors),
        "zero_dimension_rows": zero_dim,
        "distinct_prefixes": len({r["prefix_sha256"] for r in rows}),
        "distinct_descriptor_keys": len({(r.get("key_lo_0x20"), r.get("key_hi_0x28")) for r in rows}),
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    result = decode(args.run)
    summary = {k: v for k, v in result.items() if k != "rows"}
    print(json.dumps(summary, indent=2))
    for row in result["rows"][:12]:
        print(row)
    if args.json:
        args.json.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
