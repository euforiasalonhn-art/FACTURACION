import access_sync
import cash_safety
import employee_sessions
import cash_close_print
import company_benefits
import terminals,print_queue
import delivery
import employee_menu
import os, sys, sqlite3, json, secrets, time, re, io, hashlib, warnings, base64, binascii
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from datetime import datetime
from flask import g, Flask, request, jsonify, render_template, session, send_file, Response
import network_backup
import operations
import fiscal, accounting, commerce, catalog_update, timecheck, sar_reports, cancellation, employees, cancellation_mail, discount_exclusions, reprints, full_backup
from PIL import Image, ImageOps, UnidentifiedImageError
from werkzeug.security import generate_password_hash, check_password_hash
ROOT=Path(getattr(sys,'_MEIPASS',Path(__file__).parent))
DATA=Path(os.environ.get('FRY_CHICKEN_DATA_DIR',Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'FRYChickenPOS'/'data'))
DATA.mkdir(parents=True,exist_ok=True)
DB=DATA/'fry_chicken.db'
app=Flask(__name__,template_folder=str(ROOT/'templates'),static_folder=str(ROOT/'static'))
app.jinja_env.globals['receipt_items']=fiscal.receipt_items
app.jinja_env.globals['pc_name']=terminals.pc_labels.name
TOKEN=secrets.token_hex(32)
app.config.update(SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Strict',MAX_CONTENT_LENGTH=80*1024*1024)
FAILURES={}
def setting(c,key,default=None):
 r=c.execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone()
 return json.loads(r[0]) if r else default
def save_setting(c,key,value): c.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',(key,json.dumps(value)))
def auth_config(c): return setting(c,'auth')
def public_state(c):
 a=auth_config(c); branch_id=session.get('branch_id') if session.get('role')=='local' else a['branch_id']
 b=c.execute('SELECT id,name FROM branches WHERE id=?',(branch_id,)).fetchone()
 state=dict(role=session.get('role'),branch=dict(b) if b else {'id':a['branch_id'],'name':''},email=a['email'] if session.get('role')=='admin' else '',setup_required=not a.get('configured',False))
 state['branch_options']=[dict(r) for r in c.execute('SELECT id,name FROM branches WHERE active=1 AND password IS NOT NULL ORDER BY name COLLATE NOCASE')]
 if session.get('role')=='local':state['cashier']=dict(id=session['cashier_id'],name=session['cashier_name'],full_name=session['cashier_full_name'])
 state['request_token']=TOKEN
 state['terminal']=terminals.public()
 if state['terminal']['remote']:
  tid=state['terminal']['branch_id'];branch=c.execute('SELECT id,name FROM branches WHERE id=?',(tid,)).fetchone();state['branch']=dict(branch);state['branch_options']=[r for r in state['branch_options'] if r['id']==tid]
 return state | accounting.account_state(c)

class PersistentConnection(sqlite3.Connection):
 def __exit__(self,typ,value,tb):
  try:
   if typ is None and self.total_changes:network_backup.before_commit(self,DATA)
   result=super().__exit__(typ,value,tb)
   if typ is None and self.total_changes:
    try:full_backup.write(DB,DATA)
    except Exception as error:app.logger.error('No se pudo actualizar el respaldo JSON: %s',error)
    access_sync.notify()
   return result
  except Exception:
   self.rollback();raise
  finally:self.close()

def connect():
 c=sqlite3.connect(DB,timeout=20,factory=PersistentConnection); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON');c.execute('PRAGMA synchronous=EXTRA'); return c
def money(v):
 try:
  d=Decimal(str(v))
  if not d.is_finite() or d<0 or d>Decimal('100000000'): raise ValueError()
  return int((d*100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
 except (InvalidOperation,ValueError,TypeError): raise ValueError('Importe inválido')
def init_db():
 full_backup.restore_if_missing(DB,DATA)
 # Back up an existing database before either access migration.
 if DB.exists():
  with connect() as old:
   has_invoices=bool(old.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='invoices'").fetchone())
   has_accountants=bool(old.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='accountants'").fetchone())
   has_branches=bool(old.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='branches'").fetchone())
   branch_columns=[r['name'] for r in old.execute('PRAGMA table_info(branches)')] if has_branches else []
   has_special=bool(old.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='special_orders'").fetchone())
   special_columns=[r['name'] for r in old.execute('PRAGMA table_info(special_orders)')] if has_special else []
   invoice_columns=[r['name'] for r in old.execute('PRAGMA table_info(invoices)')] if has_invoices else []
   needs_migration=has_invoices and (any(k not in invoice_columns for k in ['snapshot','request_id','exempt','exempted','taxable_15','taxable_18']) or 'cash_session_id' not in special_columns or not has_special or not has_accountants or any(k not in branch_columns for k in ['password','version','active','created_at']))
   needs_migration=needs_migration or (has_invoices and ('terminal_id' not in invoice_columns or not old.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='print_jobs'").fetchone()))
   if needs_migration:
    label='v44' if 'terminal_id' not in invoice_columns else 'v19' if has_accountants else 'v5'
    backup=DATA/('respaldo-antes-'+label+'-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.db')
    with sqlite3.connect(backup) as dest: old.backup(dest)
 with connect() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS branches(id INTEGER PRIMARY KEY,name TEXT NOT NULL,address TEXT NOT NULL,rtn TEXT,next_invoice INTEGER NOT NULL,password TEXT,version INTEGER NOT NULL DEFAULT 1,active INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY,name TEXT NOT NULL,category TEXT NOT NULL,price INTEGER NOT NULL,tax_type TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS invoices(id INTEGER PRIMARY KEY,branch_id INTEGER REFERENCES branches(id),number INTEGER,invoice_type TEXT,customer_name TEXT,customer_rtn TEXT,payment_method TEXT,amount_received INTEGER,subtotal INTEGER,tax_15 INTEGER,tax_18 INTEGER,discount INTEGER,total INTEGER,created_at TEXT,status TEXT DEFAULT 'EMITIDA',snapshot TEXT,request_id TEXT UNIQUE, UNIQUE(branch_id,number));''')
  c.executescript('CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT); CREATE TABLE IF NOT EXISTS customers(rtn TEXT PRIMARY KEY,name TEXT NOT NULL);')
  if 'fiscal_number' not in [r['name'] for r in c.execute('PRAGMA table_info(invoices)')]: c.execute('ALTER TABLE invoices ADD COLUMN fiscal_number TEXT')
  branch_columns=[r['name'] for r in c.execute('PRAGMA table_info(branches)')]
  if 'password' not in branch_columns: c.execute('ALTER TABLE branches ADD COLUMN password TEXT')
  if 'version' not in branch_columns: c.execute('ALTER TABLE branches ADD COLUMN version INTEGER NOT NULL DEFAULT 1')
  if 'active' not in branch_columns: c.execute('ALTER TABLE branches ADD COLUMN active INTEGER NOT NULL DEFAULT 1')
  if 'created_at' not in branch_columns: c.execute("ALTER TABLE branches ADD COLUMN created_at TEXT NOT NULL DEFAULT ''")
  if 'delivery_fee' not in [r['name'] for r in c.execute('PRAGMA table_info(invoices)')]:c.execute('ALTER TABLE invoices ADD COLUMN delivery_fee INTEGER NOT NULL DEFAULT 0')
  invoice_columns=[r['name'] for r in c.execute('PRAGMA table_info(invoices)')]
  for key,typ in [('snapshot','TEXT'),('request_id','TEXT'),('exempt','INTEGER NOT NULL DEFAULT 0'),('exempted','INTEGER NOT NULL DEFAULT 0'),('taxable_15','INTEGER NOT NULL DEFAULT 0'),('taxable_18','INTEGER NOT NULL DEFAULT 0')]:
   if key not in invoice_columns:c.execute('ALTER TABLE invoices ADD COLUMN '+key+' '+typ)
  c.execute('CREATE UNIQUE INDEX IF NOT EXISTS unique_invoice_request ON invoices(request_id) WHERE request_id IS NOT NULL')
  c.execute('CREATE UNIQUE INDEX IF NOT EXISTS unique_fiscal_number ON invoices(fiscal_number) WHERE fiscal_number IS NOT NULL')
  c.execute('CREATE TABLE IF NOT EXISTS product_images(product_id INTEGER PRIMARY KEY REFERENCES products(id),data BLOB NOT NULL,digest TEXT NOT NULL)')
  if not setting(c,'network_instance'):save_setting(c,'network_instance',secrets.token_hex(16))
  company_benefits.init(c);accounting.init(c);employee_menu.init(c);operations.init(c);commerce.init(c);employees.init(c);employee_sessions.init(c);cancellation_mail.init(c);discount_exclusions.init(c);terminals.init(c);print_queue.init(c);access_sync.init(c)
  if not setting(c,'auth'):
   save_setting(c,'auth',dict(email='frychickencompany@gmail.com',password=generate_password_hash('FRY2026'),pin=generate_password_hash('1234'),branch_id=1,version=1,configured=False))
  c.execute("INSERT OR IGNORE INTO customers(rtn,name) SELECT customer_rtn,customer_name FROM invoices WHERE invoice_type='RTN' AND length(customer_rtn)=14 AND customer_rtn NOT GLOB '*[^0-9]*' ORDER BY id DESC")
  key=setting(c,'session_key')
  if not key: key=secrets.token_hex(32); save_setting(c,'session_key',key)
  app.secret_key=key
  legacy_auth=auth_config(c)
  c.execute('UPDATE branches SET password=? WHERE id=? AND password IS NULL',(legacy_auth['pin'],legacy_auth['branch_id']))
  import woocommerce_sync
  woocommerce_sync.init(c)
 full_backup.write(DB,DATA)
 commerce.start_worker(connect);cancellation_mail.start(connect);timecheck.start();woocommerce_sync.start(connect,prepare_photo)
@app.before_request
def guard():
 if request.path.startswith('/api/products') and request.method!='GET':return jsonify(error='Los productos y precios se administran en WooCommerce'),403
 if request.path=='/api/admin/products-import':return jsonify(error='El catálogo se sincroniza desde WooCommerce'),403
 if request.path=='/api/admin/delete-test-invoices':return jsonify(error='Función retirada'),404
 if session.get('role')=='accountant':
  match=re.fullmatch(r'/api/invoices/(\d+)',request.path)
  if match:
   with connect() as c:
    row=c.execute('SELECT fiscal_number FROM invoices WHERE id=?',(int(match[1]),)).fetchone()
    if row and not row['fiscal_number']:return jsonify(error='Documento de prueba reservado a ajustes'),403
 if session.get('role')=='accountant' and request.path.startswith(('/api/special-orders','/api/cash','/api/accounting/access-status','/api/meals')):return jsonify(error='Acceso exclusivo de ajustes'),403
 with connect() as c:
  error=terminals.prepare(c)
  if error:return error
 machine_end=request.method=='POST' and request.path=='/api/terminal/end-session' and bool(terminals.terminal_id())
 if request.method!='GET' and not machine_end and request.headers.get('X-POS-Token')!=TOKEN: return jsonify(error='Solicitud no autorizada',refresh_token=True),403
 if cash_safety.CLOSING.is_set() and request.method!='GET':return jsonify(error='PC 1 se está cerrando. No se registró esta operación.'),503
 if not request.path.startswith('/api/'): return
 if request.path in ['/api/auth/state','/api/auth/login','/api/theme']: return
 if request.method=='GET' and request.path=='/api/cash/exit-check' and terminals.terminal_id():return
 if machine_end:return
 with connect() as c:
  a=auth_config(c)
  if session.get('version')!=a['version'] or not accounting.valid_account(c): session.clear()
 if session.get('role')=='local':
  with connect() as c:branch=c.execute('SELECT version FROM branches WHERE id=?',(session.get('branch_id'),)).fetchone()
  if not branch or branch['version']!=session.get('branch_version'): session.clear()
 if not session.get('role'):
  # Preview exposes only product photos after validating the branch password.
  if request.method=='GET' and re.fullmatch(r'/api/products/[0-9]+/photo',request.path):
   with connect() as c:
    pending=session.get('branch_login',{});branch=c.execute('SELECT version,active FROM branches WHERE id=?',(pending.get('branch_id'),)).fetchone()
    if branch and branch['active'] and pending.get('branch_version')==branch['version'] and pending.get('terminal_id')==terminals.terminal_id() and pending.get('terminal_version')==getattr(g,'terminal',{}).get('version',1) and pending.get('expires',0)>time.time():return
  return jsonify(error='Inicia sesión para continuar'),401
 if session.get('role')=='accountant':
  with connect() as c:
   if accounting.account_state(c).get('must_change') and request.path not in ['/api/auth/password','/api/auth/logout']: return jsonify(error='Cambia tu contraseña temporal para continuar'),403
  if request.method!='GET' and request.path not in ['/api/auth/password','/api/auth/logout']: return jsonify(error='El contador tiene acceso de consulta y exportación'),403
 if request.path.startswith(('/api/accounting','/api/reports')) and session.get('role') not in ['admin','accountant']: return jsonify(error='Acceso contable requerido'),403
 admin=(request.path.startswith(('/api/admin',)) or '/void' in request.path or (request.path.startswith(('/api/products','/api/branches')) and request.method!='GET'))
 if admin and session['role']!='admin': return jsonify(error='Esta función es exclusiva del administrador'),403
 if session['role']=='local' and request.path in ['/api/invoices','/api/quote'] and request.method=='POST':
  if request.json.get('branch_id')!=session.get('branch_id'): return jsonify(error='Solo puedes facturar en la sucursal de tu perfil'),403
@app.get('/api/auth/state')
def state():
 with connect() as c:
  if session.get('version')!=auth_config(c)['version'] or not accounting.valid_account(c): session.clear()
  if session.get('role')=='local':
   branch=c.execute('SELECT version FROM branches WHERE id=?',(session.get('branch_id'),)).fetchone()
   if not branch or branch['version']!=session.get('branch_version'): session.clear()
  return jsonify(public_state(c))
@app.post('/api/auth/login')
def login():
 d=request.json; role=d.get('role')
 if role not in ('admin','local','accountant'): raise ValueError('Tipo de acceso inválido')
 now=time.monotonic(); failure_key=(role,terminals.terminal_id());history=FAILURES.get(failure_key,[]); history=[t for t in history if now-t<30]
 if len(history)>=5: return jsonify(error='Demasiados intentos. Espera 30 segundos.'),429
 with connect() as c:
  c.execute('BEGIN IMMEDIATE')
  a=auth_config(c)
  accountant=c.execute('SELECT * FROM accountants WHERE email=? AND active=1',(str(d.get('email','')).strip().lower(),)).fetchone() if role=='accountant' else None
  branch=c.execute('SELECT id,name,password,version,active FROM branches WHERE id=?',(d.get('branch_id'),)).fetchone() if role=='local' else None
  if role=='local' and (not branch or not branch['active']): return jsonify(error='Ese perfil de sucursal no está activo. Pide al administrador que lo configure.'),401
  if role=='local':
   if d.get('stage')=='BRANCH':
    if session.get('role')=='local':cash_safety.require_closed(c,terminals.terminal_id())
    if not branch['password'] or not check_password_hash(branch['password'],str(d.get('password',''))):
     FAILURES[failure_key]=history+[now];return jsonify(error='Contraseña de sucursal incorrecta.'),401
    employee_sessions.release_current(c,session);session.clear()
    session.update(version=a['version'],branch_login=dict(branch_id=branch['id'],branch_version=branch['version'],terminal_id=terminals.terminal_id(),terminal_version=getattr(g,'terminal',{}).get('version',1),expires=time.time()+300))
    return jsonify(next_step='EMPLOYEE',branch=dict(id=branch['id'],name=branch['name']),products=product_list(c),category_order=setting(c,'category_order',[]))
   pending=session.get('branch_login',{})
   if d.get('stage')!='EMPLOYEE' or pending.get('branch_id')!=branch['id'] or pending.get('branch_version')!=branch['version'] or pending.get('terminal_id')!=terminals.terminal_id() or pending.get('terminal_version')!=getattr(g,'terminal',{}).get('version',1) or pending.get('expires',0)<time.time() or session.get('version')!=a['version']:
    session.clear();FAILURES[failure_key]=history+[now];return jsonify(error='Primero valida la contraseña de esta sucursal.',restart_branch=True),401
  cashier=employees.authenticate(c,d.get('employee_code')) if role=='local' else None
  if role=='local' and not cashier:
   FAILURES[failure_key]=history+[now];return jsonify(error='Código de empleado incorrecto, inactivo o sin configurar. Solicita tu código al administrador.'),401
  ok=(role=='accountant' and accountant and check_password_hash(accountant['password'],str(d.get('password','')))) or (role=='admin' and str(d.get('email','')).strip().lower()==a['email'] and check_password_hash(a['password'],str(d.get('password','')))) or role=='local'
  if not ok:
   FAILURES[failure_key]=history+[now]; return jsonify(error='Datos de acceso incorrectos o sucursal sin configurar'),401
  employee_token=None
  if role=='local':
   try:employee_token=employee_sessions.acquire(c,cashier['id'],terminals.terminal_id())
   except employee_sessions.SessionInUse as error:return jsonify(error=str(error),active_pc=error.pc),409
  else:employee_sessions.release_current(c,session)
  FAILURES.pop(failure_key,None); session.clear(); session.update(role=role,version=a['version'],email=a['email'] if role=='admin' else str(d.get('email','')).strip().lower() if role=='accountant' else 'local')
  if role=='accountant':session.update(accountant_id=accountant['id'],accountant_version=accountant['version'])
  if role=='local':session.update(branch_id=branch['id'],branch_version=branch['version'],cashier_id=cashier['id'],cashier_version=cashier['version'],cashier_full_name=cashier['name'],cashier_name=cashier['first_name']+' '+cashier['first_surname'],employee_session_token=employee_token)
  session['terminal_id']=terminals.terminal_id();session['terminal_version']=getattr(g,'terminal',{}).get('version',1)
  accounting.audit(c,'INICIO_SESION',role,{})
  return jsonify(public_state(c))
@app.post('/api/auth/logout')
def logout():
 with connect() as c:
  if session.get('role')=='local':cash_safety.require_closed(c,terminals.terminal_id())
  employee_sessions.release_current(c,session)
  accounting.audit(c,'CIERRE_SESION',session.get('cashier_id',session.get('role','')),{})
 session.clear();return jsonify(ok=True)
@app.post('/api/admin/config')
def admin_config():
 d=request.json
 with connect() as c:
  a=auth_config(c)
  if not check_password_hash(a['password'],str(d.get('current_password',''))): raise ValueError('La contraseña actual del administrador es incorrecta')
  email=str(d.get('email',a['email'])).strip().lower()
  if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email): raise ValueError('Correo inválido')
  password=str(d.get('password','')); pin=str(d.get('pin',''))
  if password and len(password)<6: raise ValueError('La contraseña debe tener al menos 6 caracteres')
  if pin and len(pin)<4: raise ValueError('La contraseña de sucursal debe tener al menos 4 caracteres')
  b=c.execute('SELECT id FROM branches WHERE id=?',(d.get('branch_id'),)).fetchone()
  if not b: raise ValueError('Selecciona la sucursal de esta PC')
  a.update(email=email,branch_id=b['id'],configured=True,version=a['version']+1)
  if password: a['password']=generate_password_hash(password)
  if pin:
   a['pin']=generate_password_hash(pin)
   c.execute('UPDATE branches SET password=?,version=version+1 WHERE id=?',(a['pin'],b['id']))
  save_setting(c,'auth',a); session['version']=a['version'];session['email']=a['email'];accounting.audit(c,'CONFIGURACION_ACCESOS',a['branch_id'],{})
  return jsonify(public_state(c))
@app.route('/api/customers',methods=['GET','POST'])
def customers():
 with connect() as c:
  if request.method=='POST':
   name=required(request.json,'name'); rtn=required(request.json,'rtn')
   if not re.fullmatch(r'[0-9]{14}',rtn): raise ValueError('El RTN debe contener 14 dígitos')
   c.execute('INSERT INTO customers VALUES(?,?) ON CONFLICT(rtn) DO UPDATE SET name=excluded.name',(rtn,name))
  return jsonify([dict(r) for r in c.execute('SELECT * FROM customers ORDER BY name')])
@app.errorhandler(ValueError)
def bad(e): return jsonify(error=str(e)),400
@app.errorhandler(sqlite3.IntegrityError)
def integrity(e):
 detail=str(e)
 if 'branches.name' in detail:return jsonify(error='Ya existe una sucursal con ese nombre.'),400
 if 'branches.rtn' in detail:return jsonify(error='Ese RTN ya está asignado a otra sucursal.'),400
 if 'NOT NULL constraint failed: branches.created_at' in detail:return jsonify(error='Faltaba guardar la fecha de creación de la sucursal. Actualiza el programa y vuelve a intentar.'),400
 return jsonify(error='No se pudieron guardar los datos. Revisa que no exista ya una sucursal con el mismo nombre o RTN.'),400
def required(data,key):
 s=str(data.get(key,'')).strip()
 if not s or len(s)>200: raise ValueError('Completa '+key)
 return s
@app.get('/api/clock')
def clock_status():return jsonify(timecheck.status())
@app.route('/api/admin/cash-receipt-copy',methods=['GET','POST'])
def cash_receipt_copy():
 with connect() as c:
  if request.method=='POST':
   value=(request.get_json() or {}).get('copy')
   if type(value) is not bool:raise ValueError('Selecciona los ejemplares de caja')
   save_setting(c,'cash_receipt_copy',value)
  return jsonify(copy=setting(c,'cash_receipt_copy',False))
@app.get('/')
def home():
 with connect() as c:theme=setting(c,'appearance','light')
 return render_template('index.html',token=TOKEN,theme=theme)
@app.post('/api/theme')
def save_theme():
 theme=(request.json or {}).get('theme')
 if theme not in ['light','dark']:raise ValueError('Selecciona modo claro u oscuro')
 with connect() as c:save_setting(c,'appearance',theme)
 return jsonify(ok=True)
@app.route('/api/branches',methods=['GET','POST'])
@app.patch('/api/branches/<int:branch_id>')
@app.delete('/api/branches/<int:branch_id>')
def branches(branch_id=None):
 with connect() as c:
  if request.method=='POST':
   d=request.json; n=int(d.get('next_invoice',1))
   if n<1 or n>999999999: raise ValueError('Número inicial inválido')
   name=required(d,'name'); password=required(d,'password')
   if len(password)<4: raise ValueError('La contraseña de sucursal debe tener al menos 4 caracteres')
   if c.execute('SELECT 1 FROM branches WHERE name=? COLLATE NOCASE',(name,)).fetchone(): raise ValueError('Ya existe una sucursal con ese nombre')
   columns=[r['name'] for r in c.execute('PRAGMA table_info(branches)')]
   values={'name':name,'address':str(d.get('address','')).strip(),'rtn':str(d.get('rtn','')).strip() or None,'next_invoice':n,'password':generate_password_hash(password),'version':1,'active':1,'created_at':datetime.now().astimezone().isoformat(timespec='seconds')}
   insert_columns=[k for k in values if k in columns]
   cur=c.execute('INSERT INTO branches('+','.join(insert_columns)+') VALUES('+','.join('?' for _ in insert_columns)+')',[values[k] for k in insert_columns])
   a=auth_config(c);current=c.execute('SELECT active FROM branches WHERE id=?',(a.get('branch_id'),)).fetchone()
   if not current or not current['active']:
    a.update(branch_id=cur.lastrowid,version=a['version']+1);save_setting(c,'auth',a);session['version']=a['version']
   accounting.audit(c,'SUCURSAL_CREADA',cur.lastrowid,dict(name=name))
  if request.method=='PATCH':
   d=request.json
   if d.get('active') is True:
    if not c.execute('UPDATE branches SET active=1,version=version+1 WHERE id=?',(branch_id,)).rowcount:return jsonify(error='Sucursal no encontrada'),404
    accounting.audit(c,'SUCURSAL_RESTAURADA',branch_id,{})
   else:
    password=required(d,'password')
    if len(password)<4: raise ValueError('La contraseña de sucursal debe tener al menos 4 caracteres')
    if not c.execute('UPDATE branches SET password=?,version=version+1 WHERE id=? AND active=1',(generate_password_hash(password),branch_id)).rowcount: return jsonify(error='Sucursal no encontrada o inactiva'),404
    accounting.audit(c,'CLAVE_SUCURSAL_ACTUALIZADA',branch_id,{})
  if request.method=='DELETE':
   branch=c.execute('SELECT id,name FROM branches WHERE id=? AND active=1',(branch_id,)).fetchone()
   if not branch:return jsonify(error='Sucursal no encontrada o ya retirada'),404
   if c.execute('SELECT 1 FROM invoices WHERE branch_id=? LIMIT 1',(branch_id,)).fetchone():raise ValueError('No se puede retirar esta sucursal porque ya tiene facturas registradas.')
   if c.execute('SELECT 1 FROM cash_sessions WHERE branch_id=? LIMIT 1',(branch_id,)).fetchone():raise ValueError('No se puede retirar esta sucursal porque tiene turnos de caja registrados.')
   if c.execute('SELECT 1 FROM special_orders WHERE branch_id=? LIMIT 1',(branch_id,)).fetchone():raise ValueError('Esta sucursal tiene registros especiales guardados; conserva su historial.')
   cfg=fiscal.config(c,branch_id)
   if cfg.get('enabled'):raise ValueError('No se puede retirar esta sucursal mientras tenga un CAI activo. Desactiva la autorización primero.')
   c.execute('UPDATE branches SET active=0,version=version+1 WHERE id=?',(branch_id,))
   a=auth_config(c)
   if a.get('branch_id')==branch_id:
    other=c.execute('SELECT id FROM branches WHERE active=1 ORDER BY id LIMIT 1').fetchone()
    if other:
     a.update(branch_id=other['id'],version=a['version']+1);save_setting(c,'auth',a);session['version']=a['version']
   accounting.audit(c,'SUCURSAL_RETIRADA',branch_id,dict(name=branch['name']))
  rows=[dict(r) for r in c.execute('SELECT id,name,address,rtn,next_invoice,active FROM branches ORDER BY active DESC,name COLLATE NOCASE')]
  if session.get('role')=='local': rows=[r for r in rows if r['id']==session.get('branch_id')]
  if terminals.terminal_id():rows=[r for r in rows if r['id']==g.terminal['branch_id']]
  return jsonify(rows)
def product_list(c):
 rows=[]
 for r in c.execute('SELECT p.*,i.digest FROM products p LEFT JOIN product_images i ON i.product_id=p.id WHERE p.active=1 ORDER BY p.category,p.name'):
  d=dict(r); digest=d.pop('digest'); d['image_url']=f"/api/products/{d['id']}/photo?v={digest}" if digest else None; rows.append(d)
 return rows

def prepare_photo(raw):
 if len(raw)>8*1024*1024: raise ValueError('La foto no puede superar 8 MB')
 try:
  with warnings.catch_warnings():
   warnings.simplefilter('error',Image.DecompressionBombWarning)
   with Image.open(io.BytesIO(raw)) as source:
    if source.format not in ('JPEG','PNG','WEBP'): raise ValueError('Usa una foto JPG, PNG o WebP')
    if source.width*source.height>16000000: raise ValueError('La foto no puede superar 16 megapíxeles')
    source.seek(0); image=ImageOps.exif_transpose(source).convert('RGBA');image.thumbnail((1024,1024))
    output=Image.new('RGB',image.size,'white');output.paste(image,mask=image.getchannel('A'))
    buffer=io.BytesIO();output.save(buffer,format='JPEG',quality=88);data=buffer.getvalue()
 except (UnidentifiedImageError,OSError,Image.DecompressionBombError,Image.DecompressionBombWarning): raise ValueError('La foto está dañada o no es una imagen válida')
 return data,hashlib.sha256(data).hexdigest()
def save_photo(c,pid,file):
 raw=file.read(8*1024*1024+1)
 data,digest=prepare_photo(raw)
 c.execute('INSERT INTO product_images VALUES(?,?,?) ON CONFLICT(product_id) DO UPDATE SET data=excluded.data,digest=excluded.digest',(pid,data,digest))

@app.errorhandler(413)
def too_large(e): return jsonify(error='El archivo es demasiado grande. Usa una foto de hasta 8 MB'),413
@app.route('/api/products',methods=['GET','POST'])
@app.route('/api/products/<int:pid>',methods=['PATCH'])
def products(pid=None):
 with connect() as c:
  if request.method!='GET':
   d=request.form if request.mimetype=='multipart/form-data' else request.get_json()
   old=c.execute('SELECT * FROM products WHERE id=?',(pid,)).fetchone() if pid else None
   if pid and not old: return jsonify(error='Producto no encontrado'),404
   old=dict(old) if old else dict(name='',category='',price=0,tax_type='15')
   tax=str(d.get('tax_type',old['tax_type']))
   if tax not in ['15','18','EXENTO','EXONERADO']: raise ValueError('Clasificación inválida')
   values=(required(dict(name=d.get('name',old['name'])),'name'),required(dict(category=d.get('category',old['category'])),'category'),money(d['price']) if 'price' in d else old['price'],tax)
   if pid: c.execute('UPDATE products SET name=?,category=?,price=?,tax_type=? WHERE id=?',values+(pid,))
   else: pid=c.execute('INSERT INTO products(name,category,price,tax_type) VALUES(?,?,?,?)',values).lastrowid
   photo=request.files.get('photo')
   if photo and photo.filename: save_photo(c,pid,photo)
   accounting.audit(c,'PRODUCTO_GUARDADO',pid,dict(name=values[0],price=values[2],tax_type=values[3]))
  return jsonify(product_list(c))

@app.route('/api/products/<int:pid>/photo',methods=['GET','POST','DELETE'])
def product_photo(pid):
 with connect() as c:
  if not c.execute('SELECT 1 FROM products WHERE id=?',(pid,)).fetchone(): return jsonify(error='Producto no encontrado'),404
  if request.method=='DELETE': c.execute('DELETE FROM product_images WHERE product_id=?',(pid,));return jsonify(product_list(c))
  if request.method=='POST':
   photo=request.files.get('photo')
   if not photo or not photo.filename: raise ValueError('Selecciona una foto')
   save_photo(c,pid,photo); return jsonify(product_list(c))
  row=c.execute('SELECT data,digest FROM product_images WHERE product_id=?',(pid,)).fetchone()
  if not row: return jsonify(error='Este producto no tiene foto'),404
  response=send_file(io.BytesIO(row['data']),mimetype='image/jpeg',etag=row['digest'],max_age=86400)
  response.cache_control.public=False;response.cache_control.private=True
  return response

@app.get('/api/admin/products-export')
def products_export():
 """A portable catalog containing the normalized JPEG bytes for every product image."""
 with connect() as c:
  excluded={r['product_id'] for r in c.execute('SELECT product_id FROM discount_exclusions')}
  catalog=[]
  for row in c.execute('SELECT p.*,i.data FROM products p LEFT JOIN product_images i ON i.product_id=p.id WHERE p.active=1 ORDER BY p.category COLLATE NOCASE,p.name COLLATE NOCASE'):
   image=base64.b64encode(row['data']).decode('ascii') if row['data'] else None
   catalog.append(dict(id=row['id'],name=row['name'],category=row['category'],price_l=f"{row['price']/100:.2f}",price_centavos=row['price'],tax_type=row['tax_type'],sin_descuento=row['id'] in excluded,imagen_jpeg_base64=image))
  document=dict(formato='FRYChickenPOS-PRODUCTOS',version=1,exportado_en=datetime.now().astimezone().isoformat(timespec='seconds'),orden_categorias=setting(c,'category_order',[]),productos=catalog)
  accounting.audit(c,'CATALOGO_EXPORTADO',session.get('email','admin'),dict(products=len(catalog)))
 payload=json.dumps(document,ensure_ascii=False,indent=2)
 return Response(payload,content_type='application/json; charset=utf-8',headers={'Content-Disposition':'attachment; filename="FRYChickenPOS-productos.json"','Cache-Control':'no-store'})

def import_catalog_document(document):
 if not isinstance(document,dict) or document.get('formato')!='FRYChickenPOS-PRODUCTOS' or document.get('version')!=1: raise ValueError('El archivo no es un catálogo JSON válido de FRYChickenPOS')
 records=document.get('productos')
 if not isinstance(records,list) or not records: raise ValueError('El archivo debe contener al menos un producto')
 if len(records)>1000: raise ValueError('El archivo supera el límite de 1,000 productos')
 names=set();prepared=[]
 for position,item in enumerate(records,1):
  if not isinstance(item,dict): raise ValueError(f'Producto {position}: formato inválido')
  name=required(item,'name');category=required(item,'category');key=(name.casefold(),category.casefold())
  if key in names: raise ValueError(f'Producto {position}: el nombre está repetido dentro de su categoría')
  names.add(key);tax=str(item.get('tax_type',''))
  if tax not in ['15','18','EXENTO','EXONERADO']: raise ValueError(f'Producto {position}: impuesto inválido')
  if 'price_l' not in item: raise ValueError(f'Producto {position}: falta el precio')
  try: price=money(item['price_l'])
  except ValueError: raise ValueError(f'Producto {position}: precio inválido')
  encoded=item.get('imagen_jpeg_base64');image=None
  if encoded is not None:
   if not isinstance(encoded,str): raise ValueError(f'Producto {position}: imagen inválida')
   try: image=prepare_photo(base64.b64decode(encoded.encode('ascii'),validate=True))
   except (ValueError,UnicodeEncodeError,binascii.Error): raise ValueError(f'Producto {position}: imagen inválida o dañada')
  prepared.append((name,category,price,tax,bool(item.get('sin_descuento')),image))
 order=document.get('orden_categorias',[])
 if not isinstance(order,list) or any(not isinstance(x,str) or not x.strip() or len(x)>200 for x in order): raise ValueError('El orden de categorías es inválido')
 cleaned_order=[]
 for category in order:
  category=category.strip()
  if category.casefold() not in [x.casefold() for x in cleaned_order]: cleaned_order.append(category)
 return prepared,cleaned_order

@app.post('/api/admin/products-import')
def products_import():
 prepared,order=import_catalog_document(request.get_json(silent=True))
 with connect() as c:
  c.execute('DELETE FROM product_images')
  c.execute('DELETE FROM discount_exclusions')
  c.execute('UPDATE company_benefits SET active=0')
  c.execute('DELETE FROM products')
  for name,category,price,tax,excluded,image in prepared:
   product_id=c.execute('INSERT INTO products(name,category,price,tax_type) VALUES(?,?,?,?)',(name,category,price,tax)).lastrowid
   if image:c.execute('INSERT INTO product_images(product_id,data,digest) VALUES(?,?,?)',(product_id,image[0],image[1]))
   if excluded:c.execute('INSERT INTO discount_exclusions(product_id) VALUES(?)',(product_id,))
  save_setting(c,'category_order',order)
  save_setting(c,'catalog_enrichment_v15',[r['id'] for r in c.execute('SELECT id FROM products')])
  accounting.audit(c,'CATALOGO_IMPORTADO',session.get('email','admin'),dict(products=len(prepared),images=sum(bool(x[5]) for x in prepared)))
  rows=product_list(c)
 return jsonify(products=rows,count=len(rows))

def calculate(c,d): return delivery.apply(fiscal.calculate(c,commerce.prepare(c,d),money,company_benefits.approved(c,d)),d,money)
@app.route('/api/fiscal/state')
def fiscal_state():
 with connect() as c:
  branch=int(request.args.get('branch_id',auth_config(c)['branch_id']))
  if session['role']=='local' and branch!=session.get('branch_id'): return jsonify(error='Sucursal no asignada'),403
  cfg=fiscal.config(c,branch);warning=''
  if cfg['enabled']:
   try:fiscal.ensure_available(c,cfg)
   except ValueError as e:warning=str(e)
  remaining=cfg['range_end']-cfg['next_number']+1 if cfg['enabled'] else None
  days=(datetime.strptime(cfg['deadline'],'%Y-%m-%d').date()-datetime.now().astimezone().date()).days if cfg['enabled'] else None
  notice=('Quedan '+str(remaining)+' facturas. ' if remaining is not None and remaining<=100 else '')+('La autorización vence en '+str(days)+' días.' if days is not None and days<=7 else '')
  return jsonify(config=cfg,warning=warning,notice=notice)
@app.post('/api/admin/fiscal')
def fiscal_config():
 d=request.json
 with connect() as c:
  c.execute('BEGIN IMMEDIATE')
  branch=int(d.get('branch_id',0))
  if not c.execute('SELECT 1 FROM branches WHERE id=?',(branch,)).fetchone():raise ValueError('Selecciona la sucursal')
  cfg=fiscal.validate(c,branch,d);fiscal.save(c,branch,cfg);accounting.audit(c,'CONFIGURACION_FISCAL',branch,dict(cai=cfg['cai'],next_number=cfg['next_number'],enabled=cfg['enabled']))
  return jsonify(config=cfg)
@app.post('/api/quote')
def quote():
 with connect() as c:
  delivery.fee(request.json,money)
  if request.json.get('employee_meal'):
   employee_menu.validate(c,request.json)
   return jsonify(fiscal.calculate(c,dict(request.json,discount=0,discount_type='PERCENT'),money))
  if request.json.get('special_order'):
   if not commerce.config(c)['owner_enabled']:raise ValueError('Registro especial no habilitado')
   return jsonify(fiscal.calculate(c,dict(request.json,discount=0,discount_type='PERCENT'),money))
  fiscal.ensure_available(c,fiscal.config(c,request.json.get('branch_id',1)))
  return jsonify(calculate(c,request.json))
@app.post('/api/invoices')
def sale():
 d=request.json; key=required(d,'request_id')
 if d.get('employee_meal') or d.get('special_order'):raise ValueError('Los consumos sin cobro deben registrarse en su apartado')
 operations.order_fields(d)
 with connect() as c:
  c.execute('BEGIN IMMEDIATE')
  prev=c.execute('SELECT id,terminal_id FROM invoices WHERE request_id=?',(key,)).fetchone()
  if prev:
   if prev['terminal_id']!=terminals.terminal_id():return jsonify(error='Este cobro pertenece a otra terminal'),403
   if session['role']=='local' and c.execute('SELECT branch_id FROM invoices WHERE id=?',(prev['id'],)).fetchone()[0]!=session.get('branch_id'): return jsonify(error='Venta de otra sucursal'),403
   return jsonify(id=prev['id'],kitchen_id=(c.execute("SELECT id FROM kitchen_orders WHERE kind='SALE' AND source_id=?",(prev['id'],)).fetchone() or [None])[0])
  b=c.execute('SELECT * FROM branches WHERE id=?',(d.get('branch_id'),)).fetchone()
  if not b: raise ValueError('Selecciona un punto de venta')
  cash_safety.require_current(c,b['id'],terminals.terminal_id())
  typ=d.get('invoice_type','NORMAL'); name=str(d.get('customer_name','')).strip() or 'CONSUMIDOR FINAL'; rtn=str(d.get('customer_rtn','')).strip()
  if typ=='NORMAL':name='CONSUMIDOR FINAL';rtn=''
  if len(name)>200: raise ValueError('El nombre del cliente es demasiado largo')
  if typ not in ['NORMAL','RTN']: raise ValueError('Tipo inválido')
  if typ=='RTN' and (name=='CONSUMIDOR FINAL' or len(rtn)!=14 or not rtn.isascii() or not rtn.isdigit()): raise ValueError('Introduce nombre y RTN de 14 dígitos')
  method=d.get('payment_method')
  if method not in ['Efectivo','Tarjeta','Transferencia','Mixto']: raise ValueError('Forma de pago inválida')
  discount_person=employees.beneficiary(c,d)
  calc=calculate(c,d)
  if calc.get('company_benefit'):name=calc['company_benefit']['name']
  payments={k:0 for k in ['Efectivo','Transferencia','Tarjeta']}
  if method=='Mixto':
   entered=d.get('payments',{})
   if not isinstance(entered,dict):raise ValueError('Desglosa los pagos')
   payments={k:money(entered.get(k,0)) for k in payments}
   if sum(payments.values())!=calc['total']:raise ValueError('La suma de pagos debe ser igual al total de la factura')
  else:
   payments[method]=calc['total']
   if d.get('payment_entry_version')==2:
    entered=d.get('payments')
    if not isinstance(entered,dict):raise ValueError('Digita el monto cobrado con el medio seleccionado')
    declared={k:money(entered.get(k,0)) for k in payments}
    if declared!=payments:raise ValueError('El monto cobrado debe ser igual al total de la compra. Para combinar medios de pago selecciona Mixto.')
  cash_received=money(d.get('amount_received',0)) if payments['Efectivo'] else 0
  if cash_received<payments['Efectivo']:raise ValueError('El efectivo recibido es insuficiente')
  received=cash_received+payments['Transferencia']+payments['Tarjeta']
  cfg=fiscal.config(c,b['id']);fiscal.ensure_available(c,cfg)
  extra={k:str(d.get(k,'')).strip() for k in ['purchase_order','exemption_certificate','sag']}
  if any(len(v)>100 for v in extra.values()): raise ValueError('Los datos de exoneración son demasiado largos')
  if cfg['enabled'] and calc['exempted']>0:
   if typ!='RTN' or (not calc.get('company_benefit') and not any(extra.values())): raise ValueError('Completa cliente RTN y documentación de exoneración aplicable')
  fiscal_number=fiscal.number(cfg,cfg['next_number']) if cfg['enabled'] else None
  sales_payments,delivery_payments=delivery.split_payments(payments,calc['delivery_fee'])
  snap=json.dumps(dict(terminal_id=terminals.terminal_id(),terminal_name=terminals.terminal_name(),**operations.order_fields(d),sales_payments=sales_payments,delivery_payments=delivery_payments,payments=payments,cash_received=cash_received,branch={k:b[k] for k in ['id','name','address','rtn']},fiscal=cfg,fiscal_number=fiscal_number,extra=extra,cashier=session['cashier_name'] if session['role']=='local' else 'ADMINISTRADOR',cashier_id=session.get('cashier_id'),cashier_full_name=session.get('cashier_full_name','ADMINISTRADOR'),total_words=fiscal.amount_words(calc['total']),**calc),ensure_ascii=False)
  values=dict(branch_id=b['id'],number=b['next_invoice'],invoice_type=typ,customer_name=name,customer_rtn=rtn if typ=='RTN' else '',payment_method=method,amount_received=received,created_at=datetime.now().astimezone().isoformat(timespec='seconds'),snapshot=snap,request_id=key)
  values['delivery_fee']=calc['delivery_fee'];values['terminal_id']=terminals.terminal_id()
  values.update({k:calc[k] for k in ['subtotal','exempt','exempted','taxable_15','taxable_18','tax_15','tax_18','discount','total']})
  cur=c.execute('INSERT INTO invoices('+','.join(values)+') VALUES('+','.join('?' for _ in values)+')',list(values.values()))
  if discount_person:c.execute('INSERT INTO discount_beneficiaries(invoice_id,profile,employee_id,name,identity) VALUES(?,?,?,?,?)',(cur.lastrowid,discount_person['profile'],discount_person['employee_id'],discount_person['name'],discount_person['identity']))
  shift=c.execute("SELECT id FROM cash_sessions WHERE branch_id=? AND terminal_id=? AND status='ABIERTA'",(b['id'],terminals.terminal_id())).fetchone()
  c.execute('UPDATE invoices SET fiscal_number=?,cash_session_id=? WHERE id=?',(fiscal_number,shift['id'] if shift else None,cur.lastrowid))
  accounting.audit(c,'FACTURA_EMITIDA',cur.lastrowid,dict(number=fiscal_number,total=calc['total'],payments=payments,shift=shift['id'] if shift else None))
  if cfg['enabled']:
   cfg['next_number']+=1;fiscal.save(c,b['id'],cfg)
  c.execute('UPDATE branches SET next_invoice=next_invoice+1 WHERE id=?',(b['id'],))
  if typ=='RTN': c.execute('INSERT INTO customers VALUES(?,?) ON CONFLICT(rtn) DO UPDATE SET name=excluded.name',(rtn,name))
  kid=operations.kitchen(c,b['id'],'SALE',cur.lastrowid,calc,d)
  print_queue.invoice_original(c,cur.lastrowid)
  return jsonify(id=cur.lastrowid,kitchen_id=kid)
@app.get('/api/invoices/<int:i>')
def detail(i):
 with connect() as c:
  r=c.execute('SELECT * FROM invoices WHERE id=?',(i,)).fetchone()
  if not r: return jsonify(error='Comprobante no encontrado'),404
  if session['role']=='local' and r['branch_id']!=session.get('branch_id'): return jsonify(error='Venta de otra sucursal'),403
  d=dict(r); d['snapshot']=json.loads(d['snapshot'] or '{}')
  order=c.execute("SELECT id FROM kitchen_orders WHERE kind='SALE' AND source_id=?",(i,)).fetchone();d['kitchen_id']=order[0] if order else None
  if not d['snapshot']:
   b=c.execute('SELECT name,address,rtn FROM branches WHERE id=?',(d['branch_id'],)).fetchone();d['snapshot']=dict(branch=dict(b),items=[])
  if d['snapshot'].get('calculation_version')==4:
   d['receipt_html']=render_template('receipt.html',r=d,s=d['snapshot'],copy=request.args.get('copy','ORIGINAL'),fmt=lambda n:f'{Decimal(n)/100:,.2f}')
  return jsonify(d)
@app.post('/api/invoices/<int:i>/void')
def void(i):
 with connect() as c:
  c.execute('BEGIN IMMEDIATE');return cancel_invoice(c,i,str((request.json or {}).get('reason','')).strip())
def cancel_invoice(c,i,reason):
 if not 3<=len(reason)<=300:raise ValueError('Indica el motivo de anulación (3 a 300 caracteres)')
 r=c.execute('SELECT * FROM invoices WHERE id=?',(i,)).fetchone()
 if not r:return jsonify(error='Factura no encontrada'),404
 if r['status']=='ANULADA':return jsonify(ok=True)
 if r['cash_session_id']:
  shift=c.execute('SELECT status FROM cash_sessions WHERE id=?',(r['cash_session_id'],)).fetchone()
  if shift and shift['status']=='CERRADA':raise ValueError('El turno ya está cerrado. Requiere un procedimiento de corrección contable; no se modifica el cierre')
 c.execute("UPDATE invoices SET status='ANULADA',void_reason=?,void_actor=?,void_at=? WHERE id=?",(reason,accounting.actor(),accounting.now(),i));accounting.audit(c,'FACTURA_ANULADA',i,dict(reason=reason,total=r['total']))
 c.execute("UPDATE print_jobs SET state='CANCELLED',last_error='Factura anulada antes del envío a impresora' WHERE role='cash' AND source_kind='SALE' AND source_id=? AND state IN ('PENDING','PAUSED','CLAIMED','FAILED')",(i,))
 kitchen=c.execute("SELECT id FROM kitchen_orders WHERE kind='SALE' AND source_id=?",(i,)).fetchone()
 if kitchen:c.execute("UPDATE print_jobs SET state='CANCELLED',last_error='Pedido anulado antes del envío a cocina' WHERE role='kitchen' AND source_id=? AND state IN ('PENDING','PAUSED','CLAIMED','FAILED')",(kitchen['id'],))
 cancellation_mail.enqueue(c,r,reason)
 return jsonify(ok=True)
@app.get('/api/reports')
def reports():
 with connect() as c:return jsonify(accounting.book(c,request.args)['invoices'])
network_backup.register(app,connect,DATA)
terminals.register(app,connect,money)
print_queue.register(app,connect)
employee_menu.register(app,connect)
operations.register(app,connect,money)
accounting.register(app,connect,money)
sar_reports.register(app,connect)
employees.register(app,connect)
reprints.register(app,connect)
discount_exclusions.register(app,connect)
cancellation_mail.register(app,connect)
cancellation.register(app,connect,setting,save_setting,cancel_invoice)
company_benefits.register(app,connect)
commerce.register(app,connect,lambda c,d:fiscal.calculate(c,d,money),money)
access_sync.register(app,lambda:DB,DATA)
cash_safety.register(app,connect)
employee_sessions.register(app,connect)
cash_close_print.register(app,connect)

import woocommerce_sync
woocommerce_sync.register(app,connect,prepare_photo)
import owner_reports
owner_reports.register(app,connect)
@app.post('/api/admin/reset-sales')
def reset_all_sales():
 if (request.get_json() or {}).get('confirmation')!='RESET TODAS LAS VENTAS':raise ValueError('Escribe RESET TODAS LAS VENTAS para confirmar')
 with terminals.REQUEST_LOCK:
  backup=DATA/('respaldo-antes-reset-ventas-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.db')
  with sqlite3.connect(DB) as source,sqlite3.connect(backup) as target:source.backup(target)
  with connect() as c:
   c.execute('BEGIN IMMEDIATE')
   if c.execute("SELECT 1 FROM print_jobs WHERE state IN ('CLAIMED','SPOOLING')").fetchone():raise ValueError('Espera a que finalicen las impresiones antes de reiniciar las ventas')
   count=c.execute('SELECT COUNT(*) FROM invoices').fetchone()[0]
   c.execute("CREATE TEMP TABLE reset_jobs AS SELECT id FROM print_jobs WHERE source_kind='SALE' OR (source_kind='KITCHEN' AND source_id IN (SELECT id FROM kitchen_orders WHERE kind='SALE'))")
   c.execute('DELETE FROM print_requests WHERE job_id IN (SELECT id FROM reset_jobs)')
   c.execute('DELETE FROM print_jobs WHERE id IN (SELECT id FROM reset_jobs)')
   c.execute("DELETE FROM kitchen_orders WHERE kind='SALE'")
   tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
   for table in ['invoice_items','discount_beneficiaries','cancellation_mail','credit_notes']:
    if table in tables:c.execute('DELETE FROM '+table)
   c.execute('DELETE FROM invoices')
   accounting.audit(c,'RESET_TODAS_VENTAS','TODAS',dict(count=count,backup=backup.name))
 return jsonify(count=count)
@app.post('/api/admin/delete-test-invoices')
def delete_test_invoices():
 if (request.get_json() or {}).get('confirmation')!='ELIMINAR PRUEBAS':raise ValueError('Escribe ELIMINAR PRUEBAS para confirmar')
 with terminals.REQUEST_LOCK:
  backup=DATA/('respaldo-antes-eliminar-pruebas-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.db')
  with sqlite3.connect(DB) as source,sqlite3.connect(backup) as target:source.backup(target)
  with connect() as c:
   c.execute('BEGIN IMMEDIATE')
   c.execute("CREATE TEMP TABLE purge_invoice_ids AS SELECT id FROM invoices WHERE fiscal_number IS NULL OR trim(fiscal_number)=''")
   count=c.execute('SELECT COUNT(*) FROM purge_invoice_ids').fetchone()[0]
   c.execute("CREATE TEMP TABLE purge_kitchen_ids AS SELECT id FROM kitchen_orders WHERE kind='SALE' AND source_id IN (SELECT id FROM purge_invoice_ids)")
   c.execute("CREATE TEMP TABLE purge_job_ids AS SELECT id FROM print_jobs WHERE (source_kind='SALE' AND source_id IN (SELECT id FROM purge_invoice_ids)) OR (source_kind='KITCHEN' AND source_id IN (SELECT id FROM purge_kitchen_ids))")
   if c.execute("SELECT 1 FROM print_jobs WHERE id IN (SELECT id FROM purge_job_ids) AND state IN ('CLAIMED','SPOOLING')").fetchone():raise ValueError('Hay una impresión de prueba en proceso. Espera a que termine y vuelve a intentar.')
   c.execute('DELETE FROM print_requests WHERE job_id IN (SELECT id FROM purge_job_ids)')
   c.execute('DELETE FROM print_jobs WHERE id IN (SELECT id FROM purge_job_ids)')
   c.execute('DELETE FROM kitchen_orders WHERE id IN (SELECT id FROM purge_kitchen_ids)')
   tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
   for table in ['invoice_items','discount_beneficiaries','cancellation_mail','credit_notes']:
    if table in tables:c.execute('DELETE FROM '+table+' WHERE invoice_id IN (SELECT id FROM purge_invoice_ids)')
   c.execute('DELETE FROM invoices WHERE id IN (SELECT id FROM purge_invoice_ids)')
   accounting.audit(c,'FACTURAS_PRUEBA_ELIMINADAS','TODAS',dict(count=count,backup=backup.name))
 return jsonify(count=count)
import cash_corrections
cash_corrections.register(app,connect,setting,save_setting,money)
if __name__=='__main__':
 init_db();access_sync.start(DB,DATA,Path(__file__).parent);app.run(host='127.0.0.1',port=5050,debug=False)
