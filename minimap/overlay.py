"""Live derelict minimap overlay: a click-through window drawn on top of NMS (stdlib only; Windows).

    python -I minimap/overlay.py [--size 300] [--zoom 3] [--opacity 0.92] [--y-frac 0.36]

You are the fixed dot in the centre; the deck map moves around you (north up, like the viewer).
It shows itself only while NMS is the foreground window and you are at the system's derelict, and hides otherwise.
NMS must run in borderless windowed mode (exclusive fullscreen hides anything drawn over it).

Under the map an info panel shows the derelict's container counts (total and for your room), the hotkeys, and the end
reward, which stays hidden until you press its key (no spoilers by default).

Hotkeys (global; change with --key-*):  F7 zoom in, F8 zoom out, F9 reveal/hide the end reward,
                                        F10 hide/show the info panel (map only), F6 hide/show everything,
                                        Ctrl+Alt+Arrow keys nudge the window (saved in minimap/overlay_config.json).

It never touches the game and needs no server or network: it runs the same read-only memory reader and system
preparation (minimap/core.py State) inside this process. Close the console window (or Ctrl+C) to stop it.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import math
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from ctypes import wintypes
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
sys.path.insert(0, str(HERE))
CONFIG = HERE / "overlay_config.json"
from live_position_705 import find_pid  # noqa: E402
import settings as ST  # noqa: E402
KEY = "#010203"            # transparent colour key
BG = "#0f1318"
PALETTE = ["#4e9be6", "#e6964e", "#5fbf6a", "#d0617d", "#9a7fe0", "#d7c04a", "#46b7b0", "#c9773f", "#7aa0c2",
           "#b06fb0", "#8fb34b", "#e07a6a", "#5c8fd6", "#c4a35a"]
ZOOMS = [9, 14, 20, 30, 44, 64]   # pixels per grid cell at the 300 px size (a cell is 8 m)
PLAYER_EYE = 1.85                 # player origin above the deck floor (m)
GEOM_ROOT = ST.paths()["cache"] / "geom"   # real-geometry renders (minimap/geomrender.py), one folder per derelict and window size


# geometry model: shared with minimap/geomrender.py
from layoutmodel import build_model, cells_of, floor_, round_, to_grid  # noqa: E402,F401


def blend(c1: str, c2: str, t: float) -> str:
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(a[k] * t + b[k] * (1 - t)) for k in range(3))


# ---------------------------------------------------------------- Windows helpers
user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetAncestor.restype = wintypes.HWND
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsIconic.argtypes = [wintypes.HWND]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
user32.EnumWindows.argtypes = [ctypes.c_void_p, wintypes.LPARAM]
user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
VK_NAMES = {"NUMADD": 0x6B, "NUMSUB": 0x6D, "PAGEUP": 0x21, "PAGEDOWN": 0x22, "HOME": 0x24, "END": 0x23,
            "INSERT": 0x2D, "DELETE": 0x2E, "LEFT": 0x25, "UP": 0x26, "RIGHT": 0x27, "DOWN": 0x28}


def parse_key(name: str) -> int:
    n = name.strip().upper()
    if n in VK_NAMES:
        return VK_NAMES[n]
    if n.startswith("F") and n[1:].isdigit() and 1 <= int(n[1:]) <= 24:
        return 0x70 + int(n[1:]) - 1
    if len(n) == 1:
        return ord(n)
    raise SystemExit(f"unknown key {name!r} (use F1-F24, a letter/digit, NUMADD, NUMSUB, PAGEUP, ...)")


def make_click_through(root: tk.Tk) -> None:
    root.update_idletasks()
    hwnd = user32.GetAncestor(wintypes.HWND(root.winfo_id()), 2) or root.winfo_id()
    ex = user32.GetWindowLongPtrW(hwnd, -20)
    # layered + transparent (clicks pass through) + tool window (no taskbar) + no-activate (never takes focus)
    user32.SetWindowLongPtrW(hwnd, -20, ex | 0x80000 | 0x20 | 0x80 | 0x8000000)


def window_pid(hwnd) -> int:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return int(pid.value)


def nms_client_rect(pid: int):
    """(left, top, right, bottom) of NMS's largest visible window client area, or None."""
    best = [None, 0]

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _):
        if window_pid(hwnd) == pid and user32.IsWindowVisible(hwnd) and not user32.IsIconic(hwnd):
            rc = wintypes.RECT()
            user32.GetClientRect(hwnd, ctypes.byref(rc))
            pt = wintypes.POINT(0, 0)
            user32.ClientToScreen(hwnd, ctypes.byref(pt))
            area = rc.right * rc.bottom
            if area > best[1]:
                best[0], best[1] = (pt.x, pt.y, pt.x + rc.right, pt.y + rc.bottom), area
        return True

    user32.EnumWindows(cb, 0)
    return best[0]


