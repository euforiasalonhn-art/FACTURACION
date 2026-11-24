"""Protocolo firmado y guardado atómico del respaldo remoto."""
import base64,gzip,hashlib,hmac,io,json,os,secrets,sqlite3,time
from pathlib import Path
MAX_RAW=256*1024*1024
MAX_WIRE=64*1024*1024
MAX_TRANSPORT=128*1024*1024

def digest(data):return hashlib.sha256(data).hexdigest()
def signature(key,method,path,stamp,nonce,body,previous=''):
 return hmac.new(key.encode(),('\n'.join([method,path,stamp,nonce,digest(body),previous])).encode(),hashlib.sha256).hexdigest()
def headers(key,method,path,body=b'',previous=''):
 stamp=str(int(time.time()));nonce=secrets.token_hex(16)
 return {'X-FRY-Time':stamp,'X-FRY-Nonce':nonce,'X-FRY-Signature':signature(key,method,path,stamp,nonce,body,previous),'Content-Type':'application/octet-stream'}
def authenticated(key,method,path,h,body):
 try:
  stamp=h.get('X-FRY-Time','');nonce=h.get('X-FRY-Nonce','')
  return abs(time.time()-int(stamp))<=120 and len(nonce)==32 and hmac.compare_digest(h.get('X-FRY-Signature',''),signature(key,method,path,stamp,nonce,body,h.get('X-FRY-Previous','')))
 except (ValueError,TypeError):return False

def atomic(path,data):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 tmp=path.with_name(path.name+'.'+secrets.token_hex(8)+'.tmp')
 try:
  with tmp.open('wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
  os.replace(tmp,path)
 finally:
  if tmp.exists():tmp.unlink()

def validate(blob):
 if len(blob)>MAX_WIRE:raise ValueError('Respaldo comprimido demasiado grande')
 with gzip.GzipFile(fileobj=io.BytesIO(blob)) as f:raw=f.read(MAX_RAW+1)
 if len(raw)>MAX_RAW:raise ValueError('Respaldo demasiado grande')
 doc=json.loads(raw)
 if doc.get('format')!='FRYChickenPOS-FULL' or doc.get('version')!=1:raise ValueError('Formato de respaldo inválido')
 database=base64.b64decode(doc['database_base64'],validate=True)
 c=sqlite3.connect(':memory:')
 try:
  c.deserialize(database)
  if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Base de datos dañada')
  invoices=[dict(zip(['id','number','fiscal_number','created_at'],r)) for r in c.execute('SELECT id,number,fiscal_number,created_at FROM invoices ORDER BY id')]
  instance=c.execute("SELECT value FROM settings WHERE key='network_instance'").fetchone()
  if not instance:raise ValueError('Falta identificador de instalación')
  instance=json.loads(instance[0])
  if not isinstance(instance,str) or not instance.isalnum() or len(instance)!=32:raise ValueError('Instalación inválida')
 finally:c.close()
 # Comprueba que las imágenes restaurables estén íntegramente codificadas y sin rutas externas.
 for name,value in doc.get('assets',{}).items():
  p=Path(name)
  if p.is_absolute() or p.drive or '..' in p.parts:raise ValueError('Ruta de imagen inválida')
  base64.b64decode(value,validate=True)
 return doc,instance,invoices


def seal(key,data):
 from cryptography.fernet import Fernet
 derived=base64.urlsafe_b64encode(hashlib.sha256(('FRY-transport-v1:'+key).encode()).digest())
 return Fernet(derived).encrypt(data)

def unseal(key,data):
 from cryptography.fernet import Fernet,InvalidToken
 derived=base64.urlsafe_b64encode(hashlib.sha256(('FRY-transport-v1:'+key).encode()).digest())
 try:return Fernet(derived).decrypt(data)
 except InvalidToken as e:raise ValueError('Respuesta o archivo sin cifrado válido del receptor') from e
