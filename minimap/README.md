# In-game derelict minimap (local only, v0.3.0)

For the local NMS player only. Double-click `tools/Derelict-Minimap-Overlay.cmd` (or `python -I minimap/overlay.py`) and
leave it running. It is one program: no server, no browser, no network. Nothing is fetched from GitHub; the end reward
comes from the local atlas cache file (`end-reward-cache/rewards.csv`) or the local predictor.

**NMS must run in borderless windowed mode.**

## What you see

A click-through window on top of NMS at the right edge, a little below the middle. It appears **by itself** when you are
at the system's derelict (within 200 m) and NMS is the active window, and hides otherwise.
- **Map:** you are the fixed dot in the centre (with a heading arrow); the deck map moves around you, north up. Rooms,
  outlines, doors, ladders, all four container types, entrance. The deck follows your height.
- **Info panel under the map:** container counts for the whole derelict (All) and for your room (salvage crates,
  footlockers, briefcases, tall lockers, same symbols as the map), the **end reward** (hidden until you press its key,
  and hidden again for every new derelict), and the hotkey legend.

## Salvaged Frigate Modules (F5)

A Salvaged Frigate Module (`FRIG_TOKEN`, worth 95,000 units) can only drop from salvage crates and crew footlockers, about
2.5% of them. Which container holds one is determined by the system and the container's place in the layout
(`research-output/CRATE_LOOT_PREDICTION_20261021.md`, `tools/predict_crate_loot_705.py`). The minimap computes it per derelict
in the background and, with F5 on, draws a **gold star** over each such container and counts them in the info panel
(it says "hidden" until you press F5, so there are no spoilers by default; the choice is remembered).
Containers near a rounding boundary can't be called for sure: **pale star** = predicted but a rounding alternative differs
("uncertain"), **hollow star** = only an alternative gives one. Unknown (no POI, e.g. a summoned derelict) is shown as such.
Checked: it agrees with the scanner's published predictions (`crate-loot-cache/predictions-v2.csv`) on every system tested.

## Map styles (F11)

- **Real geometry (default):** the game's own piece meshes (from your installed game, via the mesh cache built by
  `tools/build_piece_meshes_705.py`) seen from above, cut 2.4 m above the floor so ceilings don't hide the rooms, with a
  brightness boost (`--brightness`, default 1.3) and a faint tint per room. Walls use the viewer's wall footprints (clipped to
  the rooms, pillar hollows filled, door openings cut); floor-standing props are drawn as footprint boxes. Doors, ladders,
  containers and the entrance are drawn on top as before. Flat shading: no textures, and props are boxes, not their models.
- **Schematic:** the earlier vector map (room fills, outlines).
- The picture is rendered once per derelict by a background process (about 6 s; the schematic shows meanwhile, with a grey
  "rendering map..." note) into `<analysis>/minimap-cache/geom/` (about 12 MB per derelict, the 30 newest kept).
  `python -I minimap/geomrender.py <glyphs or address> --png` renders one by hand to look at it.
- If a render fails the overlay stays on the schematic and says so (log: `geom/render.log`).

## Hotkeys (global; change with `--key-*`)

| Key | Action |
|---|---|
| F7 / F8 | zoom in / out |
| F9 | show / hide the end reward |
| F10 | show / hide the whole info panel (map only) |
| F5 | show / hide the **Salvaged Frigate Module** marks on the map (remembered; off by default) |
| F11 | map style: the game's real geometry <-> the schematic map |
| F6 | show / hide everything |
| Ctrl+Alt+arrows | move the window (remembered in `minimap/overlay_config.json`) |

Options: `--style real|schematic`, `--brightness`, `--zoom 0-5`, `--y-frac` (top of the window as a fraction of the game height), `--size`, `--opacity`,
`--always-show` (test: ignore the foreground check).

## How it works

- `tools/live_position_705.py`: read-only (`OpenProcess` VM_READ + `ReadProcessMemory`, 5 times a second). Nothing is
  written to, injected into, or paused in NMS. The memory chain is for NMS.exe `13D5060D` only (module docstring); on
  another game build it reads nothing.
- `minimap/core.py`: the live state and per-system preparation (card, layout, reward, world placement). Interior origin =
  the system's `ABAND_FREIGHTER` POI + `RefDungeonEntrance` + D, no rotation
  (`research-output/END_REWARD_PREDICTION_20261020.md` section C); layout = world position - origin. The POI step runs once
  per system (about 8 s) and is cached in `D:/Orca/NMS-Derelict-Probe-analysis/minimap-cache/poi.json`.
