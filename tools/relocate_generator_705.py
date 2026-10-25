"""Find every hard-coded NMS.exe address of the derelict chain in ANOTHER NMS.exe (static, read-only, stdlib only).

    python -I tools/relocate_generator_705.py <new NMS.exe> [--label 7.06] [--out DIR] [--extract] [--json]
    python -I tools/relocate_generator_705.py --self-test          7.05 exe against itself + a perturbed copy

What it finds (tools/build_profile_705.ADDRESSES_705 lists all 60, by role):
  native  the derelict writer FUN_14039E5E0, the 9 engine functions native_writer_705.py patches, the global G
  diag    the writer callees the Unicorn emulator only counts
  logic   game functions the Python predictors re-implement (seed/preset, end reward, crate loot) + their constants
  site    instructions inside logic functions (resolved through their function)
  poi     Shipwright's star-system generator (Shipwright re-finds these itself by signature; reported here)
How:
  1. functions = the exe's .pdata (x64 unwind table): exact start and end of every function.
  2. each 7.05 function is decoded with a small x64 length decoder; rel32 call/jmp/jcc targets, RIP-relative
     displacements and in-image imm64 are wildcarded. The first 64 bytes become a signature searched in the new
     .text; candidates are compared on the whole masked body ("body identical" = same code modulo relocation).
  3. call graph: from the writer, the n-th call of a 7.05 function maps to the n-th call of its new counterpart, which
     places the patched engine functions even when their bodies are generic (many are a few instructions).
  4. data (G, the 2^-32 double, the seed-override global): the same instruction ordinal of a function that references
     it in 7.05; constants are compared byte for byte.
Confidence per address: high (signature AND call graph agree, body identical), medium (one method, body identical),
low (found but the body changed: the Python port / patch must be re-checked by hand), none.
Output: <out>/address_map.json + build.json (a build profile for tools/build_profile_705.py); default out folder
D:/Orca/NMS-Derelict-Probe-analysis/builds/<label or sha8>/ (never the 7.05 folder). --extract also re-extracts the game
tables and scene assets the generator needs from that game's PAKs into <out>/data/ (tools/extract_build_data_705.py).
"""
from __future__ import annotations

import argparse
import bisect
import difflib
import hashlib
import json
import re
import struct
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import build_profile_705 as BP  # noqa: E402

SIG_LEN = 64
CALLGRAPH_DEPTH = 6


# ------------------------------------------------------------------------------------------------------------- PE
class Image:
    def __init__(self, path, data: bytes | None = None):
        self.path = str(path)
        self.data = d = data if data is not None else Path(path).read_bytes()
        if d[:2] != b"MZ":
            raise ValueError("not a PE file")
        nt = struct.unpack_from("<I", d, 0x3C)[0]
        nsec, = struct.unpack_from("<H", d, nt + 6)
        optsize, = struct.unpack_from("<H", d, nt + 20)
        opt = nt + 24
        self.base, = struct.unpack_from("<Q", d, opt + 24)
        self.size_of_image, = struct.unpack_from("<I", d, opt + 56)
        ndirs, = struct.unpack_from("<I", d, opt + 108)
        dirs = [struct.unpack_from("<II", d, opt + 112 + 8 * i) for i in range(ndirs)]
        self.sections = []
        so = opt + optsize
        for i in range(nsec):
            name = d[so + i * 40: so + i * 40 + 8].rstrip(b"\0").decode("latin1")
            vsize, va, rawsize, rawptr = struct.unpack_from("<IIII", d, so + i * 40 + 8)
            self.sections.append((name, va, vsize, rawptr, rawsize))
        t = next(s for s in self.sections if s[0] == ".text")
        self.text_rva, self.text_raw, self.text_size = t[1], t[3], min(t[2], t[4])
        self.text = memoryview(d)[self.text_raw:self.text_raw + self.text_size]
        prva, psize = dirs[3] if len(dirs) > 3 else (0, 0)
        po = self.off(prva) if prva else None
        funcs = {}
        if po is not None:
            for b, e, _u in struct.iter_unpack("<III", d[po:po + psize - psize % 12]):
                if b and e > b and (b not in funcs or funcs[b] < e):
                    funcs[b] = e
        self.fstart = sorted(funcs)
        self.fend = [funcs[b] for b in self.fstart]

    def off(self, rva):
        for _n, va, vs, rp, rs in self.sections:
            if va <= rva < va + max(vs, rs):
                return rp + rva - va if rva - va < rs else None
        return None

    def va(self, rva):
        return self.base + rva

    def rva(self, va):
        return va - self.base

    def in_image(self, va):
        return self.base <= va < self.base + self.size_of_image

    def bytes_at(self, va, n):
        o = self.off(self.rva(va))
        return bytes(self.data[o:o + n]) if o is not None else b""

    def section_of(self, va):
        r = self.rva(va)
        for n, s_va, vs, _rp, _rs in self.sections:
            if s_va <= r < s_va + vs:
                return n
        return None

    def function(self, va):
        """(start_va, end_va) of the .pdata function containing va, or None."""
        r = self.rva(va)
        i = bisect.bisect_right(self.fstart, r) - 1
        if i >= 0 and self.fstart[i] <= r < self.fend[i]:
            return self.va(self.fstart[i]), self.va(self.fend[i])
        return None

    def is_func_start(self, va):
        r = self.rva(va)
        i = bisect.bisect_left(self.fstart, r)
        return i < len(self.fstart) and self.fstart[i] == r


