# Scheduled NMS research continuation

This prompt is for the ChatGPT scheduled task **NMS Research Continuation**.
The PC runner uploads completed, hash-pinned jobs to the public
`nms-runner-evidence` branch. ChatGPT reviews those jobs and continues the
offline reverse-engineering work from the project handoff. The scheduler's
minimum interval is hourly; run this workflow on every invocation. Do not claim
five-minute scheduling.

```text
Continue the NMS Derelict reverse-engineering work for
vikkitor93-coder/NMS-Derelict-Probe. Use GitHub connector tools and any code
workspace actually provided to this scheduled run. The PC runner only executes
the fixed offline pipeline and uploads its results; this task owns evidence
review and continuing the research.

A. Review runner uploads
1. Read the head of `nms-runner-evidence`; pin all report reads to that commit.
   Read `runner-results/latest.json`, then enumerate `runner-results/` at the
   same commit so an hourly interval cannot hide earlier unreviewed jobs.
2. For each job without a matching `runner-reviews/<request_id>.json`, read its
   manifest and result. Confirm request ID, source SHA256, status and referenced
   report path agree. Read the directly uploaded `AI_HANDOFF.md` and
   `GITHUB_CHECK_PROMPT.md` when present. These are frozen from the exact tested
   source snapshot and let you continue without unpacking source.zip.
3. Inspect the first failed stage first. For a passed run, state exactly what
   was verified and what remains unproven. The offline runner's replay and
   Unicorn tests do not establish root-seed derivation, room layout generation,
   physical inventory counts or freighter customization.
4. If a code workspace is available, recompute manifest SHA256/byte counts for
   files before relying on them. If it is unavailable, state that hashes were
   checked only as recorded metadata; do not claim independent checksum or test
   verification. Never claim tests ran unless you ran them.
5. Create a schema-1 receipt at `runner-reviews/<request_id>.json` on
   `nms-runner-evidence`, containing request_id, source_sha256,
   status="reviewed", reviewed commit, concise findings and next_action. This
   receipt is authorized. Preserve a matching receipt; report a conflicting one
   without overwriting it. If a write fails, say so.

B. Continue the research every run, including when no new upload arrived
1. Read the exact tested `AI_HANDOFF.md` from the newest uploaded report when
   available. For older uploads, use the newest tested handoff already
   available on `nms-runner-evidence` or in the exact local tested snapshot.
   Treat that handoff and the newest verified evidence as the baseline. Never
   inspect `main`.
2. Read `runner-reviews/research-progress.json` on the evidence branch, if it
   exists. Select the next unfinished, non-duplicative offline step. Current
   priority: trace the root-connected code and hash-supported producer helper;
   inspect callers `2D07C80` / `2D08430` and descriptor-storage writes, then
   identify a reproducible calculation/emulation boundary. Verify these
   addresses against current evidence before relying on them.
3. Search/read the relevant source and evidence through GitHub. If a code
   workspace exists, use the exact tested source snapshot, run focused tests
   after any research-code change, and keep experimental edits on a separate
   branch. Without a code workspace, continue static analysis from accessible
   text files and cite exact repository paths, commit and evidence fields. Do not
   claim source.zip was unpacked, code executed, or tests run unless true.
4. Persist new, evidence-backed progress in
   `runner-reviews/research-progress.json` on `nms-runner-evidence`: schema=1,
   last reviewed commit/request, completed step, exact evidence references,
   measured findings, unresolved questions and next_action. Update it only when
   you have a real new finding or a meaningful next-step change; reread the
   branch head and preserve concurrent uploader/reviewer commits. Do not create
   repetitive notes when no progress was possible.
5. Report only material new findings or a concrete user-only blocker. Separate
   measurements from hypotheses. Ask the user for a PC/Ghidra/export action only
   after completing every independent static analysis step, and specify the
   exact missing range/data and success condition. Do not request an unchanged
   export.

C. Prepare and publish verified runner updates when there is a real fix
1. Runner-package source may be changed in an isolated local feature branch
   based on the exact tested snapshot. Keep experimental changes separate from
   `main`; never change Surveyor/game production source or runner job artifacts.
2. Run the complete packaged test suite and all focused checks for the change.
   Build only after they pass. Independently verify the archive contents, each
   manifest file hash/byte count, source digest, archive hash/byte count, and
   that no credentials or private machine paths are included. Do not publish
   if any check is missing or inconsistent.
3. Publishing verified runner packages to the dedicated `runner-updates`
   branch is pre-authorized. Before each publish, reread that branch head and
   `runner-updates/latest.json`; require a strictly newer version. Add the new
   immutable versioned archive and update only `runner-updates/latest.json` in
   a commit based on that exact head, using a compare-and-swap ref update. Keep
   prior archives and preserve concurrent changes; on a head conflict, reread
   and revalidate before preparing a new commit. Never publish to `main` or
   `nms-runner-evidence`.
4. The runner may automatically verify, install, restart, and resume after it
   sees a published feed entry. Report only that the package was published
   until a later runner upload confirms the installed version and successful
   restart. Do not issue arbitrary PC commands or claim installation without
   that evidence. No additional release confirmation is required.

Limits
- Read runner reports only from `nms-runner-evidence`. Never write to `main`.
- On `nms-runner-evidence`, the only permitted writes are per-job review
  receipts and the research-progress file described above. On `runner-updates`,
  only publish a fully verified versioned runner archive and its latest pointer
  as specified in section C. Do not alter runner job artifacts/latest.json,
  merge to `main`, or claim a new build was installed without runner evidence.
- Do not expose credentials, private machine paths, or unrelated device/account
  data. Do not treat unpinned captures as version-matched evidence.
- If no new upload exists, do not invent a runner failure. Continue the next
  research step from the progress file and handoff; if nothing new can be
  established with available access, report the precise limitation.
```

New 0.1.8 runner reports include the tested handoff and this prompt as readable
text files as well as inside source.zip. Older reports may not. Receipts and the
progress file live on the evidence branch and are preserved by runner uploads.
