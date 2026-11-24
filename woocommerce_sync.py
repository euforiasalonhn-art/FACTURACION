"""Catálogo local de WooCommerce. Descarga completa antes del cambio atómico."""
import base64
import hashlib
import html
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation,ROUND_HALF_UP
from flask import jsonify,request
import accounting
import commerce

LOCK=threading.Lock()
STARTED=False
PROGRESS_LOCK=threading.Lock()
PROGRESS=dict(running=False,phase='PENDIENTE',processed=0,total=0,images=0,finished_at='',error='')

def progress(**values):
 with PROGRESS_LOCK:PROGRESS.update(values)

def state():
 with PROGRESS_LOCK:return dict(PROGRESS)

def launch(connect,prepare_photo):
 with PROGRESS_LOCK:
  if PROGRESS['running']:return dict(started=False,**PROGRESS)
  PROGRESS.update(running=True,phase='CONECTANDO CON WOOCOMMERCE',processed=0,total=0,images=0,error='',image_errors=[],finished_at='')
 def run():
  try:
   result=sync(connect,prepare_photo)
   if result.get('busy'):progress(phase='YA HAY UNA DESCARGA EN CURSO')
   else:progress(phase='DESCARGA COMPLETA',count=result['count'],skipped=result['skipped'])
  except Exception as error:
   message=str(error) if isinstance(error,ValueError) else 'No se pudo completar la descarga. Vuelve a intentarlo.'
   progress(phase='DESCARGA INTERRUMPIDA',error=message)
  finally:progress(running=False,finished_at=datetime.now(timezone.utc).isoformat())
 threading.Thread(target=run,daemon=True,name='WooCommerce-descarga').start()
 return dict(started=True,**state())
TAXES={'15','18'}

class RemoteError(ValueError):
 def __init__(self,status,message):super().__init__(message);self.status=status

def base_url(value):
 return re.sub(r'/wp-json/wc/v[123]/?$', '',value.rstrip('/'))

class ImageRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):
  if urllib.parse.urlsplit(newurl).scheme!='https':raise ValueError('La imagen redirige a una dirección sin HTTPS')
  return super().redirect_request(req,fp,code,msg,headers,newurl)

def read(c):
 row=c.execute("SELECT value FROM settings WHERE key='woocommerce'").fetchone()
 return json.loads(row[0]) if row else dict(url='',enabled=False,categories=[],tax_map={'':'15'},revision=0)

def save(c,value):c.execute("INSERT OR REPLACE INTO settings VALUES('woocommerce',?)",(json.dumps(value,ensure_ascii=False),))

def init(c):
 if 'active' not in [r[1] for r in c.execute('PRAGMA table_info(products)')]:
  c.execute('ALTER TABLE products ADD COLUMN active INTEGER NOT NULL DEFAULT 0')
 c.execute('CREATE TABLE IF NOT EXISTS woo_products(site TEXT,remote_id INTEGER,product_id INTEGER UNIQUE REFERENCES products(id),image_url TEXT,metadata TEXT,PRIMARY KEY(site,remote_id))')

def public(cfg):
 return {k:v for k,v in cfg.items() if k not in ['key','secret']}|dict(has_credentials=bool(cfg.get('key') and cfg.get('secret')))

class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None

def download(url,authorization=None,limit=8*1024*1024):
 parsed=urllib.parse.urlsplit(url)
 if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password:raise ValueError('La conexión requiere direcciones HTTPS válidas')
 headers={'User-Agent':'FRYChicken-Catalog/91','Accept':'application/json' if authorization else 'image/*'}
 if authorization:headers['Authorization']=authorization
 try:
  with urllib.request.build_opener(NoRedirect if authorization else ImageRedirect).open(urllib.request.Request(url,headers=headers),timeout=25) as response:
   body=response.read(limit+1)
   if len(body)>limit:raise ValueError('La respuesta supera el tamaño permitido')
   return body
 except urllib.error.HTTPError as error:
  route=urllib.parse.urlsplit(url).path
  if error.code in [401,403]:message='Acceso rechazado HTTP '+str(error.code)+' en '+route+'. Revisa las claves API y el usuario asociado.'
  elif error.code==404:message='Recurso no encontrado HTTP 404 en '+route
  elif error.code in [301,302,307,308]:message='La tienda redirige la consulta '+route+'. Guarda la URL HTTPS final de la tienda.'
  else:message='Error HTTP '+str(error.code)+' al consultar '+route
  raise RemoteError(error.code,message) from None
 except (urllib.error.URLError,TimeoutError,OSError):raise ValueError('No se pudo conectar. Se conserva el último catálogo descargado.') from None