# ------------------------------------------------------------------------------------------- x64 length decoder
_MODRM1 = set(range(0x00, 0x04)) | set(range(0x08, 0x0C)) | set(range(0x10, 0x14)) | set(range(0x18, 0x1C)) | \
    set(range(0x20, 0x24)) | set(range(0x28, 0x2C)) | set(range(0x30, 0x34)) | set(range(0x38, 0x3C)) | \
    {0x63, 0x69, 0x6B} | set(range(0x80, 0x90)) | {0xC0, 0xC1, 0xC6, 0xC7} | set(range(0xD0, 0xD4)) | \
    set(range(0xD8, 0xE0)) | {0xF6, 0xF7, 0xFE, 0xFF}
_IB1 = {0x04, 0x0C, 0x14, 0x1C, 0x24, 0x2C, 0x34, 0x3C, 0x6A, 0x6B, 0x80, 0x83, 0xA8, 0xC0, 0xC1, 0xC6, 0xCD,
        0xE4, 0xE5, 0xE6, 0xE7} | set(range(0xB0, 0xB8))
_IZ1 = {0x05, 0x0D, 0x15, 0x1D, 0x25, 0x2D, 0x35, 0x3D, 0x68, 0x69, 0x81, 0xA9, 0xC7}
_REL8 = set(range(0x70, 0x80)) | {0xE0, 0xE1, 0xE2, 0xE3, 0xEB}
_NOMODRM0F = {0x05, 0x06, 0x07, 0x08, 0x09, 0x0B, 0x0E, 0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x37, 0x77, 0xA0, 0xA1,
              0xA2, 0xA8, 0xA9, 0xAA} | set(range(0xC8, 0xD0))
_IB0F = {0x70, 0x71, 0x72, 0x73, 0xA4, 0xAC, 0xBA, 0xC2, 0xC4, 0xC5, 0xC6}
_PREFIX = {0x66, 0x67, 0xF2, 0xF3, 0xF0, 0x2E, 0x36, 0x3E, 0x26, 0x64, 0x65}


def _modrm(b, i):
    m = b[i]
    i += 1
    mod, rm, reg = m >> 6, m & 7, (m >> 3) & 7
    rip = None
    if mod != 3:
        if rm == 4:
            sib = b[i]
            i += 1
            if mod == 0 and (sib & 7) == 5:
                i += 4
        if mod == 0 and rm == 5:
            rip = i
            i += 4
        elif mod == 1:
            i += 1
        elif mod == 2:
            i += 4
    return i, rip, reg


