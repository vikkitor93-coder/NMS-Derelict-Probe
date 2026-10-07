# METADATA-D Prepare assets repair — 2026-10-07

## Result

The user's 2026-10-06 22:40:48 UTC **Upload all saved evidence** action succeeded. Its asset calculation had the same SHA-256 as the October 4 snapshot, so it did not prove that Prepare assets had completed. Local METADATA-D action records show eleven `research.prepare_assets` attempts from October 1–4, all marked `failed` with an empty upload path. A new button attempt at 2026-10-07 00:04:34 UTC failed at the same point.

The latest Surveyor action log identifies the cause: MBINCompiler v7.4.1.3 encountered both MBIN and MXML files in the persistent extraction directory and could not prompt for an input format in the noninteractive action. The command `& $mbin $extracted` in the installed v0.3.58 `Prepare-Crate-Assets.ps1` returned status 1 before the upload step.

The attached patch changes that call to `& $mbin --input-format=MBIN -y $extracted`. `--input-format=MBIN` resolves the mixed-format prompt; `-y` permits regeneration of previously generated MXML outputs. The patch applies cleanly to the installed v0.3.58 script. No game files or NMS process were changed.

## Verification

- PowerShell parsed the repaired script with zero errors. Its only source difference is the MBINCompiler argument line.
- A copied single dungeon-table MBIN converted with the explicit input format. A copied mixed extraction directory converted 1,441 MBIN/MBIN.PC files with the full fixed invocation and exit status 0.
- The locally installed script was repaired after verifying its original SHA-256 `a1b74934fc5dc7df9c26ebb2ccffd5868aa13a9340a3099d46507333b266f571`; a copy of the original was preserved in the task workspace. The repaired installed script SHA-256 is `8991f9371c231d1dc32b8f904360431321464de63847633f879ac7f3955cf21c`.
- The full offline Prepare assets script then completed: 1,441 files unpacked from 97 PAKs; 1,441 converted; 1,433 dungeon scenes indexed; 75 scenes contain target containers. The saved session `20261006T223811Z_0001BF0004E84EFD` resolved 164/164 scene instances and predicts 30 salvage crates plus 13 crew footlockers, total 43. This is asset-based prediction, not a new physical count.
- Fresh outputs and a SHA-256 manifest are under `research-uploads/20261007T001735Z-metadata-prepare-assets-offline-repair/`. Local root paths were replaced with the relative `asset-work-v1/extracted` before publication; manifest hashes were checked against the published copies.
- The exact published Surveyor v0.3.60 package was reconstructed from the 31 base64 parts in `main`'s `update-manifest.json`. Its size (406,354 bytes) and SHA-256 (`0c67fe274df173c3b604283813f561760e744abed1ffa0d60a2a5ebee5203f7e`) match the manifest. The patch applies cleanly to its `Prepare-Crate-Assets.ps1`, which has the same original SHA-256 as the installed v0.3.58 script. A local source candidate ZIP was built and passed ZIP integrity verification; both source trees contain 154 files and only `Prepare-Crate-Assets.ps1` differs. Candidate SHA-256: `b75b61c9ef7d836d7c1e4999e3d0921c707903a5d6dfb42e4b1779bb4fc1e811`. This candidate was not published as an updater release.

## Static metadata boundary

The current `FREIGHTERDUNGEONSTABLE.MBIN` (SHA-256 `f5afb96f49560bf39a0ec6ffc295540ed4c38165e4458df2c7785fe391e1a82a`) decompiled successfully. It contains ten named presets: MEDI_TURRETS, MEDI_FLOATERS, MEDI_BUGS, MEDI_SLIME, MEDI_MAZE, CARGO_TURRETS, CARGO_FLOATERS, CARGO_BUGS, CARGO_SLIME, CARGO_MAZE. The two MAZE presets specify four rooms; the other eight specify seven. These are table parameters, not observed `DungeonOptions` selection weights.

The prepared files and the initially inspected dungeon scene/entity MXML did not expose `DungeonOptions`, `DungeonRootScene`, or `Weighting`. A subsequent targeted PAK filename search located the active dungeon entrance entity and resolved this static map in `STATIC_DUNGEON_OPTIONS_MAP_20261007.md`. A Windows visual refresh/rollback check for METADATA-D 1.0.1 remains open. The canonical Surveyor updater still needs this script patch; only the installed v0.3.58 copy was repaired and exercised.
