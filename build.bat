@echo off
REM Gera o executavel do LegendAI em dist\LegendAI\LegendAI.exe
REM Requisito: pip install -r requirements.txt pyinstaller

echo === LegendAI - Build do executavel ===
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Instalando PyInstaller...
    pip install pyinstaller
)

pyinstaller LegendAI.spec --noconfirm --clean
if errorlevel 1 (
    echo.
    echo Build falhou. Verifique as mensagens acima.
    exit /b 1
)

echo.
echo Build concluido: dist\LegendAI\LegendAI.exe
echo Lembre-se: o FFmpeg precisa estar instalado no PATH da maquina de destino.
pause