def decode(b, i):
    """One instruction at b[i]: (length, kind, field_pos, field_len). kind: call/jmp/jcc (rel32), rip (disp32),
    imm64, or None. field_pos is relative to the instruction start."""
    s = i
    p66 = False
    while b[i] in _PREFIX:
        p66 |= b[i] == 0x66
        i += 1
    rex = 0
    if 0x40 <= b[i] <= 0x4F:
        rex = b[i]
        i += 1
    c = b[i]
    iz = 2 if p66 else 4
    if c in (0xC4, 0xC5, 0x62):                     # VEX / EVEX (always in 64-bit mode)
        if c == 0xC5:
            mp, i = 1, i + 2
        elif c == 0xC4:
            mp, i = b[i + 1] & 0x1F, i + 3
        else:
            mp, i = b[i + 1] & 0x3, i + 4
        op = b[i]
        i += 1
        if mp == 1 and op == 0x77:
            return i - s, None, 0, 0
        i, rip, _ = _modrm(b, i)
        i += 1 if (mp == 3 or (mp == 1 and op in _IB0F)) else 0
        return i - s, ("rip" if rip is not None else None), (rip - s if rip is not None else 0), 4
    i += 1
    if c == 0x0F:
        c2 = b[i]
        i += 1
        if c2 == 0x38 or c2 == 0x3A:
            i += 1
            i, rip, _ = _modrm(b, i)
            i += 1 if c2 == 0x3A else 0
        elif 0x80 <= c2 <= 0x8F:
            return i + 4 - s, "jcc", i - s, 4
        elif c2 in _NOMODRM0F:
            return i - s, None, 0, 0
        else:
            i, rip, _ = _modrm(b, i)
            i += 1 if c2 in _IB0F else 0
        return i - s, ("rip" if rip is not None else None), (rip - s if rip is not None else 0), 4
    if c == 0xE8 or c == 0xE9:
        return i + 4 - s, ("call" if c == 0xE8 else "jmp"), i - s, 4
    if c in _REL8:
        return i + 1 - s, None, 0, 0
    if 0xB8 <= c <= 0xBF:
        if rex & 8:
            return i + 8 - s, "imm64", i - s, 8
        return i + iz - s, None, 0, 0
    if 0xA0 <= c <= 0xA3:
        return i + 8 - s, "imm64", i - s, 8
    if c in (0xC2, 0xCA):
        return i + 2 - s, None, 0, 0
    if c == 0xC8:
        return i + 3 - s, None, 0, 0
    rip = None
    if c in _MODRM1:
        i, rip, reg = _modrm(b, i)
        if c == 0xF6 and reg in (0, 1):
            i += 1
        elif c == 0xF7 and reg in (0, 1):
            i += iz
    if c in _IB1:
        i += 1
    elif c in _IZ1:
        i += iz
    return i - s, ("rip" if rip is not None else None), (rip - s if rip is not None else 0), 4


class Func:
    """Decoded function: instruction list [(va, len, kind, target)], masked body bytes, call targets in order."""

    def __init__(self, img: Image, start: int, end: int | None = None):
        self.img, self.start = img, start
        if end is None:
            f = img.function(start)
            end = f[1] if f and f[0] == start else start + 0x200
        self.end = end
        o = img.off(img.rva(start))
        raw = img.data[o:o + (end - start)]
        b = raw + b"\x90" * 16
        self.insns, masked = [], bytearray(raw)
        mask = bytearray(len(raw))
        i = 0
        while i < len(raw):
            try:
                n, kind, fp, fl = decode(b, i)
            except IndexError:
                n, kind = 1, None
            if n <= 0:
                n, kind = 1, None
            tgt = None
            if kind in ("call", "jmp", "jcc", "rip"):
                disp = struct.unpack_from("<i", b, i + fp)[0]
                tgt = start + i + n + disp
            elif kind == "imm64":
                tgt = struct.unpack_from("<Q", b, i + fp)[0]
                if not img.in_image(tgt):
                    kind, tgt = None, None
            if kind:
                for k in range(fp, fp + fl):
                    if i + k < len(raw):
                        masked[i + k] = 0
                        mask[i + k] = 1
            self.insns.append((start + i, n, kind, tgt))
            i += n
        self.masked, self.mask = bytes(masked), bytes(mask)
        self.calls = [t for _v, _n, k, t in self.insns if k == "call"]
        self.digest = hashlib.sha1(self.masked + self.mask).hexdigest()

    def signature(self, n=SIG_LEN, skip=0):
        a, b = skip, min(len(self.masked), skip + n)
        return re.compile(b"".join(b"." if self.mask[i] else re.escape(self.masked[i:i + 1]) for i in range(a, b)), re.S)

    def tokens(self):
        return [(self.masked[v - self.start:v - self.start + n]) for v, n, _k, _t in self.insns]

    def similarity(self, other) -> float:
        a, b = self.tokens(), other.tokens()
        if len(a) * len(b) > 4_000_000:
            return 1.0 if self.digest == other.digest else 0.0
        return round(difflib.SequenceMatcher(None, a, b, autojunk=False).ratio(), 4)


