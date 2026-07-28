@echo off
setlocal
cd /d "%~dp0.."
"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" "installer\LegendAI.iss" > installer_log.txt 2>&1
endlocal
