#!/usr/bin/env python3
"""NMS 7.05 (NMS.exe SHA-256 13D5060D...3499): offline prediction of a derelict freighter's END reward
(R_FREI_TECH: SHIP_CORE_C/B/A/S or a procedural frigate upgrade "Salvaged Fleet ... Unit" with class C/B/A/S).

usage:
  python -I tools/predict_end_reward_705.py <ADDRESS16> [...]          e.g. 0002250006607CAA
  python -I tools/predict_end_reward_705.py --glyphs <12 hex> [...]     portal code P SSS YY ZZZ XXX (planet ignored)
  options: --json   (one JSON object per address)

Chain (details and evidence: research-output/END_REWARD_PREDICTION_20261020.md):
 1. address -> writer seed + preset (tools/derelict_seed_preset_705.py) -> layout (fast generator,
    D:/Orca/NMS-Derelict-Probe-fastgen/fast_generate_705.py; cached derelict.json is reused).
 2. derelict world origin = ABAND_FREIGHTER space-POI position (tools/space_poi_position_705.py, game code under
    Unicorn) + RefDungeonEntrance (-100.610405, 145.536758, 31.9607048) + D (measured, see DUNGEON_D below).
    No rotation (measured: 0 deg on two derelicts).
 3. end-terminal world position = origin + R_W_END instance transform of the terminal locator
    (scene offsets 0,0,8.27731 + -0.019725,1.107091,-2.174742).
 4. interaction seed = position hash 0x140504EB0 of the rounded (half away from zero) world position.
 5. R_FREI_TECH SelectAlways pick (0x140F1AB90): one MWC draw from that seed, weights 20/25/15/5/7x100.
 6. if a FreighterTech* entry is picked: 0x140F248B0 replaces the seed with the address seed (categories 13..22);
    0x140EBF810: number = first MWC draw * 100000 >> 32; class = hash(number) -> 4th MWC draw ->
    GcGameplayGlobals.FreighterTechQualityWeightings 55/25/15/5 (C/B/A/S).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import struct
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from derelict_seed_preset_705 import derelict_seed_preset  # noqa: E402

EMU_PY = os.environ.get("EMU_PYTHON", os.path.expandvars("%USERPROFILE%/tools/NMS-Shipwright/.venv/Scripts/python.exe"))
FASTGEN = Path("D:/Orca/NMS-Derelict-Probe-fastgen/fast_generate_705.py")
LAYOUT_DIRS = [Path("D:/Orca/NMS-Derelict-Probe-analysis/emu/fastgen/generated"),
               Path("D:/Orca/NMS-Derelict-Probe-analysis/emu/generated")]

M32, M64 = 0xFFFFFFFF, (1 << 64) - 1
K_MWC = 0x5A76F899
K_HASH = 0x9DDFEA08EB382D69
D2_32 = struct.unpack("<d", bytes.fromhex("000010000000f03d"))[0]  # double at 0x144B282D8

ENTRANCE_REF = (-100.610405, 145.536758, 31.9607048)   # DUNGEON.SCENE RefDungeonEntrance
# layout origin - (POI + entrance). Fitted under the float32 model world = f32(POI + f32(entrance + D + layout)):
# every one of 89 crates/lockers/cases of 0000750006606CAB (21), 0000760006606CAB (37), 0000790006606CAB (31),
# whose integer world position was recovered from its captured reward seed, rounds correctly for D in
# x [-0.0365, -0.0050], y [21.7040, 21.7245], z [-14.0585, -14.0315]. Centre and half-width per axis.
DUNGEON_D = (-0.02075, 21.71425, -14.0450)
DUNGEON_D_ERR = (0.01575, 0.01025, 0.0135)
TERMINAL_LOCAL = (-0.019725, 1.107091, 8.27731 - 2.174742)  # ROOM_WALL_FINALTERMINAL -> terminal LOCATOR

R_FREI_TECH = [("SHIP_CORE_C", 20), ("SHIP_CORE_B", 25), ("SHIP_CORE_A", 15), ("SHIP_CORE_S", 5),
               ("FreighterTechHyp", 100), ("FreighterTechSpeed", 100), ("FreighterTechFuel", 100),
               ("FreighterTechTrade", 100), ("FreighterTechCombat", 100), ("FreighterTechMine", 100),
               ("FreighterTechExp", 100)]
TECH_NAMES = {"FreighterTechHyp": "Salvaged Fleet Hyperdrive Unit (UP_FRHYP)",
              "FreighterTechSpeed": "Salvaged Fleet Speed Unit (UP_FRSPE)",
              "FreighterTechFuel": "Salvaged Fleet Fuel Unit (UP_FRFUE)",
              "FreighterTechTrade": "Salvaged Fleet Trade Unit (UP_FRTRA)",
              "FreighterTechCombat": "Salvaged Fleet Combat Unit (UP_FRCOM)",
              "FreighterTechMine": "Salvaged Fleet Mining Unit (UP_FRMIN)",
              "FreighterTechExp": "Salvaged Fleet Exploration Unit (UP_FREXP)"}
QUALITY_WEIGHTS = [55, 25, 15, 5, 0, 0, 0, 0]  # GcGameplayGlobals.FreighterTechQualityWeightings
CLASSES = "CBAS"


def f32(x: float) -> float:
    return struct.unpack("<f", struct.pack("<f", x))[0]


def mwc_init(seed: int) -> tuple[int, int]:
    lo, hi = seed & M32, seed >> 32
    return lo + (lo == 0), (((lo << 16) | (lo >> 16)) & M32) ^ hi ^ lo


def mwc_next(n: int, u: int) -> tuple[int, int]:
    d = n * K_MWC + u
    return d & M32, d >> 32


def position_seed(x: int, y: int, z: int) -> int:
    """NMS.exe 0x140504EB0 applied to already-rounded integer coordinates."""
    cx, cy, cz = x & M64, y & M64, z & M64
    a = ((cy ^ cx) * K_HASH) & M64
    a ^= a >> 47
    a = ((a ^ cx) * K_HASH) & M64
    r8 = (((a >> 47) ^ a) * K_HASH) & M64
    c = ((cz ^ r8) * K_HASH) & M64
    d = (c >> 47) ^ c
    d = ((d ^ r8) * K_HASH) & M64
    return (((d >> 47) ^ d) * K_HASH) & M64


def round_half_away(v: float) -> int:
    return int(v + math.copysign(0.5, v))


def select_always(seed: int, items=R_FREI_TECH) -> tuple[str, float]:
    """0x140F1AB90 (SelectAlways), OverrideZeroSeed=false -> supplied seed."""
    n, u = mwc_init(seed)
    draw = f32(((n * K_MWC + u) & M32) * D2_32)  # cvtsi2sd, mulsd [0x144B282D8], cvtpd2ps
    draw = f32(draw * f32(100.0))
    total = f32(0.0)
    for _, w in items:
        total = f32(total + f32(w))
    cum = f32(0.0)
    for name, w in items:
        cum = f32(cum + f32(f32(f32(w) / total) * f32(100.0)))
        if cum >= draw:
            return name, draw
    return items[-1][0], draw


def freighter_tech_number_class(address_seed: int) -> tuple[int, str]:
    """0x140EBF810 with quality override -1 / mode 8 (number), class as 0x140EC0D5F/0x140EC87B0 derive it."""
    n, u = mwc_next(*mwc_init(address_seed))
    number = (n * 100000) >> 32
    x = (((number ^ 0x3D0000) >> 16) ^ number) & M32
    x = (x * 9) & M32
    x ^= x >> 4
    x = (x * 0x1B873593) & M32
    x ^= x >> 15
    s = (x + (x == 0), (((x << 16) | (x >> 16)) & M32) ^ x)
    for _ in range(4):
        s = mwc_next(*s)
    total = sum(QUALITY_WEIGHTS)
    roll = ((s[0] * total) >> 32) + 1
    cum = 0
    for i, w in enumerate(QUALITY_WEIGHTS):
        cum += w
        if roll <= cum:
            return number, CLASSES[i] if i < 4 else str(i)
    return number, "?"


def glyphs_to_address(glyphs: str, galaxy: int = 0) -> str:
    g = glyphs.upper().replace(" ", "").replace("-", "")
    if len(g) != 12 or any(c not in "0123456789ABCDEF" for c in g):
        raise SystemExit("glyph code must be 12 hex digits (P SSS YY ZZZ XXX)")
    return f"000{g[1:4]}{galaxy & 0xFF:02X}{g[4:6]}{g[6:9]}{g[9:12]}"


def load_layout(address: str) -> dict:
    for d in LAYOUT_DIRS:
        p = d / address / "derelict.json"
        if p.exists():
            lay = json.loads(p.read_text(encoding="utf-8"))
            if "instances" in lay and lay.get("address", address).upper() == address:
                return lay
    subprocess.run([sys.executable, "-I", str(FASTGEN), address], check=True, stdout=subprocess.DEVNULL)
    return json.loads((LAYOUT_DIRS[0] / address / "derelict.json").read_text(encoding="utf-8"))


def poi_positions(addresses: list[str]) -> dict:
    out = subprocess.run([EMU_PY, "-I", str(HERE / "space_poi_position_705.py"), *addresses],
                         check=True, capture_output=True, text=True).stdout
    res = {}
    for line in out.splitlines():
        if line.startswith("{"):
            r = json.loads(line)
            res[r["address"]] = r
    return res


def terminal_layout(lay: dict) -> list[float]:
    ends = [i for i in lay["instances"] if "ROOM_WALL_FINALTERMINAL" in i["scene_resource"].upper()]
    if len(ends) != 1:
        raise RuntimeError(f"expected one R_W_END instance, found {len(ends)}")
    a, t = ends[0]["source_axes"], ends[0]["translation"]
    return [t[k] + TERMINAL_LOCAL[0] * a[0][k] + TERMINAL_LOCAL[1] * a[1][k] + TERMINAL_LOCAL[2] * a[2][k]
            for k in range(3)]


def predict(address: str, poi: dict, lay: dict) -> dict:
    seed, preset, _ = derelict_seed_preset(address)
    res = {"address": address, "writer_seed": f"{seed:016X}", "preset": preset}
    tech_number, tech_class = freighter_tech_number_class(seed)
    res["freighter_tech_if_picked"] = {"number": tech_number, "class": tech_class}
    if not poi or poi.get("aband_freighter") is None:
        res["status"] = "no ABAND_FREIGHTER space POI in this system: end-room item cannot be predicted"
        return res
    p = poi["aband_freighter"]
    tl = terminal_layout(lay)

    def world_at(k: int, dk: float) -> float:  # float32 model, as fitted
        return f32(p[k] + f32(ENTRANCE_REF[k] + dk + tl[k]))

    world = [world_at(k, DUNGEON_D[k]) for k in range(3)]
    margin = []
    for k in range(3):
        frac_dist = abs((world[k] - math.floor(world[k])) - 0.5)  # distance to the .5 rounding boundary
        margin.append((frac_dist, DUNGEON_D_ERR[k]))
    candidates = {}
    base = [round_half_away(v) for v in world]
    axes_opts = []
    for k in range(3):
        opts = {base[k]}
        steps = 40
        for i in range(steps + 1):  # every D value inside the fitted interval
            dk = DUNGEON_D[k] - DUNGEON_D_ERR[k] + 2 * DUNGEON_D_ERR[k] * i / steps
            opts.add(round_half_away(world_at(k, dk)))
        axes_opts.append(sorted(opts))
    for x in axes_opts[0]:
        for y in axes_opts[1]:
            for z in axes_opts[2]:
                s = position_seed(x, y, z)
                item, draw = select_always(s)
                candidates[(x, y, z)] = (s, item, draw)
    s0, item0, draw0 = candidates[tuple(base)]
    res.update({
        "poi_aband_freighter": p,
        "terminal_layout": [round(v, 4) for v in tl],
        "terminal_world": [round(v, 3) for v in world],
        "terminal_rounded": base,
        "rounding_margin_m": [round(m[0], 3) for m in margin],
        "rounding_uncertainty_m": [round(m[1], 3) for m in margin],
        "end_seed": f"{s0:016X}",
        "select_draw": round(draw0, 4),
        "pick": item0,
    })
    items = {c[1] for c in candidates.values()}
    res["confidence"] = "high" if len(candidates) == 1 else ("pick stable across rounding alternatives" if len(items) == 1
                                                              else "AMBIGUOUS: rounding alternatives give different items")
    if len(candidates) > 1:
        res["alternatives"] = [{"rounded": list(k), "end_seed": f"{v[0]:016X}", "pick": v[1]} for k, v in candidates.items()]
    if item0.startswith("SHIP_CORE"):
        res["predicted_reward"] = f"{item0} (frigate ship core, class {item0[-1]})"
    else:
        res["predicted_reward"] = f"{TECH_NAMES[item0]}, {tech_class}-class (#{tech_number:05d})"
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("addresses", nargs="+")
    ap.add_argument("--glyphs", action="store_true")
    ap.add_argument("--galaxy", type=lambda v: int(v, 0), default=0)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    addrs = [glyphs_to_address(x, a.galaxy) if a.glyphs else x.upper() for x in a.addresses]
    pois = poi_positions(addrs)
    for addr in addrs:
        r = predict(addr, pois.get(addr), load_layout(addr))
        if a.json:
            print(json.dumps(r))
        else:
            print(f"{addr}: {r.get('predicted_reward', r.get('status'))}")
            for k in ("preset", "end_seed", "pick", "terminal_world", "rounding_margin_m", "confidence"):
                if k in r:
                    print(f"   {k}: {r[k]}")
            if "alternatives" in r:
                for alt in r["alternatives"]:
                    print(f"   alt {alt}")


if __name__ == "__main__":
    main()