def hotkey_thread(keys: dict[str, tuple[int, int]], out: "queue.Queue[str]") -> None:
    ids = {}
    for i, (name, (mod, vk)) in enumerate(keys.items(), 1):
        if user32.RegisterHotKey(None, i, mod, vk):
            ids[i] = name
        else:
            print(f"warning: hotkey for {name} is taken by another program; change it with --key-*", flush=True)
    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        if msg.message == 0x0312 and msg.wParam in ids:
            out.put(ids[msg.wParam])


# ---------------------------------------------------------------- data feed (in-process: no server, no port)
class Feed(threading.Thread):
    """Runs the same read-only reader + system preparation as the browser server (minimap/server.py State), in this process."""

    def __init__(self):
        super().__init__(daemon=True)
        import core as S   # imported late: it pulls in the generator/predictor tools
        self.S = S
        self.state = S.State(live_enabled=True)
        threading.Thread(target=self.state.live_loop, daemon=True).start()
        self.lock = threading.Lock()
        self.live: dict | None = None
        self.model: dict | None = None
        self.model_addr: str | None = None
        self.card: dict | None = None
        self.error: str | None = None

    def run(self) -> None:
        while True:
            try:
                live = self.state.live()
                shown = live.get("shown")
                if live.get("in_shown_system") and shown:
                    sysobj = self.state.system(shown)   # prepares the layout, POI and reward in background threads
                    if shown != self.model_addr and sysobj.derelict:
                        m = build_model(sysobj.derelict)
                        with self.lock:
                            self.model, self.model_addr = m, shown
                    with self.lock:
                        self.card = {"status": sysobj.status, "error": sysobj.error, **sysobj.card} if shown == self.model_addr else None
                with self.lock:
                    self.live, self.error = live, None
            except Exception as exc:
                with self.lock:
                    self.live, self.error = None, repr(exc)
            time.sleep(0.1)

    def snapshot(self):
        with self.lock:
            return self.live, self.model, self.card, self.error


