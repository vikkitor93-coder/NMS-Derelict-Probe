"""Always-on-top status banner for NMS Derelict Surveyor.

Runs as a separate local process. It reads the probe's local live-status JSON and
never reads/writes No Man's Sky memory or save data. Opacity, position and display
sections are controlled by Surveyor and read from a local settings file.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

OVERLAY_VERSION = "0.3.27"
STATUS_STALE_SECONDS = 3.0
POLL_MS = 200
WINDOW_TITLE_FRAGMENT = "no man's sky"
ROOT_RESOURCE_PATH = "MODELS/SPACE/POI/DUNGEON.SCENE.MBIN"


def _default_status_path() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    root = Path(local) if local else Path.home()
    return root / "NMSDerelictSurveyor" / "live-status.json"


def _safe_load(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as fh:
            value = json.load(fh)
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


DEFAULT_VIEW_SETTINGS = {
    "show_rooms": True,
    "show_research": False,
    "show_position": False,
    "show_manual": False,
    "show_hotkeys": False,
    "show_objectives": True,
    "opacity_percent": 82,
    "x_offset": 0,
    "y_offset": 18,
}


def _settings_path(status_path: Path) -> Path:
    return status_path.with_name("overlay-settings.json")


def load_overlay_settings(path: Path) -> dict[str, Any]:
    value = _safe_load(path) or {}
    result = {key: bool(value.get(key, default)) for key, default in DEFAULT_VIEW_SETTINGS.items() if key.startswith("show_")}
    for key, low, high in (("opacity_percent", 20, 100), ("x_offset", -800, 800), ("y_offset", -500, 600)):
        try:
            result[key] = max(low, min(high, int(value.get(key, DEFAULT_VIEW_SETTINGS[key]))))
        except (TypeError, ValueError):
            result[key] = DEFAULT_VIEW_SETTINGS[key]
    return result


def save_overlay_settings(path: Path, settings: dict[str, Any]):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass


def build_agent_objectives(snapshot: dict[str, Any] | None, live_status: dict[str, Any] | None, nms_running: bool) -> dict[str, Any]:
    """Prepare concise, truthful lane objectives and runtime milestones for the game banner."""
    lanes = (snapshot or {}).get("lanes") or []
    live = live_status or {}
    generation = live.get("generation_rooms") if isinstance(live.get("generation_rooms"), dict) else {}
    root_seen = bool(
        int(generation.get("dungeon_root_resource_events_seen") or 0)
        or generation.get("last_dungeon_root_seed_hex")
        or generation.get("last_dungeon_logical_entry_exact_external_caller_offset_hex")
    )
    dispatch = live.get("root_dispatch_capture") if isinstance(live.get("root_dispatch_capture"), dict) else {}
    dispatch_captured = bool(dispatch.get("captured") or dispatch.get("target_offset_hex"))
    objectives = []
    for lane in lanes[:4]:
        if not isinstance(lane, dict):
            continue
        name = str(lane.get("name") or lane.get("id") or "Agent")
        required = bool(lane.get("human_required"))
        steps = lane.get("steps") if isinstance(lane.get("steps"), list) else []
        objective = str(lane.get("surveyor_request") or lane.get("next_action") or (steps[0] if steps else "") or lane.get("status") or "No current Surveyor objective").strip()
        objective = " ".join(objective.split())
        if len(objective) > 190:
            objective = objective[:187].rstrip() + "…"
        status = "NO SURVEYOR ACTION · " + str(lane.get("status") or "agent working") if not required else "SURVEYOR ACTION REQUIRED"
        complete = False
        keep_game_open = False
        root_related = any(word in objective.lower() for word in ("root", "derelict", "dungeon", "room", "crate", "dispatch"))
        needs_dispatch = "dispatch" in objective.lower() or "+0x10" in objective.lower() or "0x10" in objective.lower()
        if required and root_related:
            if needs_dispatch:
                if dispatch_captured:
                    status = "ROOT DISPATCH +0x10 CAPTURED · OBJECTIVE COMPLETE · WAITING FOR UPLOAD · DON'T CLOSE GAME"
                    complete = True
                    keep_game_open = True
                elif root_seen:
                    status = "ROOT RESOURCE DETECTED · +0x10 DISPATCH STILL NEEDED"
                    keep_game_open = bool(nms_running)
                else:
                    status = "NMS RUNNING · WAITING FOR ROOT DISPATCH +0x10" if nms_running else "WAITING FOR NMS / ROOT DISPATCH +0x10"
            elif root_seen:
                status = "ROOT DETECTED · OBJECTIVE COMPLETE · WAITING FOR UPLOAD · DON'T CLOSE GAME"
                complete = True
                keep_game_open = True
            else:
                status = "NMS RUNNING · WAITING FOR ROOT RESOURCE" if nms_running else "WAITING FOR NMS / ROOT RESOURCE"
        objectives.append({"lane_id":str(lane.get("id") or ""),"name":name,"objective":objective or "No current Surveyor objective","status":status,"complete":complete,"keep_game_open":keep_game_open})
    return {"schema_version":1,"updated_epoch":time.time(),"objectives":objectives}


def _write_overlay_state(path: Path, pid: int, heartbeat_epoch: float):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps({"pid": pid, "heartbeat_epoch": heartbeat_epoch}) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass


def _friendly_family(value: Any, kind: str) -> str:
    if kind == "dead_end":
        return "DEAD END"
    name = str(value or "ROOM").upper()
    return {"CARG": "CARGO", "BARRACKS": "BARRACKS", "HANGAR": "HANGAR", "END": "FINAL"}.get(name, name)


def format_room_loot(gen_data: dict[str, Any], recording: bool) -> tuple[str, str]:
    rooms = gen_data.get("rooms") if isinstance(gen_data.get("rooms"), list) else []
    index_status = str(gen_data.get("crate_index_status") or "")
    if index_status != "ready":
        if recording:
            return (
                "ROOM LOOT unavailable · run Prepare-Crate-Assets.cmd once",
                "The recorder is still working; only the local scene→crate index is missing.",
            )
        return "ROOM LOOT waiting", ""
    salvage = int(gen_data.get("salvage_crates_seen") or 0)
    foot = int(gen_data.get("crew_footlockers_seen") or 0)
    total = int(gen_data.get("target_containers_seen") or 0)
    room_count = len(rooms)
    prefix = "LOOT SEEN" if recording else "LAST LOOT"
    summary = f"{prefix} {total}   SALVAGE {salvage}   FOOTLOCKERS {foot}   ROOMS {room_count}"
    lines=[]
    for row in rooms:
        idx = row.get("room_index")
        label = f"R{idx}" if idx is not None else "R?"
        kind = str(row.get("room_kind") or "main_room")
        family = _friendly_family(row.get("dominant_family"), kind)
        r_salvage = int(row.get("salvage_crates") or 0)
        r_foot = int(row.get("crew_footlockers") or 0)
        r_total = int(row.get("target_containers") or 0)
        lines.append(f"{label:<3} {family:<10} {r_total:>2}   (salvage {r_salvage:>2} + lockers {r_foot:>2})")
    return summary, "\n".join(lines)


def summarize_status(
    status: dict[str, Any] | None,
    now_epoch: float | None = None,
    nms_running: bool = False,
) -> dict[str, str]:
    """Convert raw live-status data into the strings rendered by the overlay."""
    now = time.time() if now_epoch is None else now_epoch
    hotkey_line_1 = "F5 ROOM 0 / DEAD END   F6 ROOM   F7 CRATE"
    hotkey_line_2 = "F8 STAIRS/VERTICAL   F9 HANGAR   F10 ENGINEERING   F11 MODULE C-S"
    nms_line = "Running" if nms_running else "Not running"
    if not status:
        return {
            "state": "waiting",
            "nms": nms_line,
            "probe": "Waiting for probe heartbeat" if nms_running else "Offline — Start NMS when needed",
            "capture": "Unknown" if nms_running else "Not recording",
            "caller_scan": "Armed — starts when probe connects" if nms_running else "Armed — all callers at once",
            "exact_root_caller": "Waiting for probe" if nms_running else "Not captured",
            "root_resource": f"{ROOT_RESOURCE_PATH} · waiting for probe",
            "root_dispatch": "Not captured by this probe build · Runtime-A hook required",
            "headline": "DERELICT SURVEYOR · WAITING FOR PROBE",
            "detail": "Start NMS through Start-Derelict-Probe.cmd",
            "telemetry": "POS unavailable · SOURCE waiting",
            "counts": "",
            "auto_crates": "AUTO TARGET ? · waiting for session",
            "loot_summary": "ROOM LOOT waiting",
            "room_loot": "",
            "trace": "TRACE waiting",
            "generation": "GEN ROOMS ? · MAIN ? · DEAD END ? · POI SEED ?",
            "event": "",
            "hotkeys_1": hotkey_line_1,
            "hotkeys_2": hotkey_line_2,
        }

    heartbeat = float(status.get("heartbeat_epoch") or 0.0)
    if heartbeat <= 0 or now - heartbeat > STATUS_STALE_SECONDS:
        return {
            "state": "stale",
            "nms": nms_line,
            "probe": "Heartbeat lost" if nms_running else "Offline — Start NMS when needed",
            "capture": "Unknown",
            "caller_scan": "Probe heartbeat lost" if nms_running else "Armed — all callers at once",
            "exact_root_caller": "Waiting for probe" if nms_running else "Not captured",
            "root_resource": f"{ROOT_RESOURCE_PATH} · probe heartbeat lost",
            "root_dispatch": "Not captured by this probe build · Runtime-A hook required",
            "headline": "DERELICT SURVEYOR · PROBE HEARTBEAT LOST",
            "detail": "NMS may still be starting, closing, or the runtime hook may need attention",
            "telemetry": "POS stale · SOURCE unavailable",
            "counts": "",
            "auto_crates": "AUTO TARGET ? · probe stale",
            "loot_summary": "ROOM LOOT stale",
            "room_loot": "",
            "trace": "TRACE stale",
            "generation": "GEN ROOMS ? · probe stale",
            "event": str(status.get("last_event") or ""),
            "hotkeys_1": hotkey_line_1,
            "hotkeys_2": hotkey_line_2,
        }

    state = str(status.get("state") or "ready")
    version = str(status.get("probe_version") or "?")
    recording = bool(status.get("recording"))
    generation_status = status.get("generation_rooms") if isinstance(status.get("generation_rooms"), dict) else {}
    root_resource_count = int(generation_status.get("dungeon_root_resource_events_seen") or 0)
    root_resource = (
        f"{ROOT_RESOURCE_PATH} · observed {root_resource_count}"
        if root_resource_count else f"{ROOT_RESOURCE_PATH} · not observed yet"
    )
    exact_caller = generation_status.get("last_dungeon_logical_entry_exact_external_caller_offset_hex")
    fallback_caller = generation_status.get("last_dungeon_logical_entry_caller_offset_hex")
    seen_callers = int(generation_status.get("logical_entry_unique_callers_observed") or 0)
    known_callers = int(generation_status.get("logical_entry_known_candidate_hits") or 0)
    candidate_count = int(generation_status.get("logical_entry_candidate_count") or 52)
    caller_scan = f"Watching all {candidate_count} refs — {seen_callers} callers observed ({known_callers} known)"
    exact_root_caller = (
        f"{exact_caller} — exact external match" if exact_caller else
        (f"{fallback_caller} — awaiting external match" if fallback_caller else "Not captured")
    )
    if recording:
        headline = f"DERELICT SURVEYOR v{version} · RECORDING"
    elif state == "saved":
        headline = f"DERELICT SURVEYOR v{version} · SAVED / READY"
    else:
        headline = f"DERELICT SURVEYOR v{version} · LOADED & READY"

    position = status.get("position")
    source = str(status.get("position_source") or "unavailable")
    if isinstance(position, dict):
        try:
            telemetry = (
                f"X {float(position.get('x', 0.0)):.3f}   "
                f"Y {float(position.get('y', 0.0)):.3f}   "
                f"Z {float(position.get('z', 0.0)):.3f}   "
                f"· SOURCE {source}"
            )
        except (TypeError, ValueError):
            telemetry = f"POS invalid · SOURCE {source}"
    else:
        telemetry = f"POS unavailable · SOURCE {source}"

    trace_data = status.get("trace") if isinstance(status.get("trace"), dict) else {}
    trace_line = (
        f"TRACE RES {int(trace_data.get('resource_events') or 0)}   "
        f"REWARD {int(trace_data.get('reward_events') or 0)}   "
        f"SEEDS {int(trace_data.get('unique_seed_count') or 0)}"
    )
    last_seed = str(trace_data.get("last_seed_hex") or "")
    if last_seed:
        trace_line += f"   LAST {last_seed}"

    gen_data = status.get("generation_rooms") if isinstance(status.get("generation_rooms"), dict) else {}
    gen_total = int(gen_data.get("total_rooms_seen") or 0)
    gen_main = int(gen_data.get("main_rooms_seen") or 0)
    gen_dead = int(gen_data.get("dead_end_rooms_seen") or 0)
    parent_named = int(gen_data.get("room_parent_names_seen") or 0)
    poi_candidates = gen_data.get("poi_context_arguments") if isinstance(gen_data.get("poi_context_arguments"), list) else []
    if not poi_candidates:
        poi_candidates = gen_data.get("poi_seed_candidates") if isinstance(gen_data.get("poi_seed_candidates"), list) else []
    generation_line = f"GEN ROOMS {gen_total}   MAIN {gen_main}   DEAD END {gen_dead}   PARENT-NAMED {parent_named}"
    if poi_candidates:
        label = "POI-UA" if bool(gen_data.get("poi_context_matches_universe_address")) else "POI-CTX"
        generation_line += f"   {label} {str(poi_candidates[-1])}"
    poi_return = str(gen_data.get("last_poi_description_return_hex") or "")
    if poi_return:
        generation_line += f"   POI-RET {poi_return}"
    dungeon_seed = str(gen_data.get("last_dungeon_root_seed_hex") or "")
    if dungeon_seed:
        generation_line += f"   DUNGEON-SEED {dungeon_seed}"

    loot_summary, room_loot = format_room_loot(gen_data, recording)

    auto_data = status.get("auto_crates") if isinstance(status.get("auto_crates"), dict) else {}
    auto_count = int(auto_data.get("count") or 0)
    auto_status = str(auto_data.get("status") or ("waiting-for-node-signal" if recording else "inactive"))
    auto_method = str(auto_data.get("method") or "none")
    salvage_count = int(auto_data.get("salvage_crates") or 0)
    footlocker_count = int(auto_data.get("crew_footlockers") or 0)
    scene_probe_events = int(auto_data.get("scene_probe_events") or 0)
    resolved_resources = int(auto_data.get("resolved_resource_names") or 0)
    resource_index_size = int(auto_data.get("resource_index_size") or 0)
    resource_find_events = int(auto_data.get("resource_find_events") or 0)
    resource_find_mapped = int(auto_data.get("resource_find_mapped") or 0)
    breakdown = f"SALVAGE {salvage_count}   FOOTLOCKER {footlocker_count}"
    probe_diag = (
        f"RAW {scene_probe_events}   RESOLVED {resolved_resources}   INDEX {resource_index_size}   "
        f"FINDMAP {resource_find_mapped}"
    )
    if auto_status == "live":
        auto_line = f"AUTO TARGET {auto_count} · {breakdown} · LIVE · {auto_method}"
    elif auto_status == "saved":
        auto_line = f"AUTO TARGET {auto_count} · {breakdown} · SAVED · {auto_method}"
    elif auto_status == "embedded-in-room-scenes":
        auto_line = f"AUTO TARGET ? · EMBEDDED IN ROOM SCENES · {probe_diag}"
    elif auto_status == "scanning":
        auto_line = f"AUTO TARGET {auto_count} · {breakdown} · SCANNING · {probe_diag}"
    elif recording:
        auto_line = f"AUTO TARGET ? · SALVAGE ?   FOOTLOCKER ? · WAITING · {probe_diag}"
    else:
        auto_line = "AUTO TARGET ? · enter a derelict to scan"

    counts = ""
    if recording:
        counts = (
            f"CRATES {int(status.get('blue_crates') or 0)}   "
            f"ROOMS {int(status.get('rooms') or 0)}   "
            f"ROOM 0 {int(status.get('room_zero_rooms') or 0)}   "
            f"VERTICAL {int(status.get('vertical_transitions') or 0)}   "
            f"HANGAR {int(status.get('shuttle_bays') or 0)}   "
            f"ENG {'YES' if status.get('engineering_marked') else 'NO'}   "
            f"MODULE {str(status.get('engineering_module_class') or 'unknown').upper()}"
        )
    dispatch = status.get("root_dispatch_capture") if isinstance(status.get("root_dispatch_capture"), dict) else {}
    if dispatch.get("captured"):
        slot_value = str(dispatch.get("slot_value_hex") or "captured")
        target = dispatch.get("target_identity") if isinstance(dispatch.get("target_identity"), dict) else {}
        module_rva = str(target.get("module_rva_hex") or "")
        target_address = str(target.get("address_hex") or "")
        target_label = f"NMS+{module_rva}" if module_rva else (target_address or str(target.get("status") or "identity unavailable"))
        root_dispatch = f"CAPTURED {slot_value} -> {target_label}"
    elif dispatch.get("read_status") == "unreadable":
        root_dispatch = "Root matched · owner+0x10 unreadable"
    else:
        root_dispatch = "Not captured by this probe build · Runtime-A hook required"
    return {
        "state": state,
        "nms": nms_line,
        "probe": f"Connected — probe {version}" if nms_running else f"Probe {version} heartbeat present",
        "capture": "Recording" if recording else "Ready",
        "caller_scan": caller_scan,
        "exact_root_caller": exact_root_caller,
        "root_resource": root_resource,
        "root_dispatch": root_dispatch,
        "headline": headline,
        "detail": str(status.get("detail") or "Enter a derelict freighter to start recording automatically"),
        "telemetry": telemetry,
        "counts": counts,
        "auto_crates": auto_line,
        "loot_summary": loot_summary,
        "room_loot": room_loot,
        "trace": trace_line,
        "generation": generation_line,
        "event": str(status.get("last_event") or ""),
        "hotkeys_1": hotkey_line_1,
        "hotkeys_2": hotkey_line_2,
    }


def _windows_only():
    if os.name != "nt":
        raise RuntimeError("The overlay requires Windows.")


class Win32WindowTracker:
    def __init__(self):
        _windows_only()
        self.user32 = ctypes.windll.user32
        self.kernel32 = ctypes.windll.kernel32
        self._seen_game = False

    def find_game_window(self, preferred_pid: int | None = None) -> int | None:
        matches: list[tuple[int, str, int]] = []
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        @WNDENUMPROC
        def callback(hwnd, _lparam):
            if not self.user32.IsWindowVisible(hwnd):
                return True
            length = self.user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            self.user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value
            pid = ctypes.c_ulong()
            self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if (preferred_pid and pid.value == preferred_pid) or WINDOW_TITLE_FRAGMENT in title.lower():
                matches.append((int(hwnd), title, int(pid.value)))
            return True

        self.user32.EnumWindows(callback, 0)
        if not matches:
            return None
        if preferred_pid:
            for hwnd, _title, pid in matches:
                if pid == preferred_pid:
                    self._seen_game = True
                    return hwnd
        self._seen_game = True
        return matches[0][0]

    def client_rect_screen(self, hwnd: int) -> tuple[int, int, int, int] | None:
        class RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        rect = RECT()
        if not self.user32.GetClientRect(hwnd, ctypes.byref(rect)):
            return None
        point = POINT(0, 0)
        if not self.user32.ClientToScreen(hwnd, ctypes.byref(point)):
            return None
        width = max(1, int(rect.right - rect.left))
        height = max(1, int(rect.bottom - rect.top))
        return int(point.x), int(point.y), width, height

    def is_game_foreground(self, hwnd: int) -> bool:
        """True only when the foreground window belongs to the detected NMS process."""
        foreground = int(self.user32.GetForegroundWindow() or 0)
        if not foreground:
            return False
        foreground_pid = ctypes.c_ulong()
        game_pid = ctypes.c_ulong()
        self.user32.GetWindowThreadProcessId(foreground, ctypes.byref(foreground_pid))
        self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(game_pid))
        return _same_process_is_foreground(int(game_pid.value), int(foreground_pid.value))

    @property
    def seen_game(self) -> bool:
        return self._seen_game


def _same_process_is_foreground(game_pid: int, foreground_pid: int) -> bool:
    return bool(game_pid > 0 and foreground_pid > 0 and game_pid == foreground_pid)


def _apply_safe_window_style(hwnd: int):
    """Apply non-activating helper-window flags; Tk controls opacity separately."""
    if os.name != "nt":
        return
    user32 = ctypes.windll.user32
    GWL_EXSTYLE = -20
    WS_EX_TOOLWINDOW = 0x00000080
    WS_EX_NOACTIVATE = 0x08000000
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongW(
        hwnd,
        GWL_EXSTYLE,
        style | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
    )


def _acquire_mutex() -> Any:
    if os.name != "nt":
        return None
    ERROR_ALREADY_EXISTS = 183
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateMutexW(None, False, "Local\\NMSDerelictSurveyorOverlay_v1")
    if handle and kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        return False
    return handle


def run_overlay(status_path: Path, stop_path: Path | None = None):
    _windows_only()
    mutex = _acquire_mutex()
    if mutex is False:
        return

    import tkinter as tk

    tracker = Win32WindowTracker()
    root = tk.Tk()
    root.title("NMS Derelict Surveyor Overlay")
    root.overrideredirect(True)
    root.attributes("-topmost", False)
    root.configure(bg="#101418")

    settings_path = _settings_path(status_path)
    stop_path = stop_path or status_path.with_name("overlay-stop.request")
    state_path = status_path.with_name("overlay-state.json")
    saved_settings = load_overlay_settings(settings_path)
    applied_settings = dict(saved_settings)

    frame = tk.Frame(root, bg="#101418", bd=0, highlightthickness=1, highlightbackground="#56616a")
    frame.pack(fill="both", expand=True)
    frame.grid_columnconfigure(0, weight=1)

    headline = tk.Label(frame, text="DERELICT SURVEYOR · WAITING FOR PROBE", fg="#dce8ef", bg="#101418", font=("Segoe UI", 11, "bold"))
    headline.grid(row=0, column=0, padx=14, pady=(8, 1), sticky="ew")
    detail = tk.Label(frame, text="Starting…", fg="#aebbc4", bg="#101418", font=("Segoe UI", 9))
    detail.grid(row=1, column=0, padx=14, pady=(0, 2), sticky="ew")
    runtime = tk.Label(frame, text="NMS · Probe · Capture", fg="#d8e1e8", bg="#101418", font=("Consolas", 9, "bold"))
    runtime.grid(row=2, column=0, padx=14, pady=(0, 1), sticky="ew")
    callers = tk.Label(frame, text="Caller scan · Exact root caller", fg="#e7c6ff", bg="#101418", font=("Consolas", 9, "bold"))
    callers.grid(row=3, column=0, padx=14, pady=(0, 3), sticky="ew")
    root_resource_label = tk.Label(frame, text="Root resource waiting", fg="#c6d9ef", bg="#101418", font=("Consolas", 8, "bold"))
    root_resource_label.grid(row=4, column=0, padx=14, pady=(0, 1), sticky="ew")
    dispatch_label = tk.Label(frame, text="Root dispatch +0x10 · not captured", fg="#efc7a2", bg="#101418", font=("Consolas", 8, "bold"))
    dispatch_label.grid(row=5, column=0, padx=14, pady=(0, 3), sticky="ew")

    def apply_visibility(settings: dict[str, Any]):
        sections = [
            (objectives_header, settings["show_objectives"]),
            *((label, settings["show_objectives"]) for label in objective_labels),
            (room_loot, settings["show_rooms"]),
            (telemetry, settings["show_position"]),
            (counts, settings["show_manual"]),
            (auto_crates, settings["show_research"]),
            (trace, settings["show_research"]),
            (generation, settings["show_research"]),
            (hotkeys1, settings["show_hotkeys"]),
            (hotkeys2, settings["show_hotkeys"]),
        ]
        for widget, visible in sections:
            if visible:
                widget.grid()
            else:
                widget.grid_remove()
    objectives_header = tk.Label(frame, text="AGENT OBJECTIVES", fg="#bfe8bf", bg="#101418", font=("Segoe UI", 10, "bold"))
    objectives_header.grid(row=6, column=0, padx=14, pady=(2, 0), sticky="w")
    objective_labels = []
    for idx in range(4):
        label = tk.Label(frame, text="Waiting for agent status…", fg="#d8e1e8", bg="#101418", font=("Segoe UI", 9), justify="left", anchor="w", wraplength=850)
        label.grid(row=7 + idx, column=0, padx=14, pady=(0, 2), sticky="ew")
        objective_labels.append(label)

    loot_summary = tk.Label(frame, text="ROOM LOOT waiting", fg="#b7efb0", bg="#101418", font=("Consolas", 10, "bold"))
    loot_summary.grid(row=11, column=0, padx=14, pady=(1, 1), sticky="ew")
    room_loot = tk.Label(frame, text="", fg="#d8f5d3", bg="#101418", font=("Consolas", 9, "bold"), justify="left", anchor="w")
    room_loot.grid(row=12, column=0, padx=18, pady=(0, 3), sticky="w")
    telemetry = tk.Label(frame, text="POS unavailable", fg="#8fd4ff", bg="#101418", font=("Consolas", 10, "bold"))
    telemetry.grid(row=13, column=0, padx=14, pady=(1, 1), sticky="ew")
    counts = tk.Label(frame, text="", fg="#ffffff", bg="#101418", font=("Consolas", 10, "bold"))
    counts.grid(row=14, column=0, padx=14, pady=(0, 1), sticky="ew")
    auto_crates = tk.Label(frame, text="AUTO TARGET ?", fg="#b7efb0", bg="#101418", font=("Consolas", 9, "bold"))
    auto_crates.grid(row=15, column=0, padx=14, pady=(0, 1), sticky="ew")
    trace = tk.Label(frame, text="TRACE waiting", fg="#f0d58a", bg="#101418", font=("Consolas", 9, "bold"))
    trace.grid(row=16, column=0, padx=14, pady=(0, 1), sticky="ew")
    generation = tk.Label(frame, text="GEN ROOMS ?", fg="#e7c6ff", bg="#101418", font=("Consolas", 9, "bold"))
    generation.grid(row=17, column=0, padx=14, pady=(0, 1), sticky="ew")
    event = tk.Label(frame, text="", fg="#d7e6b3", bg="#101418", font=("Segoe UI", 9, "bold"))
    event.grid(row=18, column=0, padx=14, pady=(0, 3), sticky="ew")
    hotkeys1 = tk.Label(frame, text="F5 ROOM 0 / DEAD END   F6 ROOM   F7 CRATE", fg="#c6cbd0", bg="#101418", font=("Consolas", 9, "bold"))
    hotkeys1.grid(row=19, column=0, padx=14, pady=(2, 0), sticky="ew")
    hotkeys2 = tk.Label(frame, text="F8 STAIRS/VERTICAL   F9 HANGAR   F10 ENGINEERING   F11 MODULE C-S", fg="#c6cbd0", bg="#101418", font=("Consolas", 9, "bold"))
    hotkeys2.grid(row=20, column=0, padx=14, pady=(0, 8), sticky="ew")

    apply_visibility(saved_settings)
    root.attributes("-alpha", saved_settings["opacity_percent"] / 100.0)
    root.update_idletasks()
    _apply_safe_window_style(root.winfo_id())

    last_game_seen = time.monotonic()
    last_state_write = 0.0
    overlay_pid = os.getpid()

    def refresh():
        nonlocal last_game_seen, last_state_write, applied_settings
        if stop_path.exists():
            try:
                stop_path.unlink()
            except OSError:
                pass
            root.destroy()
            return
        if time.monotonic() - last_state_write >= 2.0:
            _write_overlay_state(state_path, overlay_pid, time.time())
            last_state_write = time.monotonic()
        status = _safe_load(status_path)
        settings = load_overlay_settings(settings_path)
        if settings != applied_settings:
            apply_visibility(settings)
            root.attributes("-alpha", settings["opacity_percent"] / 100.0)
            applied_settings = settings
        objectives_data = _safe_load(status_path.with_name("overlay-objectives.json")) or {}
        objectives = objectives_data.get("objectives") if isinstance(objectives_data.get("objectives"), list) else []
        for idx, label in enumerate(objective_labels):
            if idx < len(objectives) and isinstance(objectives[idx], dict):
                item = objectives[idx]
                label.configure(text=f"{item.get('name', 'Agent')}: {item.get('objective', '')}  ·  {item.get('status', '')}", fg="#bfe8bf" if item.get("complete") else "#d8e1e8")
                if settings["show_objectives"]:
                    label.grid()
                else:
                    label.grid_remove()
            else:
                label.configure(text="")
                label.grid_remove()
        preferred_pid = None
        try:
            preferred_pid = int((status or {}).get("process_id") or 0) or None
        except Exception:
            preferred_pid = None
        hwnd = tracker.find_game_window(preferred_pid)
        view = summarize_status(status, nms_running=bool(hwnd))
        headline.configure(text=view["headline"])
        detail.configure(text=view["detail"])
        runtime.configure(text=f"NMS {view['nms']} · Probe {view['probe']} · Capture {view['capture']}")
        callers.configure(text=f"CALLERS {view['caller_scan']} · ROOT {view['exact_root_caller']}")
        root_resource_label.configure(text=f"ROOT RESOURCE · {view['root_resource']}")
        dispatch_label.configure(text=f"ROOT DISPATCH +0x10 · {view['root_dispatch']}")
        loot_summary.configure(text=view["loot_summary"])
        room_loot.configure(text=view["room_loot"])
        telemetry.configure(text=view["telemetry"])
        counts.configure(text=view["counts"])
        auto_crates.configure(text=view["auto_crates"])
        trace.configure(text=view["trace"])
        generation.configure(text=view["generation"])
        event.configure(text=view["event"])
        hotkeys1.configure(text=view["hotkeys_1"])
        hotkeys2.configure(text=view["hotkeys_2"])

        state = view["state"]
        if state == "recording":
            headline.configure(fg="#bfe8bf")
        elif state == "stale":
            headline.configure(fg="#efc7a2")
        else:
            headline.configure(fg="#dce8ef")

        if hwnd:
            last_game_seen = time.monotonic()
            if tracker.is_game_foreground(hwnd):
                root.attributes("-topmost", True)
                rect = tracker.client_rect_screen(hwnd)
            else:
                root.attributes("-topmost", False)
                root.withdraw()
                rect = None
            if rect:
                x, y, width, _height = rect
                root.update_idletasks()
                ow = max(720, root.winfo_reqwidth())
                oh = root.winfo_reqheight()
                ox = x + max(12, (width - ow) // 2) + settings["x_offset"]
                oy = y + settings["y_offset"]
                root.geometry(f"{ow}x{oh}+{ox}+{oy}")
                root.deiconify()
        else:
            root.attributes("-topmost", False)
            root.withdraw()
            if tracker.seen_game and time.monotonic() - last_game_seen > 15.0:
                root.destroy()
                return
        root.after(POLL_MS, refresh)

    _write_overlay_state(state_path, overlay_pid, time.time())
    try:
        refresh()
        root.mainloop()
    finally:
        current_state = _safe_load(state_path) or {}
        if int(current_state.get("pid") or 0) == overlay_pid:
            try:
                state_path.unlink()
            except OSError:
                pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NMS Derelict Surveyor safe live status banner")
    parser.add_argument("--status", type=Path, default=_default_status_path())
    parser.add_argument("--stop-file", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        run_overlay(args.status, args.stop_file)
    except Exception as exc:
        # Keep the overlay optional: failure must never prevent NMS/the probe from starting.
        error_path = _default_status_path().parent / "overlay-error.log"
        error_path.parent.mkdir(parents=True, exist_ok=True)
        with error_path.open("a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {type(exc).__name__}: {exc}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
