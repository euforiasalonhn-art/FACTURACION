"""Terminal: servidor loopback que pasa las operaciones cifradas a PC 1."""
import base64,json,threading
from pathlib import Path
from flask import Flask,request,Response,jsonify
import backup_protocol as protocol
from central_transport import call,CentralUnavailable

def create_proxy(cfg,folder):
 app=Flask('FRYTerminal',static_folder=None);app.config['MAX_CONTENT_LENGTH']=80*1024*1024;folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);pending=folder/'cobro-pendiente.json';lock=threading.RLock()
 def load_pending():
  try:return json.loads(pending.read_text('utf-8'))
  except FileNotFoundError:return None
 def discard():
  if pending.exists():pending.unlink()
 def who(headers):
  r=perform(dict(method='GET',path='/api/auth/state',query='',headers=headers,body=''));d=r.get_json(silent=True) or {}
  return dict(role=d.get('role'),cashier_id=(d.get('cashier') or {}).get('id'))
 def perform(packet):
  result=call(cfg,packet);response=Response(base64.b64decode(result['body']),status=int(result['status']),headers=result['headers'])
  return response
 @app.route('/',defaults={'path':''},methods=['GET','POST','PATCH','DELETE'])
 @app.route('/<path:path>',methods=['GET','POST','PATCH','DELETE'])
 def forward(path):
  headers={k:v for k,v in request.headers.items() if k.lower() in ['cookie','content-type','x-pos-token']};route='/'+path
  if route=='/api/auth/logout' and request.method=='POST' and load_pending():return jsonify(error='Recupera o cancela el cobro pendiente antes de cerrar sesión.'),409
  if route=='/api/terminal-link':return jsonify(mode='client',name=cfg.get('name','Terminal'),server=cfg['server_url'],pending=bool(load_pending()))
  if route=='/api/local-pending' and request.method=='GET':
   p=load_pending();return jsonify(pending=bool(p),request_id=p['request_id'] if p else None)
  if route=='/api/local-pending/ack' and request.method=='POST':
   if not request.headers.get('X-POS-Token'):return jsonify(error='Confirmación no autorizada'),403
   with lock:
    old=load_pending()
    if not old:return jsonify(ok=True)
    if not old.get('result') or (request.get_json(silent=True) or {}).get('invoice_id')!=old['result'].get('id'):return jsonify(error='Confirma primero la factura recuperada'),409
    discard();return jsonify(ok=True)
  if route=='/api/local-pending/cancel' and request.method=='POST':
   with lock:
    old=load_pending()
    if not old:return jsonify(ok=True)
    if old.get('result'):return jsonify(error='Este cobro tiene confirmación de factura. Recupera su resultado; no se cancela como un pedido sin factura.'),409
    try:actor=who(headers)
    except CentralUnavailable:return jsonify(error='PC 1 no responde. Se conserva el pendiente.'),503
    if actor!=old.get('actor') and actor.get('role')!='admin':return jsonify(error='Solo el empleado original o el administrador puede cancelar este pendiente'),403
    check=dict(method='GET',path='/api/terminal/recover',query='request_id='+old['request_id'],headers=headers,body='')
    try:r=perform(check)
    except CentralUnavailable:return jsonify(error='Conecta con PC 1 antes de cancelar el pendiente'),503
    d=r.get_json(silent=True) or {}
    if r.status_code!=200:return r
    if d.get('found'):return jsonify(error='El cobro ya generó una factura. Consulta el resultado para recuperarla.'),409
    if d.get('processing'):return jsonify(error='PC 1 todavía está procesando el cobro. No se cancela.'),409
    packet=dict(method='POST',path='/api/terminal/cancel-pending',query='',headers=headers,body=base64.b64encode(json.dumps(dict(request_id=old['request_id'])).encode()).decode())
    try:cancelled=perform(packet)
    except CentralUnavailable:return jsonify(error='No se confirmó la cancelación. Se conserva el pendiente.'),503
    if cancelled.status_code!=200:return cancelled
    discard();return jsonify(ok=True)
  if route=='/api/local-pending/retry' and request.method=='POST':
   with lock:
    old=load_pending()
    if not old:return jsonify(error='No hay cobro pendiente'),404
    if old.get('result'):
     try:checked=perform(dict(method='GET',path='/api/terminal/recover',query='request_id='+old['request_id'],headers=headers,body=''))
     except CentralUnavailable:return jsonify(error='PC 1 no responde; conserva la confirmación local'),503
     result=checked.get_json(silent=True) or {}
     if checked.status_code!=200:return checked
     if not result.get('found'):return jsonify(error='La factura confirmada falta en PC 1. Restaura una copia actual antes de continuar.'),409
     return jsonify(id=result['invoice']['id'])
    try:actor=who(headers)
    except CentralUnavailable:return jsonify(error='PC 1 no responde'),503
    if actor!=old.get('actor'):return jsonify(error='Inicia sesión con el mismo empleado del cobro pendiente para reintentarlo.'),403
    saved=dict(old['packet']);saved['headers']=headers
    try:r=perform(saved)
    except CentralUnavailable:return jsonify(error='PC 1 no confirmó el pendiente. Se conserva el mismo identificador.'),503
    if r.status_code<300:
     old['result']=r.get_json();protocol.atomic(pending,json.dumps(old,ensure_ascii=False).encode())
    return r
  if route=='/api/local-pending/result' and request.method=='GET':
   with lock:
    old=load_pending()
    if not old:return jsonify(found=False,pending=False)
    try:r=perform(dict(method='GET',path='/api/terminal/recover',query='request_id='+old['request_id'],headers=headers,body=''))
    except CentralUnavailable:return jsonify(error='PC 1 no responde. El cobro sigue pendiente.'),503
    if r.status_code==200:
     result=r.get_json(silent=True) or {}
     if result.get('found'):
      old['result']=result['invoice'];protocol.atomic(pending,json.dumps(old,ensure_ascii=False).encode())
     elif old.get('result'):return jsonify(error='La terminal conserva una confirmación de factura que falta en PC 1. Recupera una copia actual del servidor antes de continuar.'),409
    return r
  packet=dict(method=request.method,path=route,query=request.query_string.decode(),headers=headers,body=base64.b64encode(request.get_data()).decode())
  if route=='/api/invoices' and request.method=='POST':
   with lock:
    d=request.get_json(silent=True) or {};key=str(d.get('request_id',''));old=load_pending()
    if old and old['request_id']!=key:return jsonify(error='Existe un cobro sin confirmar. Consulta el pendiente antes de iniciar otro.',central_pending=True),409
    if not old:
     try:actor=who(headers)
     except CentralUnavailable:return jsonify(error='PC 1 no responde. No se pudo iniciar el cobro.'),503
     if actor.get('role') not in ['admin','local']:return jsonify(error='Inicia sesión para cobrar'),401
     protocol.atomic(pending,json.dumps(dict(request_id=key,packet=packet,actor=actor),ensure_ascii=False).encode())
    # Mantener exactamente el contenido original en cualquier reintento.
    elif old:
     try:actor=who(headers)
     except CentralUnavailable:return jsonify(error='PC 1 no responde. Conserva el cobro pendiente.'),503
     if actor!=old.get('actor'):return jsonify(error='El cobro pendiente pertenece a otro empleado. Consulta su resultado antes de cobrar de nuevo.',central_pending=True),409
     packet=old['packet']|dict(headers=headers)
    try:r=perform(packet)
    except CentralUnavailable as e:return jsonify(error=str(e),central_pending=True),503
    if r.status_code<300:
     saved=load_pending();saved['result']=r.get_json();protocol.atomic(pending,json.dumps(saved,ensure_ascii=False).encode())
    elif not old and r.status_code==400:discard()
    return r
  try:return perform(packet)
  except CentralUnavailable as e:
   if route=='/':return Response('<!doctype html><meta charset="utf-8"><title>Conexión con PC 1</title><h1>PC 1 NO RESPONDE</h1><p>Enciende el servidor y revisa la conexión. Esta terminal no genera facturas por su cuenta.</p><button onclick="location.reload()">Reintentar conexión</button><p>F8 permite revisar la configuración de esta computadora.</p>',status=503,mimetype='text/html')
   return jsonify(error=str(e)),503
 return app