# ---------------------------------------------------------------- overlay window
class Overlay:
    def __init__(self, a, feed: Feed):
        self.a, self.feed = a, feed
        self.cfg = {"dx": 0, "dy": 0, "zoom": a.zoom}
        try:
            self.cfg.update(json.loads(CONFIG.read_text(encoding="utf-8")))
        except Exception:
            pass
        if a.zoom_set:
            self.cfg["zoom"] = a.zoom
        self.zoom = max(0, min(len(ZOOMS) - 1, int(self.cfg["zoom"])))
        self.user_hidden = False
        self.info_on = bool(self.cfg.get("info", True))
        self.show_modules = bool(self.cfg.get("modules", False))   # mark the containers that hold a Salvaged Frigate Module
        self.style = a.style or self.cfg.get("style", "real")      # "real" = the game's own geometry, "schematic" = vector map
        self.geo_jobs: dict = {}      # render folder -> Popen
        self.geo_failed: set = set()
        self.geo_imgs: dict = {}      # (folder, level, zoom) -> PhotoImage
        self.geo_ready: dict = {}     # folder -> True once meta.json exists
        self.geo_t = 0.0
        self.geo_note = ""
        try:                                   # keep the render cache bounded: the 30 newest derelict folders
            old = sorted((d for d in GEOM_ROOT.iterdir() if d.is_dir()), key=lambda d: d.stat().st_mtime, reverse=True)[30:]
            for d in old:
                for f in d.iterdir():
                    f.unlink()
                d.rmdir()
        except OSError:
            pass
        self.warn = None
        self.reveal = False          # end reward: hidden until its key is pressed, again for every derelict
        self.reveal_addr = None
        self.shown = False
        self.rect = None
        self.rect_t = 0.0
        self.top_t = 0.0
        self.nms_pid = 0
        self.last_pos = None
        self.heading = None
        self.hk: "queue.Queue[str]" = queue.Queue()
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.overrideredirect(True)
        self.root.configure(bg=KEY)
        self.root.attributes("-topmost", True, "-transparentcolor", KEY, "-alpha", a.opacity)
        self.size = a.size
        self.cv = tk.Canvas(self.root, width=self.size, height=self.size + self.info_h(), bg=KEY, highlightthickness=0, bd=0)
        self.cv.pack()
        keys = {"in": (0, parse_key(a.key_in)), "out": (0, parse_key(a.key_out)),
                "toggle": (0x4000, parse_key(a.key_toggle)), "reward": (0x4000, parse_key(a.key_reward)),
                "info": (0x4000, parse_key(a.key_info)), "style": (0x4000, parse_key(a.key_style)),
                "modules": (0x4000, parse_key(a.key_modules))}
        for name, vk in (("left", 0x25), ("up", 0x26), ("right", 0x27), ("down", 0x28)):
            keys["nudge-" + name] = (0x1 | 0x2 | 0x4000, vk)   # Alt + Ctrl
        threading.Thread(target=hotkey_thread, args=(keys, self.hk), daemon=True).start()
        self.root.deiconify()
        make_click_through(self.root)
        self.set_visible(False)

    # -- visibility / placement
    def info_h(self) -> int:
        """Height of the info panel under the map (0 when hidden); fixed so the window doesn't jump."""
        return round(118 * self.size / 300) if self.info_on else 0

    def set_visible(self, on: bool) -> None:
        if on != self.shown:
            self.shown = on
            self.root.attributes("-alpha", self.a.opacity if on else 0.0)

    def place(self, rect, msg: bool = False) -> None:
        l, t, r, b = rect
        w, h = r - l, b - t
        k = h / 1080
        s = round(self.a.size * k) if self.a.auto_scale else self.a.size
        self.size = s
        total = round(76 * s / 300) if msg else s + self.info_h()
        x = r - round(w * 0.012) - s + self.cfg["dx"]
        y = t + round(h * self.a.y_frac) + self.cfg["dy"]
        pos = f"{s}x{total}+{x}+{y}"
        if pos != self.last_pos:
            self.last_pos = pos
            self.cv.config(width=s, height=total)
            self.root.geometry(pos)
            self.root.update_idletasks()   # apply the move before any other window attribute call resets it
        elif time.time() - self.top_t > 2:  # games can steal the top spot; re-assert now and then
            self.top_t = time.time()
            self.root.attributes("-topmost", True)

    def save(self) -> None:
        self.cfg["zoom"] = self.zoom
        self.cfg["info"] = self.info_on
        self.cfg["style"] = self.style
        self.cfg["modules"] = self.show_modules
        try:
            CONFIG.write_text(json.dumps(self.cfg), encoding="utf-8")
        except OSError:
            pass

    def hotkeys(self) -> None:
        step = round(20 * self.size / 300)
        while True:
            try:
                k = self.hk.get_nowait()
            except queue.Empty:
                return
            if k == "in":
                self.zoom = min(len(ZOOMS) - 1, self.zoom + 1)
            elif k == "out":
                self.zoom = max(0, self.zoom - 1)
            elif k == "toggle":
                self.user_hidden = not self.user_hidden
            elif k == "reward":
                self.reveal = not self.reveal
            elif k == "info":
                self.info_on = not self.info_on
                self.last_pos = None
            elif k == "modules":
                self.show_modules = not self.show_modules
            elif k == "style":
                self.style = "schematic" if self.style == "real" else "real"
            elif k.startswith("nudge-"):
                dx, dy = {"left": (-step, 0), "right": (step, 0), "up": (0, -step), "down": (0, step)}[k[6:]]
                self.cfg["dx"] += dx
                self.cfg["dy"] += dy
                self.last_pos = None
            self.save()

    # -- frame
    def frame(self) -> None:
        try:
            self.hotkeys()
            live, model, card, err = self.feed.snapshot()
            now = time.time()
            if now - self.rect_t > 1.5:
                self.rect_t = now
                p = find_pid()
                self.nms_pid = p
                self.rect = nms_client_rect(p) if p else None
            fg_ok = bool(self.rect) and (self.a.always_show or window_pid(user32.GetForegroundWindow()) == self.nms_pid)
            here = (live and live.get("connected") and live.get("in_shown_system") and live.get("layout")
                    and (live.get("distance_m") or 1e9) < 200 and model and model["address"] == live.get("shown"))
            self.warn = live.get("build_warning") if live else None
            bad = live.get("build_error") if live else None
            if bad and not getattr(self, "bad_printed", False):
                self.bad_printed = True
                print("WARNING:", bad, flush=True)
            if bad and fg_ok and not self.user_hidden:   # a game update: say so instead of showing nothing
                self.place(self.rect, msg=True)
                self.set_visible(True)
                self.draw_msg()
            elif self.user_hidden or not fg_ok or not here:
                self.set_visible(False)
            else:
                if model["address"] != self.reveal_addr:   # a new derelict: the reward is hidden again
                    self.reveal_addr, self.reveal = model["address"], False
                self.place(self.rect)
                self.set_visible(True)
                self.draw(model, live["layout"], card)
        except Exception as exc:
            print("overlay error:", repr(exc), flush=True)
        self.root.after(66, self.frame)

    # -- real-geometry layer: rendered once per derelict by minimap/geomrender.py in a background process
    def geo_folder(self, addr: str) -> Path:
        return GEOM_ROOT / f"{addr}-s{self.size}-g{self.a.brightness:g}"

    def geo_layer(self, addr: str, level: int, px: float):
        """PhotoImage of the deck at `px` px per cell, or None while it is being rendered / failed (the schematic is drawn then)."""
        d = self.geo_folder(addr)
        k = self.size / 300
        zooms = [round(z * k) for z in ZOOMS]
        if d in self.geo_failed:
            self.geo_note = "schematic (render failed)"
            return None
        if not self.geo_ready.get(d):
            if (d / "meta.json").exists():
                self.geo_ready[d] = True
            else:
                job = self.geo_jobs.get(d)
                if job is None:
                    GEOM_ROOT.mkdir(parents=True, exist_ok=True)
                    log = open(GEOM_ROOT / "render.log", "ab")
                    self.geo_jobs[d] = subprocess.Popen(
                        [sys.executable, "-I", str(HERE / "geomrender.py"), addr, "--zooms", ",".join(map(str, zooms)),
                         "--out", str(d.parent), "--gain", f"{self.a.brightness:g}", "--name", d.name],
                        stdout=log, stderr=log, creationflags=0x08000000 | 0x4000)   # no window, below-normal priority
                elif job.poll() is not None and not (d / "meta.json").exists():
                    self.geo_failed.add(d)
                    print(f"map render failed for {addr} (see {GEOM_ROOT / 'render.log'}); using the schematic", flush=True)
                self.geo_note = "rendering map..."
                return None
        z = int(round(px))
        key = (d, level, z)
        if key not in self.geo_imgs:
            f = d / f"deck{level}_z{z}.ppm"
            try:
                self.geo_imgs[key] = tk.PhotoImage(data=f.read_bytes(), format="ppm")
            except (OSError, tk.TclError):
                self.geo_imgs[key] = None
            if len(self.geo_imgs) > 14:                       # keep memory bounded
                self.geo_imgs.pop(next(iter(self.geo_imgs)))
        self.geo_note = ""
        return self.geo_imgs[key]

    def draw_msg(self) -> None:
        S, k = self.size, self.size / 300
        c = self.cv
        c.delete("all")
        c.create_rectangle(1, 1, S - 1, round(76 * k) - 1, fill=BG, outline="#ff6369", width=2)
        c.create_text(10 * k, 9 * k, anchor="nw", width=S - 20 * k, fill="#ff6369", font=("Segoe UI", max(8, round(10 * k)), "bold"),
                      text="Minimap: unsupported NMS version")
        c.create_text(10 * k, 31 * k, anchor="nw", width=S - 20 * k, fill="#e6e9ec", font=("Segoe UI", max(7, round(8 * k))),
                      text="NMS was updated. The map stays off until the minimap is updated (minimap/README.md, 'After an NMS update').")

    def draw(self, m: dict, lay: list[float], card: dict | None = None) -> None:
        S, k = self.size, self.size / 300
        c = self.cv
        c.delete("all")
        e = m["e"]
        pu, pv, level = to_grid(lay, e)
        level = round_((lay[1] - PLAYER_EYE) / 8) + e[1]
        px = float(round(ZOOMS[self.zoom] * k))        # pixels per cell (whole pixels, so the picture and the markers align)
        cx = cy = S / 2
        sx = lambda u: cx + (pu - u) * px              # noqa: E731  (+x points left, as in the viewer)
        sy = lambda v: cy + (pv - v) * px              # noqa: E731  (entrance at the bottom)
        c.create_rectangle(1, 1, S - 1, S - 1, fill=BG, outline="#3fd0c9", width=2)
        dk = m["decks"].get(level)
        geo = self.geo_layer(m["address"], level, px) if (self.style == "real" and dk) else None
        if self.style != "real":
            self.geo_note = ""
        if geo is not None:     # the game's own geometry, top-down: image column = (13 - u) * px, row = (13 - v) * px
            c.create_image(round(cx + (pu - 13) * px), round(cy + (pv - 13) * px), image=geo, anchor="nw")
        if dk:
            if geo is None:
                for (x, z, r) in dk["cells"]:
                    x0, x1, y0, y1 = sx(x + 1), sx(x), sy(z + 1), sy(z)
                    if x1 < 0 or x0 > S or y1 < 0 or y0 > S:
                        continue
                    c.create_rectangle(x0, y0, x1, y1, fill=blend(PALETTE[r % len(PALETTE)], BG, 0.30), outline="")
                for (u0, v0, u1, v1, r) in dk["edges"]:
                    c.create_line(sx(u0), sy(v0), sx(u1), sy(v1), fill=PALETTE[r % len(PALETTE)], width=max(2, round(2.2 * k)))
            for (u, v, vert, slime) in dk["doors"]:
                h = 0.28
                seg = (sx(u), sy(v - h), sx(u), sy(v + h)) if vert else (sx(u - h), sy(v), sx(u + h), sy(v))
                c.create_line(*seg, fill="#ff8c42" if slime else "#3fd0c9", width=max(3, round(3.5 * k)), capstyle="round")
            for (u, v, d) in dk["marks"]:
                x, y, r = sx(u), sy(v), 0.3 * px
                c.create_rectangle(x - r, y - r * 0.75, x + r, y + r * 0.75, fill=BG, outline="#3fd0c9")
                c.create_text(x, y, text="▼" if d == "v" else "▲", fill="#3fd0c9", font=("Segoe UI", max(6, round(0.32 * px))))
            for (u, v, kind) in dk["boxes"]:
                x, y, r = sx(u), sy(v), max(3, 0.13 * px)
                if kind == 0:
                    c.create_rectangle(x - r, y - r, x + r, y + r, fill="#2d7ab6", outline="#0d2b44")
                elif kind == 1:
                    c.create_oval(x - r, y - r, x + r, y + r, fill="#8a8a85", outline="#2d7ab6", width=2)
                elif kind == 2:
                    c.create_rectangle(x - r * 1.5, y - r * 0.8, x + r * 1.5, y + r * 0.8, fill="#a8a299", outline="#0d0e0d")
                else:
                    c.create_rectangle(x - r * 0.7, y - r * 1.4, x + r * 0.7, y + r * 1.4, fill="#3c3d3e", outline="#009cff", width=2)
            if self.show_modules:
                for mod in (card or {}).get("modules") or []:
                    if mod["level"] == level:
                        self.star(c, sx(mod["u"]), sy(mod["v"]), max(8.0, 0.26 * px), mod["state"])
            if level == e[1]:
                x, y = sx(e[0] + 0.5), sy(e[2]) - 0.15 * px
                c.create_polygon(x, y, x - 0.35 * px, y + 0.5 * px, x + 0.35 * px, y + 0.5 * px, fill="#3fd0c9", outline="")
        # heading from movement (map is north-up; the arrow shows where you are walking)
        if self.last_pos_g is not None and math.hypot(pu - self.last_pos_g[0], pv - self.last_pos_g[1]) > 0.03:
            dx, dy = -(pu - self.last_pos_g[0]), -(pv - self.last_pos_g[1])   # screen direction of travel
            self.heading = math.atan2(dx, -dy)
        self.last_pos_g = (pu, pv)
        r = 6.5 * k
        if self.heading is not None:
            a = self.heading
            tip = (cx + math.sin(a) * r * 2.3, cy - math.cos(a) * r * 2.3)
            l_ = (cx + math.sin(a + 2.5) * r * 1.4, cy - math.cos(a + 2.5) * r * 1.4)
            rr = (cx + math.sin(a - 2.5) * r * 1.4, cy - math.cos(a - 2.5) * r * 1.4)
            c.create_polygon(*tip, *l_, *rr, fill="#ff6369", outline="")
        c.create_oval(cx - r, cy - r, cx + r, cy + r, fill="#ff6369", outline="#ffffff", width=2)
        if self.geo_note:
            c.create_text(S - 8 * k, 22 * k if self.warn else 8 * k, anchor="ne", fill="#9aa3ab", font=("Segoe UI", max(7, round(8 * k))),
                          text=self.geo_note)
        if self.warn:   # addresses were auto-detected after a game update and not yet verified
            c.create_text(S - 8 * k, 8 * k, anchor="ne", fill="#ffb454", font=("Segoe UI", max(7, round(8 * k)), "bold"),
                          text="auto-detected addresses (unverified)")
        room = m["owner"].get((floor_(pu), level, floor_(pv)))
        deck_no = m["levels"].index(level) + 1 if level in m["levels"] else "?"
        label = f"Deck {deck_no}" + (f" · room {room}" if room is not None else "")
        c.create_text(8 * k, S - 8 * k, text=label, anchor="sw", fill="#e6e9ec", font=("Segoe UI", max(8, round(9 * k)), "bold"))
        if self.info_on:
            self.draw_info(m, card, room, S, k)

    @staticmethod
    def star(c, x: float, y: float, r: float, state: str) -> None:
        """Gold star over a container: filled = a Salvaged Frigate Module (certain), pale = likely, hollow = possible."""
        pts = []
        for i in range(10):
            a = -math.pi / 2 + i * math.pi / 5
            rr = r if i % 2 == 0 else r * 0.45
            pts += [x + rr * math.cos(a), y + rr * math.sin(a)]
        fill = {"certain": "#ffcc33", "likely": "#ffe58a", "possible": ""}.get(state, "#ffcc33")
        c.create_polygon(*pts, fill=fill, outline="#3a2a00" if fill else "#ffcc33", width=2 if not fill else 1)

    def draw_info(self, m: dict, card: dict | None, room, S: int, k: float) -> None:
        """Panel under the map: container counts (all / this room), end reward (only when revealed), hotkeys."""
        c, H = self.cv, self.info_h()
        c.create_rectangle(1, S, S - 1, S + H - 1, fill=BG, outline="#3fd0c9", width=2)   # also covers map overflow
        f = ("Segoe UI", max(8, round(10 * k)), "bold")
        fs = ("Segoe UI", max(7, round(8 * k)))
        row = 24 * k

        def counts(y: float, label: str, n: list[int]) -> None:
            c.create_text(8 * k, y, text=label, anchor="w", fill="#9aa3ab", font=fs)
            x = 62 * k
            for kind, v in enumerate(n):
                r = 6 * k
                if kind == 0:
                    c.create_rectangle(x, y - r, x + 2 * r, y + r, fill="#2d7ab6", outline="#0d2b44")
                elif kind == 1:
                    c.create_oval(x, y - r, x + 2 * r, y + r, fill="#8a8a85", outline="#2d7ab6", width=2)
                elif kind == 2:
                    c.create_rectangle(x - 1, y - r * 0.6, x + 2 * r + 1, y + r * 0.6, fill="#a8a299", outline="#0d0e0d")
                else:
                    c.create_rectangle(x + r * 0.4, y - r, x + r * 1.6, y + r, fill="#3c3d3e", outline="#009cff", width=2)
                c.create_text(x + 2 * r + 4 * k, y, text=str(v), anchor="w", fill="#e6e9ec", font=f)
                x += 58 * k

        y = S + 14 * k
        counts(y, "All", m["totals"])
        counts(y + row * 0.85, f"Room {room}" if room is not None else "Room –", m["per_room"].get(room, [0, 0, 0, 0]))
        y += 2 * row * 0.85
        rw = (card or {}).get("reward")
        if not self.reveal:
            c.create_text(8 * k, y, text=f"End reward: hidden   ({self.a.key_reward.upper()} to show)", anchor="w", fill="#9aa3ab", font=fs)
        elif rw and rw.get("name"):
            cls = rw.get("class", "?")
            col = {"S": "#f5c542", "A": "#b88cff", "B": "#6aa8ff", "C": "#8fc98f"}.get(cls, "#cccccc")
            c.create_rectangle(8 * k, y - 8 * k, 26 * k, y + 8 * k, fill=col, outline="")
            c.create_text(17 * k, y, text=cls, fill=BG, font=f)
            c.create_text(32 * k, y, text=rw["name"] + ("  (uncertain)" if rw.get("ambiguous") else ""), anchor="w", fill="#e6e9ec", font=f)
        else:
            msg = "working it out…" if not card or card.get("status") not in ("ready", "error") else "unknown for this system"
            c.create_text(8 * k, y, text=f"End reward: {msg}", anchor="w", fill="#9aa3ab", font=fs)
        y += row * 0.85                                   # salvaged frigate modules (95,000 units each)
        mods = (card or {}).get("modules")
        if not self.show_modules:
            c.create_text(8 * k, y, text=f"Frigate modules: hidden   ({self.a.key_modules.upper()} to show)", anchor="w", fill="#9aa3ab", font=fs)
        elif mods is None:
            c.create_text(8 * k, y, text="Frigate modules: unknown here" if card and card.get("status") in ("ready", "error")
                          else "Frigate modules: working it out…", anchor="w", fill="#9aa3ab", font=fs)
        else:
            sure = sum(1 for q in mods if q["state"] == "certain")
            unsure = len(mods) - sure
            self.star(c, 17 * k, y, 8 * k, "certain" if sure else "possible")
            txt = (f"{sure} salvaged frigate module" + ("" if sure == 1 else "s")) if (sure or not unsure) else "no sure module"
            if unsure:
                txt += f"  (+{unsure} uncertain)"
            c.create_text(32 * k, y, text=txt, anchor="w", fill="#e6e9ec", font=f)
        a = self.a
        c.create_text(8 * k, S + H - 20 * k, anchor="w", fill="#9aa3ab", font=fs,
                      text=f"{a.key_in.upper()}/{a.key_out.upper()} zoom   {a.key_reward.upper()} reward   {a.key_modules.upper()} frigate modules")
        c.create_text(8 * k, S + H - 8 * k, anchor="w", fill="#9aa3ab", font=fs,
                      text=f"{a.key_info.upper()} info   {a.key_style.upper()} map style   {a.key_toggle.upper()} hide all")

    last_pos_g = None

    def run(self) -> None:
        self.root.after(100, self.frame)
        self.root.mainloop()


