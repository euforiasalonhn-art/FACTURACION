from contextlib import closing
"""Respaldo JSON completo y atómico en la carpeta persistente de datos."""
import sqlite3,json,base64,threading,os,tempfile
from pathlib import Path
from datetime import datetime,timezone
LOCK=threading.RLock()
NAME='FRYChickenPOS-RESPALDO-COMPLETO.json'
def write(db,data):
 with LOCK:
  if not db.exists():return
  with closing(sqlite3.connect(db)) as source:
   if not source.execute("SELECT 1 FROM sqlite_master WHERE name='settings'").fetchone():return
   dest=sqlite3.connect(':memory:');source.backup(dest)
   tables={}
   for (name,) in dest.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
    cur=dest.execute('SELECT * FROM "'+name.replace('"','""')+'"');cols=[d[0] for d in cur.description];tables[name]=[dict(zip(cols,row)) for row in cur.fetchall()]
   binary=base64.b64encode(dest.serialize()).decode();dest.close()
  assets={}
  for folder in data.iterdir():
   if folder.is_dir():
    for file in folder.rglob('*'):
     if file.is_file() and file.suffix.lower() in ['.jpg','.jpeg','.png','.webp']:assets[file.relative_to(data).as_posix()]=base64.b64encode(file.read_bytes()).decode()
  doc=dict(format='FRYChickenPOS-FULL',version=1,created_at=datetime.now(timezone.utc).isoformat(),tables=tables,database_base64=binary,assets=assets)
  temp=data/(NAME+'.tmp')
  with temp.open('w',encoding='utf-8') as f:json.dump(doc,f,ensure_ascii=False,default=lambda v:{"base64":base64.b64encode(v).decode()} if isinstance(v,bytes) else str(v));f.flush();os.fsync(f.fileno())
  os.replace(temp,data/NAME)
def restore_if_missing(db,data):
 path=data/NAME
 if db.exists() or not path.exists():return
 doc=json.loads(path.read_text(encoding='utf-8'))
 if doc.get('format')!='FRYChickenPOS-FULL' or doc.get('version')!=1:raise ValueError('Formato de respaldo no reconocido')
 raw=base64.b64decode(doc['database_base64'],validate=True);check=sqlite3.connect(':memory:')
 try:
  check.deserialize(raw)
  if check.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Respaldo de datos dañado')
  if check.execute("SELECT 1 FROM sqlite_master WHERE name='print_jobs'").fetchone():
   check.execute("UPDATE print_jobs SET state='UNCERTAIN',last_error='Respaldo restaurado: revisa papel antes de pedir una copia' WHERE state IN ('PENDING','PAUSED','CLAIMED','SPOOLING','FAILED')");check.commit();raw=check.serialize()
 finally:check.close()
 temp=db.with_suffix('.restore-tmp');temp.write_bytes(raw);os.replace(temp,db)
 for name,encoded in doc.get('assets',{}).items():
  target=(data/name).resolve()
  if not target.is_relative_to(data.resolve()):raise ValueError('Ruta de imagen inválida')
  target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(base64.b64decode(encoded,validate=True))

