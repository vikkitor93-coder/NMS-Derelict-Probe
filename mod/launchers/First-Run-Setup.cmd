@echo off
rem Re-runs the first-run setup (e.g. after a game update that this version supports). Safe to repeat.
cd /d "%~dp0"
"python\python.exe" -I "NMS-Derelict-Probe\minimap\first_run.py" %*
pause
