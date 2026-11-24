"""Autorizaciones por empresa y producto, registradas exclusivamente por el dueño."""
import json,re,io,hashlib
from datetime import datetime
from decimal import Decimal
from flask import request,session,jsonify,send_file
from PIL import Image,ImageOps

def init(c):
 c.execute("CREATE TABLE IF NOT EXISTS company_benefits(id INTEGER PRIMARY KEY,name TEXT NOT NULL,rtn TEXT NOT NULL UNIQUE,kind TEXT NOT NULL,active INTEGER NOT NULL,products TEXT NOT NULL,revision INTEGER NOT NULL,updated_at TEXT NOT NULL,photo BLOB)")
 c.execute("CREATE TABLE IF NOT EXISTS company_benefit_history(company_id INTEGER,revision INTEGER,record TEXT NOT NULL,photo BLOB,PRIMARY KEY(company_id,revision))")

def public(r):
 d=dict(r);photo=d.pop('photo',None);d['products']=json.loads(d['products']);d['has_photo']=bool(photo);return d

def approved(c,d):
 if d.get('apply_company_benefit') is not True:return None
 if d.get('invoice_type')!='RTN' or not str(d.get('customer_name','')).strip() or not re.fullmatch(r'[0-9]{14}',str(d.get('customer_rtn','')).strip()):raise ValueError('Para aplicar EXENTO o EXONERADO, selecciona empresa e indica su RTN de 14 dígitos')
 row=c.execute('SELECT * FROM company_benefits WHERE rtn=? AND active=1',(str(d.get('customer_rtn','')).strip(),)).fetchone()
 if not row:raise ValueError('La empresa no tiene una autorización EXENTO o EXONERADO activa en AJUSTES')
 return public(row)

def register(app,connect):
 @app.route('/api/admin/company-benefits',methods=['GET','POST'])
 def companies():
  if session.get('role')!='admin':return jsonify(error='Acceso exclusivo del administrador'),403
  with connect() as c:
   if request.method=='POST':
    d=request.get_json();name=str(d.get('name','')).strip();rtn=str(d.get('rtn','')).strip();kind=d.get('kind');ids=d.get('products')
    if not name or len(name)>200 or not re.fullmatch(r'[0-9]{14}',rtn):raise ValueError('Completa empresa y RTN de 14 dígitos')
    if kind not in ['EXENTO','EXONERADO']:raise ValueError('Selecciona EXENTO o EXONERADO')
    if not isinstance(ids,list) or not ids or any(type(x)!=int for x in ids) or len(ids)!=len(set(ids)):raise ValueError('Selecciona los productos autorizados')
    valid={x[0] for x in c.execute('SELECT id FROM products')}
    if not set(ids)<=valid:raise ValueError('El catálogo cambió. Recarga los productos')
    rid=int(d.get('id') or 0);old=c.execute('SELECT * FROM company_benefits WHERE id=?',(rid,)).fetchone()
    if rid and not old:raise ValueError('Empresa no encontrada')
    duplicate=c.execute('SELECT id FROM company_benefits WHERE rtn=? AND id<>?',(rtn,rid)).fetchone()
    if duplicate:raise ValueError('Ya existe una autorización para ese RTN')
    photo=old['photo'] if old and not d.get('remove_photo') else None
    if d.get('photo'):
     import base64
     try:
      raw=base64.b64decode(d['photo'],validate=True)
      if len(raw)>8*1024*1024:raise ValueError()
      with Image.open(io.BytesIO(raw)) as im:
       if im.width*im.height>20000000:raise ValueError()
       im=ImageOps.exif_transpose(im).convert('RGB');im.thumbnail((2000,2000));out=io.BytesIO();im.save(out,format='JPEG',quality=88);photo=out.getvalue()
     except Exception:raise ValueError('Foto inválida. Usa JPG o PNG, máximo 8 MB y 20 megapíxeles')
    revision=old['revision']+1 if old else 1;now=datetime.now().astimezone().isoformat(timespec='seconds')
    values=(name,rtn,kind,int(d.get('active') is True),json.dumps(sorted(ids)),revision,now,photo)
    if old:c.execute('UPDATE company_benefits SET name=?,rtn=?,kind=?,active=?,products=?,revision=?,updated_at=?,photo=? WHERE id=?',values+(rid,))
    else:rid=c.execute('INSERT INTO company_benefits(name,rtn,kind,active,products,revision,updated_at,photo) VALUES(?,?,?,?,?,?,?,?)',values).lastrowid
    current=public(c.execute('SELECT * FROM company_benefits WHERE id=?',(rid,)).fetchone())
    c.execute('INSERT INTO company_benefit_history VALUES(?,?,?,?)',(rid,revision,json.dumps(current,ensure_ascii=False),photo))
    c.execute('INSERT INTO customers(rtn,name) VALUES(?,?) ON CONFLICT(rtn) DO UPDATE SET name=excluded.name',(rtn,name))
   return jsonify([public(x) for x in c.execute('SELECT * FROM company_benefits ORDER BY name')])
 @app.get('/api/admin/company-benefits/<int:rid>/photo')
 def photo(rid):
  if session.get('role')!='admin':return jsonify(error='Acceso exclusivo del administrador'),403
  with connect() as c:
   revision=request.args.get('revision',type=int)
   row=c.execute('SELECT photo FROM company_benefit_history WHERE company_id=? AND revision=?',(rid,revision)).fetchone() if revision else c.execute('SELECT photo FROM company_benefits WHERE id=?',(rid,)).fetchone()
  if not row or not row[0]:return jsonify(error='Sin foto adjunta'),404
  response=send_file(io.BytesIO(row[0]),mimetype='image/jpeg');response.headers['Cache-Control']='no-store';return response
