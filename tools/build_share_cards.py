"""Build the link-preview cards of the atlas: one small HTML page + one small PNG for every system that has a map.

  python -I tools/build_share_cards.py [ATLAS_DIR] [--base URL] [--no-generate]

For each system with a full map (index map column 1/2/3, see tools/build_atlas_index.py map_rows()) it writes
  s/<ADDRESS16>.html   Open Graph + Twitter meta tags, noindex (config.js "noindex"), and a redirect to the viewer
                       route ../#/d/<ADDRESS16> (crawlers read the tags, people land in the viewer)
  s/<ADDRESS16>.png    800x420 preview: glyph code, preset, counts, the floors' room layout (no game assets, only
                       shapes drawn here with a built-in 5x7 font)
and preview.png (the generic site preview used by systems without a card). Stale cards (systems that left the lists)
are deleted. Standard library only, deterministic (no timestamps, zlib level 9): two runs give the same bytes, and a
file whose bytes did not change is not rewritten.

Base URL = "siteBase" in viewer/static/config.js (the one place to change it), or --base.
For the scanner (after tb.build_bundle in _derived_files):
    import build_share_cards; paths = build_share_cards.build(atlas)    # list of changed repo paths (add/delete)
build(atlas, layouts=None): layouts = optional {address: derelict.json dict}; others come from the generated folders
(or the fast generator, like build_top_bundle). Layouts are checked with build_top_bundle.matches().
"""
import json
import re
import struct
import subprocess
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I leaves the script folder off sys.path
import build_atlas_index as bai  # noqa: E402
import build_top_bundle as btb  # noqa: E402

CONFIG_JS = Path(__file__).resolve().parent.parent / "viewer" / "static" / "config.js"
W, H = 800, 420
CARD_DIR = "s"
CARD_FILE = re.compile(r"^[0-9A-F]{16}\.(html|png)$")

# ---------------------------------------------------------------- config
def read_config(path=CONFIG_JS):
    text = Path(path).read_text(encoding="utf-8")
    m = re.search(r"DV_CONFIG\s*=\s*(\{.*\})\s*;?\s*$", text, re.S)
    return json.loads(m.group(1)) if m else {}


# ---------------------------------------------------------------- 5x7 font (rows are 5-bit masks, MSB = left)
_FONT = {
    "A": "0E 11 11 1F 11 11 11", "B": "1E 11 11 1E 11 11 1E", "C": "0E 11 10 10 10 11 0E", "D": "1E 11 11 11 11 11 1E",
    "E": "1F 10 10 1E 10 10 1F", "F": "1F 10 10 1E 10 10 10", "G": "0E 11 10 17 11 11 0F", "H": "11 11 11 1F 11 11 11",
    "I": "0E 04 04 04 04 04 0E", "J": "07 02 02 02 02 12 0C", "K": "11 12 14 18 14 12 11", "L": "10 10 10 10 10 10 1F",
    "M": "11 1B 15 15 11 11 11", "N": "11 11 19 15 13 11 11", "O": "0E 11 11 11 11 11 0E", "P": "1E 11 11 1E 10 10 10",
    "Q": "0E 11 11 11 15 12 0D", "R": "1E 11 11 1E 14 12 11", "S": "0F 10 10 0E 01 01 1E", "T": "1F 04 04 04 04 04 04",
    "U": "11 11 11 11 11 11 0E", "V": "11 11 11 11 11 0A 04", "W": "11 11 11 15 15 15 0A", "X": "11 11 0A 04 0A 11 11",
    "Y": "11 11 0A 04 04 04 04", "Z": "1F 01 02 04 08 10 1F",
    "0": "0E 11 13 15 19 11 0E", "1": "04 0C 04 04 04 04 0E", "2": "0E 11 01 02 04 08 1F", "3": "1F 02 04 02 01 11 0E",
    "4": "02 06 0A 12 1F 02 02", "5": "1F 10 1E 01 01 11 0E", "6": "06 08 10 1E 11 11 0E", "7": "1F 01 02 04 08 08 08",
    "8": "0E 11 11 0E 11 11 0E", "9": "0E 11 11 0F 01 02 0C",
    " ": "00 00 00 00 00 00 00", ".": "00 00 00 00 00 0C 0C", ",": "00 00 00 00 0C 04 08", ":": "00 0C 0C 00 0C 0C 00",
    "-": "00 00 00 1F 00 00 00", "/": "01 01 02 04 08 10 10", "+": "00 04 04 1F 04 04 00", "(": "02 04 08 08 08 04 02",
    ")": "08 04 02 02 02 04 08", "#": "0A 0A 1F 0A 1F 0A 0A", "%": "18 19 02 04 08 13 03",
}
FONT = {k: [int(x, 16) for x in v.split()] for k, v in _FONT.items()}

