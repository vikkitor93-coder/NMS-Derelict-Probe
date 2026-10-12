# Derelict offline experiment — AI handoff

## Purpose and state (2026-10-11)

- Experiment 0.1.15; standalone experiment-only ZIP, root `derelict_offline/`.
  Isolated from Surveyor 0.3.75 / Probe 0.3.42. No production application,
  game installation, updater or existing Unspottable runner was edited.
- Goal: address/POI → root descriptor → parameters/layout → containers.
  Implemented: public system seed (NOT root), captured-scene replay, RNG
  arithmetic, empty-vector descriptor copy and identifier swap-delete.
  Root formula and room generation are unresolved; no freighter feature.
- User confirmed 0.1.3 installer worked on Windows. Runner automates local
  execution; optional GitHub evidence uploads added for scheduled ChatGPT checks.
  PC logs confirm Unicorn and failed-run upload;
  job failed at Windows symlink privilege test, now repaired. Version 0.1.10 adds
hash-verified package polling and restart. Version 0.1.12 remembers completed
  checks by input hashes, caches the Unicorn startup smoke only while its pinned
  package bytes match, and saves the selected NMS.exe path/hash locally. See
  RUNNER.md and GITHUB_CHECK_PROMPT.md.
It also migrates the earlier incorrect update-feed URL during bootstrap so the
hourly updater can read the published feed layout.
Version 0.1.13 explicitly disconnects standard input for runner and GUI child
processes, fixing Windows launches when the parent has no valid inherited input handle.
Version 0.1.14 adds a cross-platform regression check for both spawn paths.
Version 0.1.15 updates the scheduled-review prompt with a restricted,
pre-authorized release process for fully verified runner packages on the
dedicated update branch. It forbids inspecting `main`, requires a passing full
test suite and independent package/hash checks, and requires a compare-and-swap
feed publish. Publishing alone does not prove the PC runner installed or
restarted; confirm that only from a later upload.

## Scheduled AI continuation and latest runner evidence

- The ChatGPT task **NMS Research Continuation** is configured on the connected
  GitHub evidence branch. The scheduler supports hourly checks; it cannot run
  every five minutes. Its complete operating contract is in
  `GITHUB_CHECK_PROMPT.md`.
- Runner uploads provide `AI_HANDOFF.md` and `GITHUB_CHECK_PROMPT.md` as direct
  text artifacts, frozen from the same tested snapshot as `source.zip`. This
  lets the scheduled task read current directions without opening the archive.
  The task reviews every unreceipted job and advances one offline research step
  on each run, even if no new PC upload arrived. It writes per-job review
  receipts and `runner-reviews/research-progress.json` on the evidence branch;
  it may separately publish a fully verified, versioned runner update to
  `runner-updates` under the checks in `GITHUB_CHECK_PROMPT.md`.
- Latest verified upload at handoff: request
  `e03d1d8887864ce186e2e0042127cde0`, evidence commit
  `f4567f7e0410b3be5c1712762845d6d21e844c4e`, source SHA256
  `da26dca1e612d586b15be8d2c0d1749e43e9a028e33046fd2d45ae779b358caa`, runner
  version 0.1.13. Its result says `passed`; replays and 4,040 Unicorn
  comparisons are recorded, but root generation/layout remain unverified. The
  next task must reread the evidence branch head and manifest before treating
  this snapshot as current.
- Research priority: trace root-connected code, producer-helper data flow, caller
  sites `2D07C80` / `2D08430`, and descriptor-storage writes. Verify addresses
  against current evidence before use. Identify the smallest reproducible
  calculation/emulation boundary. Unknown globals/TLS state must remain explicit.
  Ask for PC/Ghidra evidence only after independent static work is exhausted.

## Architecture, entry points and dependencies

- `start.py`: standalone bootstrap; works in renamed folder. `run.py`,
  `build_corpus.py`, `prototype.py`: diagnose/replay/corpus/benchmark.
- `rng_kernel.py`, `unicorn_check.py`: direct arithmetic / bounded x64 emulation.
  `code_evidence.py`, `export_evidence.py`: validation/read-only bounded export.
