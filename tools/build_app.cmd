@echo off
setlocal
cd /d "%~dp0.."
python -m PyInstaller LegendAI.spec --noconfirm --clean > build_offline.out.log 2> build_offline.err.log
endlocal