# --------------------------------------------------------------------------------------------------------- matching
class Relocator:
    def __init__(self, old: Image, new: Image):
        self.old, self.new = old, new
        self.cache_old, self.cache_new = {}, {}

    def fo(self, va):
        if va not in self.cache_old:
            self.cache_old[va] = Func(self.old, va)
        return self.cache_old[va]

    def fn(self, va):
        if va not in self.cache_new:
            self.cache_new[va] = Func(self.new, va)
        return self.cache_new[va]

    def by_signature(self, va):
        """Candidate starts in the new exe whose masked first bytes match; prefers .pdata function starts."""
        f = self.fo(va)
        out = []
        for n, skip in ((SIG_LEN, 0), (32, 0), (24, 0)):
            if len(f.masked) < 8:
                break
            rx = f.signature(n, skip)
            hits = [self.new.va(self.new.text_rva + m.start()) for m in rx.finditer(self.new.text)]
            starts = [h for h in hits if self.new.is_func_start(h)] or hits
            if starts:
                out = starts
                if len(starts) <= 64:
                    break
        return out

    def callgraph(self, root_old, root_new, depth=CALLGRAPH_DEPTH, limit=4000):
        """{old_va: (new_va, path)} by following call ordinals from the root pair (only where call counts agree)."""
        found = {root_old: (root_new, "root")}
        frontier = [(root_old, root_new, 0)]
        while frontier and len(found) < limit:
            o, n, d = frontier.pop(0)
            if d >= depth:
                continue
            fo, fn = self.fo(o), self.fn(n)
            if len(fo.calls) != len(fn.calls):
                continue
            for k, (co, cn) in enumerate(zip(fo.calls, fn.calls)):
                if co in found or not self.old.is_func_start(co):
                    continue
                found[co] = (cn, f"{found[o][1]}>{k}")
                frontier.append((co, cn, d + 1))
        return found

    def body(self, old_va, new_va):
        a, b = self.fo(old_va), self.fn(new_va)
        same = a.digest == b.digest and len(a.masked) == len(b.masked)
        return same, (1.0 if same else a.similarity(b))


