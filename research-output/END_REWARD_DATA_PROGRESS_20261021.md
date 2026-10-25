# End-reward data for all atlas systems: progress note (2026-10-21)

Stopped early because the usage limit was close. No project file was edited, no coordination entry was posted,
and no precompute was started. Nothing is half-edited: `tools/build_atlas_index.py` and the other shared or
scanner-imported files are unchanged.

## Measured so far (profiling only)

- **POI step** (`tools/space_poi_position_705.py`, Unicorn, Shipwright venv): 7.8 s one-time init per process
  (`PoiGen()`), then **0.28–0.42 s per system** in the same process (5 systems, incl. 0002250006607CAA). The
  current tool pays the 7.8 s init on every call, so a persistent worker removes it.
- **Layout step**: the predictor needs the `R_W_END` instance, which needs the full writer run. The scanner DB
  (`app-data/derelicts.sqlite`, read-only) has 59,859 systems. Average time per system: writer_seconds 1.67 s,
  total_seconds 1.81 s, i.e. about 30 CPU-hours in all. Every system ran on the native writer, none fell back to
  Unicorn, and there are 0 failures.
  - The DB keeps full layouts for only 101 systems. 1,458 cached `derelict.json` files are in
    `emu/fastgen/generated/`.
  - So a back-fill must re-run the writer for about 58k systems.
- **Estimate**: about 2.2 s CPU per system → about 59k × 2.2 / 6 workers ≈ **6 h**.
  - The scanner was running 6 `fast_worker_705.py` processes at 99 % CPU, so this will be slower while it scans.
  - Scan-time compute (the scanner already has the layout) costs only the POI step, about 0.35 s per system.
- **Names**: the English language files and the product and proc-tech tables were extracted (read-only) to
  `D:/Orca/Temp/claude/D--Orca-NMS-Derelict-Probe/3bcdb12b-7aa1-4b9d-a671-cd2211d292d8/scratchpad/agent-rewards/paks/`.
  They have not been searched yet for the SHIP_CORE_* and UP_FR* display names.

## Planned design (not written yet)

- `tools/end_reward_worker_705.py`: runs under the Shipwright venv python (3.13.15, the same as the system python).
  It loads, in this order:
  1. `native_writer_705.NativeSession()` first, which reserves its fixed addresses;
  2. `fast_generate_705.cached_catalog()`;
  3. `space_poi_position_705.PoiGen()`.
  It then answers JSON lines `{"address", "end_instance"?}`:
  - layout: a cached `derelict.json`, otherwise `F.generate([... "--out", <per-worker tmp>, "--override", "0"],
    writer=<same closure as fast_worker_705>)`;
  - then `predict_end_reward_705.predict(addr, poi, lay)`, the unchanged function, so results are identical by
    construction;
  - it returns the result plus the timings.
- `tools/end_reward_batch_705.py`:
  - `RewardPool(workers)` with `.predict(addresses, layouts=None)`; `predict_many(addresses, workers=N,
    layouts=None) -> {addr: (name, cls, ambiguous, alt)}`;
  - a CLI with `--cache rewards.csv`, resumable (it skips addresses already done), workers at BELOW_NORMAL
    priority, at most 6;
  - it restarts a worker that dies (a native fault).
- Mapping to the data contract:
  - SHIP_CORE_X → name from the product table or language file, class X;
  - FreighterTech* → unit name, `freighter_tech_if_picked.class`;
  - ambiguous = the confidence starts with "AMBIGUOUS";
  - alt = the distinct alternative picks.
  - Note: the alternatives keep the same tech class, because the class depends only on the address.

## Exact next steps

1. Find the display names in the extracted language and product files.
2. Write the worker and batch tool as above.
3. Check identical results against `python -I tools/predict_end_reward_705.py --json` on 200+ systems, including
   `0002250006607CAA` (Fuel B), `00003C0006607CAA` (SHIP_CORE_C), `00002A0006607CAA` (Exploration S) and
   `00001A0006607CAA` (Fuel A).
4. Post a NOTICE (index format 4: `reward_name`, `reward_class`, `reward_ambiguous` appended) and a REQUEST
   (region CSV columns, scan-time `RewardPool`, back-fill from the cache) in `D:/Orca/NMS-COORDINATION.md`.
   Only then edit `tools/build_atlas_index.py`, with a `.pre-rewards` backup first.
5. Start the precompute in the background into
   `D:/Orca/NMS-Derelict-Probe-analysis/end-reward-cache/rewards.csv`, using the addresses from the atlas
   region CSVs.
6. Update `END_REWARD_PREDICTION_20261020.md` with the batch tool, timings, contract and distribution.
