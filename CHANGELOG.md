# 0.3.61 — METADATA-D asset preparation repair

- Give MBINCompiler an explicit MBIN input format and overwrite consent when the persistent asset directory also contains generated MXML files.
- METADATA-D preparation and upload completed on Windows after the repair; the user confirmed visual refresh and rollback. No extension API or NMS process behavior changed.
- Publish the current abandoned-freighter entrance's ten static weighted dungeon choices and matching table presets as research evidence. Runtime selection semantics remain open.

# 0.3.60 — paced recovery uploads

- Keep root-event uploads prompt, then batch changed capture-journal and session evidence every 30 seconds while automatic uploads are enabled. This continues after a valid `+0x10` capture has already been uploaded.
- Retain the existing auto-upload toggle and `--only-if-changed` deduplication.
- Tests: 184 passed; compileall passed. Live Windows/NMS validation remains required.

# 0.3.59 — crash-safe event journal and root-event recovery

- Flush every trace event to a per-process JSONL journal immediately, including events observed before a recording session starts; fsync root events and other records in bounded batches.
- Atomically save the dungeon root event, seed, and universe-address metadata even when exact caller correlation or the `+0x10` slot capture is still pending. Keep pending root evidence separate from the exact-slot capture.
- Add root events and capture journals to Upload all saved evidence.
- Keep the 5-second session snapshot and flush/fsync atomic JSON writes before replacement.
- Tests: 184 passed; compileall passed.

# 0.3.53 — upload all saved evidence

- Add main-window **Upload all saved evidence**. It collects the unique existing outputs declared by research actions, uploads one shared snapshot to `main`, and records that shared upload path on all four Agent Console lane cards.
- Include an upload manifest with producer actions and lane visibility. Uploading does not write agent status branches or send agents a live notification.
- Add Runtime-A **Upload captured root event** so the atomically persisted exact root event can be uploaded after NMS closes.
- Shared local latest outputs can be replaced by subsequent runs: baseline (measure/analyze-generation), measurement summary/CSV (measure/compare-measurements), room correlation (measure/analyze-correlation), and exact root caller (analyze-generation/Runtime-A upload). Timestamped GitHub snapshots remain separate.
- Tests: updated for saved capture readiness and all-evidence path deduplication.

# 0.3.52 — constrain local mod staging

- Restrict install and update staging to the three expected EXML files; validate file types, sizes, and XML before copying anything into the game folder.
- Read ZIP member contents with a fixed size limit and reject duplicates or incomplete archives.
- No mod assets are redistributed. Keep 7.04-to-7.05 behavior pending the user's live NMS check.
- Tests: 175 passed; compileall passed.

# 0.3.51 — local DerelictFreighterFarming installer

- Add a Surveyor button to select and install the user's own DerelictFreighterFarming ZIP. No third-party mod assets are included in the app package.
- Validate only the three expected EXML paths and XML contents; do not extract arbitrary paths from the archive.
- Preserve conflicting files with backups and keep targeted rollback. The mod author requires permission before reusing the files in another mod.
- The published archive targets 7.04; live behavior on NMS 7.05 still needs testing.
- The prior 0.3.50 package was withdrawn from the current updater after identifying the author's no-reuse-without-permission condition.

# 0.3.49 — Runtime-A owner+0x10 capture

- Bump the embedded probe to 0.3.34 and read the raw 8-byte owner+0x10 slot once, only after exact descriptor correlation at the dungeon root event.
- Persist the raw slot and best-effort loaded-module identity to root evidence and live status; display the result in the existing root-dispatch row/objective.
- Keep the current data-only Runtime-A extension and all other Surveyor behavior intact. The app updater stages the probe; restart NMS to load it.
- Live Windows/NMS validation remains pending.

# 0.3.48 — transparent objective overlay

- Move all overlay visibility toggles to the main Surveyor window.
- Add opacity and horizontal/vertical positioning sliders with live application.
- Display all published agent objectives in the game overlay with root-detected, complete, and waiting-for-upload states.
- Require an explicit Root dispatch +0x10 capture signal before completing that objective.

# 0.3.47 — expose root evidence and control overlay

- Show the exact dungeon root resource path and live observed-event count in the main Surveyor and game overlay.
- Show `Root dispatch +0x10` as a separate status. It explicitly reports that the current standard probe does not capture this Runtime-A event; an exact-root-caller match is not presented as proof.
- Add **Start overlay** and **Stop overlay** beside the existing overlay auto-start toggle. Stop targets the Surveyor overlay window and also signals the overlay process through a local stop-request file, including overlays launched automatically with NMS.
- Preserve the existing NMS launch toggle behavior and keep overlay start/stop independent from NMS process control.

# 0.3.46 — visible prerequisites and collapsible sections

- Restore exact extension prerequisite keys in the fixed NEEDED box, including current missing keys; remove generic “follow the steps above” text there. Keep the existing host contract key `probe.connected` (it means the probe heartbeat is connected).
- Add small top-right +/− controls to all major main-window sections, each Agent Console card, and the fixed lane/global action groups in Agent Console. Lane and bulk buttons remain pinned in their fixed bottom areas.
- Reuse the main window’s latest NMS/probe status when updating extension button readiness, avoiding repeated process checks during a status refresh.

# 0.3.45 — responsive Agent Console and configurable refresh

- Keep the published NEEDED request, actual action label, and extension versions in separate static card areas; place each evidence-upload confirmation beneath its lane buttons.
- Add a collapsible Options panel with plus/minus visibility toggles for lane, extension, and receipt details. Persist these choices locally.
- Set the automatic status/extension refresh interval to one minute by default, with 20 seconds, 2 minutes, 5 minutes, and Off choices; manual refresh remains available.
- Cache rendered extension panels and update their enabled state in place, avoiding destroy/recreate redraws on every poll that caused scroll artifacts.

