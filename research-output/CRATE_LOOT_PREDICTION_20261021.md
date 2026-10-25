# Derelict crate and footlocker loot: offline prediction (2026-10-21)

Milestone #23. Exe: NMS.exe 7.05, SHA-256 `13D5060D…3499`. Static analysis of the exe plus the reward table
(`metadata/reality/tables/rewardtable.mbin`, SHA-256 `A0448326…6096059`). No game launch or attach was used. Live data
are the user's existing captures and screenshots.

**Result:** a container's loot depends only on the system address and the container's place in the generated layout.
`tools/predict_crate_loot_705.py` reproduces both in-game crates of `0000FE0006607CAA` and the item sequence of a whole
47-crate run, including the exact stack sizes.

```
python -I tools/predict_crate_loot_705.py 0000FE0006607CAA [--room N] [--all] [--json]    # or --glyphs <12 hex>
```

By default it lists salvage crates and crew footlockers. `--all` adds briefcases and tall lockers. It needs the same
environment as `predict_end_reward_705.py`: the Shipwright venv for the POI step, and the fast generator, or a cached
`derelict.json`. Each system takes about 1–4 s.

## Mechanism (proven)

1. **Seed = position hash of the container.** world = f32(POI + f32(RefDungeonEntrance + D + layout_local_xyz)), which
   is the same model and D as the end reward. Each axis is rounded half away from zero, and the seed is
   `0x140504EB0(x, y, z)` (CityHash Hash128to64 chain).
   - Nothing about the save or the player goes in. This is why the user's crate repeated after a quit without saving and
     on another save.
   - `UsePersonalPersistentBuffer` only stores the opened flag.
   - This hash was already matched to captured crate, footlocker and case seeds in 750/760/790/320 (end-reward work).
2. **One pick per container.** All four container tables use `TryFirst_ThenSelectAlways` (case 7 at `0x140F1B15F`):
   - The first entry, the seasonal `TIMEDUST` (season 11), is passed to the item processor first. It fails outside that
     season: 0 of 54 captured crate and locker calls gave it.
   - Then there is one weighted draw. With d1 = the first MWC draw of the seed (`n = lo + (lo==0)`,
     `u = rotl16(lo) ^ hi ^ lo`, `d1 = u32(n*0x5A76F899 + u)`): draw = f32(f32(d1·2⁻³²)·100), walked against the
     cumulative f32(w/total·100).
3. **Amounts and classes reuse the same d1.** The selected entry's handler receives the same `cTkSeed` and starts its own
   MWC from it, so it sees the same first draw:
   - **Amount** (`0x140F200B0` product, `0x140F20290` system product, `0x140F203B0` substance):
     `min + (d1·(max−min+1) >> 32)`. A float multiplier at manager `+0x9C` is applied when it is ≠ 1.0; it was 1 in
     every observation.
   - **Tech module class** (`0x140F20E20`): roll = `d1·(N+R+E+L+1) >> 32`. The class is C if roll ≤ N, B if ≤ N+R, S
     if > N+R+E, otherwise A. The weights are 55/25/15/5.
     - Every ship-tech entry of R_ABAND_CRATE lies at draw 37–43 %, so the roll is about 37–43 and **a crate or
       footlocker tech module is always C-class**. That matches the user's Photon Cannon, C.
     - A second draw then picks the module within that group and class.
   - **System-specific trade good** (`0x140F20290`): index = first MWC draw of `pack(current universe address)`
     (`0x140583A90`, planet index 0) × list length >> 32. So every TRA reward in one system is the same good.
     - Examples: region 06607CAA `0000FE…` → Quantum Accelerator; the 320 run → Fusion Core, which was observed.
   - **Consequences:**
     - A container gives exactly one stack. The amount is tied to where the draw falls inside the band: for example,
       AF_METAL sits at the top of the table, so crate Tainted Metal is always 28–30.
     - Two containers whose positions round to the same metre give identical loot (seen: seq 19/20 of the 320 run,
       same seed, both Fusion Core x3).

## Tables (7.05)

**R_ABAND_CRATE** (salvage crate *and* crew footlocker; total weight 198). Chance = weight/198.

| Entry | Weight | Chance | Amount (in the band) |
|---|---:|---:|---|
| TIMEDUST (season 11 only, tried first) | 0 | – | – |
| Derelict furniture recipe (TryUnknownRandom) | 8 | 4.04 % | blueprint; if all known: nanites (seen) |
| Projectile Ammunition | 65 | 32.83 % | 120–284 |
| Pulse Engine / Hyperdrive / Deflector Shield / Photon Cannon module | 3 each | 1.52 % each | x1, **always C** |
| Procedural Bones / Loot / BioSample / SeaHorror | 2 each | 1.01 % each | x1, name procedural |
| **Salvaged Frigate Module (FRIG_TOKEN)** | 5 | **2.525 %** | x1 |
| Storm Crystal | 10 | 5.05 % | 2 |
| Larval Core | 10 | 5.05 % | 2 |
| Hadal Core | 10 | 5.05 % | 2 |
| Hypnotic Eye | 10 | 5.05 % | 2–3 |
| System tier-5 trade good (TRA_*5) | 40 | 20.20 % | 3 |
| Tainted Metal | 20 | 10.10 % | 28–30 |

