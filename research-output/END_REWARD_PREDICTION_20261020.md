# Derelict end reward: offline prediction (2026-10-20)

Milestone #19. Exe: NMS.exe 7.05, SHA-256 `13D5060D…3499`. No game launch or attach was used. The live data are the
user's existing captures: surveyor reward journals and sessions, and the end-reward screenshot.

**Result:** the end reward is fully determined by the system address. The predictor
`tools/predict_end_reward_705.py` reproduces the ground truth: `0002250006607CAA` gives **Salvaged Fleet Fuel Unit,
B-class**. It also reproduces 4 captured end seeds and 5 more class records that the user wrote down.

```
python -I tools/predict_end_reward_705.py 0002250006607CAA          # or: --glyphs 122506607CAA ; --json
```

It needs the Shipwright venv for Unicorn (`EMU_PYTHON`, the same default as `generate_derelict_705.py`). It also needs
the fast generator for layouts: cached `derelict.json` files are reused, otherwise it runs
`fast_generate_705.py <addr>` read-only. Each system takes about 1–10 s.

## Mechanism

### A. Which item is chosen (`R_FREI_TECH`, SelectAlways)

1. The end terminal is `ABANFRIGATETERMINALFINAL.ENTITY.MBIN`, InteractionType `AbandonedFreighterEnd`. Its puzzle
   option gives `R_ABAND_END` and `R_FREI_TECH` with one seed (captured: 3 preview calls + 1 real call).
2. `cGcInteractionComponent::GiveReward` `0x140FFAC10` passes the seed stored at component `+0x48` to
   `GiveGenericReward 0x140F140F0`. The prepare code (`0x140FF16EA..0x140FF1704`) sets `+0x48` to
   **`0x140504EB0(world position of the terminal node)`**. That function rounds x, y, z half away from zero to int32,
   then chains a CityHash `Hash128to64` (K = `0x9DDFEA08EB382D69`).
   - The seed is only re-rolled from the player stat `GLOBAL_STATS/REWARD_SEED` (`0x141013C00`) when
     `ReseedAfterRewardSuccess` is set. It is not set for the end terminal.
3. `0x140F19E90` handles `OverrideZeroSeed=false`, so it uses the supplied seed. MWC init: `n = lo + (lo==0)`,
   `u = rotl16(lo) ^ hi ^ lo`. SelectAlways (`0x140F1AB90`, switch case 2) then works like this:
   - draw = `f32(u32(n*0x5A76F899+u) * 2^-32) * 100`;
   - each entry adds `f32(w/total*100)` to a running sum, and the first entry whose sum reaches the draw is picked;
   - the weights are 20/25/15/5 (SHIP_CORE_C/B/A/S) and 7 × 100 (FreighterTech Hyp, Speed, Fuel, Trade, Combat,
     Mine, Exp), 765 in total.

### B. The class of a "Salvaged Fleet … Unit"

1. The procedural-product reward giver is `0x140F248B0`. For categories 13..22 (freighter password, captain's log,
   crew list and the 7 FreighterTech types) it **replaces the seed with `splitmix(pack(current universe address))`**.
   That is the same value as the layout writer seed (`derelict_seed_preset_705.mix_seed`). The global byte
   `0x14524AEBC` must be 0 for this; that is assumed, and the ground truth supports it.
2. `0x140EBF810` is called with quality -1 and mode 8. It takes `number = (u32(first MWC draw) * 100000) >> 32`, and
   the item ID is `"%.9s#%05u"` (for example `UP_FRFUE#68446`).
3. When that item is built (`0x140EC0D5F`, categories 16..22), the class comes from the number:
   - hash: `x = ((n ^ 0x3D0000) >> 16) ^ n; x *= 9; x ^= x >> 4; x *= 0x1B873593; x ^= x >> 15`;
   - start an MWC from `x`;
   - the 4th draw is used, weighted by `GcGameplayGlobals.FreighterTechQualityWeightings` 55/25/15/5, which gives
     C/B/A/S (`0x140EC87B0`).
4. The ship cores `SHIP_CORE_C/B/A/S` are fixed items, so their class is in the name.

### C. Where the terminal is in world space

1. In 7.05 every system has a list of space POIs (`metadata/simulation/solarsystem/spacepoi/spacepoitable.mbin`). It
   includes the item `ABAND_FREIGHTER` (scene `MODELS/SPACE/POI/DUNGEON.SCENE.MBIN`, spawn type NotFarAway).
   - Galaxy info `0x14132D5E0 → 0x14132C660` builds the list from the table at `[app+0x128]`.
   - The system generator `0x14164A4A0` (sub-step `0x14164F655`) writes `cGcSolarSystemData.SpacePoiPositions`
     (`+0x1CE0`).
   - The spawner `0x1416D6D70` places each POI at its position.
   - `tools/space_poi_position_705.py` runs this game code under Unicorn. It reuses Shipwright's SystemGen, loads the
     table, and applies MBIN NMSTemplate fixups `(rel64, hash, 0xEEEEEE01)`.
2. Freighter interior origin = POI + `RefDungeonEntrance` (-100.610405, 145.536758, 31.9607048) + D, with no rotation.
   - D = (-0.0208 ± 0.016, 21.714 ± 0.010, -14.045 ± 0.014) m. It is fitted under the float32 model
     `world = f32(POI + f32(entrance + D + layout))`.
   - Every one of the 89 crates, lockers and cases in 750 (21), 760 (37) and 790 (31) rounds to its seed-recovered
     integer position inside that interval.
3. Terminal = the `R_W_END` instance (writer output) × locator (-0.019725, 1.107091, 8.27731-2.174742).

