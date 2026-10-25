@echo off
rem Run this after NMS updates (Steam): checks the minimap reader, the generator and the reward predictor against the game.
rem Takes about 10 seconds. Read-only. See minimap\README.md, section "After an NMS update".
title Check after NMS update
cd /d "%~dp0.."
python -I minimap\check_update.py %*
echo.
pause
