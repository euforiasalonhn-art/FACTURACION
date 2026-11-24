"""Identidad de terminal y permisos, siempre controlados por PC 1."""
import json,secrets,threading
from flask import request,session,g,jsonify,has_request_context
import accounting,employees
import pc_labels

REQUEST_LOCK=threading.RLock()

def terminal_id():return int(getattr(g,'terminal',{}).get('id',0)) if has_request_context() else 0
def terminal_name():return pc_labels.name(terminal_id())

def init(c):
 c.execute('CREATE TABLE IF NOT EXISTS terminals(id INTEGER PRIMARY KEY,name TEXT NOT NULL,branch_id INTEGER NOT NULL REFERENCES branches(id),secret TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1,employee_ids TEXT NOT NULL,version INTEGER NOT NULL DEFAULT 1)')
 c.execute('CREATE TABLE IF NOT EXISTS terminal_requests(terminal_id INTEGER NOT NULL,request_id TEXT NOT NULL,payload_hash TEXT NOT NULL,last_status INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(terminal_id,request_id))')
 cols={r['name'] for r in c.execute('PRAGMA table_info(cash_sessions)')}
 if 'terminal_id' not in cols:c.execute('ALTER TABLE cash_sessions ADD COLUMN terminal_id INTEGER NOT NULL DEFAULT 0')
 if 'cashier_id' not in cols:c.execute('ALTER TABLE cash_sessions ADD COLUMN cashier_id INTEGER')
 c.execute('DROP INDEX IF EXISTS one_open_shift')
 c.execute("CREATE UNIQUE INDEX IF NOT EXISTS one_open_terminal_shift ON cash_sessions(branch_id,terminal_id) WHERE status='ABIERTA'")
 for table in ['invoices','employee_meals','special_orders']:
  cols={r['name'] for r in c.execute('PRAGMA table_info('+table+')')}
  if 'terminal_id' not in cols:c.execute('ALTER TABLE '+table+' ADD COLUMN terminal_id INTEGER NOT NULL DEFAULT 0')

def prepare(c):
 if (request.path.startswith('/api/') and request.method!='GET') or request.path=='/api/terminal/recover':
  REQUEST_LOCK.acquire();g.financial_lock=True
 tid=int(request.environ.get('FRY_TERMINAL_ID',0));g.terminal={'id':0,'name':'PC 1'}
 if tid:
  r=c.execute('SELECT * FROM terminals WHERE id=? AND active=1',(tid,)).fetchone()
  if not r:return jsonify(error='Terminal retirada. Contacta al administrador.'),403
  g.terminal=dict(r)
 primary=c.execute("SELECT value FROM settings WHERE key='primary_employees'").fetchone();primary_ids=json.loads(primary[0]) if primary else None
 if not tid and session.get('role')=='local' and primary_ids is not None and session.get('cashier_id') not in primary_ids:session.clear()
 if not tid and request.path=='/api/auth/login' and request.method=='POST' and (request.json or {}).get('role')=='local' and primary_ids is not None:
  employee=employees.authenticate(c,(request.json or {}).get('employee_code'))
  if employee and employee['id'] not in primary_ids:return jsonify(error='Empleado no autorizado para PC 1'),403
 if session.get('role'):
  old=session.get('terminal_id',0)
  if old!=tid:session.clear()
  elif tid and session.get('terminal_version')!=g.terminal['version']:session.clear()
  elif tid and session.get('role')=='local' and session.get('cashier_id') not in json.loads(g.terminal['employee_ids']):session.clear()
 if tid and request.path=='/api/auth/login' and request.method=='POST':
  d=request.json or {}
  if d.get('role')=='local':
   employee=employees.authenticate(c,d.get('employee_code'))
   if int(d.get('branch_id',0))!=g.terminal['branch_id'] or (employee and employee['id'] not in json.loads(g.terminal['employee_ids'])):return jsonify(error='Empleado o sucursal no autorizado para esta terminal'),403
 if tid and request.path in ['/api/invoices','/api/quote','/api/cash','/api/employee-meals','/api/special-orders']:
  d=request.get_json(silent=True) or request.args
  if d.get('branch_id') and int(d['branch_id'])!=g.terminal['branch_id']:return jsonify(error='La terminal solo opera en su sucursal asignada'),403
 if session.get('role')=='local' and request.method=='POST' and request.path in ['/api/invoices','/api/employee-meals','/api/special-orders','/api/cash']:
  row=c.execute("SELECT cashier_id FROM cash_sessions WHERE branch_id=? AND terminal_id=? AND status='ABIERTA'",(session.get('branch_id'),tid)).fetchone()
  if row and row['cashier_id'] is not None and row['cashier_id']!=session.get('cashier_id'):return jsonify(error='Este turno pertenece a otro empleado. El administrador debe cerrarlo antes de abrir uno nuevo.'),403

