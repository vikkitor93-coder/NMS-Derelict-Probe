@echo off
rem Starts the live derelict minimap for your local network, so a phone can be a second screen.
rem The window prints the phone link. Windows may ask once to allow Python through the firewall:
rem allow it for Private networks only.
title Derelict Minimap (local network)
cd /d "%~dp0.."
python -I minimap\server.py --host 0.0.0.0 %*
if errorlevel 1 pause
