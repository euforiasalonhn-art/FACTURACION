import terminals
import cash_safety
import delivery
import operations
"""Descuentos autorizados y consumos internos sin cobro."""
import employees
import json, io, smtplib, ssl, ctypes, os, threading
SEND_LOCK=threading.Lock()
WORKER_STARTED=False
from datetime import datetime
from decimal import Decimal
from email.message import EmailMessage
from flask import request, jsonify, session, send_file

DEFAULT=dict(employee=0,senior=0,owner_enabled=False,owner_email='',smtp_host='',smtp_port=587,smtp_user='',smtp_from='',smtp_secret='')
def config(c):
 r=c.execute("SELECT value FROM settings WHERE key='commerce'").fetchone()
 return DEFAULT|json.loads(r[0]) if r else DEFAULT.copy()
def protect(value,decode=False):
 import base64
 from ctypes import wintypes
 class Blob(ctypes.Structure):_fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_byte))]
 raw=base64.b64decode(value) if decode else value.encode();buf=ctypes.create_string_buffer(raw);src=Blob(len(raw),ctypes.cast(buf,ctypes.POINTER(ctypes.c_byte)));dst=Blob()
 fn=ctypes.windll.crypt32.CryptUnprotectData if decode else ctypes.windll.crypt32.CryptProtectData
 if not fn(ctypes.byref(src),None,None,None,None,(0 if decode else 4),ctypes.byref(dst)):raise ValueError('No se pudo proteger la contraseña de correo en Windows')
 try:out=ctypes.string_at(dst.data,dst.size)
 finally:ctypes.windll.kernel32.LocalFree(dst.data)
 return out.decode() if decode else base64.b64encode(out).decode()
def prepare(c,d):
 cfg=config(c);d=dict(d);kind=d.get('discount_profile','NONE')
 if kind=='EMPLOYEE':raise ValueError('El descuento de empleado ya no está disponible. Utiliza el almuerzo gratuito autorizado.')
 if kind not in ['NONE','EMPLOYEE','SENIOR']:raise ValueError('Selecciona un descuento autorizado')
 employees.beneficiary(c,d)
 d.update(discount_type='PERCENT',discount=cfg[{'EMPLOYEE':'employee','SENIOR':'senior'}[kind]] if kind!='NONE' else 0)
 return d
def init(c):
 c.execute('''CREATE TABLE IF NOT EXISTS special_orders(id INTEGER PRIMARY KEY,branch_id INTEGER,created_at TEXT,recipient TEXT,snapshot TEXT,request_id TEXT UNIQUE,email_to TEXT,email_status TEXT DEFAULT 'PENDIENTE',email_error TEXT DEFAULT '',actor TEXT)''')
 if 'cash_session_id' not in [r['name'] for r in c.execute('PRAGMA table_info(special_orders)')]:c.execute('ALTER TABLE special_orders ADD COLUMN cash_session_id INTEGER')
def pdf(rows):
 from reportlab.pdfgen import canvas
 b=io.BytesIO();p=canvas.Canvas(b,pagesize=(595,842))
 for r in rows:
  s=json.loads(r['snapshot']);y=800
  lines=['FRY CHICKEN - REGISTRO ESPECIAL SIN COBRO',f"Registro #{r['id']} - {r['created_at']}",s['branch_name'],'Beneficiario: '+r['recipient'],'Comprobante interno - no consume correlativo CAI','']
  lines += [f"{it['quantity']} x {it['name']} - L {it['line_total']/100:,.2f}" for it in s['items']]
  lines += ['',f"Valor de referencia: L {s['total']/100:,.2f}",f"Subtotal de referencia: L {s['subtotal']/100:,.2f}",f"ISV referencia 15%: L {s['tax_15']/100:,.2f}",f"ISV referencia 18%: L {s['tax_18']/100:,.2f}",'Importe cobrado: L 0.00','Correo: '+r['email_to'],'Estado de envio: '+r['email_status']]
  for line in lines:
   if y<45:p.showPage();y=800
   p.setFont('Helvetica',10);p.drawString(35,y,line[:105]);y-=17
  p.showPage()
 p.save();b.seek(0);return b
