@echo off
rem Dois cliques aqui instalam o kit e ligam a publica‡Æo autom tica.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\instalar_tudo.ps1"
echo.
pause
