"""Unicorn emulation spike: run the real NMS 7.05 derelict layout writer FUN_14039E5E0.

Adapted from NMS-Shipwright nms_procgen/emu.py (MIT licence, (c) its authors),
trimmed: no exeaddr/globals/pak extraction, no gamepath. Reads the read-only
analysis copy of NMS.exe; never touches the game or the Steam folder.

Run:  %USERPROFILE%/tools/NMS-Shipwright/.venv/Scripts/python.exe -I tools/emulate_writer_705.py [--max-insns N]
Outputs go to D:/Orca/NMS-Derelict-Probe-analysis/emu/.
"""
from __future__ import annotations

import argparse, json, math, os, struct, sys
from pathlib import Path

from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_HOOK_MEM_UNMAPPED, UC_MODE_64, Uc, UcError
from unicorn import x86_const as X

ROOT = Path("D:/Orca/NMS-Derelict-Probe")
EXE = Path("D:/Orca/NMS-Derelict-Probe-analysis/rea/NMS-13D5060D.exe")
EXE_SHA = "13D5060D4EFB9D2A6A6B1B349BC4257231056CC2A055DF4BB15D816262CC3499"
OUT = Path("D:/Orca/NMS-Derelict-Probe-analysis/emu")
USE_LIVE_DESC = True
ASSET_ROWS = Path("D:/Orca/NMS-Derelict-Probe-analysis/emu/asset_source_rows.bin")
RUN_ROWS = ROOT / "live-runtime/NMSDerelictSurveyor/layout-cdb-r3/98a782a55ef44aec88142de0ce5e8e6a"
TABLE_MBIN = Path("D:/Orca/Temp/generatedbase-table-705-mbc707/generatedbasetemplatestable.mbin")
PRESET_MBIN = ROOT / "research-output/exact705-dungeon-inputs-20261019/metadata/reality/tables/freighterdungeonstable.mbin"
PRESET_STATIC_INPUTS = ROOT / "research-output/offline-layout-705-20261019/all_10_presets_static_inputs_corrected_20261019.json"

BASE = 0x140000000
STUBS, SENTINEL = 0x10000000, 0x10100000
NATIVE = STUBS + 0x20000
NATIVE_CODE = {
    "memmove": bytes.fromhex("57564889c84889cf4889d64c89c14839f776194a8d14064839d77310488d740eff488d7c0ffffdf3a4fceb504883f920721c0f10260f106e100f11270f116f104883c6204883c7204883e920ebde4883f9087214488b164889174883c6084883c7084883e908ebe64885c9740f8a16881748ffc648ffc748ffc9ebec5e5fc3"),
    "memset": bytes.fromhex("57" "4989c9" "4889cf" "89d0" "4c89c1" "f3aa" "4c89c8" "5f" "c3"),
    "floorf": bytes.fromhex("660f3a0ac001" "c3"),
    "ceilf": bytes.fromhex("660f3a0ac002" "c3"),
}
NATIVE_CODE["memcpy"] = NATIVE_CODE["memmove"]
STACK, STACK_SIZE = 0x20000000, 0x2000000
TEB = 0x2F000000
HEAP, HEAP_SIZE = 0x30000000, 0x20000000
APP, APP_SIZE = 0x60000000, 0x1000000
ARGS = (X.UC_X86_REG_RCX, X.UC_X86_REG_RDX, X.UC_X86_REG_R8, X.UC_X86_REG_R9)
XMM = [getattr(X, f"UC_X86_REG_XMM{i}") for i in range(8)]
_M1 = {"floor": math.floor, "ceil": math.ceil, "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
       "acos": math.acos, "asin": math.asin, "atan": math.atan, "exp": math.exp, "log": math.log, "log10": math.log10,
       "log2": math.log2, "trunc": math.trunc,
       "round": lambda x: math.floor(x + 0.5) if x >= 0 else -math.floor(-x + 0.5)}
