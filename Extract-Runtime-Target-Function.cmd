@echo off
setlocal EnableExtensions
set "TOOL_DIR=%~dp0"
set "SCRIPT=%TOOL_DIR%tools\extract_runtime_target_function.py"

if not exist "%SCRIPT%" (
  echo ERROR: The runtime-target extractor is missing:
  echo   "%SCRIPT%"
  echo Extract the complete DUNGEON-C helper-export ZIP. The GitHub lane branch archive omits required sibling tools.
  goto :failed
)

where py.exe >nul 2>&1
if not errorlevel 1 (
  py -3.13 -c "import sys" >nul 2>&1
  if not errorlevel 1 (
    py -3.13 "%SCRIPT%" %*
    goto :finished
  )
  py -3.12 -c "import sys" >nul 2>&1
  if not errorlevel 1 (
    py -3.12 "%SCRIPT%" %*
    goto :finished
  )
)

where python.exe >nul 2>&1
if not errorlevel 1 (
  python "%SCRIPT%" %*
  goto :finished
)

echo ERROR: Python 3.12 or 3.13 was not found.
echo Install one of these versions, or use the Python launcher (py.exe), then retry.
goto :failed

:failed
set "RC=1"
goto :wrapup

:finished
set "RC=%ERRORLEVEL%"
if not defined NMSDS_NONINTERACTIVE pause

:wrapup
exit /b %RC%

