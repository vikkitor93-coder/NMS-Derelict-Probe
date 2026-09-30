# NMS Derelict Probe v0.3.26

## v0.3.26 — move one function upstream without launching NMS

The uploaded `dungeon-caller-code-latest.json` resolved the root `Engine::AddResource` call much further. The call at `0x00635110` sits inside a function whose compiler-padded start is **`0x00634BC0`**. In that function the second argument is copied to `RSI`, the resource descriptor is addressed at **`RSI + 0x128`**, and the primary seed is read at **`RSI + 0x138`** before the root resource is added. NMS.py defines `cTkResourceDescriptor.mSeed` at descriptor offset `+0x10`, which matches `0x128 + 0x10 = 0x138`. The function also checks the seed-use byte at `RSI + 0x140` (`descriptor + 0x18`).

This means the observed root seed `9256392A2F5A74AC` is already present **before this function reaches `Engine::AddResource`**. The seed-construction boundary is therefore upstream again. Current public NMS.py does not expose a matching named signature for the `0x00634BC0` function, so v0.3.26 does not guess a symbol name.

v0.3.26 adds **`Extract-Dungeon-Upstream-Callers.cmd`** and the GUI button **Extract upstream callers + upload**. The tool is completely offline/read-only: it derives the containing-function boundary from the captured code bytes, scans the installed `NMS.exe` `.text` section for direct `E8` calls / `E9` tail-jumps to that function, captures small code windows around each reference, and writes `%LOCALAPPDATA%\NMSDerelictSurveyor\asset-work-v1\dungeon-upstream-callers-latest.json`. No game launch or derelict visit is required.

## v0.3.25 — fix upload launch + unclipped GUI workflow messages

The v0.3.24 diagnostic proved GitHub itself was healthy (CLI installed, authenticated, repository writable) while `Measure + upload` failed before GitHub because Windows `cmd.exe /s /c` misparsed the quoted project path. v0.3.26 removes that fragile chained command entirely.

GUI research/upload actions now run as explicit background steps:

1. **Run research command** — PowerShell workflows are launched directly with `powershell.exe -File`; caller extraction launches its Python tool directly.
2. **Upload generated evidence** — runs only if step 1 succeeds.

There is no `cmd.exe /s /c ... && ...` chain, and normal GUI research/upload actions use `CREATE_NO_WINDOW`, so they should not pop up an empty command window. Each step receives its own start/result log entry and a failure names the exact step.

pyMHF STRING rows do not word-wrap. Instead of depending on wrapping, v0.3.26 exposes **Workflow message 1 / 2 / 3**, each capped to a short width. Long paths and status text are split across those rows rather than disappearing off the right edge.

All v0.3.24 persistent diagnostics remain available: `workflow-latest.log`, per-action logs, `workflow-diagnostic-latest.txt`, `github-integration.log`, `github-diagnostic-latest.txt`, and mirrored workflow events in the normal `latest.log`.

## v0.3.24 — workflow diagnostics that survive upload/setup failures

v0.3.26 makes the GitHub/research action path diagnosable from the user machine instead of relying on the normal runtime `latest.log`.

- Every GUI action now appends `workflow_started`, `workflow_completed`, `workflow_failed`, or `workflow_exception` to `%LOCALAPPDATA%\NMSDerelictSurveyor\latest.log`.
- `%LOCALAPPDATA%\NMSDerelictSurveyor\gui-actions\workflow-latest.log` is a persistent combined action log.
- Each action also gets `latest-<action>.log` plus a timestamped archived copy.
- `workflow-diagnostic-latest.txt` records the action, sanitized command, return code, stdout and stderr even when the helper crashes before producing normal output.
- `github-integration.log` records GitHub CLI discovery, auth status return codes, upload/API stages, output-file discovery and failures without storing tokens/passwords.
- New **Open workflow log**, **Open workflow diagnostic**, and **Run GitHub diagnostic** GUI buttons make failures inspectable without finding hidden folders manually.
- GUI status/detail text is deliberately short so it no longer disappears off the right side of the pyMHF window.
- When GitHub authentication is required on Windows, `gh auth login --web` now runs in a visible console so the one-time device-code/browser flow cannot be hidden behind captured output.

The runtime probe remains read-only and the external overlay architecture is unchanged.