# 0.3.44 — clearer Agent Console status and actions

- Keep each published Surveyor action and installed/published extension versions in fixed card footers above the lane buttons.
- Request-only actions stay clickable while Surveyor is idle; the action handler explains or starts required NMS/probe prerequisites. Upload receipts are display-only and never gate actions.
- Hide lane scrollbars when content fits and ignore wheel events when a panel cannot scroll or is at a scroll boundary.
- Refresh lane status every 20 seconds with cache-busting; display lane progress, blockers, update time, and agent-reported extension version.
- Extend the backward-compatible status v1 schema and agent guidance for more frequent status publishing.
- Include the latest extensions published on main: DUNGEON-C 1.0.2, Metadata-D 1.0.1, Runtime-A 1.0.1, and Seed-B 1.0.2.

# 0.3.43 — Agent Console scroll and bulk upload

- Move extension version and evidence-upload confirmation to the top of every lane panel.
- Support mouse-wheel scrolling over app content, lane panels, and workflow output.
- Add a confirmed Upload all action that runs eligible lane workflows sequentially.

# 0.3.42 — four-lane Agent Console

- Show all four agents side by side with an independent scrollbar in each information panel.
- Keep copy steps, lane research actions, and extension update controls in the fixed bottom strip.
- Check all lane extensions from the top control, then update all available extensions or update a single lane.
- Show evidence upload receipts per lane and retain extension rollback controls.

# 0.3.41 — shared lane UI extensions

- Added the versioned Surveyor UI extension guide and a reusable prompt for all four research lanes.
- Added a data-only extension loader with API/version/dependency checks, SHA-256 verification, staged activation, update notice, live panel refresh, and rollback.
- Added the DUNGEON-C sample panel using the existing offline exact-root-caller action.
- Added lane-specific, collision-safe upload folders and local action records for extension-launched research actions.
- Preserved the controller/probe command protocol and kept all existing Surveyor actions intact.

## 0.3.40
- Show each research command, its current step, progress, latest output line, and exit status in Surveyor while it runs.
- Add a scrollable output pane and stream combined command output without blocking the UI; keep the complete workflow log and diagnostic.
- Keep individual research commands and upload steps separate. No probe protocol or game behavior changes.

## 0.3.39
- Added a compact Agent Console that opens with standalone Surveyor and refreshes agent lane status every 60 seconds.
- Shows published lane status, the exact Surveyor request, numbered user steps, evidence to return, and whether a full derelict traversal is required.
- Adds copyable Surveyor steps and a copyable status summary for relaying updates in chat.
- Reads the main `WORKSPACE_STATE.json` plus lane branch status/manifest files over public read-only HTTPS; no game, probe, or controller-command protocol changes.
- Adds `schema/agent-status-v1.schema.json` and requires each agent lane to publish `agent-patches/<lane>/STATUS.json` on its branch.
- Warns when the main registry is stale and retains the last successful status view if refresh fails.

## 0.3.38
- Added offline `Resolve root vtable + upload`.
- Uses the confirmed `02BFCC17: FF 52 10` virtual call to resolve vtable `+0x10` entries pointing to `00634BC0`.
- Captures neighbouring virtual methods, best-effort MSVC RTTI/class metadata, and RIP-relative code references.
- No NMS launch or runtime hook is required.

## 0.3.38
- Added offline **Extract exact root caller + upload** workflow for the runtime-correlated derelict caller.
- Reads `exact-root-caller-latest.json`, maps the exact return RVA into installed `NMS.exe`, captures a bounded static code window, and conservatively decodes direct `E8` or indirect `FF /2` calls.
- Records nearby compiler-padding candidates as heuristic evidence without claiming symbols or function names.
- No extra NMS run is required after an exact caller has already been captured.

# Changelog

## v0.3.36 — classic launcher quoting + TOML repair

- Fix `Start-NMS*.cmd` so a trailing project-root backslash cannot swallow `-OverlayMode`.
- Harden `Start-NMS.ps1` to fall back to its own folder if ProjectRoot arrives malformed.
- Write `%APPDATA%\pymhf\nmspy\pymhf.local.toml` as UTF-8 **without BOM**; this fixes tomlkit `EmptyKeyError` at line 1 col 0.
- Restore NMSpy's packaged Steam launch settings instead of overriding `exe` in the local config.
- Research probe/all-52 caller logic unchanged.


## v0.3.36 — restore classic console-backed NMS launch
- Fixes the standalone Start NMS regression where pyMHF was imported from a hidden/captured process and prompt_toolkit raised `NoConsoleScreenBufferError`.
- Removes the background `import pymhf` runtime preflight and unnecessary Python 3.12/winget fallback.
- Verifies installed package metadata without importing pyMHF.
- Launches the proven `pymhf.exe run nmspy` flow inside a fresh visible `cmd.exe`, matching the old working UI's console environment.
- Surveyor remains a separate standalone process and stays open when NMS closes.
- Existing all-52 caller correlation logic is unchanged.

# v0.3.34

- Repaired the standalone **Start NMS** path. The launcher now validates the real Python import traceback instead of hiding it, repairs a damaged NMSpy/pyMHF install when needed, falls back to Python 3.12 if the current 3.13 runtime remains unusable, and can install Python 3.12 through winget as a last resort.
- Uses `python -m pymhf run nmspy` directly instead of a potentially stale `pymhf.exe` shim.
- Writes the pyMHF local NMS/MODS configuration automatically, so Start NMS remains one-click.
- Added `Start-NMS-With-Overlay.cmd`; recording still works in no-overlay mode.
- Runtime failures are preserved in `%LOCALAPPDATA%\NMSDerelictSurveyor\runtime-repair-latest.log`.

