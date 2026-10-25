# Testing and running the derelict tools

Everything here runs offline on this PC and never starts or attaches to No Man's Sky. Use `python -I` (isolated mode) for all scripts.
Paths below are relative to `D:/Orca/NMS-Derelict-Probe` unless they start with a drive letter.

## 1. Regression test (one command)

Double-click `tools\Run-Regression-Test.cmd`, or:

```
python -I tools/regression_test_705.py          # fast mode, about 1-2 minutes
python -I tools/regression_test_705.py --full   # adds fast generator == slow Unicorn tool (about 1.5 minutes more)
python -I tools/regression_test_705.py --keep   # keep the temp folder for inspection
```

It prints one `PASS` / `FAIL` / `SKIP` line per check and a summary. Exit code 0 means no FAIL. Nothing real is overwritten: layouts,
views and an atlas copy go to a temp folder (`%TEMP%\nms_regression_*`, deleted at the end). The published atlas clone is only read.

Checks:

| Check | What it proves |
|---|---|
| a | The live-validated derelicts regenerate with the fast generator and match: `00003B0006606CAA` CARGO_BUGS 11 rooms / 17 crates / 6 footlockers (145 instances, fixture replay 145/145 and 23/23), `0000750006606CAB` 9/18/5, `0000320006606CAA` CARGO_FLOATERS 9/29/18, blind test `0002250006607CAA` (seed `0A94CF6386B356A4`, 12 rooms, 219 instances, 43+31, full per-room table) and blind test `00002F0006607CAA` (seed `09875D108A52CD96`, 12 rooms, 47+19, room 0 = 18+2). |
| b (`--full`) | The fast generator's `derelict.json` is identical to the main Unicorn tool's on `0000750006606CAB`. |
| c | `tools/derelict_view.py` packing in Python equals `viewer/static/model.js` packing in Node. |
| d | `node tools/build_views.js --check` reports mismatches 0. |
| e | On a temp copy of the atlas regions: `build_atlas_index` and `build_top_bundle` are deterministic (two builds byte-identical), the rebuilt index and top-100 bundle equal the published files, and the top-100 set equals the published index's `map=1` rows. |
| f | If the viewer is running at http://127.0.0.1:8765: `/api/regions`, `/api/derelict/<addr>`, a 404 for an unknown address, `/model.js`. Otherwise SKIP. |
| g | Glyph code <-> address round trips (known codes, 2000 random, every published atlas row; the three implementations agree). |

If e2/e5 fail while the scanner is running, the atlas clone changed between the snapshot and the rebuild; run the test again. A FAIL
anywhere else is a real regression: do not edit the expected values to make it pass.

## 2. Viewer

Double-click `tools\Derelict-Viewer.cmd` (this PC only) or `tools\Derelict-Viewer-LAN.cmd` (local network), or
`python -I viewer/server.py --port 8765`. Open http://127.0.0.1:8765/. Close the window to stop it. See `viewer/README.md`.
The header box accepts 12 hex digits (portal glyph code) or a 16-digit address and generates the derelict.

## 3. Generate a derelict for a glyph code

```
python -I D:/Orca/NMS-Derelict-Probe-fastgen/fast_generate_705.py 122506607CAA --glyphs
python -I D:/Orca/NMS-Derelict-Probe-fastgen/fast_generate_705.py 0002250006607CAA
python -I D:/Orca/NMS-Derelict-Probe-fastgen/fast_generate_705.py 122506607CAA --glyphs --out D:/some/folder/test
```

The glyph code is `P SSS YY ZZZ XXX` (the planet digit is ignored); the address is `000 SSS GG YY ZZZ XXX` with GG the galaxy
(`--galaxy N`, 0 = Euclid). It takes a few seconds. The printed lines show seed, preset, rooms, crates and footlockers, and the
per-room instance counts. The slow reference tool is `tools/generate_derelict_705.py` (same options, minutes per address).

## 4. Where outputs go

| Output | Location |
|---|---|
| Fast generator layouts (default) | `D:/Orca/NMS-Derelict-Probe-analysis/emu/fastgen/generated/<ADDRESS16>/derelict.json` |
| Main (Unicorn) tool layouts | `D:/Orca/NMS-Derelict-Probe-analysis/emu/generated/<ADDRESS16>/` |
| Batch sweeps | `.../emu/fastgen/generated/summary-<region>.csv` |
| Published atlas (separate git clone; the scanner publishes it) | `D:/Orca/NMS-Derelict-Atlas`: `regions/`, `index/systems.csv.gz`, `views/top100.json.gz` |
| Research notes and blind-test plans | `research-output/` (blind tests for the untested presets: `BLIND_TEST_PLAN_PRESETS_20261020.md`) |
| Regression test scratch | `%TEMP%\nms_regression_*` (removed when the test ends) |

## 5. In-game checks (user only)

Follow `research-output/BLIND_TEST_PLAN_PRESETS_20261020.md`: enter the portal glyphs, run `tools\Run-Layout-Capture-0.3.55-cdb-inputs.cmd`
yourself, board the derelict, count crates and footlockers per room, and report. Agents never launch or attach to the game.
