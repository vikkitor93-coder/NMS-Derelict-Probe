@echo off
rem Starts the live derelict minimap (http://127.0.0.1:8766/) and opens it in the browser.
rem It reads NMS read-only (system address + your position); start it before or after NMS.
rem Close this window to stop it.
title Derelict Minimap
cd /d "%~dp0.."
python -I minimap\server.py --open %*
if errorlevel 1 pause