# Changelog

## 0.3.34

- Make the 52-caller runtime test explicitly all-at-once through the single verified `0x00634BC0` hook.
- Track unique caller RVAs and hit counts while NMS runs.
- Classify the verified `0x00634C63` return as the self-recursive edge and exclude it from exact external-caller selection.
- Correlate the derelict root by exact descriptor pointer and record `logical_entry_exact_external_caller_return_offset_hex`.
- Persist `exact-root-caller-latest.json` immediately when the root caller is identified.
- Standalone Surveyor now shows **Caller scan** progress and **Exact root caller** separately.
- `Analyze generation + upload` now includes the dedicated exact-caller evidence file when present.
- Preserve read-only behavior; no game-state writes and no global RNG hooks.

## 0.3.32

- Added a narrow read-only runtime hook for the verified `0x00634BC0` logical resource-walk entry.
- Correlates that invocation to the later derelict-root `Engine::AddResource` event by exact descriptor pointer.
- Records the nearest logical-entry caller offset and a small code window only when the root descriptor matches.
- Keeps recent generic-entry events in memory only; no global RNG hooks and no game-state writes.
- Standalone Surveyor now shows `Root entry caller` when captured.
- Baseline analysis exports `dungeon_logical_entry_caller_offsets` and nearest caller evidence.


## 0.3.31
- Correct static-analysis boundary regression: root `.pdata` entry `0x0063505C..0x0063553E` is a runtime fragment, not the logical C++ function start.
- Recover logical entry `0x00634BC0` from four-byte `INT3` padding plus validated x64 prologue.
- Lower padding threshold from 6 to 4 **only when** the expected prologue shape validates, preventing selection of previous helper `0x006345B0`.
- Correct **Extract upstream callers + upload** to scan xrefs to `0x00634BC0`.
- Correct **Analyze seed function + upload** to distinguish logical entry from root runtime fragment and scan the entry-to-root prefix for seed references/writes.
- Preserve standalone Surveyor and read-only probe.
- Verification: 100/100 tests pass before packaging.

## 0.3.30
- Move the primary Surveyor interface into a standalone Tk controller that stays open independently of NMS.
- Add **Start NMS** button; NMS launch is now explicitly user-triggered from Surveyor.
- Add **Restart Surveyor** that restarts only the standalone controller and never touches NMS.
- Make the injected probe headless (`@no_gui`) and keep it as the read-only runtime backend.
- Add local controller -> probe command IPC for force-start, stop/save, undo marker and diagnostic snapshot.
- Keep live NMS/probe status, exact update versions, GitHub workflows and research uploads in the standalone controller.
- Add `Start-Surveyor.cmd/.ps1`, `Start-NMS.ps1/.cmd`; backwards-compatible `Start-Derelict-Probe.cmd` opens Surveyor only.
- Default the optional game overlay OFF.
- Fix v0.3.29 updater staging bug caused by undefined `SURVEYOR_ROOT`.
- Quick NMS launch no longer performs `pip --upgrade nmspy` every time; runtime install occurs only when missing.

## 0.3.29
- Show explicit installed/available versions for update checks.
- Show exact installed version after update installation.
- Stage updated probe into the live MODS copy.
- Replace game restart with in-process **Reload Surveyor GUI** using pyMHF live mod reload.
- Keep NMS running during Surveyor reload.
- Repurpose legacy Restart-Surveyor.ps1 as a safe v0.3.28 migration bridge only.


## 0.3.28
- Added offline PE `.pdata` validation of the root-call containing function.
- Added descriptor/seed/use-seed field reference and conservative direct-write scanning.
- Added direct xref internal/external classification.
- Added non-text function-pointer scanning and best-effort MSVC x64 RTTI recovery.
- Added **Analyze seed function + upload** GUI workflow and GitHub evidence type.
- Corrected research interpretation: the only direct xref found by v0.3.26 is an internal recursive call; do not yet assume seed construction is in a different function.

## 0.3.27
- Added **Restart Surveyor** to the pyMHF companion interface.
- Added detached `Restart-Surveyor.ps1` helper: request clean NMS window close, wait up to 30 seconds, then relaunch only after the old process has exited.
- Restart never force-kills NMS; failed/timeout restarts stop safely and write `gui-actions/restart-latest.log`.
- Persist last launch mode (`overlay` / `no-overlay`) from both start scripts so restart preserves the user's overlay preference.
- Save an active research session before handing off to the restart helper.
- Corrected stale launcher banners to v0.3.27.
- Verification: 91/91 tests pass; Python compileall passes; all packaged JSON parses.

## 0.3.26
- Analyzed the uploaded 20 KiB static caller window and identified a compiler-padded containing-function candidate at RVA `0x00634BC0`.
- Confirmed byte-level descriptor flow: second argument -> `RSI`; descriptor at `RSI+0x128`; primary seed read at `RSI+0x138`; seed-use flag checked at `RSI+0x140`; root `Engine::AddResource` call at `0x00635110`.
- Added `tools/extract_nms_upstream_callers.py` and `Extract-Dungeon-Upstream-Callers.cmd`.
- New offline scanner finds direct `E8 rel32` calls and `E9 rel32` tail-jumps in installed `NMS.exe` that target the containing function and captures bounded code windows around each candidate xref.
- Added GUI **Extract upstream callers + upload** and GitHub upload action `extract-upstream`.
- Kept the runtime probe read-only; no additional NMS run is required for this step.
- Verification: 88/88 tests pass; Python compileall passes; all packaged JSON parses.

