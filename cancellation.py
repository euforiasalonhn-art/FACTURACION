import hashlib,hmac,secrets,time,base64,struct,io
import qrcode
from urllib.parse import urlencode,quote
from werkzeug.security import check_password_hash

def totp(secret,timestamp=None,period=300,digits=6):
 key=base64.b32decode(secret.upper()+"="*((-len(secret))%8))
 counter=int((time.time() if timestamp is None else timestamp)//period)
 digest=hmac.new(key,struct.pack(">Q",counter),hashlib.sha1).digest();offset=digest[-1]&15
 return str((struct.unpack(">I",digest[offset:offset+4])[0]&0x7fffffff)%10**digits).zfill(digits)
from flask import request,session,jsonify
import accounting
from commerce import protect

def register(app,connect,setting,save_setting,cancel):
 def password(c):
  if not check_password_hash(setting(c,'auth')['password'],str((request.json or {}).get('current_password',''))):raise ValueError('Contraseña del administrador incorrecta')
 @app.post('/api/admin/cancellation-totp/setup')
 def totp_setup():
  with connect() as c:
   c.execute('BEGIN IMMEDIATE');password(c);secret=base64.b32encode(secrets.token_bytes(20)).decode().rstrip('=')
   save_setting(c,'cancellation_totp_pending',dict(secret=protect(secret),expires=time.time()+600))
   uri='otpauth://totp/'+quote('FRY Chicken:Anulacion de facturas',safe='')+'?'+urlencode(dict(secret=secret,issuer='FRY Chicken',algorithm='SHA1',digits=6,period=300))
   accounting.audit(c,'TOTP_PREPARADO','anulaciones',dict(period=300))
  qr=qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,box_size=7,border=4);qr.add_data(uri);qr.make(fit=True)
  image=qr.make_image(fill_color='black',back_color='white');buffer=io.BytesIO();image.save(buffer,format='PNG')
  response=jsonify(secret=secret,uri=uri,qr='data:image/png;base64,'+base64.b64encode(buffer.getvalue()).decode(),period=300,digits=6,algorithm='SHA1');response.headers['Cache-Control']='no-store';return response
 @app.post('/api/admin/cancellation-totp/activate')
 def totp_activate():
  with connect() as c:
   c.execute('BEGIN IMMEDIATE');password(c);pending=setting(c,'cancellation_totp_pending')
   if not pending or pending['expires']<time.time():raise ValueError('La configuración venció. Genera una nueva clave')
   if not hmac.compare_digest(str((request.json or {}).get('code','')),totp(protect(pending['secret'],True))):raise ValueError('Código incorrecto. Configura TOTP, SHA1, 6 dígitos e intervalo 300 segundos')
   save_setting(c,'cancellation_totp',dict(secret=pending['secret'],period=300,used_step=-1))
   c.execute("DELETE FROM settings WHERE key IN ('cancellation_totp_pending','cancellation_secret')")
   accounting.audit(c,'TOTP_ACTIVADO','anulaciones',dict(period=300))
  return jsonify(ok=True)
 @app.get('/api/admin/cancellation-code')
 def cancellation_code():
  with connect() as c:config=setting(c,'cancellation_totp')
  if not config:return jsonify(error='Configura y activa TOTP en el perfil del administrador'),409
  now=time.time();return jsonify(code=totp(protect(config['secret'],True),now),remaining=300-now%300,used=config['used_step']>=int(now//300))
 def branch():
  if session.get('role') not in ['admin','local']:raise ValueError('Acceso no permitido')
  return session['branch_id'] if session['role']=='local' else int((request.json or {}).get('branch_id',0))
 @app.post('/api/cancellation/find')
 def cancellation_find():
  bid=branch();number=int((request.json or {}).get('number',0))
  with connect() as c:
   r=c.execute('SELECT id,number,customer_name,total,status,created_at FROM invoices WHERE branch_id=? AND number=?',(bid,number)).fetchone()
   if not r:return jsonify(error='No se encontró esa orden en esta sucursal'),404
   return jsonify(dict(r))
 @app.post('/api/cancellation/confirm')
 def cancellation_confirm():
  bid=branch();d=request.json or {};now=time.time()
  with connect() as c:
   c.execute('BEGIN IMMEDIATE');key='cancellation_attempts:'+str(bid);attempt=setting(c,key,{'step':int(now//300),'count':0})
   if attempt['step']!=int(now//300):attempt={'step':int(now//300),'count':0}
   if attempt['count']>=5:return jsonify(error='Demasiados códigos incorrectos. Espera al próximo código de 5 minutos'),429
   config=setting(c,'cancellation_totp')
   if not config:return jsonify(error='El administrador debe configurar y activar TOTP'),409
   valid=hmac.compare_digest(str(d.get('code','')),totp(protect(config['secret'],True),now))
   if valid and config['used_step']>=int(now//300):return jsonify(error='Código ya utilizado. Espera el próximo código de 5 minutos'),409
   if not valid:
    attempt['count']+=1;save_setting(c,key,attempt);accounting.audit(c,'CODIGO_ANULACION_RECHAZADO',bid,dict(intentos=attempt['count']))
   else:
    r=c.execute('SELECT id FROM invoices WHERE branch_id=? AND number=? AND id=?',(bid,int(d.get('number',0)),int(d.get('invoice_id',0)))).fetchone()
    if not r:return jsonify(error='La orden no coincide con la factura consultada'),404
    result=cancel(c,r['id'],str(d.get('reason','')).strip())
    if isinstance(result,tuple):return result
    config['used_step']=int(now//300);save_setting(c,'cancellation_totp',config)
    return result
  if not valid:return jsonify(error='Código incorrecto o vencido. Solicita el código actual al administrador'),403

