# Derelict Viewer

A local web viewer for generated derelict layouts. Double-click `tools\Derelict-Viewer.cmd` (this PC only) or
`tools\Derelict-Viewer-LAN.cmd` (whole local network: `--host 0.0.0.0`; the window prints the network links; Windows
Firewall must allow inbound TCP 8765, e.g. `New-NetFirewallRule -DisplayName "Derelict Viewer 8765" -Direction Inbound
-Protocol TCP -LocalPort 8765 -RemoteAddress LocalSubnet -Action Allow` in an admin PowerShell), or run
`python -I viewer/server.py [--port 8765] [--no-browser]`. It opens `http://127.0.0.1:8765/`; close the window to stop it.
Only the standard library is needed. The server listens on this PC only (127.0.0.1).

## Pages

- **Region table** (`#/`): every system of a swept region (`summary-<region>.csv` from the fast batch generator).
  Filter by preset, max rooms/floors, no stairs, no hangar, min crates/total, or text; sort by any column. Click a
  row to open that derelict.
- **Derelict** (`#/d/<ADDRESS16>`): glyph code, preset, seed, counts, one top-down map per floor (room bounding
  boxes, exact crate/footlocker positions, stairs, entrance), and a per-room table. Hover or click a room to highlight it.
- **Deck links**: wherever a room has cells at the same position on two decks, that is its stairwell; both ends are
  marked (`↓2` / `↑1`) and joined by a line across the maps. Checked on 835 derelicts: every multi-deck room has one and
  every pair of adjacent decks is linked.
- **3D view**: three.js 0.160.0, vendored in `static/vendor/three/` (MIT; works offline). Rotate/pan/zoom, per-deck toggles,
  deck spacing. Default is a clean view from the decoded cells: light floor tiles and darker walls in the room colour,
  walls 4 units high (the room height in the game meshes; decks are 8 apart), round corner posts, cyan stairwell ramps,
  containers at exact heights. **Game meshes (experimental)** instead draws the game's coarse piece meshes from
  `tools/build_piece_meshes_705.py` (structure only, clustered; shaded floors light / walls darker; **Cut height** clips per deck).
- **Generate box** (header): 12 hex digits = portal glyph code (planet digit ignored), 16 = universe address.
  It runs `D:/Orca/NMS-Derelict-Probe-fastgen/fast_generate_705.py` (a few seconds; FLOATERS/TURRETS can take longer)
  and opens the result. Already generated derelicts open immediately.

## Data source: the GitHub atlas

The region table loads the published atlas directly in each visitor's browser: one listing call (GitHub API, jsDelivr as fallback,
cached for 5 minutes) and then every `regions/g<GG>/<YY>/<ZZZ>/<REGION>.csv` from raw.githubusercontent.com. All regions show in one
table; filter by Region if wanted. The server that hosts the page does no work for this, so the page also runs on any static host
(e.g. GitHub Pages). There, a system's page shows the atlas data (rooms with crates/footlockers); floor maps and 3D need the local
server and generator (Generate box, hidden when no local server is reachable). This PC's own sweeps remain under **Source**.

## Published data (for the public site)

Two files in the atlas repo:
- `index/systems.csv.gz` is every published system in one gzip file (`tools/build_atlas_index.py`). Its `map` column marks the top 100.
- `views/top100.json.gz` holds the full maps of the top 100 systems: piece table plus one view per system (`tools/build_top_bundle.py`, about 115 KB).
  - Ranking: total containers, then crates, then the lower glyph code; the same as the scanner.

`static/model.js` is the one model for drawing a derelict: `pack`, `piecesTable`, `unpack` and `build`. The page always
draws through it, also for derelicts generated on this PC, so published and local maps look the same.
`tools/derelict_view.py` is the byte-identical Python `pack` (`--verify` compares it with the JS one).
`node tools/build_views.js --out <dir> --check [ADDRESS ...]` compares drawings before and after packing.
To test against a local copy of the atlas, open `http://host/?atlas=atlas/`.

