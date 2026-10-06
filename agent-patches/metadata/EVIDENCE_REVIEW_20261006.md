# METADATA-D evidence review — 2026-10-06

## Scope and source state

This review uses `main` at `d62feb1d1045dc73f92db7759317a82dceecf6c1` and the published METADATA-D 1.0.1 panel. It does not attribute shared evidence uploads to Metadata-D merely because the metadata lane can see them.

## Confirmed

- The 1.0.1 panel requests the host's `research.prepare_assets` and `research.analyze_generation` actions. It does not run a dedicated DungeonOptions scan.
- `research-uploads/20261004T151600Z-metadata-all-saved-evidence-8c3e7065-992084a0/` includes asset calculation and crate target files, but its action is `all-saved-evidence`.
- The newer `research-uploads/20261006T224048Z-all-saved-evidence-8aff7049/` also includes asset calculation, crate target, and dungeon generation table files. Its action is likewise `all-saved-evidence`.
- No folder with a `metadata-prepare-assets` or `prepare-assets` action name appears in the reviewed `main` research-upload directory through the 2026-10-06 22:40:48 UTC upload.
- The saved asset calculation describes crate and footlocker counts for a captured session. It does not contain measured `DungeonOptions`, `DungeonRootScene`, or `Weighting` values.

## Still unverified

- Direct static mapping of the current abandoned-freighter component's `DungeonRootScene` and weighted `DungeonOptions` to dungeon table presets.
- Windows activation of METADATA-D 1.0.1 and visual refresh/rollback behavior.
- Completion of the dedicated metadata Prepare assets action.

## Next evidence request

Run **Prepare assets + upload** once from METADATA-D 1.0.1 in the current Windows Surveyor. Return the action result and new run manifest. No derelict traversal is required. The resulting files must be inspected for component options and weights before claiming a direct map; the action may only produce crate and dungeon-table data.
