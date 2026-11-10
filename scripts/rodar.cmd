@echo off
rem Roda um comando do kit e guarda a saída em saida\automacao.log (usado pelo Agendador de Tarefas).
cd /d "%~dp0.."
if not exist saida mkdir saida
set PYTHONUTF8=1
echo [%date% %time%] paginas %* >> "saida\automacao.log"
".venv\Scripts\paginas.exe" %* >> "saida\automacao.log" 2>&1
