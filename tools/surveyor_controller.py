from __future__ import annotations

import argparse
import ctypes
import json
import os
import queue
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
from datetime import datetime, timezone
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

# The overlay owns the live-status formatter used by both windows.
PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))
from overlay.derelict_overlay import summarize_status
from overlay.derelict_overlay import build_agent_objectives, load_overlay_settings, save_overlay_settings

try:
    from . import agent_console
    from . import agent_ui_extensions
except ImportError:  # Running surveyor_controller.py directly from the tools folder.
    import agent_console
    import agent_ui_extensions

CONTROLLER_VERSION = "0.3.53"
AGENT_REFRESH_INTERVALS_MS = {
    "20 seconds": 20_000,
    "1 minute": 60_000,
    "2 minutes": 120_000,
    "5 minutes": 300_000,
    "Off": 0,
}
ROOT = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "NMSDerelictSurveyor"
WORK = ROOT / "asset-work-v1"
LOG_DIR = ROOT / "gui-actions"
CONTROLLER_LOG = LOG_DIR / "controller.log"
WORKFLOW_LOG = LOG_DIR / "workflow-latest.log"
WORKFLOW_DIAGNOSTIC = LOG_DIR / "workflow-diagnostic-latest.txt"
LIVE_STATUS = ROOT / "live-status.json"
OVERLAY_STOP_REQUEST = ROOT / "overlay-stop.request"
OVERLAY_STATE = ROOT / "overlay-state.json"
PROJECT_ROOT_FILE = ROOT / "project-root.txt"
PYTHON_FILE = ROOT / "python-executable.txt"
NMS_EXE_FILE = ROOT / "nms-executable.txt"
COMMAND_FILE = ROOT / "controller-command.json"
RUNTIME_CAPTURE_FILE = ROOT / "asset-work-v1" / "exact-root-caller-latest.json"