## v0.3.23 — fix GUI helper buttons launching NMS.exe

In an injected pyMHF process, `sys.executable` can point at the host game executable rather than Python. v0.3.22 used it for GitHub/update/upload helper subprocesses, so clicking **Set up GitHub uploads** or **Install Surveyor update** could start another NMS instance.

v0.3.23 fixes the entire helper path:
- launchers persist the verified external Python 3.12/3.13 executable to `%LOCALAPPDATA%\NMSDerelictSurveyor\python-executable.txt`;
- GUI GitHub setup, update, and research-upload actions use that persisted interpreter;
- fallback resolution accepts only executables whose basename starts with `python`;
- `NMS.exe` and any other non-Python host executable are explicitly rejected;
- if no safe Python interpreter is found, the GUI reports an error instead of launching anything.

All runtime probing remains read-only and the safe overlay architecture is unchanged.



## v0.3.22 — GUI research actions + GitHub handoff/update channel

The pyMHF companion GUI now focuses on actions rather than duplicating the live room/crate overlay. It provides background buttons for **Measure derelict generation + upload**, **Extract dungeon caller code + upload**, **Prepare crate assets + upload**, generation analysis, GitHub upload setup, update checking, and update installation. Existing developer/session controls remain available.

GitHub research upload uses the authenticated **GitHub CLI (`gh`) credential store**. No PAT/password is written by the project. After a successful action, the expected JSON/CSV evidence files plus a SHA-256/size `run-manifest.json` are committed together under `research-uploads/<UTC>-<action>/`. Command logs stay local under `%LOCALAPPDATA%\NMSDerelictSurveyor\gui-actions`.

`Start-Derelict-Probe.cmd` records the extracted source folder in `%LOCALAPPDATA%\NMSDerelictSurveyor\project-root.txt`. The updater uses the public GitHub manifest and SHA-256-verified base64 package chunks to replace only managed source-project files. Restart Surveyor/NMS.py after installing an update; no live hot-patching is attempted.

The in-game/external safe overlay remains opaque/non-layered and continues to show the live room/container/research telemetry. The action GUI deliberately does not repeat those telemetry fields.

Read-only runtime research tooling for No Man's Sky derelict-freighter generation, with a human-readable companion UI for live room/container counts.


## v0.3.20 — no more derelict run for caller-code expansion

The short v0.3.19 run was sufficient even though no interior rooms streamed. It captured the stable dungeon root seed `9256392A2F5A74AC`, the outer `Engine.AddResource` caller return RVA `0x00635115`, and the inner resource-manager caller return RVA `0x01831AA3`. Decoding the 80-byte window shows a direct `E8 rel32` call at `0x00635110` targeting `0x01831A10`; immediately before the call, `mov [rsp+0x20], rdi` passes the resource descriptor unchanged from `RDI`. The missing seed construction therefore occurs earlier in the outer caller.

v0.3.20 adds **`Extract-Dungeon-Caller-Code.cmd`**. It does not launch NMS. It reads the existing `generation-baseline-latest.json`, auto-locates the installed `NMS.exe`, maps the captured RVA through the PE section table, and extracts a larger static code window (16 KiB before / 4 KiB after by default). The output is `%LOCALAPPDATA%\NMSDerelictSurveyor\asset-work-v1\dungeon-caller-code-latest.json`. Send that JSON back for offline disassembly. The output deliberately omits the full executable path and machine/user/network identifiers.

The analyzer also decodes direct rel32 caller sites into `caller_decoded` / `dungeon_root_engine_call_sites`, including the call RVA, target RVA, and the observed `RDI` descriptor pass-through. Existing runtime/UI behavior is unchanged.

## v0.3.19 — identify the caller that creates the seeded dungeon descriptor

The v0.3.18 live result ruled out the tracked POI `Prepare`, `OnActivate`, and `AdvanceLifecycle` boundaries for this 35-container derelict: all three produced zero target-component events around dungeon creation. The outer `Engine.AddResource` event and inner `cTkResourceManager.AddResource` event instead received the same descriptor pointer with the same `9256392A2F5A74AC` seed, only milliseconds apart. That proves the seed is already populated before resource-manager loading begins.

v0.3.19 keeps all existing evidence and adds a narrow read-only call-site probe:

