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
RUN_ROWS = ROOT / "live-runtime/NMSDerelictSurveyor/layout-cdb-r3/98a782a55ef44aec88142de0ce5e8e6a"
TABLE_MBIN = Path("D:/Orca/Temp/generatedbase-table-705-mbc707/generatedbasetemplatestable.mbin")
PRESET_MBIN = ROOT / "research-output/exact705-dungeon-inputs-20261019/metadata/reality/tables/freighterdungeonstable.mbin"

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
            mu.emu_start(fn, SENTINEL, count=count)
        except UcError as e:
            return {"ok": False, "error": str(e), "fault": self.fault, "rip": mu.reg_read(X.UC_X86_REG_RIP),
                    "rsp": mu.reg_read(X.UC_X86_REG_RSP)}
        pc = mu.reg_read(X.UC_X86_REG_RIP)
        return {"ok": pc == SENTINEL, "rax": mu.reg_read(X.UC_X86_REG_RAX), "pc": pc}


# ------------------------------------------------------------------ inputs
def build_inputs(e: Emu):
    sys.path.insert(0, str(ROOT / "research-output/offline-layout-705-20261019"))
    import decode_live_source_rows as dl
    info = {}
    _, tbl = e.load_mbin(TABLE_MBIN)             # GcGeneratedBaseTemplatesTable
    arr0 = e.rq(tbl)                             # 319 x 0x50 descriptors
    n0 = e.ri(tbl + 8)
    info["table_counts"] = [e.ri(tbl + 8), e.ri(tbl + 0x18), e.ri(tbl + 0x28)]
    blob = bytearray((RUN_ROWS / "source-rows.bin").read_bytes())
    nrows = len(blob) // 0x2B0
    ptrs = [struct.unpack_from("<Q", blob, i * 0x2B0 + 0x2A0)[0] for i in range(nrows)]
    lo = min(ptrs)
    for i, p in enumerate(ptrs):
        idx, rem = divmod(p - lo, 0x50)
        assert rem == 0 and idx < n0, (i, hex(p))
        struct.pack_into("<Q", blob, i * 0x2B0 + 0x2A0, arr0 + idx * 0x50)
    rows = e.alloc(len(blob), 0x100)
    e.mu.mem_write(rows, bytes(blob))
    # sanity: live-dumped descriptor bytes vs MBIN-derived element (pointer qwords ignored)
    ds = dl.descriptors_from_log((RUN_ROWS / "cdb.log").read_text(encoding="utf-8", errors="replace"))
    bad = 0
    for i, p in enumerate(ptrs):
        idx = (p - lo) // 0x50
        live = b"".join(struct.pack("<Q", q) for q in ds[i])[:0x50]
        mine = e.rd(arr0 + idx * 0x50, 0x50)
        for off in range(0, 0x50, 8):
            a, b = live[off:off + 8], mine[off:off + 8]
            if a != b and not (struct.unpack("<Q", a)[0] > 0x10000000000 and struct.unpack("<Q", b)[0] > 0x10000000):
                bad += 1
    info["descriptor_mismatch_qwords"] = bad
    G = 0x145092FF0
    e.wq(G, tbl)
    e.wi(G + 0x24, nrows)
    e.wq(G + 0x28, rows)
    info["nrows"] = nrows
    pbase, _ = e.load_mbin(PRESET_MBIN)          # CARGO_BUGS = index 7, stride 0x90, array data at file 0x30
    preset = pbase + 0x30 + 7 * 0x90
    info["preset_name"] = e.rd(preset + 0x80, 16).split(b"\0")[0].decode()
    seed = e.alloc(0x20)
    e.wq(seed, 0x7D7ED1B33E15365D)
    e.mu.mem_write(seed + 8, b"\x01")
    outbuf = e.alloc(0x100000, 0x100)
    return dict(G=G, seed=seed, preset=preset, outbuf=outbuf, info=info, tbl=tbl, rows=rows, preset_base=pbase)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-insns", type=int, default=300_000_000)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    e = Emu()
    inp = build_inputs(e)
    print("inputs:", json.dumps(inp["info"]))

    alloc_obj = e.alloc(0x1000)
    e.hook_func(0x142C1FE30, "alloc_getter", lambda emu, r, s: alloc_obj)
    e.hook_func(0x142C20E80, "alloc", lambda emu, r, s: emu._malloc(r[1], 16))
    e.hook_func(0x1403A4400, "A4400_handle", None, 0)
    e.hook_func(0x1403A4720, "A4720_instance", None, 0)
    e.hook_func(0x1403A51B0, "A51B0_prune", None, 0)
    e.hook_func(0x142BFF9A0, "timer", None, 0)
    for extra in os.environ.get("EMU_EXTRA_STUBS", "").split(","):
        if extra:
            e.hook_func(int(extra, 16), "extra_" + extra, None, 0)

    res = e.call(0x14039E5E0, inp["G"], 0x4951E1, inp["seed"], inp["preset"], stack_args=(0, inp["outbuf"]), count=a.max_insns)
    summary = {"result": {k: (hex(v) if isinstance(v, int) else v) for k, v in res.items() if k != "fault"},
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
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