## Validation

| System | Evidence | Prediction | Result |
|---|---|---|---|
| `0002250006607CAA` (SV Bulk of Kuhas) | screenshot: Salvaged Fleet Fuel Unit, B-class | FreighterTechFuel (seed `F33FB15CB1FA2D0A`), B (#68446) | **item + class match** |
| `0000750006606CAB` (Ruflas-Simly V) | captured end seed `A5326F322EC9F576`; user note class C | seed `A5326F322EC9F576`, Combat, C | match (its crates were used to fit D) |
| `0000760006606CAB` (Irchol-Luhimo XVII) | captured end seed `BA1942727AAA696F`; user note class A | seed `BA1942727AAA696F`, Combat, A | **seed matched blind** (before its crates were used for D); class matches |
| `0000790006606CAB` (Gersid XVI) | captured end seed `14C3C994A9891312`; user note class S | seed `14C3C994A9891312`, Exploration, S | **seed matched blind**; class matches |
| `0001BF0004E84EFD` (Angoto) | user note class B (10-04) | Trade, B | class matches |
| `00001A0004E84EFD` (Nezawac-Eibei) | user notes: B (09-30, probe 0.3.33), S (09-29, probe 0.2.5) | Speed, B | matches 09-30; the 09-29 "S" conflicts (same derelict, so one of the two notes is wrong) |
| `0000320006606CAA` | captured end seed `3B846EF0D74A9C94` | the system POI is ~400 km from the visited freighter | not the natural derelict (see the limits section) |

- The position hash matches every captured reward seed: 34/45 within 6 m of markers in 750 and 49 in 320 (the rest
  in 750 with a wider search), plus fixture, 760 and 790.
- A random class guess matching 6 records has a chance of about 0.25·0.55·0.15·0.05·0.25·0.25 ≈ 6e-5.
- For 225 the class could also have come from the end (position) seed, which would give C. B rules that out, so the
  address-seed replacement is confirmed.
- The "engineering_module_class" fields are the user's own notes in the surveyor sessions. The end-room log says
  "Engineering Unit Salvaged".

## Proven, inferred, and limits

**Proven:**
- the position-hash seed and the code path that uses it;
- the end seed for 4 derelicts (2 of them blind);
- the item pick and class for the one screenshot;
- the class rule against 5 more user notes;
- no player state in the chain: no inventory, stats, missions or time. Repeat visits give the same freighter
  position (750: sessions 10-10 to 10-17).

**Inferred:**
- D is the same for all derelicts. It was fitted on 3 systems, and all presets share entrance (6,3,0).
- The flag at `0x14524AEBC` is 0.
- The other unit names (Hyperdrive/Speed/Trade/Combat/Mining/Exploration ↔ `UP_FRHYP/FRSPE/FRTRA/FRCOM/FRMIN/FREXP`).
  Only Fuel is confirmed in-game.
- The class notes from 09-29 to 10-10 were made on builds that behave like 7.05.

**Limits:**
- Only the system's natural `ABAND_FREIGHTER` POI can be predicted. A derelict reached another way cannot: the one
  visited in `0000320006606CAA` had no POI nearby and used `R_ABAND_END_CV`, which suggests a summoned or other
  spawn.
- Rounding: about 10% of systems are flagged `AMBIGUOUS` when a terminal coordinate is within about 0.015 m of a .5
  boundary. The tool lists the alternatives.
- `R_ABAND_END_CV` (60% freighter base part) is not modelled.

## Test plan for the user (region 06607CAA, all ≤ 0x225, high confidence)

| Glyphs | Address | Preset | Predicted end reward | Rounding margins (m) |
|---|---|---|---|---|
| `003C06607CAA` | `00003C0006607CAA` | MEDI_FLOATERS | **SHIP_CORE_C** (frigate ship core C) | 0.36 / 0.08 / 0.25 |
| `002A06607CAA` | `00002A0006607CAA` | CARGO_BUGS | **Salvaged Fleet Exploration Unit, S-class** | 0.38 / 0.15 / 0.23 |
| `001A06607CAA` | `00001A0006607CAA` | CARGO_FLOATERS | **Salvaged Fleet Fuel Unit, A-class** | 0.44 / 0.44 / 0.38 |

Backups: `002906607CAA` SHIP_CORE_B; `002706607CAA` Exploration A.

If you already finished `002F06607CAA` (blind test #2), it predicts **SHIP_CORE_A**, but its y margin is only
0.03 m.

What to do:
1. Portal to the system.
2. Board the system's own derelict, the one you find in space. Do not summon one.
3. Complete it and use the end terminal.
4. Send a screenshot of the item tooltip (name + class).

A reward capture is optional. Only the older pymhf surveyor probe logged `R_ABAND_END` seeds; CDB r3 does not.

## Files

- `tools/predict_end_reward_705.py`: the predictor. Pure Python, plus a Unicorn subprocess for the POI step.
- `tools/space_poi_position_705.py`: ABAND_FREIGHTER POI position (Shipwright venv).
- `D:/Orca/NMS-Derelict-Probe-analysis/end-reward-cache/spacepoitable.mbin`: the table copy the POI step uses.
- Scratch (brute force, fits, disassembly helpers):
  `D:/Orca/Temp/claude/D--Orca-NMS-Derelict-Probe/3bcdb12b-7aa1-4b9d-a671-cd2211d292d8/scratchpad/agent-reward/`.
  - `posseed_bf.py` / `posseed_path.py`: seed → position.
  - `fitD2.py`: D fit.
  - `pred80b.jsonl`: 80 predictions in region 06607CAA (72 high confidence; picks: 74 tech units, 6 ship cores).
