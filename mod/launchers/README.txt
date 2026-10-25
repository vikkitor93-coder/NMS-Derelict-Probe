NMS Derelict Minimap
====================

An in-game minimap for derelict freighters in No Man's Sky. It draws the freighter's real layout around you
(you are the fixed dot, the map moves), counts the crates and footlockers in the whole freighter and in your room,
can show which containers hold a Salvaged Frigate Module, and can show the end-room reward.

Supported game version: NMS 7.05 (Steam). After a game update the overlay says "unsupported NMS version" instead of
showing a wrong map; look for a new version of this mod.

Install
-------
1. Unzip this folder anywhere (not inside the game folder).
2. Double-click Install.cmd. It builds the map data from YOUR copy of the game (a few minutes, once), then asks how
   the minimap should start.
3. In No Man's Sky use borderless windowed mode (Settings - Display). The map appears by itself when you are inside
   a derelict freighter and the game is the active window.

Keys (global)
-------------
F7 / F8 zoom in / out        F9  show / hide the end reward (hidden until you press it)
F5  show / hide frigate modules   F10 hide / show the info panel
F11 real geometry / schematic     F6  hide / show everything
Ctrl+Alt+arrows  move the window

What it does and does not do
----------------------------
* It only READS the game's memory (player position and system address). It never writes to the game, injects
  anything, hooks the game, or changes game files. Reading another program's memory is also what game trainers do,
  so it is your call whether to run it next to the game; it has only been tested in normal single-player play.
* It uses no network. Nothing is sent anywhere, nothing is downloaded after you have this folder.
* Game data (meshes, tables) is built from your own install on first run and stays in this folder. Nothing from the
  game is included in the download.
* Because it reads another program's memory, some antivirus programs may question it. The source is plain Python
  (no packed or obfuscated files) in NMS-Derelict-Probe\minimap. If your antivirus complains, check the files against
  MANIFEST.json, or add this folder as an exception.

Starting and stopping
---------------------
* "With Windows": a shortcut named "NMS Derelict Minimap" is put in your Startup folder. The program sleeps until the
  game runs. It removes the shortcut itself if the game is no longer installed (found missing on 3 different days over
  at least a week) or has not been started for 30 days, and tells you.
* "With the game" (Steam launch option): nothing runs in the background. Paste the line the installer shows into
  Steam - No Man's Sky - Properties - Launch Options.
* By hand: Start-Minimap.cmd.
* Uninstall: Uninstall.cmd, or Windows Settings - Apps - NMS Derelict Minimap. Then delete this folder.

Folder
------
python\                      the Python runtime this mod uses (python.org build, nothing else installed on your PC)
NMS-Derelict-Probe\minimap\  the program        NMS-Derelict-Probe-analysis\  caches built on your PC
NMS-Shipwright\              star-system generator (MIT licence, see LICENSES)   LICENSES\  third-party licences
