"""Install / uninstall / self-removal of the minimap's autostart (stdlib only, Windows).

What this program leaves on a PC, and nothing else:
  - one visible shortcut in the user's Startup folder ("NMS Derelict Minimap.lnk"), only if the user chose autostart
  - one entry in "Installed apps" (HKCU ...\\Uninstall\\NMSDerelictMinimap) so it can be removed like any program
  - its own folder (settings, caches, mod_state.json)
No services, no scheduled tasks, no registry Run keys, nothing hidden, no admin rights.

The autostart removes itself (the shortcut goes; the program stays and can be started by hand or re-installed):
  1. NMS is not installed any more: not found on MISSING_DAYS different days spanning at least MISSING_SPAN_DAYS
     (an unplugged game drive does not trigger it)
  2. NMS has not been running for UNUSED_DAYS days
A message box and NOTICE-autostart-removed.txt say what happened. The overlay also exits when minimap/STOP exists.

    python -I minimap/lifecycle.py status | install [--no-register] | uninstall | steam-line
"""
from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PKG = ROOT.parent if (ROOT.parent / ".nmsmm-home").is_file() else ROOT     # portable package root (the launchers live there)
APP_NAME = "NMS Derelict Minimap"
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\NMSDerelictMinimap"
STATE_FILE = HERE / "mod_state.json"
NOTICE_FILE = PKG / "NOTICE-autostart-removed.txt"
STOP_FILE = HERE / "STOP"
VERSION = "0.4.0"

MISSING_DAYS = 3          # NMS not found on this many different days...
MISSING_SPAN_DAYS = 7     # ...spanning at least this many days
UNUSED_DAYS = 30          # NMS never ran for this long


# ---------------------------------------------------------------- state
def _today() -> int:
    return date.today().toordinal()


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(st: dict) -> None:
    try:
        STATE_FILE.write_text(json.dumps(st, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass


# ---------------------------------------------------------------- autostart shortcut
def startup_dir() -> Path:
    return Path(os.environ.get("APPDATA", str(Path.home() / "AppData/Roaming"))) / "Microsoft/Windows/Start Menu/Programs/Startup"


def shortcut_path() -> Path:
    return startup_dir() / f"{APP_NAME}.lnk"


def pythonw() -> Path:
    exe = Path(sys.executable)
    w = exe.with_name("pythonw.exe")
    return w if w.is_file() else exe


def launch_args() -> tuple[str, str]:
    """(program, arguments) that start the overlay with no console window."""
    return str(pythonw()), f'-I "{HERE / "overlay.py"}"'


def _ps_quote(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def create_shortcut() -> Path:
    prog, args = launch_args()
    lnk = shortcut_path()
    lnk.parent.mkdir(parents=True, exist_ok=True)
    script = (
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut(" + _ps_quote(str(lnk)) + ");"
        "$s.TargetPath=" + _ps_quote(prog) + ";$s.Arguments=" + _ps_quote(args) + ";"
        "$s.WorkingDirectory=" + _ps_quote(str(PKG)) + ";$s.WindowStyle=7;"
        "$s.Description='Derelict minimap overlay for No Mans Sky (local, read-only)';$s.Save()"
    )
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], check=True,
                   capture_output=True, creationflags=0x08000000)
    return lnk


def autostart_installed() -> bool:
    return shortcut_path().is_file()


def remove_shortcut() -> bool:
    try:
        shortcut_path().unlink()
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


# ---------------------------------------------------------------- "Installed apps" entry
def register_uninstaller() -> None:
    import winreg
    py = str(pythonw())
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as k:
        for name, val in (("DisplayName", APP_NAME), ("DisplayVersion", VERSION), ("Publisher", "NMS Derelict Probe (community)"),
                          ("InstallLocation", str(PKG)),
                          ("UninstallString", f'"{py}" -I "{HERE / "lifecycle.py"}" uninstall --quiet')):
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, val)
        winreg.SetValueEx(k, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(k, "NoRepair", 0, winreg.REG_DWORD, 1)


def unregister_uninstaller() -> None:
    import winreg
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
    except OSError:
        pass


def registered() -> bool:
    import winreg
    try:
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY))
        return True
    except OSError:
        return False


