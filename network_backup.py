"""Respaldo confirmado antes de confirmar una factura; excepción TOTP temporal."""
import base64,gzip,hashlib,hmac,ipaddress,json,os,secrets,threading,time,urllib.request,urllib.error
from pathlib import Path
from urllib.parse import urlsplit
from flask import request,session,jsonify,has_request_context
import accounting,cancellation,commerce,backup_protocol as protocol
import backup_discovery
DISCOVERED={}
LOCK=threading.RLock()
STRICT_PATHS={'/api/invoices','/api/employee-meals','/api/special-orders'}
class BackupUnavailable(ValueError):pass

def config(c):
 r=c.execute("SELECT value FROM settings WHERE key='network_backup'").fetchone()
 return dict(enabled=False,url='',fallback_url='',key='')|(json.loads(r[0]) if r else {})
def value(c,key,default=None):
 r=c.execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone();return json.loads(r[0]) if r else default
def save(c,key,obj):c.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',(key,json.dumps(obj)))
def exempt():return has_request_context() and session.get('backup_override_until',0)>time.time()

def safe_url(url):
 p=urlsplit(str(url).strip())
 if p.scheme not in ['http','https'] or not p.hostname or p.username or p.password or p.query or p.fragment or p.path not in ['', '/']:raise ValueError('Usa la dirección del receptor, por ejemplo http://100.80.10.20:5058')
 if p.scheme=='http':
  try:ip=ipaddress.ip_address(p.hostname)
  except ValueError:raise ValueError('Para HTTP usa una IP privada de red local o de Tailscale')
  if not any(ip in ipaddress.ip_network(n) for n in ['100.64.0.0/10','10.0.0.0/8','172.16.0.0/12','192.168.0.0/16','127.0.0.0/8']):raise ValueError('HTTP solo se permite en red local privada o Tailscale. Para otra red usa HTTPS')
 return str(url).strip().rstrip('/')

def remote(cfg,method,path,body=b'',previous=''):
 wire=protocol.seal(cfg['key'],body) if method=='POST' else b''
 class NoRedirect(urllib.request.HTTPRedirectHandler):
  def redirect_request(self,*a,**kw):return None
 opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
 last=None
 endpoints=list(dict.fromkeys(v for v in [cfg['url'],cfg.get('fallback_url',''),DISCOVERED.get(cfg['key'],'')] if v))
 attempted=set()
 while endpoints:
  url=endpoints.pop(0)
  if url in attempted:continue
  attempted.add(url)
  h=protocol.headers(cfg['key'],method,path,wire,previous);h['X-FRY-Previous']=previous
  req=urllib.request.Request(url+path,data=wire if method=='POST' else None,headers=h,method=method)
  def decode(data,status):
   message=json.loads(protocol.unseal(cfg['key'],data))
   if message.get('nonce')!=h['X-FRY-Nonce'] or message.get('path')!=path or message.get('status')!=status:raise ValueError('Confirmación ajena a esta solicitud')
   return json.loads(base64.b64decode(message['data'],validate=True))
  try:
   with opener.open(req,timeout=5) as response:
    data=response.read(protocol.MAX_TRANSPORT+1)
    if len(data)>protocol.MAX_TRANSPORT:raise ValueError('Respuesta demasiado grande')
    return decode(data,response.status)
  except urllib.error.HTTPError as e:
   try:last=BackupUnavailable('Respaldo no confirmado: '+decode(e.read(65536),e.code).get('error','Respuesta rechazada'))
   except Exception:last=BackupUnavailable('El receptor no confirmó la clave y el cifrado de esta conexión')
  except (OSError,ValueError) as e:last=BackupUnavailable('La PC de respaldo no responde. Enciéndela, revisa la red local/Tailscale o solicita autorización al administrador.')
  if not endpoints and cfg.get('discovery',True):
   choices=backup_discovery.discover(cfg['key'])
   if len(choices)==1:
    candidate=choices[0]['url'];DISCOVERED[cfg['key']]=candidate
    if candidate not in attempted:endpoints.append(candidate)
 if last:raise last
 raise BackupUnavailable('Configura la dirección de la PC receptora')

