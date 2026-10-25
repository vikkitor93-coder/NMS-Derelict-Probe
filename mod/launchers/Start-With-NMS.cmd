@echo off
rem Steam launch option:  "<this folder>\Start-With-NMS.cmd" %command%
rem Starts the minimap next to the game; it closes itself when the game closes. Nothing stays in the background.
start "" /b "%~dp0python\pythonw.exe" -I "%~dp0NMS-Derelict-Probe\minimap\overlay.py" --exit-with-game
%*