def relocate(old: Image, new: Image, notes: list) -> dict:
    R = Relocator(old, new)
    addrs = BP.ADDRESSES_705
    res = {}

    def put(key, new_va, conf, method, extra=None):
        old_va, role, used_by, what = addrs[key]
        res[key] = {"old_va": hex(old_va), "va": hex(new_va) if new_va is not None else None, "role": role,
                    "confidence": conf, "method": method, "used_by": used_by, "what": what, **(extra or {})}

    # 1. the writer by signature
    w_old = addrs["writer"][0]
    cands = R.by_signature(w_old)
    exact = [c for c in cands if R.body(w_old, c)[0]]
    w_new = (exact or cands or [None])[0]
    if w_new is None:
        notes.append("writer signature not found: nothing else can be placed by call graph")
    else:
        same, sim = R.body(w_old, w_new)
        put("writer", w_new, "high" if same and len(exact) == 1 else ("medium" if len(cands) == 1 else "low"),
            f"signature ({len(cands)} candidate(s), {len(exact)} with identical body)", {"body_identical": same, "similarity": sim})
    graph = R.callgraph(w_old, w_new) if w_new else {}

    # 2. functions: call graph from the writer and/or signature
    for key, (old_va, role, _u, _w) in addrs.items():
        if key == "writer" or key.startswith("data.") or role == "site":
            continue
        via_graph = graph.get(old_va, (None, None))[0]
        sig = R.by_signature(old_va)
        sig_exact = [c for c in sig if R.body(old_va, c)[0]]
        methods, pick = [], None
        if via_graph is not None:
            methods.append(f"call graph {graph[old_va][1]}")
            pick = via_graph
        if len(sig_exact) == 1:
            methods.append("signature + identical body")
            pick = pick if pick is not None else sig_exact[0]
        elif len(sig) == 1:
            methods.append("signature (body differs)")
            pick = pick if pick is not None else sig[0]
        elif sig:
            methods.append(f"signature ambiguous ({len(sig)} hits, {len(sig_exact)} identical)")
        if pick is None:
            put(key, None, "none", "; ".join(methods) or "no signature hit")
            continue
        same, sim = R.body(old_va, pick)
        agree = via_graph is not None and (pick in sig_exact or pick in sig)
        if same and (agree or (via_graph is None and len(sig_exact) == 1) or (via_graph is not None and not sig)):
            conf = "high" if agree or len(sig_exact) == 1 else "medium"
        elif same:
            conf = "medium"
        else:
            conf = "low"
        if via_graph is not None and sig_exact and via_graph not in sig_exact and len(sig_exact) == 1:
            conf, methods = "low", methods + [f"CONFLICT: signature says {hex(sig_exact[0])}"]
        put(key, pick, conf, "; ".join(methods), {"body_identical": same, "similarity": sim})

    # 3. sites: same offset inside the relocated function (only meaningful when the body is identical)
    for key, (old_va, role, _u, _w) in addrs.items():
        if role != "site":
            continue
        f = old.function(old_va)
        parent = next((k for k, v in res.items() if v.get("va") and int(v["old_va"], 16) == (f[0] if f else -1)), None)
        if f is None:
            put(key, None, "none", "no containing .pdata function in 7.05")
            continue
        fva = f[0]
        if parent is None:     # containing function is not itself a target: relocate it now
            sig = R.by_signature(fva)
            ex = [c for c in sig if R.body(fva, c)[0]]
            nva = (ex or sig or [None])[0]
            same = bool(ex) and len(ex) == 1
        else:
            nva, same = int(res[parent]["va"], 16), res[parent].get("body_identical", False)
        if nva is None:
            put(key, None, "none", f"containing function {hex(fva)} not found")
            continue
        put(key, nva + (old_va - fva), "high" if same else "low", f"offset {old_va - fva:#x} in function {hex(fva)} -> {hex(nva)}",
            {"body_identical": same})

    # 4. data: same instruction ordinal in a relocated function that references it in 7.05
    resolved = {int(v["old_va"], 16): int(v["va"], 16) for v in res.values() if v.get("va") and v["role"] != "site"}
    resolved.update({o: n for o, (n, _p) in graph.items()})
    for key, (old_va, role, _u, _w) in addrs.items():
        if not key.startswith("data."):
            continue
        hits = []
        for o_va, n_va in resolved.items():
            fo = R.fo(o_va)
            for k, (_v, _n, kind, t) in enumerate(fo.insns):
                if kind in ("rip", "imm64") and t is not None and old_va <= t < old_va + 0x40:
                    fnw = R.fn(n_va)
                    if k < len(fnw.insns) and fnw.insns[k][2] == kind and fnw.insns[k][3] is not None:
                        hits.append((fnw.insns[k][3] - (t - old_va), o_va, k))
            if len(hits) >= 6:
                break
        vals = sorted({h[0] for h in hits})
        if not hits:
            put(key, None, "none", "no reference found in the relocated functions")
            continue
        new_va = max(vals, key=lambda v: sum(1 for h in hits if h[0] == v))
        conf = "high" if len(vals) == 1 and len(hits) >= 2 else ("medium" if len(vals) == 1 else "low")
        extra = {"references": [[hex(h[1]), h[2], hex(h[0])] for h in hits[:6]]}
        ob, nb = old.bytes_at(old_va, 16), new.bytes_at(new_va, 16)
        if old.section_of(old_va) == ".rdata":
            extra["constant_identical"] = ob == nb
            if ob != nb:
                conf = "low"
        put(key, new_va, conf, f"{len(hits)} reference(s) in relocated functions", extra)
    return res


