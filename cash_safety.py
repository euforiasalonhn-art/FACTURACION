"""Caja pendiente, cambio de día y verificación de salida sin cierres automáticos."""
from datetime import datetime,timezone,timedelta
import threading
import pc_labels

HONDURAS=timezone(timedelta(hours=-6))
CLOSING=threading.Event()

def today():return datetime.now(HONDURAS).date()

def business_date(value):
 try:
  parsed=datetime.fromisoformat(str(value).replace('Z','+00:00'))
  return (parsed.replace(tzinfo=HONDURAS) if parsed.tzinfo is None else parsed.astimezone(HONDURAS)).date().isoformat()
 except (TypeError,ValueError):return ''

def must_close(row):return business_date(row['opened_at'])!=today().isoformat()

def open_shifts(c,terminal_id=None):
 return [dict(r) for r in c.execute("SELECT id,branch_id,terminal_id,opened_at FROM cash_sessions WHERE status='ABIERTA'"+(' AND terminal_id=?' if terminal_id is not None else '')+' ORDER BY id',() if terminal_id is None else (terminal_id,))]

def exit_status(c,terminal_id=None):
 rows=open_shifts(c,terminal_id)
 return dict(can_exit=not rows,open_count=len(rows),old_count=sum(must_close(r) for r in rows),today=today().isoformat(),message=('Debes cuadrar y cerrar la caja antes de salir. Cajas pendientes: '+', '.join('#'+str(pc_labels.number(r['terminal_id'])) for r in rows)+'.') if rows else '',shifts=[dict(r,cash_number=pc_labels.number(r['terminal_id']),must_close=must_close(r)) for r in rows])

def require_current(c,branch_id,terminal_id):
 rows=open_shifts(c,terminal_id)
 for row in rows:
  if must_close(row):raise ValueError('Debes cuadrar la caja #'+str(pc_labels.number(row['terminal_id']))+' del '+(business_date(row['opened_at']) or 'día anterior')+' antes de registrar operaciones de un nuevo día.')
 row=next((r for r in rows if r['branch_id']==branch_id),None)
 if not row:raise ValueError('Inicia caja antes de registrar una compra')
 return row

def require_closed(c,terminal_id=None):
 if open_shifts(c,terminal_id):raise ValueError('Debes cuadrar y cerrar la caja pendiente antes de continuar.')

def register(app,connect):
 from flask import jsonify
 import terminals
 @app.get('/api/cash/exit-check')
 def cash_exit_check():
  with terminals.REQUEST_LOCK:
   with connect() as c:return jsonify(exit_status(c,terminals.terminal_id()))

def native_guard(cfg,data,connect=None,final=False):
 """PC 1 comprueba todas las cajas; la terminal solo comprueba la suya."""
 if cfg['mode']=='server':
  import terminals,employee_sessions
  with terminals.REQUEST_LOCK:
   with connect() as c:
    result=exit_status(c)
    if result['can_exit'] and final:employee_sessions.release_terminal(c,0)
   if result['can_exit'] and final:CLOSING.set()
  return result
 from pathlib import Path
 import base64,json
 import central_transport
 pending=Path(data).parent/('terminal-'+str(cfg['terminal_id']))/'cobro-pendiente.json'
 if pending.exists():return dict(can_exit=False,message='Recupera o cancela el cobro pendiente y cuadra la caja antes de salir.')
 reply=central_transport.call(cfg,dict(method='GET',path='/api/cash/exit-check',query='',headers={},body=''),timeout=5)
 if reply['status']!=200:raise ValueError('No se pudo verificar la caja en PC 1. Revisa la conexión antes de salir.')
 result=json.loads(base64.b64decode(reply['body']))
 if pending.exists():return dict(can_exit=False,message='Hay un cobro pendiente. Recupéralo antes de salir.')
 if result.get('can_exit') and final:
  reply=central_transport.call(cfg,dict(method='POST',path='/api/terminal/end-session',query='',headers={},body=''),timeout=5)
  if reply['status']!=200:raise ValueError('No se pudo liberar la sesión de esta PC. Verifica la caja antes de salir.')
  result=json.loads(base64.b64decode(reply['body']))
 return result