def _send(connect,rid):
 with connect() as c:r=dict(c.execute('SELECT * FROM special_orders WHERE id=?',(rid,)).fetchone());cfg=config(c)
 if r['email_status']=='ENVIADO':return 'ENVIADO'
 try:
  if not cfg['smtp_host'] or not cfg['smtp_from']:raise ValueError('Configura el servidor y remitente de correo en Administrador')
  msg=EmailMessage();msg['Subject']=f"FRY Chicken - Registro especial #{rid}";msg['From']=cfg['smtp_from'];msg['To']=r['email_to'];msg.set_content('Se registró un consumo sin cobro. El comprobante se adjunta en PDF.');msg.add_attachment(pdf([r]).getvalue(),maintype='application',subtype='pdf',filename=f'Registro-especial-{rid}.pdf')
  port=int(cfg['smtp_port']);client=smtplib.SMTP_SSL(cfg['smtp_host'],port,timeout=15,context=ssl.create_default_context()) if port==465 else smtplib.SMTP(cfg['smtp_host'],port,timeout=15)
  with client:
   if port!=465:client.starttls(context=ssl.create_default_context())
   if cfg['smtp_user']:client.login(cfg['smtp_user'],protect(cfg['smtp_secret'],True))
   client.send_message(msg)
  status,error='ENVIADO',''
 except Exception as e:status,error='PENDIENTE',type(e).__name__+': revisa la conexión y configuración de correo'
 with connect() as c:c.execute('UPDATE special_orders SET email_status=?,email_error=? WHERE id=?',(status,error,rid))
 return status
def send(connect,rid):
 with SEND_LOCK:return _send(connect,rid)
def start_worker(connect):
 global WORKER_STARTED
 if WORKER_STARTED:return
 WORKER_STARTED=True
 def worker():
  while True:
   threading.Event().wait(300)
   try:
    with connect() as c:ids=[r[0] for r in c.execute("SELECT id FROM special_orders WHERE email_status='PENDIENTE' ORDER BY id LIMIT 20")]
    for rid in ids:send(connect,rid)
   except Exception:pass
 threading.Thread(target=worker,daemon=True,name='FRY-correo-pendiente').start()
