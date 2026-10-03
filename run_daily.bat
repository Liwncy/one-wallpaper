@echo off
rem ===========================================================
rem  Daily wallpaper entry point.
rem
rem  IMPORTANT: keep this file PURE ASCII and CRLF-terminated.
rem  cmd.exe loses byte alignment when a batch file combines
rem  LF-only line endings with multibyte characters. It then
rem  silently swallows the "rem" line, merges it into the next
rem  command, and never runs "chcp" - so the console stays on
rem  the legacy codepage and the log shows mojibake.
rem
rem  Every path is derived from %~dp0, so no literal non-ASCII
rem  character is needed inside this file.
rem ===========================================================

chcp 65001 >nul
setlocal
cd /d "%~dp0"

rem Force UTF-8 on Python stdio so the log renders correctly in a
rem console and stays valid when stdout is piped or redirected.
set "PYTHONIOENCODING=utf-8"

rem Prefer the windowless interpreter; fall back to a normal one
rem so the script still works if the venv layout changes.
set "PY=%~dp0.venv\Scripts\pythonw.exe"
if not exist "%PY%" set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=pythonw.exe"

"%PY%" "%~dp0main.py" %*
set "RC=%ERRORLEVEL%"

endlocal & exit /b %RC%
