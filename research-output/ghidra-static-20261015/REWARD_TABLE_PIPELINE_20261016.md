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

## Executable symbol and interaction-dispatch follow-up — 2026-10-16

- A raw-string scan of the same SHA-256-matched NMS.exe located `TryFirst_ThenSelectAlways` at VA `0x14348FFC0`, `RewardChoice` at `0x143490C78`, and `cGcGenericRewardTableEntry` at `0x14349ECB8`. These are serialized schema/enum labels, not executable function names.
- The executable also contains RTTI lambda names for `cGcRewardManager` methods `GiveRewardCrashSiteRepair`, `GiveRewardPortalState`, `GiveRewardTeleport`, `GiveRewardClosePortal`, and `StripModelBasedOnRarityOfReward`. This confirms the manager handles several specialized rewards, but does not identify its generic reward-table selection routine.
- The targeted Ghidra database is a `-noanalysis` import. The vtable data is readable: base `cGcInteractionComponent` table at `0x144ABDA68`, derived `cGcSimpleInteractionComponent` table at `0x144AC4DB8`. Derived slot 23 points to `FUN_14106F360`; its recovered body updates component/resource state and does not expose a reward roll. The base slot-23 function `FUN_140FE32D0` has a Ghidra body that spills well beyond its `.pdata` interval, so its decompile is not treated as a reliable bounded function result.
- A targeted reference query for the raw label addresses returned no database references. Because this project was imported without analysis, that is an analysis limitation, not evidence that the strings are unused. A direct scan of instruction references or a bounded analysis pass is still needed to connect schema metadata to code.
- No reward-selection behavior, grant count, per-container RNG seed, or module rank is established. The next static target is the reward-manager dispatch path identified from RTTI/lambda callers and bounded executable code references; do not infer odds from table percentages yet.
## RTTI-reference scan — 2026-10-16

- To avoid a whole-program Ghidra analysis, scanned the exact-build `.text` section (54,599,680 raw bytes) for RIP-relative references to the five `cGcRewardManager` lambda TypeDescriptors found in RTTI. The five hits are at instruction ends `0x140F4A537`, `0x140F4A4C7`, `0x140F4A467`, `0x140F4A437`, and `0x140F4A577`.
- Each hit decodes as `48 8D 05 <disp32> C3`: a small accessor loads its matching TypeDescriptor address into RAX and returns. These are RTTI accessor thunks, not `GiveReward...` implementations. The two `GiveReward` node type names had no `.text` RIP-relative hits in this scan.
- This narrows the result: the RTTI spellings identify lambda types but do not provide a useful direct edge to reward execution. No generic reward-table resolver or selection algorithm has been found. Continue through bounded container interaction dispatch and its reward-manager call site; treat selection, count, RNG and module rank as unresolved.## Historical reality-manager lead check — 2026-10-16

- The read-only ReNMS reference checkout (`9696413ec82bd0bd6cea81565ef20122a1c168bb`, GPL-3.0; source not copied) declares `cGcRealityManager::mGenericRewardIDMap` as a map from 128-bit reward IDs to `cGcRewardTableItemList*`. This is an older-build SDK layout hint only; its header supplies no implementation or lookup callsites.
- Checked the exact hash-matched NMS 7.05 executable (SHA-256 `13d5060d4efb9d2a6a6b1b349bc4257231056cc2a055df4bb15d816262cc3499`) for `.?AVcGcRealityManager@@`, NUL-terminated `cGcRealityManager`, and `mGenericRewardIDMap`; none occur. The only `cGcRealityManager` substring is inside the unrelated `cGcRealityManagerData` RTTI name at file offset `0x4AB2D78` (RVA `0x4AB3978`, VA `0x144AB3978`). It is not a manager TypeDescriptor and yields no valid manager-xref target.
- Conclusion: the historical map layout is plausible context but does not identify the 7.05 generic reward resolver. Do not treat the absent RTTI spelling as proof that the runtime manager is absent; code may be stripped or differently represented. Continue from concrete interaction/reward dispatch code and bounded callsites.

## Bounded reward and interaction follow-up - 2026-10-16

Agent A confirmed that derived cGcSimpleInteractionComponent vftable 0x144AC4DB8 slot 23 points to FUN_14106F360 (0x14106F360..0x14106F47F .pdata range). This routine updates interaction/resource state and calls helpers FUN_14106EFE0, FUN_14106F250, FUN_14106F2E0, and FUN_14106F640; it has no observed reward-manager edge. FUN_141066CB0..0x141066E49 handles interaction text/options. This eliminates slot 23 as the reward path, not other activation/dispatch paths.

Agent B's exact-build bounded scan decoded 11,984,502 instructions across 157,445 .pdata functions and found 21 references relevant to reward metadata. Reported instruction sites include 0x142451183 loading the RewardChoice label and 0x142517EDE loading WeightedChanceNormal; the traces through FUN_142620FE0, FUN_1424506F0, and FUN_1424C4190 end in entry/list hashing or registration helpers. They do not establish a loaded-list consumer, selection, grant count, RNG input, or technology rank. The extracted R_ABAND_CRATE configuration remains data evidence only. The enum mapping to value 7 is agent-reported and still needs independent cross-check before interpretation.

Active follow-up: trace the component activation path (A) and loaded reward-list consumers (B). Keep table percentages and the TryFirst_ThenSelectAlways label as configuration until the native consumer is identified.
