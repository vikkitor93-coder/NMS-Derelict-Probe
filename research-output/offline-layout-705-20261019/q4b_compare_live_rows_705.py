#!/usr/bin/env python3
"""Q4b: compare Q4 provider rows with the native A2780 source rows from live run 98a782a5.

Rows are matched by descriptor key (+0x20/+0x28, the same field as GeneratedPieceSourceMetadata.key_pair)
and by rank inside each key group. Writes Q4B_LIVE_ROW_COMPARE_20261020.json next to this file.
"""
from __future__ import annotations
import hashlib, json, struct, sys
from collections import defaultdict, Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
RUN = ROOT / "live-runtime/NMSDerelictSurveyor/layout-cdb-r3/98a782a55ef44aec88142de0ce5e8e6a"
from nms_dungeon_reference_closure_q4_705 import Q4SourceCatalog  # noqa: E402


def native_rows():
    blob = (RUN / "source-rows.bin").read_bytes()
    live = json.loads((HERE / "LIVE_SOURCE_ROWS_98a782a5_20261020.json").read_text(encoding="utf-8"))
    out = []
    for r in live["rows"]:
        i = r["index"]
        raw = blob[i * 0x2B0:(i + 1) * 0x2B0]
        key = int(r["key_lo_0x20"], 16).to_bytes(8, "little") + int(r["key_hi_0x28"], 16).to_bytes(8, "little")
        out.append({"index": i, "key": key, "layer": r["int_0x40"], "raw": raw,
                    "prefix": hashlib.sha256(raw[:0x25E]).hexdigest().upper()})
    return out


def build_mapping(cat, nat):
    meta = cat.source_metadata()
    by_key_nat = defaultdict(list)
    for n in nat:
        by_key_nat[n["key"]].append(n)
    by_key_cat = defaultdict(list)
    for m in meta:
        by_key_cat[m.key_pair].append(m.row_index)
    mapping = {}
    for k, rows in by_key_cat.items():
        nl = by_key_nat.get(k, [])
        if len(nl) == len(rows):
            for ci, n in zip(rows, nl):
                mapping[ci] = n
    return meta, by_key_cat, by_key_nat, mapping


def main():
    cat = Q4SourceCatalog.from_workspace(ROOT)
    nat = native_rows()
    meta, bkc, bkn, mapping = build_mapping(cat, nat)
    same_prefix = 0
    dims_match = 0
    mism = []
    for ci, n in mapping.items():
        p = cat.materialize_scene_map(ci).native_map_prefix
        if hashlib.sha256(p).hexdigest().upper() == n["prefix"]:
            same_prefix += 1
        if p[0x258:0x25E] == n["raw"][0x258:0x25E]:
            dims_match += 1
        elif len(mism) < 15:
            mism.append({"cat_row": ci, "native_row": n["index"], "cat_dims": struct.unpack("<HHH", p[0x258:0x25E]),
                         "native_dims": struct.unpack("<HHH", n["raw"][0x258:0x25E]), "key": n["key"].rstrip(b"\0").decode("latin1")})
    count_mismatch = {k.rstrip(b"\0").decode("latin1"): [len(bkc.get(k, [])), len(bkn.get(k, []))]
                      for k in set(bkc) | set(bkn) if len(bkc.get(k, [])) != len(bkn.get(k, []))}
    order_same = [m.key_pair for m in meta] == [n["key"] for n in nat]
    out = {"q4_rows": len(meta), "native_rows": len(nat), "q4_keys": len(bkc), "native_keys": len(bkn),
           "row_key_sequence_identical": order_same,
           "keys_with_count_mismatch": len(count_mismatch), "count_mismatch_q4_vs_native": dict(sorted(count_mismatch.items())[:40]),
           "rank_matched_rows": len(mapping), "rank_matched_prefix_identical": same_prefix,
           "rank_matched_dims_identical": dims_match, "dims_mismatch_examples": mism,
           "q4_distinct_prefixes": len({hashlib.sha256(cat.materialize_scene_map(m.row_index).native_map_prefix).hexdigest() for m in meta}),
           "native_distinct_prefixes": len({n["prefix"] for n in nat})}
    (HERE / "Q4B_LIVE_ROW_COMPARE_20261020.json").write_text(json.dumps(out, indent=1, default=str) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