- pyMHF caller capture on the dungeon-root `Engine.AddResource` call;
- caller capture on the inner `cTkResourceManager.AddResource` call;
- a small read-only code window around the outer caller return address, obtained with `ReadProcessMemory`;
- analyzer fields `dungeon_root_engine_caller_offsets` and `dungeon_root_manager_caller_offsets`;
- the v0.3.18 resource-boundary run preserved as an immutable research fixture.

No gameplay state is modified. Room/crate counting, the companion UI, manual markers, resource/seed evidence, and existing JSON fields remain compatible.

## v0.3.17 — capture the POI function return and Prepare boundary

The widened v0.3.16 reanalysis proved the raw universe address is propagated directly into several HULK resource descriptors before the dungeon root, but it still did not expose the actual address→dungeon-root transform. v0.3.17 therefore adds a narrow runtime probe instead of a global RNG hook:

- record the **64-bit return value** of `cGcSpacePoiSiteComponent::GeneratePoiDescription` for AbandonedFreighter/Derelict POIs;
- record target-POI `Prepare` before/after events and duration;
- tag `Engine.AddResource` events that occur synchronously inside that `Prepare` scope;
- expose `POI-RET <hex>` only under the companion's existing **Research** toggle;
- summarize the evidence as `poi_generation_trace` in the generated baseline, including whether the return equals the universe address, equals the dungeon-root seed, and whether the root resource was added inside `Prepare`.

The hooks are observational only and do not alter NMS state. Existing room/crate UI, schemas and measurement fields remain backward compatible.


## v0.3.16 — wider seed context from the raw recording you already have

`Reanalyze-Latest-Generation.cmd` now emits two seed views:

- `resource_seed_lineage`: unchanged dungeon-only lineage for backward compatibility.
- `resource_seed_context_lineage`: all non-zero descriptor seeds from the derelict/POI resource events the probe already recorded, including paths outside `/DUNGEON/`.

This specifically avoids requiring another NMS run when an existing `latest.json` already contains useful upstream POI resource events. The values remain correlation evidence, not assumed RNG state.


## v0.3.15 — live room-loot view + toggleable diagnostics

The companion now defaults to the information that matters while actually running a derelict: **combined target containers, Salvage Crates, Crew Footlockers, and per-`Room N` totals/type**. It uses the same extracted scene→crate index already validated against the 51- and 35-container fixtures.

Use the companion checkboxes to show/hide **Rooms**, **Research**, **Position**, **Manual**, and **Hotkeys**. Rooms default on; the diagnostic-heavy sections default off and the choices persist locally. Research data is not deleted or simplified. The opaque/non-layered rendering path is unchanged.

Generation baseline files also include `analysis_tool_version` so a new probe recording processed by an old Measure/Analyze script can be detected immediately.

## v0.3.14 — address/layout discriminator confirmed + seed-lineage capture

The independent 35-container address `00001A0004E84EFD` now captures dungeon-root descriptor seed **`9256392A2F5A74AC`**, while the verified 51-container address `0001550006607CAC` uses **`00C9E8DF0327789E`**. The 35 run reproduced the exact prior Room-N layout multiset and 35-container total, so the root descriptor seed is no longer consistent with being a global `DUNGEON.SCENE.MBIN` constant. It remains a correlation candidate until repeat/cross-galaxy tests establish its exact role.

v0.3.14 adds **ordered seed-lineage evidence** without changing game state or crate-count behavior:
- every trace event receives a monotonic `trace_sequence` so tied millisecond timestamps cannot scramble callback order;
- generation baselines summarize non-zero seed-bearing `resource_add` / `resource_find` events under the derelict dungeon resource tree;
- the baseline stores the ordered lineage, unique primary/secondary descriptor seeds, and a SHA-256 signature for repeat comparison;
- accumulated generation measurements and seed/room correlation reports carry the lineage signature.

The goal is to identify the observed derivation chain between POI/system-address context and the seed passed to `MODELS/SPACE/POI/DUNGEON.SCENE.MBIN`, not to guess a hash from two samples.


## v0.3.13 — dungeon-root seed candidate + clean POI context

The 51-container repeat confirmed the stable Room-N layout and exposed two useful facts:

