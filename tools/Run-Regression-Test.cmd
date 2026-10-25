@echo off
rem Runs the one-command regression test (fast mode, about 1-2 minutes). Add --full for the slow comparison too.
rem Result: PASS/FAIL lines and a summary; exit code 0 = all good. Nothing real is overwritten.
title NMS derelict regression test
cd /d "%~dp0.."
python -I tools\regression_test_705.py %*
set RC=%ERRORLEVEL%
echo.
if %RC%==0 (echo ALL CHECKS PASSED) else (echo SOME CHECKS FAILED - see the FAIL lines above)
pause
exit /b %RC%
