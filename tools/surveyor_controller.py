Warning: truncated output (original token count: 33755)
Total output lines: 2476

from __future__ import annotations

import argparse
import ctypes
import hashlib
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
from typing import Any, Callable

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

CONTROLLER_VERSION = "0.3.64"
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
RUNTIME_CAPTURE_UPLOAD_RECEIPT = ROOT / "runtime-capture-upload-receipt.json"
ROOT_EVENT_UPLOAD_RECEIPT = ROOT / "root-event-upload-receipt.json"
ROOT_EVENT_FILE = WORK / "root-event-latest.json"
RUNTIME_CAPTURE_OUTBOX = ROOT / "runtime-capture-outbox"
AUTO_UPLOAD_SETTINGS = ROOT / "auto-upload-settings.json"
AUTO_RESEARCH_SETTINGS = ROOT / "auto-research-settings.json"
AUTO_RESEARCH_RECEIPT = ROOT / "auto-research-last-session.json"
AUTO_EVIDENCE_UPLOAD_INTERVAL_SECONDS = 30.0


def _load_auto_upload_setting() -> bool:
    try:
        value = json.loads(AUTO_UPLOAD_SETTINGS.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return True
    return bool(value.get("enabled", True)) if isinstance(value, dict) else True


def _load_auto_research_setting() -> bool:
    try:
        value = json.loads(AUTO_RESEARCH_SETTINGS.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return True
    return bool(value.get("enabled", True)) if isinstance(value, dict) else True


def _saved_session_snapshot(status: dict[str, Any], sessions_dir: Path = ROOT / "sessions") -> tuple[str, Path] | None:
    """Return a stable signature/path only when the probe reports a saved session on disk."""
    if status.get("state") != "saved":
        return None
    detail = str(status.get("detail") or "")
    match = re.search(r"Saved baseline\s*[—-]\s*([^;]+);", detail)
    if not match:
        return None
    name = match.group(1).strip()
    if not name or Path(name).name != name or not name.lower().endswith(".json"):
        return None
    path = sessions_dir / name
    try:
        raw = path.read_bytes()
        session = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(session, dict) or not session.get("ended_utc"):
        return None
    signature = hashlib.sha256(raw).hexdigest()
    return signature, path


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


def _runtime_capture_snapshot(path: Path = RUNTIME_CAPTURE_FILE) -> tuple[str, bytes] | None:
    """Return a stable fingerprint and bytes for a valid saved root event."""
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    capture = value.get("owner_plus_0x10_capture") if isinstance(value, dict) else None
    if not isinstance(value, dict) or value.get("schema_version") != 1 or not isinstance(capture, dict):
        return None
    if capture.get("read_status") not in {"captured", "unreadable"}:
        return None
    return hashlib.sha256(raw).hexdigest(), raw


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
        self.runtime_capture_upload_inflight = ""
        self.runtime_capture_candidate = ""
        self.runtime_capture_candidate_since = 0.0
        self.runtime_capture_retry_after = 0.0
        self.runtime_capture_last_uploaded = str(_read_json(RUNTIME_CAPTURE_UPLOAD_RECEIPT).get("sha256") or "")
        self.root_event_candidate = ""
        self.root_event_candidate_since = 0.0
        root_receipt = _read_json(ROOT_EVENT_UPLOAD_RECEIPT)
        self.root_event_last_uploaded = str(root_receipt.get("root_sha256") or root_receipt.get("sha256") or "")
        self.recovery_signature_last_uploaded = str(root_receipt.get("signature") or "")
        self.recovery_evidence_last_upload = 0.0
        self.auto_upload_enabled = tk.BooleanVar(value=_load_auto_upload_setting())
        self.auto_research_enabled = tk.BooleanVar(value=_load_auto_research_setting())
        self.auto_research_pending: list[tuple[str, Path]] = []
        self.auto_research_last_signature = str(_read_json(AUTO_RESEARCH_RECEIPT).get("session_sha256") or "")
        self.auto_research_running_signature = ""
        if not self.auto_research_last_signature:
            current_saved = _saved_session_snapshot(_read_json(LIVE_STATUS))
            if current_saved:
                self.auto_research_last_signature = current_saved[0]
                self._write_auto_research_receipt(current_saved[0], current_saved[1], "already-saved-at-startup")
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
        self.parallel_test_state = tk.StringVar(value="No parallel research test has run from this Surveyor yet.")
        self.auto_research_state = tk.StringVar(value="Automatic research runs after a new saved derelict session is detected.")
        self.output_events: queue.SimpleQueue[tuple[str, str]] = queue.SimpleQueue()
        self._latest_output = ""
        self._latest_progress = ""
        self.overlay_enabled = tk.BooleanVar(value=self._load_overlay_pref())
        self.overlay_state = tk.StringVar(value="Overlay status: checking")
        overlay_settings = load_overlay_settings(ROOT / "overlay-settings.json")
        self.overlay_setting_vars = {key: tk.BooleanVar(value=overlay_settings[key]) for key in ("show_rooms", "show_research", "show_position", "show_manual", "show_hotkeys", "show_objectives")}
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
        for title, key in (("Rooms", "show_rooms"), ("Research", "show_research"), ("Position", "show_position"), ("Manual counts", "show_manual"), ("Hotkeys", "show_hotkeys"), ("Agent objectives", "show_objectives")):
            ttk.Checkbutton(toggles, text=title, variable=self.overlay_setting_vars[key], command=self._save_overlay_settings).pack(side="left", padx=(0, 10))
        self._overlay_slider(display, "Opacity", self.overlay_opacity, 20, 100, "%")
        self._overlay_slider(display, "Horizontal position", self.overlay_x_offset, -800, 800, " px")
        self._overlay_slider(display, "Vertical position", self.overlay_y_offset, -500, 600, " px")
        ttk.Label(display, text="Display settings apply live. Position is relative to the game window.", wraplength=690).pack(anchor="w", pady=(3, 0))

        updates_group, updates = self._make_collapsible_section(root, "GitHub / updates", padding=8)
        updates_group.pack(fill="x", pady=(0, 10))
        ttk.Checkbutton(
            updates,
            text="Automatically upload new probe captures and share updated evidence with all lanes",
            variable=self.auto_upload_enabled,
            command=self._save_auto_upload_setting,
        ).pack(anchor="w", pady=(0, 6))
        ttk.Label(
            updates,
            text="When enabled, a captured root event uploads in the background; completed research and lane actions also publish a deduplicated all-lanes evidence batch.",
            wraplength=690,
        ).pack(anchor="w", pady=(0, 6))
        update_buttons = ttk.Frame(updates)
        update_buttons.pack(fill="x")
        self._button_grid(update_buttons, [
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

        parallel_group, parallel = self._make_collapsible_section(root, "Parallel research test", padding=8)
        parallel_group.pack(fill="x", pady=(0, 10))
        ttk.Label(
            parallel,
            text="Runs the eight offline research actions against one start-of-run evidence snapshot. It does not hook NMS. The queue stays local; when automatic uploads are enabled, only the combined report is shared with all four lanes.",
            wraplength=690,
            justify="left",
        ).pack(anchor="w", pady=(0, 6))
        ttk.Checkbutton(
            parallel,
            text="Automatically run all research actions after a derelict session is saved",
            variable=self.auto_research_enabled,
            command=self._save_auto_research_setting,
        ).pack(anchor="w", pady=(0, 4))
        ttk.Label(parallel, textvariable=self.auto_research_state, wraplength=690, justify="left").pack(anchor="w", pady=(0, 6))
        self.parallel_test_button = ttk.Button(
            parallel, text="Run all research actions in parallel",
            command=lambda: self.run_parallel_research_test(trigger_kind="manual_button"),
        )
        self.parallel_test_button.pack(anchor="w", pady=(0, 4))
        ttk.Label(parallel, textvariable=self.parallel_test_state, wraplength=690, justify="left").pack(anchor="w")

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
            self.agent_upl…13755 tokens truncated…
                self.auto_research_pending.clear()
            self.auto_research_state.set("Automatic research is enabled." if self.auto_research_enabled.get() else "Automatic research is off; use Run all research actions in parallel when ready.")
        except OSError as exc:
            self._set_status("Could not save automatic research setting", str(exc))

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
        self._maybe_auto_run_research_after_saved_session(live)
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
        self._maybe_auto_upload_runtime_capture()
        self.window.after(750, self._refresh)

    def _maybe_auto_upload_runtime_capture(self) -> None:
        """Debounce newly saved root evidence, snapshot it, and upload in the workflow queue."""
        if not self.auto_upload_enabled.get():
            return
        snapshot = _runtime_capture_snapshot()
        if snapshot is None:
            self.runtime_capture_candidate = ""
            self._maybe_auto_upload_root_event()
            return
        fingerprint, raw = snapshot
        if fingerprint == self.runtime_capture_last_uploaded:
            self.runtime_capture_candidate = ""
            self._maybe_auto_upload_root_event()
            return
        if fingerprint != self.runtime_capture_candidate:
            self.runtime_capture_candidate = fingerprint
            self.runtime_capture_candidate_since = time.monotonic()
            return
        if (
            time.monotonic() - self.runtime_capture_candidate_since < 2.0
            or time.monotonic() < self.runtime_capture_retry_after
            or self.workflow_running
            or self.runtime_capture_upload_inflight
        ):
            return

        snapshot_dir = RUNTIME_CAPTURE_OUTBOX / fingerprint
        snapshot_path = snapshot_dir / "exact-root-caller-latest.json"
        try:
            snapshot_dir.mkdir(parents=True, exist_ok=True)
            if not snapshot_path.exists():
                temp_path = snapshot_path.with_suffix(".json.tmp")
                temp_path.write_bytes(raw)
                os.replace(temp_path, snapshot_path)
        except OSError as exc:
            _log("runtime_capture_snapshot_failed", sha256=fingerprint, error=repr(exc))
            self.runtime_capture_retry_after = time.monotonic() + 30.0
            return

        helper = self.project_root / "tools" / "github_integration.py"
        command = [
            self.python_exe, str(helper), "upload", "--action", "upload-runtime-capture",
            "--capture-file", str(snapshot_path),
        ]
        steps = [("Upload saved Runtime-A event", command)]
        if self.auto_upload_enabled.get():
            steps.append(("Share changed evidence with all lanes", [
                self.python_exe, str(helper), "upload", "--action", "all-saved-evidence", "--only-if-changed",
            ]))
        self.runtime_capture_upload_inflight = fingerprint
        _log("runtime_capture_auto_upload_started", sha256=fingerprint, snapshot=str(snapshot_path))
        self._run_steps(
            "Auto-upload captured root event",
            steps,
            upload_action="upload-runtime-capture",
            on_complete=lambda code, key=fingerprint: self._finish_runtime_capture_auto_upload(key, code),
        )

    def _maybe_auto_upload_root_event(self) -> None:
        """Share pending root evidence and batch ongoing journal growth safely."""
        try:
            raw = ROOT_EVENT_FILE.read_bytes()
            root_doc = json.loads(raw.decode("utf-8"))
            if not isinstance(root_doc, dict) or root_doc.get("schema_version") != 1:
                raw = b""
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            raw = b""
        root_sha = hashlib.sha256(raw).hexdigest() if raw else ""
        journals = sorted(ROOT.glob("capture-journal-*.jsonl"), key=lambda path: path.stat().st_mtime_ns)
        latest_journal = journals[-1] if journals else None
        if not root_sha and latest_journal is None:
            return
        signature_hash = hashlib.sha256()
        signature_hash.update(root_sha.encode("ascii"))
        for path in journals:
            try:
                stat = path.stat()
            except OSError:
                continue
            signature_hash.update(f"{path.name}:{stat.st_size}:{stat.st_mtime_ns}".encode("utf-8"))
        signature = signature_hash.hexdigest()
        if signature == self.recovery_signature_last_uploaded:
            self.root_event_candidate = ""
            return
        if signature != self.root_event_candidate:
            self.root_event_candidate = signature
            self.root_event_candidate_since = time.monotonic()
        now = time.monotonic()
        new_root = bool(root_sha and root_sha != self.root_event_last_uploaded)
        settled = now - self.root_event_candidate_since >= 2.0
        periodic_due = (self.recovery_evidence_last_upload == 0.0 or
                        now - self.recovery_evidence_last_upload >= AUTO_EVIDENCE_UPLOAD_INTERVAL_SECONDS)
        if not settled or (not new_root and not periodic_due):
            return
        if (now < self.runtime_capture_retry_after or self.workflow_running or
                self.runtime_capture_upload_inflight):
            return
        helper = self.project_root / "tools" / "github_integration.py"
        command = [self.python_exe, str(helper), "upload", "--action", "all-saved-evidence", "--only-if-changed"]
        self.runtime_capture_upload_inflight = signature
        _log("recovery_evidence_auto_upload_started", signature=signature, root_sha256=root_sha)
        self._run_steps(
            "Auto-upload saved recovery evidence",
            [("Share saved run evidence with all lanes", command)],
            upload_action="all-saved-evidence",
            on_complete=lambda code, key=signature, root=root_sha: self._finish_root_event_auto_upload(key, root, code),
        )

    def _finish_root_event_auto_upload(self, signature: str, root_sha: str, returncode: int) -> None:
        self.runtime_capture_upload_inflight = ""
        if returncode != 0:
            self.runtime_capture_retry_after = time.monotonic() + 60.0
            _log("recovery_evidence_auto_upload_failed", signature=signature, returncode=returncode)
            return
        payload = {"schema_version": 1, "signature": signature, "root_sha256": root_sha,
                   "uploaded_utc": _utc(), "automatic": True}
        try:
            temp_path = ROOT_EVENT_UPLOAD_RECEIPT.with_suffix(".json.tmp")
            temp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            os.replace(temp_path, ROOT_EVENT_UPLOAD_RECEIPT)
            self.root_event_last_uploaded = root_sha
            self.recovery_signature_last_uploaded = signature
            self.recovery_evidence_last_upload = time.monotonic()
            self.root_event_candidate = ""
            self.runtime_capture_retry_after = 0.0
            _log("recovery_evidence_auto_upload_complete", signature=signature, root_sha256=root_sha)
        except OSError as exc:
            _log("recovery_evidence_upload_receipt_failed", signature=signature, error=repr(exc))

    def _finish_runtime_capture_auto_upload(self, fingerprint: str, returncode: int, automatic: bool = True) -> None:
        self.runtime_capture_upload_inflight = ""
        if returncode != 0:
            self.runtime_capture_retry_after = time.monotonic() + 60.0
            _log("runtime_capture_auto_upload_failed", sha256=fingerprint, returncode=returncode)
            return
        payload = {"schema_version": 1, "sha256": fingerprint, "uploaded_utc": _utc(), "automatic": automatic}
        try:
            RUNTIME_CAPTURE_UPLOAD_RECEIPT.parent.mkdir(parents=True, exist_ok=True)
            temp_path = RUNTIME_CAPTURE_UPLOAD_RECEIPT.with_suffix(".json.tmp")
            temp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            os.replace(temp_path, RUNTIME_CAPTURE_UPLOAD_RECEIPT)
            self.runtime_capture_last_uploaded = fingerprint
            self.runtime_capture_candidate = ""
            self.runtime_capture_retry_after = 0.0
            _log("runtime_capture_upload_complete", sha256=fingerprint, automatic=automatic)
        except OSError as exc:
            _log("runtime_capture_upload_receipt_failed", sha256=fingerprint, error=repr(exc))

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

    def _maybe_auto_run_research_after_saved_session(self, live: dict[str, Any]) -> None:
        if not self.auto_research_enabled.get():
            return
        snapshot = _saved_session_snapshot(live)
        if snapshot is None:
            return
        signature, path = snapshot
        queued_signatures = {item[0] for item in self.auto_research_pending}
        if signature in {self.auto_research_last_signature, self.auto_research_running_signature} or signature in queued_signatures:
            return
        self.auto_research_pending.append((signature, path))
        self.auto_research_state.set(f"Saved session detected: {path.name}; queued {len(self.auto_research_pending)} saved run(s) for research.")
        if self.workflow_running or not self.auto_research_pending:
            return
        signature, path = self.auto_research_pending.pop(0)
        self.auto_research_last_signature = signature
        self.auto_research_running_signature = signature
        self._write_auto_research_receipt(signature, path, "started")
        self.auto_research_state.set(f"Running all research actions for saved session {path.name}.")
        self.run_parallel_research_test(
            auto_session=(signature, path), trigger_kind="automatic_saved_session",
        )

    def run_parallel_research_test(self, *, auto_session: tuple[str, Path] | None = None,
                                   trigger_kind: str = "manual_button") -> None:
        if os.name != "nt":
            self._set_status("Parallel research test requires Windows", "The test runs the installed PowerShell research workflows.")
            self._fail_auto_research_start(auto_session, "Parallel research requires Windows.")
            return
        script = self.project_root / "tools" / "test_parallel_research_actions.py"
        helper = self.project_root / "tools" / "github_integration.py"
        if not script.is_file():
            self._set_status("Parallel research test unavailable", f"Missing runner: {script}")
            self._fail_auto_research_start(auto_session, f"Missing runner: {script.name}")
            return
        command = [self.python_exe, str(script), "--trigger", trigger_kind]
        if auto_session:
            signature, session_path = auto_session
            command.extend(["--session-file", session_path.name, "--session-sha256", signature])
        steps = [("Run eight isolated research actions", command)]
        auto_upload = bool(self.auto_upload_enabled.get())
        if auto_upload:
            if not helper.is_file():
                self._set_status("Parallel research test unavailable", f"Missing upload helper: {helper}")
                self._fail_auto_research_start(auto_session, f"Missing upload helper: {helper.name}")
                return
            steps.append(("Share combined research report with all lanes", [
                self.python_exe, str(helper), "upload", "--action", "parallel-action-test",
            ]))
        self.parallel_test_state.set("Running eight actions… progress is shown in Current action below.")
        self._run_steps(
            "Parallel research test",
            steps,
            upload_action="parallel-action-test" if auto_upload else "",
            on_complete=lambda code, shared=auto_upload, session=auto_session: self._finish_parallel_research_test(code, shared, session),
        )

    def _fail_auto_research_start(self, auto_session: tuple[str, Path] | None, reason: str) -> None:
        if not auto_session:
            return
        signature, path = auto_session
        self.auto_research_running_signature = ""
        self._write_auto_research_receipt(signature, path, "not-started")
        self.auto_research_state.set(f"Could not start automatic research for {path.name}: {reason}")

    def _finish_parallel_research_test(self, returncode: int, auto_upload: bool, auto_session: tuple[str, Path] | None = None) -> None:
        latest = ROOT / "parallel-action-test-latest.json"
        try:
            payload = json.loads(latest.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            self.parallel_test_state.set("No combined report was produced. Open the workflow diagnostic for details.")
            self._fail_auto_research_start(auto_session, "No combined report was produced; open the workflow diagnostic.")
            return
        run_id = str(payload.get("run_id") or "unknown run")
        summary = payload.get("summary") or {}
        done = int(summary.get("completed", 0))
        total = int(summary.get("total", 0)) - int(summary.get("upload_actions_skipped", 0))
        failed = int(summary.get("failed", 0))
        if auto_session:
            signature, path = auto_session
            self.auto_research_running_signature = ""
            report_path = str(payload.get("report_path") or f"parallel-action-tests/{run_id}/combined-results.json")
            self._write_auto_research_receipt(
                signature, path,
                "complete" if returncode == 0 and failed == 0 else "completed-with-errors",
                run_id=run_id, report_path=report_path,
            )
            self.auto_research_state.set(
                f"Automatic research finished for {path.name}: {done}/{total} actions completed, {failed} failed. "
                f"Run: {run_id}." if returncode == 0 else
                f"Automatic research failed for {path.name}; open the workflow diagnostic. Run: {run_id}."
            )
        if failed:
            self.parallel_test_state.set(f"{done}/{total} actions completed; {failed} failed. Report: parallel-action-tests/{run_id}/combined-results.json")
        elif returncode == 0 and auto_upload:
            self.parallel_test_state.set(f"{done}/{total} actions completed; combined report shared with all lanes. Run: {run_id}")
        elif returncode == 0:
            self.parallel_test_state.set(f"{done}/{total} actions completed; local only (automatic uploads are off). Report: parallel-action-tests/{run_id}/combined-results.json")
        else:
            self.parallel_test_state.set(f"{done}/{total} actions completed; report upload failed. Run: {run_id}. Open workflow diagnostic for details.")

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
        steps = [
            ("Run research command", command),
            ("Upload generated evidence", [self.python_exe, str(helper), "upload", "--action", upload_action]),
        ]
        if self.auto_upload_enabled.get():
            steps.append(("Share changed evidence with all lanes", [
                self.python_exe, str(helper), "upload", "--action", "all-saved-evidence", "--only-if-changed",
            ]))
        self._run_steps(label, steps, evidence_namespace=evidence_namespace, extension_version=extension_version,
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
        on_complete: Callable[[int], None] | None = None,
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
                elif upload_action in {"all-saved-evidence", "parallel-action-test"}:
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
                                "research.upload_all_saved_evidence" if upload_action == "all-saved-evidence" else "research.parallel_action_test",
                                "complete" if returncode == 0 and upload_path else "failed",
                                "Deduplicated all available saved evidence in one shared main-branch upload." if upload_action == "all-saved-evidence" else "Published the combined parallel research report only; individual outputs and queue were excluded.",
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
                if on_complete is not None:
                    try:
                        self.window.after(0, lambda code=returncode: on_complete(code))
                    except (tk.TclError, RuntimeError):
                        pass
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