## Glyphs and paging

- Portal addresses show as the game's own glyph icons (`static/glyphs/0-f.png`, hover a glyph for its name) or as hex; switch with
  **Glyphs** in the header (remembered per browser). Rebuild the icons from your game files with
  `D:/Orca/venv-texconv/Scripts/python.exe -I tools/build_glyph_icons_705.py` (venv packages: hgpaktool, texture2ddecoder, Pillow).
- The region table shows 100 systems per page; **Per page** goes up to 1000. Filters and sorting apply to all systems before paging.
- Floors per derelict are cached in `D:/Orca/NMS-Derelict-Probe-analysis/viewer-cache/floors.json` and warmed at startup, so
  regions load in under a second.

## Data and map rules

- Data: `D:/Orca/NMS-Derelict-Probe-analysis/emu/fastgen/generated/` first, then the main tool's `emu/generated/`.
- Room record: u16[0..5] = inclusive bounding box `x0 y0 z0 x1 y1 z1` on the 13 x 4 x 13 grid; u16[12..15] = a 64-bit
  mask of the box cells the room occupies, bit index `z + Z*(y + Y*x)` (z fastest). The map draws these exact cells.
- Layout → grid: `u = x/8 + Ex + 0.5`, `v = z/8 + Ez + 0.5`, `level = round(y/8) + Ey`, where `E` is the
  derelict's `entrance_origin`. Checked on 835 generated derelicts: all 22,565 containers lie on an occupied cell of their
  own room, and no cell belongs to two rooms. The other five bit orders fail this test.
- Map orientation: entrance (z = 0) at the bottom and **x mirrored** (+x to the left), matching the in-game
  top-down view (NMS is right-handed with Y up). The user confirmed the unmirrored v1 map was mirrored versus reality,
  and that rooms 0 and 1 of `002F06607CAA` touch without overlapping (bounding boxes overlapped; the cell masks do not).
- Summaries: any `summary-<REGION8>[-label].csv`; `-real` (systems that exist) is preferred by default. The server
  recomputes `floors` from the cell masks (the CSV's piece-based count differed for 14 of 618 real systems).
- Stair and hangar flags come from scene names in the generator output and are not yet checked in-game;
  room and container counts are confirmed in-game on several derelicts.

## Piece meshes (`tools/build_piece_meshes_705.py`)

- Read-only on the game: HGPAKtool extracts scenes (`NMSARC.EntitySceneMBIN.pak`) and geometry (`Mesh*.pak`), the pinned
  MBINCompiler 7.04.1.3 decodes them; cache in `D:/Orca/NMS-Derelict-Probe-analysis/meshcache/` (raw/, pieces/, index.json).
- Geometry: positions are half floats (`PositionVertexLayout`, stride 16), indices u16/u32; each `StreamMetaDataArray`
  entry (IdString = MESH node name) gives absolute offsets in `.geometry.data.mbin.pc`. The scene root's `GEOMETRY`
  attribute names the file; MESH nodes carry `LODLEVEL`; the coarsest LOD per mesh family is used.
- Placement: piece-local points go through the instance's `source_axes`/`translation` (row vectors, the same matrix that
  reproduced the live positions). Check: every container in 3 derelicts (163) has placed floor geometry below it.
- Unverified: Euler order for nested nodes rotated on several axes (assumed Rz*Ry*Rx; 569 such nodes in structure).
- Finding (2026-10-20): in the piece meshes the walkable floor is at the deck base (0) and the ceiling top at +4 over
  the whole room; the coarsest LODs are bounding boxes (they drew as slabs). In-room floor shaping (raised/sunken
  sections the user sees in-game) is not decoded.
