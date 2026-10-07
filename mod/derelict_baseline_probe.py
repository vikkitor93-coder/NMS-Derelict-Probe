"""NMS Derelict Surveyor - runtime baseline probe.

Requires the current NMS.py/pyMHF runtime. This mod is intentionally read-only
with respect to No Man's Sky state: it samples already-exposed runtime data and
writes local JSON/log files only.
"""

from __future__ import annotations

import ctypes
import json
import logging
import math
import os
import re
import shutil
import subprocess
import sys
import threading
import textwrap
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pymhf import Mod
from pymhf.core.hooking import get_caller, hook_manager, on_key_pressed, static_function_hook
from pymhf.gui.decorators import BOOLEAN, INTEGER, STRING, gui_button, no_gui

import nmspy.data.basic_types as basic
import nmspy.data.types as nms
from nmspy.common import gameData
from nmspy.decorators import main_loop
from nmspy.engine import GetNodeAbsoluteTransMatrix

PROBE_VERSION = "0.3.39"
SCHEMA_VERSION = 1
ABANDONED_FREIGHTER_LOCATION_VALUE = 0xB
ABANDONED_FREIGHTER_POI_TYPE_VALUE = 0x6
DERELICT_POI_TYPE_VALUE = 0x9
SAMPLE_INTERVAL_SECONDS = 0.50
MIN_SAMPLE_DISTANCE_METRES = 0.75
FORCE_SAMPLE_AFTER_SECONDS = 2.0
AUTO_END_GRACE_SECONDS = 3.0
AUTOSAVE_INTERVAL_SECONDS = 5.0
MAX_PATH_SAMPLES = 20000
MARKER_DEBOUNCE_SECONDS = 0.18
LIVE_STATUS_INTERVAL_SECONDS = 0.20
CONTROLLER_COMMAND_POLL_SECONDS = 0.20
TRACE_PRESESSION_SECONDS = 60.0
MAX_TRACE_EVENTS = 3000
MAX_PRESESSION_TRACE_EVENTS = 600
POI_CANDIDATE_RETENTION_SECONDS = 1800.0
MAX_PRESESSION_POI_CANDIDATES = 32
POI_COMPONENT_RETENTION_SECONDS = 1800.0
POI_PREPARE_SCOPE_MAX_SECONDS = 30.0
DUNGEON_ROOT_SCENE = "MODELS/SPACE/POI/DUNGEON.SCENE.MBIN"
DUNGEON_SEED_RETENTION_SECONDS = 1800.0
MAX_PRESESSION_DUNGEON_SEEDS = 16
LOGICAL_ENTRY_RETENTION_SECONDS = 30.0
MAX_RECENT_LOGICAL_ENTRY_EVENTS = 512
MAX_AUTO_CRATE_EVENTS = 2000
MAX_PRESESSION_AUTO_CRATE_EVENTS = 500
MAX_SCENE_PROBE_EVENTS = 2000
MAX_PRESESSION_SCENE_PROBE_EVENTS = 800
MAX_RAW_RESOURCE_EVENTS = 2500
MAX_PRESESSION_RAW_RESOURCE_EVENTS = 1200
SALVAGE_CRATE_ID = "ABAND_CRATE_M"
CREW_FOOTLOCKER_ID = "FOOTLOCKER"
TARGET_CRATE_IDS = (SALVAGE_CRATE_ID, CREW_FOOTLOCKER_ID)
AUTO_CRATE_DISCOVERY_TOKENS = ("ABAND_CRATE", "SALVAGE_CRATE", "SALVAGECRATE", "FOOTLOCKER", "CREW_FOOTLOCKER", "CRATE", "LOCKER", "CHEST")
DERELICT_RESOURCE_TOKENS = ("DUNGEON", "ABAND", "HULK", "MODELS/SPACE/POI", "MODELS\\SPACE\\POI")

logger = logging.getLogger(__name__)


@static_function_hook(
    signature=(
        "48 89 54 24 ? 48 89 4C 24 ? 55 53 56 41 55 "
        "48 8D AC 24 ? ? ? ? 48 81 EC ? ? ? ? 4C 8B E9 48 8B F2"
    )
)
def _resource_descriptor_walk_entry(
    context: ctypes.c_void_p,
    owner: ctypes.c_void_p,
) -> ctypes.c_int32:
    """Current-build generic resource walk entry used for narrow caller tracing.

    The signature identifies the resource-walk entry across the observed NMS
    builds. The hook is read-only and is used only to remember the
    caller/descriptor relationship long enough to correlate it with the later
    DUNGEON.SCENE.MBIN Engine::AddResource event.
    """
    ...


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        try:
            return int(value.value)
        except Exception:
            return default


def _raw_u64_bits(value: Any) -> int | None:
    """Return the raw 64-bit register/pointer bits without dereferencing memory.

    This is intentionally used for signatures where NMS.py's Python annotation
    is known to disagree with the current mangled C++ symbol.  In particular,
    cGcSpacePoiSiteComponent::GeneratePoiDescription is currently annotated as
    taking a pointer for its final argument while the mangled symbol ends in
    ``E13eSpacePoiTypem`` (enum + uint64/unsigned-long).  Reading only the raw
    bits is safe and lets us test whether that value is the deterministic POI
    seed without pretending the interpretation is already proven.
    """
    if value is None:
        return None
    try:
        raw = getattr(value, "value", value)
        if isinstance(raw, int):
            return raw & 0xFFFFFFFFFFFFFFFF
    except Exception:
        pass
    try:
        ptr = ctypes.cast(value, ctypes.c_void_p)
        if ptr.value is not None:
            return int(ptr.value) & 0xFFFFFFFFFFFFFFFF
    except Exception:
        pass
    try:
        return int(value) & 0xFFFFFFFFFFFFFFFF
    except Exception:
        return None


def _capture_callsite_window(relative_return_offset: int | None, before: int = 48, after: int = 32) -> dict[str, Any] | None:
    """Read a small code window around a pyMHF caller return offset.

    ``get_caller`` reports an address relative to the executable base and points
    one instruction after the CALL.  ReadProcessMemory is used rather than a
    direct ctypes dereference so a failed read returns cleanly instead of
    risking an access violation in the game process.  This is read-only
    diagnostic evidence; the captured bytes are intentionally tiny.
    """
    try:
        rel = int(relative_return_offset or 0)
        if rel <= 0 or os.name != "nt":
            return None
        kernel32 = ctypes.windll.kernel32
        kernel32.GetModuleHandleW.restype = ctypes.c_void_p
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        kernel32.ReadProcessMemory.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
        kernel32.ReadProcessMemory.restype = ctypes.c_int
        base = int(kernel32.GetModuleHandleW(None) or 0)
        if base <= 0:
            return None
        start_rel = max(0, rel - int(before))
        size = int(before) + int(after)
        buf = (ctypes.c_ubyte * size)()
        read = ctypes.c_size_t(0)
        ok = kernel32.ReadProcessMemory(
            kernel32.GetCurrentProcess(),
            ctypes.c_void_p(base + start_rel),
            ctypes.byref(buf),
            size,
            ctypes.byref(read),
        )
        if not ok or read.value <= 0:
            return None
        raw = bytes(buf[: read.value])
        return {
            "start_offset_hex": f"{start_rel:08X}",
            "return_offset_hex": f"{rel:08X}",
            "return_index": rel - start_rel,
            "byte_count": len(raw),
            "bytes_hex": raw.hex().upper(),
        }
    except Exception:
        return None


def _read_process_bytes(address: int, size: int) -> bytes | None:
    """Safely read this process without directly dereferencing an arbitrary pointer."""
    try:
        if os.name != "nt" or int(address) <= 0x10000 or int(size) <= 0:
            return None
        kernel32 = ctypes.windll.kernel32
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        kernel32.ReadProcessMemory.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
        kernel32.ReadProcessMemory.restype = ctypes.c_int
        buf = (ctypes.c_ubyte * int(size))()
        read = ctypes.c_size_t(0)
        ok = kernel32.ReadProcessMemory(
            kernel32.GetCurrentProcess(),
            ctypes.c_void_p(int(address)),
            ctypes.byref(buf),
            int(size),
            ctypes.byref(read),
        )
        if not ok or int(read.value) != int(size):
            return None
        return bytes(buf)
    except Exception:
        return None


def _observed_hook_rva() -> int | None:
    """Use pyMHF's installed hook target, rather than an old build's RVA."""
    try:
        hook = next(
            item for item in hook_manager.hooks.values()
            if getattr(item, "_name", None) == "_resource_descriptor_walk_entry"
        )
        kernel32 = ctypes.windll.kernel32
        kernel32.GetModuleHandleW.restype = ctypes.c_void_p
        base = int(kernel32.GetModuleHandleW(None) or 0)
        target = int(hook.target)
        if base and base <= target < base + 0x8000000:
            return target - base
    except Exception:
        pass
    return None


def _classify_caller_bytes(raw: bytes | None, caller_return_rva: int, hook_rva: int | None) -> tuple[bool, bool]:
    if raw is None or len(raw) != 5 or hook_rva is None:
        return False, False
    direct_target = caller_return_rva + int.from_bytes(raw[1:5], "little", signed=True)
    return raw[0] == 0xE8 and direct_target == hook_rva, raw[2:5] == b"\xFF\x52\x10"


def _caller_edges(caller_return_rva: int, hook_rva: int | None) -> tuple[bool, bool]:
    """Check a direct self-call and the observed indirect FF 52 10 call."""
    if not caller_return_rva or hook_rva is None or os.name != "nt":
        return False, False
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.GetModuleHandleW.restype = ctypes.c_void_p
        base = int(kernel32.GetModuleHandleW(None) or 0)
        if not base or caller_return_rva < 5:
            return False, False
        raw = _read_process_bytes(base + caller_return_rva - 5, 5)
        return _classify_caller_bytes(raw, caller_return_rva, hook_rva)
    except Exception:
        return False, False


def _loaded_module_identity(address: int) -> dict[str, Any]:
    """Identify the loaded module and RVA containing an address, when applicable."""
    target = int(address)
    if target <= 0x10000:
        return {"status": "null-or-low-address", "address_hex": f"{target:016X}"}
    if os.name != "nt":
        return {"status": "module-lookup-unavailable", "address_hex": f"{target:016X}"}
    try:
        kernel32 = ctypes.windll.kernel32
        get_module = kernel32.GetModuleHandleExW
        get_module.argtypes = [ctypes.c_uint32, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
        get_module.restype = ctypes.c_int
        module = ctypes.c_void_p()
        # FROM_ADDRESS | UNCHANGED_REFCOUNT; no module is loaded or refcount changed.
        if not get_module(0x00000004 | 0x00000002, ctypes.c_void_p(target), ctypes.byref(module)):
            return {"status": "not-in-loaded-module", "address_hex": f"{target:016X}"}
        base = int(module.value or 0)
        if base <= 0 or target < base:
            return {"status": "module-base-unavailable", "address_hex": f"{target:016X}"}
        get_name = kernel32.GetModuleFileNameW
        get_name.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint32]
        get_name.restype = ctypes.c_uint32
        buffer = ctypes.create_unicode_buffer(32768)
        name_length = int(get_name(module, buffer, len(buffer)))
        module_path = buffer.value if name_length else None
        return {
            "status": "loaded-module",
            "address_hex": f"{target:016X}",
            "module_path": module_path,
            "module_base_hex": f"{base:016X}",
            "module_rva_hex": f"{target - base:08X}",
        }
    except Exception as exc:
        return {
            "status": "module-lookup-error",
            "address_hex": f"{target:016X}",
            "error": f"{type(exc).__name__}: {exc}",
        }


def _owner_plus_0x10_capture(
    owner_pointer: int,
    phase: str,
    *,
    resolve_identity: bool = True,
) -> dict[str, Any]:
    """Read owner+0x10 at a named phase of exact root-call correlation."""
    owner = int(owner_pointer)
    slot_address = owner + 0x10
    raw = _read_process_bytes(slot_address, 8)
    result: dict[str, Any] = {
        "owner_pointer_hex": f"{owner:016X}",
        "slot_offset_hex": "00000010",
        "slot_address_hex": f"{slot_address:016X}",
        "capture_phase": phase,
        "capture_utc": _utc_now(),
        "read_status": "captured" if raw is not None and len(raw) == 8 else "unreadable",
        "raw_bytes_hex": (raw.hex().upper() if raw is not None else None),
        "slot_value_hex": None,
        "target_identity": None,
    }
    if raw is None or len(raw) != 8:
        return result
    value = int.from_bytes(raw, "little", signed=False)
    result["slot_value_hex"] = f"{value:016X}"
    if resolve_identity:
        result["target_identity"] = _loaded_module_identity(value)
    return result



def _owner_descriptor_seed_payload(owner_pointer: int) -> dict[str, Any] | None:
    """Read the embedded descriptor at owner+0x128 observed in the verified function."""
    try:
        owner = int(owner_pointer)
        descriptor = owner + 0x128
        raw = _read_process_bytes(descriptor, 0x30)
        if raw is None or len(raw) < 0x29:
            return None
        primary = int.from_bytes(raw[0x10:0x18], "little", signed=False)
        primary_use = bool(raw[0x18])
        secondary = int.from_bytes(raw[0x20:0x28], "little", signed=False)
        secondary_use = bool(raw[0x28])
        return {
            "descriptor_pointer": descriptor,
            "primary_seed_hex": f"{primary:016X}",
            "primary_use_seed_value": primary_use,
            "secondary_seed_hex": f"{secondary:016X}",
            "secondary_use_seed_value": secondary_use,
        }
    except Exception:
        return None


def _safe_bool(value: Any) -> bool:
    try:
        raw = getattr(value, "value", value)
        return bool(raw)
    except Exception:
        return False