def api(cfg,path,params=None):
 try:credentials=commerce.protect(cfg['key'],True)+':'+commerce.protect(cfg['secret'],True)
 except Exception:raise ValueError('Guarda nuevamente las claves API en esta computadora') from None
 token='Basic '+base64.b64encode(credentials.encode()).decode()
 base=base_url(cfg['url']);url=base+'/wp-json/wc/v3/'+path+'?'+urllib.parse.urlencode(params or {})
 try:
  try:raw=download(url,token,16*1024*1024)
  except RemoteError as error:
   if error.status!=404:raise
   raw=download(base+'/?'+urllib.parse.urlencode(dict(params or {},rest_route='/wc/v3/'+path)),token,16*1024*1024)
  return json.loads(raw)
 except RemoteError as error:raise RemoteError(error.status,'Consulta '+path+': '+str(error)) from None
 except (json.JSONDecodeError,UnicodeDecodeError):raise ValueError('La tienda no devolvió un JSON válido en '+path) from None

def pages(cfg,path,params=None):
 result=[]
 for page in range(1,1001):
  batch=api(cfg,path,dict(params or {},page=page,per_page=100))
  if not isinstance(batch,list):raise ValueError('Respuesta inesperada de WooCommerce')
  result.extend(batch)
  progress(phase='LEYENDO '+('CATEGORÍAS' if path.endswith('categories') else 'PRODUCTOS')+' · PÁGINA '+str(page))
  if len(batch)<100:return result
 raise ValueError('El catálogo supera el límite de paginación')

def categories(cfg):
 if not cfg.get('key') or not cfg.get('secret'):raise ValueError('Guarda primero las claves API')
 return [dict(id=r['id'],name=html.unescape(r['name']),parent=r.get('parent',0)) for r in pages(cfg,'products/categories',{'hide_empty':'false'})]

