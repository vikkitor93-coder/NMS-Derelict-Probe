@echo off
rem Starts the local derelict viewer (http://127.0.0.1:8765/) and opens it in the browser.
rem Close this window to stop the viewer.
title Derelict Viewer
cd /d "%~dp0.."
python -I viewer\server.py %*
if errorlevel 1 pause
