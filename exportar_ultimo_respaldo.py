"""Exporta el archivo confirmado por el manifiesto, sin depender del alias latest."""
import json,os
from pathlib import Path
import backup_protocol as protocol

def main():
 root=Path(os.environ.get('LOCALAPPDATA',Path.home()))/'FRYChickenBackup'
 folders=sorted(p for p in root.iterdir() if p.is_dir() and (p/'manifest.json').exists())
 if not folders:raise SystemExit('No hay respaldos confirmados en este receptor.')
 for n,p in enumerate(folders,1):
  m=json.loads((p/'manifest.json').read_text('utf-8'));last=m.get('last_invoice') or {};print(f"{n}. Instalación {p.name} | Factura {last.get('fiscal_number') or last.get('number','sin ventas')} | {m.get('confirmed_at')}")
 choice=int(input('Número de instalación a exportar: '))-1
 if not 0<=choice<len(folders):raise ValueError('Selección inválida')
 source=folders[choice];m=json.loads((source/'manifest.json').read_text('utf-8'));blob=(source/m['file']).read_bytes()
 if protocol.digest(blob)!=m['sha256']:raise ValueError('El archivo no coincide con el respaldo confirmado')
 protocol.validate(blob);dest=root/'EXPORTADOS'/('FRYChicken-'+source.name+'-'+str(m['sequence'])+'.json.gz');protocol.atomic(dest,blob)
 print('Copia este archivo a la PC nueva: '+str(dest))
 if os.name=='nt':os.startfile(str(dest.parent))
if __name__=='__main__':
 try:main()
 except Exception as e:raise SystemExit(str(e))
