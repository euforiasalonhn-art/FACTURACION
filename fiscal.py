"""Configuración y cálculo de la factura; no valida autorizaciones contra el SAR."""
import json,re
from decimal import Decimal,ROUND_HALF_UP
from datetime import datetime
DEFAULT=dict(enabled=False,legal_name='',commercial_name='FRY CHICKEN',rtn='',address='',head_address='',phone='',email='',cai='',establishment='',point='',range_start=1,range_end=1,next_number=1,deadline='',price_mode='INCLUSIVE',cashier='CAJA')
def config(c,branch):
 r=c.execute('SELECT value FROM settings WHERE key=?',(f'fiscal:{branch}',)).fetchone()
 return DEFAULT|json.loads(r[0]) if r else DEFAULT.copy()
def save(c,branch,value): c.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',(f'fiscal:{branch}',json.dumps(value,ensure_ascii=False)))
def prefix(cfg):return f"{cfg['establishment']}-{cfg['point']}-01-"
def number(cfg,n):return prefix(cfg)+f'{n:08d}'
def integer(value,name):
 if not re.fullmatch(r'[0-9]{1,8}',str(value)):raise ValueError(name+' debe contener hasta 8 dígitos')
 return int(value)
def validate(c,branch,data,today=None):
 cfg={k:data.get(k,v) for k,v in DEFAULT.items()};cfg['enabled']=data.get('enabled') is True
 for key in DEFAULT:
  if isinstance(DEFAULT[key],str):cfg[key]=str(cfg[key]).strip()
 if cfg['price_mode'] not in ['INCLUSIVE','EXCLUSIVE']:raise ValueError('Selecciona si los precios incluyen ISV')
 if len(cfg['cashier'])>100:raise ValueError('Nombre de cajero demasiado largo')
 if not cfg['enabled']:return cfg
 for key,label in [('legal_name','Razón social'),('commercial_name','Nombre comercial'),('address','Dirección del local'),('head_address','Dirección de casa matriz'),('phone','Teléfono')]:
  if not cfg[key] or len(cfg[key])>250:raise ValueError('Completa '+label)
 if not re.fullmatch(r'[0-9]{14}',cfg['rtn']):raise ValueError('El RTN del emisor debe contener 14 dígitos')
 if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',cfg['email']):raise ValueError('Completa el correo del emisor')
 cfg['cai']=cfg['cai'].upper()
 if not re.fullmatch(r'(?:[0-9A-F]{6}-){5}[0-9A-F]{2}',cfg['cai']):raise ValueError('CAI inválido: usa los 6 grupos de la autorización, separados por guiones')
 for key in ['establishment','point']:
  if not re.fullmatch(r'[0-9]{3}',cfg[key]):raise ValueError('Establecimiento y punto de emisión deben contener 3 dígitos cada uno')
 for key,label in [('range_start','Inicio del rango'),('range_end','Fin del rango'),('next_number','Siguiente número')]:cfg[key]=integer(cfg[key],label)
 if not 1<=cfg['range_start']<=cfg['next_number']<=cfg['range_end']<=99999999:raise ValueError('El siguiente número debe estar dentro del rango autorizado')
 try:deadline=datetime.strptime(cfg['deadline'],'%Y-%m-%d').date()
 except ValueError:raise ValueError('Fecha límite inválida')
 if deadline<(today or datetime.now().astimezone().date()):raise ValueError('La autorización está vencida')
 used=c.execute('SELECT MAX(fiscal_number) FROM invoices WHERE fiscal_number LIKE ?',(prefix(cfg)+'%',)).fetchone()[0]
 if used and cfg['next_number']<=int(used.rsplit('-',1)[1]):raise ValueError('El siguiente número no puede reutilizar ni retroceder sobre facturas emitidas o anuladas')
 other=c.execute('SELECT key,value FROM settings WHERE key LIKE ? AND key<>?',('fiscal:%',f'fiscal:{branch}')).fetchall()
 for r in other:
  v=json.loads(r['value'])
  if v.get('enabled') and prefix(v)==prefix(cfg):raise ValueError('Ese establecimiento y punto de emisión ya están asignados a otra sucursal en esta PC')
 return cfg

