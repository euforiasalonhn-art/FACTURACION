from contextlib import closing
"""Recuperación en una PC nueva; nunca sobrescribe una base existente."""
import argparse,base64,getpass,gzip,json,os,sqlite3
from pathlib import Path
from werkzeug.security import check_password_hash
import backup_protocol as protocol,full_backup

def restore(source,target,password):
 target=Path(target);target.mkdir(parents=True,exist_ok=True)
 if (target/'fry_chicken.db').exists():raise ValueError('Ya existe una base de datos en esta PC. No se sobrescribe. Usa una instalación nueva o conserva primero su carpeta de datos.')
 blob=Path(source).read_bytes()
 if str(source).lower().endswith('.gz'):doc,_,_=protocol.validate(blob);raw=gzip.decompress(blob)
 else:
  raw=blob;doc=json.loads(raw);protocol.validate(gzip.compress(raw))
 c=sqlite3.connect(':memory:')
 try:
  c.deserialize(base64.b64decode(doc['database_base64']));row=c.execute("SELECT value FROM settings WHERE key='auth'").fetchone()
  if not row or not check_password_hash(json.loads(row[0])['password'],password):raise ValueError('Contraseña del administrador incorrecta')
 finally:c.close()
 protocol.atomic(target/full_backup.NAME,raw);full_backup.restore_if_missing(target/'fry_chicken.db',target)
 # Comprobar que el resultado puede abrirse antes de permitir iniciar el POS.
 with closing(sqlite3.connect(target/'fry_chicken.db')) as c:
  if c.execute("SELECT 1 FROM sqlite_master WHERE name='print_jobs'").fetchone():
   c.execute("UPDATE print_jobs SET state='UNCERTAIN',last_error='Respaldo restaurado: revisar papel antes de pedir una copia' WHERE state IN ('PENDING','PAUSED','CLAIMED','SPOOLING','FAILED')");c.commit()
  if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('No se pudo verificar la restauración')
  row=c.execute('SELECT number,fiscal_number,created_at FROM invoices ORDER BY id DESC LIMIT 1').fetchone()
 return row

def main():
 p=argparse.ArgumentParser();p.add_argument('archivo',nargs='?');p.add_argument('--data',default=str(Path(os.environ.get('LOCALAPPDATA',Path.home()))/'FRYChickenPOS'/'data'));args=p.parse_args()
 file=args.archivo or input('Ruta del respaldo .json.gz o .json: ').strip().strip('"')
 print('Cierra el POS. La PC de caja anterior debe quedar fuera de uso para evitar numeración duplicada.')
 if input('Escribe RESTAURAR para continuar: ').strip()!='RESTAURAR':return
 row=restore(file,args.data,getpass.getpass('Contraseña del administrador del respaldo: '))
 print('Restauración verificada. Última factura: '+str(row));print('Abre INICIAR.bat. En una PC nueva vuelve a vincular el autenticador y las claves protegidas de Windows.')
if __name__=='__main__':
 try:main()
 except Exception as e:raise SystemExit(str(e))