_M2 = {"pow": math.pow, "fmod": math.fmod, "atan2": math.atan2}
MATH1 = {**_M1, **{k + "f": v for k, v in _M1.items()}}
MATH2 = {**_M2, **{k + "f": v for k, v in _M2.items()}}
M64 = (1 << 64) - 1


class Emu:
    def __init__(self, exe=EXE):
        import pefile
        data = Path(exe).read_bytes()
        pe = pefile.PE(data=data, fast_load=True)
        pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"],
                                               pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_TLS"]])
        mu = self.mu = Uc(UC_ARCH_X86, UC_MODE_64)
        mu.mem_map(BASE, (pe.OPTIONAL_HEADER.SizeOfImage + 0xFFF) & ~0xFFF)
        mu.mem_write(BASE, data[:pe.OPTIONAL_HEADER.SizeOfHeaders])
        for s in pe.sections:
            mu.mem_write(BASE + s.VirtualAddress,
                         data[s.PointerToRawData:s.PointerToRawData + min(s.SizeOfRawData, s.Misc_VirtualSize)])
        for addr, size in ((STUBS, 0x10000), (NATIVE, 0x1000), (SENTINEL, 0x1000), (STACK, STACK_SIZE), (TEB, 0x10000),
                           (HEAP, HEAP_SIZE), (APP, APP_SIZE)):
            mu.mem_map(addr, size)
        self.heap, self.sizes, self.imports = HEAP, {}, {}
        native, at = {}, NATIVE
        for name, code in NATIVE_CODE.items():
            native[name] = at
            mu.mem_write(at, code)
            at += (len(code) + 15) & ~15
        k = 0
        for d in pe.DIRECTORY_ENTRY_IMPORT:
            for imp in d.imports:
                name = (imp.name or b"#").decode()
                if name in native:
                    mu.mem_write(imp.address, struct.pack("<Q", native[name]))
                    continue
                stub = STUBS + 0x10 * k
                k += 1
                mu.mem_write(stub, b"\xc3")
                mu.mem_write(imp.address, struct.pack("<Q", stub))
                self.imports[stub] = name
        tls = pe.DIRECTORY_ENTRY_TLS.struct
        tmpl = bytes(mu.mem_read(tls.StartAddressOfRawData, tls.EndAddressOfRawData - tls.StartAddressOfRawData))
        block = self.alloc(len(tmpl) + 0x4000)
        mu.mem_write(block, tmpl)
        arr = self.alloc(0x100)
        mu.mem_write(arr, struct.pack("<Q", block))
        mu.mem_write(tls.AddressOfIndex, struct.pack("<I", 0))
        mu.mem_write(TEB, struct.pack("<QQQQQQQ", 0, STACK + STACK_SIZE, STACK, 0, 0, 0, TEB))
        mu.mem_write(TEB + 0x58, struct.pack("<Q", arr))
        mu.reg_write(X.UC_X86_REG_GS_BASE, TEB)
        mu.hook_add(UC_HOOK_CODE, self._on_stub, begin=STUBS, end=STUBS + 0x10000)
        mu.hook_add(UC_HOOK_MEM_UNMAPPED, self._on_unmapped)
        self.fault = None
        self.hooks = {}      # addr -> (name, python callable or None, default rax)
        self.log = []        # captured stub calls

    # ---- memory
    def alloc(self, n, align=16):
        self.heap = (self.heap + align - 1) & ~(align - 1)
        a, self.heap = self.heap, self.heap + n
        if self.heap > HEAP + HEAP_SIZE:
            raise MemoryError("emulator heap exhausted")
        return a

    def rq(self, a): return struct.unpack("<Q", self.mu.mem_read(a, 8))[0]
    def ri(self, a): return struct.unpack("<i", self.mu.mem_read(a, 4))[0]
    def wq(self, a, v): self.mu.mem_write(a, struct.pack("<Q", v & M64))
    def wi(self, a, v): self.mu.mem_write(a, struct.pack("<i", v))
    def rd(self, a, n): return bytes(self.mu.mem_read(a, n))

    def load_mbin(self, path):
        """Load an MBIN (arrays fixed up). Returns (file base address, struct address = base+0x20)."""
        b = Path(path).read_bytes()
        h = self.alloc(len(b) + 0x100, 0x100)
        self.mu.mem_write(h, b)
        for p in (i - 12 for i in range(12, len(b) - 3, 4)
                  if struct.unpack_from("<I", b, i)[0] == 0xAAAAAA01 and (i - 12) % 8 == 0):
            rel, cnt = struct.unpack_from("<qI", b, p)
            self.mu.mem_write(h + p, struct.pack("<Q", h + p + rel if cnt else 0))
        # polymorphic entries {rel offset (u64), type hash (u32), 0xEEEEEE01}: rel is from the entry itself
        for i in range(12, len(b) - 3, 4):
            if struct.unpack_from("<I", b, i)[0] == 0xEEEEEE01 and (i - 12) % 8 == 0:
                p = i - 12
                rel = struct.unpack_from("<q", b, p)[0]
                self.mu.mem_write(h + p, struct.pack("<Q", h + p + rel))
        return h, h + 0x20

    def hook_func(self, addr, name, fn=None, ret=0):
        """Record every call to `addr` (args in self.log), run fn(emu, regs, stack)->rax (optional), then return."""
        self.mu.mem_write(addr, b"\xc3")      # ret (rax is set by the hook)
        self.hooks[addr] = (name, fn, ret)
        self.mu.hook_add(UC_HOOK_CODE, self._on_hook, begin=addr, end=addr)

    def _on_hook(self, mu, addr, size, _):
        name, fn, ret = self.hooks[addr]
        regs = [mu.reg_read(r) for r in ARGS]
        rsp = mu.reg_read(X.UC_X86_REG_RSP)
        st = [self.rq(rsp + 8 + 8 * i) for i in range(8)]
        self.log.append({"fn": name, "addr": hex(addr), "args": regs, "stack": st, "ret_to": self.rq(rsp)})
        rax = fn(self, regs, st) if fn else ret
        mu.reg_write(X.UC_X86_REG_RAX, rax & M64)

    # ---- imports
    def _xmm(self, i, f32):
        v = self.mu.reg_read(XMM[i])
        return (struct.unpack("<f", struct.pack("<I", v & 0xFFFFFFFF))[0] if f32
                else struct.unpack("<d", struct.pack("<Q", v & M64))[0])

    def _set_xmm(self, i, val, f32):
        bits = (struct.unpack("<I", struct.pack("<f", val))[0] if f32 else struct.unpack("<Q", struct.pack("<d", val))[0])
        self.mu.reg_write(XMM[i], bits)

    def _malloc(self, n, align=16):
        a = self.alloc(max(n, 1), align)
        self.sizes[a] = n
        return a

    def _on_stub(self, mu, addr, size, _):
        fn = self.imports.get(addr)
        if fn is None:
            return
        rcx, rdx, r8 = (mu.reg_read(r) for r in ARGS[:3])
        ret = 0
        self.log.append({"fn": "import:" + fn, "args": [rcx, rdx, r8]})
        try:
            if fn in MATH1:
                f32 = fn.endswith("f") and fn[:-1] in MATH1
                self._set_xmm(0, MATH1[fn](self._xmm(0, f32)), f32)
            elif fn in MATH2:
                f32 = fn.endswith("f")
                self._set_xmm(0, MATH2[fn](self._xmm(0, f32), self._xmm(1, f32)), f32)
            elif fn in ("malloc", "??2@YAPEAX_K@Z", "??_U@YAPEAX_K@Z"):
                ret = self._malloc(rcx)
            elif fn == "_aligned_malloc":
                ret = self._malloc(rcx, max(16, rdx))
            elif fn == "calloc":
                ret = self._malloc(rcx * rdx)
            elif fn in ("realloc", "_aligned_realloc"):
                ret = self._malloc(rdx, max(16, r8) if fn.startswith("_") else 16)
                if rcx and self.sizes.get(rcx):
                    mu.mem_write(ret, bytes(mu.mem_read(rcx, min(self.sizes[rcx], rdx))))
        except (ValueError, OverflowError, ZeroDivisionError):
            self._set_xmm(0, float("nan"), False)
        mu.reg_write(X.UC_X86_REG_RAX, ret)

    def _on_unmapped(self, mu, access, addr, size, value, _):
        self.fault = (addr, mu.reg_read(X.UC_X86_REG_RIP))
        return False

    def call(self, fn, *args, stack_args=(), count=200_000_000):
        mu = self.mu
        rsp = ((STACK + STACK_SIZE - 0x20000) & ~0xF) - 8
        mu.mem_write(rsp, struct.pack("<Q", SENTINEL))
        for i, v in enumerate(stack_args):          # arg5 at [rsp+0x28], arg6 at [rsp+0x30]
            mu.mem_write(rsp + 0x28 + 8 * i, struct.pack("<Q", v & M64))
        mu.reg_write(X.UC_X86_REG_RSP, rsp)
        for r, v in zip(ARGS, args):
            mu.reg_write(r, v & M64)
        self.fault = None
        try:
            # count<=0: no instruction cap (Unicorn's count hook runs on every instruction and is slow)
            mu.emu_start(fn, SENTINEL, count=max(count, 0))
        except UcError as e:
            return {"ok": False, "error": str(e), "fault": self.fault, "rip": mu.reg_read(X.UC_X86_REG_RIP),
                    "rsp": mu.reg_read(X.UC_X86_REG_RSP)}
        pc = mu.reg_read(X.UC_X86_REG_RIP)
        return {"ok": pc == SENTINEL, "rax": mu.reg_read(X.UC_X86_REG_RAX), "pc": pc}


