# AI handoff — NMS Derelict Probe v0.3.29

UI/update hotfix. The user clarified that “restart” meant the Surveyor/pyMHF interface, not No Man’s Sky. v0.3.27/0.3.28 incorrectly closed NMS.

Changes:
- Check update emits explicit installed/remote version status.
- Install update emits exact installed version and stages `mod/derelict_baseline_probe.py` to the recorded live MODS copy when possible.
- Running mod and launchers persist `%LOCALAPPDATA%\NMSDerelictSurveyor\installed-mod-file.txt`.
- GUI button renamed **Reload Surveyor GUI**. It syncs source -> loaded mod file, saves the current session, then invokes pyMHF `mod_manager.reload(...)` and `_assign_mod_instances(...)` in-process. NMS remains running.
- New instance consumes `gui-actions/reload-status.json` and reports that Surveyor reloaded while NMS stayed open.
- Legacy `Restart-Surveyor.ps1` no longer closes NMS; it is only a migration bridge for users still running the old v0.3.28 button.

Migration from v0.3.28: install v0.3.29. Because the currently loaded v0.3.28 button code is old, click its old **Restart Surveyor** button once; the updated compatibility helper now only stages the v0.3.29 mod and will not close NMS. Then click pyMHF’s built-in **Reload Mod** once. After v0.3.29 is loaded, use **Reload Surveyor GUI** for future updates.

Research state unchanged.