- The long POI pre-session buffer could retain the previous system address. v0.3.13 filters POI context against the current session universe address, while preserving mismatch diagnostics.
- The older verified 51 raw session already contained a primary `cTkResourceDescriptor` seed on `MODELS/SPACE/POI/DUNGEON.SCENE.MBIN`: **`00C9E8DF0327789E`**. This is distinct from both the system address (`0001550006607CAC`) and reward seed (`1EE5E3C00986D42A`).

That dungeon-root descriptor seed is now the strongest **layout-seed candidate**, but remains explicitly unverified until repeat/cross-system testing proves its relationship to the generated Room-N layout.

New measurement behavior:
- live overlay shows `DUNGEON-SEED <hex>` when captured;
- generation baselines include `dungeon_root_seed_candidates`;
- accumulated JSON/CSV measurements include dungeon-root seeds;
- seed/room correlation checks their stability across repeated visits and collisions across addresses;
- `Reanalyze-Latest-Generation.cmd` reprocesses the existing `latest.json` offline, so a previously captured v0.3.12 run can reveal the candidate without another game run.

## v0.3.12 — stable Room N fingerprint + POI address correction

The first v0.3.11 repeat measurement resolved two important ambiguities:

- `cGcSpacePoiSiteComponent::GeneratePoiDescription` final 64-bit argument for the verified 35-container system was exactly `00001A0004E84EFD`, the session universe address. v0.3.12 therefore labels this context as **POI-UA / universe-address-confirmed**, not a layout seed. `layout_seed_status` remains `not-captured-yet`.
- Scene streaming order changed between repeat visits even though the room assemblies were identical. Current NMS parent labels expose `Room 0`, `Room 1`, ...; v0.3.12 uses these game-assigned room indices for the stable `layout_signature_sha256` and retains stream order only as diagnostics.

For the verified 35-container repeat the canonical room sequence is: `Room 0 BARRACKS=1`, `Room 1 CARG=15`, `Room 2 CARG=10`, `Room 3 HANGAR=3`, `Room 4 CARG=4`, `Room 5 DEAD END=0`, `Room 6 BARRACKS=1`, `Room 7 END=1` (35 total).

New tool: **`Analyze-Seed-Room-Correlation.cmd`** reads the accumulated generation measurement set and reports repeat-address layout stability, reward-seed stability, POI-context/address equality, and cross-address seed/layout collisions.


## v0.3.11 — seed → room-selection measurement toolkit

The two verified `CARGO_FLOATERS` baselines now confirm the room model: the table's `Rooms = 7` corresponds to **seven main rooms**, while compact family-level `DEADEND_*` groups are additional gameplay dead-end rooms. Verified baseline #1 is 7 main + 2 dead ends = 9 rooms and 51 target containers; verified baseline #2 is 7 main + 1 dead end = 8 rooms and 35 target containers.

New preferred command: **`Measure-Derelict-Generation.cmd`**. After a probe run it refreshes the crate index and generation table, builds `generation-baseline-latest.json`, archives the measurement by session ID, and rebuilds both `generation-measurements-summary.json` and spreadsheet-friendly `generation-measurements.csv`. The comparison set is automatically seeded with the two already-verified 51/35 baselines.

The runtime probe derives room groups from streamed dungeon scene parents and uses a conservative dead-end classifier: `EMPTY/ROOM_DEADEND_R_*` inside a full room does not count as an extra room; compact family-level assets such as `BARRACKS/DEADEND_BUNK*` do. **v0.3.15 promotes this to the main companion view**: when the existing scene→crate index is available, the overlay shows combined loot plus each `Room N` with its Salvage Crate and Crew Footlocker totals. The older `GEN ROOMS ...`, RAW/resource and seed diagnostics remain available under the **Research** toggle.

v0.3.11 also adds an **experimental, read-only POI seed-candidate probe**. Current NMS.py exposes `cGcSpacePoiSiteComponent::GeneratePoiDescription`; for abandoned-freighter/derelict POI types the probe records the raw 64-bit final argument as `layout-seed-candidate-unverified`. It is deliberately not promoted to a proven layout seed until repeated systems/revisits demonstrate the relationship. Candidate events are kept for up to 30 minutes before entry so a longer approach to the derelict does not lose them.

