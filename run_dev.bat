@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"

python app.py

if errorlevel 1 (
    echo.
    echo O LegendAI nao conseguiu abrir. Copie esta mensagem e me envie.
    pause
)

endlocal
