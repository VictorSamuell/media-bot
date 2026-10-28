@echo off
setlocal
cd /d "%~dp0"
".venv\Scripts\python.exe" -m media_bot.setup_local
pause
