# Derelict container reward path — 2026-10-16

## Target identity and local asset evidence

- Executable: `G:\SteamLibrary\steamapps\common\No Man's Sky\Binaries\NMS.exe`, SHA-256 `13d5060d4efb9d2a6a6b1b349bc4257231056cc2a055df4bb15d816262cc3499`.
- Source archive: local `GAMEDATA\PCBANKS\NMSARC.Precache.pak`, SHA-256 `A6371A8B2F065ECA33FD306A16CBE2BACA9D4CE75806C71E42F74E1AB9295032`.
- Read-only extraction and conversion scratch is under `D:\Orca\Temp\nms-ghidra-targeted-20261016\container-assets`. The local MBINCompiler identifies itself as 7.04.1.3; this is an older compiler build than the 7.05 executable and is recorded as a limitation.
- Actual square salvage asset `models/planets/biomes/common/buildings/parts/buildableparts/spacebase/props/cratem/entities/cratem.entity.mbin` SHA-256 `F15B654EB22FC570A66155CC9E25E01721B0C0B13B36850EC7EB3F496B1FEAE0`.
- Actual footlocker asset `models/planets/biomes/common/buildings/parts/buildableparts/spacebase/props/foot_locker/entities/footlocker.entity.mbin` SHA-256 `28FA635658BCBDC4005B936784EF51B59793461110507FAB619F2FDECDC89AB3`.
- Both entity MXMLs show a `GcSimpleInteractionComponentData` with `SimpleInteractionType=GenericReward`, `Id=R_ABAND_CRATE`, `Repeat=false`, `UsePersonalPersistentBuffer=true`, `ReseedOnRewardSuccess=false`, and an empty `RewardOverrideTable`. This directly supports that both physical container types share the same configured generic reward-table ID in this local asset build. It does not prove they receive identical per-container RNG state or rewards.
- The extracted `metadata/reality/tables/rewardtable.mbin` SHA-256 is `A04483263541824C088D59B6B63C5C36BEDDE0EF1C415EE1D91F346516096059`. Its `R_ABAND_CRATE` entry configures `RewardChoice=TryFirst_ThenSelectAlways` and these entries:
  - `TIMEDUST`, amount 10-30, inner `ChanceToUse=0.33`, entry percentage 0.
  - Recipe from the listed derelict furniture/container recipes, 8%.
  - `AMMO`, amount 100-600, 65%.
  - Four procedural tech rewards, each 3%: `SHIPJUMP_NAME_L`, `ION1_NAME_L`, `SHIPSHIELD_NAME_L`, `SHIPGUN1_NAME_L`. Each specifies quality weights Normal 55, Rare 25, Epic 15, Legendary 5 and requests relevant/quality forcing.
  - Procedural product categories Bones, Loot, BioSample, SeaHorror, each 2%.
  - `FRIG_TOKEN`, one, 5%.
  - `STORM_CRYSTAL`, `FIENDCORE`, `FISHCORE`, and `EYEBALL`, each 10%, amount 1-3.
  - One system-specific TRA product among Alloy, Commodity, Component, Energy, Exotics, Minerals, or Tech, 40%, amount 1-3.
  - `AF_METAL`, amount 10-30, 20%.
- These are literal table fields, not independently verified payout odds. The configured percentages exceed 100% in aggregate and the `RewardChoice` algorithm has not yet been traced, so do not normalize these values or assume mutual exclusivity. `TIMEDUST` also has an inner condition separate from its zero entry percentage.

## Targeted executable trace

- In the hash-matched NMS.exe, RTTI names `cGcSimpleInteractionComponent`; its primary vftable begins at VA `0x144AC4DB8` (TypeDescriptor file offset `0x051ACF98`, mapped RVA `0x051AE988`).
- The targeted `-noanalysis` Ghidra project is `D:\Orca\Temp\nms-ghidra-targeted-20261016\project-generate-dungeon`. Script output for the component methods is in the temporary file `simple_interaction_vtable.txt`; newly traced helpers are in `simple_interaction_helpers.txt`. No game process or installed game files were touched.
- `FUN_141065AD0`, one component method, mixes position-like float fields into state at object offsets `+0x128..+0x134` and initializes several other fields. This is a candidate per-instance deterministic state, but the current trace does not connect it to `R_ABAND_CRATE` reward selection.
- The methods around `FUN_14106F360`, `FUN_14106FDC0`, `FUN_14106F480`, and `FUN_14106F640` handle update/event state, resource handles, timing, and interaction state. They are not yet shown to roll generic rewards. `FUN_141066CB0` maps some interaction enum cases to configured text/options; the inspected paths did not expose the reward-table roller.
- Current static work therefore confirms the shared table ID and possible reward configuration only. It does not yet establish the executable's selection algorithm, per-container seed, number of reward grants, chosen reward, or procedural technology class/rank.

## Next offline target

Trace the actual GenericReward interaction dispatch from `cGcSimpleInteractionComponent` to the generic reward manager/table lookup. Then resolve `TryFirst_ThenSelectAlways`, reward grant count, inventory-choice input, and the seed passed into procedural technology generation. Keep `RewardChoice` percentages as configuration until that code is understood. A clean live crate observation tied to root `2A41B0E7EF42A1F7` at system `0000750006606CAB` would later validate outputs, but it is not needed to continue this static trace.