- `local_runner.py`: watcher, fixed subprocess pipeline, immutable snapshots,
  dependency health check, status/results and source/evidence packaging.
  `runner_protocol.py`: NMS request schema and atomic publication/source digest.
- `github_exchange.py`: optional gh CLI transport, config/receipts, allowlisted
  artifacts, bounded retries. `Setup-GitHub.cmd`: winget install/sign-in/setup.
  Credentials stay with gh CLI; CLI installation is external to this ZIP.
- `runner_gui.py`: native Tk status/controls/live activity/developer export;
  `gui_process.py`: owned subprocess, bounded in-memory queue, cancel/cleanup.
  Start-Runner.cmd defaults to GUI; explicit arguments preserve console behavior.
  Start-Runner-CLI.cmd and start.py gui --no-autostart are additional entry points.
  No third-party GUI dependency; standard Python Tcl/Tk required for the window.
  Runner 0.1.12 persists completed-check keys locally so restarts do not rerun
  the full test/replay/1,000-comparison pipeline for unchanged inputs. Explicit
  Run check requests still execute. The startup Unicorn smoke result is reused
  only while hashes of the pinned interpreter and Unicorn package match.
  NMS.exe selection is locked locally by resolved path plus SHA-256; edits or a
  missing file block use until it is selected again. This private setting is
  excluded from logs and uploads.
- `windows_job.py`: unchanged containment helper reused from local runner
  v0.1.9; Windows Job Object / POSIX process-group cleanup on cancel/timeout.
- `install_runner.py`: stdlib permanent install; default Path.home()/Documents/
  NMS Runner. start.py install and Install-Runner.cmd are new entry points.
  All Windows operation launchers route there before starting; Python commands
  remain portable. Both source/destination worker locks prevent active updates.
  Hash staging, source backup/restore, newer/equal-version conflict checks;
  target runtime state wins, missing data copy resumes on retry. A moved healthy
  Unicorn package is reused in a newly rooted venv; source originals retained.
- `install_unicorn.py`: private optional environment; installer build marker
  remains 0.1.3. `package_experiment.py`: explicit source allowlist.
  `RUNNER.md`, `LOCAL_WORK_PROMPT.md`: operation / local AI integration contract.
- Python 3.10+, base stdlib; optional pinned unicorn==2.1.4. `.unicorn-venv`
  excluded from packages. Seven analyzer tools are unchanged dependencies.
  `fixtures/manifest.json` preserves original source/fixture provenance.

## Contracts, data and critical flow

- Corpus/evidence/protocol/log schemas remain 1. Unsigned 64-bit hex seeds,
  observed flags preserved. Production protocols/saved formats unchanged.
- NMS request has exactly schema=1, request_id=32 lowercase hex,
  action=`offline-check` or `offline-check-and-export`, source_sha256=64 hex.
  Atomic `requests/ready.json`; no command strings/paths. Never redirect
  Unspottable `build-and-h2` requests to this separate NMS worker.
- Single-instance lock → copy/rehash source → source ZIP → focused tests →
  replay → code validation → Unicorn comparisons → optional bounded export →
  result/evidence ZIP. Stop on first failure. Changed source marks result stale.
- Claimed jobs survive crashes and require review; IDs cannot be reused.
  Automatic stable changes run once; explicit requests may intentionally retest.
- `.local/status.json`, `latest.log`, `latest-result.json` hold latest state.
  `reports/<request_id>/` retains result.json, exact tested source.zip and
  runner-evidence.zip. Logs contain allowlisted stages/codes, no personal,
  machine-path/device/network telemetry. Raw child output is console-only.
  At 100 report folders stop for cleanup instead of deleting evidence.
- Optional --exe is read-only and pinned locally by resolved path plus SHA-256.
  The path is excluded from reports/uploads; a missing or changed EXE blocks
  export until reselected. Export cache keys include exporter input and EXE
  hashes; cache ZIP is rehashed before reuse. Game EXE is never copied into
  deliverables. Unchanged exports do not supply additional research bytes.
