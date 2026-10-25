#!/usr/bin/env python3
"""NMS 7.05 (NMS.exe SHA-256 13D5060D...3499): offline prediction of derelict-freighter container loot.

usage:
  python -I tools/predict_crate_loot_705.py <ADDRESS16> [--room N] [--all] [--json]
  python -I tools/predict_crate_loot_705.py --glyphs <12 hex> ...
  --all   also list briefcases (R_ABAND_CASE) and tall lockers (R_ABAND_LOCK); default: salvage crates and crew
          footlockers (both R_ABAND_CRATE)

Mechanism (evidence: research-output/CRATE_LOOT_PREDICTION_20261021.md):
 1. container world position = ABAND_FREIGHTER POI + RefDungeonEntrance + D + the generator's layout position
    (same float32 model and D as tools/predict_end_reward_705.py); seed = position hash 0x140504EB0 of the position
    rounded half away from zero. No save, player or time input.
 2. TryFirst_ThenSelectAlways (0x140F19E90 case 7 at 0x140F1B15F): the first entry (seasonal TIMEDUST, season 11)
    is tried and fails outside that season; then ONE weighted pick with the first MWC draw d1 of the seed:
    f32(d1 * 2^-32) * 100 against the cumulative f32(w / total * 100).
 3. The picked entry's handler gets the same cTkSeed and re-derives the SAME first draw d1:
    amount = min + (d1 * (max - min + 1) >> 32)              (0x140F200B0 / 0x140F20290 / 0x140F203B0)
    tech quality roll = d1 * (N+R+E+L+1) >> 32 vs 55/80/95  (0x140F20E20) -> crate tech modules are always C.
    system-specific product index = first draw of pack(universe address) * len(list) >> 32  (0x140F20290).
    So one container gives exactly one item stack.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import predict_end_reward_705 as P  # noqa: E402
from extra_containers_705 import extra_containers  # noqa: E402
from nms_universe_address_705 import pack_universe_address_705  # noqa: E402

M32 = 0xFFFFFFFF

# ---- reward tables: metadata/reality/tables/rewardtable.mbin (SHA-256 A0448326...6096059), order as stored.
# (kind, key, weight, extra). kinds: subst/product (amount min,max), tech (group, weights E,L,N,R as stored),
# proc (procedural product category), sysprod (list, min, max), recipe, money (currency, min, max), season.
TRA5 = ["TRA_ALLOY5", "TRA_COMMODITY5", "TRA_COMPONENT5", "TRA_ENERGY5", "TRA_EXOTICS5", "TRA_MINERALS5", "TRA_TECH5"]
TRA1 = [t[:-1] + "1" for t in TRA5]
Q4 = (15, 5, 55, 25)  # Epic, Legendary, Normal, Rare (MBIN field order) = 55/25/15/5 N/R/E/L
TABLES = {
    "R_ABAND_CRATE": [
        ("season", "TIMEDUST", 0, (10, 30)),
        ("recipe", "DERELICT_RECIPE", 8, None),
        ("product", "AMMO", 65, (100, 600)),
        ("tech", "SHIPJUMP_NAME_L", 3, Q4),
        ("tech", "ION1_NAME_L", 3, Q4),
        ("tech", "SHIPSHIELD_NAME_L", 3, Q4),
        ("tech", "SHIPGUN1_NAME_L", 3, Q4),
        ("proc", "Bones", 2, None),
        ("proc", "Loot", 2, None),
        ("proc", "BioSample", 2, None),
        ("proc", "SeaHorror", 2, None),
        ("product", "FRIG_TOKEN", 5, (1, 1)),
        ("product", "STORM_CRYSTAL", 10, (1, 3)),
        ("product", "FIENDCORE", 10, (1, 3)),
        ("product", "FISHCORE", 10, (1, 3)),
        ("product", "EYEBALL", 10, (1, 3)),
        ("sysprod", "TRA5", 40, (TRA5, 1, 3)),
        ("subst", "AF_METAL", 20, (10, 30)),
    ],
    "R_ABAND_CASE": [
        ("season", "TIMEDUST", 0, (10, 30)),
        ("proc", "Document", 1, None),
        ("money", "Units", 10, (20000, 100000)),
        ("money", "Nanites", 40, (20, 50)),
        ("money", "Units", 40, (5000, 10000)),
        ("money", "Nanites", 10, (50, 200)),
        ("subst", "AF_METAL", 40, (10, 30)),
    ],
    "R_ABAND_LOCK": [
        ("season", "TIMEDUST", 0, (10, 25)),
        ("product", "GRENFUEL1", 10, (1, 1)),
        ("tech", "BOLT_NAME_L", 1, Q4),
        ("tech", "GRENADE_NAME_L", 1, Q4),
        ("tech", "T_GRENADE_NAME_L", 1, Q4),
        ("tech", "RAILGUN1_NAME_L", 1, Q4),
        ("tech", "BOLTSHOTGUN_NAME_L", 1, Q4),
        ("tech", "BOLTSMG_NAME_L", 1, Q4),
        ("tech", "UI_COLD_NAME_CORE_L", 1, (30, 10, 0, 60)),
        ("tech", "UI_SHIELD_NAME_CORE_L", 1, Q4),
        ("tech", "UI_JETPACK_NAME_CORE_L", 1, Q4),
        ("tech", "UI_ENERGY_NAME_CORE_L", 1, Q4),
        ("product", "AMMO", 20, (100, 600)),
        ("money", "Units", 20, (5000, 10000)),
        ("money", "Nanites", 20, (20, 50)),
        ("product", "NIPNIPBUDS", 10, (1, 3)),
        ("product", "WAR_CURIO1", 10, (1, 1)),
        ("product", "WAR_CURIO2", 10, (1, 1)),
        ("product", "EXP_CURIO1", 10, (1, 1)),
        ("product", "EXP_CURIO2", 10, (1, 1)),
        ("product", "TRA_CURIO1", 10, (1, 1)),
        ("product", "TRA_CURIO2", 10, (1, 1)),
        ("sysprod", "TRA1", 70, (TRA1, 1, 3)),
        ("subst", "AF_METAL", 20, (10, 25)),
    ],
}
TABLE_OF_KIND = {"salvage_crate": "R_ABAND_CRATE", "crew_footlocker": "R_ABAND_CRATE",
                 "briefcase": "R_ABAND_CASE", "tall_locker": "R_ABAND_LOCK"}
# English names from the 7.05 language / product tables (display only).
NAMES = {
    "AMMO": "Projectile Ammunition", "FRIG_TOKEN": "Salvaged Frigate Module", "STORM_CRYSTAL": "Storm Crystal",
    "FIENDCORE": "Larval Core", "FISHCORE": "Hadal Core", "EYEBALL": "Hypnotic Eye", "AF_METAL": "Tainted Metal",
    "GRENFUEL1": "Unstable Plasma", "NIPNIPBUDS": "NipNip Buds", "WAR_CURIO1": "Vy'keen Effigy",
    "WAR_CURIO2": "Vy'keen Dagger", "EXP_CURIO1": "Korvax Casing", "EXP_CURIO2": "Convergence Cube",
    "TRA_CURIO1": "Gek Relic", "TRA_CURIO2": "GekNip",
    "TRA_ALLOY5": "Superconducting Fibre", "TRA_COMMODITY5": "Teleport Coordinators",
    "TRA_COMPONENT5": "Vector Compressors", "TRA_ENERGY5": "Fusion Core", "TRA_EXOTICS5": "Neural Duct",
    "TRA_MINERALS5": "Re-latticed Arc Crystal", "TRA_TECH5": "Quantum Accelerator",
    "TRA_ALLOY1": "Nanotube Crate", "TRA_COMMODITY1": "Decrypted User Data", "TRA_COMPONENT1": "Enormous Metal Cog",
    "TRA_ENERGY1": "Spark Canister", "TRA_EXOTICS1": "De-Scented Bottles", "TRA_MINERALS1": "Dirt",
    "TRA_TECH1": "Decommissioned Circuits",
    "SHIPJUMP_NAME_L": "Pulse Engine", "ION1_NAME_L": "Hyperdrive", "SHIPSHIELD_NAME_L": "Deflector Shield",
    "SHIPGUN1_NAME_L": "Photon Cannon", "BOLT_NAME_L": "Boltcaster", "GRENADE_NAME_L": "Plasma Launcher",
    "T_GRENADE_NAME_L": "Geology Cannon", "RAILGUN1_NAME_L": "Blaze Javelin", "BOLTSHOTGUN_NAME_L": "Scatter Blaster",
    "BOLTSMG_NAME_L": "Pulse Spitter", "UI_COLD_NAME_CORE_L": "Thermal Protection",
    "UI_SHIELD_NAME_CORE_L": "Defence Systems", "UI_JETPACK_NAME_CORE_L": "Movement System",
    "UI_ENERGY_NAME_CORE_L": "Life Support",
    "Bones": "procedural bone/fossil item (name varies)", "Loot": "procedural salvaged loot item (name varies)",
    "BioSample": "procedural biological sample (name varies, e.g. Oily Worms)",
    "SeaHorror": "procedural abyssal item (name varies, e.g. Twisted Gelsack)",
    "Document": "procedural document item (name varies)",
}
CLASSES = "CBAS"


def first_draw(seed: int) -> int:
    n, u = P.mwc_init(seed)
    return (n * P.K_MWC + u) & M32


def pick_entry(seed: int, table: list) -> int | None:
    """0x140F1B1D9..0x140F1B273: one weighted pick; None = no entry reached (not seen)."""
    draw = P.f32(P.f32(first_draw(seed) * P.D2_32) * P.f32(100.0))
    total = P.f32(0.0)
    for e in table:
        total = P.f32(total + P.f32(e[2]))
    cum = P.f32(0.0)
    for i, e in enumerate(table):
        cum = P.f32(cum + P.f32(P.f32(P.f32(e[2]) / total) * P.f32(100.0)))
        if cum >= draw:
            return i
    return None


def system_product(address: str, items: list[str]) -> str:
    """0x140F20290: index from the first MWC draw of pack(current universe address)."""
    return items[(first_draw(pack_universe_address_705(address)) * len(items)) >> 32]


def loot(seed: int, table_id: str, address: str) -> dict:
    table = TABLES[table_id]
    i = pick_entry(seed, table)
    if i is None:
        return {"entry": None, "item": "nothing (draw past last boundary)"}
    kind, key, w, extra = table[i]
    d1 = first_draw(seed)
    total_w = sum(e[2] for e in table)
    r = {"entry": i, "entry_type": kind, "key": key, "table_chance_pct": round(100 * w / total_w, 3)}
    if kind in ("product", "subst"):
        lo, hi = extra
        r.update(id=key, name=NAMES.get(key, key), amount=lo + ((d1 * (hi - lo + 1)) >> 32))
    elif kind == "sysprod":
        items, lo, hi = extra
        pid = system_product(address, items)
        r.update(id=pid, name=NAMES.get(pid, pid), amount=lo + ((d1 * (hi - lo + 1)) >> 32))
    elif kind == "tech":
        e_, l_, n_, rr = extra
        roll = (d1 * (l_ + 1 + rr + n_ + e_)) >> 32
        q = 0 if roll <= n_ else 1 if roll <= n_ + rr else (3 if roll > n_ + rr + e_ else 2)
        r.update(name=f"{NAMES.get(key, key)} Module", tech_class=CLASSES[q], amount=1)
    elif kind == "money":
        lo, hi = extra
        r.update(name=key, amount=lo + ((d1 * (hi - lo + 1)) >> 32), amount_status="inferred (money handler not traced)")
    elif kind == "proc":
        r.update(name=NAMES.get(key, key), amount=1, amount_status="item name not modelled")
    elif kind == "recipe":
        r.update(name="derelict furniture blueprint (one you do not know yet; if you know them all, nanites)",
                 amount_status="depends on the player's known recipes")
    elif kind == "season":
        r.update(name="TIMEDUST (seasonal)", amount_status="only in season 11")
    return r


def describe(r: dict) -> str:
    if r.get("entry") is None:
        return r["item"]
    s = r["name"]
    if r.get("tech_class"):
        s += f" x1, {r['tech_class']}-class"
    elif isinstance(r.get("amount"), int):
        s += f" x{r['amount']}"
    return s


def deck_info(lay: dict) -> tuple[list[int], list]:
    """Deck numbering as the minimap / viewer draw it: levels top-down, Deck 1 = highest."""
    from_cells = set()
    e = lay.get("entrance_origin") or [6, 3, 0]
    for rm in lay["rooms"]:
        raw = rm["raw_u16_0x00_0x1F"]
        from_cells.update(range(raw[1], raw[4] + 1))
    return sorted(from_cells, reverse=True), e


def spot(c: dict, lay: dict, levels: list[int], e) -> dict:
    p = c["layout_local_xyz"]
    u, v, level = p[0] / 8 + e[0] + 0.5, p[2] / 8 + e[2] + 0.5, math.floor(p[1] / 8 + 0.5) + e[1]
    rm = next((r for r in lay["rooms"] if r["room_index"] == c.get("room_index")), None)
    where = ""
    if rm:
        raw = rm["raw_u16_0x00_0x1F"]
        fu = (u - raw[0]) / max(1, raw[3] - raw[0] + 1)
        fv = (v - raw[2]) / max(1, raw[5] - raw[2] + 1)
        where = ("top" if fv < 0.34 else "bottom" if fv > 0.66 else "middle") + "-" + \
                ("left" if fu < 0.34 else "right" if fu > 0.66 else "centre")
    return {"deck": levels.index(level) + 1 if level in levels else None, "map_uv": [round(u, 2), round(v, 2)],
            "spot_in_room_bbox_north_up": where, "room_template": rm["template_name"] if rm else None}


def predict(address: str, poi: dict, lay: dict, room: int | None, kinds: tuple[str, ...]) -> dict:
    res = {"address": address, "preset": lay.get("preset")}
    if not poi or poi.get("aband_freighter") is None:
        res["status"] = "no ABAND_FREIGHTER space POI in this system: container positions (and seeds) unknown"
        return res
    p = poi["aband_freighter"]
    res["poi_aband_freighter"] = p
    levels, e = deck_info(lay)
    conts = [c for c in list(lay["containers"]) + extra_containers(lay) if c["container_kind"] in kinds]
    if room is not None:
        conts = [c for c in conts if c.get("room_index") == room]
    out = []
    for c in conts:
        lp = c["layout_local_xyz"]

        def world_at(k, dk):
            return P.f32(p[k] + P.f32(P.ENTRANCE_REF[k] + dk + lp[k]))

        base = [P.round_half_away(world_at(k, P.DUNGEON_D[k])) for k in range(3)]
        opts = []
        for k in range(3):
            s = {base[k]}
            for i in range(41):
                dk = P.DUNGEON_D[k] - P.DUNGEON_D_ERR[k] + 2 * P.DUNGEON_D_ERR[k] * i / 40
                s.add(P.round_half_away(world_at(k, dk)))
            opts.append(sorted(s))
        tid = TABLE_OF_KIND[c["container_kind"]]
        seed = P.position_seed(*base)
        r = loot(seed, tid, address)
        alts = []
        for x in opts[0]:
            for y in opts[1]:
                for z in opts[2]:
                    if [x, y, z] != base:
                        s2 = P.position_seed(x, y, z)
                        alts.append({"rounded": [x, y, z], "seed": f"{s2:016X}", "loot": describe(loot(s2, tid, address))})
        world = [world_at(k, P.DUNGEON_D[k]) for k in range(3)]
        margin = [round(abs((w - math.floor(w)) - 0.5), 3) for w in world]
        row = {"room": c.get("room_index"), "kind": c["container_kind"], "table": tid, "node": c.get("scene_node_name"),
               "layout_xyz": [round(v, 3) for v in lp], **spot(c, lay, levels, e),
               "world_rounded": base, "rounding_margin_m": margin, "seed": f"{seed:016X}",
               "loot": r, "predicted": describe(r)}
        if alts:
            row["confidence"] = ("stable" if all(a["loot"] == row["predicted"] for a in alts)
                                 else "AMBIGUOUS (rounding alternatives differ)")
            row["alternatives"] = alts
        else:
            row["confidence"] = "high"
        out.append(row)
    out.sort(key=lambda r: (r["room"] if r["room"] is not None else 99, r["kind"], r["layout_xyz"]))
    res["containers"] = out
    res["frig_token_count"] = sum(1 for r in out if r["loot"].get("key") == "FRIG_TOKEN")
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("addresses", nargs="+")
    ap.add_argument("--glyphs", action="store_true")
    ap.add_argument("--galaxy", type=lambda v: int(v, 0), default=0)
    ap.add_argument("--room", type=int)
    ap.add_argument("--all", action="store_true", help="include briefcases and tall lockers")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    kinds = tuple(TABLE_OF_KIND) if a.all else ("salvage_crate", "crew_footlocker")
    addrs = [P.glyphs_to_address(x, a.galaxy) if a.glyphs else x.upper() for x in a.addresses]
    pois = P.poi_positions(addrs)
    for addr in addrs:
        r = predict(addr, pois.get(addr), P.load_layout(addr), a.room, kinds)
        if a.json:
            print(json.dumps(r))
            continue
        print(f"{addr}  preset {r.get('preset')}")
        if "status" in r:
            print("   " + r["status"])
            continue
        for c in r["containers"]:
            flag = "" if c["confidence"] in ("high", "stable") else "   [" + c["confidence"] + "]"
            print(f"   room {c['room']} deck {c['deck']} {c['kind']:<15} {c['spot_in_room_bbox_north_up']:<14}"
                  f" layout {c['layout_xyz']}  ->  {c['predicted']}{flag}")
            if flag:
                for alt in c["alternatives"]:
                    print(f"        alt {alt['rounded']}: {alt['loot']}")
        print(f"   Salvaged Frigate Modules: {r['frig_token_count']}")


if __name__ == "__main__":
    main()