`Compare-Generation-Measurements.cmd` rebuilds and opens the accumulated JSON/CSV comparison without needing another game run.


## v0.3.10 — compact generation fingerprints

The verified 51-container baseline now has a compact generation fingerprint: address `0001550006607CAC`, inferred preset **`CARGO_FLOATERS`**, 126 streamed dungeon scene pieces collapsed into **9 logical parent chunks**, and **32 Salvage Crates + 19 Crew Footlockers = 51**. The same non-zero reward seed `1EE5E3C00986D42A` appears on three derelict reward paths.

New one-click tool: **`Analyze-Generation-Baseline.cmd`**. It reuses the existing extracted assets and `latest.json`, refreshes the room crate index and dungeon-generation table, then writes `%LOCALAPPDATA%\NMSDerelictSurveyor\asset-work-v1\generation-baseline-latest.json`. The output contains preset inference, current generation rules, reward seed candidates, logical room-group scene composition and per-group crate totals.

The Cosmos generation-rule parser now unwraps the current nested rule shape correctly, so `GcRoomCountRule`, `GcRoomSequenceRule` and `GcQuestItemPlacementRule` fields are normalized instead of appearing as null. Runtime scene probes also attempt to record `parent_node_name` for future captures using the read-only `Engine.GetNodeName(parent)` path.

Historical community research suggesting 16-system derelict blocks is recorded only as a **hypothesis** in the baseline output; v0.3.10 does not assume it still holds in Cosmos.


## v0.3.9 — generation-model extraction

The verified 51-container baseline is now solved end-to-end by the asset calculator: **32 exact `CRATEM` nodes + 19 exact `FOOT_LOCKER` nodes = 51**, with all 126 captured dungeon scene instances resolved. The next bottleneck is reproducing **address/seed → generated dungeon room scenes** offline.

If you already ran `Prepare-Crate-Assets.cmd`, you do not need NMS or another extraction. Double-click **`Analyze-Dungeon-Generation.cmd`**. It parses the already-extracted current `FREIGHTERDUNGEONSTABLE` and writes `%LOCALAPPDATA%\NMSDerelictSurveyor\asset-work-v1\dungeon-generation-table.json`. Send that file back to ChatGPT. The parser normalizes size/entrance/room/probability fields, main/branch room types, room-count/sequence rules and pruning rules, while also preserving the full raw property tree and unknown rule types to avoid silently losing Cosmos-era fields.

## v0.3.8 crate-calculator breakthrough

Current Cosmos derelict room scenes expose the two desired blue loot containers through exact scene-node names:

- `CRATEM` → Salvage Crate counting signal
- `FOOT_LOCKER` → Crew Footlocker counting signal

The verified 51-container baseline produced **32 `CRATEM` + 19 `FOOT_LOCKER` = 51** from the exact room scenes streamed by the game. `REFCRATEM*` / `REFFOOTLOCKER*` are paired reference names and are used only to validate the node counts, never added to them.

If you already ran `Prepare-Crate-Assets.cmd`, you do **not** need to extract again. Double-click `Analyze-Existing-Crate-Assets.cmd`; v0.3.8 rebuilds `room-crate-index.json` with the exact node-token rule and regenerates `asset-calculation-latest.json`.


A read-only runtime + asset-analysis toolkit focused on reverse-engineering **coordinates/seed → total target-container count** (Salvage Crates + Crew Footlockers), with module class as a secondary filter. v0.3.8 pivots the crate calculator from unreliable top-level node counting to current-game scene-asset extraction after the v0.3.5 field run proved the target containers are embedded inside streamed derelict room scenes.


## Fastest next step for the generator research

The crate identity/count layer is validated on the 51 baseline. Do **not** recount that freighter. For an existing capture, double-click **`Analyze-Generation-Baseline.cmd`**. For new RNG research runs, prefer **`Measure-Derelict-Generation.cmd`**. It refreshes the current asset index + generation table and produces one compact `generation-baseline-latest.json`.

For the first v0.3.11 seed-candidate validation, a **repeat visit to either verified 51- or 35-container system is especially useful** because the layout is already known. Traverse the whole derelict so every room streams in, leave, then run `Measure-Derelict-Generation.cmd`. Manual F5/F6/F7 marking is optional; the measurement tool now classifies main rooms/dead ends and calculates crate totals automatically.