def _distance(a: dict[str, float], b: dict[str, float]) -> float:
    return math.sqrt((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2 + (a["z"] - b["z"]) ** 2)



def _decode_pointer_text(value: Any) -> str:
    """Best-effort decode for char* / pyMHF c_char_p64 hook arguments.

    pyMHF intentionally represents NMS char* arguments as a uint64 wrapper
    (c_char_p64). Its public `.value` is therefore the pointer address, while
    its `_value` property / `bytes()` exposes the pointed-to bytes. Treating it
    like a normal ctypes pointer produced garbage/blank names in v0.3.4.
    """
    if value is None:
        return ""
    try:
        if isinstance(value, str):
            return value
        if isinstance(value, (bytes, bytearray)):
            return bytes(value).split(b"\x00", 1)[0].decode("utf-8", errors="replace")

        wrapped = getattr(value, "_value", None)
        if isinstance(wrapped, (bytes, bytearray)):
            return bytes(wrapped).split(b"\x00", 1)[0].decode("utf-8", errors="replace")

        try:
            wrapped_bytes = bytes(value)
            if wrapped_bytes:
                return wrapped_bytes.split(b"\x00", 1)[0].decode("utf-8", errors="replace")
        except Exception:
            pass

        raw = getattr(value, "value", None)
        if isinstance(raw, (bytes, bytearray)):
            return bytes(raw).split(b"\x00", 1)[0].decode("utf-8", errors="replace")
        if isinstance(raw, int) and raw > 0x10000:
            ptr = ctypes.cast(ctypes.c_void_p(raw), ctypes.c_char_p)
            if ptr and ptr.value:
                return ptr.value.decode("utf-8", errors="replace")

        ptr = ctypes.cast(value, ctypes.c_char_p)
        if ptr and ptr.value:
            return ptr.value.decode("utf-8", errors="replace")
    except Exception:
        pass
    return ""


def _decode_fixed_string_pointer(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value.contents)
    except Exception:
        return _decode_pointer_text(value)


def _seed_payload(value: Any) -> dict[str, Any] | None:
    """Read a cTkSeed/GcSeed or pointer without ever mutating it."""
    if value is None:
        return None
    try:
        seed_obj = value.contents
    except Exception:
        seed_obj = value
    try:
        signed = int(seed_obj.Seed)
        unsigned = signed & 0xFFFFFFFFFFFFFFFF
        return {
            "seed_signed": signed,
            "seed_u64": unsigned,
            "seed_hex": f"{unsigned:016X}",
            "use_seed_value": bool(seed_obj.UseSeedValue),
        }
    except Exception:
        return None


def _descriptor_seed_payload(value: Any) -> dict[str, Any]:
    result: dict[str, Any] = {"primary": None, "secondary": None}
    if value is None:
        return result
    try:
        desc = value.contents
    except Exception:
        return result
    try:
        result["primary"] = _seed_payload(desc.mSeed)
    except Exception:
        pass
    try:
        result["secondary"] = _seed_payload(desc.mSecondarySeed)
    except Exception:
        pass
    return result


def _handle_key(value: Any) -> str | None:
    """Return a stable TkHandle key without dereferencing arbitrary memory."""
    if value is None:
        return None
    try:
        obj = value.contents
    except Exception:
        obj = value
    try:
        raw = int(obj.lookupInt) & 0xFFFFFFFF
        if raw:
            return f"{raw:08X}"
    except Exception:
        pass
    return None


def _resource_handle_value(value: Any) -> int | None:
    """Read an Engine resource handle from a smart-handle pointer/value."""
    if value is None:
        return None
    try:
        obj = value.contents
    except Exception:
        obj = value
    for attr in ("miInternalHandle", "value"):
        try:
            return int(getattr(obj, attr))
        except Exception:
            pass
    try:
        return int(obj)
    except Exception:
        return None


def _resource_from_return_pointer(value: Any) -> tuple[int | None, str]:
    """Read the `cTkResource*` returned by cTkResourceManager::FindResourceA.

    The NMS.py wrapper currently annotates/comments this return as a
    `cTkSmartResHandle*`, but the current mangled game symbol is
    `?FindResourceA@cTkResourceManager@@QEAAPEAVcTkResource@@...`, i.e. it
    returns `cTkResource*`. v0.3.4 decoded the wrong object type, which explains
    the huge number of FindResourceA callbacks with no usable handle/name map.
    """
    if value is None:
        return None, ""
    try:
        raw = int(getattr(value, "value", value))
    except Exception:
        return None, ""
    if raw <= 0x10000:
        return None, ""
    try:
        ptr = ctypes.cast(ctypes.c_void_p(raw), ctypes.POINTER(nms.cTkResource))
        obj = ptr.contents
        handle = int(obj.mHandle)
        name = str(obj.msName).split("\x00", 1)[0].strip()
        if handle < 0:
            handle = None
        return handle, name
    except Exception:
        return None, ""


def _normalize_scene_name(value: str) -> str:
    return str(value or "").strip().upper().replace("\\", "/")


def _target_crate_name_match(value: str) -> tuple[str, str] | None:
    """Classify an explicit spawned node/resource as one of our two target loot containers.

    The research target is the combined total of Salvage Crates (`ABAND_CRATE_M`)
    plus Crew Footlockers (`FOOTLOCKER`) inside a generated derelict. Exact and
    ID-prefixed matches are countable; generic crate-like names are diagnostics only.
    """
    name = _normalize_scene_name(value)
    if not name:
        return None
    leaf = name.rsplit("/", 1)[-1]
    stem = leaf.split(".", 1)[0]
    segments = [seg for seg in re.split(r"[/\\.]", name) if seg]
    for target_id in TARGET_CRATE_IDS:
        if name == target_id or leaf == target_id or stem == target_id or target_id in segments:
            return target_id, "exact"
        for candidate in (name, leaf, stem, *segments):
            if candidate.startswith(target_id + "_") or candidate.startswith(target_id + "-"):
                return target_id, "id-prefixed"
    return None


def _crate_discovery_name(value: str) -> bool:
    name = _normalize_scene_name(value)
    return bool(name and any(token in name for token in AUTO_CRATE_DISCOVERY_TOKENS))

def _output_root() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    root = Path(local) if local else Path.home()
    return root / "NMSDerelictSurveyor"


def _empty_manual() -> dict[str, Any]:
    return {
        "historical_expected_blue_crates": -1,
        "engineering_module_class": "unknown",
        "notes": "",
    }


@no_gui
class DerelictBaselineProbe(Mod):
    __author__ = "OpenAI / user research project"
    __description__ = "Read-only derelict crate/seed capture for high-count calculator reverse-engineering"
    __version__ = PROBE_VERSION

    def __init__(self):
        super().__init__()
        self._lock = threading.RLock()
        self._root = _output_root()
        self._sessions_dir = self._root / "sessions"
        self._root.mkdir(parents=True, exist_ok=True)
        self._sessions_dir.mkdir(parents=True, exist_ok=True)
        self._latest_log = self._root / "latest.log"
        # Append-only per-process journal: unlike the session snapshot this is
        # durable for events observed before a session has started as well.
        self._capture_journal_path = self._root / f"capture-journal-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{os.getpid()}.jsonl"
        self._journal_events_since_sync = 0
        self._live_status_path = self._root / "live-status.json"
        self._controller_command_path = self._root / "controller-command.json"
        self._controller_ack_path = self._root / "controller-command-ack.json"
        self._last_controller_command_id: str | None = None
        self._last_controller_poll_monotonic = 0.0
        self._crate_index_path = self._root / "asset-work-v1" / "room-crate-index.json"
        self._crate_index_mtime_ns: int | None = None
        self._crate_index_by_scene: dict[str, dict[str, int]] = {}
        self._crate_index_status = "not-loaded"
        self._last_generation_room_summary: dict[str, Any] | None = None
        self._session: dict[str, Any] | None = None
        self._session_path: Path | None = None
        self._last_tick = 0.0
        self._last_sample_monotonic = 0.0
        self._last_autosave_monotonic = 0.0
        self._last_non_derelict_monotonic: float | None = None
        self._last_marker_monotonic = 0.0
        self._last_status_publish_monotonic = 0.0
        self._pre_session_trace: list[dict[str, Any]] = []
        self._trace_sequence = 0
        self._pre_session_poi_candidates: list[dict[str, Any]] = []
        self._target_poi_components: dict[int, dict[str, Any]] = {}
        self._active_poi_prepare_components: dict[int, float] = {}
        self._active_poi_activation_components: dict[int, dict[str, Any]] = {}
        self._active_poi_lifecycle_components: dict[int, dict[str, Any]] = {}
        self._poi_lifecycle_call_counts: dict[int, int] = {}
        self._pre_session_dungeon_seeds: list[dict[str, Any]] = []
        self._recent_logical_entry_events: list[dict[str, Any]] = []
        self._logical_entry_caller_hits: dict[str, int] = {}
        self._logical_entry_tls = threading.local()
        self._observed_logical_entry_rva: int | None = None
        self._observed_recursive_return_rva: int | None = None
        self._last_exact_root_caller: dict[str, Any] | None = None
        self._exact_root_caller_path = self._root / "asset-work-v1" / "exact-root-caller-latest.json"
        self._root_event_path = self._root / "asset-work-v1" / "root-event-latest.json"
        self._pre_session_auto_crates: list[dict[str, Any]] = []
        self._pre_session_scene_probes: list[dict[str, Any]] = []
        self._pre_session_raw_resources: list[dict[str, Any]] = []
        self._resource_names_by_handle: dict[int, str] = {}
        self._resource_index_sources: dict[int, str] = {}
        self._node_spawn_events_seen = 0
        self._resource_ctor_events_seen = 0
        self._resource_find_events_seen = 0
        self._resource_find_mapped_handles: set[int] = set()
        self._resource_find_attempts: dict[int, int] = {}
        self._session_auto_node_probes = 0
        self._last_auto_crate_summary: dict[str, Any] = {
            "count": 0, "target_ids": list(TARGET_CRATE_IDS), "status": "inactive",
            "confidence": "unknown", "method": "none", "node_spawn_events": 0,
            "salvage_crates": 0, "crew_footlockers": 0,
            "candidate_name_count": 0, "last_candidate_name": None,
            "scene_probe_events": 0, "resolved_resource_names": 0,
            "resource_index_size": 0,
            "resource_find_events": 0,
            "resource_find_mapped": 0,
            "scene_handle_unique": 0, "scene_handle_top": [],
        }
        self._manual_started = False
        self._latest_error = "none"
        self._status = "Loaded & ready — enter a derelict freighter"
        self._last_event = "Probe loaded — ready to record"
        self._last_event_utc = _utc_now()
        self._workflow_status = "Ready"
        self._workflow_detail = "Use the research/GitHub buttons below."
        self._workflow_running = False
        self._available_version = "not checked"
        self._workflow_log_dir = self._root / "gui-actions"
        self._workflow_log_dir.mkdir(parents=True, exist_ok=True)
        self._workflow_latest_log = self._workflow_log_dir / "workflow-latest.log"
        self._workflow_diagnostic = self._workflow_log_dir / "workflow-diagnostic-latest.txt"
        self._reload_status_file = self._workflow_log_dir / "reload-status.json"
        try:
            if self._reload_status_file.is_file():
                payload = json.loads(self._reload_status_file.read_text(encoding="utf-8-sig"))
                self._workflow_status = str(payload.get("status") or self._workflow_status)[:120]
                self._workflow_detail = str(payload.get("detail") or self._workflow_detail)[:300]
                self._reload_status_file.unlink(missing_ok=True)
        except Exception as exc:
            self._write_log("reload_status_read_error", {"error": repr(exc)})
        try:
            (self._root / "installed-mod-file.txt").write_text(str(Path(__file__).resolve()), encoding="utf-8")
        except Exception as exc:
            self._write_log("installed_mod_path_write_error", {"error": repr(exc)})
        self._write_log("probe_started", {"version": PROBE_VERSION})
        self._publish_live_status(force=True)

    # --------------------------- GUI / diagnostics ---------------------------
    @property
    def probe_status(self):
        return self._status

    @property
    def live_overlay_state(self):
        return self._status

    @property
    def live_xyz_telemetry(self):
        pos, source, _candidates = self._player_position_with_source()
        if pos is None:
            return f"unavailable ({source})"
        return f"X={pos['x']:.3f} Y={pos['y']:.3f} Z={pos['z']:.3f} [{source}]"

    @property
    @STRING("Output folder")
    def output_folder(self):
        return str(self._root)

    @property
    @STRING("Current session file")
    def current_session_file(self):
        return str(self._session_path) if self._session_path else "none"

    @property
    def marked_blue_crates(self):
        if not self._session:
            return 0
        return sum(1 for m in self._session["markers"] if m["type"] == "blue_crate")

    @property
    def auto_salvage_crates(self):
        return int(self._auto_crate_summary().get("count") or 0)

    @property
    def auto_salvage_crate_only(self):
        return int(self._auto_crate_summary().get("salvage_crates") or 0)

    @property
    def auto_crew_footlockers(self):
        return int(self._auto_crate_summary().get("crew_footlockers") or 0)

    @property
    def auto_crate_detector(self):
        summary = self._auto_crate_summary()
        return f"{summary.get('status', 'unknown')} / {summary.get('method', 'none')}"

    @property
    def marked_rooms(self):
        if not self._session:
            return 0
        return sum(1 for m in self._session["markers"] if m["type"] == "room")

    @property
    def marked_room_zero(self):
        if not self._session:
            return 0
        return sum(1 for m in self._session["markers"] if m["type"] == "room_zero")

    @property
    def trace_resource_event_count(self):
        if not self._session:
            return 0
        return sum(1 for e in self._session.get("trace", {}).get("events", []) if e.get("kind") in {"resource_add", "resource_find"})

    @property
    def trace_reward_event_count(self):
        if not self._session:
            return 0
        return sum(1 for e in self._session.get("trace", {}).get("events", []) if e.get("kind") == "reward")

    @property
    def trace_latest_seed(self):
        return self._trace_summary().get("last_seed_hex") or "none"

    @property
    @INTEGER("Historical expected blue crates")
    def historical_expected_blue_crates(self):
        if not self._session:
            return -1
        return int(self._session["manual"]["historical_expected_blue_crates"])

    @historical_expected_blue_crates.setter
    def historical_expected_blue_crates(self, value: int):
        if self._session:
            self._session["manual"]["historical_expected_blue_crates"] = int(value)
            self._save_session()

    @property
    @STRING("Engineering module class")
    def engineering_module_class(self):
        if not self._session:
            return "unknown"
        return str(self._session["manual"]["engineering_module_class"])

    @engineering_module_class.setter
    def engineering_module_class(self, value: str):
        if self._session:
            clean = str(value).strip().upper()
            if clean not in {"C", "B", "A", "S"}:
                clean = "unknown"
            self._session["manual"]["engineering_module_class"] = clean
            self._last_event = f"Engineering module rank set to {clean.upper() if clean != 'unknown' else 'UNKNOWN'}"
            self._last_event_utc = _utc_now()
            self._save_session()
            self._publish_live_status(force=True)

    @property
    @STRING("Notes")
    def notes(self):
        if not self._session:
            return ""
        return str(self._session["manual"]["notes"])

    @notes.setter
    def notes(self, value: str):
        if self._session:
            self._session["manual"]["notes"] = str(value)[:1000]
            self._save_session()

    @property
    def recording(self):
        return self._session is not None

    @property
    @STRING("Loaded Surveyor version")
    def loaded_surveyor_version(self):
        return PROBE_VERSION

    @property
    @STRING("Downloaded/source version")
    def source_surveyor_version(self):
        root = self._source_project_root()
        if root is None:
            return "unknown"
        try:
            return (root / "VERSION.txt").read_text(encoding="utf-8-sig").strip() or "unknown"
        except Exception:
            return "unknown"

    @property
    @STRING("Available Surveyor version")
    def available_surveyor_version(self):
        return self._available_version

    @property
    @STRING("Latest error")
    def latest_error(self):
        return self._latest_error

    @property
    @STRING("Research workflow")
    def research_workflow_status(self):
        return self._workflow_status

    def _workflow_detail_lines(self) -> list[str]:
        text = str(self._workflow_detail or "")
        if not text:
            return [""]
        # pyMHF's STRING rows do not word-wrap. Keep each value short enough to
        # remain visible and expose additional rows rather than clipping paths.
        lines = textwrap.wrap(text, width=52, break_long_words=True, break_on_hyphens=False)
        return lines[:3] or [""]

    @property
    @STRING("Workflow message 1")
    def research_workflow_detail(self):
        return self._workflow_detail_lines()[0] if self._workflow_detail_lines() else ""

    @property
    @STRING("Workflow message 2")
    def research_workflow_detail_2(self):
        lines = self._workflow_detail_lines()
        return lines[1] if len(lines) > 1 else ""

    @property
    @STRING("Workflow message 3")
    def research_workflow_detail_3(self):
        lines = self._workflow_detail_lines()
        return lines[2] if len(lines) > 2 else ""

    def _source_project_root(self) -> Path | None:
        root_file = self._root / "project-root.txt"
        try:
            path = Path(root_file.read_text(encoding="utf-8-sig").strip())
            if path.is_dir() and (path / "VERSION.txt").is_file():
                return path
        except Exception:
            pass
        return None

    def _python_executable(self) -> str | None:
        """Resolve the real external Python interpreter, never the injected NMS host."""
        candidates: list[Path] = []
        persisted = self._root / "python-executable.txt"
        try:
            value = persisted.read_text(encoding="utf-8-sig").strip()
            if value:
                candidates.append(Path(value))
        except Exception:
            pass

        for value in (os.environ.get("NMSDS_PYTHON_EXE"), sys.executable):
            if value:
                candidates.append(Path(value))

        if os.name == "nt":
            for base in (getattr(sys, "prefix", ""), getattr(sys, "base_prefix", "")):
                if base:
                    candidates.append(Path(base) / "python.exe")
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
            base = resolved.name.lower()
            # In an injected pyMHF process sys.executable may be NMS.exe. Never
            # use a non-Python host executable for helper subprocesses.
            if not base.startswith("python"):
                continue
            if resolved.is_file():
                return str(resolved)
        return None

    def _workflow_safe_text(self, value: str) -> str:
        text = str(value or "")
        replacements = []
        for env_name, token in (("USERPROFILE", "%USERPROFILE%"), ("LOCALAPPDATA", "%LOCALAPPDATA%")):
            raw = os.environ.get(env_name)
            if raw:
                replacements.append((raw, token))
        for raw, token in replacements:
            text = text.replace(raw, token).replace(raw.replace("\\", "/"), token)
        return text

    def _workflow_command_text(self, command: list[str]) -> str:
        return " ".join(self._workflow_safe_text(part) for part in command)

    def _append_workflow_log(self, block: str):
        try:
            self._workflow_log_dir.mkdir(parents=True, exist_ok=True)
            with self._workflow_latest_log.open("a", encoding="utf-8", newline="\n") as fh:
                fh.write(block.rstrip() + "\n")
        except Exception as exc:
            self._write_log("workflow_log_error", {"error": repr(exc)})

    def _write_workflow_diagnostic(self, *, label: str, command: list[str], cwd: Path, returncode: int | None, stdout: str, stderr: str, exception: str | None = None, step: str | None = None):
        lines = [
            "NMS Derelict Surveyor workflow diagnostic",
            f"UTC: {_utc_now()}",
            f"Version: {PROBE_VERSION}",
            f"Action: {label}",
            f"Step: {step or 'single'}",
            f"Return code: {returncode if returncode is not None else 'exception'}",
            f"Command: {self._workflow_command_text(command)}",
            f"Working directory: {self._workflow_safe_text(str(cwd))}",
            f"Python helper: {self._workflow_safe_text(self._python_executable() or 'not found')}",
            "",
        ]
        if exception:
            lines += ["EXCEPTION", self._workflow_safe_text(exception), ""]
        lines += ["STDOUT", self._workflow_safe_text(stdout or "<empty>"), "", "STDERR", self._workflow_safe_text(stderr or "<empty>"), ""]
        try:
            self._workflow_diagnostic.write_text("\n".join(lines), encoding="utf-8", errors="replace")
        except Exception as exc:
            self._write_log("workflow_diagnostic_error", {"error": repr(exc)})

    def _launch_workflow(self, label: str, command: list[str], *, cwd: Path, setup_window: bool = False):
        self._launch_workflow_steps(label, [(label, command)], cwd=cwd, setup_window=setup_window)

    def _launch_workflow_steps(self, label: str, steps: list[tuple[str, list[str]]], *, cwd: Path, setup_window: bool = False):
        with self._lock:
            if self._workflow_running:
                self._workflow_detail = "Another research action is already running."
                return
            self._workflow_running = True
            self._workflow_status = f"Running: {label}"
            self._workflow_detail = f"Starting 1/{len(steps)}. Open workflow log for details."

        safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", label).strip("-").lower() or "action"
        per_action_log = self._workflow_log_dir / f"latest-{safe}.log"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        archive_log = self._workflow_log_dir / f"{timestamp}-{safe}.log"
        first_command = steps[0][1] if steps else []
        self._write_log("workflow_started", {"label": label, "steps": len(steps), "command": self._workflow_command_text(first_command)})
        self._append_workflow_log(f"===== {timestamp} START {label} ({len(steps)} step(s)) =====")

        def worker():
            env = os.environ.copy()
            env["NMSDS_NONINTERACTIVE"] = "1"
            env["NMSDS_PARENT_ACTION"] = label
            flags = 0
            if os.name == "nt" and not setup_window:
                flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            collected: list[str] = []
            try:
                final_returncode = 0
                final_command = first_command
                final_stdout = ""
                final_stderr = ""
                failed_step = None
                for index, (step_name, command) in enumerate(steps, start=1):
                    final_command = command
                    with self._lock:
                        self._workflow_status = f"Running: {label}"
                        self._workflow_detail = f"Step {index}/{len(steps)}: {step_name}"
                    self._write_log("workflow_step_started", {
                        "label": label, "step": step_name, "index": index, "total": len(steps),
                        "command": self._workflow_command_text(command),
                    })
                    self._append_workflow_log(
                        f"--- STEP {index}/{len(steps)} {step_name} ---\n"
                        f"Command: {self._workflow_command_text(command)}"
                    )
                    result = subprocess.run(
                        command,
                        cwd=str(cwd),
                        env=env,
                        text=True,
                        capture_output=True,
                        creationflags=flags,
                        check=False,
                    )
                    stdout = result.stdout or ""
                    stderr = result.stderr or ""
                    combined = stdout + ("\n" if stdout and stderr else "") + stderr
                    final_returncode = result.returncode
                    final_stdout = stdout
                    final_stderr = stderr
                    collected.append(
                        f"STEP {index}/{len(steps)}: {step_name}\n"
                        f"Return code: {result.returncode}\n"
                        f"Command: {self._workflow_command_text(command)}\n\n"
                        f"{self._workflow_safe_text(combined or '<no output>')}\n"
                    )
                    self._append_workflow_log(collected[-1])
                    self._write_log("workflow_step_completed" if result.returncode == 0 else "workflow_step_failed", {
                        "label": label, "step": step_name, "index": index,
                        "returncode": result.returncode,
                    })
                    if result.returncode != 0:
                        failed_step = f"{index}/{len(steps)} {step_name}"
                        break

                content = (
                    f"UTC: {_utc_now()}\nAction: {label}\nFinal return code: {final_returncode}\n\n"
                    + "\n".join(collected)
                )
                for path in (per_action_log, archive_log):
                    path.write_text(content, encoding="utf-8", errors="replace")
                self._append_workflow_log(f"===== END {label} =====")
                self._write_workflow_diagnostic(
                    label=label, command=final_command, cwd=cwd, returncode=final_returncode,
                    stdout=final_stdout, stderr=final_stderr, step=failed_step or f"{len(steps)}/{len(steps)} complete",
                )
                tail = [line.strip() for line in (final_stdout + "\n" + final_stderr).splitlines() if line.strip()]
                last = self._workflow_safe_text(tail[-1] if tail else "No command output.")
                with self._lock:
                    if final_returncode == 0:
                        marker_status = None
                        marker_detail = None
                        marker_remote_version = None
                        for line in (final_stdout + "\n" + final_stderr).splitlines():
                            if line.startswith("NMSDS_STATUS="):
                                marker_status = line.split("=", 1)[1].strip()
                            elif line.startswith("NMSDS_DETAIL="):
                                marker_detail = line.split("=", 1)[1].strip()
                            elif line.startswith("NMSDS_REMOTE_VERSION="):
                                marker_remote_version = line.split("=", 1)[1].strip()
                        if marker_remote_version:
                            self._available_version = marker_remote_version[:40]
                        self._workflow_status = (marker_status or f"Complete: {label}")[:120]
                        if marker_detail:
                            self._workflow_detail = marker_detail[:300]
                        elif len(steps) > 1:
                            self._workflow_detail = "Complete. Output and upload finished."
                        else:
                            self._workflow_detail = last[:300]
                        self._write_log("workflow_completed", {"label": label, "returncode": 0, "last_output": last[:500], "status": self._workflow_status})
                    else:
                        self._workflow_status = f"Failed: {label} (exit {final_returncode})"
                        self._workflow_detail = f"Failed at step {failed_step}. Open workflow diagnostic."
                        self._latest_error = f"Workflow {label} failed at {failed_step}: {last}"[:1000]
                        self._write_log("workflow_failed", {"label": label, "step": failed_step, "returncode": final_returncode, "last_output": last[:1000]})
            except Exception as exc:
                message = f"{type(exc).__name__}: {exc}"
                self._write_workflow_diagnostic(
                    label=label, command=first_command, cwd=cwd, returncode=None,
                    stdout="", stderr="", exception=message, step="exception",
                )
                self._append_workflow_log(f"EXCEPTION {label}: {self._workflow_safe_text(message)}\n===== END {label} =====")
                self._write_log("workflow_exception", {"label": label, "error": repr(exc)})
                with self._lock:
                    self._workflow_status = f"Failed: {label}"
                    self._workflow_detail = "Helper exception. Open workflow diagnostic."
                    self._latest_error = f"Workflow {label}: {message}"[:1000]
            finally:
                with self._lock:
                    self._workflow_running = False

        threading.Thread(target=worker, name=f"NMSDS-{label}", daemon=True).start()

    def _powershell_executable(self) -> str:
        if os.name == "nt":
            system_root = os.environ.get("SystemRoot", r"C:\Windows")
            candidate = Path(system_root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
            if candidate.is_file():
                return str(candidate)
        return shutil.which("powershell.exe") or shutil.which("powershell") or "powershell.exe"

    def _project_action_command(self, root: Path, cmd_name: str, python_exe: str) -> list[str] | None:
        # GUI actions bypass .cmd wrappers entirely. This avoids cmd.exe /s /c
        # quoting bugs and guarantees a hidden/noninteractive child process.
        stem = Path(cmd_name).stem
        ps1 = root / f"{stem}.ps1"
        if ps1.is_file():
            return [self._powershell_executable(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1)]
        if cmd_name.lower() == "extract-dungeon-caller-code.cmd":
            script = root / "tools" / "extract_nms_caller_code.py"
            if script.is_file():
                return [python_exe, str(script)]
        if cmd_name.lower() == "extract-dungeon-upstream-callers.cmd":
            script = root / "tools" / "extract_nms_upstream_callers.py"
            if script.is_file():
                return [python_exe, str(script)]
        if cmd_name.lower() == "analyze-dungeon-seed-function.cmd":
            script = root / "tools" / "analyze_nms_seed_function.py"
            if script.is_file():
                return [python_exe, str(script)]
        cmd_path = root / cmd_name
        if cmd_path.is_file():
            # Fallback for future wrappers. No /s and no chained command text.
            return [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", str(cmd_path)]
        return None

    def _project_action(self, label: str, cmd_name: str, upload_action: str | None = None):
        root = self._source_project_root()
        if root is None:
            self._workflow_status = "Source project not found"
            self._workflow_detail = "Start Surveyor from the extracted project once."
            return
        python_exe = self._python_executable()
        if python_exe is None:
            self._workflow_status = "Python interpreter not found"
            self._workflow_detail = "Relaunch Surveyor from Start-Derelict-Probe.cmd."
            return
        action_command = self._project_action_command(root, cmd_name, python_exe)
        if action_command is None:
            self._workflow_status = "Action unavailable"
            self._workflow_detail = f"Missing workflow for {cmd_name}"
            return
        steps: list[tuple[str, list[str]]] = [("Run research command", action_command)]
        if upload_action:
            helper = root / "tools" / "github_integration.py"
            if not helper.is_file():
                self._workflow_status = "GitHub helper unavailable"
                self._workflow_detail = "tools/github_integration.py is missing."
                return
            steps.append(("Upload generated evidence", [python_exe, str(helper), "upload", "--action", upload_action]))
        self._launch_workflow_steps(label, steps, cwd=root)

    def _integration_action(self, label: str, subcommand: str, *, setup_window: bool = False):
        root = self._source_project_root()
        if root is None:
            self._workflow_status = "Source project not found"
            self._workflow_detail = "Start Surveyor once from Start-Derelict-Probe.cmd in the extracted project."
            return
        helper = root / "tools" / "github_integration.py"
        python_exe = self._python_executable()
        if python_exe is None:
            self._workflow_status = "Python interpreter not found"
            self._workflow_detail = "Relaunch Surveyor once from Start-Derelict-Probe.cmd so the real Python path is recorded. NMS.exe will never be used as a helper."
            return
        self._launch_workflow(label, [python_exe, str(helper), subcommand], cwd=root, setup_window=setup_window)

    @gui_button("Open workflow log")
    def open_workflow_log(self):
        try:
            self._workflow_log_dir.mkdir(parents=True, exist_ok=True)
            if not self._workflow_latest_log.exists():
                self._workflow_latest_log.write_text("No workflow actions have been logged yet.\n", encoding="utf-8")
            if os.name == "nt":
                subprocess.Popen(["notepad.exe", str(self._workflow_latest_log)])
            else:
                self._workflow_detail = f"Workflow log: {self._workflow_latest_log}"
        except Exception as exc:
            self._workflow_status = "Could not open workflow log"
            self._workflow_detail = f"{type(exc).__name__}: {exc}"[:160]
            self._write_log("workflow_open_log_error", {"error": repr(exc)})

    @gui_button("Open workflow diagnostic")
    def open_workflow_diagnostic(self):
        try:
            if not self._workflow_diagnostic.exists():
                self._workflow_diagnostic.write_text("No workflow diagnostic has been generated yet.\n", encoding="utf-8")
            if os.name == "nt":
                subprocess.Popen(["notepad.exe", str(self._workflow_diagnostic)])
            else:
                self._workflow_detail = f"Diagnostic: {self._workflow_diagnostic}"
        except Exception as exc:
            self._workflow_status = "Could not open workflow diagnostic"
            self._workflow_detail = f"{type(exc).__name__}: {exc}"[:160]
            self._write_log("workflow_open_diagnostic_error", {"error": repr(exc)})

    @gui_button("Run GitHub diagnostic")
    def run_github_diagnostic(self):
        self._integration_action("GitHub diagnostic", "diagnose")

    @gui_button("Set up GitHub uploads")
    def setup_github_uploads(self):
        self._integration_action("GitHub setup", "setup", setup_window=True)

    @gui_button("Check for Surveyor update")
    def check_project_update(self):
        self._integration_action("Check update", "check-update")

    @gui_button("Install Surveyor update")
    def install_project_update(self):
        self._integration_action("Install update", "install-update")

    def _sync_source_mod_to_loaded_path(self) -> tuple[bool, str]:
        root = self._source_project_root()
        if root is None:
            return False, "Source project not found."
        source = root / "mod" / "derelict_baseline_probe.py"
        if not source.is_file():
            return False, "Updated Surveyor mod source is missing."
        try:
            loaded = Path(__file__).resolve()
            if source.resolve() != loaded:
                shutil.copy2(source, loaded)
            (self._root / "installed-mod-file.txt").write_text(str(loaded), encoding="utf-8")
            return True, str(loaded)
        except Exception as exc:
            return False, f"{type(exc).__name__}: {exc}"

    @gui_button("Reload Surveyor GUI")
    def restart_surveyor(self):
        """Reload only this pyMHF mod/interface. No NMS process restart."""
        if self._workflow_running:
            self._workflow_status = "Reload blocked: workflow running"
            self._workflow_detail = "Wait for the current action to finish, then reload."
            return
        ok, detail = self._sync_source_mod_to_loaded_path()
        if not ok:
            self._workflow_status = "Surveyor reload failed"
            self._workflow_detail = detail
            self._write_log("surveyor_reload_sync_error", {"error": detail})
            return
        gui = getattr(self, "pymhf_gui", None)
        mod_name = getattr(self, "_mod_name", None)
        if gui is None or not mod_name:
            self._workflow_status = "Surveyor reload unavailable"
            self._workflow_detail = "pyMHF GUI reload context was not found."
            self._write_log("surveyor_reload_context_missing", {})
            return
        if self._session:
            try:
                self._save_session()
            except Exception as exc:
                self._write_log("reload_presave_error", {"error": repr(exc)})
        try:
            self._reload_status_file.write_text(json.dumps({
                "status": f"Reloaded Surveyor {PROBE_VERSION}",
                "detail": "Surveyor interface/mod reloaded. NMS stayed open.",
            }), encoding="utf-8")
            self._write_log("surveyor_reload_requested", {"mod": mod_name, "loaded_file": detail})
            from pymhf.core.mod_loader import mod_manager
            # Match pyMHF's built-in Reload Mod action: reload the mod file and
            # refresh its GUI tab/hooks in-process, without closing NMS.
            mod_manager.reload(mod_name, gui)
            mod_manager._assign_mod_instances(mod_name)
        except Exception as exc:
            try:
                self._reload_status_file.unlink(missing_ok=True)
            except Exception:
                pass
            self._workflow_status = "Surveyor reload failed"
            self._workflow_detail = f"{type(exc).__name__}: {exc}"[:300]
            self._latest_error = self._workflow_detail
            self._write_log("surveyor_reload_error", {"error": repr(exc)})

    @gui_button("Measure derelict generation + upload")
    def measure_generation_and_upload(self):
        self._project_action("Measure + upload", "Measure-Derelict-Generation.cmd", "measure")

    @gui_button("Extract dungeon caller code + upload")
    def extract_caller_and_upload(self):
        self._project_action("Extract caller + upload", "Extract-Dungeon-Caller-Code.cmd", "extract-caller")

    @gui_button("Extract upstream callers + upload")
    def extract_upstream_callers_and_upload(self):
        self._project_action("Extract upstream + upload", "Extract-Dungeon-Upstream-Callers.cmd", "extract-upstream")

    @gui_button("Analyze seed function + upload")
    def analyze_seed_function_and_upload(self):
        self._project_action("Analyze seed function + upload", "Analyze-Dungeon-Seed-Function.cmd", "analyze-seed-function")

    @gui_button("Prepare crate assets + upload")
    def prepare_assets_and_upload(self):
        self._project_action("Prepare assets + upload", "Prepare-Crate-Assets.cmd", "prepare-assets")

    @gui_button("Analyze generation baseline + upload")
    def analyze_generation_and_upload(self):
        self._project_action("Analyze generation + upload", "Analyze-Generation-Baseline.cmd", "analyze-generation")

    @gui_button("Force start session")
    def force_start_session(self):
        if not self._session:
            self._manual_started = True
            self._start_session(trigger="manual")

    @gui_button("Stop + save session")
    def stop_session(self):
        if self._session:
            self._end_session(reason="manual_stop")

    @gui_button("Undo last marker")
    def undo_last_marker(self):
        with self._lock:
            if self._session and self._session["markers"]:
                removed = self._session["markers"].pop()
                self._write_log("marker_undone", removed)
                self._last_event = f"Undid {removed.get('type', 'marker')} marker"
                self._last_event_utc = _utc_now()
                self._save_session()
                self._publish_live_status(force=True)

    @gui_button("Write diagnostic snapshot")
    def write_diagnostic_snapshot(self):
        try:
            snapshot = {
                "probe_version": PROBE_VERSION,
                "utc": _utc_now(),
                "status": self._status,
                "recording": bool(self._session),
                "session_path": str(self._session_path) if self._session_path else None,
                "runtime": self._capture_runtime_metadata(),
                "latest_error": self._latest_error,
            }
            path = self._root / "diagnostic-latest.json"
            self._atomic_write_json(path, snapshot)
            self._write_log("diagnostic_written", {"path": str(path)})
        except Exception as exc:
            self._record_error("diagnostic", exc)

    def _marker_counts(self) -> dict[str, int]:
        counts = {
            "blue_crates": 0,
            "rooms": 0,
            "room_zero_rooms": 0,
            "vertical_transitions": 0,
            "shuttle_bays": 0,
            "engineering": 0,
        }
        if not self._session:
            return counts
        mapping = {
            "blue_crate": "blue_crates",
            "room": "rooms",
            "room_zero": "room_zero_rooms",
            "vertical_transition": "vertical_transitions",
            "shuttle_bay": "shuttle_bays",
            "engineering": "engineering",
        }
        for marker in self._session.get("markers", []):
            key = mapping.get(marker.get("type"))
            if key:
                counts[key] += 1
        return counts

    def _record_scene_probe(self, event: dict[str, Any]):
        event = {"utc": _utc_now(), **event}
        now = time.monotonic()
        with self._lock:
            if self._session is not None:
                bucket = self._session.setdefault("scene_probe", {}).setdefault("events", [])
                if len(bucket) < MAX_SCENE_PROBE_EVENTS:
                    bucket.append(event)
                else:
                    self._session["scene_probe"]["event_limit_reached"] = True
            else:
                buffered = {"_monotonic": now, **event}
                self._pre_session_scene_probes.append(buffered)
                if len(self._pre_session_scene_probes) > MAX_PRESESSION_SCENE_PROBE_EVENTS:
                    del self._pre_session_scene_probes[:-MAX_PRESESSION_SCENE_PROBE_EVENTS]

    def _recent_pre_session_scene_probes(self) -> list[dict[str, Any]]:
        now = time.monotonic()
        out: list[dict[str, Any]] = []
        for event in self._pre_session_scene_probes:
            if now - float(event.get("_monotonic", 0.0)) <= TRACE_PRESESSION_SECONDS:
                clean = dict(event)
                clean.pop("_monotonic", None)
                out.append(clean)
        return out

    def _record_raw_resource(self, name: str, handle: int | None, source: str, resource_type: int | None = None):
        if not name:
            return
        event = {
            "utc": _utc_now(),
            "resource_name": name,
            "resource_handle": handle,
            "source": source,
            "resource_type": resource_type,
        }
        now = time.monotonic()
        with self._lock:
            if self._session is not None:
                bucket = self._session.setdefault("raw_resources", {}).setdefault("events", [])
                if len(bucket) < MAX_RAW_RESOURCE_EVENTS:
                    bucket.append(event)
                else:
                    self._session["raw_resources"]["event_limit_reached"] = True
            else:
                buffered = {"_monotonic": now, **event}
                self._pre_session_raw_resources.append(buffered)
                if len(self._pre_session_raw_resources) > MAX_PRESESSION_RAW_RESOURCE_EVENTS:
                    del self._pre_session_raw_resources[:-MAX_PRESESSION_RAW_RESOURCE_EVENTS]

    def _recent_pre_session_raw_resources(self) -> list[dict[str, Any]]:
        now = time.monotonic()
        out: list[dict[str, Any]] = []
        for event in self._pre_session_raw_resources:
            if now - float(event.get("_monotonic", 0.0)) <= TRACE_PRESESSION_SECONDS:
                clean = dict(event)
                clean.pop("_monotonic", None)
                out.append(clean)
        return out

    def _resolve_node_resource(self, node: Any, fallback_handle: int | None = None) -> tuple[int | None, str]:
        handle = fallback_handle
        try:
            out = ctypes.c_int32(-1)
            nms.Engine.GetResourceHandleForNode(ctypes.byref(out), node)
            if int(out.value) >= 0:
                handle = int(out.value)
        except Exception:
            pass
        name = self._resource_names_by_handle.get(int(handle), "") if handle is not None else ""
        return handle, name

    def _auto_crate_events(self) -> list[dict[str, Any]]:
        if not self._session:
            return []
        return self._session.get("auto_crates", {}).get("events", [])

    def _auto_crate_summary(self) -> dict[str, Any]:
        if not self._session:
            return dict(self._last_auto_crate_summary)
        events = self._auto_crate_events()
        keys: list[str] = []
        keys_by_target: dict[str, list[str]] = {target: [] for target in TARGET_CRATE_IDS}
        methods: list[str] = []
        candidate_names: list[str] = []
        node_spawn_events = self._session_auto_node_probes if self._session else 0
        for event in events:
            key = event.get("instance_key")
            target_id = str(event.get("target_id") or "")
            if event.get("countable") and key:
                keys.append(str(key))
                if target_id in keys_by_target:
                    keys_by_target[target_id].append(str(key))
                methods.append(str(event.get("method") or "spawned-node"))
            candidate = event.get("node_name") or event.get("resource_name")
            if event.get("discovery_only") and candidate:
                candidate_names.append(str(candidate))
        unique_keys = list(dict.fromkeys(keys))
        per_target = {target: len(list(dict.fromkeys(vals))) for target, vals in keys_by_target.items()}
        unique_methods = list(dict.fromkeys(methods))
        if unique_keys:
            status = "live"
            confidence = "high"
        elif self._session and candidate_names:
            status = "embedded-in-room-scenes"
            confidence = "unproven"
        elif self._session and node_spawn_events:
            status = "scanning"
            confidence = "unproven"
        elif self._session:
            status = "waiting-for-node-signal"
            confidence = "unknown"
        else:
            status = "inactive"
            confidence = "unknown"
        scene_events = self._session.get("scene_probe", {}).get("events", []) if self._session else []
        resolved_resource_names = sum(1 for e in scene_events if e.get("resource_name"))
        scene_handle_counts: dict[int, int] = {}
        for e in scene_events:
            handle = e.get("scene_graph_handle")
            if isinstance(handle, int) and handle >= 0:
                scene_handle_counts[handle] = scene_handle_counts.get(handle, 0) + 1
        scene_handle_top = [
            {"handle": handle, "count": count, "resource_name": self._resource_names_by_handle.get(handle) or None}
            for handle, count in sorted(scene_handle_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:20]
        ]
        return {
            "count": len(unique_keys),
            "target_ids": list(TARGET_CRATE_IDS),
            "salvage_crates": per_target.get(SALVAGE_CRATE_ID, 0),
            "crew_footlockers": per_target.get(CREW_FOOTLOCKER_ID, 0),
            "status": status,
            "confidence": confidence,
            "method": "+".join(unique_methods) if unique_methods else "none",
            "node_spawn_events": node_spawn_events,
            "candidate_name_count": len(set(candidate_names)),
            "last_candidate_name": candidate_names[-1] if candidate_names else None,
            "scene_probe_events": len(scene_events),
            "resolved_resource_names": resolved_resource_names,
            "resource_index_size": len(self._resource_names_by_handle),
            "resource_find_events": self._resource_find_events_seen,
            "resource_find_mapped": len(self._resource_find_mapped_handles),
            "scene_handle_unique": len(scene_handle_counts),
            "scene_handle_top": scene_handle_top,
        }

    @staticmethod
    def _is_dead_end_group_paths(paths: list[str]) -> bool:
        """Classify the small standalone DEADEND_* room groups seen in verified baselines.

        Do not treat EMPTY/ROOM_DEADEND_R_* as a dead-end room by itself: the
        35-container verified baseline contains that piece inside a normal full
        room.  The confirmed extra rooms are compact groups containing a
        family-level ``/DEADEND_`` asset such as BARRACKS/DEADEND_BUNK*.
        """
        normalized = [_normalize_scene_name(p) for p in paths if p]
        family_deadend = any(re.search(r"/DUNGEON/(?!EMPTY/)[^/]+/DEADEND_[^/]+\.SCENE\.MBIN$", p) for p in normalized)
        return bool(family_deadend and len(normalized) <= 4)

    def _load_live_crate_index(self) -> tuple[dict[str, dict[str, int]], str]:
        """Load/cache the extracted scene -> loot index used by offline analysis.

        This reads only Surveyor's own LOCALAPPDATA asset cache. Missing assets are
        non-fatal: recording continues and the companion UI explains how to enable
        per-room loot counts.
        """
        try:
            stat = self._crate_index_path.stat()
        except OSError:
            self._crate_index_status = "index-unavailable"
            self._crate_index_by_scene = {}
            self._crate_index_mtime_ns = None
            return self._crate_index_by_scene, self._crate_index_status
        if self._crate_index_mtime_ns == int(stat.st_mtime_ns) and self._crate_index_by_scene:
            return self._crate_index_by_scene, self._crate_index_status
        try:
            data = json.loads(self._crate_index_path.read_text(encoding="utf-8"))
            mapped: dict[str, dict[str, int]] = {}
            for entry in data.get("entries", []):
                path = _normalize_scene_name(str(entry.get("scene_path") or ""))
                if not path:
                    continue
                salvage = max(0, _safe_int(entry.get("salvage_crates"), 0))
                foot = max(0, _safe_int(entry.get("crew_footlockers"), 0))
                mapped[path] = {
                    "salvage_crates": salvage,
                    "crew_footlockers": foot,
                    "target_containers": salvage + foot,
                }
            self._crate_index_by_scene = mapped
            self._crate_index_mtime_ns = int(stat.st_mtime_ns)
            self._crate_index_status = "ready" if mapped else "index-empty"
        except Exception as exc:
            self._crate_index_by_scene = {}
            self._crate_index_mtime_ns = int(stat.st_mtime_ns)
            self._crate_index_status = f"index-error:{type(exc).__name__}"
        return self._crate_index_by_scene, self._crate_index_status

    @staticmethod
    def _room_index_from_names(names: list[str]) -> int | None:
        for name in names:
            match = re.match(r"^Room\s+(\d+)$", str(name).strip(), re.IGNORECASE)
            if match:
                return int(match.group(1))
        return None

    @staticmethod
    def _scene_family(path: str) -> str | None:
        match = re.search(r"/DUNGEON/([^/]+)/", _normalize_scene_name(path))
        return match.group(1) if match else None

    def _generation_room_summary(self) -> dict[str, Any]:
        root_dispatch_capture = (self._last_exact_root_caller or {}).get("owner_plus_0x10_capture")
        if not self._session:
            if self._last_generation_room_summary is not None:
                summary = dict(self._last_generation_room_summary)
                summary["last_dungeon_root_owner_plus_0x10_capture"] = root_dispatch_capture
                return summary
            return {
                "total_rooms_seen": 0, "main_rooms_seen": 0, "dead_end_rooms_seen": 0,
                "room_parent_names_seen": 0, "rooms": [],
                "salvage_crates_seen": 0, "crew_footlockers_seen": 0, "target_containers_seen": 0,
                "dungeon_root_resource_events_seen": 0,
                "crate_index_status": self._crate_index_status,
                "poi_seed_candidates": [], "poi_context_arguments": [],
                "poi_context_matches_universe_address": False, "poi_system_address_hex": None,
                "poi_description_return_candidates": [], "last_poi_description_return_hex": None,
                "dungeon_root_seed_candidates": [], "last_dungeon_root_seed_hex": None,
                "dungeon_logical_entry_caller_offsets": [], "last_dungeon_logical_entry_caller_offset_hex": None,
                "dungeon_logical_entry_exact_external_caller_offsets": [],
                "last_dungeon_logical_entry_exact_external_caller_offset_hex": None,
                "last_dungeon_root_owner_plus_0x10_capture": root_dispatch_capture,
                "logical_entry_unique_callers_observed": len(self._logical_entry_caller_hits),
                "logical_entry_known_candidate_hits": None,
                "logical_entry_candidate_count": None,
            }

        scene_events = self._session.get("scene_probe", {}).get("events", [])
        crate_index, crate_index_status = self._load_live_crate_index()
        groups: dict[str, dict[str, Any]] = {}
        dungeon_root_resource_events_seen = 0
        for event in scene_events:
            event_resource = _normalize_scene_name(str(event.get("resource_name") or ""))
            if event_resource == DUNGEON_ROOT_SCENE:
                dungeon_root_resource_events_seen += 1
            if event.get("kind") != "spawned_node":
                continue
            path = _normalize_scene_name(str(event.get("resource_name") or event.get("node_name") or ""))
            if "/DUNGEON/" not in path:
                continue
            parent = str(event.get("parent_key") or "UNKNOWN")
            row = groups.setdefault(parent, {
                "parent_key": parent,
                "parent_node_names": [],
                "scene_paths": [],
                "family_counts": {},
                "salvage_crates": 0,
                "crew_footlockers": 0,
                "first_seen_utc": event.get("utc"),
            })
            pname = event.get("parent_node_name")
            if pname and pname not in row["parent_node_names"]:
                row["parent_node_names"].append(str(pname))
            row["scene_paths"].append(path)
            family = self._scene_family(path)
            if family:
                row["family_counts"][family] = int(row["family_counts"].get(family, 0)) + 1
            indexed = crate_index.get(path)
            if indexed:
                row["salvage_crates"] += int(indexed.get("salvage_crates") or 0)
                row["crew_footlockers"] += int(indexed.get("crew_footlockers") or 0)

        neutral = {"EMPTY", "COMM", "SPAWNERS"}
        room_rows: list[dict[str, Any]] = []
        for row in groups.values():
            dead_end = self._is_dead_end_group_paths(row["scene_paths"])
            room_index = self._room_index_from_names(row["parent_node_names"])
            styles = {k: v for k, v in row["family_counts"].items() if k not in neutral}
            dominant = max(styles, key=styles.get) if styles else None
            salvage = int(row["salvage_crates"])
            foot = int(row["crew_footlockers"])
            room_rows.append({
                "room_index": room_index,
                "room_label": f"Room {room_index}" if room_index is not None else None,
                "room_kind": "dead_end" if dead_end else "main_room",
                "dominant_family": dominant,
                "salvage_crates": salvage,
                "crew_footlockers": foot,
                "target_containers": salvage + foot,
            })
        room_rows.sort(key=lambda row: (row.get("room_index") is None, int(row.get("room_index") or 0), str(row.get("room_label") or "")))
        dead = sum(1 for row in room_rows if row.get("room_kind") == "dead_end")
        total = len(room_rows)

        poi_candidates=[]
        for event in self._session.get("trace", {}).get("events", []):
            if event.get("kind") == "space_poi_description" and event.get("raw_argument_hex"):
                hx=str(event["raw_argument_hex"]).upper()
                if hx not in poi_candidates:
                    poi_candidates.append(hx)
        runtime_start = self._session.get("runtime_start") or {}
        ua = str(runtime_start.get("universe_address_hex") or "").upper().zfill(16)
        poi_matches_ua = bool(poi_candidates and ua and all(str(x).upper().zfill(16) == ua for x in poi_candidates))

        poi_return_hexes: list[str] = []
        for event in self._session.get("trace", {}).get("events", []):
            if event.get("kind") != "space_poi_description_result":
                continue
            hx = str(event.get("return_value_hex") or "").upper()
            raw = str(event.get("raw_argument_hex") or "").upper().zfill(16)
            if ua and raw and raw != ua:
                continue
            if hx and hx not in poi_return_hexes:
                poi_return_hexes.append(hx)

        dungeon_seed_hexes: list[str] = []
        logical_entry_caller_offsets: list[str] = []
        logical_entry_exact_external_offsets: list[str] = []
        for event in self._session.get("trace", {}).get("events", []):
            if event.get("kind") != "resource_add":
                continue
            if _normalize_scene_name(str(event.get("resource_name") or "")) != DUNGEON_ROOT_SCENE:
                continue
            seed = event.get("primary_seed") or {}
            hx = str(seed.get("seed_hex") or "").upper()
            if hx and hx not in ("0000000000000000", "FFFFFFFFFFFFFFFF") and hx not in dungeon_seed_hexes:
                dungeon_seed_hexes.append(hx)
            for match in event.get("logical_entry_matches") or []:
                caller = str(match.get("caller_return_offset_hex") or "").upper()
                if caller and caller not in logical_entry_caller_offsets:
                    logical_entry_caller_offsets.append(caller)
            exact_external = str(event.get("logical_entry_exact_external_caller_return_offset_hex") or "").upper()
            if exact_external and exact_external not in logical_entry_exact_external_offsets:
                logical_entry_exact_external_offsets.append(exact_external)

        return {
            "total_rooms_seen": total,
            "main_rooms_seen": max(0, total-dead),
            "dead_end_rooms_seen": dead,
            "poi_seed_candidates": poi_candidates,
            "poi_context_arguments": poi_candidates,
            "poi_context_matches_universe_address": poi_matches_ua,
            "poi_system_address_hex": (ua if poi_matches_ua else None),
            "poi_description_return_candidates": poi_return_hexes,
            "last_poi_description_return_hex": (poi_return_hexes[-1] if poi_return_hexes else None),
            "dungeon_root_seed_candidates": dungeon_seed_hexes,
            "last_dungeon_root_seed_hex": (dungeon_seed_hexes[-1] if dungeon_seed_hexes else None),
            "dungeon_root_resource_events_seen": dungeon_root_resource_events_seen,
            "dungeon_logical_entry_caller_offsets": logical_entry_caller_offsets,
            "last_dungeon_logical_entry_caller_offset_hex": (logical_entry_caller_offsets[-1] if logical_entry_caller_offsets else None),
            "dungeon_logical_entry_exact_external_caller_offsets": logical_entry_exact_external_offsets,
            "last_dungeon_logical_entry_exact_external_caller_offset_hex": (logical_entry_exact_external_offsets[-1] if logical_entry_exact_external_offsets else None),
            "last_dungeon_root_owner_plus_0x10_capture": root_dispatch_capture,
            "logical_entry_unique_callers_observed": len(self._logical_entry_caller_hits),
            "logical_entry_known_candidate_hits": None,
            "logical_entry_candidate_count": None,
            "room_parent_names_seen": sum(1 for row in groups.values() if row["parent_node_names"]),
            "crate_index_status": crate_index_status,
            "crate_index_scene_count": len(crate_index),
            "salvage_crates_seen": sum(int(row.get("salvage_crates") or 0) for row in room_rows),
            "crew_footlockers_seen": sum(int(row.get("crew_footlockers") or 0) for row in room_rows),
            "target_containers_seen": sum(int(row.get("target_containers") or 0) for row in room_rows),
            "rooms": room_rows,
        }

    def _record_auto_crate_event(self, event: dict[str, Any]):
        event = {"utc": _utc_now(), **event}
        now = time.monotonic()
        with self._lock:
            if self._session is not None:
                bucket = self._session.setdefault("auto_crates", {}).setdefault("events", [])
                if len(bucket) < MAX_AUTO_CRATE_EVENTS:
                    bucket.append(event)
                else:
                    self._session["auto_crates"]["event_limit_reached"] = True
            else:
                buffered = {"_monotonic": now, **event}
                self._pre_session_auto_crates.append(buffered)
                if len(self._pre_session_auto_crates) > MAX_PRESESSION_AUTO_CRATE_EVENTS:
                    del self._pre_session_auto_crates[:-MAX_PRESESSION_AUTO_CRATE_EVENTS]

    def _recent_pre_session_auto_crates(self) -> list[dict[str, Any]]:
        now = time.monotonic()
        out: list[dict[str, Any]] = []
        for event in self._pre_session_auto_crates:
            mono = float(event.get("_monotonic", 0.0))
            if now - mono <= TRACE_PRESESSION_SECONDS:
                clean = dict(event)
                clean.pop("_monotonic", None)
                out.append(clean)
        return out

    def _probe_spawned_node(self, result: Any, method: str, resource_name: str = "", resource_handle: int | None = None, parent: Any = None):
        """Inspect one newly-created scene/group root without modifying it."""
        try:
            key = _handle_key(result)
            node_name = ""
            node_obj = None
            if key:
                try:
                    node_obj = result.contents
                except Exception:
                    node_obj = result
                try:
                    node_name = _decode_pointer_text(nms.Engine.GetNodeName(node_obj))
                except Exception:
                    node_name = ""
            resolved_handle, resolved_name = self._resolve_node_resource(node_obj, resource_handle) if node_obj is not None else (resource_handle, "")
            if not resource_name:
                resource_name = resolved_name
            parent_name = ""
            if parent is not None:
                try:
                    parent_name = _decode_pointer_text(nms.Engine.GetNodeName(parent))
                except Exception:
                    parent_name = ""
            self._record_scene_probe({
                "kind": "spawned_node",
                "method": method,
                "instance_key": key,
                "parent_key": _handle_key(parent),
                "parent_node_name": parent_name or None,
                "node_name": node_name or None,
                "scene_graph_handle": resource_handle,
                "node_resource_handle": resolved_handle,
                "resource_name": resource_name or None,
            })

            node_match = _target_crate_name_match(node_name)
            resource_match = _target_crate_name_match(resource_name)
            matched = node_match or resource_match
            target_id = matched[0] if matched else None
            match = matched[1] if matched else None
            countable = bool(key and matched)
            discovery = _crate_discovery_name(node_name) or _crate_discovery_name(resource_name)

            # Keep lightweight node-probe evidence while a derelict is active or
            # during the pre-session generation window. Discovery-only names are
            # invaluable if HG uses a different root label in a new build.
            relevant = self._session is not None or self._is_on_derelict() or countable or discovery
            if not relevant:
                return
            self._node_spawn_events_seen += 1
            if self._session is not None:
                self._session_auto_node_probes += 1
                self._session.setdefault("auto_crates", {})["node_probe_events_seen"] = self._session_auto_node_probes
            if countable or discovery:
                event = {
                    "kind": "node_probe",
                    "method": method,
                    "instance_key": key,
                    "node_name": node_name or None,
                    "resource_name": resource_name or None,
                    "target_id": target_id,
                    "match": match,
                    "countable": countable,
                    "discovery_only": bool(discovery and not countable),
                }
                self._record_auto_crate_event(event)
            if countable:
                summary = self._auto_crate_summary()
                self._last_event = f"Auto target container detected #{summary.get('count', 0)}"
                self._last_event_utc = _utc_now()
                self._publish_live_status(force=True)
        except Exception as exc:
            self._write_log("auto_crate_probe_error", {"method": method, "error": repr(exc)})

    def _trace_summary(self) -> dict[str, Any]:
        events = self._session.get("trace", {}).get("events", []) if self._session else []
        resource_count = 0
        reward_count = 0
        seeds: list[str] = []
        for event in events:
            if event.get("kind") in {"resource_add", "resource_find"}:
                resource_count += 1
            elif event.get("kind") == "reward":
                reward_count += 1
            for key in ("seed", "primary_seed", "secondary_seed"):
                value = event.get(key)
                if isinstance(value, dict) and value.get("seed_hex"):
                    seeds.append(str(value["seed_hex"]))
        unique = list(dict.fromkeys(seeds))
        poi_candidates: list[str] = []
        for event in events:
            if event.get("kind") == "space_poi_description" and event.get("raw_argument_hex"):
                hx = str(event.get("raw_argument_hex")).upper()
                if hx not in poi_candidates:
                    poi_candidates.append(hx)
        return {
            "resource_events": resource_count,
            "reward_events": reward_count,
            "unique_seed_count": len(unique),
            "last_seed_hex": unique[-1] if unique else None,
            "poi_seed_candidate_count": len(poi_candidates),
            "last_poi_seed_candidate_hex": poi_candidates[-1] if poi_candidates else None,
        }

    def _record_trace_event(self, event: dict[str, Any]):
        now = time.monotonic()
        with self._lock:
            # Preserve callback order across threads. UTC timestamps can tie at
            # millisecond resolution, which is not enough for seed-lineage work.
            self._trace_sequence += 1
            event = {"utc": _utc_now(), "trace_sequence": self._trace_sequence, **event}
            self._append_capture_journal(event)
            if self._session is not None:
                events = self._session.setdefault("trace", {}).setdefault("events", [])
                if len(events) < MAX_TRACE_EVENTS:
                    events.append(event)
                else:
                    self._session["trace"]["event_limit_reached"] = True
            else:
                buffered = {"_monotonic": now, **event}
                self._pre_session_trace.append(buffered)
                if len(self._pre_session_trace) > MAX_PRESESSION_TRACE_EVENTS:
                    del self._pre_session_trace[:-MAX_PRESESSION_TRACE_EVENTS]

    def _append_capture_journal(self, event: dict[str, Any]) -> None:
        """Durably append each observed trace event before returning to the hook."""
        try:
            self._capture_journal_path.parent.mkdir(parents=True, exist_ok=True)
            with self._capture_journal_path.open("a", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
                fh.flush()
                self._journal_events_since_sync += 1
                root_event = (event.get("kind") == "resource_add" and
                              str(event.get("resource_name") or "").upper().replace("\\", "/") == DUNGEON_ROOT_SCENE)
                if root_event or self._journal_events_since_sync >= 16:
                    os.fsync(fh.fileno())
                    self._journal_events_since_sync = 0
        except Exception as exc:
            # Avoid recursive trace logging if persistence itself fails.
            self._write_log("capture_journal_write_failed", {"error": repr(exc), "path": str(self._capture_journal_path)})

    def _recent_pre_session_trace(self) -> list[dict[str, Any]]:
        now = time.monotonic()
        out: list[dict[str, Any]] = []
        for event in self._pre_session_trace:
            mono = float(event.get("_monotonic", 0.0))
            if now - mono <= TRACE_PRESESSION_SECONDS:
                clean = dict(event)
                clean.pop("_monotonic", None)
                out.append(clean)
        return out

    def _buffer_pre_session_poi_event(self, event: dict[str, Any]):
        """Retain target-POI lifecycle evidence independently of the 60s generic trace."""
        if self._session is not None:
            return
        buffered = {"_monotonic": time.monotonic(), **event}
        self._pre_session_poi_candidates.append(buffered)
        if len(self._pre_session_poi_candidates) > MAX_PRESESSION_POI_CANDIDATES:
            del self._pre_session_poi_candidates[:-MAX_PRESESSION_POI_CANDIDATES]

    def _recent_pre_session_poi_candidates(self) -> list[dict[str, Any]]:
        now = time.monotonic()
        out: list[dict[str, Any]] = []
        for event in self._pre_session_poi_candidates:
            mono = float(event.get("_monotonic", 0.0))
            if now - mono <= POI_CANDIDATE_RETENTION_SECONDS:
                clean = dict(event)
                clean.pop("_monotonic", None)
                out.append(clean)
        return out

    def _target_poi_context(self, this: Any) -> tuple[int | None, dict[str, Any] | None]:
        component = _raw_u64_bits(this)
        if component is None:
            return None, None
        ctx = self._target_poi_components.get(component)
        if not ctx:
            return component, None
        if time.monotonic() - float(ctx.get("_monotonic", 0.0)) > POI_COMPONENT_RETENTION_SECONDS:
            self._target_poi_components.pop(component, None)
            return component, None
        return component, ctx

    def _poi_component_snapshot(self, this: Any) -> dict[str, Any]:
        snapshot: dict[str, Any] = {}
        try:
            obj = this.contents
            snapshot["space_poi_id"] = str(obj.mSpacePoiID).strip("\x00") or None
            snapshot["name"] = str(obj.mName).strip("\x00") or None
            snapshot["description"] = str(obj.mDescription).strip("\x00") or None
            snapshot["root_node"] = _safe_int(obj.mRootNode, -1)
            snapshot["node"] = _safe_int(obj.mNode, -1)
            snapshot["distance_from_center"] = float(obj.mDistanceFromCenter)
        except Exception:
            pass
        return snapshot

    @staticmethod
    def _poi_snapshot_signature(snapshot: dict[str, Any]) -> tuple[Any, ...]:
        """Compact equality key for target-POI lifecycle snapshots."""
        return (
            snapshot.get("space_poi_id"),
            snapshot.get("name"),
            snapshot.get("description"),
            snapshot.get("root_node"),
            snapshot.get("node"),
        )

    def _recent_pre_session_dungeon_seeds(self) -> list[dict[str, Any]]:
        now = time.monotonic()
        out: list[dict[str, Any]] = []
        for event in self._pre_session_dungeon_seeds:
            mono = float(event.get("_monotonic", 0.0))
            if now - mono <= DUNGEON_SEED_RETENTION_SECONDS:
                clean = dict(event)
                clean.pop("_monotonic", None)
                out.append(clean)
        return out

    def _publish_live_status(self, force: bool = False):
        now = time.monotonic()
        if not force and now - self._last_status_publish_monotonic < LIVE_STATUS_INTERVAL_SECONDS:
            return
        self._last_status_publish_monotonic = now
        try:
            counts = self._marker_counts()
            recording = self._session is not None
            state = "recording" if recording else ("saved" if self._status.startswith("Saved") else "ready")
            pos, pos_source, pos_candidates = self._player_position_with_source()
            payload = {
                "schema_version": 1,
                "probe_version": PROBE_VERSION,
                "process_id": os.getpid(),
                "heartbeat_epoch": time.time(),
                "utc": _utc_now(),
                "state": state,
                "recording": recording,
                "detail": self._status,
                "blue_crates": counts["blue_crates"],
                "auto_crates": self._auto_crate_summary(),
                "rooms": counts["rooms"],
                "room_zero_rooms": counts["room_zero_rooms"],
                "vertical_transitions": counts["vertical_transitions"],
                "shuttle_bays": counts["shuttle_bays"],
                "engineering_marked": counts["engineering"] > 0,
                "engineering_module_class": (
                    str(self._session.get("manual", {}).get("engineering_module_class", "unknown"))
                    if self._session else "unknown"
                ),
                "last_event": self._last_event,
                "last_event_utc": self._last_event_utc,
                "session_path": str(self._session_path) if self._session_path else None,
                "latest_error": self._latest_error,
                "position": ({
                    "x": round(pos["x"], 4),
                    "y": round(pos["y"], 4),
                    "z": round(pos["z"], 4),
                } if pos is not None else None),
                "position_source": pos_source,
                "position_candidates": pos_candidates,
                "trace": self._trace_summary(),
                "generation_rooms": self._generation_room_summary(),
                "root_dispatch_capture": self._root_dispatch_capture_payload(),
                "hotkeys": {
                    "room_zero": "F5",
                    "room": "F6",
                    "blue_crate": "F7",
                    "vertical_transition": "F8",
                    "shuttle_bay": "F9",
                    "engineering": "F10",
                    "engineering_module_class": "F11",
                },
            }
            self._atomic_write_json(self._live_status_path, payload)
        except Exception as exc:
            # Never allow an optional visual-status write to stop runtime capture.
            self._write_log("live_status_error", {"error": repr(exc)})

    def _remember_logical_entry_event(self, event: dict[str, Any]) -> None:
        now = time.monotonic()
        event = {
            **event,
            "caller_class": ("recursive-self" if event.get("recursive_self_call") else "external"),
            "known_static_candidate": None,
        }
        with self._lock:
            kept = [
                row for row in self._recent_logical_entry_events
                if now - float(row.get("_monotonic", 0.0)) <= LOGICAL_ENTRY_RETENTION_SECONDS
            ]
            kept.append({"_monotonic": now, **event})
            self._recent_logical_entry_events = kept[-MAX_RECENT_LOGICAL_ENTRY_EVENTS:]

    def _logical_entry_matches_for_descriptor(self, descriptor_pointer: int | None) -> list[dict[str, Any]]:
        if descriptor_pointer is None:
            return []
        now = time.monotonic()
        target = int(descriptor_pointer)
        rows: list[dict[str, Any]] = []
        with self._lock:
            for event in self._recent_logical_entry_events:
                age = now - float(event.get("_monotonic", 0.0))
                if age > LOGICAL_ENTRY_RETENTION_SECONDS:
                    continue
                if int(event.get("descriptor_pointer") or 0) != target:
                    continue
                clean = dict(event)
                clean.pop("_monotonic", None)
                clean.pop("descriptor_pointer", None)
                clean["age_ms_at_root_add"] = round(age * 1000.0, 3)
                rows.append(clean)
        rows.sort(key=lambda row: float(row.get("age_ms_at_root_add") or 0.0))
        # The closest entry is normally the exact invocation which reaches the
        # root AddResource call. Preserve a few older recursive ancestors too.
        return rows[:8]

    def _logical_entry_external_match_for_descriptor(self, descriptor_pointer: int | None) -> dict[str, Any] | None:
        """Return the nearest descriptor match with its inherited external caller.

        The shared walk is recursive. A nested invocation can own the exact
        derelict descriptor while its immediate caller is a verified self edge.
        The before/after hook pair maintains a tiny per-thread
        call stack, so each seeded invocation inherits the original external
        caller which entered the recursive chain. This lets one hook distinguish
        callers in one run without a hook at every callsite.
        """
        if descriptor_pointer is None:
            return None
        target = int(descriptor_pointer)
        now = time.monotonic()
        candidates: list[dict[str, Any]] = []
        with self._lock:
            for event in self._recent_logical_entry_events:
                age = now - float(event.get("_monotonic", 0.0))
                if age > LOGICAL_ENTRY_RETENTION_SECONDS:
                    continue
                if int(event.get("descriptor_pointer") or 0) != target:
                    continue
                external = str(event.get("external_origin_caller_return_offset_hex") or "").upper()
                if not external:
                    continue
                clean = dict(event)
                clean.pop("_monotonic", None)
                clean.pop("descriptor_pointer", None)
                clean["age_ms_at_root_add"] = round(age * 1000.0, 3)
                clean["resolved_external_caller_return_offset_hex"] = external
                candidates.append(clean)
        candidates.sort(key=lambda row: float(row.get("age_ms_at_root_add") or 0.0))
        return candidates[0] if candidates else None

    def _persist_root_event(self, root_event: dict[str, Any], exact: dict[str, Any] | None = None) -> None:
        runtime_metadata = root_event.get("runtime_metadata_at_capture")
        if not isinstance(runtime_metadata, dict):
            runtime_metadata = {}
        payload = {
            "schema_version": 1,
            "capture_version": 2,
            "probe_version": PROBE_VERSION,
            "utc": _utc_now(),
            "method": ("all-callers-single-hook-exact-descriptor-correlation" if exact else "root-resource-event-capture"),
            "capture_status": "exact-caller-correlated" if exact else "root-event-saved-caller-correlation-pending",
            "logical_entry_rva_hex": (f"{self._observed_logical_entry_rva:08X}" if self._observed_logical_entry_rva is not None else None),
            "logical_entry_rva_source": "installed-pymhf-hook-target" if self._observed_logical_entry_rva is not None else "unavailable",
            "static_direct_reference_count": None,
            "static_direct_reference_count_status": "not-enumerated-for-this-build",
            "recursive_return_rva_hex": (f"{self._observed_recursive_return_rva:08X}" if self._observed_recursive_return_rva is not None else None),
            "root_resource": DUNGEON_ROOT_SCENE,
            "root_descriptor_pointer_hex": root_event.get("descriptor_pointer_hex"),
            "root_seed_hex": str((root_event.get("primary_seed") or {}).get("seed_hex") or "").upper() or None,
            "root_event_utc": root_event.get("utc"),
            "universe_address_hex_at_capture": root_event.get("universe_address_hex_at_capture"),
            "runtime_metadata_at_capture": runtime_metadata,
            "root_event": root_event,
            "exact_external_caller": exact,
            "owner_plus_0x10_capture": exact.get("owner_plus_0x10_capture") if exact else None,
            "exact_external_caller_return_offset_hex": ((exact.get("resolved_external_caller_return_offset_hex") or exact.get("external_origin_caller_return_offset_hex") or exact.get("caller_return_offset_hex")) if exact else None),
            "external_call_register_snapshot_at_entry": exact.get("external_call_register_snapshot_at_entry") if exact else None,
            "observed_callee_hook_target_rva_hex": (f"{self._observed_logical_entry_rva:08X}" if self._observed_logical_entry_rva is not None else None),
            "precall_dispatch_slot_captured": False,
            "unique_callers_observed": len(self._logical_entry_caller_hits),
            "caller_hit_counts": dict(sorted(self._logical_entry_caller_hits.items())),
            "interpretation": "All shared-entry callers are observed at once; exact descriptor identity selects the derelict path and the verified self-recursive edge is excluded.",
        }
        self._atomic_write_json(self._root_event_path, payload)
        if exact:
            self._last_exact_root_caller = payload
            self._atomic_write_json(self._exact_root_caller_path, payload)

    def _persist_exact_root_caller(self, root_event: dict[str, Any], exact: dict[str, Any]) -> None:
        """Compatibility wrapper for callers and structural consumers."""
        self._persist_root_event(root_event, exact)

    def _root_dispatch_capture_payload(self) -> dict[str, Any] | None:
        capture = (self._last_exact_root_caller or {}).get("owner_plus_0x10_capture")
        if not isinstance(capture, dict):
            return None
        identity = capture.get("target_identity") if isinstance(capture.get("target_identity"), dict) else {}
        module_rva = identity.get("module_rva_hex")
        return {
            "captured": capture.get("read_status") == "captured",
            "target_offset_hex": module_rva,
            "slot_value_hex": capture.get("slot_value_hex"),
            "read_status": capture.get("read_status"),
            "target_identity": identity,
        }

    @get_caller
    @_resource_descriptor_walk_entry.before
    def _trace_resource_descriptor_walk_entry(self, context, owner):
        """Track every shared-entry caller and retain seeded descriptor evidence only."""
        try:
            try:
                caller_offset = int(self._trace_resource_descriptor_walk_entry.caller_address())
            except Exception:
                caller_offset = 0
            stack = getattr(self._logical_entry_tls, "stack", None)
            if stack is None:
                stack = []
                self._logical_entry_tls.stack = stack
            if self._observed_logical_entry_rva is None:
                self._observed_logical_entry_rva = _observed_hook_rva()
            recursive_self_call, indirect_ff52_10 = _caller_edges(caller_offset, self._observed_logical_entry_rva)
            if recursive_self_call:
                self._observed_recursive_return_rva = caller_offset
            if recursive_self_call and stack:
                external_origin = int(stack[-1].get("external_origin_caller_offset") or 0)
                external_owner_pointer_hex = stack[-1].get("external_owner_pointer_hex")
                external_slot_capture = stack[-1].get("external_owner_plus_0x10_capture")
                external_register_snapshot = stack[-1].get("external_call_register_snapshot")
            else:
                external_origin = caller_offset
                external_owner_pointer_hex = None
                external_slot_capture = None
                external_register_snapshot = None
            frame = {
                "caller_offset": caller_offset,
                "external_origin_caller_offset": external_origin,
                "external_owner_pointer_hex": external_owner_pointer_hex,
                "external_owner_plus_0x10_capture": external_slot_capture,
                "external_call_register_snapshot": external_register_snapshot,
                "recursive_self_call": recursive_self_call,
            }
            stack.append(frame)

            caller_hex = f"{caller_offset:08X}" if caller_offset else ""
            if caller_hex:
                with self._lock:
                    self._logical_entry_caller_hits[caller_hex] = self._logical_entry_caller_hits.get(caller_hex, 0) + 1

            owner_pointer = _raw_u64_bits(owner)
            if owner_pointer is None or owner_pointer <= 0x10000:
                return
            seed = _owner_descriptor_seed_payload(owner_pointer)
            if not seed or not seed.get("primary_use_seed_value"):
                return
            primary_hex = str(seed.get("primary_seed_hex") or "").upper()
            if primary_hex in {"", "0000000000000000", "FFFFFFFFFFFFFFFF"}:
                return
            if not recursive_self_call:
                # At the callee entry the indirect call has just happened, before
                # later root-resource work can clear or repurpose this slot.
                frame["external_owner_pointer_hex"] = f"{owner_pointer:016X}"
                frame["external_owner_plus_0x10_capture"] = _owner_plus_0x10_capture(
                    owner_pointer,
                    phase="logical-entry-after-external-call",
                    resolve_identity=False,
                )
                # The hook runs at the shared callee entry, immediately after
                # its caller's instruction. Under the Windows x64 ABI, the first
                # two integer/pointer arguments arrive in RCX and RDX. Capture
                # those values with the already-read [RDX+0x10] slot so every
                # caller is observed through this one hook.
                frame["external_call_register_snapshot"] = {
                    "capture_phase": "shared-entry-hook-after-call",
                    "capture_utc": _utc_now(),
                    "caller_return_rva_hex": (f"{caller_offset:08X}" if caller_offset else None),
                    "observed_hook_target_rva_hex": (f"{self._observed_logical_entry_rva:08X}" if self._observed_logical_entry_rva is not None else None),
                    "caller_instruction_ff52_10_verified": indirect_ff52_10,
                    "precall_dispatch_slot_captured": False,
                    "rdx_plus_0x10_interpretation": "callee-owner-field-after-call; not the pre-call virtual dispatch slot",
                    "rcx_hex": (f"{_raw_u64_bits(context):016X}" if _raw_u64_bits(context) is not None else None),
                    "rdx_hex": f"{owner_pointer:016X}",
                    "rdx_plus_0x10_capture": frame["external_owner_plus_0x10_capture"],
                }
            self._remember_logical_entry_event({
                "utc": _utc_now(),
                "context_pointer_hex": (f"{_raw_u64_bits(context):016X}" if _raw_u64_bits(context) is not None else None),
                "owner_pointer_hex": f"{owner_pointer:016X}",
                "descriptor_pointer": int(seed["descriptor_pointer"]),
                "descriptor_pointer_hex": f"{int(seed['descriptor_pointer']):016X}",
                "primary_seed_hex": primary_hex,
                "secondary_seed_hex": str(seed.get("secondary_seed_hex") or "").upper() or None,
                "caller_return_offset_hex": (f"{caller_offset:08X}" if caller_offset else None),
                "external_origin_caller_return_offset_hex": (f"{external_origin:08X}" if external_origin else None),
                "recursion_depth": max(0, len(stack) - 1),
                "recursive_self_call": recursive_self_call,
                "external_owner_pointer_hex": frame.get("external_owner_pointer_hex"),
                "external_owner_plus_0x10_capture_at_entry": frame.get("external_owner_plus_0x10_capture"),
                "external_call_register_snapshot_at_entry": frame.get("external_call_register_snapshot"),
            })
        except Exception as exc:
            self._write_log("trace_logical_entry_error", {"error": repr(exc)})

    @_resource_descriptor_walk_entry.after
    def _trace_resource_descriptor_walk_entry_after(self, context, owner):
        """Balance the per-thread recursion stack after the read-only observation."""
        try:
            stack = getattr(self._logical_entry_tls, "stack", None)
            if stack:
                stack.pop()
        except Exception as exc:
            self._write_log("trace_logical_entry_stack_error", {"error": repr(exc)})

    # --------------------------- Seed/resource trace --------------------------
    @nms.cTkResourceManager.FindResourceA.after
    def _index_resource_find_after(
        self,
        this,
        liType,
        lsName,
        lpResourceDescriptor,
        a5,
        lbIgnoreDefaultFallback,
        lbIgnoreKilled,
        a8,
        _result_,
    ):
        """Resolve resource handles at lookup time, including resources loaded long before the session.

        AddNodes gives us an anonymous scene resource handle. Current NMS
        `FindResourceA` returns `cTkResource*`; reading that object's `mHandle`
        and `msName` creates the missing handle -> asset-name map. Repeated
        lookup calls are extremely frequent, so only newly-resolved handles are
        recorded/indexed as events.
        """
        try:
            self._resource_find_events_seen += 1
            handle, returned_name = _resource_from_return_pointer(_result_)
            arg_name = _decode_pointer_text(lsName)
            name = returned_name or arg_name

            if handle is None:
                return

            handle = int(handle)
            if not name:
                attempts = self._resource_find_attempts.get(handle, 0) + 1
                self._resource_find_attempts[handle] = attempts
                if attempts >= 3:
                    return
            else:
                self._resource_names_by_handle[handle] = name
                self._resource_index_sources[handle] = "cTkResourceManager.FindResourceA:cTkResource*"
                if handle in self._resource_find_mapped_handles:
                    return
                self._resource_find_mapped_handles.add(handle)

            if self._session is not None or self._is_on_derelict():
                self._record_raw_resource(name, handle, "cTkResourceManager.FindResourceA:cTkResource*", _safe_int(liType, -1))

            if name:
                upper = _normalize_scene_name(name)
                if any(token.replace("\\", "/") in upper for token in DERELICT_RESOURCE_TOKENS):
                    desc = _descriptor_seed_payload(lpResourceDescriptor)
                    self._record_trace_event({
                        "kind": "resource_find",
                        "resource_name": name,
                        "resource_handle": handle,
                        "resource_type": _safe_int(liType, -1),
                        "primary_seed": desc.get("primary"),
                        "secondary_seed": desc.get("secondary"),
                    })
        except Exception as exc:
            self._write_log("resource_find_index_error", {"error": repr(exc)})

    @nms.cGcSpacePoiSiteComponent.GeneratePoiDescription.before
    def _trace_derelict_poi_description(self, this, lPoiType, a3):
        """Capture the 64-bit derelict POI context input without modifying game state."""
        try:
            poi_type = _safe_int(lPoiType, -1)
            if poi_type not in (ABANDONED_FREIGHTER_POI_TYPE_VALUE, DERELICT_POI_TYPE_VALUE):
                return
            raw = _raw_u64_bits(a3)
            component = _raw_u64_bits(this)
            event = {
                "kind": "space_poi_description",
                "phase": "before",
                "poi_type_value": poi_type,
                "poi_type_name": ("AbandonedFreighter" if poi_type == ABANDONED_FREIGHTER_POI_TYPE_VALUE else "Derelict"),
                "component_address_hex": (f"{component:016X}" if component is not None else None),
                "raw_argument_u64": raw,
                "raw_argument_hex": (f"{raw:016X}" if raw is not None else None),
                "interpretation": "poi-context-u64; abandoned-freighter observed as universe-address",
                "signature_evidence": "GeneratePoiDescription(eSpacePoiType,uint64) mangled-symbol shape",
                **self._poi_component_snapshot(this),
            }
            if component is not None:
                self._target_poi_components[component] = {
                    "_monotonic": time.monotonic(),
                    "raw_argument_hex": event.get("raw_argument_hex"),
                    "poi_type_value": poi_type,
                    "poi_type_name": event.get("poi_type_name"),
                }
            self._record_trace_event(event)
            self._buffer_pre_session_poi_event(event)
        except Exception as exc:
            self._write_log("trace_space_poi_description_error", {"error": repr(exc)})

    @nms.cGcSpacePoiSiteComponent.GeneratePoiDescription.after
    def _trace_derelict_poi_description_after(self, this, lPoiType, a3, _result_):
        """Capture GeneratePoiDescription's 64-bit return value as an unclassified derived candidate."""
        try:
            poi_type = _safe_int(lPoiType, -1)
            if poi_type not in (ABANDONED_FREIGHTER_POI_TYPE_VALUE, DERELICT_POI_TYPE_VALUE):
                return
            raw = _raw_u64_bits(a3)
            result = _raw_u64_bits(_result_)
            component = _raw_u64_bits(this)
            event = {
                "kind": "space_poi_description_result",
                "phase": "after",
                "poi_type_value": poi_type,
                "poi_type_name": ("AbandonedFreighter" if poi_type == ABANDONED_FREIGHTER_POI_TYPE_VALUE else "Derelict"),
                "component_address_hex": (f"{component:016X}" if component is not None else None),
                "raw_argument_u64": raw,
                "raw_argument_hex": (f"{raw:016X}" if raw is not None else None),
                "return_value_u64": result,
                "return_value_hex": (f"{result:016X}" if result is not None else None),
                "return_matches_input": bool(raw is not None and result is not None and raw == result),
                "interpretation": "GeneratePoiDescription return candidate; unclassified until correlated with dungeon-root seed/layout",
                **self._poi_component_snapshot(this),
            }
            if component is not None:
                ctx = self._target_poi_components.setdefault(component, {})
                ctx.update({
                    "_monotonic": time.monotonic(),
                    "raw_argument_hex": event.get("raw_argument_hex"),
                    "poi_type_value": poi_type,
                    "poi_type_name": event.get("poi_type_name"),
                    "return_value_hex": event.get("return_value_hex"),
                })
            self._record_trace_event(event)
            self._buffer_pre_session_poi_event(event)
        except Exception as exc:
            self._write_log("trace_space_poi_description_result_error", {"error": repr(exc)})

    @nms.cGcSpacePoiSiteComponent.Prepare.before
    def _trace_derelict_poi_prepare_before(self, this):
        """Mark the synchronous Prepare scope for a previously identified derelict POI component."""
        try:
            component, ctx = self._target_poi_context(this)
            if component is None or ctx is None:
                return
            self._active_poi_prepare_components[component] = time.monotonic()
            event = {
                "kind": "space_poi_prepare",
                "phase": "before",
                "component_address_hex": f"{component:016X}",
                "raw_argument_hex": ctx.get("raw_argument_hex"),
                "poi_type_value": ctx.get("poi_type_value"),
                "poi_type_name": ctx.get("poi_type_name"),
                **self._poi_component_snapshot(this),
            }
            self._record_trace_event(event)
            self._buffer_pre_session_poi_event(event)
        except Exception as exc:
            self._write_log("trace_space_poi_prepare_before_error", {"error": repr(exc)})

    @nms.cGcSpacePoiSiteComponent.Prepare.after
    def _trace_derelict_poi_prepare_after(self, this):
        """Close the target POI Prepare scope and retain the post-prepare component snapshot."""
        try:
            component, ctx = self._target_poi_context(this)
            if component is None or ctx is None:
                return
            started = self._active_poi_prepare_components.pop(component, None)
            event = {
                "kind": "space_poi_prepare",
                "phase": "after",
                "component_address_hex": f"{component:016X}",
                "raw_argument_hex": ctx.get("raw_argument_hex"),
                "poi_type_value": ctx.get("poi_type_value"),
                "poi_type_name": ctx.get("poi_type_name"),
                "duration_ms": (round((time.monotonic() - started) * 1000.0, 3) if started is not None else None),
                **self._poi_component_snapshot(this),
            }
            self._record_trace_event(event)
            self._buffer_pre_session_poi_event(event)
        except Exception as exc:
            self._write_log("trace_space_poi_prepare_after_error", {"error": repr(exc)})

    @nms.cGcSpacePoiSiteComponent.OnActivate.before
    def _trace_derelict_poi_activate_before(self, this):
        """Bracket activation only for a POI component already proven to be the target derelict."""
        try:
            component, ctx = self._target_poi_context(this)
            if component is None or ctx is None:
                return
            snapshot = self._poi_component_snapshot(this)
            self._active_poi_activation_components[component] = {
                "started": time.monotonic(),
                "before_snapshot": snapshot,
                "root_seen": False,
            }
            event = {
                "kind": "space_poi_activate",
                "phase": "before",
                "component_address_hex": f"{component:016X}",
                "raw_argument_hex": ctx.get("raw_argument_hex"),
                "poi_type_value": ctx.get("poi_type_value"),
                "poi_type_name": ctx.get("poi_type_name"),
                **snapshot,
            }
            self._record_trace_event(event)
            self._buffer_pre_session_poi_event(event)
        except Exception as exc:
            self._write_log("trace_space_poi_activate_before_error", {"error": repr(exc)})

    @nms.cGcSpacePoiSiteComponent.OnActivate.after
    def _trace_derelict_poi_activate_after(self, this, _result_):
        """Close activation scope and record whether dungeon-root loading happened synchronously inside it."""
        try:
            component, ctx = self._target_poi_context(this)
            if component is None or ctx is None:
                return
            state = self._active_poi_activation_components.pop(component, None) or {}
            started = state.get("started")
            result = _raw_u64_bits(_result_)
            event = {
                "kind": "space_poi_activate",
                "phase": "after",
                "component_address_hex": f"{component:016X}",
                "raw_argument_hex": ctx.get("raw_argument_hex"),
                "poi_type_value": ctx.get("poi_type_value"),
                "poi_type_name": ctx.get("poi_type_name"),
                "duration_ms": (round((time.monotonic() - float(started)) * 1000.0, 3) if started is not None else None),
                "return_value_hex": (f"{result:016X}" if result is not None else None),
                "dungeon_root_added_during_call": bool(state.get("root_seen")),
                "before_snapshot": state.get("before_snapshot"),
                **self._poi_component_snapshot(this),
            }
            self._record_trace_event(event)
            self._buffer_pre_session_poi_event(event)
        except Exception as exc:
            self._write_log("trace_space_poi_activate_after_error", {"error": repr(exc)})

    @nms.cGcSpacePoiSiteComponent.AdvanceLifecycle.before
    def _trace_derelict_poi_lifecycle_before(self, this, lfTimeStep, a3):
        """Open a short scope around one target-POI lifecycle tick without logging every frame."""
        try:
            component, ctx = self._target_poi_context(this)
            if component is None or ctx is None:
                return
            call_index = int(self._poi_lifecycle_call_counts.get(component, 0)) + 1
            self._poi_lifecycle_call_counts[component] = call_index
            try:
                time_step = float(getattr(lfTimeStep, "value", lfTimeStep))
            except Exception:
                time_step = None
            self._active_poi_lifecycle_components[component] = {
                "started": time.monotonic(),
                "call_index": call_index,
                "before_snapshot": self._poi_component_snapshot(this),
                "root_seen": False,
                "time_step": time_step,
                "flag": _safe_bool(a3),
            }
        except Exception as exc:
            self._write_log("trace_space_poi_lifecycle_before_error", {"error": repr(exc)})

    @nms.cGcSpacePoiSiteComponent.AdvanceLifecycle.after
    def _trace_derelict_poi_lifecycle_after(self, this, lfTimeStep, a3):
        """Record only the first, state-changing, or dungeon-root-producing target lifecycle tick."""
        try:
            component, ctx = self._target_poi_context(this)
            if component is None or ctx is None:
                return
            state = self._active_poi_lifecycle_components.pop(component, None) or {}
            before_snapshot = state.get("before_snapshot") or {}
            after_snapshot = self._poi_component_snapshot(this)
            call_index = int(state.get("call_index") or self._poi_lifecycle_call_counts.get(component, 0))
            changed = self._poi_snapshot_signature(before_snapshot) != self._poi_snapshot_signature(after_snapshot)
            root_seen = bool(state.get("root_seen"))
            if call_index != 1 and not changed and not root_seen:
                return
            started = state.get("started")
            event = {
                "kind": "space_poi_lifecycle",
                "phase": "after",
                "component_address_hex": f"{component:016X}",
                "raw_argument_hex": ctx.get("raw_argument_hex"),
                "poi_type_value": ctx.get("poi_type_value"),
                "poi_type_name": ctx.get("poi_type_name"),
                "call_index": call_index,
                "duration_ms": (round((time.monotonic() - float(started)) * 1000.0, 3) if started is not None else None),
                "time_step": state.get("time_step"),
                "flag": state.get("flag"),
                "snapshot_changed": changed,
                "dungeon_root_added_during_call": root_seen,
                "before_snapshot": before_snapshot,
                **after_snapshot,
            }
            self._record_trace_event(event)
            self._buffer_pre_session_poi_event(event)
        except Exception as exc:
            self._write_log("trace_space_poi_lifecycle_after_error", {"error": repr(exc)})

    @get_caller
    @nms.Engine.AddResource.before
    def _trace_resource_add(
        self,
        result,
        liType,
        lpcName,
        liFlags,
        lAlternateMaterialId,
        unknown,
    ):
        """Observe relevant resource additions and descriptor seeds without modifying them."""
        try:
            name = _decode_pointer_text(lpcName)
            if not name:
                return
            upper = name.upper().replace("\\", "/")
            if not any(token.replace("\\", "/") in upper for token in DERELICT_RESOURCE_TOKENS):
                return
            desc = _descriptor_seed_payload(lAlternateMaterialId)
            descriptor_ptr = _raw_u64_bits(lAlternateMaterialId)
            caller_offset = None
            caller_window = None
            if upper == DUNGEON_ROOT_SCENE:
                try:
                    caller_offset = int(self._trace_resource_add.caller_address())
                except Exception:
                    caller_offset = None
                caller_window = _capture_callsite_window(caller_offset)
            now_mono = time.monotonic()
            active_prepare = []
            for component, started in list(self._active_poi_prepare_components.items()):
                if now_mono - float(started) <= POI_PREPARE_SCOPE_MAX_SECONDS:
                    active_prepare.append(f"{component:016X}")
                else:
                    self._active_poi_prepare_components.pop(component, None)
            active_activation = [f"{component:016X}" for component in self._active_poi_activation_components]
            active_lifecycle = [f"{component:016X}" for component in self._active_poi_lifecycle_components]
            event = {
                "utc": _utc_now(),
                "kind": "resource_add",
                "resource_name": name,
                "resource_type": _safe_int(liType, -1),
                "resource_flags": _safe_int(liFlags, 0),
                "descriptor_pointer_hex": (f"{descriptor_ptr:016X}" if descriptor_ptr is not None else None),
                "caller_return_offset_hex": (f"{caller_offset:08X}" if caller_offset else None),
                "caller_code_window": caller_window,
                "primary_seed": desc.get("primary"),
                "secondary_seed": desc.get("secondary"),
                "poi_prepare_scope_component_hexes": active_prepare,
                "poi_activation_scope_component_hexes": active_activation,
                "poi_lifecycle_scope_component_hexes": active_lifecycle,
            }
            if upper == DUNGEON_ROOT_SCENE:
                try:
                    runtime_metadata = self._capture_runtime_metadata()
                    event["runtime_metadata_at_capture"] = runtime_metadata
                    event["universe_address_hex_at_capture"] = runtime_metadata.get("universe_address_hex")
                except Exception as exc:
                    event["runtime_metadata_at_capture"] = {"capture_error": repr(exc)}
                    event["universe_address_hex_at_capture"] = None
                entry_matches = self._logical_entry_matches_for_descriptor(descriptor_ptr)
                event["logical_entry_matches"] = entry_matches
                event["logical_entry_match_count"] = len(entry_matches)
                event["logical_entry_unique_callers_observed"] = len(self._logical_entry_caller_hits)
                event["logical_entry_static_candidate_count"] = None
                if entry_matches:
                    nearest = entry_matches[0]
                    nearest_offset = nearest.get("caller_return_offset_hex")
                    event["logical_entry_nearest_caller_return_offset_hex"] = nearest_offset
                    if nearest_offset:
                        try:
                            event["logical_entry_nearest_caller_code_window"] = _capture_callsite_window(int(str(nearest_offset), 16), before=96, after=64)
                        except Exception:
                            event["logical_entry_nearest_caller_code_window"] = None
                exact_external = self._logical_entry_external_match_for_descriptor(descriptor_ptr)
                if exact_external:
                    owner_hex = str(exact_external.get("owner_pointer_hex") or "")
                    try:
                        owner_pointer = int(owner_hex, 16)
                    except ValueError:
                        owner_pointer = 0
                    external_owner_hex = str(exact_external.get("external_owner_pointer_hex") or "")
                    try:
                        external_owner_pointer = int(external_owner_hex, 16)
                    except ValueError:
                        external_owner_pointer = 0
                    if external_owner_pointer > 0x10000:
                        exact_external["owner_plus_0x10_capture_at_root_add"] = _owner_plus_0x10_capture(
                            external_owner_pointer,
                            phase="root-resource-add",
                        )
                    if owner_pointer > 0x10000 and owner_pointer != external_owner_pointer:
                        exact_external["matched_descriptor_owner_plus_0x10_capture_at_root_add"] = _owner_plus_0x10_capture(
                            owner_pointer,
                            phase="root-resource-add-descriptor-owner",
                        )
                    entry_capture = exact_external.get("external_owner_plus_0x10_capture_at_entry")
                    if isinstance(entry_capture, dict):
                        entry_capture = dict(entry_capture)
                        entry_value = entry_capture.get("slot_value_hex")
                        if entry_capture.get("read_status") == "captured" and entry_value:
                            try:
                                entry_capture["target_identity"] = _loaded_module_identity(int(str(entry_value), 16))
                            except ValueError:
                                entry_capture["target_identity"] = {"status": "invalid-address", "address_hex": str(entry_value)}
                    register_snapshot = exact_external.get("external_call_register_snapshot_at_entry")
                    if isinstance(register_snapshot, dict):
                        register_snapshot = dict(register_snapshot)
                        register_snapshot["rdx_plus_0x10_capture"] = entry_capture
                        exact_external["external_call_register_snapshot_at_entry"] = register_snapshot
                    exact_external["owner_plus_0x10_capture"] = entry_capture
                    exact_external["owner_plus_0x10_capture_at_entry"] = entry_capture
                    event["owner_plus_0x10_capture"] = entry_capture
                    event["logical_entry_exact_external_match"] = exact_external
                    event["owner_plus_0x10_capture"] = exact_external.get("owner_plus_0x10_capture")
                    exact_offset = (
                        exact_external.get("resolved_external_caller_return_offset_hex")
                        or exact_external.get("external_origin_caller_return_offset_hex")
                        or exact_external.get("caller_return_offset_hex")
                    )
                    event["logical_entry_exact_external_match"] = exact_external
                    event["logical_entry_exact_external_caller_return_offset_hex"] = exact_offset
                    if exact_offset:
                        try:
                            event["logical_entry_exact_external_caller_code_window"] = _capture_callsite_window(int(str(exact_offset), 16), before=128, after=96)
                        except Exception:
                            event["logical_entry_exact_external_caller_code_window"] = None
                    self._persist_exact_root_caller(event, exact_external)
                else:
                    # Preserve the root seed and universe address even when
                    # the exact caller / owner slot was not observed.
                    self._persist_root_event(event)

            # The dungeon-root resource descriptor is the closest seed-bearing
            # object we have observed to actual derelict room construction.
            # Preserve it for up to 30 minutes because the root scene can load
            # well before the player crosses the interior trigger.
            if upper == DUNGEON_ROOT_SCENE:
                for state in self._active_poi_activation_components.values():
                    state["root_seen"] = True
                for state in self._active_poi_lifecycle_components.values():
                    state["root_seen"] = True
                buffered = {"_monotonic": time.monotonic(), **event}
                self._pre_session_dungeon_seeds.append(buffered)
                if len(self._pre_session_dungeon_seeds) > MAX_PRESESSION_DUNGEON_SEEDS:
                    del self._pre_session_dungeon_seeds[:-MAX_PRESESSION_DUNGEON_SEEDS]

            self._record_trace_event(event)
        except Exception as exc:
            self._write_log("trace_resource_error", {"error": repr(exc)})

    @nms.Engine.AddResource.after
    def _index_resource_after_add(
        self,
        result,
        liType,
        lpcName,
        liFlags,
        lAlternateMaterialId,
        unknown,
    ):
        """Map engine resource handles back to filenames for spawned-node probes."""
        try:
            name = _decode_pointer_text(lpcName)
            handle = _resource_handle_value(result)
            if name and handle is not None and handle >= 0:
                self._resource_names_by_handle[int(handle)] = name
                self._resource_index_sources[int(handle)] = "Engine.AddResource"
            self._record_raw_resource(name, handle, "Engine.AddResource", _safe_int(liType, -1))
        except Exception as exc:
            self._write_log("resource_index_error", {"error": repr(exc)})

    @get_caller
    @nms.cTkResourceManager.AddResource.before
    def _trace_resource_manager_add(
        self,
        this,
        result,
        liType,
        lsName,
        lxFlags,
        lbUserCall,
        lpResourceDescriptor,
        unknown,
    ):
        """Capture the inner resource-manager boundary for the dungeon root only."""
        try:
            name = _decode_pointer_text(lsName)
            if _normalize_scene_name(name) != DUNGEON_ROOT_SCENE:
                return
            descriptor_ptr = _raw_u64_bits(lpResourceDescriptor)
            desc = _descriptor_seed_payload(lpResourceDescriptor)
            try:
                caller_offset = int(self._trace_resource_manager_add.caller_address())
            except Exception:
                caller_offset = None
            self._record_trace_event({
                "kind": "resource_manager_add",
                "resource_name": name,
                "resource_type": _safe_int(liType, -1),
                "resource_flags": _safe_int(lxFlags, 0),
                "user_call": _safe_bool(lbUserCall),
                "descriptor_pointer_hex": (f"{descriptor_ptr:016X}" if descriptor_ptr is not None else None),
                "caller_return_offset_hex": (f"{caller_offset:08X}" if caller_offset else None),
                "primary_seed": desc.get("primary"),
                "secondary_seed": desc.get("secondary"),
                "poi_activation_scope_component_hexes": [f"{component:016X}" for component in self._active_poi_activation_components],
                "poi_lifecycle_scope_component_hexes": [f"{component:016X}" for component in self._active_poi_lifecycle_components],
            })
        except Exception as exc:
            self._write_log("trace_resource_manager_add_error", {"error": repr(exc)})

    @nms.cTkResource.cTkResource.after
    def _index_resource_ctor(self, this, liType, lsName, lxFlags):
        """Second resource-name index path that does not depend on AddResource's hidden return storage."""
        try:
            self._resource_ctor_events_seen += 1
            name = _decode_fixed_string_pointer(lsName)
            handle = None
            try:
                obj = this.contents
                if not name:
                    name = str(obj.msName)
                handle = int(obj.mHandle)
            except Exception:
                pass
            if name and handle is not None and handle >= 0:
                self._resource_names_by_handle[int(handle)] = name
                self._resource_index_sources[int(handle)] = "cTkResource.cTkResource"
            self._record_raw_resource(name, handle, "cTkResource.cTkResource", _safe_int(liType, -1))
        except Exception as exc:
            self._write_log("resource_ctor_index_error", {"error": repr(exc)})

    @nms.Engine.AddNodes.after
    def _auto_crate_add_nodes(self, result, parent, sceneGraphRes):
        """Count actual spawned scene roots matching Salvage Crate or Crew Footlocker."""
        try:
            resource_handle = _safe_int(sceneGraphRes, -1)
            resource_name = self._resource_names_by_handle.get(resource_handle, "")
            self._probe_spawned_node(result, "Engine.AddNodes", resource_name, resource_handle, parent)
        except Exception as exc:
            self._write_log("auto_crate_add_nodes_error", {"error": repr(exc)})

    @nms.Engine.AddGroupNode.after
    def _auto_crate_add_group_node(self, result, parent, name):
        """Observe dynamically generated group nodes; some dungeon objects use their product ID as the node name."""
        try:
            explicit_name = _decode_pointer_text(name)
            # Avoid a second GetNodeName call when the generator gives us the
            # explicit group label. Count only a real returned node handle.
            key = _handle_key(result)
            try:
                node_obj = result.contents
            except Exception:
                node_obj = result
            resolved_handle, resolved_name = self._resolve_node_resource(node_obj if key else None)
            parent_name = ""
            if parent is not None:
                try:
                    parent_name = _decode_pointer_text(nms.Engine.GetNodeName(parent))
                except Exception:
                    parent_name = ""
            self._record_scene_probe({
                "kind": "spawned_group",
                "method": "Engine.AddGroupNode",
                "instance_key": key,
                "parent_key": _handle_key(parent),
                "parent_node_name": parent_name or None,
                "node_name": explicit_name or None,
                "scene_graph_handle": None,
                "node_resource_handle": resolved_handle,
                "resource_name": resolved_name or None,
            })
            matched = _target_crate_name_match(explicit_name) or _target_crate_name_match(resolved_name)
            target_id = matched[0] if matched else None
            match = matched[1] if matched else None
            discovery = _crate_discovery_name(explicit_name) or _crate_discovery_name(resolved_name)
            relevant = self._session is not None or self._is_on_derelict() or bool(match) or discovery
            if not relevant:
                return
            self._node_spawn_events_seen += 1
            if self._session is not None:
                self._session_auto_node_probes += 1
                self._session.setdefault("auto_crates", {})["node_probe_events_seen"] = self._session_auto_node_probes
            if match or discovery:
                self._record_auto_crate_event({
                    "kind": "node_probe",
                    "method": "Engine.AddGroupNode",
                    "instance_key": key,
                    "node_name": explicit_name or None,
                    "resource_name": resolved_name or None,
                    "target_id": target_id,
                    "match": match,
                    "countable": bool(key and matched),
                    "discovery_only": bool(discovery and not match),
                })
            if key and matched:
                summary = self._auto_crate_summary()
                self._last_event = f"Auto target container detected #{summary.get('count', 0)}"
                self._last_event_utc = _utc_now()
                self._publish_live_status(force=True)
        except Exception as exc:
            self._write_log("auto_crate_add_group_error", {"error": repr(exc)})

    @nms.cGcRewardManager.GiveGenericReward.before
    def _trace_generic_reward(
        self,
        this,
        lRewardID,
        lMissionID,
        lSeed,
        lbPeek,
        lbForceShowMessage,
        liOutMultiProductCount,
        lbForceSilent,
        lInventoryChoiceOverride,
        lbUseMiningModifier,
    ):
        """Capture reward IDs/seeds while a derelict session is active."""
        try:
            if self._session is None and not self._is_on_derelict():
                return
            event = {
                "kind": "reward",
                "reward_id": _decode_fixed_string_pointer(lRewardID),
                "mission_id": _decode_fixed_string_pointer(lMissionID),
                "seed": _seed_payload(lSeed),
                "peek": _safe_bool(lbPeek),
                "force_show_message": _safe_bool(lbForceShowMessage),
                "force_silent": _safe_bool(lbForceSilent),
                "inventory_choice_override": _safe_int(lInventoryChoiceOverride, -1),
                "use_mining_modifier": _safe_bool(lbUseMiningModifier),
            }
            self._record_trace_event(event)
            self._last_event = f"Reward seed captured: {event.get('reward_id') or 'unknown reward'}"
            self._last_event_utc = _utc_now()
            self._publish_live_status(force=True)
        except Exception as exc:
            self._write_log("trace_reward_error", {"error": repr(exc)})

    # ------------------------------- Hotkeys --------------------------------
    @on_key_pressed("f5")
    def mark_room_zero(self):
        self._add_marker("room_zero")

    @on_key_pressed("f6")
    def mark_room(self):
        self._add_marker("room")

    @on_key_pressed("f7")
    def mark_blue_crate(self):
        self._add_marker("blue_crate")

    @on_key_pressed("f8")
    def mark_vertical_transition(self):
        self._add_marker("vertical_transition")

    @on_key_pressed("f9")
    def mark_shuttle_bay(self):
        self._add_marker("shuttle_bay")

    @on_key_pressed("f10")
    def mark_engineering(self):
        self._add_marker("engineering")

    @on_key_pressed("f11")
    def cycle_engineering_module_class(self):
        """Cycle the Engineering freighter-module rank: unknown -> C -> B -> A -> S -> unknown."""
        with self._lock:
            if self._session is None:
                self._status = "Ignored module rank: no active session"
                self._last_event = self._status
                self._last_event_utc = _utc_now()
                self._publish_live_status(force=True)
                return
            order = ["unknown", "C", "B", "A", "S"]
            current = str(self._session.get("manual", {}).get("engineering_module_class", "unknown"))
            current = current if current in order else "unknown"
            new_value = order[(order.index(current) + 1) % len(order)]
            self._session["manual"]["engineering_module_class"] = new_value
            display = new_value.upper() if new_value != "unknown" else "UNKNOWN"
            self._status = f"Engineering module rank: {display}"
            self._last_event = f"Module rank set to {display} (F11)"
            self._last_event_utc = _utc_now()
            self._write_log("engineering_module_class", {"value": new_value, "hotkey": "F11"})
            self._save_session()
            self._publish_live_status(force=True)

    # ------------------------------ Main loop -------------------------------
    def _poll_controller_command(self, now: float):
        if now - self._last_controller_poll_monotonic < CONTROLLER_COMMAND_POLL_SECONDS:
            return
        self._last_controller_poll_monotonic = now
        if not self._controller_command_path.is_file():
            return
        try:
            payload = json.loads(self._controller_command_path.read_text(encoding="utf-8-sig"))
            command_id = str(payload.get("id") or "")
            action = str(payload.get("action") or "").strip()
            if not command_id or command_id == self._last_controller_command_id:
                return
            self._last_controller_command_id = command_id
            status = "ok"
            detail = action
            if action == "force_start_session":
                if not self._session:
                    self._manual_started = True
                    self._start_session(trigger="controller")
                detail = "Session started" if self._session else "Session start requested"
            elif action == "stop_session":
                if self._session:
                    self._end_session(reason="controller_stop")
                detail = "Session saved/stopped"
            elif action == "undo_last_marker":
                if self._session and self._session.get("markers"):
                    removed = self._session["markers"].pop()
                    self._write_log("marker_undone", {**removed, "source": "controller"})
                    self._save_session()
                    detail = f"Removed {removed.get('type', 'marker')}"
                else:
                    detail = "No marker to undo"
            elif action == "write_diagnostic_snapshot":
                self.write_diagnostic_snapshot()
                detail = "Diagnostic snapshot written"
            else:
                status = "error"
                detail = f"Unknown controller action: {action}"
            self._controller_ack_path.write_text(json.dumps({
                "version": 1, "id": command_id, "utc": _utc_now(),
                "action": action, "status": status, "detail": detail,
            }, indent=2), encoding="utf-8")
            self._write_log("controller_command", {"id": command_id, "action": action, "status": status, "detail": detail})
            self._publish_live_status(force=True)
        except Exception as exc:
            self._write_log("controller_command_error", {"error": repr(exc)})

    @main_loop.after
    def _tick(self):
        now = time.monotonic()
        if now - self._last_tick < 0.10:
            return
        self._last_tick = now
        try:
            self._poll_controller_command(now)
            on_derelict = self._is_on_derelict()
            if on_derelict:
                self._last_non_derelict_monotonic = None
                if self._session is None:
                    self._start_session(trigger="environment")
                self._sample_position(now)
                if now - self._last_autosave_monotonic >= AUTOSAVE_INTERVAL_SECONDS:
                    self._save_session()
                    self._last_autosave_monotonic = now
            elif self._session is not None and not self._manual_started:
                if self._last_non_derelict_monotonic is None:
                    self._last_non_derelict_monotonic = now
                elif now - self._last_non_derelict_monotonic >= AUTO_END_GRACE_SECONDS:
                    self._end_session(reason="left_abandoned_freighter")
            self._publish_live_status()
        except Exception as exc:
            self._record_error("tick", exc)

    # ------------------------------ Capture ---------------------------------
    def _is_on_derelict(self) -> bool:
        env = gameData.player_environment
        if env is None:
            return False
        for attr in ("meLocationStable", "meLocation"):
            try:
                value = getattr(env, attr)
                if _safe_int(value, -1) == ABANDONED_FREIGHTER_LOCATION_VALUE:
                    return True
                if getattr(value, "name", "") == "AbandonedFreighter":
                    return True
            except Exception:
                continue
        return False

    @staticmethod
    def _vector_position(value: Any) -> dict[str, float] | None:
        try:
            pos = {"x": float(value.x), "y": float(value.y), "z": float(value.z)}
            if all(math.isfinite(v) for v in pos.values()):
                return pos
        except Exception:
            pass
        return None

    def _player_position_with_source(self) -> tuple[dict[str, float] | None, str, dict[str, Any]]:
        """Return the best live position plus its source and compact candidates.

        Prefer a non-zero finite source when alternatives disagree. A true origin
        position is still retained if every available source is zero. The candidate
        map is published to live-status.json so telemetry problems can be diagnosed
        without another instrumented build.
        """
        candidates: list[tuple[str, dict[str, float]]] = []

        player = gameData.player
        if player is not None:
            try:
                pos = self._vector_position(player.mPosition)
                if pos is not None:
                    candidates.append(("player.mPosition", pos))
            except Exception:
                pass

        try:
            env = gameData.player_environment
            if env is not None:
                pos = self._vector_position(env.mPlayerTM.pos)
                if pos is not None:
                    candidates.append(("environment.mPlayerTM", pos))
        except Exception:
            pass

        if player is not None:
            try:
                mat = GetNodeAbsoluteTransMatrix(player.mRootNode)
                pos = self._vector_position(mat.pos)
                if pos is not None:
                    candidates.append(("scene_node_absolute", pos))
            except Exception:
                pass

        compact = {
            source: {"x": round(pos["x"], 4), "y": round(pos["y"], 4), "z": round(pos["z"], 4)}
            for source, pos in candidates
        }
        if not candidates:
            return None, "unavailable", compact

        def meaningful(pos: dict[str, float]) -> bool:
            return abs(pos["x"]) + abs(pos["y"]) + abs(pos["z"]) > 0.0001

        for source, pos in candidates:
            if meaningful(pos):
                return pos, source, compact
        source, pos = candidates[0]
        return pos, source, compact

    def _player_position(self) -> dict[str, float] | None:
        pos, _source, _candidates = self._player_position_with_source()
        return pos

    def _capture_runtime_metadata(self) -> dict[str, Any]:
        meta: dict[str, Any] = {
            "environment_location": None,
            "system_name": None,
            "reality_index": None,
            "galactic_address": None,
            "universe_address_hex": None,
        }
        try:
            env = gameData.player_environment
            if env is not None:
                live_loc = getattr(env, "meLocation", None)
                stable_loc = getattr(env, "meLocationStable", None)
                live_name = getattr(live_loc, "name", str(live_loc))
                stable_name = getattr(stable_loc, "name", str(stable_loc))
                meta["environment_location_live"] = live_name
                meta["environment_location_stable"] = stable_name

                # If either view reports the derelict, preserve that as the
                # canonical environment for the session snapshot. v0.2.2
                # preferred the stable value unconditionally, which produced
                # misleading `Default` snapshots in the first verified run.
                if (
                    _safe_int(live_loc, -1) == ABANDONED_FREIGHTER_LOCATION_VALUE
                    or getattr(live_loc, "name", "") == "AbandonedFreighter"
                ):
                    meta["environment_location"] = "AbandonedFreighter"
                elif (
                    _safe_int(stable_loc, -1) == ABANDONED_FREIGHTER_LOCATION_VALUE
                    or getattr(stable_loc, "name", "") == "AbandonedFreighter"
                ):
                    meta["environment_location"] = "AbandonedFreighter"
                else:
                    meta["environment_location"] = stable_name if stable_loc is not None else live_name
        except Exception as exc:
            meta["environment_error"] = repr(exc)

        try:
            ps = gameData.player_state
            if ps is not None:
                location = ps.mLocation
                ga = location.GalacticAddress
                reality = _safe_int(location.RealityIndex)
                planet = _safe_int(ga.PlanetIndex)
                solar = _safe_int(ga.SolarSystemIndex)
                vx = _safe_int(ga.VoxelX)
                vy = _safe_int(ga.VoxelY)
                vz = _safe_int(ga.VoxelZ)
                meta["reality_index"] = reality
                meta["galactic_address"] = {
                    "planet_index": planet,
                    "solar_system_index": solar,
                    "voxel_x": vx,
                    "voxel_y": vy,
                    "voxel_z": vz,
                }
                iteration = min(max(reality, 0), 0xFF)
                solar_index = min(max(solar, 0), 0xFFF)
                ua = (
                    (vx & 0xFFF)
                    | ((vz & 0xFFF) << 12)
                    | ((vy & 0xFF) << 24)
                    | (iteration << 32)
                    | (solar_index << 40)
                    | ((planet & 0xF) << 52)
                )
                meta["universe_address_hex"] = f"{ua:016X}"
        except Exception as exc:
            meta["address_error"] = repr(exc)

        try:
            sim = gameData.simulation
            if sim is not None and sim.mpSolarSystem:
                name = basic.cTkFixedString0x80()
                sim.mpSolarSystem.contents.GetName(ctypes.byref(name))
                meta["system_name"] = str(name)
        except Exception as exc:
            meta["system_name_error"] = repr(exc)
        return meta

    def _start_session(self, trigger: str):
        with self._lock:
            if self._session is not None:
                return
            now_utc = _utc_now()
            runtime = self._capture_runtime_metadata()
            safe_system = runtime.get("universe_address_hex") or "unknown"
            if runtime.get("system_name"):
                safe_system = "".join(c if c.isalnum() or c in "-_" else "_" for c in runtime["system_name"])[:48]
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            self._session_path = self._sessions_dir / f"{stamp}_{safe_system}.json"
            trace_events = self._recent_pre_session_trace()
            current_ua_raw = str(runtime.get("universe_address_hex") or "").upper()
            current_ua = current_ua_raw.zfill(16) if current_ua_raw else ""

            # v0.3.12 proved the POI context value equals the universe address,
            # but a long retention window could carry the previous system's
            # address into a new session. Keep only POI context matching the
            # session UA when the UA is known.
            poi_mismatches: list[dict[str, Any]] = []
            seen_poi = {(e.get("utc"), e.get("kind"), e.get("raw_argument_hex")) for e in trace_events if e.get("kind") == "space_poi_description"}
            filtered_trace: list[dict[str, Any]] = []
            for event in trace_events:
                if event.get("kind") == "space_poi_description" and current_ua:
                    hx = str(event.get("raw_argument_hex") or "").upper().zfill(16)
                    if hx and hx != current_ua:
                        poi_mismatches.append(event)
                        continue
                filtered_trace.append(event)
            trace_events = filtered_trace
            seen_poi = {(e.get("utc"), e.get("kind"), e.get("raw_argument_hex")) for e in trace_events if e.get("kind") == "space_poi_description"}
            for event in self._recent_pre_session_poi_candidates():
                hx = str(event.get("raw_argument_hex") or "").upper().zfill(16)
                if current_ua and hx and hx != current_ua:
                    poi_mismatches.append(event)
                    continue
                key = (event.get("utc"), event.get("kind"), event.get("raw_argument_hex"))
                if key not in seen_poi:
                    trace_events.append(event)
                    seen_poi.add(key)

            # The dungeon-root descriptor seed is retained independently of the
            # generic 60-second trace. Prefer candidates captured in the same UA.
            seen_root = {
                (e.get("kind"), (e.get("primary_seed") or {}).get("seed_hex"), str(e.get("universe_address_hex_at_capture") or "").upper())
                for e in trace_events
                if e.get("kind") == "resource_add"
                and _normalize_scene_name(str(e.get("resource_name") or "")) == DUNGEON_ROOT_SCENE
            }
            for event in self._recent_pre_session_dungeon_seeds():
                captured_raw = str(event.get("universe_address_hex_at_capture") or "").upper()
                captured_ua = captured_raw.zfill(16) if captured_raw else ""
                if current_ua and captured_ua and captured_ua != current_ua:
                    continue
                key = (event.get("kind"), (event.get("primary_seed") or {}).get("seed_hex"), str(event.get("universe_address_hex_at_capture") or "").upper())
                if key not in seen_root:
                    trace_events.append(event)
                    seen_root.add(key)

            trace_events.sort(key=lambda e: str(e.get("utc") or ""))
            self._last_auto_crate_summary = {
                "count": 0, "target_ids": list(TARGET_CRATE_IDS), "status": "inactive",
                "confidence": "unknown", "method": "none", "node_spawn_events": 0,
                "salvage_crates": 0, "crew_footlockers": 0,
                "candidate_name_count": 0, "last_candidate_name": None,
                "scene_probe_events": 0, "resolved_resource_names": 0,
                "resource_index_size": len(self._resource_names_by_handle),
                "resource_find_events": self._resource_find_events_seen,
                "resource_find_mapped": len(self._resource_find_mapped_handles),
                "scene_handle_unique": 0, "scene_handle_top": [],
            }
            self._session = {
                "schema_version": SCHEMA_VERSION,
                "probe_version": PROBE_VERSION,
                "session_id": f"{stamp}_{runtime.get('universe_address_hex') or 'unknown'}",
                "started_utc": now_utc,
                "ended_utc": None,
                "start_trigger": trigger,
                "end_reason": None,
                "runtime_start": runtime,
                "runtime_end": None,
                "path_samples": [],
                "markers": [],
                "trace": {
                    "capture_version": 1,
                    "pre_session_window_seconds": TRACE_PRESESSION_SECONDS,
                    "events": trace_events,
                    "event_limit_reached": False,
                },
                "auto_crates": {
                    "capture_version": 2,
                    "target_ids": list(TARGET_CRATE_IDS),
                    "pre_session_window_seconds": TRACE_PRESESSION_SECONDS,
                    "events": self._recent_pre_session_auto_crates(),
                    "event_limit_reached": False,
                    "read_only": True,
                },
                "scene_probe": {
                    "capture_version": 1,
                    "pre_session_window_seconds": TRACE_PRESESSION_SECONDS,
                    "events": self._recent_pre_session_scene_probes(),
                    "event_limit_reached": False,
                    "read_only": True,
                },
                "raw_resources": {
                    "capture_version": 1,
                    "pre_session_window_seconds": TRACE_PRESESSION_SECONDS,
                    "events": self._recent_pre_session_raw_resources(),
                    "event_limit_reached": False,
                    "read_only": True,
                },
                "manual": _empty_manual(),
                "diagnostics": {
                    "errors": [],
                    "sample_limit_reached": False,
                    "read_only_game_state": True,
                    "discarded_pre_session_poi_context_mismatches": len(poi_mismatches),
                },
            }
            self._last_sample_monotonic = 0.0
            self._last_autosave_monotonic = time.monotonic()
            self._session_auto_node_probes = 0
            self._pre_session_auto_crates = []
            self._pre_session_scene_probes = []
            self._pre_session_raw_resources = []
            if trigger == "environment":
                self._status = "Entered derelict — recording started automatically"
                self._last_event = "Entered derelict — recording started"
            else:
                self._status = "Recording derelict baseline (manual start)"
                self._last_event = "Recording started manually"
            self._last_event_utc = _utc_now()
            self._write_log("session_started", {"trigger": trigger, "path": str(self._session_path), "runtime": runtime})
            self._sample_position(time.monotonic(), force=True)
            self._save_session()
            self._publish_live_status(force=True)

    def _end_session(self, reason: str):
        with self._lock:
            if self._session is None:
                return
            self._session["ended_utc"] = _utc_now()
            self._session["end_reason"] = reason
            self._session["runtime_end"] = self._capture_runtime_metadata()
            final_auto = self._auto_crate_summary()
            self._session.setdefault("auto_crates", {})["final_summary"] = final_auto
            self._last_auto_crate_summary = {**final_auto, "status": "saved"}
            # Preserve the final per-room loot summary for the companion after
            # the active session object is cleared.
            self._last_generation_room_summary = self._generation_room_summary()
            self._save_session(final=True)
            self._write_log("session_ended", {"reason": reason, "path": str(self._session_path)})
            saved_name = self._session_path.name if self._session_path else "session"
            self._status = f"Saved baseline — {saved_name}; ready for another derelict"
            self._last_event = "Left derelict — recording saved" if reason == "left_abandoned_freighter" else "Recording stopped — session saved"
            self._last_event_utc = _utc_now()
            self._session = None
            self._session_path = None
            self._manual_started = False
            self._last_non_derelict_monotonic = None
            self._pre_session_auto_crates = []
            self._pre_session_scene_probes = []
            self._pre_session_raw_resources = []
            self._session_auto_node_probes = 0
            self._publish_live_status(force=True)

    def _sample_position(self, now: float, force: bool = False):
        with self._lock:
            if self._session is None:
                return
            samples = self._session["path_samples"]
            if len(samples) >= MAX_PATH_SAMPLES:
                self._session["diagnostics"]["sample_limit_reached"] = True
                return
            if not force and now - self._last_sample_monotonic < SAMPLE_INTERVAL_SECONDS:
                return
            pos, pos_source, _pos_candidates = self._player_position_with_source()
            if pos is None:
                return
            should_add = force or not samples
            if samples and not should_add:
                last = samples[-1]
                moved = _distance(pos, last)
                elapsed = now - self._last_sample_monotonic
                should_add = moved >= MIN_SAMPLE_DISTANCE_METRES or elapsed >= FORCE_SAMPLE_AFTER_SECONDS
            if should_add:
                elapsed_s = max(0.0, now - self._last_tick + 0.0)
                sample = {
                    "utc": _utc_now(),
                    "x": round(pos["x"], 4),
                    "y": round(pos["y"], 4),
                    "z": round(pos["z"], 4),
                    "position_source": pos_source,
                }
                samples.append(sample)
                self._last_sample_monotonic = now

    def _add_marker(self, marker_type: str):
        now = time.monotonic()
        with self._lock:
            if now - self._last_marker_monotonic < MARKER_DEBOUNCE_SECONDS:
                return
            self._last_marker_monotonic = now
            if self._session is None:
                self._status = f"Ignored {marker_type}: no active session"
                self._last_event = self._status
                self._last_event_utc = _utc_now()
                self._publish_live_status(force=True)
                return
            pos, pos_source, _pos_candidates = self._player_position_with_source()
            if pos is None:
                self._status = f"Could not mark {marker_type}: player position unavailable"
                self._last_event = self._status
                self._last_event_utc = _utc_now()
                self._publish_live_status(force=True)
                return
            marker = {
                "utc": _utc_now(),
                "type": marker_type,
                "x": round(pos["x"], 4),
                "y": round(pos["y"], 4),
                "z": round(pos["z"], 4),
                "position_source": pos_source,
                "ordinal": 1 + sum(1 for m in self._session["markers"] if m["type"] == marker_type),
            }
            self._session["markers"].append(marker)
            label = {
                "blue_crate": "Crate added",
                "room": "Room/zone added",
                "room_zero": "Room 0 / dead end added",
                "vertical_transition": "Vertical transition added",
                "shuttle_bay": "Shuttle Bay added",
                "engineering": "Engineering marked",
            }.get(marker_type, "Marker added")
            hotkey = {
                "blue_crate": "F7",
                "room": "F6",
                "room_zero": "F5",
                "vertical_transition": "F8",
                "shuttle_bay": "F9",
                "engineering": "F10",
            }.get(marker_type, "")
            self._status = f"{label} #{marker['ordinal']}"
            self._last_event = f"{label} #{marker['ordinal']}{f' ({hotkey})' if hotkey else ''}"
            self._last_event_utc = _utc_now()
            self._write_log("marker", marker)
            self._save_session()
            self._publish_live_status(force=True)

    # ------------------------------- I/O ------------------------------------
    def _save_session(self, final: bool = False):
        with self._lock:
            if self._session is None or self._session_path is None:
                return
            try:
                self._atomic_write_json(self._session_path, self._session)
                self._atomic_write_json(self._root / "latest.json", self._session)
                if final:
                    self._status = f"Saved {self._session_path.name}"
            except Exception as exc:
                self._record_error("save_session", exc)

    @staticmethod
    def _atomic_write_json(path: Path, payload: dict[str, Any]):
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8", newline="\n") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)

    def _write_log(self, event: str, payload: dict[str, Any]):
        try:
            record = {"utc": _utc_now(), "event": event, **payload}
            with self._latest_log.open("a", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        except Exception:
            pass

    def _record_error(self, where: str, exc: Exception):
        message = f"{where}: {type(exc).__name__}: {exc}"
        self._latest_error = message[:1000]
        self._last_event = f"Probe error: {where}"
        self._last_event_utc = _utc_now()
        logger.exception("DerelictBaselineProbe error in %s", where)
        self._write_log("error", {"where": where, "error": repr(exc)})
        with self._lock:
            if self._session is not None:
                errors = self._session["diagnostics"]["errors"]
                if len(errors) < 100:
                    errors.append({"utc": _utc_now(), "where": where, "error": repr(exc)})
        self._publish_live_status(force=True)