def ensure_available(c,cfg,today=None):
 missing=[]
 for key,label in [('legal_name','razón social'),('commercial_name','nombre comercial'),('rtn','RTN del emisor'),('address','dirección de sucursal'),('phone','teléfono'),('email','correo'),('cai','CAI'),('establishment','establecimiento'),('point','punto de emisión'),('deadline','fecha límite')]:
  if not str(cfg.get(key,'')).strip():missing.append(label)
 if not cfg.get('enabled'):missing.append('activar autorización CAI')
 if missing:raise ValueError('FACTURACIÓN BLOQUEADA. Falta configurar: '+', '.join(missing)+'. Ingresa en Ajustes → Facturación y CAI.')
 if not re.fullmatch(r'[0-9]{14}',str(cfg.get('rtn',''))):raise ValueError('FACTURACIÓN BLOQUEADA. Revisa el RTN del emisor: debe contener 14 dígitos')
 if not re.fullmatch(r'(?:[0-9A-F]{6}-){5}[0-9A-F]{2}',str(cfg.get('cai','')).upper()):raise ValueError('FACTURACIÓN BLOQUEADA. Revisa el formato del CAI')
 if datetime.strptime(cfg['deadline'],'%Y-%m-%d').date()<(today or datetime.now().astimezone().date()):raise ValueError('CAI vencido. El administrador debe registrar la autorización vigente')
 if not cfg['range_start']<=cfg['next_number']<=cfg['range_end']:raise ValueError('Rango autorizado agotado. No se emitió la venta')
 if c.execute('SELECT 1 FROM invoices WHERE fiscal_number=?',(number(cfg,cfg['next_number']),)).fetchone():raise ValueError('El correlativo ya fue usado. Revisa la autorización')