def document(c,data):
 tables={}
 for row in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall():
  name=row[0];cur=c.execute('SELECT * FROM "'+name.replace('"','""')+'"');cols=[d[0] for d in cur.description];tables[name]=[dict(zip(cols,r)) for r in cur.fetchall()]
 assets={}
 for folder in Path(data).iterdir():
  if folder.is_dir():
   for f in folder.rglob('*'):
    if f.is_file() and f.suffix.lower() in ['.jpg','.jpeg','.png','.webp']:assets[f.relative_to(data).as_posix()]=base64.b64encode(f.read_bytes()).decode()
 doc=dict(format='FRYChickenPOS-FULL',version=1,created_at=accounting.now(),tables=tables,database_base64=base64.b64encode(c.serialize()).decode(),assets=assets)
 return json.dumps(doc,ensure_ascii=False,default=lambda v:{'base64':base64.b64encode(v).decode()} if isinstance(v,bytes) else str(v)).encode()

def state(data):
 p=Path(data)/'network-backup-status.json'
 try:return json.loads(p.read_text('utf-8'))
 except (OSError,ValueError):return dict(online=False,error='Sin comprobar',last_invoice=None)

def synchronize(c,data):
 cfg=config(c)
 if not cfg['enabled']:return dict(enabled=False,online=False)
 instance=value(c,'network_instance')
 if not instance:raise BackupUnavailable('Reinicia la versión 40 para preparar el identificador del respaldo')
 with LOCK:
  previous=state(data);upload_attempted=False
  try:
   manifest=remote(cfg,'GET','/status/'+instance)
   raw=document(c,data);doc=json.loads(raw);doc.pop('created_at',None);content=protocol.digest(json.dumps(doc,sort_keys=True,ensure_ascii=False).encode())
   if previous.get('content')==content and previous.get('sha256')==manifest.get('sha256'):
    result=previous|dict(enabled=True,online=True,error='')
   else:
    blob=gzip.compress(raw,compresslevel=5,mtime=0)
    upload_attempted=True
    result=remote(cfg,'POST','/snapshot/'+instance,blob,manifest['sha256'])
    if result.get('sha256')!=protocol.digest(blob):raise BackupUnavailable('La PC remota no confirmó el mismo archivo enviado')
    result.update(enabled=True,online=True,error='',content=content)
   result['requires_recovery']=False
   protocol.atomic(Path(data)/'network-backup-status.json',json.dumps(result,ensure_ascii=False).encode());return result
  except Exception as e:
   result=previous|dict(enabled=True,online=False,error=str(e),requires_recovery=previous.get('requires_recovery',False) or upload_attempted);protocol.atomic(Path(data)/'network-backup-status.json',json.dumps(result,ensure_ascii=False).encode())
   if isinstance(e,BackupUnavailable):raise
   raise BackupUnavailable('No se pudo verificar el respaldo: '+str(e)) from e

def before_commit(c,data):
 if not has_request_context() or request.method!='POST' or request.path not in STRICT_PATHS or not config(c)['enabled']:return
 if exempt():
  accounting.audit(c,'VENTA_EN_EMERGENCIA',request.path,dict(until=session['backup_override_until']))
  return
 # serialize() incluye las escrituras de esta transacción aún sin confirmar.
 # No se informa éxito ni se imprime antes de la confirmación remota y del commit local.
 synchronize(c,data)

