# Seed-Lineage public system-seed comparison — 2026-10-09

## Source and provenance

This comparison uses the third-address candidate only from the SHA-256-verified automatic saved-session report `research-uploads/20261009T015948Z-automatic-research-batch-20261009T015908Z-d4d6ae3f-50cb03/reports/20261009T015909Z-77532ce2/combined-results.json` (SHA-256 `721427df0b4d95a3bb0cfee5ececa3fdb5517713c0abd998fca4802e3ced994b`). Its batch index is `research-uploads/20261009T015948Z-automatic-research-batch-20261009T015908Z-d4d6ae3f-50cb03/batch-results.json` (SHA-256 `b1ea5afaee7aa2f6d2a49bd48c28b73a67d59a9aad3f6b53702d41fe2b0ea18a`). The report records address `0001680006607CAC`, root resource `MODELS/SPACE/POI/DUNGEON.SCENE.MBIN`, candidate `2139770A2614E3DC`, and one observation. It does not include an NMS.exe hash, so executable identity is unverified. The same report's caller and seed-function outputs cite the earlier `0001550006607CAC` session and are not joined to this sample.

## Calculation and checks

The address-derived system-seed calculation follows the pinned public `indexPrimedPRNG` implementation from [hadsh/nms_namegen at 52ad48affaa4089c8f487a470a888dc9b7a650aa](https://github.com/hadsh/nms_namegen/tree/52ad48affaa4089c8f487a470a888dc9b7a650aa), specifically [iprng.py](https://github.com/hadsh/nms_namegen/blob/52ad48affaa4089c8f487a470a888dc9b7a650aa/nms_namegen/iprng.py) and [system.py](https://github.com/hadsh/nms_namegen/blob/52ad48affaa4089c8f487a470a888dc9b7a650aa/nms_namegen/system.py). The implementation was independently reproduced with fixed-width JavaScript BigInt arithmetic. Its low 32-bit output matches both lane anchors:

- `00001A0004E84EFD -> B006BAB6`
- `0001550006607CAC -> 9E1A7905`

For the third address it returns **`8A6EF089`**. This is the public 32-bit system seed. The saved report's separate 64-bit dungeon-root candidate is **`2139770A2614E3DC`**. The calculation does not explain or derive that root candidate.

## Evidence boundaries

The result is an offline address-to-system-seed comparison, not proof that the pinned public implementation matches the current NMS executable. The third root candidate remains a one-observation measurement with no executable hash and no same-session caller → upstream → seed-function chain.

The combined report's asset-derived 43-target CARGO_FLOATERS prediction remains separate from its generation-measurement `target_container_values`; this comparison treats neither as a physical traversal count. The MEDI 14-target asset prediction remains separately labeled as well. The zero `+0x10` read and separate resolver sample remain unresolved and are not used in this calculation.

## Next

Continue offline review for an independently supported address-to-root-seed link. When the 1.0.5 request is integrated, use the already-saved third-address sample for the caller → upstream → seed-function chain; no new traversal is required unless the saved sample is unavailable.