## 0.3.25
- Fix GUI research/upload actions failing before GitHub with a quoted `cmd.exe /s /c` chain.
- Run research generation and GitHub upload as two explicit subprocess steps; upload occurs only after research succeeds.
- Launch PowerShell research scripts directly and caller extraction directly through the persisted Python interpreter.
- Keep normal GUI actions hidden/background; no empty CMD window for Measure/Prepare/Analyze/Extract + upload.
- Add per-step workflow events and diagnostics (`workflow_step_started`, `workflow_step_completed`, `workflow_step_failed`).
- Replace one clipped long workflow detail row with three short `Workflow message` rows because pyMHF STRING rows do not wrap.
- Preserve v0.3.24 GitHub diagnostics and v0.3.23 real-Python-only helper safety.

## v0.3.24
- Added persistent combined workflow logging plus per-action and timestamped GUI-action logs.
- Mirror workflow start/success/failure/exception events into the normal `latest.log`.
- Added `workflow-diagnostic-latest.txt` with return code, sanitized command, stdout/stderr and exception details.
- Added a dedicated `github-integration.log` covering CLI discovery, auth state, API stages and upload-file discovery without logging credentials.
- Added **Open workflow log**, **Open workflow diagnostic**, and **Run GitHub diagnostic** GUI buttons.
- Kept GUI status/detail messages short so pyMHF's non-wrapping fields remain readable.
- GitHub web authentication now opens a visible Windows console so the device-code prompt is not hidden.
- Verification: 82/82 unit tests, compileall, JSON parse, helper failure/diagnostic smoke tests.

## v0.3.23
- Fixed pyMHF GUI helper actions launching a second `NMS.exe` because injected `sys.executable` referred to the host game process.
- Persist the real Python interpreter path during both normal and NoOverlay launch.
- GitHub setup, update, and research-upload helpers now accept only a real Python executable and fail closed otherwise.
- Added regression guards against direct `sys.executable` helper launching.


## v0.3.22
- Added background pyMHF GUI buttons for the existing Measure / Extract / Prepare / Analyze research workflows.
- Added one-time GitHub CLI upload setup; credentials remain in GitHub CLI's store and the project does not persist a PAT/password.
- Successful GUI research actions can atomically upload expected JSON/CSV evidence plus a SHA-256/size run manifest under `research-uploads/<UTC>-<action>/`.
- Added GitHub update check/install using a public manifest and SHA-256-verified base64 package chunks; updates modify only the extracted source project and require restart.
- Launchers persist the source project root locally so the installed pyMHF mod can invoke/update the extracted project.
- GUI-launched CMD/PowerShell workflows suppress `pause` and Explorer popups while double-click behavior stays unchanged.
- Removed duplicated live telemetry from the pyMHF GUI; the safe overlay remains the live room/crate/research display.
- Regression suite: 77 tests.

## 0.3.20 — offline caller-code extraction

- The v0.3.19 short run proved a full derelict traversal is unnecessary for caller research: root seed/caller evidence was captured with zero streamed dungeon rooms.
- Decodes the captured outer `E8 rel32` call: call RVA `0x00635110` -> target RVA `0x01831A10`; recognizes `mov [rsp+0x20], rdi` as the unchanged descriptor argument pass-through.
- Adds `Extract-Dungeon-Caller-Code.cmd` + `tools/extract_nms_caller_code.py`, which read a larger code window directly from the installed `NMS.exe` using PE RVA-to-file-offset mapping. NMS does not need to be launched.
- The offline JSON stores only build/code evidence, not the full executable path, username, machine name, or network information.
- Archives the v0.3.19 short caller capture as `corpus/research/baseline-002-short-generation-v0.3.19-caller.json`.
- Existing runtime probe, room/container companion UI, and read-only behavior remain unchanged.
- Verification: 70/70 unittest regressions pass; Python compileall passes; all 35 packaged JSON files parse.

## 0.3.19 — dungeon caller call-site capture

- Confirmed from the v0.3.18 live fixture that target POI `Prepare`, `OnActivate`, and `AdvanceLifecycle` did not bracket dungeon-root creation.
- Preserved the v0.3.18 35-container resource-boundary result in `corpus/research/baseline-002-repeat-generation-v0.3.18-resource-boundary.json`.
- Added pyMHF `get_caller` instrumentation to the dungeon-root `Engine.AddResource` and `cTkResourceManager.AddResource` boundaries.
- Added a small read-only executable-code window around the outer caller return address using Windows `ReadProcessMemory`; failed reads degrade to `null`.
- Analyzer now exposes outer/inner dungeon-root caller offsets while retaining every existing field.
- Measurement summaries retain the new caller offsets for future cross-run comparison.
- Existing room/container UI and all read-only behavior are unchanged.

## 0.3.18 — target activation/lifecycle boundary
- v0.3.17 evidence confirmed `GeneratePoiDescription` returns the POI component address, not the universe address or dungeon-root seed; target `Prepare` produced zero events.
- Added target-only `OnActivate.before/after` bracketing and sparse `AdvanceLifecycle.before/after` instrumentation. Lifecycle after-events are emitted only for the first call, component snapshot changes, or a call that synchronously adds the dungeon root.
- `Engine.AddResource` now tags active activation/lifecycle scopes and records the descriptor pointer.
- Added a dungeon-root-only `cTkResourceManager.AddResource.before` observation to compare the inner descriptor/seed boundary without tracing unrelated resources.
- Extended `poi_generation_trace` and generation-measurement rows with activation/lifecycle/root-manager evidence.
- Archived the verified v0.3.17 35-container POI-boundary result as a regression fixture.