def cents(value):
 try:
  number=Decimal(str(value))
  if not number.is_finite() or number<0 or number>100000000:raise ValueError()
  return int((number*100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
 except (InvalidOperation,ValueError):raise ValueError('Hay un producto sin precio válido en WooCommerce') from None

def currency(cfg):
 try:return api(cfg,'settings/general/woocommerce_currency').get('value')
 except RemoteError as error:
  if error.status!=404:raise
 options=api(cfg,'settings/general')
 if isinstance(options,list):
  for item in options:
   if item.get('id')=='woocommerce_currency':return item.get('value')
 raise ValueError('La tienda no devolvió su moneda en la configuración general de WooCommerce')

def image_bytes(cfg,url):
 candidates=[url]
 parsed=urllib.parse.urlsplit(url)
 # WordPress image proxies can expose /domain/wp-content/... URLs that fail.
 # Retry the same uploaded file on the configured store's origin.
 marker='/wp-content/uploads/'
 if marker in parsed.path:
  origin=urllib.parse.urlsplit(base_url(cfg['url']))
  original=urllib.parse.urlunsplit(('https',origin.netloc,parsed.path[parsed.path.index(marker):],'',''))
  if original not in candidates:candidates.append(original)
 last=None
 for candidate in candidates:
  try:return download(candidate)
  except ValueError as error:last=error
 raise last

def sync(connect,prepare_photo):
 if not LOCK.acquire(False):return dict(busy=True)
 try:
  with connect() as c:cfg=read(c);cached={r['remote_id']:dict(r) for r in c.execute('SELECT w.*,EXISTS(SELECT 1 FROM product_images i WHERE i.product_id=w.product_id) AS has_photo FROM woo_products w WHERE site=?',(cfg.get('url',''),))}
  if not cfg.get('enabled'):raise ValueError('Activa la sincronización en Ajustes → WooCommerce')
  if not cfg.get('categories'):raise ValueError('Selecciona las categorías que se mostrarán')
  if currency(cfg)!='HNL':raise ValueError('La moneda de WooCommerce debe ser HNL para importar precios en lempiras')
  category_rows=categories(cfg);names={r['id']:r['name'] for r in category_rows}
  selected=cfg['categories'];prepared=[];skipped=[]
  records=pages(cfg,'products',{'status':'publish'})
  progress(total=len(records),phase='REVISANDO PRODUCTOS')
  image_count=0;image_errors=[]
  for index,parent in enumerate(records,1):
   progress(processed=index,phase='REVISANDO '+html.unescape(parent['name']))
   assigned=[i for i in selected if i in [x['id'] for x in parent.get('categories',[])]]
   if not assigned:continue
   category=names.get(assigned[0])
   if not category:raise ValueError('Una categoría seleccionada ya no existe. Revisa la selección.')
   variants=pages(cfg,'products/'+str(parent['id'])+'/variations') if parent['type']=='variable' else [parent]
   if parent['type'] not in ['simple','variable']:skipped.append(parent['name']);continue
   for product in variants:
    if product.get('status','publish')!='publish' or product.get('stock_status')=='outofstock':continue
    if product.get('price') in [None,'']:skipped.append(parent['name']);continue
    name=html.unescape(parent['name'])
    if parent['type']=='variable':name+=' · '+', '.join(html.unescape(x['option']) for x in product.get('attributes',[]))
    if len(name)>200 or len(category)>200:raise ValueError('Hay un nombre de producto o categoría de más de 200 caracteres')
    tax_class=product.get('tax_class',parent.get('tax_class',''))
    if tax_class=='parent':tax_class=parent.get('tax_class','')
    tax=cfg.get('tax_map',{}).get(tax_class)
    # La configuración tributaria de la tienda no autoriza beneficios por empresa.
    if tax in ['EXENTO','EXONERADO']:tax='15'
    if tax not in TAXES:raise ValueError('Configura el impuesto local de la clase WooCommerce: '+(tax_class or 'estándar'))
    images=parent.get('images',[])
    image=product.get('image') or (images[0] if images else {})
    image_url=image.get('src','');old=cached.get(product['id']);photo=None
    metadata=json.dumps(dict(sku=product.get('sku',''),description=parent.get('description',''),remote_modified=product.get('date_modified_gmt'),categories=parent.get('categories',[]),image=image),ensure_ascii=False)
    if image_url and (not old or not old['has_photo'] or old['image_url']!=image_url or old['metadata']!=metadata):
     progress(phase='DESCARGANDO IMAGEN · '+name)
     try:photo=prepare_photo(image_bytes(cfg,image_url));image_count+=1;progress(images=image_count)
     except ValueError as error:
      image_errors.append(name+': '+str(error));image_url=old['image_url'] if old else '';metadata=''
    prepared.append(dict(remote_id=product['id'],name=name,category=category,price=cents(product['price']),tax=tax,image_url=image_url,photo=photo,metadata=metadata))
  progress(phase='GUARDANDO CATÁLOGO EN ESTA PC')
  with connect() as c:
   c.execute('BEGIN IMMEDIATE');current=read(c)
   if current.get('revision')!=cfg.get('revision'):raise ValueError('La configuración cambió durante la descarga. Sincroniza de nuevo.')
   c.execute('UPDATE products SET active=0')
   for row in prepared:
    old=c.execute('SELECT product_id FROM woo_products WHERE site=? AND remote_id=?',(cfg['url'],row['remote_id'])).fetchone()
    if old:pid=old[0];c.execute('UPDATE products SET name=?,category=?,price=?,tax_type=?,active=1 WHERE id=?',(row['name'],row['category'],row['price'],row['tax'],pid))
    else:pid=c.execute('INSERT INTO products(name,category,price,tax_type,active) VALUES(?,?,?,?,1)',(row['name'],row['category'],row['price'],row['tax'])).lastrowid
    if row['photo']:c.execute('INSERT INTO product_images(product_id,data,digest) VALUES(?,?,?) ON CONFLICT(product_id) DO UPDATE SET data=excluded.data,digest=excluded.digest',(pid,*row['photo']))
    elif not row['image_url'] and not any(e.startswith(row['name']+': ') for e in image_errors):c.execute('DELETE FROM product_images WHERE product_id=?',(pid,))
    c.execute('INSERT INTO woo_products VALUES(?,?,?,?,?) ON CONFLICT(site,remote_id) DO UPDATE SET image_url=excluded.image_url,metadata=excluded.metadata',(cfg['url'],row['remote_id'],pid,row['image_url'],row['metadata']))
   chosen_names=[names[i] for i in selected if i in names]
   saved_order=c.execute("SELECT value FROM settings WHERE key='category_order'").fetchone()
   previous_order=json.loads(saved_order[0]) if saved_order else []
   order=[name for name in previous_order if name in chosen_names]+[name for name in chosen_names if name not in previous_order]
   c.execute("INSERT OR REPLACE INTO settings VALUES('category_order',?)",(json.dumps(order,ensure_ascii=False),))
   current.update(last_success=datetime.now(timezone.utc).isoformat(),error='',count=len(prepared),skipped=len(skipped),category_cache=category_rows,image_errors=image_errors)
   save(c,current)
   c.execute('INSERT INTO audit(created_at,actor,event,entity,detail) VALUES(?,?,?,?,?)',(accounting.now(),'Sincronización WooCommerce','WOOCOMMERCE_SINCRONIZADO','CATALOGO',json.dumps(dict(count=len(prepared),skipped=len(skipped)))))
  progress(image_errors=image_errors)
  return dict(count=len(prepared),skipped=len(skipped))
 except ValueError as error:
  with connect() as c:cfg=read(c);cfg['error']=str(error);save(c,cfg)
  raise
 finally:LOCK.release()

def start(connect,prepare_photo):
 global STARTED
 if STARTED:return
 STARTED=True
 def worker():
  while True:
   time.sleep(300)
   try:
    with connect() as c:enabled=read(c).get('enabled')
    if enabled:launch(connect,prepare_photo)
   except Exception:pass
 threading.Thread(target=worker,daemon=True,name='WooCommerce-catalogo').start()

def register(app,connect,prepare_photo):
 @app.route('/api/admin/woocommerce',methods=['GET','POST'])
 def woo_config():
  with connect() as c:
   cfg=read(c)
   if request.method=='POST':
    d=request.get_json() or {};url=base_url(str(d.get('url','')).strip());parsed=urllib.parse.urlsplit(url)
    if parsed.scheme!='https' or not parsed.hostname or parsed.query or parsed.fragment or parsed.username or parsed.password:raise ValueError('Ingresa la dirección HTTPS de la tienda')
    key=str(d.get('key','')).strip();secret=str(d.get('secret','')).strip()
    if url!=base_url(cfg.get('url','')) and not (key and secret):raise ValueError('Para cambiar de tienda ingresa ambas claves')
    for name,value,prefix in [('key',key,'ck_'),('secret',secret,'cs_')]:
     if value:
      if not value.startswith(prefix):raise ValueError('Clave API inválida')
      cfg[name]=commerce.protect(value)
    selected=d.get('categories',[])
    if not isinstance(selected,list) or any(type(x) is not int or x<=0 for x in selected) or len(set(selected))!=len(selected):raise ValueError('Selección de categorías inválida')
    tax_map=d.get('tax_map',{'':'15'})
    if not isinstance(tax_map,dict) or any(v not in TAXES for v in tax_map.values()):raise ValueError('Asignación de impuestos inválida')
    cfg.update(url=url,enabled=d.get('enabled') is True,categories=selected,tax_map=tax_map,revision=cfg.get('revision',0)+1)
    if cfg['enabled'] and not(cfg.get('key') and cfg.get('secret')):raise ValueError('Ingresa las claves API')
    save(c,cfg)
   return jsonify(public(cfg))
 @app.get('/api/admin/woocommerce/categories')
 def woo_categories():
  with connect() as c:cfg=read(c)
  return jsonify(categories=categories(cfg))
 @app.post('/api/admin/woocommerce/sync')
 def woo_sync():return jsonify(launch(connect,prepare_photo)),202
 @app.get('/api/admin/woocommerce/progress')
 def woo_progress():return jsonify(state())
