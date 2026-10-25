# Derelict end reward: scoping (2026-10-20)

Source table: `D:/Orca/Temp/nms-ghidra-targeted-20261016/container-assets/metadata/reality/tables/rewardtable.MXML` (7.05 container-assets extract).

- `R_ABAND_END` (GiveAll): mission state EndRoomComplete, stat ABAND_FREIGHTER +1, complete space POI. It gives no item.
- `R_FREI_TECH` (SelectAlways, one weighted pick; total weight 765):

  | Item | Weight | Chance |
  | --- | --- | --- |
  | SHIP_CORE_C | 20 | 2.6% |
  | SHIP_CORE_B | 25 | 3.3% |
  | SHIP_CORE_A | 15 | 2.0% |
  | SHIP_CORE_S | 5 | 0.65% |
  | each of 7 procedural FreighterTech{Hyp,Speed,Fuel,Trade,Combat,Mine,Exp} | 100 | 13.1% |

  These are the MXML weights. The native selection and the procedural class roll are not traced yet.
- `R_ABAND_END_CV` (seen on 0000320006606CAA only): 60% chance of a freighter base-part product from a 24-item list (B_COK_*, B_HAB_*, B_WNG_*, B_TRU_*, B_GEN_*, B_TUR_C).
- Captured end seeds (UseSeedValue=true, one per derelict; 3 preview calls + 1 real call, the same seed for END and FREI_TECH):
  - `0000750006606CAB`: `A5326F322EC9F576`
  - `0000320006606CAA`: `3B846EF0D74A9C94`
  - `0000760006606CAB`: `BA1942727AAA696F`

  These seeds are NOT the packed address, the writer seed, the root-seed candidate, or the splitmix of any of those (tested). Their derivation is unknown.
- No outcome (which item was received) was captured. Ground truth would need the user's record or a future capture.

Work needed: (1) derive the end seed from the address (trace the caller of `GiveGenericReward` for R_ABAND_END); (2) reproduce the SelectAlways pick in `0x140F19E90` (RNG uses multiplier 0x5A76F899, as the preset chooser does); (3) for procedural tech, the class C–S / stats roll in the procedural-product generator (it may depend on system wealth or other player state).