## 0.3.17 — narrow POI derivation instrumentation
- Added read-only `GeneratePoiDescription.after` capture for the function's 64-bit return value; the existing input is already proven to be the universe address.
- Added target-POI `Prepare.before` / `Prepare.after` lifecycle capture and bounded synchronous Prepare-scope tagging on resource additions.
- Added `poi_generation_trace` analysis: return candidates, universe-address/root-seed equality checks, Prepare events, and whether `DUNGEON.SCENE.MBIN` was added inside Prepare.
- Added live `POI-RET` research display without changing the default room-loot UI.
- Preserved the returned 58-event v0.3.16 context baseline as a regression fixture and kept all existing contracts.
- Verification: 64/64 offline regression tests pass; Python compile and all shipped JSON parse checks pass.

## 0.3.16 — reanalyze existing raw trace for wider POI seed context

- Preserves the existing dungeon-only `resource_seed_lineage` contract.
- Adds `resource_seed_context_lineage`, which surfaces every non-zero seed-bearing `resource_add`/`resource_find` event already captured by the probe, including derelict/POI resources outside `/DUNGEON/`.
- This is analysis-first: a v0.3.14/v0.3.15 raw `latest.json` can be reanalyzed without launching NMS.
- Compact generation measurements retain the wider context signature/seed list in new backward-compatible fields.
- Fixes comparison-set seeding to reference research fixtures that actually exist in the package.
- Adds the verified v0.3.15 reanalysis of the repeat 35-container session to the research corpus.

## 0.3.15 — room-loot companion view + diagnostic toggles

- Promotes the already-validated scene→container index into the live companion: streamed `Room N` groups now expose Salvage Crate, Crew Footlocker and combined target counts while recording.
- Companion defaults to a human-readable loot view (`LOOT SEEN`, per-room totals/type) instead of RAW/resource/seed telemetry.
- Adds persistent companion checkboxes: **Rooms**, **Research**, **Position**, **Manual**, and **Hotkeys**. Research/position/manual/hotkeys default off; no diagnostics were removed.
- Keeps the safe opaque/non-layered window path; no Tk alpha or `WS_EX_LAYERED` regression.
- Preserves the final room-loot summary after leaving the derelict until the next recording begins.
- Archives the user’s second 35-container repeat: 31 Salvage + 4 Footlockers = 35, identical room multiset and the same `9256392A2F5A74AC` dungeon-root descriptor seed.
- Generation baselines now stamp `analysis_tool_version` independently of `probe_version`, making old Measure/Analyze script usage visible.
- Regression suite: 58/58 tests passing; Python compilation and JSON-schema parsing also pass.

## 0.3.14 — seed-lineage instrumentation

- Archived today’s returned 51-repeat reanalysis and the new verified 35-container v0.3.13 measurement; the 35 result is: address `00001A0004E84EFD`, 35 targets, exact prior Room-N multiset, dungeon-root descriptor seed `9256392A2F5A74AC`.
- Cross-address evidence now rejects the idea that the dungeon-root descriptor seed is a single global `DUNGEON.SCENE.MBIN` constant: the 51-container address uses `00C9E8DF0327789E`.
- Added monotonic `trace_sequence` values to seed/resource trace events so callback ordering survives tied UTC timestamps.
- Generation baselines now emit `resource_seed_lineage` with ordered non-zero descriptor-seed events, unique seed lists, and an ordered SHA-256 signature.
- Accumulated measurement/correlation outputs retain the lineage signature for repeat-address stability checks.
- No game-state mutation, crate-count logic, room classification, overlay rendering mode, or existing schema contract was removed.

## 0.3.13 — dungeon-root seed candidate instrumentation

- Promoted the primary descriptor seed on `MODELS/SPACE/POI/DUNGEON.SCENE.MBIN` into an explicit **dungeon-root seed candidate**.
- Added 30-minute dedicated retention for dungeon-root seed events, tagged with the universe address available at capture time.
- Live overlay now displays `DUNGEON-SEED` when available.
- Generation baselines, accumulated CSV/JSON measurements, and seed/room correlation reports now include dungeon-root seed candidates.
- Fixed v0.3.12 POI-context contamination: buffered POI address events from a previous system are discarded when they do not match the current session UA, and the discarded count remains diagnostic.
- Added the verified v0.3.12 51-container repeat as a regression fixture. It confirms 9 indexed rooms (7 main + 2 dead ends), 32+19=51, and the same room-assembly multiset as the earlier 51 capture.
- Added `Reanalyze-Latest-Generation.cmd` so existing v0.3.12 captures can be reprocessed offline for the new seed candidate.
- The candidate remains unverified; no code assumes it is the actual layout RNG seed.

## 0.3.12 — stable room-index fingerprint + seed-correlation diagnostics

- Corrected the experimental POI hook interpretation: on the verified 35-container repeat, the captured uint64 exactly equals the universe address (`00001A0004E84EFD`), so it is now reported as POI context / system address rather than a layout-seed candidate.
- Captures `space_poi_id` when safely readable from the documented NMS.py structure.
- Parses game-assigned parent labels (`Room N`) into `room_index`/`room_label`.
- Adds stable `layout_signature_sha256` ordered by `Room N`; retains `legacy_stream_signature_sha256` because threaded scene-stream order is not deterministic.
- Adds `canonical_room_sequence` and parent-index coverage to generation baselines.
- Adds `Analyze-Seed-Room-Correlation.cmd`/`.ps1` and `tools/analyze_seed_room_correlation.py`.
- Adds the verified 35-container repeat as a regression research fixture; it has the same logical room multiset as the prior run despite a different stream order.

## 0.3.11 — seed/room-selection measurement toolkit