The baseline report records: address, system index, inferred preset, main/dead-end room counts, generation order, parent-node names where available, per-room crate totals, non-zero reward seed candidates, experimental POI seed candidates, current generation rules, and a generation-signature SHA-256.

## Python 3.14 users

Do **not** uninstall Python 3.14 just for this project. The Surveyor now includes `Setup-Python-3.13.cmd`, which installs Python 3.13 side-by-side and leaves 3.14 untouched. `Start-Derelict-Probe.cmd` will run that setup automatically when it cannot find Python 3.12/3.13.

The setup prefers the official Python Install Manager and falls back to WinGet. After setup, the launcher explicitly selects the supported interpreter instead of relying on whichever `python.exe` happens to be first on PATH.

## What you should see

Double-click **`Start-Derelict-Probe.cmd`**. The launcher starts a small **opaque safe status banner** and then starts NMS through NMS.py/pyMHF. v0.3.8 deliberately does not use alpha/layered transparency because that caused black/frozen rendering on a real Windows/NMS setup.

Once the runtime probe has actually loaded, the overlay at the top-centre of the NMS window should say:

**DERELICT SURVEYOR v0.3.19 · LOADED & READY**

That is the visual proof that the mod code has initialized. It is deliberately visible at the main menu before you visit a freighter.

When NMS reports the player environment as `AbandonedFreighter`, the probe automatically starts a session and the overlay changes to:

**DERELICT SURVEYOR v0.3.19 · RECORDING**

with live totals such as:

`CRATES 7   ROOMS 3   VERTICAL 1   HANGAR 0`

Every marker also produces an immediate status/event message, for example:

- `Room 0 / dead end added #1 (F5)`
- `Crate added #8 (F7)`
- `Room/zone added #4 (F6)`
- `Vertical transition added #1 (F8)`
- `Shuttle Bay added #1 (F9)`
- `Engineering marked #1 (F10)`

When you leave the derelict and NMS is no longer reporting the abandoned-freighter environment for 3 seconds, the session is finalized and the overlay reports that it was saved.

### Exactly when does recording begin?

The automatic trigger is **not based on guessing distance from the freighter**. It starts on the first runtime tick where NMS changes the player's environment state to `AbandonedFreighter` (`0xB`). We still need one live run to establish exactly where Cosmos changes that state physically — touchdown, airlock entry, or slightly farther inside. The overlay makes that transition visible so we can record the answer rather than assume it.


### Overlay hotkey legend

The safe companion now has persistent view toggles: **Rooms** (on by default), **Research**, **Position**, **Manual**, and **Hotkeys** (off by default). This keeps the normal view focused on loot while preserving all research diagnostics. Enabling **Hotkeys** shows:

`F5 ROOM 0 / DEAD END   F6 ROOM   F7 CRATE`

`F8 STAIRS/VERTICAL   F9 HANGAR   F10 ENGINEERING   F11 MODULE C-S`

This is intentionally always visible so the user does not need to remember or alt-tab to check controls during a survey.

## Runtime capture

- Runtime galaxy/RealityIndex and galactic address.
- **Automatic derelict resource tracing**: relevant resource names plus `cTkResourceDescriptor` primary/secondary seeds seen around entry and during the run.
- **Automatic reward tracing**: reward ID, mission ID, and `cTkSeed` for generic rewards issued while on the derelict.
- A 60-second pre-entry trace buffer so resource requests that happen just before NMS flips to `AbandonedFreighter` are retained.
- System name when available.
- Player 3D breadcrumb path while the session is active.
- Live X/Y/Z telemetry plus the selected runtime position source.
- Manual ground-truth markers:
  - **F5** — **Room 0 / dead end**: a room/branch that does not progress to another route room
  - **F6** — new numbered route room/zone
  - **F7** — one blue salvage crate
  - **F8** — stairs/ladder/vertical transition
  - **F9** — Shuttle Bay / ship hangar
  - **F10** — Engineering Core
- Crash-resistant session JSON plus a lightweight `live-status.json` heartbeat for the overlay.

