@echo off
cd /d "%~dp0"
.venv\Scripts\python.exe abrir_access.py
if errorlevel 1 pause