def summary(res: dict) -> dict:
    by = {}
    for k, v in res.items():
        by.setdefault(v["role"], {}).setdefault(v["confidence"], 0)
        by[v["role"]][v["confidence"]] += 1
    native = [k for k, v in res.items() if v["role"] == "native"]
    ok_native = all(res[k]["confidence"] in ("high", "medium") and res[k].get("body_identical", True) for k in native)
    logic_changed = [k for k, v in res.items() if v["role"] == "logic" and (v["confidence"] in ("low", "none") or v.get("body_identical") is False)]
    return {"by_role": by, "native_writer_ready": ok_native, "logic_changed_or_missing": logic_changed,
            "verdict": ("native writer addresses found with identical bodies" if ok_native else
                        "native writer NOT ready: some patched addresses are missing or their code changed (manual work)")
            + ("; predictor logic unchanged" if not logic_changed else f"; predictor logic to re-check: {', '.join(logic_changed)}")}


def build_profile(new_path, sha, label, res, out: Path) -> dict:
    prof = BP.builtin_705()
    prof.update(build_id=label, label=f"NMS {label} (auto-relocated, unverified)", exe=str(new_path), exe_sha256=sha,
                addresses={k: (v["va"] or "0x0") for k, v in res.items()}, catalog_cache=str(out / "cache"),
                shipwright_cache=str(out / "shipwright"), relocated_from="7.05", verified=False)
    data = out / "data"
    if (data / "research-output").is_dir():
        prof["data_root"] = str(data)
        prof["preset_mbin"] = str(data / "research-output/exact705-dungeon-inputs-20261019/metadata/reality/tables/freighterdungeonstable.mbin")
        prof["writer_table_mbin"] = str(data / "writer-table/generatedbasetemplatestable.mbin")
        prof["writer_table_mxml"] = str(data / "writer-table/generatedbasetemplatestable.MXML")
        prof["asset_rows"] = str(data / "asset_source_rows.bin")
        prof["spacepoi_dir"] = str(data / "spacepoi")
        fpf = data / "fingerprints.json"
        if fpf.is_file():
            prof["fingerprints"] = json.loads(fpf.read_text(encoding="utf-8"))
    return prof


def run(new_path, label=None, out=None, as_json=False, old_path=None, new_data=None) -> dict:
    t0 = time.time()
    old = Image(old_path or BP.builtin_705()["exe"])
    new = Image(new_path, new_data)
    sha = hashlib.sha256(new.data).hexdigest().upper()
    notes = []
    res = relocate(old, new, notes)
    live = {}
    try:
        import nms_find_addresses_705 as FIND
        r = FIND.find_app(FIND.Pe(str(new_path))) if new_data is None else {"found": None, "notes": ["skipped for in-memory test image"]}
        live = {"found": r.get("found"), "app_rva": hex(r["app_rva"]) if r.get("app_rva") else None,
                "data_ptr": hex(r["data_ptr"]) if r.get("data_ptr") is not None else None, "method": r.get("method"),
                "notes": r.get("notes")}
    except Exception as exc:
        live = {"found": False, "error": repr(exc)}
    doc = {"exe": str(new_path), "exe_sha256": sha, "base_build": "7.05", "base_exe_sha256": BP.EXE_SHA_705,
           "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "seconds": round(time.time() - t0, 1),
           "functions_in_pdata": {"old": len(old.fstart), "new": len(new.fstart)},
           "addresses": res, "live_reader": live, "struct_offsets_not_relocatable": BP.STRUCT_OFFSETS_705,
           "summary": summary(res), "notes": notes}
    if out:
        out = Path(out)
        if sha == BP.EXE_SHA_705 and Path(out).resolve() == (BP.BUILDS / BP.BASE_ID).resolve():
            raise SystemExit("refusing to write into the 7.05 build folder")
        out.mkdir(parents=True, exist_ok=True)
        (out / "address_map.json").write_text(json.dumps(doc, indent=1), encoding="utf-8")
        prof = build_profile(new_path, sha, label or f"sha-{sha[:8]}", res, out)
        (out / "build.json").write_text(json.dumps(prof, indent=1), encoding="utf-8")
        doc["written"] = [str(out / "address_map.json"), str(out / "build.json")]
    return doc


