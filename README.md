# NMS Derelict Probe

Current stable package: **v0.3.29**.

## v0.3.29 UI/update fixes

- **Check for Surveyor update** now shows both installed and available version numbers.
- **Install Surveyor update** now reports the exact installed version.
- Updates stage the refreshed probe into the live NMS `GAMEDATA\MODS` copy when its path is known.
- The old game-restart behavior is removed. The normal button is now **Reload Surveyor GUI** and uses pyMHF live mod reload; **NMS stays open**.
- Launchers and the running mod persist the installed probe path for future one-click update/reload cycles.
- `Restart-Surveyor.ps1` remains only as a v0.3.28 compatibility bridge: it stages the updated mod file and never closes NMS.

pyMHF supports reloading a mod in-process, so future Surveyor code/UI updates do not require restarting No Man's Sky.

Current research target remains the deterministic address -> dungeon-root seed derivation.