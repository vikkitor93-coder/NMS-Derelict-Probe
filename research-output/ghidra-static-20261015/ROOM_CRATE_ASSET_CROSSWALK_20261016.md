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

## Exact 7.05 asset linkage and remaining limits

The local `NMSARC.EntitySceneMBIN.pak` hash is `58958536E58DFAEB81E0423B5508C7D3DBF3713BAC09E857577FEB275D9F2627`. D extracted the referenced room component scenes and both dungeon prop scenes from that exact pak to read-only scratch under `%LOCALAPPDATA%\NMSDerelictSurveyor\exact705-readonly-audit-20261016\members`. All 23 room-scene member hashes match their cached raw MBINs; for example, `CARG/CORNER_CRATES00.SCENE.MBIN` is `195C852F2ADC3833A3E9AA22BC725B40E85F801528F837E3670A0517F5319D82` in both locations. Thus the cache's room files used by the join are byte-identical to the current 7.05 archive members.

The exact scene members `MODELS/PLANETS/BIOMES/COMMON/BUILDINGS/PARTS/BUILDABLEPARTS/SPACEBASE/PROPS/CRATEM.SCENE.MBIN` (SHA-256 `D2C4C2CD23D58BF2D26BD68B8B6A0ADC146CCB9B38B6CEF52072A188039A393E`) and `.../SPACEBASE/PROPS/FOOT_LOCKER.SCENE.MBIN` (`42979C04AB8019443A3A7D1E20055DC78D83BF806EE7E4B98E4896111F633FC0`) attach entities from `NMSARC.Precache.pak`: `.../SPACEBASE/PROPS/CRATEM/ENTITIES/CRATEM.ENTITY.MBIN` (`F15B654EB22FC570A66155CC9E25E01721B0C0B13B36850EC7EB3F496B1FEAE0`) and `.../SPACEBASE/PROPS/FOOT_LOCKER/ENTITIES/FOOTLOCKER.ENTITY.MBIN` (`28FA635658BCBDC4005B936784EF51B59793461110507FAB619F2FDECDC89AB3`). Both exact entity members, converted with the already-installed MBINCompiler 7.04.1-pre3 (MXML header 7.04.1.3), have byte-identical normalized `GcSimpleInteractionComponentData` subtrees (SHA-256 `7C5CAFC61390C08F80CF9E7389F8DB5BE130AC69819EAD7062A64111DBA80515`). The interpreted fields are `SimpleInteractionType=GenericReward`, `Id=R_ABAND_CRATE`, `RewardOverrideTable` empty, `UsePersonalPersistentBuffer=true`, and `ReseedOnRewardSuccess=false`. The local parser successfully converted the 7.05 members; however its schema/type interpretation is still from compiler 7.04.

The similarly named decoration scenes/entities are distinct. Their entity MXML says `SimpleInteractionType=Interact` with empty `Id`; they are not evidence for dungeon container reward behavior. The room-scene references lead to the spacebase prop scenes, not those decoration aliases. Combining the runtime-observed Room 0..8 child-resource selection with exact 7.05 authored scene refs therefore supports **32 CRATEM and 19 FOOT_LOCKER references configured as GenericReward / R_ABAND_CRATE** for this session. It does not prove that all 51 were instantiated, active, reachable, or paid out during that traversal; saved `scene_probe` has no per-container instance/state observations.

The remaining live discriminator, if a corresponding direct static/runtime path is not found, is one same-seed instance census recording each container instance ID, its Room parent, resource path, and active/present state. A successful interaction is additionally required to establish actual payout behavior. The current probe-source capture-feasibility audit and runtime reward selection traces are still in progress.