- `minimap/overlay.py`: the window, hotkeys and drawing. `minimap/layoutmodel.py`: the shared layout geometry (a port of
  `viewer/static/model.js`). `minimap/geomrender.py`: the real-geometry renderer (below).
- A summoned derelict is not at the system's usual position; the overlay won't show for it (the manual anchor of the old
  browser version is not in the overlay yet).

## After an NMS update

The minimap is tied to one game build (now **NMS 7.05, exe SHA-256 `13D5060D...3499`**). When Steam updates NMS:

1. Double-click `tools/Check-After-NMS-Update.cmd` (about 10 s, read-only; or `python -I minimap/check_update.py`). It checks:
   the installed game file, whether the live reader knows that build, whether the generator's pinned game copy is the
   same build, whether the game's PAK files changed (names + sizes against `minimap/build_baseline.json`), two
   user-verified golden layouts, the golden end reward, and (with NMS running) the live reader.
2. **What happens by itself:** the live reader checks the build before reading any memory. On an unknown build it runs
   the **address finder** (`tools/nms_find_addresses_705.py`, 1.5 s, static scan of the new NMS.exe by the same byte
   signatures NMS.py uses) and uses the application-object address it finds, marked **unverified** (an amber "auto-detected
   addresses (unverified)" line on the map). The offsets inside the game's data block are taken from the last verified
   build, since they have not moved between the builds seen so far. Every reading is checked for plausibility, and the
   data block must be one large allocation. If the finder finds nothing, the reader reads nothing and the overlay shows a
   red "unsupported NMS version" box instead of a wrong map.
   **Verify it once** while in the game: `python -I tools/live_position_705.py --verify-glyphs <12 glyph hex of the system
   you are in>`. On a match the build is recorded as verified in `minimap/learned_builds.json` and the amber note goes.
   Limits: tested only on 7.05, where it reproduces the hand-found values; a patch that changes the code patterns or the
   offsets inside the data block defeats it (the reader then shows an implausible-reading error, not a wrong map).
   `python -I minimap/selftest_autofind_live.py` (NMS running, save loaded) checks the auto path against the known chain.
3. **What stays old until re-verified:** the generator and reward predictor read a *pinned copy* of the 7.05 game file
   (`rea/NMS-13D5060D.exe`) plus extracted game data, not your installed game. After an update they keep producing 7.05
   results. The check reports this as FAIL ("generator uses the installed build"); don't trust or publish new atlas data
   until it is re-verified.
4. To adopt a new build for the generator too, the pinned copy and extracted data must be refreshed and the golden checks
   must pass again. Then run `python -I minimap/check_update.py --save-baseline` to record the new PAK baseline. (The
   live reader does not need this; it only needs step 2.)
5. **Tools for steps 3-4 (2026-10-22):** the scanner stops by itself on a changed game (`tools/update_guard_705.py`).
   `tools/relocate_generator_705.py <new NMS.exe> --extract` finds every hard-coded address in the new exe and
   re-extracts the game data into its own build folder, `tools/compare_builds_705.py --old 7.05 --new <build>` decides
   whether the published atlas is still valid, and `tools/golden_ingame_705.py` re-checks every in-game fact. The
   full runbook (commands in order) is in `research-output/GAME_UPDATE_RESILIENCE_20261022.md`. `check_update.py` now
   also checks the game-table fingerprints (step 8) and runs the golden facts (step 9; `--quick` = the 54 seed checks).

## Moving to another PC

Machine-specific paths for the minimap live in `minimap/settings.json` (created on first run, never overwritten):
`nms_exe` (empty = find it via the running game or Steam), `analysis_dir`, `fastgen_dir`, `emu_python`. The defaults are
siblings of the project folder, so copying the folder set to another drive works without edits except `emu_python`
(a Python with `unicorn` and `pefile`).
Still hard-coded elsewhere (not covered by the settings): the pinned game copy path in the fast generator
(`native_writer_705.py`) and in `tools/emulate_writer_705_assets.py`, the analysis and atlas paths inside other
`tools/*.py`, and the Shipwright folder. The game file itself must come from the user's own NMS install; it is never shipped.

## Tests

`python -I minimap/test_minimap.py`: address helpers, the live entrance sample, the overlay geometry on the validated
fixture `003B06606CAA` (11 rooms, 23 containers on occupied cells, doors = rooms - 1), the build check and the settings.

Verified on the live game on 2026-10-21 by screenshot: placement, the fixed dot with a moving map, F7 zoom, the info panel,
reward reveal and info hide.

## Archive

`minimap/archive-browser/` holds the earlier browser/phone version (HTTP server, web page, launchers). It was dropped on
2026-10-21 (the user only needs the in-game overlay) and is not maintained.
