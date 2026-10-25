@echo off
rem Starts the minimap overlay by hand (no console window). It shows itself when you are in a derelict.
start "" "%~dp0python\pythonw.exe" -I "%~dp0NMS-Derelict-Probe\minimap\overlay.py"
