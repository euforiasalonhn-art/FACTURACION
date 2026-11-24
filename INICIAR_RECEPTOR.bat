@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
 echo Ejecuta primero CONFIGURAR_RESPALDO.bat
 pause
 exit /b 1
)
.venv\Scripts\python.exe backup_receiver.py
pause
