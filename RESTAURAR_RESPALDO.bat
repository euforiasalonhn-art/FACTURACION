@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
 echo Ejecuta primero CONFIGURAR_RESPALDO.bat para instalar Python y Flask.
 pause
 exit /b 1
)
.venv\Scripts\python.exe restaurar_respaldo.py
pause