def public():
 t=getattr(g,'terminal',{'id':0,'name':'PC 1'})
 return dict(id=t['id'],name=pc_labels.name(t['id']),branch_id=t.get('branch_id'),remote=bool(t['id']))

def register(app,connect,money):
 @app.teardown_request
 def unlock(error):
  if getattr(g,'financial_lock',False):
   g.financial_lock=False;REQUEST_LOCK.release()
 @app.route('/api/admin/primary-employees',methods=['GET','POST'])
 def primary_staff():
  with connect() as c:
   if request.method=='POST':
    ids=(request.json or {}).get('employee_ids')
    if not isinstance(ids,list) or any(type(i) is not int or not c.execute('SELECT id FROM employees WHERE id=? AND active=1',(i,)).fetchone() for i in ids):raise ValueError('Selecciona empleados activos')
    c.execute("INSERT OR REPLACE INTO settings VALUES('primary_employees',?)",(json.dumps(list(set(ids))),));accounting.audit(c,'EMPLEADOS_MAQUINA_1','primary',dict(employees=ids))
   r=c.execute("SELECT value FROM settings WHERE key='primary_employees'").fetchone()
   return jsonify(employee_ids=json.loads(r[0]) if r else None)
 @app.get('/api/admin/central-info')
 def central_info():
  import socket
  return jsonify(port=5060,addresses=sorted({r[4][0] for r in socket.getaddrinfo(socket.gethostname(),None,socket.AF_INET)}))
 @app.route('/api/admin/terminals',methods=['GET','POST'])
 def terminals_admin():
  with connect() as c:
   if request.method=='POST':
    d=request.json or {};name=str(d.get('name','')).strip();branch=int(d.get('branch_id',0));ids=d.get('employee_ids')
    if not 1<=len(name)<=100 or not isinstance(ids,list) or not ids or any(type(i) is not int for i in ids) or len(ids)!=len(set(ids)):raise ValueError('Indica nombre, sucursal y empleados autorizados')
    if not c.execute('SELECT id FROM branches WHERE id=? AND active=1',(branch,)).fetchone():raise ValueError('Sucursal no disponible')
    if any(not c.execute('SELECT id FROM employees WHERE id=? AND active=1',(i,)).fetchone() for i in ids):raise ValueError('Selecciona empleados activos')
    c.execute('BEGIN IMMEDIATE');secret=secrets.token_urlsafe(32);tid=d.get('id')
    if tid:
     old=c.execute('SELECT * FROM terminals WHERE id=?',(tid,)).fetchone()
     if not old:raise ValueError('Terminal no encontrada')
     if old['branch_id']!=branch and c.execute("SELECT 1 FROM cash_sessions WHERE terminal_id=? AND status='ABIERTA'",(tid,)).fetchone():raise ValueError('Cierra el turno antes de cambiar de sucursal')
     secret=secret if d.get('rotate_key') else old['secret']
     c.execute('UPDATE terminals SET name=?,branch_id=?,employee_ids=?,active=?,secret=?,version=version+1 WHERE id=?',(name,branch,json.dumps(ids),int(d.get('active',True)),secret,tid))
    else:tid=c.execute('INSERT INTO terminals(name,branch_id,secret,employee_ids) VALUES(?,?,?,?)',(name,branch,secret,json.dumps(ids))).lastrowid
    accounting.audit(c,'TERMINAL_CONFIGURADA',tid,dict(name=name,branch_id=branch,employees=ids,active=d.get('active',True)))
    # La clave solo se devuelve al crear o rotar; nunca en consultas/listados.
    return jsonify(id=tid,key=secret if not d.get('id') or d.get('rotate_key') else '',name=name)
   rows=[dict(r) for r in c.execute('SELECT id,name,branch_id,active,employee_ids,version FROM terminals ORDER BY id')]
   for r in rows:
    r['employee_ids']=json.loads(r['employee_ids']);shift=c.execute("SELECT id,opened_by,opening FROM cash_sessions WHERE terminal_id=? AND status='ABIERTA'",(r['id'],)).fetchone();r['open_shift']=dict(shift) if shift else None
   return jsonify(rows)
 @app.post('/api/admin/terminals/<int:tid>/cash-close')
 def close_terminal_cash(tid):
  d=request.json or {}
  if 'counted' not in d:raise ValueError('Indica el efectivo contado')
  with connect() as c:
   c.execute('BEGIN IMMEDIATE');r=c.execute("SELECT * FROM cash_sessions WHERE terminal_id=? AND status='ABIERTA'",(tid,)).fetchone()
   if not r or r['id']!=int(d.get('shift_id',0)):raise ValueError('El turno cambió. Actualiza la lista de terminales.')
   counted=money(d['counted']);expected=accounting.shift_summary(c,r)['live_expected']
   c.execute("UPDATE cash_sessions SET status='CERRADA',closed_by=?,closed_at=?,counted=?,expected=?,difference=? WHERE id=?",(accounting.actor(),accounting.now(),counted,expected,counted-expected,r['id']))
   accounting.audit(c,'CIERRE_CAJA_ADMINISTRADOR',r['id'],dict(terminal_id=tid,expected=expected,counted=counted,difference=counted-expected))
  return jsonify(ok=True)
 @app.post('/api/terminal/cancel-pending')
 def cancel_pending():
  if session.get('role') not in ['admin','local']:return jsonify(error='Inicia sesión'),403
  key=str((request.json or {}).get('request_id',''))
  if not 1<=len(key)<=200:raise ValueError('Identificador inválido')
  with connect() as c:
   c.execute('BEGIN IMMEDIATE')
   if c.execute('SELECT id FROM invoices WHERE request_id=?',(key,)).fetchone():return jsonify(error='El cobro ya generó una factura; recupera el resultado.'),409
   r=c.execute('SELECT last_status FROM terminal_requests WHERE terminal_id=? AND request_id=?',(terminal_id(),key)).fetchone()
   if r and r['last_status']==0:return jsonify(error='PC 1 todavía está procesando el cobro. Consulta otra vez.'),409
   c.execute("INSERT INTO terminal_requests(terminal_id,request_id,payload_hash,last_status) VALUES(?,?,'',410) ON CONFLICT(terminal_id,request_id) DO UPDATE SET last_status=410",(terminal_id(),key))
   accounting.audit(c,'COBRO_PENDIENTE_CANCELADO',key,dict(terminal_id=terminal_id()))
  return jsonify(ok=True)
 @app.get('/api/terminal/recover')
 def recover_sale():
  if session.get('role') not in ['admin','local']:return jsonify(error='Inicia sesión'),403
  key=str(request.args.get('request_id',''))
  with connect() as c:
   r=c.execute('SELECT id,terminal_id,number,total FROM invoices WHERE request_id=?',(key,)).fetchone()
   if r and r['terminal_id']!=terminal_id():return jsonify(error='Cobro de otra terminal'),403
   pending=c.execute('SELECT last_status FROM terminal_requests WHERE terminal_id=? AND request_id=?',(terminal_id(),key)).fetchone()
   return jsonify(found=bool(r),invoice=dict(r) if r else None,processing=bool(not r and pending and pending['last_status']==0))
