"""System names (the original procedural name, as the game generates it) for the NMS derelict project.

    name(address16_or_glyphs, galaxy=None)  ->  e.g. "Abarof-Dulin"

address16 is the project's universal address "000SSSGGYYZZZXXX" (16 hex digits; the galaxy is inside it).
glyphs is the 12-digit portal code "PSSSYYZZZXXX" and needs the galaxy (0 = Euclid). Standard library only.

This is a Python port of the system-naming part of hadsh/nms_namegen (https://github.com/hadsh/nms_namegen),
itself a fork of stuart/nms_namegen. The data file system_names_705_data.json.gz holds that project's eight alphasets
and its letter map (letter_map.json), flattened to one lookup per three-letter key (checked equal to the original
tree search for all 24,458 leaves). It knows nothing about names changed by players or by Discovery Services.
How far the names are verified is in research-output/SYSTEM_NAMES_CACHE_TRIM_20261024.md (562/562 upstream AGT names,
6/7 own in-game captures); after the NMS Almanac check (2026-10-24, 19/20 identical) the UI label is "name checked".

Copyright (c) 2026 Stuart Coyle & had.sh & GGF   (original nms_namegen: Stuart Coyle, with GoodGuysFree)
MIT License, the notice of hadsh/nms_namegen, reproduced as the licence requires:

  Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
  documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
  rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
  permit persons to whom the Software is furnished to do so, subject to the following conditions:

  The above copyright notice and this permission notice shall be included in all copies or substantial portions of
  the Software.

  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
  THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
  TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
  SOFTWARE.
"""
import gzip
import json
from pathlib import Path

NAME_STATUS = "checked"      # UI chip "name checked" after the NMS Almanac check (was "unverified")
DATA = Path(__file__).with_name("system_names_705_data.json.gz")
_D = None
_MUL = 0x5A76F899
_TINY = 2.3283064370807974e-10
# Corrections confirmed by NMS Almanac and an own in-game capture (upstream alphaset data differs): address16 -> name.
OVERRIDES = {"0000760006606CAB": "Irchol-Luhimo XVII"}
_ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV", "XVI",
          "XVII", "XVIII", "XIX", "XX"]


def _data():
    global _D
    if _D is None:
        d = json.loads(gzip.decompress(DATA.read_bytes()))
        lm = {}
        for k, m in d["letter_map"].items():
            lm[int(k)] = {key: [(p[0], float(p[1:])) for p in s.split(",")[:-1]] for key, s in m.items()}
        _D = (d["alphasets"], lm)
    return _D


class _Rng:
    def __init__(self, seed):
        self.seed = seed

    def _upd(self):
        self.seed = ((self.seed & 0xFFFFFFFF) * _MUL) + (self.seed >> 32)

    def random(self, n):          # 0 .. n-1
        self._upd()
        return ((self.seed & 0xFFFFFFFF) * n) >> 32

    def randi(self):
        self._upd()
        return self.seed & 0xFFFFFFFF