- Confirmed the room model on two independent verified `CARGO_FLOATERS` layouts: 51-container baseline = 7 main + 2 dead ends; 35-container baseline = 7 main + 1 dead end.
- Added conservative automatic dead-end classification that ignores `EMPTY/ROOM_DEADEND_R_*` pieces embedded inside full normal rooms and counts compact family-level `DEADEND_*` groups.
- Generation baselines now record generation order, first/last seen time, parent-node names, room kind, dead-end evidence, room-model validation, and a deterministic generation-signature SHA-256.
- Added experimental read-only `cGcSpacePoiSiteComponent.GeneratePoiDescription.before` capture for abandoned-freighter/derelict POIs. The raw 64-bit argument is stored only as `layout-seed-candidate-unverified`.
- Added a dedicated 30-minute pre-entry retention buffer for POI seed candidates.
- Overlay now shows `GEN ROOMS / MAIN / DEAD END / PARENT-NAMED / POI-CAND` live diagnostics.
- Added `Measure-Derelict-Generation.cmd` / `.ps1` to archive each compact measurement and rebuild accumulated JSON + CSV comparison outputs.
- Added `Compare-Generation-Measurements.cmd` / `.ps1`.
- Added verified v0.3.11 generation fixtures for both 51 and 35 baselines.
- Offline regression suite expanded to 38 tests.

## 0.3.10 — generation fingerprint + Cosmos rule parser fix

- Fixed current Cosmos nested generation-rule normalization; room count/sequence/quest placement fields no longer collapse to null.
- Added `Analyze-Generation-Baseline.cmd` / `.ps1` and `tools/analyze_generation_baseline.py`.
- Collapses streamed dungeon scene pieces by runtime parent handle into logical generated chunks and totals Salvage Crates / Crew Footlockers per chunk.
- Infers dungeon preset conservatively from observed scene family + hazard resources; verified baseline #1 resolves to `CARGO_FLOATERS`.
- Captures compact non-zero reward-seed candidates and records solar-system 16-block information only as a historical hypothesis.
- Runtime scene probes now attempt to capture `parent_node_name` using read-only `Engine.GetNodeName(parent)`.
- Added verified generation fingerprint fixture: 126 scene instances -> 9 logical chunks -> 32 + 19 = 51, reward seed `1EE5E3C00986D42A`.
- Offline regression suite expanded to 31 tests.

## 0.3.9 — generation table analyzer

- Locked the verified 51-container baseline as an asset-calculator regression fixture: 126/126 scene instances resolved, 32 Salvage Crates + 19 Crew Footlockers = 51.
- Added `Analyze-Dungeon-Generation.cmd` / `.ps1`.
- Added schema-tolerant `tools/analyze_dungeon_generation_table.py` for current `FREIGHTERDUNGEONSTABLE` MXML/EXML.
- Normalizes dimensions, entrance, room count, axis/straight probabilities, main/branch room types, generation rules and pruning rules.
- Preserves full raw source properties and unknown rule types to avoid hallucinating or discarding current-game fields.
- Offline regression suite expanded to 29 tests.

# Changelog

## 0.3.31
- Correct static-analysis boundary regression: root `.pdata` entry `0x0063505C..0x0063553E` is a runtime fragment, not the logical C++ function start.
- Recover logical entry `0x00634BC0` from four-byte `INT3` padding plus validated x64 prologue.
- Lower padding threshold from 6 to 4 **only when** the expected prologue shape validates, preventing selection of previous helper `0x006345B0`.
- Correct **Extract upstream callers + upload** to scan xrefs to `0x00634BC0`.
- Correct **Analyze seed function + upload** to distinguish logical entry from root runtime fragment and scan the entry-to-root prefix for seed references/writes.
- Preserve standalone Surveyor and read-only probe.
- Verification: 100/100 tests pass before packaging.

## 0.3.8 — exact CRATEM/FOOT_LOCKER node counting

- Promotes exact room-scene node token `CRATEM` to the Salvage Crate counting signal.
- Uses exact `FOOT_LOCKER` node tokens as the Crew Footlocker counting signal.
- `REFCRATEM*` and `REFFOOTLOCKER*` remain validation aliases only; they are not counted as extra objects.
- Evidence: in the verified 51-container address `0001550006607CAC`, the v0.3.7 discovery pass found 32 exact `CRATEM` + 19 exact `FOOT_LOCKER` = 51, while the `REFCRATEM*` family partitions exactly to 32 one-for-one.
- `Analyze-Existing-Crate-Assets.cmd` now rebuilds the room index and recalculates the latest session from already-extracted assets; no game run or re-extraction is required.
- Adds regression fixture `baseline-001-cratem-node-correlation-v0.3.7.json`.


## 0.3.8 — asset calculator bootstrap
- Diagnosed the v0.3.5 known-51 field run: 459 active node probes, 1,259 scene probes, 1,184 resolved resource names, 19,238 indexed resources, and still no exact top-level `ABAND_CRATE_M`/`FOOTLOCKER` instance.
- Confirmed the v0.3.5 resource decoder fix worked; crate counting is now blocked by **nested scene content**, not resource-name resolution.
- Runtime AUTO status now reports `EMBEDDED IN ROOM SCENES` instead of presenting a misleading zero when crate-like room scenes are visible but exact target children are not.
- Added one-click `Prepare-Crate-Assets.cmd` / `.ps1`: locate current NMS `PCBANKS`, install/update HGPAKtool, filtered-extract derelict dungeon assets + target placement candidates, download/verify current MBINCompiler, install private .NET 8 if needed, decompile, index, and calculate the latest session.
- Added `tools/extract_current_derelict_assets.py` with narrow HGPAK filters.
- Added `tools/build_scene_crate_index.py`, which recursively follows scene references and counts Salvage Crate + Crew Footlocker targets, including candidate placement-scene aliases.
- Added `tools/calculate_session_crates_from_assets.py`, which applies the scene index to unique streamed dungeon scene instances from an existing session.
- `analyze_crate_trace.py` now lists encountered dungeon scene resources.
- Added the v0.3.5 resource-resolution research fixture and expanded regression suite to 22 tests.


