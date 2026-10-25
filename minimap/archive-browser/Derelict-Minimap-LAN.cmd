@echo off
rem ARCHIVED phone/LAN version of the minimap. Not maintained; use tools\Derelict-Minimap-Overlay.cmd.
title Derelict Minimap (local network, archived)
cd /d "%~dp0..\.."
python -I minimap\archive-browser\server.py --host 0.0.0.0 %*
if errorlevel 1 pause
