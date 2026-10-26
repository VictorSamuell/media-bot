@echo off
setlocal
cd /d "%~dp0frontend"
call npm ci
if errorlevel 1 goto error
call npm run build
if errorlevel 1 goto error
echo Painel preparado. Agora abra iniciar.cmd.
pause
exit /b 0
:error
echo Nao foi possivel preparar o painel. Confira o Node.js e as mensagens acima.
pause
exit /b 1
