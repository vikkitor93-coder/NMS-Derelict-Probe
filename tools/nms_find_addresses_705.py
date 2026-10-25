"""Find the memory addresses the live minimap reader needs in a given NMS.exe (static, stdlib only, read-only).

    python -I tools/nms_find_addresses_705.py [path\\to\\NMS.exe] [--json]

What it finds: the RVA of the global cGcApplication object, and the offset inside it of the pointer to the big
cGcApplication::Data block (7.05: 0x6E8D6D0 and 0x38). The offsets inside that block (simulation, universe address, player
position) do not move with every update, so they are taken from the last verified build (live_position_705.KNOWN_BUILDS)
and then checked while the game runs (live_position_705.LiveReader plausibility checks + --verify-glyphs).

How: cGcApplication::Construct is located by the same byte signature NMS.py uses; the object is the `lea rcx,[rip+x]` just
before its call to cTkFSM::Construct, and the Data pointer is the first store into the object right after an allocation call.
If the signature no longer matches, a weaker search over all callers of cTkFSM::Construct is tried and reported as such.

Tested only on NMS 7.05 (13D5060D): it reproduces the hand-found values. On another build treat the result as a candidate
until the live reader verifies it.
"""
from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from pathlib import Path

SIG_APP_CONSTRUCT = "40 57 48 83 EC ? 33 FF 48 89 5C 24 ? 83 3D"                 # cGcApplication::Construct (NMS.py)
SIG_FSM_CONSTRUCT = "48 89 5C 24 ? 48 89 6C 24 ? 48 89 74 24 ? 57 48 83 EC ? 33 ED 48 89 51"   # cTkFSM::Construct (NMS.py)
SCAN = 0x600            # bytes of cGcApplication::Construct to look through
MIN_ALLOC = 0x400000    # the Data block is about 10 MB (7.05: 0x95F210)


class Pe:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self.data = Path(path).read_bytes()
        d = self.data
        if d[:2] != b"MZ":
            raise ValueError("not a PE file")
        nt = struct.unpack_from("<I", d, 0x3C)[0]
        if d[nt:nt + 4] != b"PE\0\0":
            raise ValueError("bad PE header")
        nsec, = struct.unpack_from("<H", d, nt + 6)
        optsize, = struct.unpack_from("<H", d, nt + 20)
        opt = nt + 24
        if struct.unpack_from("<H", d, opt)[0] != 0x20B:
            raise ValueError("not a 64-bit PE")
        self.image_base, = struct.unpack_from("<Q", d, opt + 24)
        self.sections = []
        so = opt + optsize
        for i in range(nsec):
            name = d[so + i * 40: so + i * 40 + 8].rstrip(b"\0").decode("latin1")
            vsize, va, rawsize, rawptr = struct.unpack_from("<IIII", d, so + i * 40 + 8)
            self.sections.append((name, va, vsize, rawptr, rawsize))
        self.text = next(s for s in self.sections if s[0] == ".text")

    def off(self, rva: int) -> int | None:
        for _n, va, vs, rp, rs in self.sections:
            if va <= rva < va + min(vs, rs or vs):
                return rp + rva - va
        return None

    def rva(self, off: int) -> int | None:
        for _n, va, vs, rp, rs in self.sections:
            if rp <= off < rp + rs:
                return va + off - rp
        return None

    def text_bytes(self) -> tuple[bytes, int]:
        _n, va, _vs, rp, rs = self.text
        return self.data[rp:rp + rs], va

    def in_image(self, rva: int) -> bool:
        return any(va <= rva < va + vs for _n, va, vs, _rp, _rs in self.sections)


def sig_regex(sig: str):
    return re.compile(b"".join(b"." if t == "?" else re.escape(bytes([int(t, 16)])) for t in sig.split()), re.S)


def find_sig(pe: Pe, sig: str) -> list[int]:
    text, va = pe.text_bytes()
    return [va + m.start() for m in sig_regex(sig).finditer(text)]


def rel_targets(pe: Pe, fn_rva: int, size: int):
    """Yield (offset_in_function, kind, target_rva) for call rel32, lea r64,[rip+x] and mov [rip+x],r64 / mov r64,[rip+x]."""
    base = pe.off(fn_rva)
    b = pe.data[base:base + size]
    for i in range(len(b) - 7):
        if b[i] == 0xE8:
            yield i, "call", fn_rva + i + 5 + struct.unpack_from("<i", b, i + 1)[0], None
        if b[i] in (0x48, 0x4C) and b[i + 2] & 0xC7 == 0x05 and b[i + 1] in (0x8D, 0x89, 0x8B):
            reg = ((b[i] & 4) << 1) | ((b[i + 2] >> 3) & 7)
            kind = {0x8D: "lea", 0x89: "store", 0x8B: "load"}[b[i + 1]]
            yield i, kind, fn_rva + i + 7 + struct.unpack_from("<i", b, i + 3)[0], reg