# ------------------------------------------------------------------ inputs
def build_inputs(e: Emu, *, seed_value: int, preset_index: int):
    sys.path.insert(0, str(ROOT / "research-output/offline-layout-705-20261019"))
    import decode_live_source_rows as dl
    info = {}
    _, tbl = e.load_mbin(TABLE_MBIN)             # GcGeneratedBaseTemplatesTable
    arr0 = e.rq(tbl)                             # 319 x 0x50 descriptors
    n0 = e.ri(tbl + 8)
    info["table_counts"] = [e.ri(tbl + 8), e.ri(tbl + 0x18), e.ri(tbl + 0x28)]
    # ASSETS VARIANT: rows built from game assets by tools/build_source_rows_from_assets.py;
    # +0x2A0 holds the descriptor INDEX into the table's first array (0x50 stride).
    blob = bytearray(ASSET_ROWS.read_bytes())
    nrows = len(blob) // 0x2B0
    ptrs = [struct.unpack_from("<Q", blob, i * 0x2B0 + 0x2A0)[0] for i in range(nrows)]
    lo = 0
    for i, p in enumerate(ptrs):
        assert p < n0, (i, hex(p))
        struct.pack_into("<Q", blob, i * 0x2B0 + 0x2A0, arr0 + p * 0x50)
    rows = e.alloc(len(blob), 0x100)
    e.mu.mem_write(rows, bytes(blob))
    # overlay live-dumped descriptor qwords (first 0x50 bytes) where they are plain data: the runtime fills a few
    # fields (e.g. +0x18) and rewrites array flag words that the MBIN does not carry; pointer qwords stay ours.
    ds = dl.descriptors_from_log((RUN_ROWS / "cdb.log").read_text(encoding="utf-8", errors="replace")) if USE_LIVE_DESC else None
    patched = set(range(n0)) if not USE_LIVE_DESC else set()
    for i, p in enumerate(ptrs):
        idx = (p - lo) // 0x50
        if idx in patched:
            continue
        patched.add(idx)
        for k in range(10):
            q = ds[i][k]
            if not (0x10000000000 < q < 0x7FFFFFFFFFFF):
                e.wq(arr0 + idx * 0x50 + 8 * k, q)
    info["descriptors_overlaid"] = len(patched)
    G = 0x145092FF0
    e.wq(G, tbl)
    e.wi(G + 0x24, nrows)
    e.wq(G + 0x28, rows)
    info["nrows"] = nrows
    pbase, _ = e.load_mbin(PRESET_MBIN)          # CARGO_BUGS = index 7, stride 0x90, array data at file 0x30
    # The hash-matched freighterdungeonstable has ten 0x90-byte entries.
    if not 0 <= preset_index < 10:
        raise ValueError(f"preset index out of range: {preset_index}")
    preset = pbase + 0x30 + preset_index * 0x90
    info["preset_name"] = e.rd(preset + 0x80, 16).split(b"\0")[0].decode()
    info["preset_index"] = preset_index
    seed = e.alloc(0x20)
    e.wq(seed, seed_value)
    e.mu.mem_write(seed + 8, b"\x01")
    info["writer_seed"] = f"{seed_value:016X}"
    outbuf = e.alloc(0x100000, 0x100)
    return dict(G=G, seed=seed, preset=preset, outbuf=outbuf, info=info, tbl=tbl, rows=rows, preset_base=pbase)