def _runtime_capture_saved(path: Path = RUNTIME_CAPTURE_FILE) -> bool:
    """True when the probe has atomically persisted a root-event slot record."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    capture = value.get("owner_plus_0x10_capture") if isinstance(value, dict) else None
    return (
        isinstance(value, dict)
        and value.get("schema_version") == 1
        and isinstance(capture, dict)
        and capture.get("read_status") in {"captured", "unreadable"}
    )


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _safe(value: object) -> str:
    text = str(value if value is not None else "")
    for env_name, token in (("USERPROFILE", "%USERPROFILE%"), ("LOCALAPPDATA", "%LOCALAPPDATA%")):
        raw = os.environ.get(env_name)
        if raw:
            text = text.replace(raw, token).replace(raw.replace("\\", "/"), token)
    return text


def _log(event: str, **fields: object) -> None:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        record = {"utc": _utc(), "event": event, **{k: _safe(v) for k, v in fields.items()}}
        with CONTROLLER_LOG.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    except Exception:
        pass


def _project_root(explicit: str | None = None) -> Path:
    if explicit:
        p = Path(explicit).expanduser().resolve()
        if (p / "VERSION.txt").is_file():
            return p
    if PROJECT_ROOT_FILE.is_file():
        try:
            p = Path(PROJECT_ROOT_FILE.read_text(encoding="utf-8-sig").strip())
            if p.is_dir() and (p / "VERSION.txt").is_file():
                return p
        except Exception:
            pass
    p = Path(__file__).resolve().parents[1]
    if (p / "VERSION.txt").is_file():
        return p
    raise RuntimeError("Surveyor source project could not be located.")


def _external_python() -> str:
    candidates: list[Path] = []
    if PYTHON_FILE.is_file():
        try:
            candidates.append(Path(PYTHON_FILE.read_text(encoding="utf-8-sig").strip()))
        except Exception:
            pass
    candidates.append(Path(sys.executable))
    for name in ("python", "python3"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))
    seen: set[str] = set()
    for candidate in candidates:
        try:
            resolved = candidate.expanduser().resolve()
        except Exception:
            resolved = candidate
        key = str(resolved).lower()
        if key in seen:
            continue
        seen.add(key)
        if resolved.name.lower().startswith("python") and resolved.is_file():
            return str(resolved)
    raise RuntimeError("A real external Python executable could not be located.")


def _nms_running() -> bool:
    if os.name != "nt":
        return False
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        result = subprocess.run(
            ["tasklist.exe", "/FI", "IMAGENAME eq NMS.exe", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            check=False,
            creationflags=flags,
            timeout=5,
        )
        return '"NMS.exe"' in (result.stdout or "")
    except Exception:
        return False


def _find_overlay_window() -> int | None:
    if os.name != "nt":
        return None
    try:
        hwnd = ctypes.windll.user32.FindWindowW(None, "NMS Derelict Surveyor Overlay")
        return int(hwnd) if hwnd else None
    except Exception:
        return None


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _powershell() -> str:
    return os.environ.get("SystemRoot", "C:\\Windows") + "\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" if os.name == "nt" else "pwsh"


class SurveyorController:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.python_exe = _external_python()
        ROOT.mkdir(parents=True, exist_ok=True)
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        PROJECT_ROOT_FILE.write_text(str(project_root), encoding="utf-8")
        PYTHON_FILE.write_text(self.python_exe, encoding="utf-8")

        self.window = tk.Tk()
        self.window.title("NMS Derelict Surveyor")
        self.window.geometry("760x760")
        self.window.minsize(690, 620)
        self.window.protocol("WM_DELETE_WINDOW", self._close)

        self.workflow_running = False
        self.last_nms_running = False
        self.last_probe_connected = False
        self.available_version = "not checked"
        self.last_live_pid: int | None = None
        self.agent_console_window: tk.Toplevel | None = None
        self.agent_cards: dict[str, dict] = {}
        self.agent_upload_vars: dict[str, tk.BooleanVar] = {}
        self.agent_console_preferences = self._load_agent_console_preferences()
        self.agent_refresh_interval_var = tk.StringVar(value=self.agent_console_preferences["refresh_interval"])
        self.agent_show_status_details_var = tk.BooleanVar(value=self.agent_console_preferences["show_status_details"])
        self.agent_show_extension_details_var = tk.BooleanVar(value=self.agent_console_preferences["show_extension_details"])
        self.agent_show_receipt_details_var = tk.BooleanVar(value=self.agent_console_preferences["show_receipt_details"])
        self.agent_console_options_frame: ttk.Frame | None = None
        self.agent_console_options_visible = False
        self.agent_console_option_buttons: dict[str, ttk.Button] = {}
        self.agent_refresh_after_id: str | None = None
        self.agent_extension_render_keys: dict[str, str] = {}
        self.agent_console_state = tk.StringVar(value="Loading agent status from GitHub…")
        self.agent_console_updated = tk.StringVar(value="Not refreshed yet")
        self.agent_copy_button: ttk.Button | None = None
        self.agent_fetch_running = False
        self.agent_snapshot: dict | None = None
        self.agent_selected_lane: dict | None = None
        self.agent_ui_extensions_root = ROOT / "ui-extensions"
        self.agent_ui_extension_index: list[dict] = []
        self.agent_ui_extension_error = ""
        self.agent_ui_extension_check_running = False
        self.agent_ui_extension_frame: ttk.LabelFrame | None = None
        self.agent_ui_extension_bodies: dict[str, ttk.Frame] = {}
        self.agent_ui_extension_notices: dict[str, tk.StringVar] = {}
        self.agent_ui_extension_controls: dict[str, dict] = {}
        self.agent_ui_extension_update_buttons: dict[str, ttk.Button] = {}
        self.agent_ui_extension_entries: dict[str, dict] = {}
        self.agent_ui_extension_rollback_versions: dict[str, str] = {}
        self.agent_ui_bulk_update_button: ttk.Button | None = None
        self.agent_ui_upload_all_button: ttk.Button | None = None
        self.agent_ui_upload_queue: list[dict] = []
        self.agent_ui_upload_queue_running = False
        self.agent_ui_upload_queue_total = 0
        self._mousewheel_scroll_targets: dict[str, tk.Widget] = {}
        self.agent_ui_action_buttons: list[tuple[ttk.Button, list[str]]] = []
        self.agent_ui_action_buttons_by_lane: dict[str, list[tuple[ttk.Button, list[str]]]] = {}
        self.agent_ui_extension_installing: set[str] = set()
        self.agent_ui_extension_notice = tk.StringVar(value="Checking for lane UI extensions…")
        self.extension_updates_state = tk.StringVar(value="Checking published lane extensions…")

        self.loaded_version = tk.StringVar(value=f"Controller {CONTROLLER_VERSION}")
        self.source_version = tk.StringVar(value=self._source_version())
        self.available_version_var = tk.StringVar(value=self.available_version)
        self.nms_state = tk.StringVar(value="Checking...")
        self.probe_state = tk.StringVar(value="Waiting for NMS/probe")
        self.recording_state = tk.StringVar(value="Not recording")
        self.counts_state = tk.StringVar(value="Crates —   Rooms —")
        self.root_caller_state = tk.StringVar(value="Not captured")
        self.caller_scan_state = tk.StringVar(value="Armed — all callers at once")
        self.workflow_status = tk.StringVar(value="Ready")
        self.workflow_detail = tk.StringVar(value="Surveyor is independent from NMS and will stay open when the game closes.")
        self.workflow_command = tk.StringVar(value="")
        self.workflow_progress = tk.StringVar(value="")
        self.workflow_latest = tk.StringVar(value="")
        self.output_events: queue.SimpleQueue[tuple[str, str]] = queue.SimpleQueue()
        self._latest_output = ""
        self._latest_progress = ""
        self.overlay_enabled = tk.BooleanVar(value=self._load_overlay_pref())
        self.overlay_state = tk.StringVar(value="Overlay status: checking")
        overlay_settings = load_overlay_settings(ROOT / "overlay-settings.json")
        self.overlay_setting_vars = {key: tk.BooleanVar(value=overlay_settings[key]) for key in ("show_rooms", "show_research", "show_position", "show_manual", "show_hotkeys")}
        self.overlay_opacity = tk.IntVar(value=overlay_settings["opacity_percent"])
        self.overlay_x_offset = tk.IntVar(value=overlay_settings["x_offset"])
        self.overlay_y_offset = tk.IntVar(value=overlay_settings["y_offset"])

        self._build_ui()
        self._open_agent_console()
        self._reschedule_agent_refresh()
        _log("controller_started", version=CONTROLLER_VERSION, project_root=self.project_root)
        self._refresh()

    @staticmethod
    def _make_collapsible_section(
        parent: ttk.Widget,
        title: str,
        *,
        padding: int = 8,
        body_fill: str = "x",
        body_expand: bool = False,
    ) -> tuple[ttk.LabelFrame, ttk.Frame]:
        """Create a bordered section with a compact top-right +/− toggle."""
        section = ttk.LabelFrame(parent, padding=padding)
        header = ttk.Frame(section)
        header.pack(fill="x")
        ttk.Label(header, text=title, font=("Segoe UI", 9, "bold")).pack(side="left", anchor="w")
        body = ttk.Frame(section)
        toggle = ttk.Button(header, text="−", width=2)
        toggle.pack(side="right", anchor="e")

        def toggle_body() -> None:
            if body.winfo_manager():
                body.pack_forget()
                toggle.configure(text="+")
            else:
                body.pack(fill=body_fill, expand=body_expand, pady=(4, 0))
                toggle.configure(text="−")

        toggle.configure(command=toggle_body)
        body.pack(fill=body_fill, expand=body_expand, pady=(4, 0))
        return section, body

    def _build_ui(self) -> None:
        canvas = tk.Canvas(self.window, highlightthickness=0)
        self._register_mousewheel_scroll_target(canvas)
        self.window.bind_all("<MouseWheel>", self._on_mousewheel, add="+")
        self.window.bind_all("<Button-4>", self._on_mousewheel, add="+")
        self.window.bind_all("<Button-5>", self._on_mousewheel, add="+")
        page_scroll = ttk.Scrollbar(self.window, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=page_scroll.set)
        page_scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        root = ttk.Frame(canvas, padding=12)
        page = canvas.create_window((0, 0), window=root, anchor="nw")
        root.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(page, width=event.width))

        title_row = ttk.Frame(root)
        title_row.pack(fill="x")
        title = ttk.Label(title_row, text="NMS Derelict Surveyor", font=("Segoe UI", 16, "bold"))
        title.pack(side="left", anchor="w")
        ttk.Button(title_row, text="Agent console", command=self._open_agent_console).pack(side="right")
        ttk.Label(root, text="Standalone controller — closing NMS does not close this window.").pack(anchor="w", pady=(0, 10))

        status_group, status = self._make_collapsible_section(root, "Status", padding=8)
        status_group.pack(fill="x", pady=(0, 10))
        self._row(status, "NMS", self.nms_state)
        self._row(status, "Probe", self.probe_state)
        self._row(status, "Capture", self.recording_state)
        self._row(status, "Counts", self.counts_state)
        self._row(status, "Caller scan", self.caller_scan_state)
        self._row(status, "Exact root caller", self.root_caller_state)
        self.root_resource_state = tk.StringVar(value="MODELS/SPACE/POI/DUNGEON.SCENE.MBIN · waiting for probe")
        self.root_dispatch_state = tk.StringVar(value="Not captured by this probe build · Runtime-A hook required")
        self._row(status, "Root resource", self.root_resource_state)
        self._row(status, "Root dispatch +0x10", self.root_dispatch_state)

        overlay_group, overlay_status = self._make_collapsible_section(root, "Overlay details", padding=8)
        overlay_group.pack(fill="x", pady=(0, 10))
        self.overlay_detail_vars = {
            key: tk.StringVar(value="") for key in (
                "detail", "telemetry", "overlay_counts", "auto_crates", "loot_summary", "room_loot",
                "trace", "generation", "event", "root_resource", "root_dispatch", "hotkeys_1", "hotkeys_2",
            )
        }
        for label, key in (
            ("Detail", "detail"), ("Position", "telemetry"), ("Overlay counts", "overlay_counts"),
            ("Automatic crates", "auto_crates"), ("Loot summary", "loot_summary"),
            ("Room loot", "room_loot"), ("Trace", "trace"), ("Generation", "generation"),
            ("Root resource", "root_resource"), ("Root dispatch +0x10", "root_dispatch"),
            ("Last event", "event"), ("Hotkeys", "hotkeys_1"), ("", "hotkeys_2"),
        ):
            self._row(overlay_status, label, self.overlay_detail_vars[key])

        versions_group, versions = self._make_collapsible_section(root, "Versions", padding=8)
        versions_group.pack(fill="x", pady=(0, 10))
        self._row(versions, "Loaded controller", self.loaded_version)
        self._row(versions, "Downloaded/source", self.source_version)
        self._row(versions, "Available", self.available_version_var)

        game_group, game = self._make_collapsible_section(root, "Game", padding=8)
        game_group.pack(fill="x", pady=(0, 10))
        game_buttons = ttk.Frame(game)
        game_buttons.pack(fill="x")
        self.start_nms_button = ttk.Button(game_buttons, text="Start NMS", command=self.start_nms)
        self.start_nms_button.pack(side="left", padx=(0, 8))
        ttk.Button(game_buttons, text="Restart Surveyor", command=self.restart_controller).pack(side="left", padx=(0, 8))
        ttk.Checkbutton(game_buttons, text="Game overlay", variable=self.overlay_enabled, command=self._save_overlay_pref).pack(side="left")
        self.start_overlay_button = ttk.Button(game_buttons, text="Start overlay", command=self.start_overlay)
        self.start_overlay_button.pack(side="left", padx=(8, 0))
        self.stop_overlay_button = ttk.Button(game_buttons, text="Stop overlay", command=self.stop_overlay)
        self.stop_overlay_button.pack(side="left", padx=(6, 0))
        ttk.Label(game, textvariable=self.overlay_state).pack(anchor="w", pady=(4, 0))
        ttk.Label(game, text="Restart Surveyor restarts only this controller. It never closes NMS.", wraplength=690).pack(anchor="w", pady=(8, 0))

        display_group, display = self._make_collapsible_section(root, "In-game overlay display", padding=8)
        display_group.pack(fill="x", pady=(0, 10))
        toggles = ttk.Frame(display)
        toggles.pack(fill="x")
        for title, key in (("Rooms", "show_rooms"), ("Research", "show_research"), ("Position", "show_position"), ("Manual counts", "show_manual"), ("Hotkeys", "show_hotkeys")):
            ttk.Checkbutton(toggles, text=title, variable=self.overlay_setting_vars[key], command=self._save_overlay_settings).pack(side="left", padx=(0, 10))
        self._overlay_slider(display, "Opacity", self.overlay_opacity, 20, 100, "%")
        self._overlay_slider(display, "Horizontal position", self.overlay_x_offset, -800, 800, " px")
        self._overlay_slider(display, "Vertical position", self.overlay_y_offset, -500, 600, " px")
        ttk.Label(display, text="Display settings apply live. Position is relative to the game window.", wraplength=690).pack(anchor="w", pady=(3, 0))

        updates_group, updates = self._make_collapsible_section(root, "GitHub / updates", padding=8)
        updates_group.pack(fill="x", pady=(0, 10))
        self._button_grid(updates, [
            ("Set up GitHub uploads", lambda: self._integration("GitHub setup", "setup", visible=True)),
            ("Run GitHub diagnostic", lambda: self._integration("GitHub diagnostic", "diagnose")),
            ("Check app update", lambda: self._integration("Check update", "check-update")),
            ("Install update", lambda: self._integration("Install update", "install-update")),
            ("Install Derelict Farming archive", self.install_derelict_farming_archive),
            ("Check lane extensions", self._check_agent_ui_extensions),
            ("Open workflow log", self.open_workflow_log),
            ("Open workflow diagnostic", self.open_workflow_diagnostic),
        ])

        extensions_group, extensions = self._make_collapsible_section(root, "Lane extensions", padding=8)
        extensions_group.pack(fill="x", pady=(0, 10))
        ttk.Label(extensions, textvariable=self.extension_updates_state, wraplength=690, justify="left").pack(anchor="w")

        research_group, research = self._make_collapsible_section(root, "Research", padding=8)
        research_group.pack(fill="x", pady=(0, 10))
        self._button_grid(research, [
            ("Upload all saved evidence", self.upload_all_saved_evidence),
            ("Analyze seed function + upload", lambda: self._project_action("Analyze seed function + upload", "Analyze-Dungeon-Seed-Function.cmd", "analyze-seed-function")),
            ("Extract upstream callers + upload", lambda: self._project_action("Extract upstream + upload", "Extract-Dungeon-Upstream-Callers.cmd", "extract-upstream")),
            ("Extract exact root caller + upload", lambda: self._project_action("Extract exact root caller + upload", "Extract-Exact-Root-Caller-Code.cmd", "extract-exact-root-caller")),
            ("Resolve root vtable + upload", lambda: self._project_action("Resolve root vtable + upload", "Resolve-Exact-Root-VTable.cmd", "resolve-root-vtable")),
            ("Extract caller code + upload", lambda: self._project_action("Extract caller + upload", "Extract-Dungeon-Caller-Code.cmd", "extract-caller")),
            ("Measure generation + upload", lambda: self._project_action("Measure + upload", "Measure-Derelict-Generation.cmd", "measure")),
            ("Prepare crate assets + upload", lambda: self._project_action("Prepare assets + upload", "Prepare-Crate-Assets.cmd", "prepare-assets")),
            ("Analyze generation + upload", lambda: self._project_action("Analyze generation + upload", "Analyze-Generation-Baseline.cmd", "analyze-generation")),
        ])

        capture_group, capture = self._make_collapsible_section(root, "Live capture", padding=8)
        capture_group.pack(fill="x", pady=(0, 10))
        self._button_grid(capture, [
            ("Force start session", lambda: self._send_probe_command("force_start_session")),
            ("Stop + save session", lambda: self._send_probe_command("stop_session")),
            ("Undo last marker", lambda: self._send_probe_command("undo_last_marker")),
            ("Write diagnostic snapshot", lambda: self._send_probe_command("write_diagnostic_snapshot")),
        ])

        workflow_group, workflow = self._make_collapsible_section(root, "Current action", padding=8, body_fill="both", body_expand=True)
        workflow_group.pack(fill="both", expand=True)
        ttk.Label(workflow, textvariable=self.workflow_status, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Label(workflow, textvariable=self.workflow_detail, wraplength=690, justify="left").pack(anchor="w", pady=(4, 0))
        ttk.Label(workflow, textvariable=self.workflow_command, wraplength=690, justify="left").pack(anchor="w", pady=(4, 0))
        ttk.Label(workflow, textvariable=self.workflow_progress).pack(anchor="w")
        ttk.Label(workflow, textvariable=self.workflow_latest, wraplength=690, justify="left").pack(anchor="w")
        output_frame = ttk.Frame(workflow)
        output_frame.pack(fill="both", expand=True, pady=(4, 0))
        self.workflow_output = tk.Text(output_frame, height=12, wrap="none", state="disabled")
        output_scroll = ttk.Scrollbar(output_frame, orient="vertical", command=self.workflow_output.yview)
        self.workflow_output.configure(yscrollcommand=output_scroll.set)
        self.workflow_output.pack(side="left", fill="both", expand=True)
        output_scroll.pack(side="right", fill="y")
        self.window.after(50, self._drain_output_events)

    def _register_mousewheel_scroll_target(self, widget: tk.Widget) -> None:
        self._mousewheel_scroll_targets[widget._w] = widget

    @staticmethod
    def _set_lane_scrollbar(canvas: tk.Canvas, scrollbar: ttk.Scrollbar, first: str, last: str) -> None:
        scrollbar.set(first, last)
        try:
            if float(last) - float(first) >= 0.999:
                scrollbar.grid_remove()
            else:
                scrollbar.grid()
        except (tk.TclError, ValueError):
            pass

    def _on_mousewheel(self, event: tk.Event) -> str | None:
        """Scroll the nearest registered canvas beneath the pointer; let Text keep its native binding."""
        try:
            target = self.window.winfo_containing(event.x_root, event.y_root)
        except tk.TclError:
            return None
        while target is not None:
            if isinstance(target, tk.Text):
                return None
            scroll_target = self._mousewheel_scroll_targets.get(target._w)
            if scroll_target is not None:
                if getattr(event, "num", None) == 4:
                    units = -1
                elif getattr(event, "num", None) == 5:
                    units = 1
                else:
                    delta = int(getattr(event, "delta", 0) or 0)
                    units = int(-delta / 120)
                    if units == 0 and delta:
                        units = -1 if delta > 0 else 1
                if units:
                    first, last = scroll_target.yview()
                    # Ignore wheel input entirely when this panel fits, and keep
                    # boundary events from making short text jump or bubble oddly.
                    if (first <= 0.0 and last >= 1.0) or (units < 0 and first <= 0.0) or (units > 0 and last >= 1.0):
                        return "break"
                    scroll_target.yview_scroll(units, "units")
                return "break"
            target = getattr(target, "master", None)
        return None

    def _drain_output_events(self) -> None:
        lines = []
        for _ in range(200):
            try:
                kind, value = self.output_events.get_nowait()
            except queue.Empty:
                break
            if kind == "clear":
                self.workflow_output.configure(state="normal")
                self.workflow_output.delete("1.0", "end")
                self.workflow_output.configure(state="disabled")
                self.workflow_progress.set("")
                self.workflow_latest.set("")
            elif kind == "command":
                self.workflow_command.set(value)
            elif kind == "line":
                lines.append(value)
        if lines:
            self.workflow_output.configure(state="normal")
            self.workflow_output.insert("end", "".join(lines))
            self.workflow_output.see("end")
            self.workflow_output.configure(state="disabled")
        self.workflow_latest.set(self._latest_output)
        self.workflow_progress.set(self._latest_progress)
        self.window.after(50, self._drain_output_events)

    @staticmethod
    def _row(parent: ttk.Widget, label: str, value: tk.StringVar) -> None:
        frame = ttk.Frame(parent)
        frame.pack(fill="x", pady=1)
        ttk.Label(frame, text=f"{label}:", width=22).pack(side="left")
        ttk.Label(frame, textvariable=value).pack(side="left", fill="x", expand=True)

    def _overlay_slider(self, parent: ttk.Widget, label: str, variable: tk.IntVar, low: int, high: int, suffix: str) -> None:
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=1)
        ttk.Label(row, text=f"{label}:", width=22).pack(side="left")
        value_label = ttk.Label(row, width=8, anchor="e")
        value_label.pack(side="right")
        def changed(raw: str) -> None:
            variable.set(round(float(raw)))
            value_label.configure(text=f"{variable.get()}{suffix}")
            self._save_overlay_settings()
        slider = ttk.Scale(row, from_=low, to=high, variable=variable, command=changed)
        slider.pack(side="left", fill="x", expand=True, padx=(4, 10))
        value_label.configure(text=f"{variable.get()}{suffix}")

    @staticmethod
    def _button_grid(parent: ttk.Widget, items: list[tuple[str, object]]) -> None:
        for col in range(2):
            parent.columnconfigure(col, weight=1)
        for i, (label, command) in enumerate(items):
            btn = ttk.Button(parent, text=label, command=command)
            btn.grid(row=i // 2, column=i % 2, sticky="ew", padx=4, pady=4)

    def _source_version(self) -> str:
        try:
            return (self.project_root / "VERSION.txt").read_text(encoding="utf-8-sig").strip() or "unknown"
        except Exception:
            return "unknown"

    def _load_agent_console_preferences(self) -> dict:
        defaults = {
            "refresh_interval": "1 minute",
            "show_status_details": True,
            "show_extension_details": True,
            "show_receipt_details": True,
        }
        path = ROOT / "agent-console-options.json"
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return defaults
        if not isinstance(saved, dict):
            return defaults
        interval = saved.get("refresh_interval")
        if interval not in AGENT_REFRESH_INTERVALS_MS:
            interval = defaults["refresh_interval"]
        return {
            "refresh_interval": interval,
            "show_status_details": bool(saved.get("show_status_details", defaults["show_status_details"])),
            "show_extension_details": bool(saved.get("show_extension_details", defaults["show_extension_details"])),
            "show_receipt_details": bool(saved.get("show_receipt_details", defaults["show_receipt_details"])),
        }

    def _save_agent_console_preferences(self) -> None:
        preferences = {
            "refresh_interval": self.agent_refresh_interval_var.get(),
            "show_status_details": self.agent_show_status_details_var.get(),
            "show_extension_details": self.agent_show_extension_details_var.get(),
            "show_receipt_details": self.agent_show_receipt_details_var.get(),
        }
        try:
            ROOT.mkdir(parents=True, exist_ok=True)
            (ROOT / "agent-console-options.json").write_text(
                json.dumps(preferences, indent=2) + "\n", encoding="utf-8"
            )
        except OSError as exc:
            _log("agent_console_preferences_save_failed", error=repr(exc))

    def _open_agent_console(self) -> None:
        if self.agent_console_window is not None and self.agent_console_window.winfo_exists():
            self.agent_console_window.deiconify()
            self.agent_console_window.lift()
            return

        win = tk.Toplevel(self.window)
        win.title("Surveyor · Agent Console")
        win.geometry("1680x940")
        win.minsize(1320, 700)
        win.protocol("WM_DELETE_WINDOW", win.withdraw)
        self.agent_console_window = win

        outer = ttk.Frame(win, padding=10)
        outer.pack(fill="both", expand=True)
        header = ttk.Frame(outer)
        header.pack(fill="x")
        ttk.Label(header, text="Agent Console", font=("Segoe UI", 14, "bold")).pack(side="left", anchor="w")
        ttk.Button(header, text="Check extensions", command=self._check_agent_ui_extensions).pack(side="right")
        ttk.Button(header, text="Refresh now", command=self._refresh_agent_console_all).pack(side="right", padx=(0, 8))
        self.agent_options_toggle_button = ttk.Button(header, text="Options +", command=self._toggle_agent_console_options)
        self.agent_options_toggle_button.pack(side="right", padx=(0, 8))
        ttk.Label(header, text="Auto refresh:").pack(side="right", padx=(8, 3))
        interval_box = ttk.Combobox(
            header,
            textvariable=self.agent_refresh_interval_var,
            values=list(AGENT_REFRESH_INTERVALS_MS),
            state="readonly",
            width=12,
        )
        interval_box.pack(side="right")
        interval_box.bind("<<ComboboxSelected>>", self._on_agent_refresh_interval_changed)
        ttk.Label(
            outer,
            text="All four agent lanes are shown together. Each information panel scrolls independently; the action buttons stay below.",
            wraplength=1540,
        ).pack(anchor="w", pady=(2, 8))
        options_frame = ttk.LabelFrame(outer, text="Agent Console options", padding=(6, 4))
        self.agent_console_options_frame = options_frame
        for key, label, command, visible in (
            ("status", "lane details", self._toggle_agent_status_details, self.agent_show_status_details_var.get()),
            ("extension", "extension details", self._toggle_agent_extension_details, self.agent_show_extension_details_var.get()),
            ("receipt", "receipt details", self._toggle_agent_receipt_details, self.agent_show_receipt_details_var.get()),
        ):
            button = ttk.Button(options_frame, text=f"− Hide {label}" if visible else f"+ Show {label}", command=command)
            button.pack(side="left", padx=3)
            self.agent_console_option_buttons[key] = button
        options_frame.pack_forget()
        self.agent_console_state_label = ttk.Label(outer, textvariable=self.agent_console_state, font=("Segoe UI", 10, "bold"))
        self.agent_console_state_label.pack(anchor="w")
        ttk.Label(outer, textvariable=self.agent_console_updated).pack(anchor="w", pady=(0, 4))

        actions = ttk.Frame(outer)
        actions.pack(side="bottom", fill="x", pady=(8, 0))
        lane_actions = ttk.Frame(actions)
        lane_actions.pack(fill="x")
        for index, lane_config in enumerate(agent_console.LANES):
            lane_id = lane_config["id"]
            lane_actions.columnconfigure(index, weight=1, uniform="lane-actions")
            lane_group, lane_box = self._make_collapsible_section(lane_actions, lane_config["name"], padding=5)
            lane_group.grid(row=0, column=index, sticky="nsew", padx=4)
            lane_box.columnconfigure(0, weight=1)
            uploaded_var = tk.BooleanVar(value=False)
            self.agent_upload_vars[lane_id] = uploaded_var
            steps_button = ttk.Button(lane_box, text="Copy full steps", command=lambda i=lane_id: self._copy_agent_steps(i))
            steps_button.pack(fill="x", pady=2)
            steps_button.state(["disabled"])
            update_button = ttk.Button(
                lane_box,
                text="Up to date",
                command=lambda i=lane_id: self._install_lane_extension(i),
            )
            update_button.pack(fill="x", pady=2)
            update_button.state(["disabled"])
            rollback_button = ttk.Button(lane_box, text="Rollback unavailable", state="disabled")
            rollback_button.pack(fill="x", pady=2)
            action_host = ttk.Frame(lane_box)
            action_host.pack(fill="x")
            receipt_check = ttk.Checkbutton(
                lane_box,
                text="Evidence upload confirmed",
                variable=uploaded_var,
                state="disabled",
            )
            receipt_check.pack(anchor="w", pady=(4, 0))
            self.agent_ui_extension_controls[lane_id] = {
                "steps": steps_button,
                "update": update_button,
                "rollback": rollback_button,
                "actions": action_host,
                "action_buttons": [],
                "action_specs": [],
            }
            self.agent_ui_extension_update_buttons[lane_id] = update_button

        global_actions_group, global_actions = self._make_collapsible_section(actions, "Agent actions", padding=5)
        global_actions_group.pack(fill="x", pady=(6, 0))
        ttk.Button(global_actions, text="Refresh agents", command=self._refresh_agent_console).pack(side="left")
        ttk.Button(global_actions, text="Copy status summary", command=self._copy_agent_summary).pack(side="left", padx=(8, 0))
        self.agent_ui_extension_notice_label = ttk.Label(global_actions, textvariable=self.agent_ui_extension_notice)
        self.agent_ui_extension_notice_label.pack(side="left", padx=(12, 0), fill="x", expand=True)
        self.agent_ui_bulk_update_button = ttk.Button(
            global_actions, text="Update all extensions", command=self._install_all_agent_ui_extensions
        )
        self.agent_ui_bulk_update_button.pack(side="right")
        self.agent_ui_upload_all_button = ttk.Button(
            global_actions, text="Upload all", command=self._upload_all_agent_evidence
        )
        self.agent_ui_upload_all_button.pack(side="right", padx=(0, 8))

        cards = ttk.Frame(outer)
        cards.pack(fill="both", expand=True)
        for index in range(len(agent_console.LANES)):
            cards.columnconfigure(index, weight=1, uniform="agent-card")
        cards.rowconfigure(0, weight=1)
        for index, lane_config in enumerate(agent_console.LANES):
            lane_id = lane_config["id"]
            card_group, card = self._make_collapsible_section(
                cards, lane_config["name"], padding=5, body_fill="both", body_expand=True
            )
            card_group.grid(row=0, column=index, sticky="nsew", padx=4, pady=4)
            card.columnconfigure(0, weight=1)
            card.rowconfigure(0, weight=1)
            info = ttk.Frame(card)
            info.grid(row=0, column=0, sticky="nsew")
            info.columnconfigure(0, weight=1)
            info.rowconfigure(0, weight=1)
            info_canvas = tk.Canvas(info, highlightthickness=0, width=360)
            self._register_mousewheel_scroll_target(info_canvas)
            info_scroll = ttk.Scrollbar(info, orient="vertical", command=info_canvas.yview)
            info_canvas.configure(yscrollcommand=lambda first, last, c=info_canvas, s=info_scroll: self._set_lane_scrollbar(c, s, first, last))
            info_canvas.grid(row=0, column=0, sticky="nsew")
            info_scroll.grid(row=0, column=1, sticky="ns")
            info_body = ttk.Frame(info_canvas, padding=(2, 2, 6, 2))
            info_window = info_canvas.create_window((0, 0), window=info_body, anchor="nw")
            info_body.bind("<Configure>", lambda _e, c=info_canvas: c.configure(scrollregion=c.bbox("all")))
            info_canvas.bind("<Configure>", lambda e, c=info_canvas, w=info_window: c.itemconfigure(w, width=e.width))
            status_var = tk.StringVar(value="Loading published status…")
            summary_var = tk.StringVar(value="Waiting for agent status.")
            request_var = tk.StringVar(value="")
            upload_detail_var = tk.StringVar(value="No lane upload confirmed yet.")
            notice_var = tk.StringVar(value="Checking published lane extension…")
            action_needed_var = tk.StringVar(value="Checking published agent status…")
            action_label_var = tk.StringVar(value="Action: Checking published extension…")
            action_reason_var = tk.StringVar(value="Needs: checking published action…")
            version_var = tk.StringVar(value="Installed extension version: checking…")
            details_frame = ttk.Frame(info_body)
            details_frame.pack(fill="x")
            ttk.Label(details_frame, text="Receipt history only; it does not lock action buttons.", wraplength=310, justify="left").pack(anchor="w")
            ttk.Label(details_frame, textvariable=status_var, font=("Segoe UI", 10, "bold"), wraplength=310, justify="left").pack(anchor="w", fill="x", pady=(4, 0))
            ttk.Label(details_frame, textvariable=summary_var, wraplength=310, justify="left").pack(anchor="w", fill="x", pady=(4, 4))
            ttk.Label(details_frame, textvariable=request_var, wraplength=310, justify="left").pack(anchor="w", fill="x", pady=(0, 4))
            receipt_detail_label = ttk.Label(details_frame, textvariable=upload_detail_var, wraplength=310, justify="left")
            receipt_detail_label.pack(anchor="w", fill="x", pady=(0, 4))
            extension_body = ttk.Frame(info_body)
            extension_body.pack(fill="x", pady=(2, 0))
            extension_body.columnconfigure(0, weight=1)
            needed_box = ttk.LabelFrame(card, text="NEEDED", padding=(6, 4))
            needed_box.grid(row=1, column=0, sticky="ew", pady=(4, 2))
            ttk.Label(needed_box, textvariable=action_needed_var, wraplength=320, justify="left", font=("Segoe UI", 9, "bold")).pack(anchor="w", fill="x")
            ttk.Label(needed_box, textvariable=action_label_var, wraplength=320, justify="left").pack(anchor="w", fill="x", pady=(3, 0))
            ttk.Label(needed_box, textvariable=action_reason_var, wraplength=320, justify="left").pack(anchor="w", fill="x", pady=(2, 0))
            ttk.Label(card, textvariable=version_var, wraplength=340, justify="left").grid(row=2, column=0, sticky="ew", pady=(0, 2))
            self.agent_cards[lane_id] = {
                "status": status_var, "summary": summary_var, "request": request_var,
                "uploaded": uploaded_var, "upload_detail": upload_detail_var,
                "action_needed": action_needed_var, "action_label": action_label_var,
                "action_reason": action_reason_var, "version": version_var,
                "details_frame": details_frame, "extension_body": extension_body,
                "receipt_detail_label": receipt_detail_label,
            }
            self.agent_ui_extension_bodies[lane_id] = extension_body
            self.agent_ui_extension_notices[lane_id] = notice_var
            self.agent_ui_extension_notices[lane_id].set("Published extension status loading…")
        self.agent_ui_extension_frame = None

        for lane_config in agent_console.LANES:
            self._render_agent_ui_extension({
                "id": lane_config["id"], "name": lane_config["name"], "human_required": False,
            })

        self._apply_agent_console_visibility()
        self.window.after_idle(self._refresh_agent_console)
        self.window.after_idle(self._check_agent_ui_extensions)

    def _toggle_agent_console_options(self) -> None:
        frame = self.agent_console_options_frame
        if frame is None:
            return
        self.agent_console_options_visible = not self.agent_console_options_visible
        if self.agent_console_options_visible:
            frame.pack(fill="x", pady=(0, 6), before=self.agent_console_state_label)
            self.agent_options_toggle_button.configure(text="Options −")
        else:
            frame.pack_forget()
            self.agent_options_toggle_button.configure(text="Options +")

    def _apply_agent_console_visibility(self) -> None:
        for card in self.agent_cards.values():
            details = card["details_frame"]
            if self.agent_show_status_details_var.get():
                details.pack(fill="x")
            else:
                details.pack_forget()
            extension = card["extension_body"]
            if self.agent_show_extension_details_var.get():
                extension.pack(fill="x", pady=(2, 0))
            else:
                extension.pack_forget()
            receipt = card["receipt_detail_label"]
            if self.agent_show_receipt_details_var.get() and self.agent_show_status_details_var.get():
                receipt.pack(anchor="w", fill="x", pady=(0, 4))
            else:
                receipt.pack_forget()
        settings = (
            ("status", "lane details", self.agent_show_status_details_var.get()),
            ("extension", "extension details", self.agent_show_extension_details_var.get()),
            ("receipt", "receipt details", self.agent_show_receipt_details_var.get()),
        )
        for key, label, visible in settings:
            button = self.agent_console_option_buttons.get(key)
            if button:
                button.configure(text=f"− Hide {label}" if visible else f"+ Show {label}")

    def _toggle_agent_status_details(self) -> None:
        self.agent_show_status_details_var.set(not self.agent_show_status_details_var.get())
        self._save_agent_console_preferences()
        self._apply_agent_console_visibility()

    def _toggle_agent_extension_details(self) -> None:
        self.agent_show_extension_details_var.set(not self.agent_show_extension_details_var.get())
        self._save_agent_console_preferences()
        self._apply_agent_console_visibility()

    def _toggle_agent_receipt_details(self) -> None:
        self.agent_show_receipt_details_var.set(not self.agent_show_receipt_details_var.get())
        self._save_agent_console_preferences()
        self._apply_agent_console_visibility()

    def _on_agent_refresh_interval_changed(self, _event: tk.Event | None = None) -> None:
        self._save_agent_console_preferences()
        self._reschedule_agent_refresh()

    def _refresh_agent_console_all(self) -> None:
        self._refresh_agent_console()
        self._check_agent_ui_extensions()

    def _reschedule_agent_refresh(self) -> None:
        if self.agent_refresh_after_id:
            try:
                self.window.after_cancel(self.agent_refresh_after_id)
            except tk.TclError:
                pass
            self.agent_refresh_after_id = None
        interval = AGENT_REFRESH_INTERVALS_MS.get(self.agent_refresh_interval_var.get(), 60_000)
        if interval and self.window.winfo_exists():
            self.agent_refresh_after_id = self.window.after(interval, self._scheduled_agent_refresh)

    def _refresh_agent_console(self) -> None:
        if self.agent_fetch_running:
            return
        self.agent_fetch_running = True
        self.agent_console_state.set("Refreshing published agent status…")

        def worker() -> None:
            snapshot = agent_console.load_agent_snapshot()
            try:
                self.window.after(0, lambda: self._apply_agent_snapshot(snapshot))
            except (tk.TclError, RuntimeError):
                pass

        threading.Thread(target=worker, name="Surveyor-Agent-Console", daemon=True).start()

    def _scheduled_agent_refresh(self) -> None:
        self.agent_refresh_after_id = None
        if AGENT_REFRESH_INTERVALS_MS.get(self.agent_refresh_interval_var.get(), 0):
            self._refresh_agent_console_all()
            self._reschedule_agent_refresh()

    def _apply_agent_snapshot(self, snapshot: dict) -> None:
        self.agent_fetch_running = False
        if not snapshot.get("registry_available") and not snapshot.get("any_lane_data"):
            if self.agent_snapshot:
                self.agent_console_state.set("Refresh failed — showing the last successful snapshot.")
                return
            self.agent_console_state.set("Could not load published status. Check the connection and retry.")
            self.agent_console_updated.set("No status snapshot is available yet.")
            return

        self.agent_snapshot = snapshot
        self._publish_overlay_objectives()
        stale = agent_console.registry_is_stale(snapshot.get("registry_updated_utc", ""))
        if stale is True:
            self.agent_console_state.set("Main status registry is over 30 minutes old; each lane status is fetched separately.")
        elif not snapshot.get("registry_available"):
            self.agent_console_state.set("Main status registry unavailable; showing status published on agent branches.")
        else:
            self.agent_console_state.set("Showing the latest status published to the project repository.")
        registry_time = snapshot.get("registry_updated_utc") or "unknown"
        fetched = snapshot.get("fetched_utc") or "unknown"
        self.agent_console_updated.set(f"Registry updated: {registry_time}   ·   Refreshed: {fetched}")

        for lane in snapshot.get("lanes", []):
            self._render_agent_details(lane)
            self._render_agent_ui_extension(lane)
        self._refresh_agent_upload_indicators()
        if self.agent_ui_extension_index:
            self._update_agent_extension_summary()

    def _check_agent_ui_extensions(self) -> None:
        if self.agent_ui_extension_check_running:
            return
        self.agent_ui_extension_check_running = True
        self.agent_ui_extension_notice.set("Checking published lane UI extensions…")
        self.extension_updates_state.set("Checking the published extension index…")

        def worker() -> None:
            try:
                entries = agent_ui_extensions.load_index()
                error = ""
            except Exception as exc:
                entries = []
                error = f"{type(exc).__name__}: {exc}"
            try:
                self.window.after(0, lambda: self._apply_agent_ui_extensions(entries, error))
            except (tk.TclError, RuntimeError):
                pass

        threading.Thread(target=worker, name="Surveyor-UI-Extensions", daemon=True).start()

    def _apply_agent_ui_extensions(self, entries: list[dict], error: str) -> None:
        self.agent_ui_extension_check_running = False
        if error:
            self.agent_ui_extension_error = error
            self.extension_updates_state.set("Could not reach the published extension index. Check again when online.")
            self.agent_ui_extension_notice.set("Could not refresh published extensions.")
            if not self.agent_ui_extension_index:
                _log("agent_ui_extension_index_error", error=error)
        else:
            self.agent_ui_extension_error = ""
            self.agent_ui_extension_index = entries
            self._update_agent_extension_summary()
            self.agent_ui_extension_notice.set("Published extension index refreshed.")
        for lane in (self.agent_snapshot or {}).get("lanes", []):
            self._render_agent_ui_extension(lane)

    def _update_agent_extension_summary(self) -> None:
        candidates = agent_ui_extensions.update_candidates(
            self.agent_ui_extension_index, self.agent_ui_extensions_root
        )
        lane_names = {
            lane.get("id"): lane.get("name")
            for lane in (self.agent_snapshot or {}).get("lanes", [])
        }
        if candidates:
            updates = ", ".join(
                f"{lane_names.get(item['extension_id'], item['extension_id'])} v{item['version']}"
                for item in candidates
            )
            self.extension_updates_state.set(
                f"Updates available: {updates}. Use Update all extensions or the lane buttons in Agent Console."
            )
        else:
            self.extension_updates_state.set(
                "Published extensions are current. Check extensions in Agent Console to refresh all lanes."
            )
        if hasattr(self, "agent_ui_extension_update_buttons"):
            self._refresh_agent_extension_update_controls()

    def _refresh_agent_extension_update_controls(self) -> None:
        candidates = {
            item["extension_id"]: item
            for item in agent_ui_extensions.update_candidates(
                self.agent_ui_extension_index, self.agent_ui_extensions_root
            )
        }
        for extension_id, button in self.agent_ui_extension_update_buttons.items():
            entry = candidates.get(extension_id)
            if entry:
                button.configure(text=f"Update to v{entry['version']}")
                can_update = (
                    extension_id not in self.agent_ui_extension_installing
                    and not self.agent_ui_upload_queue_running
                )
                button.state(["!disabled"] if can_update else ["disabled"])
                self.agent_ui_extension_entries[extension_id] = entry
            else:
                button.configure(text="Up to date")
                button.state(["disabled"])
                self.agent_ui_extension_entries.pop(extension_id, None)
        for extension_id, control in self.agent_ui_extension_controls.items():
            version = self.agent_ui_extension_rollback_versions.get(extension_id)
            rollback = control["rollback"]
            if version:
                rollback.configure(text=f"Roll back to v{version}", command=lambda i=extension_id, v=version: self._rollback_agent_ui_extension(i, v))
                rollback.state(["!disabled"])
            else:
                rollback.configure(text="Rollback unavailable")
                rollback.state(["disabled"])
        if self.agent_ui_bulk_update_button:
            busy = any(item in self.agent_ui_extension_installing for item in candidates)
            self.agent_ui_bulk_update_button.configure(
                text=f"Update all ({len(candidates)})" if candidates else "Update all extensions"
            )
            self.agent_ui_bulk_update_button.state(
                ["!disabled"] if candidates and not busy and not self.agent_ui_upload_queue_running else ["disabled"]
            )

    def _install_lane_extension(self, extension_id: str) -> None:
        entry = self.agent_ui_extension_entries.get(extension_id)
        if entry:
            self._confirm_agent_ui_extension_update(entry)

    def _install_all_agent_ui_extensions(self) -> None:
        candidates = agent_ui_extensions.update_candidates(
            self.agent_ui_extension_index, self.agent_ui_extensions_root
        )
        candidates = [item for item in candidates if item["extension_id"] not in self.agent_ui_extension_installing]
        if not candidates:
            return
        names = ", ".join(f"{item['extension_id']} v{item['version']}" for item in candidates)
        if not messagebox.askyesno(
            "Update agent extensions",
            f"Install all available agent extension updates?\n\n{names}",
            parent=self.agent_console_window,
        ):
            return
        self.agent_ui_extension_installing.update(item["extension_id"] for item in candidates)
        if hasattr(self, "agent_ui_extension_update_buttons"):
            self._refresh_agent_extension_update_controls()
        self.agent_ui_extension_notice.set("Installing all available lane extensions…")

        def worker() -> None:
            failures = []
            for entry in candidates:
                extension_id = entry["extension_id"]
                try:
                    agent_ui_extensions.install_extension(
                        self.agent_ui_extensions_root,
                        entry,
                        CONTROLLER_VERSION,
                        agent_ui_extensions.HOST_ACTION_IDS,
                    )
                    _log("agent_ui_extension_updated", extension_id=extension_id, version=entry["version"], batch=True)
                except Exception as exc:
                    failures.append(f"{extension_id}: {type(exc).__name__}: {exc}")
                    _log("agent_ui_extension_update_failed", extension_id=extension_id, error=repr(exc), batch=True)
            try:
                self.window.after(0, lambda: self._finish_agent_ui_extension_batch(candidates, failures))
            except (tk.TclError, RuntimeError):
                pass

        threading.Thread(target=worker, name="Surveyor-UI-Extensions-Batch", daemon=True).start()

    def _finish_agent_ui_extension_batch(self, entries: list[dict], failures: list[str]) -> None:
        for entry in entries:
            extension_id = entry["extension_id"]
            self.agent_ui_extension_installing.discard(extension_id)
            lane = next((item for item in (self.agent_snapshot or {}).get("lanes", []) if item.get("id") == extension_id), None)
            self._render_agent_ui_extension(lane or {"id": extension_id, "name": extension_id, "human_required": False})
        if failures:
            self.agent_ui_extension_notice.set("Some updates failed; those lanes kept their previous versions.")
            messagebox.showerror("Agent extension updates", "Some updates failed; successful updates remain active.\n\n" + "\n".join(failures), parent=self.agent_console_window)
        else:
            self.agent_ui_extension_notice.set("All available agent extensions updated and active.")
            self._update_agent_extension_summary()
        self._refresh_agent_extension_update_controls()

    def _extension_context(self) -> dict:
        return {
            "workflow_idle": not self.workflow_running,
            "nms_running": self.last_nms_running,
            "probe_connected": self.last_probe_connected,
            "runtime_capture_saved": _runtime_capture_saved(),
        }

    def _render_agent_ui_extension(self, lane: dict) -> None:
        extension_id = lane.get("id", "")
        body = self.agent_ui_extension_bodies.get(extension_id)
        if body is None or not body.winfo_exists():
            return
        control = self.agent_ui_extension_controls.get(extension_id)
        entry = next((item for item in self.agent_ui_extension_index if item["extension_id"] == extension_id), None)
        notice = self.agent_ui_extension_notices[extension_id]
        active = None
        panel = None
        extension_version = ""
        try:
            loaded = agent_ui_extensions.load_installed_extension(
                self.agent_ui_extensions_root,
                extension_id,
                CONTROLLER_VERSION,
                agent_ui_extensions.HOST_ACTION_IDS,
            )
            if loaded:
                manifest, panel = loaded
                active = manifest
                extension_version = manifest["version"]
        except Exception as exc:
            _log("agent_ui_extension_load_error", extension_id=extension_id, error=repr(exc))
            ttk.Label(body, text="This lane extension failed validation. Surveyor core actions are unaffected.", wraplength=310, justify="left").pack(anchor="w")
            notice.set("Installed panel failed validation.")

        if entry and (active is None or agent_ui_extensions.update_candidates([entry], self.agent_ui_extensions_root)):
            version = entry["version"]
            notice.set(f"Update available: v{version}")
        elif self.agent_ui_extension_error:
            notice.set("Update check failed; installed panel remains available.")
        elif active:
            notice.set(f"Extension v{extension_version} active")
        else:
            notice.set("No published extension for this lane")
        card = self.agent_cards.get(extension_id)
        if card:
            installed_text = f"Installed v{extension_version}" if extension_version else "Installed extension: none"
            published_text = f"Published v{entry['version']}" if entry else "No published extension"
            reported = str(lane.get("extension_version") or "").strip()
            reported_text = f" · Agent reports v{reported}" if reported else ""
            card["version"].set(f"{installed_text} · {published_text}{reported_text}")

        render_key = json.dumps({"entry": entry, "active": active, "panel": panel, "error": self.agent_ui_extension_error}, sort_keys=True, ensure_ascii=False)
        if self.agent_extension_render_keys.get(extension_id) == render_key:
            if panel and panel.get("actions") and card:
                card["action_label"].set("Action: " + str(panel["actions"][0]["label"]))
            self._refresh_agent_ui_lane_action_states(extension_id, lane)
            return

        self.agent_extension_render_keys[extension_id] = render_key
        for child in body.winfo_children():
            child.destroy()
        if control:
            for button in control["action_buttons"]:
                button.destroy()
            control["action_buttons"] = []
            control["action_specs"] = []
        lane_buttons: list[tuple[ttk.Button, list[str]]] = []
        self.agent_ui_action_buttons_by_lane[extension_id] = lane_buttons

        if panel:
            ttk.Label(body, text=panel["title"], font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(4, 0))
            if panel.get("summary"):
                ttk.Label(body, text=panel["summary"], wraplength=310, justify="left").pack(anchor="w", pady=(2, 2))
            for action in panel["actions"]:
                context = self._extension_context()
                reason_var = tk.StringVar(value=self._agent_action_reason(action["preconditions"], context, lane, bool(panel.get("request_only"))))
                if card and action is panel["actions"][0]:
                    card["action_reason"].set(self._agent_needs_text(action["preconditions"], context))
                if card and action is panel["actions"][0]:
                    card["action_label"].set("Action: " + str(action["label"]))
                enabled = agent_ui_extensions.action_button_enabled(
                    action["preconditions"], context,
                    request_only=bool(panel.get("request_only")),
                    requested=bool(lane.get("human_required")),
                )
                button = ttk.Button(
                    control["actions"] if control else body,
                    text=action["label"],
                    command=lambda a=action, i=extension_id, v=extension_version: self._run_agent_ui_extension_action(i, v, a),
                )
                button.pack(fill="x", pady=2)
                if not enabled:
                    button.state(["disabled"])
                lane_buttons.append((button, action["preconditions"]))
                if control:
                    control["action_buttons"].append(button)
                    control["action_specs"].append({
                        "button": button,
                        "extension_id": extension_id,
                        "version": extension_version,
                        "action": action,
                        "preconditions": action["preconditions"],
                        "request_only": bool(panel.get("request_only")),
                        "requested": bool(lane.get("human_required")),
                        "reason_var": reason_var,
                    })

        if active:
            versions = agent_ui_extensions.installed_versions(self.agent_ui_extensions_root, extension_id)
            older = [version for version in versions if agent_ui_extensions._version(version) < agent_ui_extensions._version(extension_version)]
            self.agent_ui_extension_rollback_versions[extension_id] = older[0] if older else ""
            if older:
                ttk.Label(body, text=f"Rollback available: v{older[0]}", wraplength=310).pack(anchor="w", pady=(4, 0))
        else:
            self.agent_ui_extension_rollback_versions.pop(extension_id, None)
        self.agent_ui_action_buttons = [
            item for lane_items in self.agent_ui_action_buttons_by_lane.values() for item in lane_items
        ]
        if control:
            control["steps"].state(["!disabled"] if lane.get("human_required") else ["disabled"])
        self._refresh_agent_extension_update_controls()

    def _refresh_agent_ui_lane_action_states(self, extension_id: str, lane: dict) -> None:
        control = self.agent_ui_extension_controls.get(extension_id)
        if not control:
            return
        requested = bool(lane.get("human_required"))
        control["steps"].state(["!disabled"] if requested else ["disabled"])
        context = self._extension_context()
        for spec in control["action_specs"]:
            enabled = agent_ui_extensions.action_button_enabled(
                spec["preconditions"], context,
                request_only=spec["request_only"], requested=requested,
            )
            spec["button"].state(["!disabled"] if enabled else ["disabled"])
            spec["reason_var"].set(
                self._agent_action_reason(spec["preconditions"], context, lane, spec["request_only"])
            )
        card = self.agent_cards.get(extension_id)
        if card and control["action_specs"]:
            first = control["action_specs"][0]
            card["action_label"].set("Action: " + str(first["action"]["label"]))
            card["action_reason"].set(self._agent_needs_text(first["preconditions"], context))

    @staticmethod
    def _agent_needs_text(preconditions: list[str], state: dict) -> str:
        if not preconditions:
            return "Needs: none"
        allowed, _reason = agent_ui_extensions.preconditions_met(preconditions, state)
        line = "Needs: " + ", ".join(preconditions)
        if not allowed:
            _ok, missing = agent_ui_extensions.preconditions_met(preconditions, state)
            line += "\nMissing now: " + missing.removeprefix("Needs: ")
        else:
            line += "\nReady"
        return line

    @staticmethod
    def _agent_action_reason(preconditions: list[str], state: dict, lane: dict, request_only: bool) -> str:
        if request_only and not lane.get("human_required"):
            return "Waiting for this lane to publish a Surveyor request."
        allowed, reason = agent_ui_extensions.preconditions_met(preconditions, state)
        if allowed:
            return "Ready to run. The upload receipt does not affect this action."
        labels = {
            "workflow.idle": "finish the current Surveyor action",
            "nms.running": "start NMS",
            "probe.connected": "wait for the probe connection",
            "runtime.capture_saved": "capture the root event and wait for Surveyor to save it",
        }
        failed = reason.removeprefix("Needs: ").split(", ")
        missing = [labels.get(item, item) for item in failed]
        prefix = "Request published; " if request_only and lane.get("human_required") else "Action unavailable; "
        return prefix + " and ".join(missing) + ". The upload receipt does not lock this button."

    def _confirm_agent_ui_extension_update(self, entry: dict) -> None:
        extension_id = entry["extension_id"]
        version = entry["version"]
        if extension_id in self.agent_ui_extension_installing:
            return
        # The persistent update button is the notice. Avoid repeated popups on refresh.
        if not messagebox.askyesno("Surveyor UI update", f"The {extension_id} agent has published a UI update (v{version}). Install it now?", parent=self.agent_console_window):
            return
        self.agent_ui_extension_installing.add(extension_id)
        self._refresh_agent_extension_update_controls()
        if extension_id in self.agent_ui_extension_notices:
            self.agent_ui_extension_notices[extension_id].set(f"Installing v{version}…")

        def worker() -> None:
            try:
                agent_ui_extensions.install_extension(
                    self.agent_ui_extensions_root,
                    entry,
                    CONTROLLER_VERSION,
                    agent_ui_extensions.HOST_ACTION_IDS,
                )
                error = ""
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
            try:
                self.window.after(0, lambda: self._finish_agent_ui_extension_update(extension_id, error))
            except (tk.TclError, RuntimeError):
                pass

        threading.Thread(target=worker, name=f"Surveyor-UI-Extension-{extension_id}", daemon=True).start()

    def _finish_agent_ui_extension_update(self, extension_id: str, error: str) -> None:
        self.agent_ui_extension_installing.discard(extension_id)
        notices = getattr(self, "agent_ui_extension_notices", {})
        if error:
            if extension_id in notices:
                notices[extension_id].set("Update failed; previous version remains active.")
            elif getattr(self, "agent_ui_extension_notice", None):
                self.agent_ui_extension_notice.set("Extension update failed. The previous version remains active.")
            _log("agent_ui_extension_update_failed", extension_id=extension_id, error=error)
            messagebox.showerror("Surveyor UI extension", f"The update failed; the previous version is still active.\n\n{error}", parent=self.agent_console_window)
        else:
            if extension_id in notices:
                notices[extension_id].set("Updated and active")
            elif getattr(self, "agent_ui_extension_notice", None):
                self.agent_ui_extension_notice.set(f"{extension_id} UI extension refreshed without restarting Surveyor.")
            _log("agent_ui_extension_updated", extension_id=extension_id)
            self._update_agent_extension_summary()
        lane = next((item for item in (getattr(self, "agent_snapshot", None) or {}).get("lanes", []) if item.get("id") == extension_id), None)
        lane = lane or getattr(self, "agent_selected_lane", None)
        if lane:
            self._render_agent_ui_extension(lane)
        if hasattr(self, "agent_ui_extension_update_buttons"):
            self._refresh_agent_extension_update_controls()

    def _rollback_agent_ui_extension(self, extension_id: str, version: str) -> None:
        try:
            agent_ui_extensions.activate_installed_extension(
                self.agent_ui_extensions_root,
                extension_id,
                version,
                CONTROLLER_VERSION,
                agent_ui_extensions.HOST_ACTION_IDS,
            )
            _log("agent_ui_extension_rollback", extension_id=extension_id, version=version)
            if extension_id in self.agent_ui_extension_notices:
                self.agent_ui_extension_notices[extension_id].set(f"Rolled back to v{version}")
            lane = next((item for item in (self.agent_snapshot or {}).get("lanes", []) if item.get("id") == extension_id), None)
            if lane:
                self._render_agent_ui_extension(lane)
        except Exception as exc:
            _log("agent_ui_extension_rollback_failed", extension_id=extension_id, version=version, error=repr(exc))
            messagebox.showerror("Surveyor UI extension", f"Rollback failed; the active extension was left unchanged.\n\n{exc}", parent=self.agent_console_window)

    def _run_agent_ui_extension_action(self, extension_id: str, version: str, action: dict) -> None:
        if action.get("action_id") not in agent_ui_extensions.HOST_ACTION_IDS:
            self._set_status("Extension action rejected", "The action ID is not registered by Surveyor.")
            return
        current = agent_ui_extensions.load_installed_extension(
            self.agent_ui_extensions_root, extension_id, CONTROLLER_VERSION, agent_ui_extensions.HOST_ACTION_IDS
        )
        if not current or current[0].get("version") != version:
            self._set_status("Extension action rejected", "The selected UI extension version is no longer active.")
            return
        state = self._extension_context()
        allowed, reason = agent_ui_extensions.preconditions_met(action["preconditions"], state)
        if not allowed:
            if not state.get("workflow_idle"):
                self._set_status("Agent action waiting", "Finish the current Surveyor action, then press this lane action again. The upload receipt does not lock it.")
                return
            if "nms.running" in action["preconditions"] and not state.get("nms_running"):
                if messagebox.askyesno(
                    "This lane needs NMS",
                    "This published action needs NMS and a live probe connection. The checked upload receipt is only history and does not block it. Start NMS now?",
                    parent=self.agent_console_window,
                ):
                    self.start_nms()
                else:
                    self._set_status("Agent action waiting", "Start NMS, wait until the probe shows Connected, then press the lane action again.")
                return
            if "probe.connected" in action["preconditions"] and not state.get("probe_connected"):
                self._set_status("Waiting for probe connection", "NMS is running, but the live probe has not connected yet. Wait for Surveyor to show Connected, then press the lane action again.")
                return
            self._set_status("Agent action unavailable", reason + ". Upload receipt state is not used as an action lock.")
            return
        calls = {
            "research.analyze_seed_function": ("Analyze seed function + upload", "Analyze-Dungeon-Seed-Function.cmd", "analyze-seed-function"),
            "research.extract_upstream_callers": ("Extract upstream callers + upload", "Extract-Dungeon-Upstream-Callers.cmd", "extract-upstream"),
            "research.extract_exact_root_caller": ("Extract exact root caller + upload", "Extract-Exact-Root-Caller-Code.cmd", "extract-exact-root-caller"),
            "research.resolve_root_vtable": ("Resolve root vtable + upload", "Resolve-Exact-Root-VTable.cmd", "resolve-root-vtable"),
            "research.extract_caller_code": ("Extract caller code + upload", "Extract-Dungeon-Caller-Code.cmd", "extract-caller"),
            "research.measure_generation": ("Measure generation + upload", "Measure-Derelict-Generation.cmd", "measure"),
            "research.prepare_assets": ("Prepare crate assets + upload", "Prepare-Crate-Assets.cmd", "prepare-assets"),
            "research.analyze_generation": ("Analyze generation + upload", "Analyze-Generation-Baseline.cmd", "analyze-generation"),
        }
        if action["action_id"] == "research.upload_runtime_capture":
            if not state.get("runtime_capture_saved"):
                self._set_status(
                    "Saved root capture not found",
                    "Run NMS until Root dispatch +0x10 is captured. The probe saves the evidence before you close the game.",
                )
                return
            helper = self.project_root / "tools" / "github_integration.py"
            self._run_steps(
                "Upload saved root capture",
                [("Upload Runtime-A root event", [self.python_exe, str(helper), "upload", "--action", "upload-runtime-capture"])],
                evidence_namespace=extension_id,
                extension_version=version,
                extension_action_id=action["action_id"],
                upload_action="upload-runtime-capture",
            )
            return
        call = calls.get(action["action_id"])
        if call is None:
            self._set_status("Agent action unavailable", "This Surveyor build has no handler for that action.")
            return
        _log("agent_ui_extension_action", extension_id=extension_id, version=version, action_id=action["action_id"])
        self._project_action(*call, evidence_namespace=extension_id, extension_version=version, extension_action_id=action["action_id"])

    def _eligible_agent_upload_actions(self, state: dict | None = None) -> list[dict]:
        context = state or self._extension_context()
        eligible = []
        for controls in self.agent_ui_extension_controls.values():
            for item in controls["action_specs"]:
                if item["request_only"] and not item["requested"]:
                    continue
                allowed, _reason = agent_ui_extensions.preconditions_met(item["preconditions"], context)
                if allowed:
                    eligible.append(item)
        return eligible

    def _upload_all_agent_evidence(self) -> None:
        if self.agent_ui_upload_queue_running:
            return
        actions = self._eligible_agent_upload_actions()
        if not actions:
            self.agent_ui_extension_notice.set("No lane upload actions are currently ready.")
            return
        steps = "\n".join(
            f"• {item['extension_id']}: {item['action']['label']}"
            for item in actions
        )
        if not messagebox.askyesno(
            "Upload all lane evidence",
            "Run each currently available lane action and upload its result? Actions run one at a time. Some may analyze or prepare evidence before uploading.\n\n"
            + steps,
            parent=self.agent_console_window,
        ):
            return
        self.agent_ui_upload_queue = list(actions)
        self.agent_ui_upload_queue_total = len(actions)
        self.agent_ui_upload_queue_running = True
        self._refresh_agent_upload_all_state()
        self._refresh_agent_extension_update_controls()
        for button, _preconditions in self.agent_ui_action_buttons:
            button.state(["disabled"])
        self._advance_agent_ui_upload_queue()

    def _advance_agent_ui_upload_queue(self) -> None:
        if not self.agent_ui_upload_queue_running:
            return
        if self.workflow_running:
            self.window.after(250, self._advance_agent_ui_upload_queue)
            return
        if not self.agent_ui_upload_queue:
            self.agent_ui_upload_queue_running = False
            total = self.agent_ui_upload_queue_total
            self.agent_ui_upload_queue_total = 0
            self._refresh_agent_upload_indicators()
            self.agent_ui_extension_notice.set(
                f"Upload-all finished ({total} lane action{'s' if total != 1 else ''}). Check each lane’s receipt above."
            )
            self._refresh_agent_upload_all_state()
            self._refresh_agent_extension_update_controls()
            return

        item = self.agent_ui_upload_queue.pop(0)
        action = item["action"]
        lane = next(
            (row for row in (self.agent_snapshot or {}).get("lanes", []) if row.get("id") == item["extension_id"]),
            {},
        )
        context = self._extension_context()
        allowed, reason = agent_ui_extensions.preconditions_met(item["preconditions"], context)
        if item["request_only"] and not lane.get("human_required"):
            allowed = False
            reason = "This lane no longer requests Surveyor input."
        if allowed:
            remaining = len(self.agent_ui_upload_queue)
            self.agent_ui_extension_notice.set(
                f"Uploading {item['extension_id']}: {action['label']} ({remaining} after this)."
            )
            self._run_agent_ui_extension_action(item["extension_id"], item["version"], action)
        else:
            _log("agent_ui_upload_all_skipped", extension_id=item["extension_id"], action_id=action["action_id"], reason=reason)
        self._refresh_agent_upload_all_state()
        self.window.after(250 if self.workflow_running else 25, self._advance_agent_ui_upload_queue)

    def _refresh_agent_upload_all_state(self) -> None:
        button = self.agent_ui_upload_all_button
        if not button:
            return
        if self.agent_ui_upload_queue_running:
            button.configure(text="Uploading…")
            button.state(["disabled"])
            return
        eligible = self._eligible_agent_upload_actions({
            "workflow_idle": not self.workflow_running,
            "nms_running": _nms_running(),
            "probe_connected": bool(self.probe_state.get().startswith("Connected")),
            "runtime_capture_saved": _runtime_capture_saved(),
        })
        button.configure(text=f"Upload all ({len(eligible)})" if eligible else "Upload all")
        button.state(["!disabled"] if eligible else ["disabled"])

    def _render_agent_details(self, lane: dict) -> None:
        card = self.agent_cards.get(lane.get("id", ""))
        if not card:
            return
        needs_you = bool(lane.get("human_required"))
        controls = self.agent_ui_extension_controls.get(lane.get("id", ""))
        if controls:
            controls["steps"].state(["!disabled"] if needs_you else ["disabled"])
        card["status"].set(("NEEDS SURVEYOR · " if needs_you else "NO SURVEYOR ACTION · ") + str(lane.get("status") or "status unknown"))
        card["summary"].set(str(lane.get("summary") or "No result summary has been published yet."))
        lines = []
        if lane.get("progress"):
            lines.append("Progress: " + str(lane["progress"]))
        if lane.get("blockers"):
            lines.append("Blockers: " + "; ".join(str(item) for item in lane["blockers"]))
        if lane.get("has_agent_status"):
            published_at = str(lane.get("updated_utc") or "timestamp missing")
            if agent_console.lane_status_is_stale(str(lane.get("updated_utc") or "")) is True:
                published_at += " · stale for over 15 minutes"
            lines.append("Lane status published: " + published_at)
        else:
            lines.append("No lane STATUS.json is published yet; showing registry/manifest fallback.")
        if lane.get("human_required"):
            lines.append("Surveyor request: " + str(lane.get("surveyor_request") or "Complete the steps below."))
            if lane.get("steps"):
                lines.extend(f"{index}. {step}" for index, step in enumerate(lane["steps"][:3], start=1))
                if len(lane["steps"]) > 3:
                    lines.append(f"…and {len(lane['steps']) - 3} more steps (Copy full steps)")
            if lane.get("success_condition"):
                lines.append("Success when: " + str(lane["success_condition"]))
            if lane.get("evidence_to_return"):
                lines.append("Return: " + ", ".join(str(item) for item in lane["evidence_to_return"][:3]))
            if lane.get("full_derelict_required") is not None:
                lines.append("Full traversal: " + ("Yes" if lane["full_derelict_required"] else "No"))
            lines.append('When done, return to Main and write "check".')
        elif lane.get("next_action"):
            lines.append("Next: " + str(lane["next_action"]))
        card["request"].set("\n".join(lines) if lines else "No Surveyor request is currently published.")
        if needs_you:
            needed = lane.get("surveyor_request") or "Complete the published Surveyor steps."
            card["action_needed"].set(str(needed))
            action = lane.get("next_action") or (lane.get("steps") or [""])[0]
            card["action_label"].set("Action: " + str(action) if action else "Action: see the published steps")
        else:
            card["action_needed"].set("No Surveyor action is currently published.")
            action = lane.get("next_action") or "No action requested"
            card["action_label"].set("Action: " + str(action))
        card["action_reason"].set("Needs: checking published action…" if needs_you else "Needs: none")

    def _refresh_agent_upload_indicators(self) -> None:
        for extension_id, card in self.agent_cards.items():
            record = agent_ui_extensions.latest_action_record(self.agent_ui_extensions_root, extension_id)
            upload_record = agent_ui_extensions.latest_upload_record(self.agent_ui_extensions_root, extension_id)
            uploaded = agent_ui_extensions.action_record_confirms_upload(upload_record)
            card["uploaded"].set(uploaded)
            if uploaded:
                stamp = str(upload_record.get("utc") or "upload confirmed")
                path = str(upload_record.get("upload_path") or "")
                card["upload_detail"].set(f"{path} · {stamp}")
            elif record and record.get("status") == "failed":
                card["upload_detail"].set("Latest lane action failed; no successful upload is confirmed.")
            elif record:
                card["upload_detail"].set("Latest lane action has no GitHub upload confirmation.")
            else:
                card["upload_detail"].set("No lane upload confirmed yet.")

    def _copy_agent_steps(self, lane_id: str | None = None) -> None:
        lane = next(
            (item for item in (self.agent_snapshot or {}).get("lanes", []) if item.get("id") == lane_id),
            None,
        ) if lane_id else self.agent_selected_lane
        if not lane or not lane.get("human_required"):
            return
        text = agent_console.build_instruction(lane)
        self.agent_console_window.clipboard_clear()
        self.agent_console_window.clipboard_append(text)
        self.agent_console_state.set("Surveyor steps copied. Complete them, then return here and write ‘check’.")

    def _copy_agent_summary(self) -> None:
        if not self.agent_snapshot:
            return
        rows = ["NMS Derelict Probe agent status"]
        for lane in self.agent_snapshot.get("lanes", []):
            rows.append(f"{lane.get('name')}: {lane.get('status')}")
            if lane.get("human_required"):
                rows.append("  Surveyor request: " + (lane.get("surveyor_request") or "see copied steps"))
                rows.extend(f"  {i}. {step}" for i, step in enumerate(lane.get("steps", []), start=1))
                if lane.get("full_derelict_required") is not None:
                    rows.append("  Full derelict traversal required: " + ("Yes" if lane["full_derelict_required"] else "No"))
        self.window.clipboard_clear()
        self.window.clipboard_append("\n".join(rows))
        self.agent_console_state.set("Agent status summary copied to clipboard.")

    def _close(self) -> None:
        try:
            if self.agent_console_window is not None and self.agent_console_window.winfo_exists():
                self.agent_console_window.destroy()
        finally:
            self.window.destroy()

    def _load_overlay_pref(self) -> bool:
        pref = ROOT / "overlay-enabled.txt"
        try:
            return pref.read_text(encoding="utf-8-sig").strip().lower() == "true"
        except Exception:
            return False

    def _save_overlay_pref(self) -> None:
        try:
            (ROOT / "overlay-enabled.txt").write_text("true" if self.overlay_enabled.get() else "false", encoding="utf-8")
        except Exception as exc:
            _log("overlay_pref_error", error=repr(exc))

    def _save_overlay_settings(self) -> None:
        settings = {key: bool(var.get()) for key, var in self.overlay_setting_vars.items()}
        settings.update({
            "opacity_percent": int(self.overlay_opacity.get()),
            "x_offset": int(self.overlay_x_offset.get()),
            "y_offset": int(self.overlay_y_offset.get()),
        })
        save_overlay_settings(ROOT / "overlay-settings.json", settings)

    def _publish_overlay_objectives(self) -> None:
        path = ROOT / "overlay-objectives.json"
        payload = build_agent_objectives(self.agent_snapshot, _read_json(LIVE_STATUS), _nms_running())
        existing = _read_json(path)
        if existing and {k: v for k, v in existing.items() if k != "updated_epoch"} == {k: v for k, v in payload.items() if k != "updated_epoch"}:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            os.replace(tmp, path)
        except OSError as exc:
            _log("overlay_objectives_error", error=repr(exc))

    def _refresh(self) -> None:
        running = _nms_running()
        self.start_nms_button.state(["disabled"] if running else ["!disabled"])
        self.source_version.set(self._source_version())

        live = _read_json(LIVE_STATUS)
        self._publish_overlay_objectives()
        view = summarize_status(live, nms_running=running)
        self.nms_state.set(view["nms"])
        self.probe_state.set(view["probe"])
        self.recording_state.set(view["capture"])
        self.counts_state.set(view["counts"])
        self.caller_scan_state.set(view["caller_scan"])
        self.root_caller_state.set(view["exact_root_caller"])
        self.root_resource_state.set(view["root_resource"])
        self.root_dispatch_state.set(view["root_dispatch"])
        overlay_state = _read_json(OVERLAY_STATE)
        overlay_heartbeat = float(overlay_state.get("heartbeat_epoch") or 0.0)
        is_overlay_window = bool(_find_overlay_window())
        self.overlay_state.set("Overlay status: running" if is_overlay_window or (overlay_heartbeat > 0 and time.time() - overlay_heartbeat < 6.0) else "Overlay status: stopped")
        for key, source_key in (
            ("detail", "detail"), ("telemetry", "telemetry"), ("overlay_counts", "counts"),
            ("auto_crates", "auto_crates"), ("loot_summary", "loot_summary"),
            ("room_loot", "room_loot"), ("trace", "trace"), ("generation", "generation"),
            ("event", "event"), ("root_resource", "root_resource"), ("root_dispatch", "root_dispatch"),
            ("hotkeys_1", "hotkeys_1"), ("hotkeys_2", "hotkeys_2"),
        ):
            self.overlay_detail_vars[key].set(view[source_key])
        heartbeat = float(live.get("heartbeat_epoch") or 0.0)
        fresh = heartbeat > 0 and time.time() - heartbeat < 3.5
        self.last_nms_running = running
        self.last_probe_connected = bool(running and fresh)
        self._refresh_agent_extension_action_states(running, running and fresh)
        if running and fresh:
            self.last_live_pid = int(live.get("process_id") or 0) or None
        elif not running:
            self.last_live_pid = None
        self.window.after(750, self._refresh)

    def _refresh_agent_extension_action_states(self, nms_running: bool, probe_connected: bool) -> None:
        state = {
            "workflow_idle": not self.workflow_running,
            "nms_running": nms_running,
            "probe_connected": probe_connected,
            "runtime_capture_saved": _runtime_capture_saved(),
        }
        upload_available = False
        for lane_id, controls in self.agent_ui_extension_controls.items():
            lane = next((row for row in (self.agent_snapshot or {}).get("lanes", []) if row.get("id") == lane_id), {})
            for item in controls["action_specs"]:
                try:
                    enabled = agent_ui_extensions.action_button_enabled(
                        item["preconditions"], state,
                        request_only=item["request_only"],
                        requested=bool(lane.get("human_required")),
                    )
                    if self.agent_ui_upload_queue_running:
                        enabled = False
                    item["button"].state(["!disabled"] if enabled else ["disabled"])
                    item["reason_var"].set(self._agent_action_reason(item["preconditions"], state, lane, item["request_only"]))
                    if controls["action_specs"] and item is controls["action_specs"][0]:
                        card = self.agent_cards.get(lane_id)
                        if card:
                            card["action_reason"].set(self._agent_needs_text(item["preconditions"], state))
                    ready, _reason = agent_ui_extensions.preconditions_met(item["preconditions"], state)
                    if enabled and ready:
                        upload_available = True
                except tk.TclError:
                    continue
        if self.agent_ui_upload_all_button:
            if self.agent_ui_upload_queue_running:
                self.agent_ui_upload_all_button.configure(text="Uploading…")
                self.agent_ui_upload_all_button.state(["disabled"])
            else:
                self.agent_ui_upload_all_button.configure(
                    text="Upload all" if not upload_available else f"Upload all ({sum(1 for item in self._eligible_agent_upload_actions(state))})"
                )
                self.agent_ui_upload_all_button.state(["!disabled"] if upload_available else ["disabled"])

    def _set_status(self, status: str, detail: str = "") -> None:
        self.window.after(0, lambda: self.workflow_status.set(status))
        self.window.after(0, lambda: self.workflow_detail.set(detail))

    def start_nms(self) -> None:
        if _nms_running():
            self._set_status("NMS already running", "Surveyor stays connected while the game is open.")
            return
        script = self.project_root / "Start-NMS.ps1"
        if not script.is_file():
            self._set_status("Start NMS unavailable", "Start-NMS.ps1 is missing from the Surveyor project.")
            return
        self._save_overlay_pref()
        mode = "overlay" if self.overlay_enabled.get() else "nooverlay"
        command = [_powershell(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), "-ProjectRoot", str(self.project_root), "-OverlayMode", mode]
        self._run_steps("Start NMS", [("Prepare and launch NMS", command)], visible=False)

    def start_overlay(self) -> None:
        if os.name != "nt":
            self._set_status("Overlay unavailable", "The game overlay can only run on Windows.")
            return
        script = self.project_root / "overlay" / "derelict_overlay.py"
        if not script.is_file():
            self._set_status("Overlay unavailable", "overlay/derelict_overlay.py is missing from the project.")
            return
        if _find_overlay_window():
            self._set_status("Overlay already running", "The existing Surveyor overlay is active.")
            return
        try:
            OVERLAY_STOP_REQUEST.unlink(missing_ok=True)
            python = Path(_external_python())
            pythonw = python.with_name("pythonw.exe")
            executable = str(pythonw if pythonw.is_file() else python)
            flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            subprocess.Popen(
                [executable, str(script), "--status", str(LIVE_STATUS), "--stop-file", str(OVERLAY_STOP_REQUEST)],
                cwd=str(self.project_root), creationflags=flags, close_fds=True,
            )
            self._set_status("Overlay starting", "The overlay will appear over No Man’s Sky when its window is detected.")
        except Exception as exc:
            self._set_status("Start overlay failed", f"{type(exc).__name__}: {exc}")
            _log("overlay_start_failed", error=repr(exc))

    def stop_overlay(self) -> None:
        try:
            ROOT.mkdir(parents=True, exist_ok=True)
            OVERLAY_STOP_REQUEST.write_text("stop\n", encoding="utf-8")
            hwnd = _find_overlay_window()
            if hwnd:
                ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
            self._set_status("Overlay stopping", "The overlay will close on its next refresh.")
        except Exception as exc:
            self._set_status("Stop overlay failed", f"{type(exc).__name__}: {exc}")
            _log("overlay_stop_failed", error=repr(exc))

    def restart_controller(self) -> None:
        if self.workflow_running:
            self._set_status("Restart blocked", "Wait for the current action to finish first.")
            return
        try:
            script = self.project_root / "tools" / "surveyor_controller.py"
            if not script.is_file():
                raise FileNotFoundError(script)
            python = _external_python()
            pythonw = str(Path(python).with_name("pythonw.exe")) if os.name == "nt" else python
            if os.name == "nt" and not Path(pythonw).is_file():
                pythonw = python
            flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            subprocess.Popen([pythonw, str(script), "--project-root", str(self.project_root)], cwd=str(self.project_root), creationflags=flags if os.name == "nt" else 0, close_fds=True)
            _log("controller_restart", nms_running=_nms_running())
            self.window.after(150, self.window.destroy)
        except Exception as exc:
            self._set_status("Restart Surveyor failed", f"{type(exc).__name__}: {exc}")
            _log("controller_restart_failed", error=repr(exc))

    def install_derelict_farming_archive(self) -> None:
        archive = filedialog.askopenfilename(
            parent=self.window,
            title="Select your DerelictFreighterFarming archive",
            filetypes=[("ZIP archives", "*.zip"), ("All files", "*.*")],
        )
        if not archive:
            return
        helper = self.project_root / "tools" / "github_integration.py"
        self._run_steps("Install DerelictFreighterFarming", [(
            "Validate and install mod archive",
            [self.python_exe, str(helper), "install-derelict-farming", "--archive", archive],
        )])

    def _integration(self, label: str, subcommand: str, visible: bool = False) -> None:
        helper = self.project_root / "tools" / "github_integration.py"
        if not helper.is_file():
            self._set_status("GitHub helper missing", str(helper))
            return
        self._run_steps(label, [(label, [self.python_exe, str(helper), subcommand])], visible=visible)

    def upload_all_saved_evidence(self) -> None:
        helper = self.project_root / "tools" / "github_integration.py"
        if not helper.is_file():
            self._set_status("GitHub helper missing", str(helper))
            return
        self._run_steps(
            "Upload all saved evidence",
            [("Upload deduplicated saved research files", [self.python_exe, str(helper), "upload", "--action", "all-saved-evidence"])],
            upload_action="all-saved-evidence",
        )

    def _project_action_command(self, cmd_name: str) -> list[str] | None:
        lower = cmd_name.lower()
        if lower.endswith(".cmd"):
            ps1 = self.project_root / (cmd_name[:-4] + ".ps1")
            if ps1.is_file():
                return [_powershell(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1)]
        mapping = {
            "extract-dungeon-caller-code.cmd": self.project_root / "tools" / "extract_nms_caller_code.py",
            "extract-dungeon-upstream-callers.cmd": self.project_root / "tools" / "extract_nms_upstream_callers.py",
            "extract-exact-root-caller-code.cmd": self.project_root / "tools" / "extract_exact_root_caller_code.py",
            "resolve-exact-root-vtable.cmd": self.project_root / "tools" / "resolve_exact_root_vtable.py",
            "analyze-dungeon-seed-function.cmd": self.project_root / "tools" / "analyze_nms_seed_function.py",
        }
        tool = mapping.get(lower)
        if tool and tool.is_file():
            return [self.python_exe, str(tool)]
        cmd = self.project_root / cmd_name
        if cmd.is_file() and os.name == "nt":
            return [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", str(cmd)]
        return None

    def _project_action(
        self,
        label: str,
        cmd_name: str,
        upload_action: str,
        evidence_namespace: str = "",
        extension_version: str = "",
        extension_action_id: str = "",
    ) -> None:
        command = self._project_action_command(cmd_name)
        if command is None:
            self._set_status("Research action unavailable", f"Missing workflow for {cmd_name}")
            return
        helper = self.project_root / "tools" / "github_integration.py"
        self._run_steps(label, [
            ("Run research command", command),
            ("Upload generated evidence", [self.python_exe, str(helper), "upload", "--action", upload_action]),
        ], evidence_namespace=evidence_namespace, extension_version=extension_version,
           extension_action_id=extension_action_id, upload_action=upload_action)

    def _run_steps(
        self,
        label: str,
        steps: list[tuple[str, list[str]]],
        visible: bool = False,
        evidence_namespace: str = "",
        extension_version: str = "",
        extension_action_id: str = "",
        upload_action: str = "",
    ) -> None:
        if self.workflow_running:
            self._set_status("Another action is running", "Wait for the current action to finish.")
            return
        self.workflow_running = True
        self._latest_output = ""
        self._latest_progress = ""
        self._set_status(f"Running: {label}", f"Step 1/{len(steps)}")
        self.output_events.put(("clear", ""))

        def worker() -> None:
            env = os.environ.copy()
            env["NMSDS_NONINTERACTIVE"] = "1"
            env["NMSDS_PARENT_ACTION"] = label
            env.pop("NMSDS_EVIDENCE_NAMESPACE", None)
            if evidence_namespace:
                env["NMSDS_EVIDENCE_NAMESPACE"] = evidence_namespace
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "-", label).strip("-").lower() or "action"
            if evidence_namespace:
                safe_name = f"{evidence_namespace}-{safe_name}"
            per_log = LOG_DIR / f"latest-{safe_name}.log"
            archive = LOG_DIR / f"{timestamp}-{safe_name}.log"
            all_output: list[str] = []
            returncode = 0
            failed_step = ""
            last_command: list[str] = []
            try:
                for index, (step_name, command) in enumerate(steps, start=1):
                    last_command = command
                    self._set_status(f"Running: {label}", f"Step {index}/{len(steps)}: {step_name}")
                    command_text = subprocess.list2cmdline(command) if os.name == "nt" else shlex.join(command)
                    self.output_events.put(("command", f"Command: {command_text}"))
                    self.output_events.put(("line", f"===== STEP {index}/{len(steps)} {step_name} =====\nCommand: {command_text}\n"))
                    _log("workflow_step_started", label=label, step=step_name, command=" ".join(_safe(x) for x in command))
                    flags = 0
                    if os.name == "nt" and not visible:
                        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                    if visible:
                        proc = subprocess.run(command, cwd=str(self.project_root), env=env, check=False, creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0) if os.name == "nt" else 0)
                        stdout = ""
                        stderr = ""
                    else:
                        chunks: list[str] = []
                        with subprocess.Popen(command, cwd=str(self.project_root), env=env,
                                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                              text=True, errors="replace", bufsize=1,
                                              creationflags=flags) as proc:
                            assert proc.stdout is not None
                            for line in proc.stdout:
                                chunks.append(line)
                                self.output_events.put(("line", line))
                                self._latest_output = line.strip()
                                if "progress" in line.lower() or re.search(r"\b\d{1,3}%", line):
                                    self._latest_progress = line.strip()
                            proc.wait()
                        stdout = "".join(chunks)
                        stderr = ""
                    returncode = proc.returncode
                    self._latest_output = f"Exit status: {returncode}"
                    self.output_events.put(("line", f"Exit status: {returncode}\n"))
                    text = f"===== STEP {index}/{len(steps)} {step_name} =====\nCommand: {' '.join(_safe(x) for x in command)}\nReturn code: {returncode}\n\nSTDOUT\n{_safe(stdout or '<empty>')}\n\nSTDERR\n{_safe(stderr or '<empty>')}\n"
                    all_output.append(text)
                    if returncode != 0:
                        failed_step = step_name
                        break
                LOG_DIR.mkdir(parents=True, exist_ok=True)
                block = f"===== {timestamp} START {label} =====\n" + "\n".join(all_output) + f"===== END {label} =====\n"
                per_log.write_text(block, encoding="utf-8")
                archive.write_text(block, encoding="utf-8")
                with WORKFLOW_LOG.open("a", encoding="utf-8") as fh:
                    fh.write(block)
                WORKFLOW_DIAGNOSTIC.write_text(
                    "NMS Derelict Surveyor standalone workflow diagnostic\n"
                    f"UTC: {_utc()}\nController version: {CONTROLLER_VERSION}\nAction: {label}\n"
                    f"Failed step: {failed_step or 'none'}\nReturn code: {returncode}\n\n" + "\n".join(all_output),
                    encoding="utf-8",
                )
                combined = "\n".join(all_output)
                if evidence_namespace and extension_version and extension_action_id:
                    upload_match = re.search(
                        rf"https://github\.com/{re.escape(agent_ui_extensions.REPOSITORY)}/tree/[^/\s]+/(research-uploads/[^\s]+)",
                        combined,
                    )
                    upload_path = upload_match.group(1).rstrip(".,)") if upload_match else ""
                    try:
                        record = agent_ui_extensions.write_action_record(
                            self.agent_ui_extensions_root,
                            evidence_namespace,
                            extension_version,
                            extension_action_id,
                            "complete" if returncode == 0 else "failed",
                            f"Exit status: {returncode}; failed step: {failed_step or 'none'}",
                            upload_path,
                        )
                        _log("agent_ui_extension_action_recorded", extension_id=evidence_namespace, record=record)
                    except Exception as record_error:
                        _log("agent_ui_extension_action_record_error", extension_id=evidence_namespace, error=repr(record_error))
                    try:
                        self.window.after(0, self._refresh_agent_upload_indicators)
                    except (tk.TclError, RuntimeError):
                        pass
                elif upload_action == "all-saved-evidence":
                    upload_match = re.search(
                        rf"https://github\.com/{re.escape(agent_ui_extensions.REPOSITORY)}/tree/[^/\s]+/(research-uploads/[^\s]+)",
                        combined,
                    )
                    upload_path = upload_match.group(1).rstrip(".,)") if upload_match else ""
                    versions = {item.get("extension_id"): item.get("version", "") for item in self.agent_ui_extension_index}
                    for lane in agent_console.LANES:
                        lane_id = lane["id"]
                        try:
                            agent_ui_extensions.write_action_record(
                                self.agent_ui_extensions_root,
                                lane_id,
                                versions.get(lane_id) or "shared-evidence-batch",
                                "research.upload_all_saved_evidence",
                                "complete" if returncode == 0 and upload_path else "failed",
                                "Deduplicated all available saved evidence in one shared main-branch upload.",
                                upload_path,
                            )
                        except Exception as record_error:
                            _log("agent_ui_extension_action_record_error", extension_id=lane_id, error=repr(record_error))
                    try:
                        self.window.after(0, self._refresh_agent_upload_indicators)
                    except (tk.TclError, RuntimeError):
                        pass
                remote = re.search(r"NMSDS_REMOTE_VERSION=([^\r\n]+)", combined)
                status = re.findall(r"NMSDS_STATUS=([^\r\n]+)", combined)
                detail = re.findall(r"NMSDS_DETAIL=([^\r\n]+)", combined)
                if remote:
                    self.available_version = remote.group(1).strip()
                    self.window.after(0, lambda: self.available_version_var.set(self.available_version))
                if returncode == 0:
                    if label == "Install update":
                        self.window.after(0, lambda: self.source_version.set(self._source_version()))
                    status_text = status[-1].strip() if status else f"Complete: {label}"
                    detail_text = detail[-1].strip() if detail else "Completed successfully."
                    self._set_status(status_text, detail_text)
                else:
                    self._set_status(f"Failed: {label} (exit {returncode})", f"Failed at {failed_step}. Open workflow diagnostic.")
            except Exception as exc:
                _log("workflow_exception", label=label, error=repr(exc))
                self._set_status(f"Failed: {label}", f"{type(exc).__name__}: {exc}")
            finally:
                self.workflow_running = False
        threading.Thread(target=worker, name=f"Surveyor-{label}", daemon=True).start()

    def _send_probe_command(self, action: str) -> None:
        if not _nms_running():
            self._set_status("NMS is not running", "Start NMS before sending a live capture command.")
            return
        payload = {"version": 1, "id": f"{time.time_ns()}", "utc": _utc(), "action": action}
        tmp = COMMAND_FILE.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            os.replace(tmp, COMMAND_FILE)
            self._set_status("Command sent", action.replace("_", " "))
            _log("probe_command_sent", action=action, id=payload["id"])
        except Exception as exc:
            self._set_status("Could not send command", f"{type(exc).__name__}: {exc}")

    @staticmethod
    def _open_file(path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text("No log has been generated yet.\n", encoding="utf-8")
        if os.name == "nt":
            subprocess.Popen(["notepad.exe", str(path)])

    def open_workflow_log(self) -> None:
        self._open_file(WORKFLOW_LOG)

    def open_workflow_diagnostic(self) -> None:
        self._open_file(WORKFLOW_DIAGNOSTIC)

    def run(self) -> None:
        self.window.mainloop()
        _log("controller_closed")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root")
    args = ap.parse_args()
    try:
        project = _project_root(args.project_root)
        SurveyorController(project).run()
        return 0
    except Exception as exc:
        _log("controller_fatal", error=f"{type(exc).__name__}: {exc}")
        try:
            messagebox.showerror("NMS Derelict Surveyor", f"Surveyor could not start:\n\n{type(exc).__name__}: {exc}")
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
