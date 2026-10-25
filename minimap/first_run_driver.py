"""Runs tools/extract_build_data_705.py with the one extra step it needs on a PC that has no earlier extraction.

    python -I minimap/first_run_driver.py <game folder> <raw output dir>

extract_build_data_705.py's last step (the writer source rows) reads the q4 reference closure
(research-output/offline-layout-705-20261019/q4-reference-closure-20261020), which is produced from the scenes that the
same script extracts one step earlier. The development tree already has it. Here it is made just before it is needed,
by hooking the step from the outside (no other file is edited).
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OFFLINE = ROOT / "research-output" / "offline-layout-705-20261019"
for p in (ROOT / "tools", OFFLINE, ROOT / "research-output" / "offline-generator-assessment-20261019"):
    sys.path.insert(0, str(p))

import build_source_rows_from_assets as BS  # noqa: E402
import extract_build_data_705 as X  # noqa: E402

_orig = BS.build_rows


def build_rows(*a, **k):
    print("[extract] reference closure (scenes referenced by the generated-base scenes)", flush=True)
    try:
        runpy.run_path(str(OFFLINE / "extract_reference_closure_q4_705.py"), run_name="__main__")
    except SystemExit as e:
        if e.code not in (None, 0):
            raise
    return _orig(*a, **k)


BS.build_rows = build_rows

if __name__ == "__main__":
    sys.exit(X.main([sys.argv[1], sys.argv[2], "--reproduce-705"]))
