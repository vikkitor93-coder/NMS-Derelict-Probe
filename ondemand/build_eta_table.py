#!/usr/bin/env python3
"""Rebuilds the "presets" table in ondemand/eta_config.json from the scanner DB (read-only).
Per preset: median and p90 of writer_seconds, and the median of (total_seconds - writer_seconds) as overhead.
Everything else in eta_config.json (wording, load factors, thresholds) is kept as it is. Run: python -I build_eta_table.py"""
import json, sqlite3, statistics, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB = "D:/Orca/NMS-Derelict-Probe-analysis/emu/fastgen/app-data/derelicts.sqlite"
CFG = HERE / "eta_config.json"


def pct(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(round(p * (len(v) - 1))))]


def main():
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=5)
    rows = {}
    for preset, w, t in db.execute("select preset, writer_seconds, total_seconds from systems where writer_seconds is not null"):
        rows.setdefault(preset, []).append((float(w), float(t or w)))
    table = {}
    for p, v in sorted(rows.items()):
        w = [x[0] for x in v]
        table[p] = {"median_s": round(statistics.median(w), 2), "p90_s": round(pct(w, 0.9), 2),
                    "overhead_s": round(max(0.0, statistics.median([x[1] - x[0] for x in v])), 2), "n": len(v)}
    cfg = json.loads(CFG.read_text(encoding="utf-8")) if CFG.is_file() else {}
    cfg["presets"] = table
    cfg["table_built"] = time.strftime("%Y-%m-%d", time.gmtime())
    CFG.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(table, indent=1))


if __name__ == "__main__":
    main()