def find_app(pe: Pe) -> dict:
    notes: list[str] = []
    fsm = find_sig(pe, SIG_FSM_CONSTRUCT)
    cons = find_sig(pe, SIG_APP_CONSTRUCT)
    res = {"found": False, "method": None, "notes": notes,
           "fsm_construct": [hex(x) for x in fsm], "app_construct": [hex(x) for x in cons]}
    if len(fsm) != 1:
        notes.append(f"cTkFSM::Construct signature matched {len(fsm)} places (expected 1)")
    if len(cons) != 1:
        notes.append(f"cGcApplication::Construct signature matched {len(cons)} places (expected 1)")
    for fn in cons:
        ev = list(rel_targets(pe, fn, SCAN))
        calls = [e for e in ev if e[1] == "call" and e[2] in fsm]
        if not calls:
            continue
        ci = calls[0][0]
        leas = [e for e in ev if e[1] == "lea" and e[3] == 1 and 0 < ci - e[0] <= 0x40]   # lea rcx before the call
        if not leas:
            notes.append("no lea rcx before the cTkFSM::Construct call")
            continue
        app = leas[-1][2]
        if not pe.in_image(app):
            continue
        stores = [e for e in ev if e[1] == "store" and app <= e[2] < app + 0x100]
        # the allocation result: a store into the object right after a call (xor edx,edx / mov in between)
        alloc = [s for s in stores if any(c[1] == "call" and 0 < s[0] - c[0] <= 12 for c in ev)]
        res.update({"found": True, "method": "signature", "app_rva": app, "app_construct_rva": fn})
        if len(alloc) == 1:
            res.update({"data_ptr": alloc[0][2] - app, "data_ptr_confidence": "unique store after a call"})
        else:
            cands = sorted({s[2] - app for s in alloc or stores})
            res.update({"data_ptr": cands[0] if cands else 0x38, "data_ptr_candidates": cands,
                        "data_ptr_confidence": "ambiguous: verify against the Data block size at run time"})
            notes.append(f"{len(alloc)} allocation-like stores into the object; candidates {[hex(c) for c in cands]}")
        return res
    # weaker fallback: every caller of cTkFSM::Construct whose function also makes a big-immediate allocation
    notes.append("signature path failed; trying all callers of cTkFSM::Construct")
    text, va = pe.text_bytes()
    cand = []
    for f in fsm[:1]:
        for m in re.finditer(b"\xE8", text):
            i = m.start()
            if i + 5 <= len(text) and va + i + 5 + struct.unpack_from("<i", text, i + 1)[0] == f:
                win = text[max(0, i - 0x60):i]
                j = win.rfind(b"\x48\x8D\x0D")
                if j >= 0 and j + 7 <= len(win):
                    app = va + max(0, i - 0x60) + j + 7 + struct.unpack_from("<i", win, j + 3)[0]
                    if pe.in_image(app):
                        cand.append((va + i, app))
    res["fallback_callers"] = [(hex(c), hex(a)) for c, a in cand]
    if cand:
        res.update({"found": True, "method": "fallback (unverified, several candidates possible)", "app_rva": cand[0][1],
                    "data_ptr": 0x38, "data_ptr_confidence": "assumed 0x38 (7.05)"})
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("exe", nargs="?", help="NMS.exe (default: the installed game)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    exe = a.exe
    if not exe:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "minimap"))
        import settings
        found = settings.find_nms_exe()
        if not found:
            raise SystemExit("NMS.exe not found; pass its path")
        exe = str(found)
    pe = Pe(exe)
    r = find_app(pe)
    r["exe"] = exe
    if a.json:
        print(json.dumps(r, indent=1, default=lambda o: hex(o) if isinstance(o, int) else str(o)))
    else:
        print(f"exe: {exe}")
        if r["found"]:
            print(f"cGcApplication object : RVA {r['app_rva']:#x}  ({r['method']})")
            print(f"Data pointer          : object + {r['data_ptr']:#x}  ({r.get('data_ptr_confidence')})")
        else:
            print("NOT FOUND")
        for n in r["notes"]:
            print("note:", n)
    return 0 if r["found"] else 1


if __name__ == "__main__":
    sys.exit(main())