This version does **not** yet claim to predict crate totals from coordinates, but it now attempts to **count spawned target-container instances automatically**. The overlay shows `AUTO TARGET` separately from manual F7 markers. F7 remains the trusted ground-truth check until repeated runs prove the automatic detector exact. The seed/resource trace continues in parallel for the eventual offline coordinate calculator.

## Start

1. Extract this ZIP somewhere convenient.
2. Double-click **`Start-Derelict-Probe.cmd`**.
3. The installer tries to find No Man's Sky automatically. If it cannot, select `NMS.exe` in the file picker.
4. It copies the probe into `GAMEDATA\MODS\DerelictBaselineProbe`, installs/updates `nmspy`, installs the overlay under `%LOCALAPPDATA%\NMSDerelictSurveyor\overlay`, and launches both.
5. On the first pyMHF run, if asked for the mods directory, choose the game's `GAMEDATA\MODS` folder shown by the launcher.
6. At the NMS main menu, confirm the overlay says **LOADED & READY** before doing a test run.
7. Move around briefly and confirm the displayed X/Y/Z telemetry changes. The overlay also shows which runtime source supplied the coordinates.

NMS.py currently recommends Python 3.12/3.13 and does not yet support Python 3.14. The launcher checks this first.

### If NMS is black or frozen

1. Close NMS.
2. Run **`Stop-Derelict-Overlay.cmd`** once to make sure no old transparent v0.2.0/v0.2.1 banner is still running.
3. Try **`Start-Derelict-Probe-NoOverlay.cmd`**. This installs/starts the same runtime probe but does not launch any companion window.
4. If NMS renders normally in No-Overlay mode, the old external overlay/compositor path was the problem; use the normal v0.3.8 launcher next, which uses the safe non-layered banner.
5. If NMS is still black in No-Overlay mode, stop there and send `latest.log` plus the pyMHF terminal output. That isolates the issue to NMS.py/pyMHF/runtime compatibility rather than the banner.

### Overlay visibility note

The banner is a separate local Windows window rather than an invasive NMS HUD patch. **v0.3.8 is intentionally opaque and non-layered**: it does not use Tk `-alpha` or `WS_EX_LAYERED`, because that compositor path caused black/frozen rendering in v0.2.1 on a real system. It should work over normal windowed/borderless NMS. If an exclusive-fullscreen mode hides external windows, use borderless/windowed for the baseline test. Failure of the banner never prevents the probe from recording; banner errors are written to `%LOCALAPPDATA%\NMSDerelictSurveyor\overlay-error.log`.

## Crate-calculator workflow

The primary path is now asset-first:

1. Run **`Prepare-Crate-Assets.cmd`** once after a game update.
2. Send back `room-crate-index.json` and `asset-calculation-latest.json`.
3. The calculator combines the captured streamed dungeon scene instances with the recursively indexed target-container counts from current game assets.
4. The existing runtime probe remains useful for addresses, deterministic reward seeds, streamed room-scene identities, and later validation.
5. F7 remains available only as ground truth/regression evidence; routine manual recounting is no longer the preferred research path.

Output is under `%LOCALAPPDATA%\NMSDerelictSurveyor`:

- `live-status.json` — transient overlay/heartbeat, per-room live loot summary, and research counters.
- `overlay-settings.json` — local display-toggle preferences only; no identifying/device/network data.
- `latest.json` — latest captured derelict session.
- `latest.log` — structured runtime log.
- `sessions\...json` — retained sessions.
- `asset-work-v1\room-crate-index.json` — recursive dungeon scene → target-container lookup.
- `asset-work-v1\asset-calculation-latest.json` — calculated total for the latest session using that lookup.

### Analyze the newest capture locally

Double-click **`Analyze-Latest-Crate-Trace.cmd`**. It writes:

`%LOCALAPPDATA%\NMSDerelictSurveyor\crate-research-latest.json`

The report contains the portal/runtime address, observed F7 crate total, module class, relevant resource names, reward IDs and all unique candidate seeds with their origins.

For multiple session files, `tools\build_crate_dataset.py` creates CSV/JSON research datasets. `tools\build_scene_crate_index.py` recursively follows decompiled scene references and counts Salvage Crate / Crew Footlocker targets. `tools\calculate_session_crates_from_assets.py` applies that index to a captured session. `tools\index_extracted_crates.py` remains as the simpler raw text-reference indexer.

