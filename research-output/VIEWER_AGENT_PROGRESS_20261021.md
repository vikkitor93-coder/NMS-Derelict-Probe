# Viewer agent progress, 2026-10-21

All five tasks are implemented and saved. `node --check` passes for app.js, model.js and view3d.js. `derelict_view.py --verify` reports 1454 layouts, 0 different. `regression_test_705.py` reports 20 passed, 0 failed, 1 skipped. `build_piece_props.py --check` reports the file is current.

## Done and verified
1. **Column layout.** Browser profiles were not needed: the user sent the layout. `DEFAULT_COLUMN_LAYOUT` in app.js is that order, with `reward` appended. `dv.columnsVer` (version 2) resets a browser that still has the old default saved, once. Verified over DevTools: default order, migration, header drag and header click-sort (real mouse events). The Columns panel rows now drag by a grip with a drop-line indicator, and the up/down buttons stay. Panel drag verified with real mouse events.
   - Earlier search found no `dv.columns` in the Chrome, Brave or Edge profiles. Chrome had only `dv.filters` and `dv.region`.
2. **Total counts.** The "Total counts:" checkboxes sit in the atlas filters and on the derelict page. Total, sort, min-total filter, stats and the derelict "Total" card use the ticked groups. An unknown ticked group shows "N+" with a tooltip, and sorts after known equal totals. Saved in `dv.filters.totalGroups`. Verified.
3. **3D layers.** One checkbox per layer (`dv.layers3d`). Tall lockers, briefcases and barrels are no longer drawn as fixture blocks (`piece_props.json` key `p`, 88 tagged fixtures, checked against the piece index). New low-poly models with colours sampled from the game textures are in `PAL` in view3d.js, with sources in the README. 2D map colours are updated to match. Verified by zoomed screenshots. No overlap.
4. **Walk inside.** Pointer lock, WASD, Shift, collision, stairwell climb (Space/E up, Q/C down) and Esc work; orbit view works again afterwards. Verified over DevTools with real key events: blocked by wall (moved 0.000), climb up/down, Esc. The help overlay shows. Pointer lock is not available headless, so the drag-to-look fallback is used there. Not tested in a headed browser.
5. **Reward.** Reward column (name and C/B/A/S badge, "≈" for ambiguous, last column), picker (types, classes, only matching, persisted) and the derelict "Predicted end reward" card. Verified with a test atlas copy served via `?atlas=` (copy in the scratchpad `agent-fp/testatlas`). The real atlas has no reward columns yet, so the card shows "–".

## Left / next steps
- Test the first-person look and pointer lock in a normal headed Chrome.
- The `piece_props.json` `p` tags must ship with the public site, and the viewer README note must be carried over.
- When the scanner publishes reward columns, check the real index (the parser is `parseAtlasCsv`).

## Files
Edited: `viewer/static/{app.js,app.css,model.js,view3d.js,piece_props.json}`, `viewer/build_piece_props.py`, `viewer/README.md`. Backups: `<name>.pre-fp` next to each.
Screenshots and test scripts: `D:/Orca/Temp/claude/D--Orca-NMS-Derelict-Probe/3bcdb12b-7aa1-4b9d-a671-cd2211d292d8/scratchpad/agent-fp/`.
# Codex follow-up — 2026-10-21 01:37Z

- The user confirms first-person pointer lock works in a headed browser. The reported usability issue is getting stuck in some narrow spaces. Codex reduced the collision radius from 0.4 to 0.25 game units to increase clearance.
- Walk inside now requests fullscreen for the 3D view and shows an in-view Leave button. If element fullscreen is unsupported or rejected, a fixed full-window fallback is used. Leaving restores the prior body overflow style.
- Coarse-pointer devices receive a virtual movement joystick, a right-side drag-look area, and Up/Down ladder buttons. Keyboard/mouse behavior remains available on desktop.
- `node --check` passed for `app.js`, `view3d.js`, and `model.js` after the changes. The refreshed 25-file public candidate is `D:/Orca/NMS-Derelict-Probe-analysis/public-site-candidate-20261021-v3/site/`; it includes `piece_props.json`, omits official glyph PNGs, and its local HTTP asset checks passed against `?atlas=`.
- Remaining verification: the user already reports pointer lock works; touch-device controls and the particular narrow passage still need an actual browser check. Public-site repo location and deployment remain for the user's later choice.


## Codex follow-up ? low-poly assets and interaction update (2026-10-21)

- Replaced 3D container geometry with the supplied four ultra-low-poly GLBs. Runtime asset folder `viewer/static/models/containers-ultralow/` is 27,172 bytes; `view3d.js` has an inline GLB reader and keeps the original geometry as a load-failure fallback. `node --check` passed; asset structure and local HTTP serving were checked.
- Public candidate v5 is staged at `D:/Orca/NMS-Derelict-Probe-analysis/public-site-candidate-20261021-v5/site/`, including `piece_props.json` and excluding `viewer/static/glyphs/` official game glyph PNGs. Static server `?atlas=` asset checks passed. No deployment or publication occurred. User will choose `docs/` versus separate repo later.
- User confirms Walk inside pointer lock works. Fullscreen and touch joystick/look/ladder controls are implemented. Narrow-space behavior and mobile interaction remain untested by the user.
- Real atlas reward columns are now partially populated (7,706 / 60,190); scanner status already exposes the new reward backfill progress.
