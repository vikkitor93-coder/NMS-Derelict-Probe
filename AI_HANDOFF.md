# AI handoff — NMS Derelict Probe v0.3.23

Critical regression fixed: v0.3.22 used `sys.executable` for helper subprocesses from inside injected pyMHF. On the user's machine that resolves to `NMS.exe`, so GUI setup/update buttons started another game instance. v0.3.23 persists the external Python interpreter path from the launcher and refuses any non-Python host executable.

This applies to **Set up GitHub uploads**, **Check for Surveyor update**, **Install Surveyor update**, and all research `+ upload` buttons. If no safe Python interpreter is available, the GUI reports an error and launches nothing.

Verification: 79/79 tests pass; Python compileall and ZIP integrity pass.

Migration: v0.3.22 users must install v0.3.23 manually once because the v0.3.22 updater button is itself affected. After v0.3.23, GitHub self-update is the intended path.

Research state remains unchanged: address `00001A0004E84EFD` -> root seed `9256392A2F5A74AC`; next evidence target is offline caller code around RVA `0x00635110`.

Next action after installing v0.3.23: click **Set up GitHub uploads**. It should open GitHub authentication if needed and must not launch NMS. Then use **Extract dungeon caller code + upload** and tell ChatGPT `check`.
