@echo off
cd /d "%~dp0"
python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install -r requirements-desktop.txt
python -m PyInstaller --noconfirm --windowed --name FRYChickenPOS --add-data "templates;templates" --add-data "static;static" --add-data "catalog_assets;catalog_assets" --add-data "catalog_enrichment.json;." --add-data "access_template.accdb;." --add-data "access_apply.ps1;." desktop_main.py
pause
