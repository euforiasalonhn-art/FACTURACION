"""Puerta de entrada de PC 1. Cada solicitud mantiene su propia sesión."""
import base64,hashlib,json,threading,time
from flask import Flask,request,jsonify
import backup_protocol as protocol
from central_transport import MAX_PACKET

def create_gateway(pos,connect):
 with connect() as c:c.execute('UPDATE terminal_requests SET last_status=499 WHERE last_status=0')
 gateway=Flask('FRYCentral');gateway.config['MAX_CONTENT_LENGTH']=MAX_PACKET;seen={};lock=threading.Lock()
 @gateway.post('/rpc')
 def rpc():
  try:tid=int(request.headers.get('X-FRY-Terminal',''))
  except ValueError:return jsonify(error='Terminal inválida'),403
  with connect() as c:row=c.execute('SELECT * FROM terminals WHERE id=? AND active=1',(tid,)).fetchone()
  if not row:return jsonify(error='Terminal no autorizada'),403
  key=row['secret'];body=request.get_data()
  if not protocol.authenticated(key,'POST','/rpc',request.headers,body):return jsonify(error='Conexión no autorizada o reloj incorrecto'),403
  nonce=request.headers['X-FRY-Nonce']
  with lock:
   now=time.time()
   for item,stamp in list(seen.items()):
    if now-stamp>180:del seen[item]
   if (tid,nonce) in seen:return jsonify(error='Solicitud ya recibida'),409
   seen[(tid,nonce)]=now
  def answer(response):return gateway.response_class(protocol.seal(key,json.dumps(dict(nonce=nonce,**response)).encode()),mimetype='application/octet-stream')
  def error(message,status=400):return answer(dict(status=status,headers=[['Content-Type','application/json']],body=base64.b64encode(json.dumps(dict(error=message)).encode()).decode()))
  stamp=None
  try:
   p=json.loads(protocol.unseal(key,body));method=p['method'];path=p['path'];query=p.get('query','')
   if method not in ['GET','POST','PATCH','DELETE'] or not isinstance(path,str) or not (path=='/' or path.startswith(('/api/','/static/'))) or '?' in path or '\\' in path or '..' in path or '://' in path or '#' in path:raise ValueError('Ruta no permitida')
   raw=base64.b64decode(p.get('body',''),validate=True)
   if len(raw)>80*1024*1024:raise ValueError('Solicitud demasiado grande')
   headers={k:v for k,v in p.get('headers',{}).items() if k.lower() in ['cookie','content-type','x-pos-token']}
   if method=='POST' and path in ['/api/invoices','/api/employee-meals','/api/special-orders']:
    d=json.loads(raw);request_id=str(d.get('request_id',''));fingerprint=hashlib.sha256(json.dumps(d,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if not 1<=len(request_id)<=200:raise ValueError('Identificador de cobro inválido')
    with connect() as c:
     c.execute('BEGIN IMMEDIATE');previous=c.execute('SELECT payload_hash,last_status FROM terminal_requests WHERE terminal_id=? AND request_id=?',(tid,request_id)).fetchone()
     if previous and previous['last_status']==410:return error('Ese cobro pendiente fue cancelado. Inicia uno nuevo.',409)
     if previous and previous[0]!=fingerprint:
      if previous['last_status'] not in [400,401,403,415]:return error('El cobro pendiente tiene otro contenido. Recupera su resultado antes de cambiarlo.',409)
      c.execute('UPDATE terminal_requests SET payload_hash=?,last_status=0 WHERE terminal_id=? AND request_id=?',(fingerprint,tid,request_id))
     c.execute('INSERT OR IGNORE INTO terminal_requests(terminal_id,request_id,payload_hash) VALUES(?,?,?)',(tid,request_id,fingerprint));c.execute('UPDATE terminal_requests SET last_status=0 WHERE terminal_id=? AND request_id=?',(tid,request_id));stamp=(tid,request_id)
   client=pos.test_client(use_cookies=False)
   response=client.open(path,query_string=query,method=method,data=raw,headers=headers,environ_overrides={'FRY_TERMINAL_ID':tid})
   if stamp:
    with connect() as c:c.execute('UPDATE terminal_requests SET last_status=? WHERE terminal_id=? AND request_id=?',(response.status_code,*stamp))
   output=[(k,v) for k,v in response.headers if k.lower() in ['content-type','set-cookie','content-disposition','cache-control','etag','x-fry-backup-pending']]
   status=response.status_code;raw_response=response.get_data();response.close()
   return answer(dict(status=status,headers=output,body=base64.b64encode(raw_response).decode()))
  except (ValueError,TypeError,KeyError) as e:return error(str(e))
 return gateway
