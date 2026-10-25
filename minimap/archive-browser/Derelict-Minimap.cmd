@echo off
rem ARCHIVED browser version of the minimap (http://127.0.0.1:8766/). Not maintained; use tools\Derelict-Minimap-Overlay.cmd.
title Derelict Minimap (browser, archived)
cd /d "%~dp0..\.."
python -I minimap\archive-browser\server.py --open %*
if errorlevel 1 pause