# palette index -> RGB
PAL = [(0x0E, 0x11, 0x16), (0x16, 0x1B, 0x22), (0x2A, 0x33, 0x40), (0xE6, 0xED, 0xF3), (0x8B, 0x98, 0xA8), (0x3F, 0xD0, 0xC9),
       (0xE3, 0xA3, 0x3B), (0x5B, 0x8D, 0xEF), (0x4F, 0xBF, 0x73), (0xB0, 0x7B, 0xE8), (0xE0, 0x60, 0x5A), (0x7D, 0x87, 0x94),
       (0x12, 0x16, 0x1C)]
for c in (6, 7, 8, 9, 10, 11):          # dim versions of the room colours (about 45 % over the background), indexes 13..18
    PAL.append(tuple((a * 45 + b * 55) // 100 for a, b in zip(PAL[c], PAL[0])))
BG, PANEL, LINE, TEXT, MUTED, ACCENT = 0, 1, 2, 3, 4, 5
FAMILY = ["end", "hangar", "cargo", "barracks", "medical", "other"]
FAMILY_COLOR = {"cargo": 6, "barracks": 7, "medical": 8, "end": 9, "hangar": 10, "other": 11}


class Canvas:
    def __init__(self, w=W, h=H, bg=BG):
        self.w, self.h = w, h
        self.px = bytearray([bg]) * (w * h)

    def rect(self, x, y, w, h, c):
        x0, x1, y0, y1 = max(0, x), min(self.w, x + w), max(0, y), min(self.h, y + h)
        for yy in range(y0, y1):
            self.px[yy * self.w + x0: yy * self.w + x1] = bytes([c]) * max(0, x1 - x0)

    def text(self, x, y, s, scale=2, c=TEXT):
        for ch in s.upper():
            rows = FONT.get(ch, FONT[" "])
            for r, bits in enumerate(rows):
                for b in range(5):
                    if bits >> (4 - b) & 1:
                        self.rect(x + b * scale, y + r * scale, scale, scale, c)
            x += 6 * scale
        return x

    def png(self):
        raw = b"".join(b"\x00" + bytes(self.px[y * self.w:(y + 1) * self.w]) for y in range(self.h))

        def chunk(tag, data):
            return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        plte = b"".join(bytes(c) for c in PAL)
        return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", self.w, self.h, 8, 3, 0, 0, 0))
                + chunk(b"PLTE", plte) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def family(template):
    t = template or ""
    return ("end" if t == "R_END" else "hangar" if "HANG" in t else "cargo" if "CARG" in t
            else "barracks" if "BARR" in t else "medical" if "MED" in t else "other")


def floors_cells(d):
    """{level: [(col, row, family)]} from the room cell masks (13x13 grid, entrance at the bottom, x mirrored like the viewer)."""
    out = {}
    for room in d.get("rooms", []):
        raw = room["raw_u16_0x00_0x1F"]
        x0, y0, z0, x1, y1, z1 = raw[:6]
        nx, ny, nz = x1 - x0 + 1, y1 - y0 + 1, z1 - z0 + 1
        mask = raw[12] | raw[13] << 16 | raw[14] << 32 | raw[15] << 48
        fam = family(room.get("template_name"))
        for x in range(nx):
            for y in range(ny):
                for z in range(nz):
                    if mask >> (z + nz * (y + ny * x)) & 1:
                        out.setdefault(y0 + y, []).append((12 - (x0 + x), 12 - (z0 + z), fam))
    return out


def pretty(glyphs):
    return f"{glyphs[0]} {glyphs[1:4]} {glyphs[4:6]} {glyphs[6:9]} {glyphs[9:]}"


def card_png(row, d):
    cv = Canvas()
    cv.rect(0, 0, W, 6, ACCENT)
    cv.text(24, 24, "NMS DERELICT ATLAS", 2, MUTED)
    cv.text(24, 56, row["glyphs"], 4, TEXT)
    cv.text(24, 100, row["preset"].replace("_", " "), 3, ACCENT)
    kinds = int(row["map_kind"])
    y = 148
    for label, val in (("CRATES", row["crates"]), ("FOOTLOCKERS", row["footlockers"]), ("FRIGATE MODULES", row.get("frigate_modules") or "-"),
                       ("ROOMS", row["rooms"])):
        x = cv.text(24, y, str(val), 4, TEXT)
        cv.text(x + 12, y + 8, label, 2, MUTED)
        y += 44
    tags = ([("TOP 100 BY CRATES", 6)] if kinds & 1 else []) + ([("TOP 100 BY MODULES", 8)] if kinds & 2 else [])
    for k, (t, c) in enumerate(tags):
        cv.text(24, 332 + k * 26, t, 2, c)
    cv.text(24, 392, "UNOFFICIAL FAN PROJECT", 1, MUTED)
    cv.text(24, 404, "NOT AFFILIATED WITH HELLO GAMES", 1, MUTED)
    # floors, right side (x 400..776, y 24..396)
    fl = floors_cells(d)
    levels = sorted(fl, reverse=True)           # top deck first, like the viewer
    n = max(1, len(levels))
    cols = 1 if n == 1 else 2 if n <= 4 else 3
    rows_n = -(-n // cols)
    area_w, area_h, gap = 376, 372, 12
    tile = min((area_w - (cols - 1) * gap) // cols, (area_h - (rows_n - 1) * gap) // rows_n)
    cs = max(2, tile // 13)
    side = cs * 13
    for k, lv in enumerate(levels):
        ox = 400 + (k % cols) * (side + gap)
        oy = 24 + (k // cols) * (side + gap)
        cv.rect(ox, oy, side, side, 12)
        for col, rw, fam in fl[lv]:
            cv.rect(ox + col * cs, oy + rw * cs, cs - 1, cs - 1, FAMILY_COLOR[fam] + 7)   # dim colour index = base + 7
    return cv.png()


def generic_png():
    cv = Canvas()
    cv.rect(0, 0, W, 6, ACCENT)
    cv.text(40, 120, "NMS DERELICT", 7, TEXT)
    cv.text(40, 184, "ATLAS", 7, ACCENT)
    cv.text(40, 270, "PREDICTED DERELICT FREIGHTER LAYOUTS", 2, MUTED)
    cv.text(40, 296, "NO MANS SKY 7.05 - EUCLID - CRATES, FOOTLOCKERS, MAPS", 2, MUTED)
    cv.text(40, 380, "UNOFFICIAL FAN PROJECT - NOT AFFILIATED WITH HELLO GAMES", 1, MUTED)
    x0 = 480
    demo = [(0, 0, 6), (1, 0, 6), (2, 0, 7), (2, 1, 7), (3, 1, 8), (3, 2, 8), (1, 2, 9), (0, 1, 10)]
    for gx, gy, c in demo:
        cv.rect(x0 + gx * 56, 40 + gy * 56 + 380 - 380, 52, 52, c + 7)
    return cv.png()


def page(row, kinds, base, noindex):
    a, g = row["address"], row["glyphs"]
    lists = " and ".join(n for bit, n in ((1, "crates"), (2, "frigate modules")) if kinds & bit)
    desc = (f"Derelict {pretty(g)}: {row['preset']}, {row['crates']} salvage crates, {row['footlockers']} footlockers, "
            f"{row.get('frigate_modules') or 0} predicted frigate modules, {row['rooms']} rooms. Top 100 by {lists}. Full map and 3D view.")
    title = f"Derelict {pretty(g)} - NMS Derelict Atlas"
    url, img = f"{base}{CARD_DIR}/{a}.html", f"{base}{CARD_DIR}/{a}.png"
    q = lambda s: s.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")
    target = f"../#/d/{a}"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{q(title)}</title>
{'<meta name="robots" content="noindex">' if noindex else ''}
<meta name="description" content="{q(desc)}">
<meta property="og:type" content="website"><meta property="og:site_name" content="NMS Derelict Atlas">
<meta property="og:title" content="{q(title)}"><meta property="og:description" content="{q(desc)}">
<meta property="og:url" content="{q(url)}"><meta property="og:image" content="{q(img)}">
<meta property="og:image:width" content="{W}"><meta property="og:image:height" content="{H}">
<meta property="og:image:alt" content="Room layout of derelict {g}">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{q(title)}">
<meta name="twitter:description" content="{q(desc)}"><meta name="twitter:image" content="{q(img)}">
<meta http-equiv="refresh" content="0; url={target}">
</head><body><p><a href="{target}">Open derelict {g} in the viewer</a></p>
<script>location.replace("{target}")</script></body></html>
"""


def write_if_changed(path, data):
    if path.exists() and path.read_bytes() == data:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return True


def build(atlas, layouts=None, base=None, generate=True, rows=None):
    """Write/prune the cards under <atlas>/s and <atlas>/preview.png. Returns the changed repo paths (Path, relative)."""
    atlas = Path(atlas)
    cfg = read_config()
    base = (base or cfg.get("siteBase") or "").rstrip("/") + "/"
    noindex = bool(cfg.get("noindex", True))
    rows = rows if rows is not None else bai.systems(atlas)
    kinds = bai.map_kinds(rows)
    layouts = dict(layouts or {})
    changed, keep = [], set()
    for row in bai.map_rows(rows):
        addr = bai.address(row)
        row = dict(row, address=addr, map_kind=kinds[(row["galaxy"], row["glyphs"])])
        d = layouts.get(addr) or btb.find_layout(addr, btb.GENERATED)
        if d is None and generate:
            subprocess.run([sys.executable, "-I", str(btb.FAST_GEN), addr], check=True, capture_output=True, text=True, timeout=1800)
            d = btb.find_layout(addr, btb.GENERATED)
        if d is None or not btb.matches(d, row):
            raise RuntimeError(f"{addr}: no matching layout for its card")
        files = {f"{addr}.png": card_png(row, d), f"{addr}.html": page(row, row["map_kind"], base, noindex).encode("utf-8")}
        for name, data in files.items():
            keep.add(name)
            if write_if_changed(atlas / CARD_DIR / name, data):
                changed.append(Path(CARD_DIR) / name)
    sdir = atlas / CARD_DIR
    if sdir.exists():
        for p in sorted(sdir.iterdir()):
            if CARD_FILE.match(p.name) and p.name not in keep:
                p.unlink()
                changed.append(Path(CARD_DIR) / p.name)
    if write_if_changed(atlas / "preview.png", generic_png()):
        changed.append(Path("preview.png"))
    return changed


def main():
    args = sys.argv[1:]
    generate = "--no-generate" not in args
    args = [a for a in args if a != "--no-generate"]
    base = None
    if "--base" in args:
        i = args.index("--base")
        base = args[i + 1]
        del args[i:i + 2]
    atlas = Path(args[0] if args else "D:/Orca/NMS-Derelict-Atlas")
    ch = build(atlas, base=base, generate=generate)
    files = [p for p in (atlas / CARD_DIR).glob("*") if CARD_FILE.match(p.name)] if (atlas / CARD_DIR).exists() else []
    size = sum(p.stat().st_size for p in files) + (atlas / "preview.png").stat().st_size
    print(f"{atlas}: {len(files)} card files + preview.png, {size / 1024:.1f} KB; {len(ch)} written or deleted")


if __name__ == "__main__":
    main()
