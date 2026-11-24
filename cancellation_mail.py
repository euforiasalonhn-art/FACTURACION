"""Avisos persistentes de anulación, enviados después de confirmar la transacción."""
import json,threading,smtplib,ssl,html
from email.message import EmailMessage
from flask import request,jsonify
import commerce,accounting
LOCK=threading.Lock();WAKE=threading.Event();STARTED=False

def init(c):
 c.execute('''CREATE TABLE IF NOT EXISTS cancellation_mail(invoice_id INTEGER PRIMARY KEY,email_to TEXT NOT NULL,payload TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'PENDIENTE',error TEXT NOT NULL DEFAULT '',sent_at TEXT,attempts INTEGER NOT NULL DEFAULT 0)''')
def recipient(c):
 r=c.execute("SELECT value FROM settings WHERE key='cancellation_email'").fetchone()
 if r:return json.loads(r[0])
 r=c.execute("SELECT value FROM settings WHERE key='auth'").fetchone()
 return json.loads(r[0]).get('email','') if r else ''
def enqueue(c,invoice,reason):
 b=c.execute('SELECT name FROM branches WHERE id=?',(invoice['branch_id'],)).fetchone()
 p=dict(invoice);p.update(branch_name=b['name'],void_reason=reason,void_actor=accounting.actor(),void_at=accounting.now(),status='ANULADA');c.execute('INSERT OR IGNORE INTO cancellation_mail(invoice_id,email_to,payload) VALUES(?,?,?)',(invoice['id'],recipient(c),json.dumps(p,ensure_ascii=False)))
def content(p):
 fmt=lambda n:f'L {float(n or 0)/100:,.2f}'
 lines=['FRY CHICKEN — FACTURA ANULADA','Orden: #'+str(p['number']),'Factura: '+str(p.get('fiscal_number') or 'INTERNO-'+str(p['number'])),'Sucursal: '+p['branch_name'],'Fecha de venta: '+p['created_at'],'Cliente: '+p['customer_name'],'RTN: '+str(p.get('customer_rtn') or '0'),'Total original: '+fmt(p['total']),'Descuento original: '+fmt(p['discount']),'ISV 15%: '+fmt(p['tax_15']),'ISV 18%: '+fmt(p['tax_18']),'Forma de pago: '+p['payment_method'],'Anulada por: '+p['void_actor'],'Fecha de anulación: '+p['void_at'],'Motivo: '+p['void_reason'],'','PRODUCTOS:']
 snap=json.loads(p.get('snapshot') or '{}')
 for it in snap.get('items',[]):lines.append(str(it['quantity'])+' × '+it['name']+' — '+fmt(it.get('line_total',0)))
 lines+=['','La factura se conserva ANULADA en el historial. Su número no se reutiliza. Este aviso no es una factura nueva.']
 return '\n'.join(lines)
def send(connect,i):
 with LOCK:
  with connect() as c:
   r=c.execute('SELECT * FROM cancellation_mail WHERE invoice_id=?',(i,)).fetchone()
   if not r or r['status']=='ENVIADO':return 'ENVIADO'
   r=dict(r);cfg=commerce.config(c)
  try:
   if not r['email_to'] or not cfg['smtp_host'] or not cfg['smtp_from']:raise ValueError('Configuración de correo pendiente')
   p=json.loads(r['payload']);body=content(p);msg=EmailMessage();msg['Subject']=f"FRY Chicken — FACTURA ANULADA — Orden #{p['number']}";msg['From']=cfg['smtp_from'];msg['To']=r['email_to'];msg['Message-ID']=f'<fry-cancellation-{i}@frychicken.local>';msg.set_content(body)
   attachment='<!doctype html><html lang="es"><meta charset="utf-8"><title>Factura anulada</title><body><h1>FACTURA ANULADA</h1><pre style="white-space:pre-wrap;font:15px Arial">'+html.escape(body)+'</pre></body></html>'
   msg.add_attachment(attachment.encode(),maintype='text',subtype='html',filename=f'Factura-anulada-orden-{p["number"]}.html')
   port=int(cfg['smtp_port']);client=smtplib.SMTP_SSL(cfg['smtp_host'],port,timeout=15,context=ssl.create_default_context()) if port==465 else smtplib.SMTP(cfg['smtp_host'],port,timeout=15)
   with client:
    if port!=465:client.starttls(context=ssl.create_default_context())
    if cfg['smtp_user']:client.login(cfg['smtp_user'],commerce.protect(cfg['smtp_secret'],True))
    client.send_message(msg)
   status,error='ENVIADO',''
  except Exception as e:status,error='PENDIENTE',type(e).__name__+': revisa conexión, destinatario y configuración SMTP'
  with connect() as c:
   c.execute('UPDATE cancellation_mail SET status=?,error=?,sent_at=?,attempts=attempts+1 WHERE invoice_id=?',(status,error,accounting.now() if status=='ENVIADO' else None,i))
  return status

def start(connect):
 global STARTED
 if STARTED:return
 STARTED=True
 def worker():
  while True:
   WAKE.wait(300);WAKE.clear()
   try:
    with connect() as c:ids=[r[0] for r in c.execute("SELECT invoice_id FROM cancellation_mail WHERE status='PENDIENTE' ORDER BY invoice_id LIMIT 30")]
    for i in ids:send(connect,i)
   except Exception:pass
 threading.Thread(target=worker,daemon=True,name='FRY-avisos-anulacion').start()
def register(app,connect):
 @app.after_request
 def cancellation_wake(response):
  if request.method=='POST' and response.status_code==200 and (request.path=='/api/cancellation/confirm' or request.path.endswith('/void')):WAKE.set()
  return response
 @app.route('/api/admin/cancellation-email',methods=['GET','POST'])
 def cancellation_mail_settings():
  with connect() as c:
   if request.method=='POST':
    email=str((request.json or {}).get('email','')).strip()
    import re
    if len(email)>254 or not re.fullmatch(r'[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+',email):raise ValueError('Ingresa un correo válido de la empresa')
    c.execute("INSERT OR REPLACE INTO settings VALUES('cancellation_email',?)",(json.dumps(email),));c.execute("UPDATE cancellation_mail SET email_to=? WHERE status='PENDIENTE'",(email,));accounting.audit(c,'CORREO_ANULACIONES_ACTUALIZADO','empresa',{})
   cfg=commerce.config(c)
   return jsonify(email=recipient(c),smtp_ready=bool(cfg['smtp_host'] and cfg['smtp_from']))
 @app.get('/api/admin/cancellation-emails')
 def cancellation_mail_history():
  with connect() as c:return jsonify([dict(r) for r in c.execute('SELECT m.invoice_id,m.email_to,m.status,m.error,m.sent_at,m.attempts,i.number,b.name AS branch_name FROM cancellation_mail m JOIN invoices i ON i.id=m.invoice_id JOIN branches b ON b.id=i.branch_id ORDER BY m.invoice_id DESC')])
 @app.post('/api/admin/cancellation-emails/retry')
 def cancellation_mail_retry():WAKE.set();return jsonify(ok=True)
