"""Small native desktop runner using Python's bundled Tk toolkit."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import queue
import subprocess
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from . import VERSION
from .common import HERE
from .gui_process import WorkerProcess
from .local_runner import is_paused, load_executable_selection, save_executable_selection, set_paused
from .runner_protocol import digest, publish_request

STAGES = {"setup": "Preparing Unicorn", "snapshot": "Freezing source", "source-package": "Packaging source",
          "tests": "Running tests", "diagnose": "Checking captured scenes", "code": "Checking code evidence",
          "emulate": "Running Unicorn comparisons", "export": "Exporting selected game bytes",
          "complete": "Checks completed", "watching": "Waiting for source changes", "runner": "Runner",
          "request": "Checking request", "update": "Checking verified update"}


def read_state(root, name):
    try:
        path = root / ".local" / name
        if path.stat().st_size > 512 * 1024:
            return {}
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def display_status(event):
    stage, status = event.get("stage"), event.get("status")
    if status == "paused":
        return "Paused — current job has finished", False
    if status in ("failed", "blocked", "rejected"):
        return STAGES.get(stage, "Runner") + " needs attention", False
    if stage == "watching":
        return "Ready — watching for source changes", False
    return STAGES.get(stage, "Starting runner") + ("…" if status == "running" else ""), status == "running"


class RunnerWindow:
    def __init__(self, window, root=HERE, autostart=True):
        self.window, self.root = window, Path(root).resolve()
        self.worker = WorkerProcess(self.root)
        self.mode = None
        self.closing = False
        self.update_wait_version = None
        self.update_wait_attempts = 0
        self.update_wait_started = None
        self.update_wait_last_log = 0
        self.last_log_at = time.monotonic()
        self.exe_selection_invalid = False
        try:
            self.executable = load_executable_selection(self.root)
        except ValueError:
            self.executable = None
            self.exe_selection_invalid = True
        self.pause_requested = False
        self.queued_id = None
        self.window.title("NMS Offline · " + VERSION)
        self.window.geometry("920x690")
        self.window.minsize(820, 620)
        self.window.configure(bg="#111827")
        style = ttk.Style(window)
        style.theme_use("clam")
        style.configure("TFrame", background="#111827")
        style.configure("TLabel", background="#111827", foreground="#e5e7eb", font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 21, "bold"))
        style.configure("Card.TLabel", background="#1f2937", padding=12)
        style.configure("TButton", font=("Segoe UI", 10), padding=(12, 9),
                        background="#334155", foreground="#f1f5f9")
        style.map("TButton", background=[("active", "#475569")], foreground=[("disabled", "#94a3b8")])
        style.configure("TCheckbutton", background="#111827", foreground="#e5e7eb")
        content = ttk.Frame(window, padding=24)
        content.pack(fill="both", expand=True)
        ttk.Label(content, text="NMS Offline", style="Title.TLabel").pack(anchor="w")
        ttk.Label(content, text="Local research worker · Game can stay closed · Build " + VERSION).pack(anchor="w", pady=(4, 18))
        self.status = tk.StringVar(value="Ready to start")
        self.detail = tk.StringVar(value="Tests, evidence checks and GitHub uploads in one place.")
        ttk.Label(content, textvariable=self.status, font=("Segoe UI", 15, "bold")).pack(anchor="w")
        ttk.Label(content, textvariable=self.detail, wraplength=850).pack(anchor="w", pady=(6, 10))
        activity = ttk.Frame(content, height=6)
        activity.pack(fill="x", pady=(0, 14))
        activity.pack_propagate(False)
        self.progress = ttk.Progressbar(activity, mode="indeterminate")
        self.spinning = False
        cards = ttk.Frame(content)
        cards.pack(fill="x")
        self.result = tk.StringVar(value="Latest check: not run")
        self.upload = tk.StringVar(value="GitHub: checking setup")
        self.elapsed = tk.StringVar(value="Session: 00:00")
        for variable in (self.result, self.upload, self.elapsed):
            ttk.Label(cards, textvariable=variable, style="Card.TLabel").pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.action = tk.StringVar()
        if self.exe_selection_invalid:
            self.action.set("Saved NMS.exe is missing or changed. Select it again before exporting.")
        ttk.Label(content, textvariable=self.action, foreground="#fbbf24", wraplength=850).pack(anchor="w", pady=12)
        buttons = ttk.Frame(content)
        buttons.pack(fill="x")
        self.start_button = ttk.Button(buttons, text="Start", command=self.start)
        self.pause_button = ttk.Button(buttons, text="Pause", command=self.pause)
        self.stop_button = ttk.Button(buttons, text="Stop", command=self.stop)
        self.check_button = ttk.Button(buttons, text="Run check", command=self.check)
        self.retry_button = ttk.Button(buttons, text="Retry uploads", command=self.retry)
        for button in (self.start_button, self.pause_button, self.stop_button, self.check_button, self.retry_button):
            button.pack(side="left", padx=(0, 8))
        links = ttk.Frame(content)
        links.pack(fill="x", pady=12)
        self.setup_button = ttk.Button(links, text="Set up GitHub", command=self.setup_github)
        self.setup_button.pack(side="left", padx=(0, 8))
        ttk.Button(links, text="Open reports", command=lambda: self.open_folder(self.root / "reports")).pack(side="left", padx=(0, 8))
        ttk.Button(links, text="Select NMS.exe", command=self.select_exe).pack(side="left", padx=(0, 8))
        ttk.Button(links, text="Developer", command=self.debug).pack(side="right")
        self.logs_visible = tk.BooleanVar(value=False)
        self.summary = tk.StringVar(value="The first check will verify source, tests, captured evidence and Unicorn.")
        ttk.Label(content, textvariable=self.summary, style="Card.TLabel", wraplength=850).pack(fill="x", pady=(0, 12))
        ttk.Checkbutton(content, text="Show live activity", variable=self.logs_visible, command=self.toggle_logs).pack(anchor="w")
        self.log_frame = ttk.Frame(content)
        self.log = tk.Text(self.log_frame, height=9, bg="#0b1220", fg="#cbd5e1", font=("Consolas", 9),
                           relief="flat", wrap="word", state="disabled")
        scroll = ttk.Scrollbar(self.log_frame, command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        self.log.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        ttk.Label(content, text="Pause finishes the current job. Stop cancels owned work. Logs stay on this screen.",
                  foreground="#94a3b8", wraplength=850).pack(side="bottom", anchor="w", pady=(12, 0))
        window.protocol("WM_DELETE_WINDOW", self.close)
        window.after(100, self.poll)
        if autostart:
            window.after(250, self.start)

    def append(self, line):
        now = time.monotonic()
        stamp = datetime.now().astimezone().strftime("%H:%M:%S")
        elapsed = None
        if self.update_wait_started is not None:
            elapsed = int(now - self.update_wait_started)
        elif self.worker.started is not None:
            elapsed = int(now - self.worker.started)
        prefix = f"[{stamp}]"
        if elapsed is not None:
            prefix += " [+%02d:%02d]" % (elapsed // 60, elapsed % 60)
        self.log.configure(state="normal")
        self.log.insert("end", prefix + " " + line[:8192] + "\n")
        self.last_log_at = now
        lines = int(self.log.index("end-1c").split(".")[0])
        if lines > 500:
            self.log.delete("1.0", str(lines - 500) + ".0")
        self.log.see("end")
        self.log.configure(state="disabled")

    def launch(self, args, mode):
        if self.worker.active:
            return
        try:
            self.worker.start(args)
            self.last_log_at = time.monotonic()
            self.mode = mode
            self.status.set("Starting " + ("runner" if mode == "runner" else mode) + "…")
            self.action.set("")
        except (OSError, ValueError):
            self.action.set("Could not start. Check Python and folder permissions in RUNNER.md.")

    def start(self):
        if self.worker.active:
            return
        try:
            set_paused(self.root, False)
            self.pause_requested = False
            args = ["runner"]
            if self.executable:
                args += ["--exe", str(self.executable)]
            self.launch(args, "runner")
        except OSError:
            self.action.set("This folder is not writable. Extract the complete ZIP into a writable folder.")

    def pause(self):
        try:
            self.pause_requested = not self.pause_requested
            set_paused(self.root, self.pause_requested)
            self.action.set("Pause requested — finishing the current job first." if self.pause_requested else "Resuming…")
        except OSError:
            self.action.set("Could not save pause control. Check folder permissions.")

    def stop(self):
        self.worker.stop()
        self.status.set("Stopping — saving the result…")

    def check(self):
        try:
            from .local_runner import source_files
            request = publish_request(self.root, digest(source_files(self.root)),
                                      "offline-check-and-export" if self.executable else "offline-check")
            self.queued_id = request["request_id"]
            self.action.set("Check queued. Resume if the runner is paused.")
            if not self.worker.active:
                self.start()
        except FileExistsError:
            self.action.set("A check is already queued. Wait for it to finish.")
        except (OSError, ValueError):
            self.action.set("Could not queue a check. Verify the complete extraction and folder permissions.")

    def retry(self):
        self.launch(["github", "--retry"], "upload retry")

    def setup_github(self):
        try:
            if os.name == "nt":
                subprocess.Popen(["cmd.exe", "/c", str(self.root / "Setup-GitHub.cmd")], cwd=self.root,
                                 creationflags=subprocess.CREATE_NEW_CONSOLE)
                self.action.set("Complete GitHub setup in its window, then click Start here.")
            else:
                self.action.set("Use python start.py github --setup in a terminal, then Start here.")
        except OSError:
            self.action.set("Could not open setup. Run Setup-GitHub.cmd from this folder.")

    def select_exe(self):
        if self.worker.active:
            messagebox.showinfo("Stop first", "Stop the runner before changing the optional executable selection.")
            return
        path = filedialog.askopenfilename(title="Select NMS.exe for bounded read-only exports",
                                          filetypes=[("Executable", "*.exe")])
        if path:
            try:
                self.executable = save_executable_selection(self.root, path)
                self.action.set("NMS.exe path saved on this PC and locked to its current SHA-256.")
            except (OSError, ValueError):
                self.action.set("Could not save selection. Choose the actual NMS.exe file.")

    def open_folder(self, folder):
        try:
            folder.mkdir(parents=True, exist_ok=True)
            if os.name == "nt":
                os.startfile(folder)
            else:
                subprocess.Popen(["xdg-open", str(folder)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            self.action.set("Could not open the folder. Reports are in this experiment's reports folder.")

    def debug(self):
        panel = tk.Toplevel(self.window)
        panel.title("NMS Offline developer · " + VERSION)
        panel.geometry("780x470")
        text = tk.Text(panel, wrap="word")
        text.pack(fill="both", expand=True, padx=12, pady=12)
        state = {name: read_state(self.root, name) for name in ("status.json", "latest-result.json", "github-status.json")}
        text.insert("end", "Build " + VERSION + "\n\n" + json.dumps(state, indent=2))
        text.configure(state="disabled")
        ttk.Button(panel, text="Export complete source ZIP", command=self.export_source).pack(pady=(0, 12))

    def export_source(self):
        path = filedialog.asksaveasfilename(title="Export complete current source", defaultextension=".zip",
                                           initialfile="NMS-Derelict-Offline-v" + VERSION + ".zip")
        if path:
            try:
                from .package_experiment import package
                package(path)
                self.action.set("Complete source ZIP exported, including AI_HANDOFF.md.")
            except (OSError, ValueError):
                self.action.set("Could not export source. Choose a writable destination outside source files.")

    def toggle_logs(self):
        if self.logs_visible.get():
            self.log_frame.pack(fill="both", expand=True, pady=(8, 0))
        else:
            self.log_frame.pack_forget()

    def poll(self):
        self.worker.tick()
        for _ in range(100):
            try:
                self.append(self.worker.messages.get_nowait())
            except queue.Empty:
                break
        active = self.worker.active
        event = read_state(self.root, "status.json")
        last = read_state(self.root, "latest-result.json")
        upload = read_state(self.root, "github-status.json")
        self.result.set("Latest check: " + last.get("status", "not run").capitalize())
        if last.get("request_id") == self.queued_id and self.queued_id:
            self.queued_id = None
            if self.action.get().startswith("Check queued"):
                self.action.set("")
        if last.get("stages"):
            self.summary.set("Latest completed check\n" + "\n".join(
                STAGES.get(stage.get("stage"), "Check") + " · " + ("Passed" if stage.get("returncode") == 0 else "Failed")
                for stage in last["stages"]))
        configured = (self.root / ".local/github-config.json").is_file()
        self.upload.set("GitHub: " + (upload.get("status", "enabled") if configured else "off"))
        busy = False
        if active:
            if self.worker.stopping_since is not None:
                self.status.set("Stopping — saving the result…")
                busy = True
            elif self.mode == "runner":
                label, busy = display_status(event)
                self.status.set(label)
            else:
                self.status.set("Retrying GitHub uploads…")
                busy = True
        elif self.mode and self.worker.reader_done.is_set():
            code = self.worker.finish()
            if code == 75 and self.mode == "runner" and not self.closing:
                self.status.set("Applying verified update — restarting…")
                self.update_wait_version = read_state(self.root, "update-requested.json").get("version")
                self.update_wait_attempts = 0
                self.update_wait_started = time.monotonic()
                self.update_wait_last_log = 0
                self.action.set("Waiting for the installer to confirm the restart.")
                self.append("[update] Verified package handed to installer; restart wait started.")
                self.mode = None
                self.window.after(500, self.wait_for_update)
                self.window.after(150, self.poll)
                return
            cancelled = self.worker.stopping_since is not None and last.get("status") == "cancelled"
            self.status.set("Stopped — check cancelled" if cancelled else "Stopped" if code == 0 else "Stopped — needs attention")
            if cancelled:
                self.action.set("Cancelled check retained in reports.")
            elif code:
                self.action.set("Open live activity or Developer for the failed stage. Reports were retained.")
                self.logs_visible.set(True)
                self.toggle_logs()
            self.mode = None
        if event.get("status") in ("failed", "blocked", "rejected") and self.mode == "runner":
            self.action.set("Action needed: " + ", ".join(event.get("errors", ["review the failed stage"])))
        elif last.get("status") in ("failed", "stale"):
            self.action.set("Action needed: " + ", ".join(last.get("errors", ["review latest result"])))
        elif last.get("status") == "passed" and self.action.get().startswith("Action needed:"):
            self.action.set("")
        if upload.get("status") == "pending-or-blocked":
            self.action.set("Uploads need attention. Stop, then Retry uploads after checking sign-in/network.")
        if active and self.worker.stopping_since is None and upload.get("status") == "uploading":
            self.status.set("Uploading evidence to GitHub…")
            busy = True
        if self.update_wait_version:
            busy = True
        self.detail.set("Connected to the local worker" if active else "Local worker is stopped")
        if busy != self.spinning:
            if busy:
                self.progress.pack(fill="both", expand=True)
                self.progress.start(12)
            else:
                self.progress.stop()
                self.progress.pack_forget()
            self.spinning = busy
        if self.update_wait_started is not None and self.update_wait_version:
            elapsed = max(0, int(time.monotonic() - self.update_wait_started))
            idle = max(0, int(time.monotonic() - self.last_log_at))
            self.elapsed.set("Update wait: %02d:%02d · no log: %02d:%02d" %
                             (elapsed // 60, elapsed % 60, idle // 60, idle % 60))
            busy = True
            self.detail.set("Waiting for verified update " + str(self.update_wait_version) + " to restart")
        elif active and self.worker.started:
            elapsed = max(0, int(time.monotonic() - self.worker.started))
            idle = max(0, int(time.monotonic() - self.last_log_at))
            self.elapsed.set("Run: %02d:%02d · no log: %02d:%02d" %
                             (elapsed // 60, elapsed % 60, idle // 60, idle % 60))
        else:
            self.elapsed.set("Session: 00:00")
        waiting_update = self.update_wait_started is not None and bool(self.update_wait_version)
        self.start_button.configure(state="disabled" if active or waiting_update else "normal")
        self.stop_button.configure(state="normal" if active else "disabled")
        self.pause_button.configure(text="Resume" if self.pause_requested else "Pause",
                                    state="normal" if active and self.mode == "runner" else "disabled")
        self.retry_button.configure(state="normal" if not active and not waiting_update and configured else "disabled")
        self.setup_button.configure(state="disabled" if active or waiting_update else "normal")
        self.check_button.configure(state="normal" if not waiting_update and self.mode in (None, "runner") else "disabled")
        if self.closing and not active:
            self.worker.finish()
            self.window.destroy()
            return
        self.window.after(150, self.poll)

    def wait_for_update(self):
        if self.closing or not self.update_wait_version:
            return
        elapsed = max(0, int(time.monotonic() - (self.update_wait_started or time.monotonic())))
        state = read_state(self.root, "update-state.json")
        if state.get("status") == "applied" and state.get("version") == self.update_wait_version:
            self.append("[update] Installer confirmed version " + str(self.update_wait_version) +
                        " after %02d:%02d; restarting runner." % (elapsed // 60, elapsed % 60))
            self.update_wait_version = None
            self.update_wait_started = None
            self.start()
            return
        if state.get("status") == "failed":
            self.append("[update] Installer failed after %02d:%02d; status=%s." %
                        (elapsed // 60, elapsed % 60, str(state.get("error", "failed"))))
            self.update_wait_version = None
            self.update_wait_started = None
            self.status.set("Update failed after %02d:%02d" % (elapsed // 60, elapsed % 60))
            self.action.set("Update step: " + str(state.get("error", "review update state")))
            return
        phase = state.get("phase", "not-reported")
        heartbeat_age = None
        updated_at = state.get("updated_at")
        if isinstance(updated_at, str):
            try:
                stamp = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                heartbeat_age = max(0, int((datetime.now().astimezone() - stamp.astimezone()).total_seconds()))
            except ValueError:
                pass
        self.update_wait_attempts += 1
        if elapsed - self.update_wait_last_log >= 10:
            self.update_wait_last_log = elapsed
            line = "[update] Waiting for installer; elapsed %02d:%02d; state=%s; phase=%s" % (
                elapsed // 60, elapsed % 60, str(state.get("status", "unknown")), str(phase))
            if isinstance(state.get("elapsed_seconds"), int):
                line += "; installer elapsed %ds" % state["elapsed_seconds"]
            if heartbeat_age is not None:
                line += "; last installer update %ds ago" % heartbeat_age
            self.append(line + ".")
        if heartbeat_age is not None and heartbeat_age >= 30:
            self.status.set("Installer stopped reporting — update may be stuck")
            self.action.set("See .local/update-installer.log. Keep the runner closed until the update reports applied or failed.")
        elif elapsed >= 60:
            self.status.set("Update taking longer than expected — waiting %02d:%02d" %
                            (elapsed // 60, elapsed % 60))
            self.action.set("Installer phase: " + str(phase) + ". The timer is still running.")
        else:
            self.status.set("Applying verified update — " + str(phase) + " — waiting %02d:%02d" %
                            (elapsed // 60, elapsed % 60))
        self.window.after(500, self.wait_for_update)

    def close(self):
        self.closing = True
        self.stop()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-autostart", action="store_true")
    args = parser.parse_args(argv)
    try:
        window = tk.Tk()
    except tk.TclError:
        print("Could not open the desktop window. Use Start-Runner-CLI.cmd, or install Python with Tcl/Tk enabled.", flush=True)
        return 2
    RunnerWindow(window, autostart=not args.no_autostart)
    window.mainloop()
    return 0
