@echo off
setlocal
cd /d "%~dp0"
set "PYEXE="
if exist "%LOCALAPPDATA%\NMSDerelictSurveyor\python-executable.txt" set /p PYEXE=<"%LOCALAPPDATA%\NMSDerelictSurveyor\python-executable.txt"
if not defined PYEXE set "PYEXE=python"
"%PYEXE%" "%~dp0tools\extract_runtime_target_function.py" %*
set "RC=%ERRORLEVEL%"
if not defined NMSDS_NONINTERACTIVE pause
exit /b %RC%