def register(app,connect,data):
 @app.errorhandler(BackupUnavailable)
 def unavailable(e):return jsonify(error=str(e),backup_blocked=True),503
 @app.before_request
 def preflight():
  if request.method=='POST' and request.path in STRICT_PATHS and session.get('role') in ['admin','local']:
   with connect() as c:
    if config(c)['enabled'] and not exempt():synchronize(c,data)
 @app.after_request
 def automatic(response):
  if request.method in ['POST','PATCH','DELETE'] and response.status_code<300 and request.path.startswith('/api/') and not request.path.startswith('/api/network-backup') and not request.path.startswith('/api/admin/network-backup'):
   try:
    with connect() as c:
     if config(c)['enabled']:synchronize(c,data)
   except Exception:
    response.headers['X-FRY-Backup-Pending']='1'
  return response
 @app.get('/api/network-backup/status')
 def status():
  with connect() as c:cfg=config(c)
  s=state(data);return jsonify(s|dict(enabled=cfg['enabled'],override_until=session.get('backup_override_until',0)))
 @app.post('/api/network-backup/check')
 def check():
  if session.get('role') not in ['admin','local']:return jsonify(error='Acceso no permitido'),403
  with connect() as c:
   try:result=synchronize(c,data)
   except BackupUnavailable:result=state(data)
   return jsonify(result|dict(override_until=session.get('backup_override_until',0)))
 @app.post('/api/admin/network-backup/discover')
 def find_backup_receiver():
  with connect() as c:key=str((request.json or {}).get('key','')).strip() or config(c)['key']
  if len(key)<32:raise ValueError('Copia primero la clave del receptor instalado')
  return jsonify(backup_discovery.discover(key,timeout=1.5))
 @app.route('/api/admin/network-backup',methods=['GET','POST'])
 def network_settings():
  with connect() as c:
   cfg=config(c)
   if request.method=='POST':
    d=request.json or {};enabled=d.get('enabled') is True;url=safe_url(d.get('url',cfg['url'])) if enabled or d.get('url') else '';key=str(d.get('key','')).strip() or cfg['key']
    if enabled and len(key)<32:raise ValueError('Copia la clave de conexión del receptor (mínimo 32 caracteres)')
    fallback=safe_url(d.get('fallback_url',cfg.get('fallback_url',''))) if d.get('fallback_url',cfg.get('fallback_url','')) else '';cfg=dict(enabled=enabled,url=url,fallback_url=fallback,key=key,discovery=True);save(c,'network_backup',cfg);accounting.audit(c,'CONFIGURACION_RESPALDO_RED','PC',dict(enabled=enabled,url=url))
   result={k:v for k,v in cfg.items() if k!='key'};result['has_key']=bool(cfg['key']);result['instance']=value(c,'network_instance')
  if request.method=='POST' and cfg['enabled']:
   try:
    with connect() as c:result['status']=synchronize(c,data)
   except BackupUnavailable:result['status']=state(data)
  return jsonify(result)
 @app.post('/api/network-backup/emergency')
 def emergency():
  if session.get('role') not in ['admin','local']:return jsonify(error='Acceso no permitido'),403
  if state(data).get('requires_recovery'):return jsonify(error='La respuesta de una copia quedó pendiente. Reconecta y comprueba el respaldo; si la copia remota está adelantada, restaura esa copia antes de facturar. Se bloquea la excepción para evitar reutilizar números.'),409
  d=request.json or {};reason=str(d.get('reason','')).strip()
  if not 5<=len(reason)<=300:raise ValueError('Indica el motivo de emergencia (5 a 300 caracteres)')
  now=time.time();step=int(now//300);bid=session.get('branch_id',0)
  with connect() as c:
   c.execute('BEGIN IMMEDIATE')
   remote_last=(state(data).get('last_invoice') or {}).get('id',0);local_last=c.execute('SELECT COALESCE(MAX(id),0) FROM invoices').fetchone()[0]
   if remote_last>local_last:return jsonify(error='La copia remota confirma una factura que falta en la base local. Recupera esa copia antes de autorizar una emergencia para evitar reutilizar números.'),409
   cfg=value(c,'cancellation_totp')
   if not cfg:return jsonify(error='El administrador debe activar el autenticador de anulación'),409
   attempts=value(c,'backup_attempts:'+str(bid),dict(step=step,count=0))
   if attempts['step']!=step:attempts=dict(step=step,count=0)
   if attempts['count']>=5:return jsonify(error='Demasiados intentos. Espera el próximo código del autenticador'),429
   valid=hmac.compare_digest(str(d.get('code','')),cancellation.totp(commerce.protect(cfg['secret'],True),now))
   if not valid:
    attempts['count']+=1;save(c,'backup_attempts:'+str(bid),attempts);accounting.audit(c,'RESPALDO_CODIGO_RECHAZADO',bid,{})
   elif cfg['used_step']>=step:return jsonify(error='Código ya utilizado. Espera el siguiente código del autenticador'),409
   else:
    cfg['used_step']=step;save(c,'cancellation_totp',cfg);session['backup_override_until']=now+1800
    accounting.audit(c,'RESPALDO_EMERGENCIA_AUTORIZADA',bid,dict(reason=reason,until=now+1800))
    return jsonify(ok=True,override_until=now+1800)
  return jsonify(error='Código incorrecto o vencido'),403