def main():
    global USE_LIVE_DESC, ASSET_ROWS, OUT
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-insns", type=int, default=300_000_000, help="instruction cap; 0 = unlimited (much faster)")
    ap.add_argument("--no-counters", action="store_true", help="skip the per-callee entry counters (faster)")
    ap.add_argument("--no-live-desc", action="store_true", help="skip the live-dumped descriptor qword overlay")
    ap.add_argument("--asset-rows", default=str(ASSET_ROWS))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--seed", type=lambda value: int(value, 0),
                    help="64-bit seed passed directly to FUN_14039E5E0 (integer accepts 0x prefix)")
    ap.add_argument("--preset-index", type=int,
                    help="GcFreighterDungeonParams table index (CARGO_BUGS is 7)")
    ap.add_argument("--universe-address",
                    help="canonical 16-digit universe address; resolves writer seed and preset")
    ap.add_argument("--global-override", type=lambda value: int(value, 0),
                    help="explicit 64-bit global seed override for --universe-address; required with that option")
    a = ap.parse_args()
    input_metadata = {}
    if a.universe_address is not None:
        if a.seed is not None or a.preset_index is not None:
            ap.error("--universe-address cannot be combined with --seed or --preset-index")
        if a.global_override is None:
            ap.error("--universe-address requires explicit --global-override (use 0 for the default-path assumption)")
        sys.path.insert(0, str(ROOT / "research-output/offline-layout-705-20261019"))
        from nms_dungeon_preset_705 import (
            options_from_export_rows,
            select_dungeon_preset_for_address,
            table_rows_from_export_rows,
        )
        static = json.loads(PRESET_STATIC_INPUTS.read_text(encoding="utf-8"))
        preset_data = static["preset_selection"]
        table_rows = [{"Name": row["name"], "_index": row["table_index"]} for row in static["presets"]]
        selection = select_dungeon_preset_for_address(
            a.universe_address,
            options_from_export_rows(preset_data["entrance_options_in_source_order"]),
            global_override_value=a.global_override,
            dungeon_table_rows=table_rows_from_export_rows(table_rows),
        )
        if selection.mixed_seed is None or selection.native_table_index is None or selection.selected_name is None:
            ap.error("address did not produce a unique writer seed and preset")
        seed_value = selection.mixed_seed
        preset_index = selection.native_table_index
        input_metadata = {
            "universe_address": str(a.universe_address).upper().removeprefix("0X").zfill(16),
            "global_override": f"{a.global_override:016X}",
            "preset_selection_status": selection.status,
            "selected_option": selection.selected_name,
        }
    else:
        seed_value = 0x7D7ED1B33E15365D if a.seed is None else a.seed
        preset_index = 7 if a.preset_index is None else a.preset_index
        if a.global_override is not None:
            ap.error("--global-override is only valid with --universe-address")
    USE_LIVE_DESC = not a.no_live_desc
    ASSET_ROWS = Path(a.asset_rows)
    OUT = Path(a.out)
    OUT.mkdir(parents=True, exist_ok=True)
    e = Emu()
    inp = build_inputs(e, seed_value=seed_value, preset_index=preset_index)
    inp["info"].update(input_metadata)
    print("inputs:", json.dumps(inp["info"]))

    alloc_obj = e.alloc(0x1000)
    e.hook_func(0x142C1FE30, "alloc_getter", lambda emu, r, s: alloc_obj)
    e.hook_func(0x142C20E80, "alloc", lambda emu, r, s: emu._malloc(r[1], 16))
    e.hook_func(0x1403A4400, "A4400_handle", None, 0)
    captured = {}

    def cap_a4720(emu, r, st):          # placement descriptor array (count at +4, data ptr at +8, 20-byte records)
        cnt, ptr = emu.ri(r[1] + 4), emu.rq(r[1] + 8)
        captured["count"] = cnt
        captured["placements"] = emu.rd(ptr, cnt * 20)
        captured["rooms_at_a4720"] = emu.rd(inp["outbuf"], 0x40 * 16)
        return 0
    e.hook_func(0x1403A4720, "A4720_instance", cap_a4720, 0)
    e.hook_func(0x1403A51B0, "A51B0_prune", None, 0)
    e.hook_func(0x142BFF9A0, "timer", None, 0)
    e.hook_func(0x142C090F0, "C090F0_engine", None, 0)
    e.hook_func(0x142BFA8F0, "BFA8F0_free", None, 0)
    e.hook_func(0x142C22170, "C22170_allocator_restore", None, 0)
    for extra in os.environ.get("EMU_EXTRA_STUBS", "").split(","):
        if extra:
            e.hook_func(int(extra, 16), "extra_" + extra, None, 0)

    # entry counters on the writer's main callees (no behaviour change)
    counts = {}
    for name, va in (("A03E0", 0x1403A03E0), ("A06E0", 0x1403A06E0), ("A0580", 0x1403A0580), ("A0850", 0x1403A0850),
                     ("A01F0", 0x1403A01F0), ("A1DA0", 0x1403A1DA0), ("A2780", 0x1403A2780), ("A3270", 0x1403A3270),
                     ("A3BC0", 0x1403A3BC0), ("A5480", 0x1403A5480), ("A0AD0", 0x1403A0AD0), ("A0FF0", 0x1403A0FF0), ("A15F0", 0x1403A15F0), ("A2120", 0x1403A2120), ("A1A00", 0x1403A1A00)):
        counts[name] = 0
        if a.no_counters:
            continue
        def cb(mu, addr, size, _, name=name):
            counts[name] += 1
        e.mu.hook_add(UC_HOOK_CODE, cb, begin=va, end=va)
    import time
    t0 = time.time()
    res = e.call(0x14039E5E0, inp["G"], 0x4951E1, inp["seed"], inp["preset"], stack_args=(0, inp["outbuf"]), count=a.max_insns)
    summary = {"seconds": round(time.time() - t0, 1), "inputs": inp["info"], "entry_counts": counts, "result": {k: (hex(v) if isinstance(v, int) else v) for k, v in res.items() if k != "fault"},
               "fault": [hex(x) for x in res["fault"]] if res.get("fault") else None}
    calls = [c for c in e.log if not c["fn"].startswith("import:")]
    summary["stub_calls"] = {}
    for c in calls:
        summary["stub_calls"][c["fn"]] = summary["stub_calls"].get(c["fn"], 0) + 1
    imps = {}
    for c in e.log:
        if c["fn"].startswith("import:"):
            imps[c["fn"]] = imps.get(c["fn"], 0) + 1
    summary["imports_called"] = imps
    (OUT / "last_run_summary.json").write_text(json.dumps(summary, indent=1))
    (OUT / "stub_call_log.json").write_text(json.dumps(
        [{**c, "args": [hex(x) for x in c["args"]], "stack": [hex(x) for x in c.get("stack", [])]} for c in calls[:5000]]))
    (OUT / "outbuf.bin").write_bytes(e.rd(inp["outbuf"], 0x40 * 64))
    if "placements" in captured:
        summary["compare_to_replay"] = compare_to_replay(e, inp, captured, res)
        (OUT / "a2780_placements.bin").write_bytes(captured["placements"])
        (OUT / "last_run_summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))


def compare_to_replay(e, inp, cap, res):
    import csv
    import xml.etree.ElementTree as ET
    from collections import Counter
    mx = ET.parse("D:/Orca/Temp/generatedbase-table-705-mbc707/generatedbasetemplatestable.MXML").getroot()
    names = []
    for el in mx.find("Property[@name='DecorationTemplates']"):
        fn = [x.get("value") for x in el.iter("Property") if x.get("name") == "Filename"]
        names.append((el.get("_id"), fn[0] if fn else None))
    arr0 = e.rq(inp["tbl"])
    recs = [cap["placements"][i * 20:(i + 1) * 20] for i in range(cap["count"])]
    emu_scene, emu_room_counts, per_rec = Counter(), Counter(), []
    for r in recs:
        rowidx = struct.unpack_from("<I", r, 4)[0]
        dptr = e.rq(inp["rows"] + rowidx * 0x2B0 + 0x2A0)
        did = (dptr - arr0) // 0x50
        nid, fn = names[did]
        room = r[0x0E]
        emu_scene[fn] += 1
        emu_room_counts[room] += 1
        per_rec.append({"row": rowidx, "desc": did, "id": nid, "scene": fn, "room": room,
                        "xy": struct.unpack_from("<HH", r, 8), "z": struct.unpack_from("<H", r, 12)[0]})
    rep = list(csv.DictReader(open(ROOT / "research-output/known-derelict-replay-20261019/KNOWN_DERELICT_ROOM_COMPONENTS_20261019.csv")))
    rep_scene = Counter(x["scene_resource"] for x in rep)
    rep_room = Counter(int(x["room_index"]) for x in rep)
    # absolute layout position (relative to root) per A4720 doc: -32+(d-origin)*8 etc, origin = preset Entrance (6,3,0)
    pos_emu = Counter()
    for pr in per_rec:
        pos_emu[(pr["scene"], -32 + (pr["xy"][0] - 6) * 8, -16 + (pr["xy"][1] - 3) * 8, -32 + (pr["z"] - 0) * 8)] += 1
    out = {
        "writer_rax_room_count": res.get("rax"),
        "emu_instances": len(recs), "replay_instances": len(rep),
        "scene_multiset_equal": emu_scene == rep_scene,
        "scene_multiset_diff_emu_minus_replay": dict(emu_scene - rep_scene),
        "scene_multiset_diff_replay_minus_emu": dict(rep_scene - emu_scene),
        "per_room_emu": dict(sorted(emu_room_counts.items())), "per_room_replay": dict(sorted(rep_room.items())),
        "per_room_equal": dict(emu_room_counts) == dict(rep_room),
    }
    (OUT / "emu_placements.json").write_text(json.dumps(per_rec, indent=0))
    return out


if __name__ == "__main__":
    main()
