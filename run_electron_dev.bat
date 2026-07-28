@echo off
setlocal
cd /d "%~dp0"

echo Atualizando a interface do LegendAI...
call npm.cmd run build
if errorlevel 1 goto :error

echo Abrindo a nova interface...
start "LegendAI Dev" /wait ".\node_modules\electron\dist\electron.exe" "."
goto :end

:error
echo.
echo A interface Electron nao conseguiu preparar. Copie esta mensagem e me envie.
pause

:end
endlocal