The project has no networking and does not collect IP addresses, machine IDs, hardware IDs, or real-world location data.

## Generate a visual baseline

```bat
python tools\build_preview.py "%LOCALAPPDATA%\NMSDerelictSurveyor\latest.json"
```

This creates `latest-preview.html`, a runtime breadcrumb map of the actual player route plus F5-F10 markers and the F11 session-level module rank. Room 0/dead-end markers render separately from normal route rooms.

## Cross-galaxy experiment

Make one run at the same galactic/portal address in galaxy A and another in galaxy B, then run:

```bat
python tools\compare_sessions.py first.json second.json
```

The comparison treats RealityIndex separately from X/Y/Z + solar-system index so we can directly test the claim that the same derelict is generated across galaxies.

## Developer / debug access

The pyMHF GUI exposes the `DerelictBaselineProbe` tab with runtime status, counters, current session path, latest error, manual start/stop, undo, and diagnostic snapshot. The safe companion has display-only checkboxes for Rooms/Research/Position/Manual/Hotkeys; these do not mutate NMS state.

`%LOCALAPPDATA%\NMSDerelictSurveyor\latest.log` remains the primary diagnostic log.

## Safety / rollback

The runtime probe reads NMS.py-exposed data and writes its own local files only. The visual overlay reads only `live-status.json`; it never attaches to NMS memory itself.

To uninstall the runtime probe, delete `GAMEDATA\MODS\DerelictBaselineProbe`. The companion overlay automatically exits after the NMS window closes; deleting `%LOCALAPPDATA%\NMSDerelictSurveyor\overlay` removes its installed copy.

## Automatic target-container status (v0.3.8)

The direct runtime detector is retained as a diagnostic, but it is no longer treated as the primary counting strategy. The v0.3.5 field run proved that real derelict room resources resolve correctly while `ABAND_CRATE_M` / `FOOTLOCKER` are not exposed as top-level spawned nodes.

The overlay can therefore show:

- `AUTO TARGET ? · ... WAITING` — no relevant scene activity yet.
- `AUTO TARGET ? · EMBEDDED IN ROOM SCENES` — crate-like derelict room resources are visible, but the target containers are nested inside them; use the asset calculator.
- `AUTO TARGET N ... LIVE` — reserved for a future directly proven spawned-instance path.

Generic names containing `crate` or `locker` are never promoted to an automatic crate count. This prevents the tool from turning decorative props or unrelated player-build assets into false positives.

## Why v0.3.8 pivots to asset extraction

The known 51-target system on v0.3.5 produced:

- 459 active spawned-node probes;
- 1,259 scene-probe events;
- 1,184 resolved resource names;
- 19,238 runtime handle→resource-name entries;
- 172 unique scene handles;
- no exact top-level `ABAND_CRATE_M` / `FOOTLOCKER` instance.

Only one crate-named dungeon scene was observed while actually traversing the derelict: `MODELS/SPACE/POI/DUNGEON/CARG/CORNER_CRATES00.SCENE.MBIN`. That is sufficient evidence to stop iterating blind top-level hooks and inspect the current room-scene contents directly.

`Prepare-Crate-Assets.cmd` automates that inspection path with HGPAKtool + MBINCompiler, then immediately reuses the latest Surveyor session.


### v0.3.8 crate-target discovery
The v0.3.6 asset pass proved that current dungeon room scenes expose Crew Footlockers directly but do not expose the desired large Salvage Crate as `ABAND_CRATE_M` or the previously assumed `CRATEM_PLACEMENT` scene alias. Do not treat the v0.3.6 `19` prediction as the complete target-container total.

If `Prepare-Crate-Assets.cmd` has already been run, use `Analyze-Existing-Crate-Assets.cmd`. It does not require another derelict run. It analyzes the existing `%LOCALAPPDATA%\NMSDerelictSurveyor\asset-work-v1\extracted` cache plus `latest.json` and writes `crate-target-discovery.json`. Send that JSON back for the next reverse-engineering step.

A fresh `Prepare-Crate-Assets.cmd` run additionally extracts the current base-building object/part tables and `FREIGHTERDUNGEONSTABLE.MBIN`, so target IDs can be mapped from current game metadata instead of relying on hard-coded scene aliases.