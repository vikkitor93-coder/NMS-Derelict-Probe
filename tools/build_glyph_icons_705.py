"""Extract the game's official portal glyph icons (16 BC7 DDS textures) into the viewer as PNGs.

  D:/Orca/venv-texconv/Scripts/python.exe -I tools/build_glyph_icons_705.py

Source: NMSARC.TexUI.pak, textures/ui/frontend/icons/update3/portalsymbol.<0-f>.dds (256x256, DXGI 98 = BC7).
Output: viewer/static/glyphs/<0-f>.png, downscaled to 64x64 (the viewer shows them at ~20 px).
Needs hgpaktool, texture2ddecoder and Pillow (all installed in the venv above).
The PNGs are copies of game assets for local viewing only; they are not committed to the public atlas.
"""
import struct
from pathlib import Path

import texture2ddecoder
from hgpaktool import HGPAKFile
from PIL import Image

PCBANKS = Path("G:/SteamLibrary/steamapps/common/No Man's Sky/GAMEDATA/PCBANKS")
OUT = Path(__file__).resolve().parent.parent / "viewer" / "static" / "glyphs"
MEMBER = "textures/ui/frontend/icons/update3/portalsymbol.{}.dds"
SIZE = 64


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with HGPAKFile(PCBANKS / "NMSARC.TexUI.pak") as pak:
        names = {n.lower(): n for n in pak.filenames}
        wanted = [names[MEMBER.format(c)] for c in "0123456789abcdef"]
        for name, data in pak.extract(wanted):
            h, w = struct.unpack_from("<II", data, 12)
            assert data[84:88] == b"DX10" and struct.unpack_from("<I", data, 128)[0] == 98, name  # BC7
            bgra = texture2ddecoder.decode_bc7(data[148:148 + w * h], w, h)  # top mip only
            img = Image.frombytes("RGBA", (w, h), bgra, "raw", "BGRA").resize((SIZE, SIZE), Image.LANCZOS)
            digit = name.lower().rsplit(".", 2)[1]
            img.save(OUT / f"{digit}.png", optimize=True)
            print("wrote", OUT / f"{digit}.png")


if __name__ == "__main__":
    main()
