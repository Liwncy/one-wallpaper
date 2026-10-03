@echo off
rem ===========================================================
rem  Launcher for install_task.ps1 - creates (or removes) the
rem  Windows scheduled task that runs run_daily.bat once a day.
rem
rem  Usage:
rem    install_task.bat             create / update the task
rem    install_task.bat -Remove     delete the task
rem
rem  IMPORTANT: keep this file PURE ASCII and CRLF-terminated.
rem  cmd.exe loses byte alignment when LF-only line endings meet
rem  multibyte characters - see the header of run_daily.bat.
rem ===========================================================

chcp 65001 >nul
setlocal
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_task.ps1" %*
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" (echo [done] finished, exit code 0.) else (echo [FAILED] exit code %RC% - see the messages above.)
echo.
pause

endlocal & exit /b %RC%