# ---------------------------------------------------------------- main
def main(argv=None) -> int:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)   # physical pixels, so window rects and drawing agree
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Live derelict minimap overlay for NMS")
    ap.add_argument("--size", type=int, default=300, help="window size in px at 1080p (scales with the game window)")
    ap.add_argument("--no-auto-scale", dest="auto_scale", action="store_false")
    ap.add_argument("--zoom", type=int, default=3, help=f"start zoom 0-{len(ZOOMS) - 1}")
    ap.add_argument("--opacity", type=float, default=0.92)
    ap.add_argument("--y-frac", type=float, default=0.36, help="top of the window as a fraction of the game height")
    ap.add_argument("--always-show", action="store_true", help="test: show even when NMS is not the foreground window")
    ap.add_argument("--key-in", default="F7")
    ap.add_argument("--key-out", default="F8")
    ap.add_argument("--key-toggle", default="F6")
    ap.add_argument("--key-reward", default="F9", help="show/hide the end reward (hidden by default)")
    ap.add_argument("--key-info", default="F10", help="show/hide the info panel (map only when hidden)")
    ap.add_argument("--key-modules", default="F5", help="show/hide the Salvaged Frigate Module marks on the map")
    ap.add_argument("--key-style", default="F11", help="switch between the game's real geometry and the schematic map")
    ap.add_argument("--style", choices=("real", "schematic"), help="map style (default: the last one used, else real)")
    ap.add_argument("--brightness", type=float, default=1.3, help="brightness boost of the real-geometry map")
    a = ap.parse_args(argv)
    a.zoom_set = any(x.startswith("--zoom") for x in (argv if argv is not None else sys.argv[1:]))
    feed = Feed()
    feed.start()
    ov = Overlay(a, feed)
    print(f"Minimap overlay running. {a.key_in}/{a.key_out} zoom, {a.key_reward} end reward, {a.key_info} hide info, "
          f"{a.key_style} map style, {a.key_modules} frigate modules, {a.key_toggle} hide all, Ctrl+Alt+arrows move. Needs NMS in borderless windowed mode.", flush=True)
    try:
        ov.run()
    except KeyboardInterrupt:
        pass
    finally:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