- Doors (2026-10-20): a `DOOR_*` piece's translation is its cell centre; `t + 4*A[2]` (4 units along its local +z) is the
  midpoint of the edge between two rooms. Checked on 300 derelicts: every door lands exactly on an inter-room edge and
  doors = rooms - 1 (the rooms form a tree). Kinds: PATH / BRANCH, SLIME-covered variants.
- Stairwells: the shared cell is a hole in the upper deck (railing, open on the entry side) with 10 steps down; the
  direction enters from the room on the upper deck and arrives in the room on the lower deck.
- Fixtures: floor-standing props (worktops, shelving, machinery, barrels, ...) from `build_piece_meshes_705.py`
  (`fixtures` in index.json: prop LOD0 mesh AABBs in piece space; containers, slime and hanging items excluded), drawn
  as dark blocks in 2D and 3D. The user's in-game non-walkable strip in room 0 of 002F06607CAA lines up with the
  `CARG/ROOM_WALL_1_2` + `CARG/CORNER04` wall sets there.
- Hangar rooms get a simple stand-in ship (primitives), not the game's model.
- Walls (2026-10-20): `index.json` "walls" = each piece's footprint of structure at waist height (0.8-3.2 units),
  from LOD1 meshes, rasterised at 0.5 units, merged into rectangles; compact enclosed holes (< 16 sq units and
  <= 4.5 x 4.5, i.e. hollow pillars) filled. The dungeon wrapper scenes (`models/space/poi/dungeon/...`) have their own
  cell-sized 0..4 boxes (helper volumes: they caused the slabs in the mesh view and seams on every cell edge); their own
  geometry is skipped, the visible structure is the base-building parts they reference. The viewer places the rects
  with the instance matrix, cuts 0.5-cell door openings at decoded doors, and draws them as the walls (2D and 3D),
  replacing the cell-edge walls. Checked against the user's red outline of room 0 (002F06607CAA): alcove, two pillars,
  entrance bump, top-right block match. Debug: `tools/debug_wall_rects_705.py <ADDR> <level> <out.png> [rooms]`.
