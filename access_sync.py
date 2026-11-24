"""Proyección contable durable a Access; nunca bloquea el cobro del POS."""
import os,json,sqlite3,threading,subprocess,tempfile,shutil,time,logging
from pathlib import Path
from datetime import datetime
import access_model
WAKE=threading.Event();STARTED=False;RUN_LOCK=threading.Lock();FORCE=False
def init(c):
 c.execute('CREATE TABLE IF NOT EXISTS access_sync_outbox(id INTEGER PRIMARY KEY AUTOINCREMENT,table_name TEXT NOT NULL,changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
 for table in access_model.WATCH:
  if not c.execute("SELECT 1 FROM sqlite_master WHERE name=?",(table,)).fetchone():continue
  for action in ['INSERT','UPDATE','DELETE']:
   c.execute(f"CREATE TRIGGER IF NOT EXISTS access_{table}_{action} AFTER {action} ON {table} BEGIN INSERT INTO access_sync_outbox(table_name) VALUES('{table}'); END")
def notify():WAKE.set()
def request_sync():
 global FORCE
 FORCE=True;WAKE.set()
def atomic(path,doc):
 path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp')
 with tmp.open('w',encoding='utf-8') as f:json.dump(doc,f,ensure_ascii=False);f.flush();os.fsync(f.fileno())
 os.replace(tmp,path)
def load(path):
 try:return json.loads(path.read_text(encoding='utf-8-sig'))
 except (OSError,ValueError):return {}
def destination(data):
 config=load(Path(data).parent/'access_sync.json');value=config.get('path')
 if value:
  path=Path(value)
  if not path.is_absolute() or path.suffix.lower()!='.accdb':raise ValueError('La ruta de Access debe ser absoluta y terminar en .accdb')
  return path
 return Path(data).parent/'contabilidad'/'FRYChicken-Contabilidad.accdb'
def checkpoint(db):
 with sqlite3.connect(Path(db).resolve().as_uri()+'?mode=ro',uri=True,timeout=10) as c:
  if not c.execute("SELECT 1 FROM sqlite_master WHERE name='access_sync_outbox'").fetchone():return 0
  return c.execute("SELECT COALESCE((SELECT seq FROM sqlite_sequence WHERE name='access_sync_outbox'),0)").fetchone()[0]
def status(db,data):
 state=load(Path(data).parent/'access_estado.json')
 try:
  target=destination(data);state['path']=str(target);state['exists']=target.exists();last=checkpoint(db)
  state['pending']=max(0,last-int(state.get('last_event',-1)))
  if state.get('error'):state['state']='PENDIENTE - REVISAR ACCESS'
  elif not target.exists() or state['pending'] or state.get('target')!=str(target):state['state']='PENDIENTE DE SINCRONIZAR'
  else:state['state']='ACTUALIZADO'
  if target.exists() and target.stat().st_size>1500*1024*1024:state['size_warning']='Access supera 1.5 GB. Solicita mantenimiento antes de alcanzar su limite de archivo.'
 except Exception as e:state.update(state='PENDIENTE - REVISAR',error=str(e))
 return state
def sync_once(db,data,root):
 data=Path(data);root=Path(root);statepath=data.parent/'access_estado.json';old=load(statepath);target=destination(data)
 if not RUN_LOCK.acquire(blocking=False):return None
 temp=None
 try:
  if os.name!='nt':raise RuntimeError('La copia Access requiere Windows y Microsoft Access / motor ACE compatible')
  if not target.exists():
   target.parent.mkdir(parents=True,exist_ok=True);template=root/'access_template.accdb'
   if not template.exists():raise RuntimeError('No se encontro la plantilla de Access junto al programa')
   # Publicar un archivo completo sin truncar un destino existente.
   candidate=target.with_suffix('.nuevo.accdb');shutil.copy2(template,candidate);os.replace(candidate,target)
  if target.stat().st_size>1850*1024*1024:raise RuntimeError('Access se acerca a 2 GB. La copia contable requiere mantenimiento; el historial sigue en el POS')
  payload=access_model.build(db)
  with tempfile.NamedTemporaryFile('w',suffix='.json',prefix='access-',dir=data,encoding='utf-8',delete=False) as f:json.dump(payload,f,ensure_ascii=False);temp=Path(f.name)
  shell=Path(os.environ.get('WINDIR','C:/Windows'))/'System32/WindowsPowerShell/v1.0/powershell.exe'
  args=['-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(root/'access_apply.ps1'),'-InputPath',str(temp),'-AccessPath',str(target)]
  result=subprocess.run([str(shell),*args],capture_output=True,timeout=180,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
  if result.returncode and any(x in (result.stderr+result.stdout).decode(errors='replace') for x in ['80040154','Class not registered','Clase no registrada']):
   alternate=Path(os.environ.get('WINDIR','C:/Windows'))/'SysWOW64/WindowsPowerShell/v1.0/powershell.exe'
   if alternate.exists():result=subprocess.run([str(alternate),*args],capture_output=True,timeout=180,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
  if result.returncode:raise RuntimeError((result.stderr or result.stdout).decode('utf-8',errors='replace').strip()[-1500:] or 'El motor Access no confirmo la escritura')
  state=dict(last_event=payload['last_event'],target=str(target),last_success=datetime.now().astimezone().isoformat(timespec='seconds'),last_invoice=payload['tables']['ControlSincronizacion'][0]['values']['UltimaFactura'],error='',invoice_count=len(payload['tables']['Facturas']))
  atomic(statepath,state)
  # Mantener solo una cola corta ya confirmada, conservando su secuencia monotónica.
  with sqlite3.connect(db,timeout=20) as c:c.execute('DELETE FROM access_sync_outbox WHERE id<=?',(max(0,payload['last_event']-500),))
  return state
 except Exception as e:
  atomic(statepath,old|dict(error=str(e),last_attempt=datetime.now().astimezone().isoformat(timespec='seconds')));raise
 finally:
  if temp:
   try:temp.unlink()
   except OSError:pass
  RUN_LOCK.release()
def start(db,data,root):
 global STARTED
 if STARTED:return
 STARTED=True
 def run():
  global FORCE
  first=True
  while True:
   WAKE.wait(5);WAKE.clear()
   try:
    state=status(db,data);force=FORCE;FORCE=False
    if first or force or state.get('pending') or not state.get('exists') or state.get('error') or state.get('target')!=state.get('path') or checkpoint(db)<state.get('last_event',-1):sync_once(db,data,root)
    first=False
   except Exception as e:logging.getLogger('access_contable').warning('Copia Access pendiente: %s',e)
 threading.Thread(target=run,daemon=True,name='FRY-Access-contable').start();WAKE.set()
def register(app,db,data):
 from flask import jsonify
 @app.get('/api/accounting/access-status')
 def access_status():return jsonify(status(db(),data))
 @app.post('/api/admin/access-sync')
 def access_request():request_sync();return jsonify(ok=True,message='Sincronizacion Access solicitada; consulta el estado para confirmar')
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--db',required=True);p.add_argument('--data',required=True);p.add_argument('--root',default=str(Path(__file__).parent));args=p.parse_args();print(json.dumps(sync_once(args.db,args.data,args.root),ensure_ascii=False))
