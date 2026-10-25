"""NMS 7.05 (SHA 13D5060D...) derelict address -> (writer seed, FreighterDungeons preset).

Native evidence: FUN_1410FED60 (component init) and FUN_1411001D0 (worker) both do
  a = FUN_140583A90(universe address)  (packing, see nms_universe_address_705.py)
  if _DAT_14526D4F0 != 0: a = override
  a = (a>>33 ^ a) * 0x64DD81482CBD31D7 ; a = (a>>33 ^ a) * -0x1C955A39EC9ED669 ; seed = a>>33 ^ a
The worker passes `seed` to writer FUN_14039E5E0.  FUN_1410FED60 passes the same seed to the
weighted chooser FUN_141100D40 (list at component_cfg+0x58, 0x18-byte entries, float weight at +0x10).
Chooser RNG: lo=u32(seed), hi=seed>>32; n=lo+(lo==0); u=rotl16(lo)^hi^lo;
  r=(float)((double)u32(n*0x5A76F899+u) * D282D8) ; D282D8 = bytes 00 00 10 00 00 00 F0 3D (double)
  cum=w[0]; idx=0; k=0; while cum < f32(r*total) and k<count: cum+=w[k+1]; idx++; k++
Result idx is the options index == freighterdungeonstable element.
"""
import os, struct, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'research-output', 'offline-layout-705-20261019'))
from nms_universe_address_705 import pack_universe_address_705

def f32(x):
    return struct.unpack('<f', struct.pack('<f', x))[0]


M = (1 << 64) - 1
C_D282D8 = struct.unpack('<d', bytes.fromhex('000010000000f03d'))[0]
PRESETS = [('MEDI_TURRETS', 0.66), ('MEDI_FLOATERS', 0.33), ('MEDI_BUGS', 1.0), ('MEDI_SLIME', 0.25),
           ('MEDI_MAZE', 0.15), ('CARGO_TURRETS', 0.66), ('CARGO_FLOATERS', 0.33), ('CARGO_BUGS', 1.0),
           ('CARGO_SLIME', 0.25), ('CARGO_MAZE', 0.15)]


def mix_seed(packed, override=0):
    a = override if override else packed
    a = ((a >> 33 ^ a) * 0x64DD81482CBD31D7) & M
    a = ((a >> 33 ^ a) * (-0x1C955A39EC9ED669 & M)) & M
    return a >> 33 ^ a


def choose_preset_index(seed, weights=None):
    w = [f32(x) for _, x in PRESETS] if weights is None else [f32(x) for x in weights]
    cnt = min(len(w), 32)
    total = f32(0)
    for x in w[:cnt]:
        total = f32(total + x)
    lo, hi = seed & 0xFFFFFFFF, seed >> 32
    n = lo + (lo == 0)
    u = (((lo >> 16) | (lo << 16)) & 0xFFFFFFFF) ^ hi ^ lo
    rv = ((n * 0x5A76F899 + u) & 0xFFFFFFFF)
    r = f32(rv * C_D282D8)
    thr = f32(r * total)
    cum = w[0]; idx = 0; k = 0
    while cum < thr and k < cnt:
        nxt = w[k + 1] if k + 1 < cnt else f32(0)  # native reads stack garbage here (edge case)
        cum = f32(cum + nxt); idx += 1; k += 1
    return min(idx, cnt - 1)


def derelict_seed_preset(address, override=0):
    seed = mix_seed(pack_universe_address_705(address), override)
    i = choose_preset_index(seed)
    return seed, PRESETS[i][0], i


if __name__ == '__main__':
    for a in sys.argv[1:] or ['00003B0006606CAA']:
        s, p, i = derelict_seed_preset(a)
        print(f'{a} seed={s:016X} preset={p} index={i}')