- Uploads default off; .local/github-config.json enables fixed evidence branch
  nms-runner-evidence in vikkitor93-coder/NMS-Derelict-Probe (public), or a repo
  explicitly selected during setup. Never write main. Artifact limits 4 MiB/file,
  8 MiB/job; only result/log/stage JSON, evidence/source ZIPs. Full EXE/private
  environment/raw child output/config/secrets excluded. No token read by Python.
- One git tree/commit publishes immutable job files + runner-results/latest.json
  together; non-forced branch advance rejects conflicts. Manifests contain source
  hash/status/file SHA256/size. Matching ID is idempotent, conflicting ID blocked.
  Preserve base tree, including AI review receipts. Separate local upload ledger;
  no change to research results on transport failure. Three persisted attempts/job,
  minute idle polling; failure blocks later uploads, retains evidence, no rerun.
- Scheduled review prompt pins reads to a commit and records runner-reviews/ID.json
  for deduplication. It also records a bounded research-progress ledger so each
  hourly run can continue from prior findings. A receipt does not implement remote
  coding or install the next build.
- Additive local runner-control.json schema 1: {schema:1,paused:boolean}. Pause
  waits after active work, preserves ready requests, uploads still poll; --once
  ignores pause. Resume unsets it. GUI Start clears pause; request schema unchanged.
- Raw subprocess output now streams live without saving it. Expected dependency
  health failure is hidden and automatic repair explained. Installer remains
build 0.1.3 (unchanged installer code); current launcher/worker/GUI are 0.1.15. Symlink
  rejection test simulates the link flag, so Windows privilege 1314 is avoided.

## Research evidence and constraints

- Four projections: roots 9C2818C7FE094FC8 / 2A41B0E7EF42A1F7; repeat asset
  totals 37 / 23. Historical captures lack captured full version/hash; keep
  quarantined. 7.05 is user context only; never retroactively pin captures.
- Latest offline-code-evidence-20261011-v0.1.2.json: 149 ranges / 103,256 bytes;
  hashes and four root-call windows verified. Exporter-reported EXE SHA256
  13d5060d4efb9d2a6a6b1b349bc4257231056cc2a055df4bb15d816262cc3499,
  image base 140000000, size 88,560,712. Full EXE not uploaded/rehashed here.
- 4,040 Unicorn comparisons: 1,009 seed initialization, 1,004 state/output,
  1,024 empty-vector copies, 1,003 deletions; zero mismatches. RX code,
  private stack/data, clean state per case, instruction/time budgets. Unknown
  imports/memory fail. ONLY external model: 033E4B4C for zero byte length;
  refuses nonzero. Supplement 406 vector-helper bytes from prior same-identity
  export after validation. Nonempty copy fails at global RVA 05292041; no
  invented allocator/TLS model. Kernel tests do not prove dungeon generation.
- 00227A40 copies +10/+18 and +20/+28 seed fields; 00227620 manages 32-byte
  identifiers; 00641160 builds identifier/hash. None derives the root.
  Owner 639BE0 → 639610 → 227A40 forwards input argument five; wrappers
  639490 / 639A70 forward descriptors. Caller sites 1B2CF9, 1688764, 16888D2,
  2D08081, 2D08898 decoded; last pair forwards argument six into
  2D07C80 / 2D08430. Upstream producer and live derelict branch unknown.
- Shipwright f89691ed037edf437a7406c176aa6b96e654d314 labels matching 0062E2B0
  palette-related. Semantic inference only, not dungeon proof; independent
  code here. Table Rooms=7 vs observed 10/9 groups unresolved. Asset totals
  are not physical inventory/topology proof. No generation speedup established.

## Run, debug and verification

- Windows: install/migrate → permanent-folder Start-Runner.cmd. Reuses healthy private environment;
  setup only if needed. Ctrl+C stops. NMS.exe stays pinned to the selected path/hash locally.
- Developer: `python start.py runner --status`, `runner --once`,
  `runner --request offline-check`, `diagnose`, `code`, `test`, `emulate`.
  Source export: `python start.py package --out complete-source.zip`.
