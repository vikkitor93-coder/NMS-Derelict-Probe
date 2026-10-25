"""Read-only live reader for NMS 7.05 (exe SHA-256 13D5060D...3499): universe address + player position.

Uses only OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ) + ReadProcessMemory.
Nothing is written to, injected into, or suspended in the game.

Chain (static, NMS.exe 13D5060D):
  cGcApplication object  = NMS + 0x6E8D6D0   (cGcApplication::Construct stores the 0x95F210 Data alloc at +0x38 = 0x6E8D708)
  app + 0x38             -> cGcApplication::Data*   (allocation size 0x95F210, as NMS.py 180132)
  data + 0x4CCF90        =  cGcSimulation           (offset used by Data::Data and Update)
  sim + 0x265940         =  mCurrentUA (u64 universe address)
  sim + 0x25F760 + 0x360 =  cGcPlayer.mPosition (3 x f32)

CLI:  python -I tools/live_position_705.py [--watch SECONDS] [--json]
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import struct
import sys
import time
from ctypes import wintypes
from pathlib import Path

APP_RVA = 0x6E8D6D0
APP_DATA_PTR = 0x38
DATA_SIMULATION = 0x4CCF90
SIM_CURRENT_UA = 0x265940
SIM_PLAYER = 0x25F760
PLAYER_POSITION = 0x360

# Builds this reader knows (SHA-256 of NMS.exe -> memory chain). On any other build the reader refuses to read, so a game
# update shows "unsupported build" instead of garbage. Add a build here only after verifying it live (an address that
# matches the portal glyphs and a position that moves with the player).
KNOWN_BUILDS = {
    "13D5060D4EFB9D2A6A6B1B349BC4257231056CC2A055DF4BB15D816262CC3499": {
        "name": "NMS 7.05", "app_rva": APP_RVA, "data_ptr": APP_DATA_PTR, "sim": DATA_SIMULATION,
        "ua": SIM_CURRENT_UA, "player": SIM_PLAYER, "pos": PLAYER_POSITION},
}

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_VM_READ = 0x0010
TH32CS_SNAPPROCESS = 0x2
TH32CS_SNAPMODULE = 0x8
TH32CS_SNAPMODULE32 = 0x10

k32 = ctypes.WinDLL("kernel32", use_last_error=True)


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_void_p), ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD), ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD),
                ("szExeFile", ctypes.c_wchar * 260)]


class MODULEENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("th32ModuleID", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                ("GlblcntUsage", wintypes.DWORD), ("ProccntUsage", wintypes.DWORD),
                ("modBaseAddr", ctypes.c_void_p), ("modBaseSize", wintypes.DWORD),
                ("hModule", wintypes.HMODULE), ("szModule", ctypes.c_wchar * 256),
                ("szExePath", ctypes.c_wchar * 260)]


k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
k32.OpenProcess.restype = wintypes.HANDLE
k32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                  ctypes.POINTER(ctypes.c_size_t)]
k32.CloseHandle.argtypes = [wintypes.HANDLE]
INVALID = ctypes.c_void_p(-1).value
PROCESS_QUERY_INFORMATION = 0x0400


class MBI(ctypes.Structure):  # MEMORY_BASIC_INFORMATION (x64)
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p), ("AllocationProtect", wintypes.DWORD),
                ("PartitionId", wintypes.WORD), ("RegionSize", ctypes.c_size_t), ("State", wintypes.DWORD),
                ("Protect", wintypes.DWORD), ("Type", wintypes.DWORD)]


k32.VirtualQueryEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.POINTER(MBI), ctypes.c_size_t]


# Builds found by tools/nms_find_addresses_705.py on a game update (static scan of the new NMS.exe). They stay "unverified"
# until --verify-glyphs confirms them in the running game. Stored next to the minimap so no code edit is needed.
# Test hooks: MINIMAP_LEARNED_FILE redirects this file; MINIMAP_FORCE_AUTO=1 makes the reader treat even a known build as
# unknown, to exercise the auto-detected path on the real running game.
LEARNED_FILE = Path(os.environ.get("MINIMAP_LEARNED_FILE") or Path(__file__).resolve().parents[1] / "minimap" / "learned_builds.json")


def load_learned() -> dict:
    try:
        return json.loads(LEARNED_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_learned(d: dict) -> None:
    tmp = LEARNED_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, indent=1), encoding="utf-8")
    os.replace(tmp, LEARNED_FILE)


def resolve_build(exe_path, sha):
    """(build, error): a built-in build (verified), a learned one (verified or not), or a fresh auto-detection (unverified).
    Auto-detection finds the application object and the Data pointer in the new exe; the offsets inside the Data block are
    taken from the latest known build (they have not moved between the builds seen so far) and checked while the game runs."""
    if sha in KNOWN_BUILDS and not os.environ.get("MINIMAP_FORCE_AUTO"):
        return {**KNOWN_BUILDS[sha], "verified": True, "source": "built-in"}, None
    learned = load_learned()
    if sha in learned:
        return learned[sha], None
    known = ", ".join(f"{b['name']} ({k[:8]})" for k, b in KNOWN_BUILDS.items())
    base = (f"unsupported NMS build (exe SHA-256 {(sha or 'unknown')[:8]}); the minimap knows {known}. The game was probably "
            "updated: see minimap/README.md, section 'After an NMS update'.")
    if not exe_path or not sha:
        return None, base
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import nms_find_addresses_705 as finder
        r = finder.find_app(finder.Pe(exe_path))
    except Exception as exc:  # a missing or unreadable exe, a changed PE layout...
        return None, base + f" The address finder failed: {exc!r}"
    if not r.get("found"):
        return None, base + " The address finder found nothing."
    prior = list(KNOWN_BUILDS.values())[-1]
    b = {"name": "auto-detected", "app_rva": r["app_rva"], "data_ptr": r["data_ptr"], "sim": prior["sim"], "ua": prior["ua"],
         "player": prior["player"], "pos": prior["pos"], "verified": False, "source": "auto: " + str(r["method"]),
         "found_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    learned[sha] = b
    try:
        save_learned(learned)
    except OSError:
        pass
    return b, None


def find_pid(name: str = "NMS.exe") -> int | None:
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == INVALID:
        return None
    try:
        e = PROCESSENTRY32W(dwSize=ctypes.sizeof(PROCESSENTRY32W))
        ok = k32.Process32FirstW(snap, ctypes.byref(e))
        while ok:
            if e.szExeFile.lower() == name.lower():
                return int(e.th32ProcessID)
            ok = k32.Process32NextW(snap, ctypes.byref(e))
    finally:
        k32.CloseHandle(snap)
    return None


k32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]


def process_path(pid: int) -> str | None:
    h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return None
    try:
        buf = ctypes.create_unicode_buffer(1024)
        n = wintypes.DWORD(len(buf))
        return buf.value if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)) else None
    finally:
        k32.CloseHandle(h)


_HASHES: dict = {}


def file_sha256(path: str) -> str:
    """SHA-256 (upper hex) of a file, cached by path + size + mtime (the 88 MB exe takes about half a second)."""
    import os
    st = os.stat(path)
    key = (path, st.st_size, st.st_mtime_ns)
    if key not in _HASHES:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        _HASHES[key] = h.hexdigest().upper()
    return _HASHES[key]


def module_base(pid: int, name: str = "NMS.exe") -> int | None:
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
    if snap == INVALID:
        return None
    try:
        m = MODULEENTRY32W(dwSize=ctypes.sizeof(MODULEENTRY32W))
        ok = k32.Module32FirstW(snap, ctypes.byref(m))
        while ok:
            if m.szModule.lower() == name.lower():
                return int(m.modBaseAddr)
            ok = k32.Module32NextW(snap, ctypes.byref(m))
    finally:
        k32.CloseHandle(snap)
    return None


class LiveReader:
    """Attach read-only to NMS.exe; `sample()` returns address + position or None while unavailable."""

    def __init__(self, pid: int | None = None):
        self.pid = pid or find_pid()
        if not self.pid:
            raise RuntimeError("NMS.exe is not running")
        self.base = module_base(self.pid)
        if not self.base:
            raise RuntimeError("NMS.exe module base not found")
        # read-only access (QUERY_INFORMATION is only for the Data block size check; VM_READ for reading)
        self.handle = (k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, self.pid)
                       or k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ, False, self.pid))
        if not self.handle:
            raise OSError(ctypes.get_last_error(), "OpenProcess failed")
        # build check: a known build, or addresses auto-detected from this exe (unverified); otherwise read nothing
        self.exe_path = process_path(self.pid)
        self.exe_sha = file_sha256(self.exe_path) if self.exe_path else None
        self.build, self.build_error = resolve_build(self.exe_path, self.exe_sha)
        self.verified = bool(self.build and self.build.get("verified"))
        self.sanity_error = None
        self._data_checked = False

    def close(self) -> None:
        if self.handle:
            k32.CloseHandle(self.handle)
            self.handle = None

    def read(self, addr: int, size: int) -> bytes | None:
        buf = ctypes.create_string_buffer(size)
        got = ctypes.c_size_t()
        if not k32.ReadProcessMemory(self.handle, ctypes.c_void_p(addr), buf, size, ctypes.byref(got)):
            return None
        return buf.raw[: got.value] if got.value == size else None

    def sim_address(self) -> int | None:
        if not self.build:
            return None
        raw = self.read(self.base + self.build["app_rva"] + self.build["data_ptr"], 8)
        if raw is None:
            return None
        data = struct.unpack("<Q", raw)[0]
        if data <= 0x10000:
            return None
        if not self.verified and not self._data_checked:   # auto-detected: the Data block must be one big allocation
            mbi = MBI()
            if k32.VirtualQueryEx(self.handle, ctypes.c_void_p(data), ctypes.byref(mbi), ctypes.sizeof(mbi)):
                if mbi.RegionSize < 0x400000:
                    self.sanity_error = f"auto-detected Data pointer is not a large block ({mbi.RegionSize:#x} bytes): wrong offset"
                    return None
            self._data_checked = True
        return data + self.build["sim"]

    def sample(self) -> dict | None:
        sim = self.sim_address()
        if sim is None:
            return None
        ua = self.read(sim + self.build["ua"], 8)
        pos = self.read(sim + self.build["player"] + self.build["pos"], 12)
        if ua is None or pos is None:
            return None
        x, y, z = struct.unpack("<3f", pos)
        addr = struct.unpack("<Q", ua)[0]
        if addr >> 56 or not all(abs(v) < 1e9 for v in (x, y, z)):   # impossible values: wrong offsets, not a real reading
            self.sanity_error = f"implausible reading (address {addr:016X}, position {x:g}, {y:g}, {z:g})"
            return None
        self.sanity_error = None
        return {"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "pid": self.pid,
                "address": f"{addr:016X}", "x": x, "y": y, "z": z, "verified": self.verified}

    def mark_verified(self) -> None:
        """Record this auto-detected build as verified (called after a glyph check passed)."""
        learned = load_learned()
        if self.exe_sha in learned:
            learned[self.exe_sha]["verified"] = True
            learned[self.exe_sha]["verified_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            save_learned(learned)
            self.verified = True


def verify_glyphs(glyphs: str, galaxy: int = 0) -> int:
    """Compare the running game's universe address with the portal glyphs the user reads in-game."""
    g = glyphs.upper().replace(" ", "").replace("-", "")
    if len(g) != 12 or any(c not in "0123456789ABCDEF" for c in g):
        print("give the 12 hex digits of the portal glyphs (planet SSS YY ZZZ XXX)")
        return 2
    want = int(f"000{g[1:4]}{galaxy & 0xFF:02X}{g[4:6]}{g[6:9]}{g[9:12]}", 16)
    r = LiveReader()
    try:
        if r.build_error:
            print(r.build_error)
            return 1
        s = r.sample()
        if s is None:
            print("no reading yet" + (f": {r.sanity_error}" if r.sanity_error else " (load a save first)"))
            return 1
        mask = ~(0xF << 52)   # the planet nibble differs per planet; the derelict is per system
        got = int(s["address"], 16)
        if got & mask == want & mask:
            print(f"MATCH: the game's address {s['address']} equals the glyphs you gave.")
            if not r.verified:
                r.mark_verified()
                print("Build recorded as verified in minimap/learned_builds.json.")
            return 0
        print(f"NO MATCH: the game's address is {s['address']}, the glyphs give {want:016X}.")
        return 1
    finally:
        r.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--watch", type=float, default=0, help="keep sampling every N seconds")
    ap.add_argument("--count", type=int, default=0, help="stop after N samples (with --watch)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--verify-glyphs", metavar="GLYPHS12", help="check an auto-detected build against the glyphs of the system you are in")
    ap.add_argument("--build-info", action="store_true", help="show which build/addresses are in use")
    a = ap.parse_args(argv)
    if a.verify_glyphs:
        return verify_glyphs(a.verify_glyphs)
    if a.build_info:
        r = LiveReader()
        print(json.dumps({"exe": r.exe_path, "sha256": r.exe_sha, "build": r.build, "verified": r.verified, "error": r.build_error},
                         indent=1, default=str))
        r.close()
        return 0
    r = LiveReader()
    try:
        n = 0
        while True:
            s = r.sample()
            if a.json:
                print(json.dumps(s), flush=True)
            elif s is None:
                print("unavailable (game not loaded?)", flush=True)
            else:
                print(f"{s['address']}  x={s['x']:.2f} y={s['y']:.2f} z={s['z']:.2f}", flush=True)
            n += 1
            if a.watch <= 0 or (a.count and n >= a.count):
                return 0
            time.sleep(a.watch)
    finally:
        r.close()


if __name__ == "__main__":
    sys.exit(main())