# ---------------------------------------------------------------- commands
def install(register: bool = True) -> None:
    lnk = create_shortcut()
    if register:
        register_uninstaller()
    st = load_state()
    st.update({"installed": _today(), "last_nms_run": st.get("last_nms_run") or _today(), "missing_days": [], "autostart": True})
    save_state(st)
    try:
        STOP_FILE.unlink()
    except OSError:
        pass
    print(f"Autostart installed: {lnk}")


def uninstall(quiet: bool = False) -> None:
    remove_shortcut()
    unregister_uninstaller()
    try:
        STOP_FILE.write_text("uninstalled\n", encoding="utf-8")     # a running overlay sees this and exits
    except OSError:
        pass
    st = load_state()
    st["autostart"] = False
    save_state(st)
    if not quiet:
        print("Autostart and the 'Installed apps' entry removed. A running overlay closes itself within a few seconds.\n"
              f"The program folder ({PKG}) can now simply be deleted.")


def steam_line() -> str:
    return f'"{PKG / "Start-With-NMS.cmd"}" %command%'


def status() -> dict:
    st = load_state()
    return {"autostart_shortcut": autostart_installed(), "installed_apps_entry": registered(),
            "last_nms_run_days_ago": (_today() - st["last_nms_run"]) if st.get("last_nms_run") else None,
            "missing_check_days": st.get("missing_days", []), "stop_file": STOP_FILE.exists()}


# ---------------------------------------------------------------- self-removal rules (called by the overlay)
def evaluate(st: dict, nms_found: bool, nms_running: bool, today: int | None = None) -> tuple[dict, str | None]:
    """Pure rule check. Returns (new state, reason or None). Only meaningful while the autostart shortcut exists."""
    today = _today() if today is None else today
    st = dict(st)
    days = [d for d in st.get("missing_days", []) if d >= today - 60]
    if nms_running:
        st["last_nms_run"] = today
    if nms_found:
        days = []
    elif today not in days:
        days.append(today)
    st["missing_days"] = days
    if not nms_found and len(days) >= MISSING_DAYS and today - min(days) >= MISSING_SPAN_DAYS:
        return st, (f"No Man's Sky was not found on this PC on {len(days)} different days over "
                    f"{today - min(days)} days, so it looks uninstalled.")
    last = st.get("last_nms_run") or st.get("installed") or today
    if today - last >= UNUSED_DAYS:
        return st, f"No Man's Sky has not been started for {today - last} days."
    return st, None


def remove_autostart_with_notice(reason: str, quiet: bool = False) -> None:
    remove_shortcut()
    text = (f"{APP_NAME}: autostart removed.\n\n{reason}\n\nThe minimap will no longer start with Windows. "
            f"It is still in {PKG}.\nTo bring it back, run:  python -I minimap\\lifecycle.py install\n"
            "or just delete the folder if you no longer need it.\n")
    try:
        NOTICE_FILE.write_text(text, encoding="utf-8")
    except OSError:
        pass
    st = load_state()
    st["autostart"] = False
    save_state(st)
    if not quiet:
        try:
            ctypes.windll.user32.MessageBoxW(0, text, APP_NAME, 0x40)
        except Exception:
            pass


def check_and_apply(nms_found: bool, nms_running: bool) -> str | None:
    """Overlay hook: update the state and apply the rules. Returns the reason if the autostart was just removed."""
    if not autostart_installed():
        st = load_state()
        if nms_running:
            st["last_nms_run"] = _today()
            save_state(st)
        return None
    st, reason = evaluate(load_state(), nms_found, nms_running)
    save_state(st)
    if reason:
        remove_autostart_with_notice(reason)
    return reason


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "status"
    if cmd == "install":
        install(register="--no-register" not in argv)
    elif cmd == "uninstall":
        uninstall(quiet="--quiet" in argv)
    elif cmd == "steam-line":
        print("Steam > right-click No Man's Sky > Properties > General > Launch Options, paste:\n\n  " + steam_line())
    else:
        print(json.dumps(status(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
