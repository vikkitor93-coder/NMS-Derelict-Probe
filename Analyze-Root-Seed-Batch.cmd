@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Analyze-Root-Seed-Batch.ps1"
exit /b %ERRORLEVEL%