def _chars(rng, aset):
    alphaset = _data()[0][aset & 7]
    r = rng.random(len(alphaset) // 3) * 3
    return alphaset[r:r + 3]


def _insert_vowel(name, rng, index):
    return name[:index] + "aeiou"[rng.random(5)] + name[index:]


def _consecutive_consonants(name):
    run = 0
    for i, ch in enumerate(name):
        if run < 3:
            run = run + 1 if ch not in "aeiou" else 0
        else:
            if ch not in "aeiouy":
                return i - 3
            run = 0
    return -1


def _generate(rng, aset, min_len, max_len):
    lmap = _data()[1]
    alt = False
    name = _chars(rng, aset)
    if rng.randi() & 1:
        alt = True
    register = rng.random(max_len - min_len + 1) + min_len - 3
    add = register
    if register > 0:
        tries = 8
        i = 0
        while i < register:
            weights = lmap[aset].get(name[i:i + 3])
            target = rng.randi() * _TINY
            if weights is None:
                tries -= 1
                i -= 1
                aset = (aset + 1) & 0x08000007
                if aset < 0:
                    aset = -aset
                if tries == 0:
                    if add < 3:
                        break
                    temp = _chars(rng, aset)
                    if name[i + 2] in "aeiou" and temp[0] in "aeiou":
                        name += "'"
                    elif temp[0] not in "aeiou":
                        name += "aeiou"[rng.random(5) & 0xFF]
                    name += temp
                    tries = 1
                    i += 2
                    add -= 3
            else:
                if alt:
                    target *= len(weights) - 1
                    index = int((0.5 if target > 0 else 0.0) + target)
                else:
                    total, j = 0, 0
                    for j in range(len(weights)):
                        total += weights[j][1]
                        if total >= target:
                            break
                    index = j
                name += weights[index][0]
                add -= 1
            if len(name) > 63:
                name = name[:64]
            i += 1
    first, second = name[0], name[1]
    if first not in "aeiou" and second not in "aeiou":
        if first != "s" or second not in "hklmnprtwy":
            if not ((second == "h" and first in "ctw") or (second == "l" and first in "bcfgps")
                    or (second == "r" and first in "bcdfgkpt") or (second == "w" and first in "dgt")
                    or (second == "y" and first in "hmr")):
                name = _insert_vowel(name, rng, 1)
    if len(name) > 1:
        ult, pen = name[-1], name[-2]
        if pen != "g" or ult in "aeiou":
            if ((ult == "b" and pen in "gn") or (ult == "d" and pen in "bdfghkmpst") or (ult == "g" and pen == "l")
                    or (ult == "p" and pen in "bdhkt") or (ult == "r" and pen in "bfg") or (ult == "t" and pen == "g")
                    or (ult == "w" and pen not in "aeiou")):
                name = _insert_vowel(name, rng, len(name) - 1)
    ci = _consecutive_consonants(name)
    if ci != -1:
        ci += rng.random(3) + 1
        name = _insert_vowel(name, rng, ci)
    return name


def system_name(portal_code, galaxy):
    """portal_code: int 0xPSSSYYZZZXXX (the planet digit is ignored); galaxy 0-255 (Euclid = 0)."""
    coords = portal_code & 0xFFFFFFFF
    sysidx = ((portal_code & 0x0FFF00000000) >> 24) | galaxy
    rol = (((coords & 0xFFFF) << 16) | ((coords & 0xFFFF0000) >> 16)) ^ coords ^ sysidx
    rol &= 0xFFFFFFFF
    seed = ((coords + 1) if coords == 0 else coords) * _MUL + rol
    rng = _Rng(seed)
    reg = ((seed & 0xFFFFFFFF) * 5) >> 32
    if reg == 0:
        aset = 2
    elif (reg & 0xFF) < 4:
        aset = (reg & 0xFF) + 2
    else:
        aset = 7
    name = _generate(rng, aset, 6, rng.random(4) + 6).capitalize()
    if len(name) < 8 and rng.random(4) < 2:
        reg = rng.random(5)
        aset = 2 if reg == 0 else (reg + 2 if reg < 4 else 7)
        name = f"{name}-{_generate(rng, aset, 3, 5).capitalize()}"
    if rng.random(10) < 3:
        n = min(rng.random(19) + 1, 19)
        name = f"{name} {_ROMAN[n - 1]}"
    return name


def parse(address, galaxy=None):
    """-> (portal_code int, galaxy int). 16 hex digits = project address16 (000SSSGGYYZZZXXX); 12 = glyphs + galaxy."""
    a = str(address).strip().replace(" ", "").replace(":", "").upper()
    if len(a) == 16:
        g = int(a[6:8], 16)
        if galaxy is not None and int(galaxy) != g:
            raise ValueError(f"galaxy {galaxy} does not match the one inside address {a} ({g})")
        return int(a[3:6] + a[8:], 16), g
    if len(a) == 12:
        if galaxy is None:
            raise ValueError("a 12-digit glyph code needs the galaxy")
        return int(a, 16), int(galaxy)
    raise ValueError(f"expected 12 (glyphs) or 16 (address16) hex digits: {address!r}")


def name(address, galaxy=None):
    """The procedural system name for an address16 or a 12-digit glyph code (+ galaxy), or '' if it cannot be parsed."""
    try:
        portal, g = parse(address, galaxy)
        key = f"000{(portal >> 32) & 0xFFF:03X}{g:02X}{portal & 0xFFFFFFFF:08X}"
        if key in OVERRIDES:
            return OVERRIDES[key]
        return system_name(portal, g)
    except (ValueError, IndexError, KeyError):
        return ""


if __name__ == "__main__":
    import sys
    for arg in sys.argv[1:]:
        print(arg, name(arg))