## 0.3.4
- Diagnosed v0.3.3 live run: 464 scene-probe events, 400 active node probes, but only one usable resource-name index entry; raw scene handles streamed progressively as the player moved.
- Added `cTkResourceManager.FindResourceA.after` capture to map resource lookup filenames back to returned smart-resource handles, including assets loaded before the current `Engine.AddResource` path becomes visible.
- Added `resource_find` trace events and live `FIND` diagnostic count.
- Added per-session anonymous scene-handle histogram (`scene_handle_top`) so repeated streamed assets can be correlated even before their names resolve.
- Preserved exact-only auto counting: anonymous handle frequency is research evidence only, never promoted to a crate count.
- Added the v0.3.3 streaming session and a compact analysis fixture; one handle occurred 34 times and another 17 times (51 combined), explicitly marked correlation-only until identity is proven.

## 0.3.3
- Diagnosed the v0.3.2 live miss: 365 spawned-node probes fired, but no root node names exposed `ABAND_CRATE_M` or `FOOTLOCKER`.
- Added raw spawned-scene evidence capture with the existing 60-second pre-entry window.
- Added a second resource-index path via `cTkResource.cTkResource` so node resource handles can resolve to filenames without relying only on `Engine.AddResource`.
- `Engine.AddNodes` now records raw scene-graph handle, node resource handle, parent handle, root node name, and resolved resource name.
- `Engine.AddGroupNode` records the same identity evidence.
- Added bounded raw resource-name capture so the next short run reveals the actual crate/room scene naming.
- Overlay now shows `RAW`, `RESOLVED`, and `INDEX` diagnostics beside AUTO TARGET.
- Counting remains exact-only; generic crate/locker-like names are diagnostics and never inflate the target count.

## 0.3.2
- Corrected the research target: high-value crate metric is now the combined total of `ABAND_CRATE_M` Salvage Crates and `FOOTLOCKER` Crew Footlockers.
- Automatic detector reports combined `AUTO TARGET` plus separate Salvage and Footlocker counts.
- Asset indexer counts both target IDs independently and combined.
- Kept manual F7 as the combined ground-truth target count for validation.

# 0.3.2

- Added experimental automatic salvage-crate counting for `ABAND_CRATE_M`.
- Counts deduplicated spawned node handles from `Engine.AddNodes` / `Engine.AddGroupNode` when the node or mapped resource identity matches the salvage-crate ID.
- Keeps weaker crate-like names as diagnostics only; never promotes them into the automatic total.
- Buffers exact pre-entry crate instances for 60 seconds so generation just before the environment transition is not lost.
- Overlay now shows `AUTO CRATES ?`, `AUTO CRATES 0 · SCANNING`, or `AUTO CRATES N · LIVE/SAVED` separately from manual F7 markers.
- Crate trace analyzer/dataset now include automatic count and auto-vs-manual match state.
- Existing seed trace, telemetry, manual markers, module rank, safe overlay, and session schema compatibility preserved.

# Changelog

## 0.3.31
- Correct static-analysis boundary regression: root `.pdata` entry `0x0063505C..0x0063553E` is a runtime fragment, not the logical C++ function start.
- Recover logical entry `0x00634BC0` from four-byte `INT3` padding plus validated x64 prologue.
- Lower padding threshold from 6 to 4 **only when** the expected prologue shape validates, preventing selection of previous helper `0x006345B0`.
- Correct **Extract upstream callers + upload** to scan xrefs to `0x00634BC0`.
- Correct **Analyze seed function + upload** to distinguish logical entry from root runtime fragment and scan the entry-to-root prefix for seed references/writes.
- Preserve standalone Surveyor and read-only probe.
- Verification: 100/100 tests pass before packaging.

## 0.3.0 — crate calculator capture pivot

- Pivoted primary goal to **high salvage-crate count prediction/search**; detailed room geometry is secondary.
- Added automatic `Engine.AddResource` tracing for derelict-related resource names and resource descriptor primary/secondary seeds.
- Added a 60-second pre-session resource trace buffer to catch generation activity before the `AbandonedFreighter` environment flag is set.
- Added automatic `cGcRewardManager.GiveGenericReward` capture for reward IDs and `cTkSeed` values during derelict sessions.
- Added live overlay trace counters: resource events, reward events, unique candidate seeds and latest seed.
- Added `tools/analyze_crate_trace.py` and one-click `Analyze-Latest-Crate-Trace.cmd`.
- Added `tools/build_crate_dataset.py` for aggregating labeled sessions.
- Added `tools/index_extracted_crates.py` to build `ABAND_CRATE_M` lookup data from decompiled asset exports.
- Added verified 35-crate S-class Cosmos fixture from the latest user run.
- Preserved all v0.2.5 recorder, telemetry, Room 0 and module-rank behavior.

## v0.2.5
- Added **F11 Engineering freighter-module rank** selector.
- F11 cycles `UNKNOWN → C → B → A → S → UNKNOWN`.
- Overlay now shows `MODULE UNKNOWN/C/B/A/S` live while recording.
- Added `F11 MODULE C-S` to the always-visible hotkey legend.
- Rank persists in existing `manual.engineering_module_class`, keeping session schema v1 backward-compatible.
- Live-status schema v1 gains optional `engineering_module_class` enum for the overlay.
- pyMHF manual text entry is now normalized to only `unknown/C/B/A/S`.

## 0.2.4

