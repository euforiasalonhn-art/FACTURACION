"""Una sesión de empleado por PC y por empleado, reservada en la base central."""
import secrets
import pc_labels

class SessionInUse(ValueError):
 def __init__(self,terminal_id,message=None):
  self.pc=pc_labels.name(terminal_id)
  super().__init__(message or 'Este empleado ya tiene una sesión o caja abierta en '+self.pc+'. Debe cerrar su caja y sesión allí antes de ingresar en otra PC.')

def init(c):
 c.execute('CREATE TABLE IF NOT EXISTS employee_sessions(employee_id INTEGER PRIMARY KEY REFERENCES employees(id),terminal_id INTEGER NOT NULL UNIQUE,token TEXT NOT NULL,started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')

def valid(c,state):
 token=state.get('employee_session_token')
 if not token:return False
 row=c.execute('SELECT token,terminal_id FROM employee_sessions WHERE employee_id=?',(state.get('cashier_id'),)).fetchone()
 return bool(row and row['terminal_id']==state.get('terminal_id',0) and secrets.compare_digest(row['token'],str(token)))

def acquire(c,employee_id,terminal_id):
 opened=c.execute("SELECT terminal_id FROM cash_sessions WHERE cashier_id=? AND status='ABIERTA' AND terminal_id<>? ORDER BY id LIMIT 1",(employee_id,terminal_id)).fetchone()
 if opened:raise SessionInUse(opened['terminal_id'])
 previous=c.execute('SELECT terminal_id FROM employee_sessions WHERE employee_id=?',(employee_id,)).fetchone()
 if previous and previous['terminal_id']!=terminal_id:raise SessionInUse(previous['terminal_id'])
 other=c.execute('SELECT employee_id FROM employee_sessions WHERE terminal_id=? AND employee_id<>?',(terminal_id,employee_id)).fetchone()
 if other:raise SessionInUse(terminal_id,'Ya hay otro empleado con sesión en '+pc_labels.name(terminal_id)+'. Cierra esa sesión o pide al administrador que revise el cuadre.')
 owner=c.execute("SELECT cashier_id FROM cash_sessions WHERE terminal_id=? AND status='ABIERTA' AND cashier_id IS NOT NULL AND cashier_id<>? LIMIT 1",(terminal_id,employee_id)).fetchone()
 if owner:raise SessionInUse(terminal_id,'La caja de '+pc_labels.name(terminal_id)+' pertenece a otro empleado. El administrador debe cuadrarla antes del cambio.')
 token=secrets.token_urlsafe(32)
 c.execute('INSERT INTO employee_sessions(employee_id,terminal_id,token) VALUES(?,?,?) ON CONFLICT(employee_id) DO UPDATE SET terminal_id=excluded.terminal_id,token=excluded.token,started_at=CURRENT_TIMESTAMP',(employee_id,terminal_id,token))
 return token

def release_current(c,state):
 if state.get('role')!='local':return
 if c.execute("SELECT 1 FROM cash_sessions WHERE terminal_id=? AND status='ABIERTA'",(state.get('terminal_id',0),)).fetchone():
  c.execute('UPDATE employee_sessions SET token=? WHERE employee_id=? AND terminal_id=? AND token=?',(secrets.token_urlsafe(32),state.get('cashier_id'),state.get('terminal_id',0),state.get('employee_session_token','')))
  return
 c.execute('DELETE FROM employee_sessions WHERE employee_id=? AND terminal_id=? AND token=?',(state.get('cashier_id'),state.get('terminal_id',0),state.get('employee_session_token','')))

def release_terminal(c,terminal_id):
 if c.execute("SELECT 1 FROM cash_sessions WHERE terminal_id=? AND status='ABIERTA'",(terminal_id,)).fetchone():raise ValueError('Cuadra la caja antes de liberar la sesión de esta PC.')
 c.execute('DELETE FROM employee_sessions WHERE terminal_id=?',(terminal_id,))

def descriptions(c):
 rows=c.execute("SELECT S.employee_id,S.terminal_id,EXISTS(SELECT 1 FROM cash_sessions C WHERE (C.cashier_id=S.employee_id OR C.terminal_id=S.terminal_id) AND C.status='ABIERTA') AS open_cash FROM employee_sessions S")
 return {r['employee_id']:dict(pc=pc_labels.name(r['terminal_id']),terminal_id=r['terminal_id'],open_cash=bool(r['open_cash'])) for r in rows}

def register(app,connect):
 from flask import jsonify
 import accounting,terminals
 @app.post('/api/admin/employees/<int:eid>/release-session')
 def release_employee_session(eid):
  with connect() as c:
   c.execute('BEGIN IMMEDIATE')
   if c.execute("SELECT 1 FROM cash_sessions WHERE status='ABIERTA' AND (cashier_id=? OR terminal_id IN (SELECT terminal_id FROM employee_sessions WHERE employee_id=?))",(eid,eid)).fetchone():raise ValueError('El empleado tiene una caja abierta. Debes cuadrarla antes de liberar su sesión.')
   c.execute('DELETE FROM employee_sessions WHERE employee_id=?',(eid,));accounting.audit(c,'SESION_EMPLEADO_LIBERADA',eid,{})
  return jsonify(ok=True)
 @app.post('/api/terminal/end-session')
 def end_terminal_session():
  if not terminals.terminal_id():return jsonify(error='Esta operación requiere una PC vinculada.'),403
  with connect() as c:
   c.execute('BEGIN IMMEDIATE');release_terminal(c,terminals.terminal_id())
  return jsonify(can_exit=True)
