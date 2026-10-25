@echo off
setlocal
cd /d "%~dp0"
title NMS Derelict Minimap - install
echo.
echo  NMS Derelict Minimap - install
echo  ------------------------------
echo  Reads No Man's Sky's memory (read-only) to draw a map of the derelict freighter you are in.
echo  Nothing is injected into the game, nothing is sent over the network.
echo.
if not exist "python\python.exe" (
  echo  python\python.exe is missing - the download is incomplete.
  pause
  exit /b 1
)
echo  Step 1 of 2: first-run setup (builds the map data from YOUR copy of the game; a few minutes, once).
echo.
"python\python.exe" -I "NMS-Derelict-Probe\minimap\first_run.py"
if errorlevel 1 (
  echo.
  echo  Setup did not complete - see the message above.
  pause
  exit /b 1
)
echo.
echo  Step 2 of 2: how should the minimap start?
echo.
echo    [W] With Windows. A shortcut "NMS Derelict Minimap" is added to your Startup folder. The program sleeps until
echo        No Man's Sky runs, and removes the shortcut itself if the game is uninstalled or unused for 30 days.
echo    [S] With the game, through a Steam launch option. Nothing runs in the background. You paste one line into Steam.
echo    [N] Neither - start it yourself with Start-Minimap.cmd.
echo.
choice /c WSN /n /m "  Your choice (W/S/N): "
if errorlevel 3 goto done
if errorlevel 2 goto steam
"python\python.exe" -I "NMS-Derelict-Probe\minimap\lifecycle.py" install
start "" "python\pythonw.exe" -I "NMS-Derelict-Probe\minimap\overlay.py"
goto done
:steam
"python\python.exe" -I "NMS-Derelict-Probe\minimap\lifecycle.py" steam-line
echo.
echo  (Copy the line above exactly, including the quotes and %%command%%.)
:done
echo.
echo  Done. In No Man's Sky use borderless windowed mode. Hotkeys: F7/F8 zoom, F9 end reward, F5 frigate modules,
echo  F10 hide info, F11 map style, F6 hide all.
echo  Uninstall any time: Uninstall.cmd, or Windows Settings - Apps - NMS Derelict Minimap.
echo.
pause
