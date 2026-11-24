from pathlib import Path
import os,json
import access_sync
folder=Path(os.environ.get('FRY_CHICKEN_DATA_DIR',Path(os.environ.get('LOCALAPPDATA',Path.home()))/'FRYChickenPOS'/'data'))
file=access_sync.destination(folder)
if not file.exists():raise SystemExit('Abre primero POS V55 como PC 1 y espera la sincronizacion de Access.')
os.startfile(str(file))
