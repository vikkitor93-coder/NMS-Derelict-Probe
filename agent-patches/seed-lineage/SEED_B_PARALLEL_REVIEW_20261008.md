# Seed-B review of the 2026-10-08 parallel run

The sole source for results of run `20261008T130233Z-755d4c43` is the combined report inside the user-attached 0.3.62 **local candidate** ZIP: `research/parallel-action-tests/20261008T130233Z-755d4c43/combined-results.json`. Its SHA-256 matches `research/LATEST_PARALLEL_ACTION_TEST.json`: `12035c7362e77363af084bc24254c7b013edecba6ca9015f1d3c6985ea527eda`. The run completed eight offline actions from a start-of-run saved-evidence snapshot; the ninth, an upload, was disabled. It did not attach to NMS or record a new game event. This note does not publish the pointer or report to GitHub.

## Seed-lineage findings

- Generation and asset outputs use saved session `20261006T223811Z_0001BF0004E84EFD`; seed-function analysis uses `20261002T213047Z_00001A0004E84EFD`; upstream-caller analysis uses `20261004T151219Z_0001BF0004E84EFD`. These are distinct observations and cannot be joined into one live call chain by matching a candidate RVA.
- The asset model for CARGO_FLOATERS predicts 43 target containers (30 salvage crates and 13 footlockers) among 164 resolved scene instances. It is a prediction, separate from the historical pre-7.05 physical 35 and post-update user-observed 16. The offline repeated-address comparisons support stability within their saved records, not new traversals.
- The saved exact-root-caller extraction identifies current call bytes `02C08607: FF 52 10`, return `02C0860A`. The owner `+0x10` read was zero at entry and root add. It was not a pre-call slot read and does not resolve the call target.
- The resolver analyzed a separate older sample (`02C04977`, return `02C0497A`) and found zero matches for candidate `00634BC0`. It cannot be combined with the current exact caller to name a dispatch target.
- The seed-function result describes an older saved session and reports no descriptor writes in its selected code window. This does not rule out upstream descriptor construction. The upstream caller result found no direct rel32 reference to its candidate in its own saved session; it does not establish the current root constructor.

## Independent current-executable trace and remaining boundary

Separately from the combined run, read-only disassembly of the user-supplied current `NMS.exe` (SHA-256 `13d5060d4efb9d2a6a6b1b349bc4257231056cc2a055df4bb15d816262cc3499`) maps the old logical entry label to current `0063A6D0`. The descriptor wrapper previously labeled `00637C40` maps to `00639A70`; its two callers are `01688764` and `016888D2` and use zero seed templates. The wrapper previously labeled `00637660` maps to `00639490`; its callers are `001B2CF9`, `02D08081`, and `02D08898`. The latter two receive a descriptor source through a runtime stack argument. The constructor at current `00639610` copies fields into owner `+0x128`. None of these static paths identifies the exact live root owner's constructor or derives `5B4AE67D9C2A8F61` from universe address `0001BF0004E84EFD`.

An isolated read-only constructor-capture variant was compiled locally from 0.3.60, but has no live validation and is not proposed for main. The next useful evidence is a short, read-only capture tying constructor object identity to a root resource event on the current executable. A full derelict traversal is unnecessary. Until such evidence exists, root seed derivation and indirect dispatch remain open.
