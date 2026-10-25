@echo off
setlocal
cd /d "%~dp0"
title NMS Derelict Minimap - uninstall
"python\python.exe" -I "NMS-Derelict-Probe\minimap\lifecycle.py" uninstall
echo.
echo  Also remove the Steam launch option if you added one (Steam - No Man's Sky - Properties - Launch Options).
pause