def round_int(value):return int(Decimal(value).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
def calculate(c,d,money,approval=None):
 branch=d.get('branch_id',1);cfg=config(c,branch);items=d.get('items',[])
 if not items or len(items)>200:raise ValueError('Agrega productos')
 rows=[]
 for item in items:
  q=item.get('quantity')
  if not isinstance(q,int) or isinstance(q,bool) or not 1<=q<=999:raise ValueError('Cantidad inválida')
  p=c.execute('SELECT * FROM products WHERE id=?',(item.get('id'),)).fetchone()
  if p and 'active' in p.keys() and not p['active']:raise ValueError('Este producto ya no está disponible en el catálogo seleccionado')
  if not p or p['price']<=0:raise ValueError('Configura el precio de los productos antes de vender')
  price=round_int(p['price']);rows.append(dict(p)|dict(price=price,quantity=q,line_total=price*q))
  if rows[-1]['tax_type'] in ['EXENTO','EXONERADO']:
   rows[-1]['catalog_tax_type']=rows[-1]['tax_type'];rows[-1]['tax_type']='15'
 # The server supplies the authorization; client tax overrides are never trusted.
 applied=[]
 if approval:
  if d.get('invoice_type')!='RTN' or str(d.get('customer_rtn','')).strip()!=approval['rtn'] or not str(d.get('customer_name','')).strip():raise ValueError('El beneficio requiere empresa y RTN autorizados')
  allowed=set(approval['products'])
  for row in rows:
   if row['id'] not in allowed:continue
   row['original_tax_type']=row['tax_type'];row['original_price']=row['price']
   if cfg['price_mode']=='INCLUSIVE' and row['tax_type'] in ['15','18']:
    denominator=100+int(row['tax_type'])
    row['price']=round_int(Decimal(row['price'])*100/denominator)
    row['line_total']=round_int(Decimal(row['line_total'])*100/denominator)
   row['tax_type']=approval['kind'];applied.append(row['id'])
 excluded={r[0] for r in c.execute('SELECT product_id FROM discount_exclusions')} if c.execute("SELECT 1 FROM sqlite_master WHERE name='discount_exclusions'").fetchone() else set()
 for r in rows:r['no_discount']=r['id'] in excluded
 listed=sum(r['line_total'] for r in rows)
 eligible=sum(r['line_total'] for r in rows if not r['no_discount'])
 discount_type=d.get('discount_type','AMOUNT');rate=Decimal('0')
 if discount_type=='PERCENT':
  try:rate=Decimal(str(d.get('discount',0)))
  except Exception:raise ValueError('Porcentaje inválido')
  if not rate.is_finite() or not 0<=rate<=100:raise ValueError('El porcentaje debe estar entre 0 y 100')
  discount=round_int(Decimal(eligible)*rate/100)
 elif discount_type=='AMOUNT':discount=money(d.get('discount',0))
 else:raise ValueError('Tipo de descuento inválido')
 if discount>eligible:raise ValueError('El descuento no puede superar el importe de productos autorizados')
 # Largest remainder allocation keeps every cent of a global discount assigned.
 parts=[divmod(discount*r['line_total'],eligible) if eligible and not r['no_discount'] else (0,0) for r in rows];shares=[p[0] for p in parts]
 for i in sorted(range(len(rows)),key=lambda i:parts[i][1],reverse=True)[:discount-sum(shares)]:shares[i]+=1
 groups={'15':0,'18':0,'EXENTO':0,'EXONERADO':0}
 for r,share in zip(rows,shares):r['line_discount']=share;groups[r['tax_type']]+=r['line_total']-share
 bases={};taxes={}
 discount_rate=rate
 for rate in ['15','18']:
  bases[rate]=round_int(Decimal(groups[rate])*100/(100+int(rate))) if cfg['price_mode']=='INCLUSIVE' else groups[rate]
  taxes[rate]=groups[rate]-bases[rate] if cfg['price_mode']=='INCLUSIVE' else round_int(Decimal(bases[rate])*int(rate)/100)
 subtotal=bases['15']+bases['18']+groups['EXENTO']+groups['EXONERADO'];total=subtotal+sum(taxes.values())
 if total>10000000000:raise ValueError('El total supera el máximo permitido por venta')
 return dict(company_benefit=({k:approval[k] for k in ['id','revision','name','rtn','kind','updated_at','has_photo']}|dict(products=applied)) if applied else None,discount_type=discount_type,discount_rate=str(discount_rate) if discount_type=='PERCENT' else '',items=rows,listed_total=listed,discount_eligible_total=eligible,no_discount_total=listed-eligible,subtotal=subtotal,exempt=groups['EXENTO'],exempted=groups['EXONERADO'],taxable_15=bases['15'],taxable_18=bases['18'],tax_15=taxes['15'],tax_18=taxes['18'],discount=discount,total=total,price_mode=cfg['price_mode'],calculation_version=4)

def words(n):
 units=['cero','uno','dos','tres','cuatro','cinco','seis','siete','ocho','nueve','diez','once','doce','trece','catorce','quince','dieciséis','diecisiete','dieciocho','diecinueve','veinte','veintiuno','veintidós','veintitrés','veinticuatro','veinticinco','veintiséis','veintisiete','veintiocho','veintinueve']
 if n<30:return units[n]
 if n<100:return ['','','','treinta','cuarenta','cincuenta','sesenta','setenta','ochenta','noventa'][n//10]+(' y '+words(n%10) if n%10 else '')
 if n==100:return 'cien'
 if n<1000:return ['','ciento','doscientos','trescientos','cuatrocientos','quinientos','seiscientos','setecientos','ochocientos','novecientos'][n//100]+(' '+words(n%100) if n%100 else '')
 if n<1000000:return ('mil' if n//1000==1 else apocope(words(n//1000))+' mil')+(' '+words(n%1000) if n%1000 else '')
 return ('un millón' if n//1000000==1 else apocope(words(n//1000000))+' millones')+(' '+words(n%1000000) if n%1000000 else '')
def apocope(s):
 if s.endswith('veintiuno'):return s[:-9]+'veintiún'
 if s.endswith('uno'):return s[:-3]+'un'
 return s
def amount_words(cents):return apocope(words(cents//100)).upper()+(' LEMPIRA' if cents//100==1 else ' LEMPIRAS')+f' Y {cents%100:02d}/100'


def receipt_items(snapshot):
 # Importes de presentación antes del descuento; no modifica el snapshot guardado.
 rows=[dict(it) for it in snapshot.get('items',[])]
 inclusive=snapshot.get('price_mode',snapshot.get('fiscal',{}).get('price_mode'))=='INCLUSIVE'
 groups={}
 for i,it in enumerate(rows):
  price=round_int(it['price']);total=round_int(it['line_total']);rate=str(it.get('tax_type',''))
  it['receipt_price']=price;it['receipt_total']=total
  if inclusive and rate in ['15','18']:
   denominator=100+int(rate);it['receipt_price']=round_int(Decimal(price)*100/denominator)
   groups.setdefault(rate,[]).append((i,total))
 for rate,entries in groups.items():
  denominator=100+int(rate);target=round_int(Decimal(sum(total for _,total in entries))*100/denominator)
  parts=[divmod(total*100,denominator) for _,total in entries];values=[a for a,b in parts]
  for j in sorted(range(len(entries)),key=lambda j:parts[j][1],reverse=True)[:target-sum(values)]:values[j]+=1
  for (i,_),value in zip(entries,values):rows[i]['receipt_total']=value
 return rows
