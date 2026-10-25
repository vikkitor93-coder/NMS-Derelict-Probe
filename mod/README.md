# Portable minimap package ("the mod")

`python -I mod/build_package.py [--with-mbincompiler] [--keep-data] [--no-runtime]` builds
`D:/Orca/NMS-Derelict-Minimap-dist/NMS-Derelict-Minimap/`, a folder that runs from anywhere with nothing installed on the PC.
Local only: nothing here uploads or publishes anything. Built 2026-10-23.

## What the user gets

`Install.cmd` -> first-run setup (builds the map data from the user's own game, about 4 min extraction + ~2 min checks, once) ->
asks how to start: with Windows (visible Startup shortcut, self-removing), with the game (Steam launch option, nothing resident),
or by hand. `Uninstall.cmd` / Windows "Installed apps" removes it. `README.txt` is the user-facing text.

## Layout (mirrors the development folders on purpose, so unchanged generator code finds its inputs)

```
.nmsmm-home                      marker; nmshome.py finds the package root from it
python/                          trimmed python.org runtime (tkinter) + unicorn, pefile, hgpaktool, lz4, zstandard
NMS-Derelict-Probe/              minimap/, tools/, research-output/offline-layout-705-20261019/*.py, viewer/static/piece_props.json
NMS-Derelict-Probe-fastgen/      fast_generate_705.py (native_writer_705.py is NOT shipped)
NMS-Derelict-Probe-analysis/     built on the user's PC: rea/ (pinned game copy), emu/, meshcache/, minimap-cache/, ...
NMS-Shipwright/                  nms_procgen + nms_save (MIT; finds the game itself)
game-data/                       raw first-run extraction;  third-party/ MBINCompiler (used by first run only)
```

## How the shipped copies differ from the project files (nothing in the project is edited)

1. Machine paths (`D:/Orca/...`, `C:/Users/<name>/...`, `G:/SteamLibrary/...`) become `nmshome` lookups (`RULES` in build_package.py).
2. `sys.executable` for child processes becomes the package's console `python.exe` (the overlay itself runs under `pythonw.exe`).
3. **Unicorn engine only.** `fast_generate_705.py` normally runs the game's writer natively through `ctypes` in
   `PAGE_EXECUTE_READWRITE` memory (about 2 s). That is the behaviour antivirus heuristics flag, so the package never ships
   `native_writer_705.py` and passes `--engine unicorn` (verified: identical layout, only the timing fields differ; about 25 s per
   new derelict, once, in the background). The builder fails if any shipped file mentions `VirtualAlloc`, `PAGE_EXECUTE`,
   `VirtualProtect`, `CreateRemoteThread`, `WriteProcessMemory` or `NtWriteVirtualMemory`.
4. The full 13-system golden chain (`golden_ingame_705.py`) needs the native engine; in the package `check_update.py` runs the
   54 seed checks, the two golden layouts and the golden end reward through Unicorn instead and reports the rest as SKIP.

## First run (`minimap/first_run.py`, `first_run_driver.py`)

- Refuses to run outside a package (it replaces the generator's input folders; the development tree must never be touched).
- Copies NMS.exe to `analysis/rea/NMS-<sha8>.exe` (the generator reads the pinned copy), then runs
  `tools/extract_build_data_705.py --reproduce-705` through `first_run_driver.py`, which also makes the q4 reference closure
  at the moment the extractor needs it (a fresh PC has no earlier copy). Verified on the development PC: the extraction reproduces
  all 653 files of the validated 7.05 data byte for byte (209 s).
- Installs the results where the generator looks, then runs `check_update.py`. Unsupported game builds stop with a message.
- Map meshes are built on demand per derelict (`geomrender.ensure_meshes`, first time a piece is seen).

## Lifecycle (`minimap/lifecycle.py`)

Install / uninstall / status / steam-line. Autostart = one Startup shortcut (visible) + one "Installed apps" entry (HKCU). Self-removal of
the shortcut: NMS not found on 3 different days spanning >= 7 days, or NMS not run for 30 days; a message box and
`NOTICE-autostart-removed.txt` say so. The overlay exits when `minimap/STOP` exists and keeps one instance per session (mutex).
`--exit-with-game` (Steam launch option) leaves 20 s after the game closes.

## Tested (2026-10-23, this PC)

- Cold package: first run, golden layouts (11/17/6/145 and 9/18/5), golden end reward, 54 seed checks all PASS.
- Cold derelict `0000760004607CAB` in the package: CARGO_MAZE, 7 rooms, 26/13/19/32 containers, Mining Unit C, 5 certain frigate
  modules = same as the development tree. Map render with an empty mesh cache: 6/6 images byte-identical to the development render.
- Windows Defender (real-time protection on, signatures of 2026-10-23): the package ran (runtime, Unicorn engine, overlay reading
  nothing because NMS was closed) without a block, and an explicit custom scan of the whole folder (93 s) reported no detections.
  This is one scanner on one PC, not a guarantee for other products.
- Overlay from the package starts; second instance exits; STOP file ends it; shortcut created (target = package pythonw.exe, hidden
  window) and removed.

## Not done / open

- Antivirus: see the scan result in STATUS.md. Real-world false positives can only be known by uploading to VirusTotal (not done:
  that publishes the files) and by user reports. Code signing is not done.
- MBINCompiler's licence must be confirmed before it is redistributed (the package built with `--with-mbincompiler` is for local tests).
- Not tested on a second PC / another user name / a drive other than D:, and not on GOG or Game Pass installs (Steam only).
- Update path after an NMS patch: the package says "unsupported build"; shipping a new version means re-running the finder and
  the re-extraction (`tools/relocate_generator_705.py`, `extract_build_data_705.py`) and rebuilding.
