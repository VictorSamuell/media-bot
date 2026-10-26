@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Ambiente Python ausente.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m media_bot.launcher --stop
pause
