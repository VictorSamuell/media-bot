@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Ambiente Python ausente. Consulte docs\uso-local.md.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m media_bot.launcher
pause
