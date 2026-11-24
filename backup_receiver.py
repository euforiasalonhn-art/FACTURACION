"""Receptor independiente: no inicia el POS ni abre su base de datos."""
import argparse,base64,gzip,json,os,secrets,threading,logging
from pathlib import Path
from datetime import datetime,timezone
from flask import Flask,request,jsonify,Response
from werkzeug.serving import run_simple
import backup_protocol as protocol

def create_receiver(folder,key):
 folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);app=Flask('FRYBackup');app.config['MAX_CONTENT_LENGTH']=protocol.MAX_TRANSPORT;lock=threading.RLock()
 @app.before_request
 def guard():
  body=request.get_data()
  if not protocol.authenticated(key,request.method,request.path,request.headers,body):return jsonify(error='Autenticación de respaldo rechazada; revisa clave y hora de Windows'),403
 @app.after_request
 def encrypted_response(response):
  envelope=dict(path=request.path,nonce=request.headers.get('X-FRY-Nonce',''),status=response.status_code,data=base64.b64encode(response.get_data()).decode())
  response.set_data(protocol.seal(key,json.dumps(envelope).encode()));response.content_type='application/octet-stream';response.headers['Cache-Control']='no-store';return response
 @app.errorhandler(ValueError)
 def invalid(e):return jsonify(error=str(e)),400
 def location(instance):
  if not instance.isalnum() or len(instance)!=32:raise ValueError('Instalación inválida')
  return folder/instance
 @app.get('/status/<instance>')
 def status(instance):
  with lock:
   p=location(instance)/'manifest.json'
   return jsonify(json.loads(p.read_text('utf-8')) if p.exists() else dict(sequence=0,sha256='',last_invoice=None))
 @app.post('/snapshot/<instance>')
 def upload(instance):
  blob=protocol.unseal(key,request.get_data());doc,identity,invoices=protocol.validate(blob)
  if identity!=instance:raise ValueError('El respaldo pertenece a otra instalación')
  with lock:
   dest=location(instance);dest.mkdir(exist_ok=True);mp=dest/'manifest.json';old=json.loads(mp.read_text('utf-8')) if mp.exists() else dict(sequence=0,sha256='')
   sha=protocol.digest(blob)
   if sha==old['sha256']:return jsonify(old)
   if request.headers.get('X-FRY-Previous','')!=old['sha256']:return jsonify(error='Otra actualización llegó primero. Reintenta.'),409
   latest=dest/'latest.json.gz'
   if old.get('file'):
    _,_,previous=protocol.validate((dest/old['file']).read_bytes())
    known={x['id']:x for x in invoices}
    if any(x['id'] not in known or known[x['id']]!=x for x in previous):return jsonify(error='El respaldo recibido elimina o cambia la numeración histórica. Se conserva la copia remota.'),409
   filename=f"snapshot-{old['sequence']+1:012d}-{sha}.json.gz"
   # El manifiesto apunta a un archivo inmutable ya verificado: una interrupción no publica una copia incompleta.
   protocol.atomic(dest/filename,blob)
   if protocol.digest((dest/filename).read_bytes())!=sha:raise ValueError('No se pudo verificar el archivo guardado')
   now=datetime.now(timezone.utc).isoformat(timespec='seconds')
   manifest=dict(sequence=old['sequence']+1,sha256=sha,file=filename,confirmed_at=now,last_invoice=invoices[-1] if invoices else None,invoice_count=len(invoices),instance=instance)
   protocol.atomic(mp,json.dumps(manifest,ensure_ascii=False).encode())
   protocol.atomic(latest,blob)
   protocol.atomic(dest/('diario-'+now[:10]+'.json.gz'),blob)
   # Conservar los dos puntos recientes y las copias diarias; cada uno contiene todas las ventas históricas.
   snapshots=sorted(dest.glob('snapshot-*.json.gz'))
   for p in snapshots[:-2]:p.unlink()
   return jsonify(manifest)
 @app.get('/download/<instance>')
 def download(instance):
  with lock:
   dest=location(instance);p=dest/'manifest.json'
   if not p.exists():return jsonify(error='No existe respaldo confirmado'),404
   m=json.loads(p.read_text('utf-8'));blob=(dest/m['file']).read_bytes()
   if protocol.digest(blob)!=m['sha256']:raise ValueError('El respaldo guardado no coincide con su verificación')
   return Response(blob,mimetype='application/gzip',headers={'X-FRY-SHA256':m['sha256']})
 return app

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--data',default=str(Path(os.environ.get('LOCALAPPDATA',Path.home()))/'FRYChickenBackup'));parser.add_argument('--setup',action='store_true');parser.add_argument('--port',type=int,default=5058);args=parser.parse_args()
 data=Path(args.data);data.mkdir(parents=True,exist_ok=True);config=data/'receptor.json'
 if not config.exists():
  if not args.setup:raise SystemExit('Primero ejecuta CONFIGURAR_RESPALDO.bat')
  protocol.atomic(config,json.dumps(dict(key=secrets.token_urlsafe(32)),indent=2).encode())
 key=json.loads(config.read_text('utf-8'))['key']
 if args.setup:
  print('CARPETA DE RESPALDOS: '+str(data));print('CLAVE DE CONEXIÓN (solo para configurar caja): '+key);return
 logging.basicConfig(filename=str(data/'receptor.log'),level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
 import backup_discovery
 threading.Thread(target=backup_discovery.serve,args=(key,None,args.port),daemon=True).start()
 run_simple('0.0.0.0',args.port,create_receiver(data,key),threaded=True,use_reloader=False)
if __name__=='__main__':main()
