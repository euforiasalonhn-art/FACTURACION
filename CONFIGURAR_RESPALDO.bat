@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
 py -3.12 -m venv .venv
 if errorlevel 1 python -m venv .venv
)
if not exist .venv\Scripts\python.exe goto error
.venv\Scripts\python.exe -m pip install Flask==3.1.3 cryptography==50.0.2
if errorlevel 1 goto error
.venv\Scripts\python.exe backup_receiver.py --setup
if errorlevel 1 goto error
echo.
echo Copia la clave en Administrador - Respaldos en red de la PC de caja.
echo Para arrancar con Windows, ejecuta INSTALAR_INICIO_RESPALDO.ps1 como administrador.
pause
exit /b
:error
echo No se pudo preparar el receptor.
pause
