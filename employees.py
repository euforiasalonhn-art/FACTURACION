"""Beneficiarios de descuentos; identidades disponibles exclusivamente para administrador."""
import re,sqlite3,hashlib
from werkzeug.security import generate_password_hash,check_password_hash
from flask import request,jsonify,session
import accounting
import employee_sessions

def init(c):
 c.executescript('''CREATE TABLE IF NOT EXISTS employees(id INTEGER PRIMARY KEY,name TEXT NOT NULL,identity TEXT NOT NULL UNIQUE,active INTEGER NOT NULL DEFAULT 1);
 CREATE TABLE IF NOT EXISTS discount_beneficiaries(invoice_id INTEGER PRIMARY KEY,profile TEXT NOT NULL,employee_id INTEGER,name TEXT NOT NULL,identity TEXT NOT NULL);''')
 cols={r['name'] for r in c.execute('PRAGMA table_info(employees)')}
 for key,typ in [('first_name',"TEXT NOT NULL DEFAULT ''"),('first_surname',"TEXT NOT NULL DEFAULT ''"),('code_hash','TEXT'),('code_lookup','TEXT'),('version','INTEGER NOT NULL DEFAULT 1')]:
  if key not in cols:c.execute(f'ALTER TABLE employees ADD COLUMN {key} {typ}')
 c.execute('CREATE UNIQUE INDEX IF NOT EXISTS employee_code_unique ON employees(code_lookup) WHERE code_lookup IS NOT NULL')
def access_code(value):return str(value or '').strip().upper()
def authenticate(c,code):
 code=access_code(code)
 if not re.fullmatch(r'[A-Z0-9]{4,32}',code):return None
 row=c.execute('SELECT * FROM employees WHERE active=1 AND code_lookup=?',(hashlib.sha256(code.encode()).hexdigest(),)).fetchone()
 return row if row and row['first_name'] and row['first_surname'] and check_password_hash(row['code_hash'],code) else None
def identity(value):
 value=re.sub(r'[\s-]','',str(value or ''))
 if not re.fullmatch(r'[0-9]{13}',value):raise ValueError('La identidad debe tener 13 dígitos')
 return value

def beneficiary(c,d):
 kind=d.get('discount_profile','NONE')
 if kind=='NONE':return None
 if kind=='EMPLOYEE':
  r=c.execute('SELECT * FROM employees WHERE id=? AND active=1',(d.get('discount_employee_id'),)).fetchone()
  if not r:raise ValueError('Selecciona un empleado registrado y activo para aplicar el descuento')
  return dict(profile=kind,employee_id=r['id'],name=r['name'],identity=r['identity'])
 if kind=='SENIOR':
  name=str(d.get('discount_beneficiary_name','')).strip()
  if not 3<=len(name)<=200:raise ValueError('Ingresa el nombre completo del beneficiario del descuento')
  return dict(profile=kind,employee_id=None,name=name,identity=identity(d.get('discount_beneficiary_identity')))
 raise ValueError('Selecciona un descuento autorizado')

def register(app,connect):
 @app.get('/api/employees')
 def employee_names():
  if session.get('role') not in ['admin','local']:return jsonify(error='Acceso no permitido'),403
  with connect() as c:return jsonify([dict(r) for r in c.execute('SELECT id,name FROM employees WHERE active=1 ORDER BY name COLLATE NOCASE,id')])
 @app.get('/api/admin/employees')
 def employee_list():
  with connect() as c:
   active=employee_sessions.descriptions(c)
   return jsonify([dict(r,active_session=active.get(r['id'])) for r in c.execute('SELECT id,name,identity,active,first_name,first_surname,CASE WHEN code_hash IS NULL THEN 0 ELSE 1 END AS has_code FROM employees ORDER BY name COLLATE NOCASE,id')])
 @app.post('/api/admin/employees')
 def employee_save():
  d=request.json or {};name=str(d.get('name','')).strip();number=identity(d.get('identity'));active=1 if d.get('active',True) else 0
  if not 3<=len(name)<=200:raise ValueError('Ingresa el nombre completo del empleado')
  with connect() as c:
   c.execute('BEGIN IMMEDIATE')
   try:
    old=c.execute('SELECT * FROM employees WHERE id=?',(d.get('id'),)).fetchone() if d.get('id') else None
    if d.get('id') and not old:raise ValueError('Empleado no encontrado')
    first=str(d.get('first_name',old['first_name'] if old else '')).strip()
    surname=str(d.get('first_surname',old['first_surname'] if old else '')).strip()
    code=access_code(d.get('access_code'))
    if code and not re.fullmatch(r'[A-Z0-9]{4,32}',code):raise ValueError('El código debe tener de 4 a 32 letras o números')
    if (code or (old and old['code_hash'])) and (not first or not surname or len(first)>80 or len(surname)>80):raise ValueError('Indica primer nombre y primer apellido para la factura')
    hashed=generate_password_hash(code) if code else old['code_hash'] if old else None
    lookup=hashlib.sha256(code.encode()).hexdigest() if code else old['code_lookup'] if old else None
    if old:
     c.execute('UPDATE employees SET name=?,identity=?,active=?,first_name=?,first_surname=?,code_hash=?,code_lookup=?,version=version+1 WHERE id=?',(name,number,active,first,surname,hashed,lookup,old['id']));eid=old['id']
    else:eid=c.execute('INSERT INTO employees(name,identity,active,first_name,first_surname,code_hash,code_lookup) VALUES(?,?,?,?,?,?,?)',(name,number,active,first,surname,hashed,lookup)).lastrowid
   except sqlite3.IntegrityError:raise ValueError('Ya existe un empleado con esa identidad o código')
   accounting.audit(c,'EMPLEADO_ACTUALIZADO',eid,dict(active=active))
  return jsonify(ok=True)
 @app.get('/api/admin/discount-beneficiaries')
 def discount_history():
  with connect() as c:return jsonify([dict(r) for r in c.execute('SELECT d.*,i.number,i.created_at,i.status,b.name AS branch_name FROM discount_beneficiaries d JOIN invoices i ON i.id=d.invoice_id JOIN branches b ON b.id=i.branch_id ORDER BY i.id DESC')])