- In the 549 systems 06607CAA ≤ 0x225, the predictor puts FRIG_TOKEN in 358 of 14,891 crates and footlockers
  (2.40 %), ammo at 32.7 %, TRA at 20.3 % and so on, in line with the weights. 56 of those derelicts have an
  unambiguous FRIG_TOKEN container.
- **R_ABAND_LOCK** (tall locker, total 240): Unstable Plasma 10; 10 weapon/suit tech entries at 1 each (Thermal
  Protection is always B, the rest always C); ammo 20; Units 5–10k 20; Nanites 20–50 20; NipNip 10; six curios at 10
  each (Vy'keen Effigy/Dagger, Korvax Casing, Convergence Cube, Gek Relic, GekNip); tier-1 trade good 70; Tainted Metal
  10–25 20.
- **R_ABAND_CASE** (briefcase, total 141): Document 1; Units 20–100k 10; Nanites 20–50 40; Units 5–10k 40; Nanites
  50–200 10; Tainted Metal 40.

## Validation

| Evidence | Prediction | Result |
|---|---|---|
| `0000FE0006607CAA` room 2 salvage crate (only crate in the room), Photon Cannon Module x1 C, same after a reload and on another save | seed `CBF9457ED4E527F9` → SHIPGUN1, C | **match**. Only 1 of the 26 neighbouring integer positions gives SHIPGUN1. |
| `0000FE0006607CAA` room 3 salvage crate, Larval Core, same after a reload | seed `7BC7BB07C4D8C222` → FIENDCORE x2 | **item match**. The screenshots show "x1", but the toast counts up (the video shows Larval Core x1→2), so the final count is still to be confirmed. |
| Run `0000320006606CAA` (video `D:\Untitled1.mp4`, 47 captured R_ABAND_CRATE seeds in order) | pick + amount per seed | the whole popup sequence matches in order (table below) |
| Same run, 5 captured R_ABAND_LOCK seeds | Vy'keen Effigy; Convergence Cube; Spark Canister x2; Tainted Metal x24; Ammo x183 | all 5 match (video rows 26, 27, 30, 47, 48) |

320 run, captured seed order → predicted → video popup (`UNTITLED1_LOOT_ATTRIBUTION_REVIEW.md` rows). Final toast
counts:
- 1 Hadal Core 2 → Hadal Core x1→2.
- 2 Pulse Engine → Pulse Engine Module.
- 3 Tainted Metal 30 → →30.
- 4+5 Ammo 209+128 → Ammo x6→**337**.
- 6 SeaHorror → Twisted Gelsack (user-confirmed first square crate).
- 7 Tainted 28 → →28.
- 8 recipe → Nanites.
- 9 Ammo 257 → 257.
- 10 Hyperdrive → Hyperdrive Module.
- 11 Eye 3 → 3.
- 12 TRA 3 → Fusion Core →3.
- 13 Larval 2 → 2.
- 14 Eye 3 → 3.
- 15 Storm 2 → 2.
- 16 Ammo 186 → 186.
- 17 Tainted 29 → 29.
- 18 Ammo 194 → 194.
- 19+20 TRA 3+3 → Fusion Core x1→**6**.
- 21 TRA 3 → 3.
- 22 Ammo 168 → 168.
- 23 TRA 3 → Fusion Core 3.
- 24 TRA (not in the sampled video).
- 25, 26 recipe → Nanites, Nanites.
- 27 Larval 2 → 2.
- 28 Ammo 199 → 199.
- 29 Larval 2 → 2.
- 30 Tainted 29 → 29.
- 31 Storm 2 → 2.
- 32 TRA 3 → 3.
- 33 Tainted 30 → 30.
- 34 Ammo 133 → 133.
- 35 Eye 2 → 2.
- 36 Ammo 262 → 262.
- 37 Photon Cannon → Photon Cannon Module.
- 38 BioSample → Oily Worms.
- 39 Ammo 200 → 200.
- 40 TRA 3 → 3.
- 41 Storm 2 → 2.
- 42 Tainted 30 → 30.
- 43 Ammo 124 → 124.
- 44–47 Ammo 279, 154, 224, 167 → only Ammo x23→**391** = 224+167 was sampled.

Every popup the video shows is explained, including the exact ammo stacks and the two combined toasts. The video's
"Footlocker/Square" labels are not needed: both use the same table. A random model would reproduce this sequence with
probability far below 1e-30.

## Proven, inferred, unknown

**Proven** (code path plus live match):
- the seed source (position hash of the container), with no save or player input;
- one weighted pick per container and the R_ABAND_CRATE / R_ABAND_LOCK weights;
- the amount formula and its reuse of d1;
- the tech-class formula, and that crate tech is always C;
- the system trade-good rule (Fusion Core / Spark Canister in 320);
- the FE crates' items.

**Inferred:**
- D and the float32 position model for systems never visited. This is the end-reward fit: 89 containers, 3 systems.
  - About 7.5 % of containers lie within D's uncertainty of a .5 rounding edge. The tool then marks them
    `AMBIGUOUS` and lists every alternative.
- R_ABAND_CASE amounts: the money handler was not traced, and no briefcase item was ever observed.
- The multiplier at `+0x9C` is 1 for all saves (true for the two saves seen).
- TIMEDUST fails in every non-expedition save. In a season-11 expedition the first try may succeed and change the loot.
- The FE room-3 Larval Core count: x2 is predicted.

**Unknown / not modelled:**
- the names of procedural items (Bones/Loot/BioSample/SeaHorror/Document): the category is predicted, the name is not;
- which recipe is given: it depends on the player's known recipes. When all are known, nanites were seen (amounts
  about 100–200, rule unknown);
