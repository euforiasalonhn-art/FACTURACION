"""Cola durable central: un original por documento; copias explícitas e idempotentes."""
import json,uuid
from decimal import Decimal
from flask import request,session,jsonify,render_template
import accounting,terminals

def init(c):
 c.execute('''CREATE TABLE IF NOT EXISTS print_jobs(id INTEGER PRIMARY KEY,origin_key TEXT NOT NULL UNIQUE,role TEXT NOT NULL,branch_id INTEGER NOT NULL,source_kind TEXT NOT NULL,source_id INTEGER NOT NULL,terminal_id INTEGER NOT NULL,html TEXT NOT NULL,state TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,last_error TEXT NOT NULL DEFAULT '',is_copy INTEGER NOT NULL DEFAULT 0)''')
 c.execute('CREATE TABLE IF NOT EXISTS print_requests(request_key TEXT PRIMARY KEY,job_id INTEGER NOT NULL REFERENCES print_jobs(id))')

def invoice_html(c,i,copy='ORIGINAL'):
 r=dict(c.execute('SELECT * FROM invoices WHERE id=?',(i,)).fetchone());s=json.loads(r['snapshot'] or '{}');r['snapshot']=s
 row=c.execute("SELECT id FROM kitchen_orders WHERE kind='SALE' AND source_id=?",(i,)).fetchone();r['kitchen_id']=row[0] if row else None
 return render_template('receipt.html',r=r,s=s,copy=copy,fmt=lambda n:f'{Decimal(n)/100:,.2f}')

def kitchen_html(c,i,copy=False):
 r=dict(c.execute('SELECT * FROM kitchen_orders WHERE id=?',(i,)).fetchone());s=json.loads(r['snapshot'])
 cancelled=r['kind']=='SALE' and c.execute("SELECT 1 FROM invoices WHERE id=? AND status='ANULADA'",(r['source_id'],)).fetchone()
 return ('<h2>PEDIDO ANULADO · NO PREPARAR</h2>' if cancelled else '')+('<h2>REIMPRESIÓN</h2>' if copy else '')+render_template('kitchen.html',r=r,s=s)

