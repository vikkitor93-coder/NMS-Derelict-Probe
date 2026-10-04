@echo off
setlocal
set "TOOL_DIR=%~dp0"
pushd "%TOOL_DIR%" >nul 2>&1
if errorlevel 1 (
  echo ERROR: Could not enter the extractor folder:
  echo   "%TOOL_DIR%"
  echo Extract the ZIP to a normal local folder, then run this file again.
  goto :failed
)
set "PYEXE="
set "PYFILE=%LOCALAPPDATA%\NMSDerelictSurveyor\python-executable.txt"
if exist "%PYFILE%" for /f "usebackq delims=" %%I in ("%PYFILE%") do if not defined PYEXE set "PYEXE=%%~I"
if defined PYEXE if not exist "%PYEXE%" (
  set "SAVED_PYEXE=%PYEXE%"
  set "PYEXE="
)
if not defined PYEXE (
  where py.exe >nul 2>&1
  if not errorlevel 1 (
    py -3 "%TOOL_DIR%tools\extract_runtime_target_function.py" %*
    goto :finished
  )
  where python.exe >nul 2>&1
  if not errorlevel 1 (
    python "%TOOL_DIR%tools\extract_runtime_target_function.py" %*
    goto :finished
  )
  echo ERROR: Could not find Surveyor's Python, the Python launcher, or python.exe on PATH.
  if defined SAVED_PYEXE echo Surveyor's saved path was not usable: "%SAVED_PYEXE%"
  echo Start Surveyor once to create its managed Python path, or install Python 3 and retry.
  goto :failed
)
"%PYEXE%" "%TOOL_DIR%tools\extract_runtime_target_function.py" %*
goto :finished

:failed
set "RC=1"
goto :wrapup

:finished
set "RC=%ERRORLEVEL%"
if not defined NMSDS_NONINTERACTIVE pause
:wrapup
popd >nul 2>&1
exit /b %RC%
