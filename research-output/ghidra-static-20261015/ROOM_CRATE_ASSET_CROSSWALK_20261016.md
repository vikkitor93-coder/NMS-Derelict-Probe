# Room-local container asset crosswalk — 2026-10-16

## Result

An independent join between the saved session `20260929T175122Z_0001550006607CAC.json` and the local `room-crate-index.json` reproduces the model's **32 CRATEM references / 19 FOOT_LOCKER references** for the nine recorded room groups. These are counts of authored child-scene references in the cached scene exports, selected by the runtime-observed room child-scene resources. They are not a live census of active or rewardable containers.

## Pinned inputs

| Input | SHA-256 | What it establishes |
|---|---|---|
| Matching local `NMS.exe` | `13d5060d4efb9d2a6a6b1b349bc4257231056cc2a055df4bb15d816262cc3499` | Executable identity used for the surrounding Ghidra work. |
| Local `NMSARC.Precache.pak` | `A6371A8B2F065ECA33FD306A16CBE2BACA9D4CE75806C71E42F74E1AB9295032` | Current local archive identity; this hash does not by itself prove the cached MXML exports came from this archive. |
| Saved 000155 session | `D83AEBB07E4E14E47F5432A7C2175EC3B71C1BC0D061F650D4C1093ADC4019B9` | Runtime start address `0001550006607CAC`; root `00C9E8DF0327789E` is present in the pre-session trace window; scene stream contains Room 0 through Room 8. |
| Cached `room-crate-index.json` | `B2E1E5C7F4F5273D373FD5DB44049EFB3C84A7C5F6D0F22DC9F2690B93BEF721` | Index of 1,433 dungeon scene exports with node-token-derived authored references. The index has no source-pak/member manifest. |

The cached session's auto-crate summary reports `count=0`, `status=embedded-in-room-scenes`, `confidence=unproven`, and `method=none`; it is a failed/unresolved detection, not evidence that the derelict contains zero containers. The raw session scene stream has 1,115 events and does not identify individual `ABAND_CRATE_M`, `FOOTLOCKER`, `R_ABAND_CRATE`, or `GenericReward` instances. `CRATEM_OPEN.ANIM.MBIN` is an animation resource, not a container instance.

## Reproducible join

The index has 1,441 total scene exports, 1,433 under the dungeon path, and 75 dungeon scene entries with CRATEM/FOOT_LOCKER node references. Its generic placement aliases fail `contains_expected_id`, so the join uses observed dungeon child resource paths and the per-scene authored node-reference counts instead of those aliases.

For every saved `scene_probe` event whose parent label is `Room 0` through `Room 8`, join its exact `MODELS/SPACE/POI/DUNGEON/...SCENE.MBIN` `resource_name` to the same `scene_path` in the index. Summing the index's `salvage_crates` and `crew_footlockers` counts over matched events yields:

| Room | CRATEM references | FOOT_LOCKER references |
|---|---:|---:|
| Room 0 | 0 | 2 |
| Room 1 | 3 | 1 |
| Room 2 | 4 | 0 |
| Room 3 | 0 | 4 |
| Room 4 | 1 | 0 |
| Room 5 | 3 | 0 |
| Room 6 | 17 | 2 |
| Room 7 | 1 | 0 |
| Room 8 | 3 | 10 |
| **Total** | **32** | **19** |

The arithmetic was independently repeated in PowerShell against the pinned session and index; 30 room-child resource events contributed counts. Repeated child resources are counted as separate loaded references; the index counts scene nodes, not runtime entities. The result supports 32/19 as a stronger, room-associated **asset prediction** for this session than an unjoined aggregate model row, but does not promote it to a confirmed physical count.

## Asset linkage and remaining limits

Cached `basebuildingpartstable.MXML` maps `_ABAND_CRATE_M` to the generic decoration `CRATEM.SCENE.MBIN`; `basebuildingobjectstable.MXML` maps `ABAND_CRATE_M` to `CRATEM_PLACEMENT.SCENE.MBIN`. The dungeon room MXML instead references `MODELS/SPACE/POI/DUNGEON/.../SPACEBASE/PROPS/CRATEM.SCENE.MBIN` and corresponding `FOOT_LOCKER.SCENE.MBIN` props. The generic decoration placement aliases do not validate against the dungeon node IDs. The exact nested dungeon prop scene/entity MXML files were missing from the inspected cache, so the attachment of `GenericReward / R_ABAND_CRATE` to these exact dungeon prop instances has not yet been established.

Cached MXML headers identify MBINCompiler 7.04.1.3, while the local game is 7.05. No member-level export manifest currently ties the cached index/MXML set to the verified 7.05 pak. An in-progress offline follow-up is extracting only the referenced dungeon prop scene/entity members from that exact pak using tools already installed locally, then checking their entity/reward configuration. No game state or source files were changed for the crosswalk.

The minimum eventual live discriminator, if the exact pak still cannot prove active instances, is one same-seed instance census that records each container instance ID, its Room parent, and attached interaction/reward ID. A successful interaction is additionally required to establish actual payout behavior. This gate has not been requested while the exact-pak asset route and static reward-table work remain active.
