# Shipwright Windows baseline — 2026-10-16

## Exact local inputs

- Shipwright checkout: `C:\Users\Vikman\tools\NMS-Shipwright`, commit `f89691ed037edf437a7406c176aa6b96e654d314` (working tree clean).
- Shipwright license: MIT. No Shipwright source was copied or changed.
- Isolated environment: existing `.venv` under that checkout; Unicorn 2.1.4, pefile 2024.8.26, hgpaktool 1.1.3.
- Cache: `C:\Users\Vikman\AppData\Local\NMS-Shipwright-derelict-test`.
- Local game inputs: `G:\SteamLibrary\steamapps\common\No Man's Sky\Binaries\NMS.exe` SHA-256 `13d5060d4efb9d2a6a6b1b349bc4257231056cc2a055df4bb15d816262cc3499`; `GAMEDATA\PCBANKS\NMSARC.globals.pak` present.
- PE build tuple reported by Shipwright: `[1790874153, 88560712]` (timestamp, executable file size).

## Results

- `nms_procgen.exeaddr.resolve` succeeded. It resolved `gen`, `info`, `planet_sentinels`, and `planet_info`; 30 global entries were found.
- The existing `smoke_systemgen.py` validated universe address `0000750006606CAB` as a system-level address (Euclid, system 117; planet 0) and ran `SystemGen.system` successfully through Unicorn.
- Result: region valid, Korvax, inhabited, 5 planets, 1 moon, 50 generated ship records.
- The run reads the installed executable and archive and emulates the star-system generator. It did not start or attach to NMS and did not alter game files or saves.

## Boundary and follow-up

This confirms Shipwright's address resolver and star-system emulator baseline on this local executable. It does not test any abandoned-freighter, dungeon-room, container-placement, or reward-generation code. The Shipwright checkout contains no such generator in the inspected `systemgen.py`; keep the baseline separate from derelict evidence. The derelict-specific search remains the bounded matching-build Ghidra trace from simple interaction dispatch to generic reward resolution and, independently, the dungeon layout/container path.
