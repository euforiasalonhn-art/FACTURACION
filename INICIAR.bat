@echo off
setlocal
cd /d "%~dp0"
title Sistema de facturación FRY Chicken - Iniciando
if not exist desktop_main.py (
 echo No encuentro desktop_main.py. Coloca este archivo .bat dentro de la carpeta FRYChickenPOS.
 pause
 exit /b 1
)
if not exist .venv\Scripts\python.exe (
 where py >nul 2>&1
 if not errorlevel 1 (
  py -3.12 -m venv .venv
 ) else (
  python -m venv .venv
 )
 if errorlevel 1 goto error
)
.venv\Scripts\python.exe -c "import cryptography, flask, PIL, reportlab, openpyxl, qrcode, PySide6.QtWebEngineWidgets" >nul 2>&1
if errorlevel 1 (
 echo Instalando los componentes necesarios. Esto solo se hace la primera vez...
 .venv\Scripts\python.exe -m pip install -r requirements-desktop.txt
 if errorlevel 1 goto error
)
.venv\Scripts\python.exe desktop_main.py
if errorlevel 1 goto error
exit /b
:error
echo No se pudo abrir el programa. Revisa el mensaje anterior.
pause