- GitHub: Setup-GitHub.cmd once, then restart runner. CLI controls:
  `python start.py github --retry` (stop runner first); `github --disable` then
  restart. Retry resets only failed upload counts; receipts persist across runs.
- 100 experiment tests passed with Unicorn on Linux; 18 runner regressions
  cover schema, atomic claims, snapshots, stale/failed/cancelled runs, timeouts,
  exclusive lock, export cache, limits and packaging privacy. 14 transport tests
  cover atomic visibility, conflicts, lost replies, retry limits, restart receipts,
  bounded artifacts, default-off behavior and upload failure without rerunning.
  Network writes simulated; no live upload/Windows sign-in tested here.
- Twelve new permanent-folder regressions cover default path, retained state,
  idempotence, retry, backups, partial-write rollback, both worker locks,
  downgrade/same-version conflicts, unrelated/nested/link folders and CMD routing.
- Seven GUI/control regressions: pause protocol, pending requests preserved,
  quiet dependency probe, actual live output before exit, owned start/stop,
  pythonw interpreter selection and non-spinning idle/error status.
- Real missing-Unicorn private environment automatically repaired using the
  official local 2.1.4 wheel, with visible progress and x64 instruction check.
  Windows GUI cancellation/launcher must still be confirmed on PC.
  Linux desktop smoke passed: actual window Start, Pause/Resume, queued full
  check, Developer panel and graceful Stop. Uses an isolated display; no test
  display dependencies are included in the source ZIP.
- 0.1.7 real installation smoke passed: new Documents/NMS Runner root,
  pinned package reuse in a fresh correctly rooted venv, report/receipt retention,
  idempotent reinstall and full installed-folder one-shot (99 tests / 4,040
  comparisons). No live network writes. Windows migration remains untested here.
- Previous 0.1.4 real one-shot pipeline passed on Linux: source ZIP, 66 tests,
  four replays, hashes, 4,040 comparisons. 0.1.5 real one-shot also passed
  on Linux: source ZIP, current experiment suite, four replays, hashes and
  4,040 comparisons. Current 0.1.6 one-shot and the GUI-triggered full pipeline
  passed too. No network upload was enabled here; STATUS.json records gates.
- New Windows GUI launcher/cancellation behavior cannot be executed here: first GUI run
  needed. Previous full application suite in 0.1.3: 303 run / 285 passed /
  18 display skips. Not rerun in this experiment-only package.

## Migration, rollback and exact next action

- 0.1.8 adds direct tested handoff/prompt artifacts to each report so the scheduled
  AI can continue without unpacking source.zip; the project/source protocols are
  unchanged. 0.1.7 added permanent-folder installation; research/protocol/data schemas are
  unchanged. Source-only backups are made on replacement; stop and restore one
  into the permanent folder to roll back, retaining runtime data/dependencies.
  Original migration source is preserved; keep it until the new run succeeds.
- Research-module changes picked up in snapshots; runner/bootstrap changes
  require restart. No PC-local AI/scheduler/chat connection is installed. The separate ChatGPT
  scheduled task is active. Use an authorized local Work/Codex session on this
  folder + LOCAL_WORK_PROMPT.md;
  never claim the unattended AI connection is already active.
- User: stop old worker and close window; copy new ZIP's derelict_offline contents
  over the existing runner (retain .local/.unicorn-venv/reports); open new
  Start-Runner.cmd. It installs/migrates to %USERPROFILE%\Documents\NMS Runner
  and launches there. Future launches/updates keep that default. Confirm the
  first Windows migration/GUI check; existing GitHub setup is reused.
  The ChatGPT scheduled task continues research hourly from uploaded handoffs;
  five-minute cadence is unsupported. No next-build auto apply.
- AI: each scheduled run reviews all unreceipted PC jobs and advances one
  evidence-backed offline research step, even when there is no new upload. Start
  with root-connected code, producer-helper data flow, callers of 2D07C80/2D08430,
  and descriptor-storage writes; validate addresses against current evidence.
  Update the targeted exporter only when specific missing bytes are named; never
  request another unchanged export. Do not invent globals to claim generation.
