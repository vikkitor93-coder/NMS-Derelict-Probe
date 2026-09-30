# AI handoff — NMS Derelict Probe v0.3.25

Read-only NMS.py/pyMHF derelict research project.

User supplied v0.3.24 workflow log proving GitHub integration itself is healthy (gh found/auth OK/repo API OK/push=true). The failing Measure + upload command returned exit 1 before upload because Windows cmd.exe /s /c misparsed the quoted Measure-Derelict-Generation.cmd path.

v0.3.25 fixes this by removing the chained CMD string entirely. _project_action now creates explicit sequential subprocess steps: research command first, upload helper second. PowerShell workflows launch their .ps1 directly; caller extraction launches tools/extract_nms_caller_code.py with the persisted safe Python interpreter. Upload only runs after research returns 0. Normal GUI actions use CREATE_NO_WINDOW.

GUI clipping is also fixed without relying on unsupported wrapping: the single long detail field is exposed as three <=52-character Workflow message rows.

Step-level logging events: workflow_step_started, workflow_step_completed, workflow_step_failed. workflow-diagnostic-latest.txt records the failed step.

Verification: 85/85 tests, compileall, 35 packaged JSON files parse, ZIP integrity passes.

Research state unchanged: known 35-container address 00001A0004E84EFD, root descriptor seed 9256392A2F5A74AC, caller return 00635115 / CALL RVA 00635110.

Next live action: update/install v0.3.25 and click **Extract dungeon caller code + upload**. It should display Step 1/2 then Step 2/2 and complete without opening an empty command window. If it fails, send workflow-diagnostic-latest.txt or workflow-latest.log.