def enqueue(c,role,kind,source,branch,html,key,is_copy=False):
 cfgrow=c.execute('SELECT value FROM settings WHERE key=?',('printer' if role=='cash' else 'kitchen_printer',)).fetchone();cfg=json.loads(cfgrow[0]) if cfgrow else {'automatic':True}
 state='PENDING' if is_copy or cfg.get('automatic',True) else 'PAUSED';stamp=accounting.now()
 c.execute('INSERT OR IGNORE INTO print_jobs(origin_key,role,branch_id,source_kind,source_id,terminal_id,html,state,created_at,updated_at,is_copy) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(key,role,branch,kind,source,terminals.terminal_id(),html,state,stamp,stamp,int(is_copy)))
 return c.execute('SELECT id FROM print_jobs WHERE origin_key=?',(key,)).fetchone()[0]

def invoice_original(c,i):
 r=c.execute('SELECT branch_id FROM invoices WHERE id=?',(i,)).fetchone()
 original=enqueue(c,'cash','SALE',i,r['branch_id'],invoice_html(c,i),'ORIGINAL:SALE:'+str(i))
 option=c.execute("SELECT value FROM settings WHERE key='cash_receipt_copy'").fetchone()
 if option and json.loads(option[0]):enqueue(c,'cash','SALE',i,r['branch_id'],invoice_html(c,i,'COPIA'),'AUTO-COPY:SALE:'+str(i),True)
 return original
def kitchen_original(c,i):
 r=c.execute('SELECT branch_id FROM kitchen_orders WHERE id=?',(i,)).fetchone();return enqueue(c,'kitchen','KITCHEN',i,r['branch_id'],kitchen_html(c,i),'ORIGINAL:KITCHEN:'+str(i))

def recover_worker(c):
 # Un documento entregado al sistema de impresión podría haber salido en papel.
 c.execute("UPDATE print_jobs SET state='UNCERTAIN',last_error='El servidor se cerró durante el envío. Revisa el papel antes de pedir una copia.',updated_at=? WHERE state='SPOOLING'",(accounting.now(),))
 c.execute("UPDATE print_jobs SET state='PENDING',updated_at=? WHERE state='CLAIMED'",(accounting.now(),))

def claim(c,roles):
 if not roles:return None
 c.execute('BEGIN IMMEDIATE');row=c.execute("SELECT * FROM print_jobs WHERE state='PENDING' AND role IN ("+','.join('?' for _ in roles)+') ORDER BY id LIMIT 1',list(roles)).fetchone()
 if not row:return None
 c.execute("UPDATE print_jobs SET state='CLAIMED',updated_at=?,last_error='' WHERE id=? AND state='PENDING'",(accounting.now(),row['id']))
 return dict(row)

def spooling(c,jid):
 return bool(c.execute("UPDATE print_jobs SET state='SPOOLING',updated_at=? WHERE id=? AND state='CLAIMED'",(accounting.now(),jid)).rowcount)

def finish(c,jid,ok,error=''):
 row=c.execute('SELECT state FROM print_jobs WHERE id=?',(jid,)).fetchone()
 if not row or row['state']=='CANCELLED':return
 state='SPOOLED' if ok else 'UNCERTAIN' if row['state']=='SPOOLING' else 'FAILED'
 c.execute("UPDATE print_jobs SET state=?,updated_at=?,last_error=?,html=CASE WHEN ? THEN '' ELSE html END WHERE id=?",(state,accounting.now(),'' if ok else (error[:500] or 'No se confirmó el envío. Revisa la impresora antes de pedir una copia.'),int(ok),jid))

def register(app,connect):
 @app.get('/api/printing/jobs')
 def jobs():
  if session.get('role') not in ['admin','local']:return jsonify(error='Acceso no permitido'),403
  with connect() as c:
   vals=[];where=''
   if session['role']=='local':where=' WHERE branch_id=?';vals=[session['branch_id']]
   rows=[dict(r) for r in c.execute('SELECT id,role,branch_id,source_kind,source_id,terminal_id,state,created_at,updated_at,last_error,is_copy FROM print_jobs'+where+' ORDER BY id DESC LIMIT 150',vals)]
   for r in rows:
    terminal=c.execute('SELECT name FROM terminals WHERE id=?',(r['terminal_id'],)).fetchone();r['terminal_name']=terminals.pc_labels.name(r.get('terminal_id',0))
    document=c.execute('SELECT fiscal_number,number FROM invoices WHERE id=?',(r['source_id'],)).fetchone() if r['source_kind']=='SALE' else None;r['document_number']=(document['fiscal_number'] or str(document['number'])) if document else str(r['source_id'])
   return jsonify(rows)
 @app.post('/api/printing/reprint')
 def reprint():
  if session.get('role') not in ['admin','local']:return jsonify(error='Acceso no permitido'),403
  d=request.json or {};role=d.get('role');source=int(d.get('source_id',0));key=str(d.get('request_id',''))
  try:uuid.UUID(key)
  except (ValueError,AttributeError):raise ValueError('Identificador de impresión inválido')
  if role not in ['cash','kitchen']:raise ValueError('Tipo de impresión inválido')
  with connect() as c:
   c.execute('BEGIN IMMEDIATE');table='invoices' if role=='cash' else 'kitchen_orders';r=c.execute('SELECT branch_id FROM '+table+' WHERE id=?',(source,)).fetchone()
   if not r:return jsonify(error='Documento no encontrado'),404
   if session['role']=='local' and r['branch_id']!=session['branch_id']:return jsonify(error='Documento de otra sucursal'),403
   request_key='COPY:'+str(terminals.terminal_id())+':'+role+':'+str(source)+':'+key
   previous=c.execute('SELECT job_id FROM print_requests WHERE request_key=?',(request_key,)).fetchone()
   if previous:return jsonify(id=previous['job_id'],is_copy=bool(c.execute('SELECT is_copy FROM print_jobs WHERE id=?',(previous['job_id'],)).fetchone()[0]))
   waiting=c.execute("SELECT * FROM print_jobs WHERE role=? AND source_kind=? AND source_id=? AND state IN ('PENDING','CLAIMED','SPOOLING','PAUSED','FAILED') ORDER BY is_copy,id LIMIT 1",(role,'SALE' if role=='cash' else 'KITCHEN',source)).fetchone()
   if waiting:
    jid=waiting['id']
    if waiting['state'] in ['PAUSED','FAILED']:c.execute("UPDATE print_jobs SET state='PENDING',last_error='',updated_at=? WHERE id=?",(accounting.now(),jid))
   else:
    content=invoice_html(c,source,'COPIA') if role=='cash' else kitchen_html(c,source,True)
    jid=enqueue(c,role,'SALE' if role=='cash' else 'KITCHEN',source,r['branch_id'],content,request_key,True)
   c.execute('INSERT INTO print_requests VALUES(?,?)',(request_key,jid))
   is_copy=bool(c.execute('SELECT is_copy FROM print_jobs WHERE id=?',(jid,)).fetchone()[0]);accounting.audit(c,'COPIA_EN_COLA_CENTRAL' if is_copy else 'ORIGINAL_CENTRAL_CONFIRMADO',jid,dict(source=source,role=role))
   return jsonify(id=jid,is_copy=is_copy)
 @app.post('/api/admin/printing/jobs/<int:jid>/release')
 def release(jid):
  with connect() as c:
   c.execute('BEGIN IMMEDIATE');row=c.execute('SELECT * FROM print_jobs WHERE id=?',(jid,)).fetchone()
   if not row:return jsonify(error='Documento no encontrado'),404
   if row['state'] not in ['PAUSED','FAILED']:raise ValueError('Solo se reintenta un documento que no se entregó al sistema de impresión. Para un envío dudoso solicita una copia.')
   c.execute("UPDATE print_jobs SET state='PENDING',last_error='',updated_at=? WHERE id=?",(accounting.now(),jid));accounting.audit(c,'IMPRESION_LIBERADA',jid,{})
  return jsonify(ok=True)
