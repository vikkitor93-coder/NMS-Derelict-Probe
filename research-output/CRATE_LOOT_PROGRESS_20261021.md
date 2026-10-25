# Crate loot prediction: progress and handoff (2026-10-21)

The full report is in `CRATE_LOOT_PREDICTION_20261021.md`. No background jobs are running; the region batch finished.

## Ground truth (user, in-game)

- **`0000FE0006607CAA` room 2 salvage crate:** Photon Cannon Module x1, C-class. It repeats after a reload and on another save.
- **`0000FE0006607CAA` room 3 salvage crate:** Larval Core. The toast shows x1, and it repeats after a reload.
- These are the only 2 salvage crates in this derelict.

## Proven

**Seed:**
- The seed is the position hash `0x140504EB0` of the container's world position, rounded half away from zero.
- World position = f32(POI + f32(RefDungeonEntrance + D + layout_local_xyz)), the same model and D as the end reward.
- It has no save or player input.

**The pick:**
- Every container table uses `TryFirst_ThenSelectAlways`. The seasonal TIMEDUST is tried first and fails out of season; then one weighted pick is made with the first MWC draw d1.

**Using the same d1:**
- **Amount:** `min + (d1·(max−min+1) >> 32)`.
- **Tech class:** roll `d1·101 >> 32` against 55/80/95. Crate and footlocker tech modules are therefore always C.
- **System trade good:** picked by the first draw of `pack(universe address)`.

**Matches:**
- both FE crates (the items);
- the whole 47-seed run `0000320006606CAA`, with exact stacks;
- 5/5 tall-locker seeds.

**Tables:** both the crate and the footlocker use R_ABAND_CRATE, where FRIG_TOKEN has weight 5/198 = 2.525 %.

## Inferred

- D (and the position model) for systems never visited. About 7.5 % of containers are flagged AMBIGUOUS.
- Briefcase money amounts.
- The multiplier at manager `+0x9C` is 1.
- Expedition (season 11) saves may differ.

### Open discrepancy

FE room 3 is predicted as **Larval Core x2**, but the user's toast showed x1 twice.
- The 320 video shows these toasts counting up (Larval Core x1→2), so x1 may be a frame captured mid-count.
- The user should check the inventory delta. If it really is 1, recheck the amount formula for SpecificProduct (`0x140F200B0`, the max/min field offsets `+0x40/+0x44`) and the `+0x9C` multiplier.

## Unknown

- The names of procedural items (Bones/Loot/BioSample/SeaHorror/Document).
- The recipe result: it depends on the player, and nanites are given when all are known.
- Derelicts that are not natural POI derelicts.

## Files created or changed

- `tools/predict_crate_loot_705.py` (new).
- `research-output/CRATE_LOOT_PREDICTION_20261021.md` (new).
- This file (new).
- `STATUS.md`: one line under the 12:00 Claude checkpoint (backup `STATUS.md.pre-crate-loot-20261021`).
- Scratch: `D:/Orca/Temp/claude/D--Orca-NMS-Derelict-Probe/3bcdb12b-7aa1-4b9d-a671-cd2211d292d8/scratchpad/crate/`
  - t1–t6.py: checks;
  - the disassembly txt files;
  - `region.jsonl`: 549 systems in 06607CAA ≤ 0x225;
  - `lang_en.json`.

## Commands that work

```
python -I tools/predict_crate_loot_705.py 0000FE0006607CAA            # crates + footlockers
python -I tools/predict_crate_loot_705.py 0000FE0006607CAA --room 3 --all --json
```

## Next steps

1. Get the user's Larval Core inventory count (x1 or x2).
2. The user tests `0002050006607CAA`, `00009D0006607CAA` and `0000360006607CAA` (tables in the report).
3. Optional:
   - trace the money handler (briefcase/locker Units/Nanites);
   - trace the procedural product names (`0x140F248B0`);
   - add the crate predictor to the minimap or viewer. This needs a NOTICE in `D:/Orca/NMS-COORDINATION.md` first.