- Piece placement: a piece's geometry is centred one cell ahead of its translation (`t + 8*A[2]`); doors at `t + 4*A[2]`.
- Walls v2 (2026-10-20, user feedback): band lowered to 0.5-2.0 units (archway/door lintels at ~2.5-3 closed corridors),
  raster 0.25 units (bends had no path at 0.5), ladders included with bands per deck offset -1/0/+1 (`ROOM_LADDER`
  rises 12 units from the lower deck; its upper walls were missing), 1-pixel gaps closed. In the viewer (`wallsFrom`)
  walls are finished per deck on a 1/32-cell raster: clipped to room cells + 5 px, compact enclosed holes (< 16 sq
  units, <= 4.5 x 4.5) filled across pieces (mid-room pillars are built from four pieces' corner quarters), door
  openings cleared, merged back into rectangles (~80 ms per derelict). Note: the game's "stairs" are ladders
  (`STAIRS_UP/DOWN` -> `ROOM_LADDER`); the viewer draws a ladder (rails + rungs) against the far side of the shaft.

## Briefcases, tall lockers, enemies and turrets (milestones #20-#22)

- **Extra loot containers** (briefcase, tall locker; `research-output/CONTAINER_TYPES_20261020.md`): extra columns "Briefcases" and
  "Tall lockers" in the atlas table (not part of Total or the top-100 rank; blank in the atlas = not known yet, shown as "–", sorted
  last, left out of the "Min briefcases / Min tall lockers" filters), cards, per-room columns, purple flat / teal tall map markers,
  3D markers, legend and hover text. A layout without `extra_containers` (old layouts) gets them computed in `model.js build()`
  from its placed pieces (float32 like `tools/extra_containers_705.py`); published views use their `"x"` columns.
- **Enemies and turrets** (`research-output/ENEMIES_TURRETS_20261020.md`): `build()` finds floater / fast floater / drone spawners,
  ceiling turrets, hanging / pillar bug sacs and barrels from the placed pieces (same as `tools/derelict_hazards_705.py`). Map
  symbols with legend, an "Enemies & turrets" and a "Barrels" toggle (maps and 3D; plus "Briefcases & tall lockers"), per-room badge
  (`T3 D2 F1 S4`), summary cards (turrets, spawners, sacs, creatures at Normal difficulty: a run-time range, see the card tooltip).
- **`static/piece_props.json`** holds, per scene piece, the piece-local positions of its extra containers and hazards. It is generated
  by `python -I viewer/build_piece_props.py` (`--check` compares); rebuild it when the piece catalog changes. It is fetched next to
  `app.js`, so the public site must publish it with the other static files. Without it, extras fall back to what the layout carries
  and hazards are hidden.
- Verified JS == Python (positions, counts, creature ranges) on 84 layouts; slime and slime doors are not drawn as hazards.

## Total counts, map and 3D layers, walking, reward (agent additions, 2026-10-21)

- **Total counts.** The Total column, its sort and filter, the table stats and the derelict page's total card add up only the groups ticked under
  "Total counts:" (saved in `dv.filters` as `totalGroups`): "Salvaged Frigate Module Crates" (salvage crates + footlockers, default), Briefcases, Tall lockers.
  A ticked group that is unknown for a system shows the total as "N+" (a lower bound; sorts after known totals of the same value). The top-100 map ranking is unchanged.
- **Column layout.** `DEFAULT_COLUMN_LAYOUT` is the user's own order (+ the Reward column at the end). `dv.columnsVer` resets a browser that still has the old default saved, once.
  Rows of the Columns panel drag by their grip (pointer events; mouse and touch); table headers drag as before.
- **Map and 3D layers.** Every layer has a checkbox (`LAYERS` in `view3d.js`, saved as `dv.layers3d`) that controls both the 2D floor maps and 3D view. Loot-container markers are drawn last in the 2D SVG so crates and footlockers stay visible over overlapping map details. Fixture boxes that are really a tall locker, briefcase or explosive barrel
  are tagged in `piece_props.json` (`p`, built by `build_piece_props.py` from the same scene traversal as the piece index, checked against it) and are not drawn as dark blocks.
  Object models are low-poly merged shapes; their colours (`PAL` in `view3d.js`) are the dominant colour clusters of the props' own diffuse textures (hgpaktool + texture2ddecoder,
  materials from the prop scenes): ROVERTRIM.BLUE (crate, footlocker, case, locker body/lid), PANNINGMAT3 (amber), BUTTONANIM (red), INTERIORFREIGHTERTRIM (case, locker), UIMISCPARTS (screen cyan),
  turret BITS4 crate1, slime materials (sacs), FIEND_MAT (bug), EGGSHELL_MAT (egg), DRONE_MAT, explodingbarrel materials. Floater spawner colours have no model source (marker colours). Only the numbers are stored.
- **Container meshes.** The four loot markers now load the supplied six-face ultralow GLBs (crate, footlocker, tall locker, briefcase) from
  `static/models/containers-ultralow/`. Each uses 12 triangles and a shared 3.1 KB atlas; all runtime assets total about 27 KB. Instances share geometry and texture.
- **Walk inside** (first person): opens the 3D view fullscreen; Leave or Esc returns to the page. Pointer lock + mouse look (drag to look when the browser refuses pointer lock), WASD, Shift to run, eye 1.7 m, collision against the wall footprint, solid fixtures and the room cells;
  in a stairwell cell Space/E climbs up, Q/C down. On touchscreens, drag the left joystick to walk, drag the right side to look, and tap Up or Down to climb when at a stairwell. `#view3d.dvView` exposes `firstPerson()` / `placeFirstPerson()` for automated checks.
- **Reward.** Reads `reward_name`, `reward_class`, `reward_ambiguous`, `reward_alt` from `index/systems.csv.gz` when present ("–" and last when empty): Reward column, picker (types, classes, only matching), derelict page card.