- Added live X/Y/Z telemetry to the safe overlay, updated about five times per second.
- Overlay now shows the selected coordinate source (`player.mPosition`, `environment.mPlayerTM`, or scene-node fallback) for field diagnosis.
- `live-status.json` also publishes all available compact position candidates to aid debugging if one source is wrong.
- Added **F5 = Room 0 / dead end**, stored separately as marker type `room_zero`.
- Added live `ROOM 0` count without mixing dead ends into normal route-room totals.
- Added an always-visible two-line F5-F10 hotkey legend to the overlay.
- Preview and session-comparison tools now understand Room 0/dead-end markers.
- Position selection now prefers a non-zero finite source if another source incorrectly reports all-zero coordinates.
- Preserved the non-layered/opaque overlay safety path introduced after the black-screen issue.
- Regression suite expanded to 9 tests.

## v0.2.3 — First verified 51-crate baseline + capture corrections

- Added `corpus/verified/baseline-001_51-crates.json`: historical 51 crates, manually observed 51 again on 2026-09-29.
- Preserved the untouched v0.2.2 source session beside the fixture.
- Position sampling now prefers `cGcPlayer.mPosition`, then `cGcPlayerEnvironment.mPlayerTM.pos`, before the scene-node transform fallback.
- Runtime metadata records both live and stable environment locations and reports `AbandonedFreighter` if either runtime field does.
- Session filenames fall back to the captured universe address instead of `unknown` when NMS does not expose a system name.
- Added regressions for the first fixture and the zero-position defect.
## v0.2.3
- Replaced the transparent/layered Tk overlay with a small **opaque safe banner** after a real NMS test produced black/frozen rendering.
- Removed Tk `-alpha` and `WS_EX_LAYERED`; the default overlay no longer uses Windows composited transparency.
- Added `Start-Derelict-Probe-NoOverlay.cmd` to isolate runtime-hook problems from overlay problems.
- Added `Stop-Derelict-Overlay.cmd` to terminate only Surveyor overlay processes, without touching unrelated Python processes.
- Main launcher now stops any stale v0.2.0/v0.2.1 overlay before starting the safe banner.
- Session schema, live-status schema and F6-F10 marker contracts are unchanged.

## 0.2.0
- Added a transparent, always-on-top, click-through Windows companion overlay.
- Added main-menu visual proof: `LOADED & READY` appears once the runtime probe is alive.
- Added automatic visual transition to `RECORDING` when NMS reports `EnvironmentLocation.AbandonedFreighter`.
- Added live crate, room, vertical-transition, and Shuttle Bay counters.
- Added immediate visual event text for F6-F10 marker actions and session start/stop.
- Added versioned `live-status.json` heartbeat contract and JSON schema.
- Overlay tracks the NMS client window and prefers the live NMS process ID published by the probe.
- Overlay failure is isolated from runtime capture and logs separately.
- Existing session schema v1 and F6-F10 marker contract are unchanged.

## 0.1.0
- Initial read-only runtime baseline probe.
- Automatic derelict session start/end.
- Runtime system/RealityIndex capture, route sampling and F6-F10 ground-truth markers.
- Offline preview and cross-galaxy comparison tools.

## v0.2.1
- Added `Setup-Python-3.13.cmd` / `.ps1` for one-click side-by-side Python 3.13 installation.
- Launcher now automatically invokes the Python 3.13 setup when no supported Python is found.
- Python 3.14 is deliberately preserved; the Surveyor selects 3.13 explicitly rather than uninstalling or replacing 3.14.
- Setup prefers the official Python Install Manager (`pymanager install 3.13`) and falls back to WinGet (`Python.Python.3.13`).

## 0.3.8 - crate target discovery
- Preserves v0.3.6 asset calculator and runtime probe.
- Adds `Analyze-Existing-Crate-Assets.cmd` for a no-gameplay follow-up using the already extracted asset cache.
- Adds `tools/discover_crate_targets.py` to inventory ENTITY references and crate/loot-related identifiers from the exact dungeon scene pieces used by the latest session.
- `Prepare-Crate-Assets.cmd` now also extracts `BASEBUILDINGOBJECTSTABLE.MBIN`, `BASEBUILDINGPARTSTABLE.MBIN`, and `FREIGHTERDUNGEONSTABLE.MBIN`, then emits `crate-target-discovery.json`.
- Adds a permanent v0.3.6 research fixture recording that 126/126 used dungeon scene instances resolved, but the static index predicted 0 Salvage Crates + 19 Crew Footlockers. The 19 result is explicitly diagnostic, not accepted as the true target total.
- Regression suite expanded to cover entity-reference discovery and the v0.3.6 salvage-gap failure mode.
# 0.3.58 — one-pass caller register snapshot

- Build Runtime-A probe 0.3.37 from the verified Surveyor 0.3.57 updater payload, which contains probe 0.3.35.
- Retain the shared logical-entry owner+0x10 sample and add RCX/RDX snapshots for all callers through one hook; keep root-add capture distinct.
- Package publication and live Windows/NMS validation remain pending.

# 0.3.57 — fix startup layout conflict

- Put GitHub update buttons in their own child frame, avoiding the Tk `pack`/`grid` parent conflict that prevented Surveyor from starting.
- Preserve the v0.3.56 automatic evidence upload controls.

# 0.3.56 — optional automatic evidence uploads

- Add a persistent main-window toggle for automatic root-capture and shared all-lanes evidence uploads.
- Upload the updated shared evidence batch after successful lane/research workflows; skip duplicate batches when the saved evidence has not changed.
- Preserve lane-specific upload paths and the manual Upload all saved evidence action.

# 0.3.54 — persist complete root capture

- Bump embedded Runtime-A probe to 0.3.35.
- Persist the full root event, runtime metadata, event timestamp, and universe address in the atomically saved exact-root capture so Upload all saved evidence carries the live capture after NMS exits.
- Capture runtime metadata before writing the exact-root artifact; preserve a null address and any capture error explicitly when unavailable.
- Keep existing schema version 1 fields and upload paths backward compatible.

