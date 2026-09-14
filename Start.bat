@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title snip-ai

set "PYLAUNCH="
where py >nul 2>&1
if %ERRORLEVEL%==0 set "PYLAUNCH=py -3"
if not defined PYLAUNCH (
  where python >nul 2>&1
  if %ERRORLEVEL%==0 set "PYLAUNCH=python"
)

if not defined PYLAUNCH (
  echo.
  echo snip-ai needs Python, which is not installed yet.
  echo.
  echo  1. The download page will open.
  echo  2. Run the installer and CHECK the box "Add python.exe to PATH".
  echo  3. Close this window, then double-click Start.bat again.
  echo.
  start https://www.python.org/downloads/
  pause
  exit /b 1
)

%PYLAUNCH% scripts\ensure_and_run.py %*
set "ERR=%ERRORLEVEL%"
if not "%ERR%"=="0" (
  echo.
  echo snip-ai could not start. You can copy the text above if you need help.
  pause
)
exit /b %ERR%
