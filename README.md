# NMS Derelict Probe

Read-only No Man's Sky derelict-freighter generation research/modding toolkit.

Current stable package: **v0.3.23**.

## v0.3.23 hotfix

v0.3.22 launched GUI GitHub/update/upload helpers with Python's `sys.executable`. Inside the injected pyMHF process that value can be the host game executable (`NMS.exe`), which is why **Set up GitHub uploads** and **Install Surveyor update** could start another No Man's Sky instance.

v0.3.23 fixes the complete helper path:

- launchers persist the verified external Python 3.12/3.13 executable in `%LOCALAPPDATA%\NMSDerelictSurveyor\python-executable.txt`;
- GitHub setup, update checks/installs, and every research `+ upload` action use that interpreter;
- only executables whose basename starts with `python` are accepted;
- non-Python hosts such as `NMS.exe` are refused rather than launched.

Because the updater button itself is affected in v0.3.22, **v0.3.23 must be installed manually once**. From v0.3.23 onward, the GUI updater can be used normally.

## GitHub workflow

After v0.3.23 is installed, the pyMHF companion GUI can:

- **Set up GitHub uploads** once using GitHub CLI's credential store;
- **Measure derelict generation + upload**;
- **Extract dungeon caller code + upload**;
- run the existing Prepare / Analyze workflows in the background;
- **Check for Surveyor update** and **Install Surveyor update**.

Successful research actions commit only the expected generated evidence plus a SHA-256/size run manifest under `research-uploads/<UTC>-<action>/`.

The active updater package is the SHA-256-verified three-part delta under `packages/v0.3.23-delta/`.