def print_report(doc):
    s = doc["summary"]
    print(f"exe {doc['exe']}  SHA-256 {doc['exe_sha256'][:8]}...  ({doc['seconds']} s, "
          f"{doc['functions_in_pdata']['new']} functions)")
    for k, v in doc["addresses"].items():
        moved = "" if v["va"] == v["old_va"] else f" (7.05 {v['old_va']})"
        print(f"  {k:<32} {str(v['va']):<14}{moved:<22} {v['confidence']:<6} {v['method']}")
    print("  live reader:", doc["live_reader"])
    print("VERDICT:", s["verdict"])


def self_test() -> int:
    """7.05 vs itself must give every known address exactly; a perturbed in-memory copy must still find the writer
    with a lower confidence and report the changed body."""
    prof = BP.builtin_705()
    ok = True
    doc = run(prof["exe"])
    wrong = {k: (v["va"], v["old_va"], v["confidence"]) for k, v in doc["addresses"].items()
             if v["va"] != v["old_va"] or v["confidence"] not in ("high", "medium")}
    n = len(doc["addresses"])
    print(f"[{'PASS' if not wrong else 'FAIL'}] 7.05 vs 7.05: {n - len(wrong)}/{n} addresses found exactly "
          f"({doc['seconds']} s); writer {doc['addresses']['writer']['va']}")
    for k, v in wrong.items():
        print("     wrong:", k, v)
    ok &= not wrong
    conf = {}
    for v in doc["addresses"].values():
        conf[v["confidence"]] = conf.get(v["confidence"], 0) + 1
    print("     confidence:", conf)
    # perturbed copy: change 4 opcode bytes deep inside the writer and inside one hook body (not their prologues)
    data = bytearray(Path(prof["exe"]).read_bytes())
    img = Image(prof["exe"], bytes(data))
    w = BP.ADDRESSES_705["writer"][0]
    f = Func(img, w)
    k = len(f.insns) // 2
    while f.insns[k][2] is not None:
        k += 1
    o = img.off(img.rva(f.insns[k][0]))
    data[o:o + f.insns[k][1]] = b"\x90" * f.insns[k][1]          # one instruction -> NOPs (a "small code change")
    doc2 = run(prof["exe"], new_data=bytes(data))
    wv = doc2["addresses"]["writer"]
    good = wv["va"] == hex(w) and wv.get("body_identical") is False and wv["confidence"] in ("medium", "low")
    print(f"[{'PASS' if good else 'FAIL'}] perturbed writer body: writer found at {wv['va']} ({wv['confidence']}, "
          f"body identical {wv.get('body_identical')}, similarity {wv.get('similarity')}); verdict: {doc2['summary']['verdict']}")
    ok &= good
    others = sum(1 for kk, v in doc2["addresses"].items() if kk != "writer" and v["va"] == v["old_va"])
    print(f"     other addresses still exact: {others}/{len(doc2['addresses']) - 1}")
    print("SELFTEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("exe", nargs="?")
    ap.add_argument("--label")
    ap.add_argument("--out")
    ap.add_argument("--extract", action="store_true", help="also re-extract game data into <out>/data")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return self_test()
    if not a.exe:
        ap.error("pass the new NMS.exe (or --self-test)")
    sha = BP.sha256_file(a.exe)
    label = a.label or f"sha-{sha[:8]}"
    out = Path(a.out) if a.out else BP.BUILDS / label
    if sha == BP.EXE_SHA_705 and not a.out:
        print("this is the 7.05 exe; report only (the 7.05 profile is built in and never overwritten)")
        out = None
    if a.extract and out:
        import extract_build_data_705 as XB
        XB.extract(Path(a.exe).parent.parent, out / "data")
    doc = run(a.exe, label, out)
    print(json.dumps(doc, indent=1) if a.json else "", end="")
    if not a.json:
        print_report(doc)
        for w in doc.get("written", []):
            print("wrote", w)
    return 0 if doc["summary"]["native_writer_ready"] else 1


if __name__ == "__main__":
    sys.exit(main())