def register(app,connect,calculate,money):
 @app.route('/api/category-order',methods=['GET','POST'])
 def category_order():
  default=[]
  import unicodedata
  def norm(v):return ''.join(x for x in unicodedata.normalize('NFD',v) if unicodedata.category(x)!='Mn').strip().lower()
  with connect() as c:
   extra=[r[0] for r in c.execute('SELECT DISTINCT category FROM products WHERE active=1 ORDER BY category') if norm(r[0]) not in ['envios a domicilio','menu empleados']]
   names=list(dict.fromkeys(default+extra))
   saved=c.execute("SELECT value FROM settings WHERE key='category_order'").fetchone()
   order=json.loads(saved[0]) if saved else default
   if request.method=='POST':
    if session['role']!='admin':return jsonify(error='Solo el administrador puede ordenar las categorías'),403
    order=request.json.get('order')
    if not isinstance(order,list) or any(not isinstance(v,str) for v in order) or len(order)!=len(set(order)) or set(order)!=set(names):raise ValueError('La lista cambió. Recarga las categorías y vuelve a ordenar.')
    c.execute("INSERT OR REPLACE INTO settings VALUES('category_order',?)",(json.dumps(order,ensure_ascii=False),))
   return jsonify(order=[v for v in order if v in names]+[v for v in names if v not in order])

 @app.route('/api/commerce',methods=['GET','POST'])
 def settings():
  with connect() as c:
   cfg=config(c)
   if request.method=='POST':
    if session['role']!='admin':return jsonify(error='Solo el administrador configura estas opciones'),403
    d=request.json
    for k in ['employee','senior']:
     v=Decimal(str(d.get(k,0)))
     if not v.is_finite() or not 0<=v<=100:raise ValueError('El porcentaje debe estar entre 0 y 100')
     cfg[k]=str(v)
    for k in ['owner_email','smtp_host','smtp_user','smtp_from']:cfg[k]=str(d.get(k,'')).strip()
    cfg['owner_enabled']=d.get('owner_enabled') is True;cfg['smtp_port']=int(d.get('smtp_port',587))
    if cfg['smtp_port'] not in [465,587]:raise ValueError('Usa puerto seguro 465 o 587')
    if cfg['owner_enabled'] and ('@' not in cfg['owner_email'] or not cfg['smtp_host'] or not cfg['smtp_from']):raise ValueError('Completa correo destinatario, servidor y remitente para habilitar el registro especial')
    if d.get('smtp_password'):cfg['smtp_secret']=protect(str(d['smtp_password']))
    c.execute("INSERT OR REPLACE INTO settings VALUES('commerce',?)",(json.dumps(cfg),))
   result={k:v for k,v in cfg.items() if k!='smtp_secret'}
   if session['role']!='admin':result={k:cfg[k] for k in ['employee','senior','owner_enabled']}
   return jsonify(result)
 @app.route('/api/special-orders',methods=['GET','POST'])
 def orders():
  if request.method=='POST':
   d=request.json
   with connect() as c:
    c.execute('BEGIN IMMEDIATE');cfg=config(c);branch=int(d.get('branch_id',0))
    if session['role'] not in ['admin','local']:return jsonify(error='Acceso no permitido'),403
    if session['role']=='local' and branch!=session.get('branch_id'):return jsonify(error='Sucursal incorrecta'),403
    prev=c.execute('SELECT id,branch_id,terminal_id FROM special_orders WHERE request_id=?',(str(d.get('request_id','')),)).fetchone()
    if prev:
     if prev['branch_id']!=branch or prev['terminal_id']!=terminals.terminal_id():return jsonify(error='Registro de otra sucursal'),403
     return jsonify(id=prev['id'],email_status='YA REGISTRADO',kitchen_id=(c.execute("SELECT id FROM kitchen_orders WHERE kind='SPECIAL' AND source_id=?",(prev['id'],)).fetchone() or [None])[0])
    if not cfg['owner_enabled']:raise ValueError('El administrador no ha habilitado el registro especial')
    recipient=str(d.get('recipient','')).strip()
    if not recipient or len(recipient)>200 or not d.get('request_id'):raise ValueError('Completa el nombre del dueño o ejecutivo')
    b=c.execute('SELECT name FROM branches WHERE id=? AND active=1',(branch,)).fetchone()
    if not b:raise ValueError('Sucursal no disponible')
    shift=c.execute("SELECT id FROM cash_sessions WHERE branch_id=? AND terminal_id=? AND status='ABIERTA'",(branch,terminals.terminal_id())).fetchone()
    cash_safety.require_current(c,branch,terminals.terminal_id())
    if not shift:raise ValueError('Inicia caja antes de registrar una compra')
    delivery.fee(dict(d,special_order=True),money)
    calc=calculate(c,dict(d,discount=0,discount_type='PERCENT'));calc['branch_name']=b['name']
    rid=c.execute('INSERT INTO special_orders(branch_id,created_at,recipient,snapshot,request_id,email_to,actor) VALUES(?,?,?,?,?,?,?)',(branch,datetime.now().astimezone().isoformat(timespec='seconds'),recipient,json.dumps(calc,ensure_ascii=False),d['request_id'],cfg['owner_email'],session.get('email','local'))).lastrowid
    c.execute('UPDATE special_orders SET cash_session_id=?,terminal_id=? WHERE id=?',(shift['id'],terminals.terminal_id(),rid))
    kid=operations.kitchen(c,branch,'SPECIAL',rid,calc,d,recipient)
   return jsonify(id=rid,kitchen_id=kid,email_status=send(connect,rid))
  if session['role'] not in ['admin','accountant']:return jsonify(error='Acceso contable requerido'),403
  with connect() as c:rows=[dict(r) for r in c.execute('SELECT * FROM special_orders ORDER BY id DESC')]
  for r in rows:r['snapshot']=json.loads(r['snapshot'])
  return jsonify(rows)
 @app.post('/api/admin/special-orders/<int:rid>/retry')
 def retry(rid):return jsonify(email_status=send(connect,rid))
 @app.get('/api/special-orders/export/<kind>')
 def special_export(kind):
  if session['role'] not in ['admin','accountant']:return jsonify(error='Acceso contable requerido'),403
  with connect() as c:rows=[dict(r) for r in c.execute('SELECT * FROM special_orders ORDER BY id')]
  if kind=='pdf':return send_file(pdf(rows),mimetype='application/pdf',as_attachment=True,download_name='Registros-especiales.pdf')
  if kind!='xlsx':raise ValueError('Formato no permitido')
  from openpyxl import Workbook
  w=Workbook();sheet=w.active;sheet.title='Consumos sin cobro';sheet.append(['Registro','Fecha','Sucursal','Beneficiario','Valor referencia L','Cobrado L','Correo','Estado envío','Productos'])
  for r in rows:
   s=json.loads(r['snapshot']);sheet.append([r['id'],r['created_at'],s['branch_name'],r['recipient'],s['total']/100,0,r['email_to'],r['email_status'],'; '.join(str(it['quantity'])+' x '+it['name'] for it in s['items'])])
   for cell in sheet[sheet.max_row]:
    if isinstance(cell.value,str):cell.data_type='s'
  detail=w.create_sheet('Productos');detail.append(['Registro','Producto','Cantidad','Precio unitario L','Importe L','Clasificación'])
  for r in rows:
   for it in json.loads(r['snapshot'])['items']:
    detail.append([r['id'],it['name'],it['quantity'],it['price']/100,it['line_total']/100,it['tax_type']])
    for cell in detail[detail.max_row]:
     if isinstance(cell.value,str):cell.data_type='s'
  b=io.BytesIO();w.save(b);b.seek(0);return send_file(b,as_attachment=True,download_name='Registros-especiales.xlsx')

