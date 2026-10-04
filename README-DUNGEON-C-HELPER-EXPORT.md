# DUNGEON-C helper export

This is a complete research build based on the Surveyor 0.3.58 source package. It includes all source dependencies required by the offline runtime-target extractor, the DUNGEON-C lane status/manifest, and the validated callback direct-call inventory.

## Run the helper export

1. Extract this ZIP to a normal local folder.
2. Run `Extract-Runtime-Target-Function.cmd` from the extracted folder.
3. Wait for the success line showing the `.pdata` range, function byte count, and `NMS.exe` SHA-256.
4. In Surveyor, click **GitHub / updates > Upload all saved evidence**.
5. Return to the research chat and write **check**.

The extractor reads the saved exact-root event and the local installed `NMS.exe`. It does not launch NMS, write game memory, or require a derelict traversal. Use this complete ZIP; the GitHub `agent/dungeon-decompile` branch archive omits imported sibling modules.

## Success condition

The newly uploaded `exact-root-caller-code-latest.json` contains `runtime_target_function.direct_call_candidates` and at least one bounded `target_function_body`. These are heuristic call candidates until each call instruction boundary and destination `.pdata` range is matched against the separately published `CALLBACK_DIRECT_CALL_INVENTORY.json`.

If the extractor reports that it cannot find `NMS.exe`, run the command with `--exe "G:\SteamLibrary\steamapps\common\No Man's Sky\Binaries\NMS.exe"` (or the actual installed executable path). No fresh capture or repeated evidence upload is needed before running the extractor.