- containers in derelicts that are not the system's natural ABAND_FREIGHTER POI (summoned or other spawns), the same
  limit as the end reward.

## User test (region 06607CAA, natural derelict, all confident)

Use the minimap: "Deck N · room R", and the per-room counts.
- Spot = position inside the room's bounding box with the map north-up (top = −z).
- Open each crate and wait for the toast to stop counting, or check the inventory.

**A. `0002050006607CAA`** (glyphs `020506607CAA`, MEDI_SLIME, end reward C-Class Reactor). It has 4 salvage crates and
no footlockers.

| Room | Deck | Spot | Predicted |
|---|---|---|---|
| 9 | 3 | bottom-right | **Salvaged Frigate Module x1** |
| 3 | 2 | middle-left (the left one of two crates) | Quantum Accelerator x3 |
| 3 | 2 | middle (the right one) | Projectile Ammunition x187 |
| 5 | 3 | bottom-centre | Quantum Accelerator x3 |

**B. `00009D0006607CAA`** (glyphs `009D06607CAA`, MEDI_BUGS, end reward Fuel Unit C). It has 3 crates and 4
footlockers.

| Room | Deck | Container, spot | Predicted |
|---|---|---|---|
| 6 | 3 | footlocker, middle | **Salvaged Frigate Module x1** |
| 6 | 3 | footlocker, middle-right | Deflector Shield Module x1, C |
| 2 | 2 | footlocker, middle-right | Photon Cannon Module x1, C |
| 2 | 2 | salvage crate, middle | Projectile Ammunition x270 |
| 5 | 2 | salvage crate, bottom-right | Hypnotic Eye x3 |
| 8 | 3 | salvage crate, bottom-left (next to a footlocker) | Pulse Engine Module x1, C |
| 8 | 3 | footlocker beside it | Tainted Metal x30 |

**C. `0000360006607CAA`** (glyphs `003606607CAA`, CARGO_SLIME, end reward Combat Unit C). It has 5 salvage crates.

| Room | Deck | Spot | Predicted |
|---|---|---|---|
| 1 | 1 | top-left | **Salvaged Frigate Module x1** |
| 4 | 4 | bottom-right | Tainted Metal x30 |
| 6 | 4 | bottom-right | Hadal Core x2 |
| 7 | 4 | top-left | Larval Core x2 |
| 8 | 4 | bottom-right | Hadal Core x2 |

- Also on `0000FE0006607CAA`: check that the room-3 Larval Core ends at **x2** in the inventory.
- A miss on one crate with hits elsewhere would point to D or rounding; misses everywhere would point to the position
  model.

## Files

- `tools/predict_crate_loot_705.py`: the predictor. It reuses `predict_end_reward_705.py` (POI, D, hash, MWC),
  `extra_containers_705.py` and `nms_universe_address_705.py`.
- Scratch (disassembly listings, checks, region run `region.jsonl`, English name map `lang_en.json`):
  `D:/Orca/Temp/claude/D--Orca-NMS-Derelict-Probe/3bcdb12b-7aa1-4b9d-a671-cd2211d292d8/scratchpad/crate/`.
- Handler map, from type hash in the reward MBIN to the handler called by the item processor `0x140F1BAE0`:

| Reward type | Hash | Handler |
|---|---|---|
| SpecificProduct | 21B90B77 | 0x140F21570 |
| SpecificSubstance | 4551B575 | 0x140F1E6F0 |
| ProcTechProduct | C2F84D8E | 0x140F24490 → 0x140F20E20 |
| ProceduralProduct | 948E6184 | 0x140F248B0 |
| SystemSpecificProductFromList | 333BADF8 | 0x140F22480 → 0x140F20290 |
| ProductRecipeFromList | 83563CF0 | 0x140F389B0 |
| SeasonalSubstance | ED0B8631 | 0x140F1EA80 |
