@echo off
rem Live derelict minimap drawn on top of NMS (click-through). One program: no server, no network.
rem NMS must be in borderless windowed mode. It appears by itself when you are at the system's derelict.
rem F7/F8 zoom, F9 reward, F5 frigate modules, F10 hide info, F11 map style, F6 hide all, Ctrl+Alt+arrows move it.
rem Close this window to stop it.
title Derelict Minimap Overlay
cd /d "%~dp0.."
python -I minimap\overlay.py %*
if errorlevel 1 pause
