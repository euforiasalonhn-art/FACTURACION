"""Modelo contable Access. Solo lectura del POS; sin credenciales ni fotos."""
import sqlite3,json,hashlib
import pc_labels
from pathlib import Path
from decimal import Decimal,ROUND_HALF_UP
from datetime import datetime

SCHEMA={}
def table(name,fields):
 SCHEMA[name]=dict(ClaveRegistro='TEXT(120)',**dict(x.split(':',1) for x in fields.split('|')))
table('Sucursales','IdSucursal:LONG|Nombre:TEXT(200)|Direccion:LONGTEXT|RTN:TEXT(30)|Activa:YESNO')
table('Empleados','IdEmpleado:LONG|Nombre:TEXT(200)|NombreFactura:TEXT(180)|Activo:YESNO')
table('Terminales','IdTerminal:LONG|IdSucursal:LONG|Nombre:TEXT(100)|Activa:YESNO')
table('Clientes','RTN:TEXT(30)|Nombre:TEXT(200)')
table('Productos','IdProducto:LONG|Nombre:TEXT(200)|Categoria:TEXT(150)|Precio:CURRENCY|TipoImpuesto:TEXT(30)')
table('Facturas','IdFactura:LONG|IdSucursal:LONG|Sucursal:TEXT(200)|IdTerminal:LONG|Terminal:TEXT(100)|IdEmpleado:LONG|Empleado:TEXT(200)|IdTurno:LONG|Orden:LONG|NumeroFiscal:TEXT(60)|Documento:TEXT(60)|Fiscal:YESNO|Fecha:DATETIME|FechaISO:TEXT(80)|Cliente:TEXT(200)|RTN:TEXT(30)|Modalidad:TEXT(30)|Servicio:TEXT(40)|Estado:TEXT(30)|MedioPrincipal:TEXT(30)|Subtotal:CURRENCY|Exento:CURRENCY|Exonerado:CURRENCY|Base15:CURRENCY|Base18:CURRENCY|ISV15:CURRENCY|ISV18:CURRENCY|Descuento:CURRENCY|VentaProductos:CURRENCY|Envio:CURRENCY|TotalCobrado:CURRENCY|Efectivo:CURRENCY|Tarjeta:CURRENCY|Transferencia:CURRENCY|OtrosPagos:CURRENCY|Recibido:CURRENCY|Cambio:CURRENCY|CAI:TEXT(80)|FechaLimite:TEXT(30)|RangoInicial:LONG|RangoFinal:LONG|OrdenCompra:TEXT(150)|Constancia:TEXT(150)|RegistroSAG:TEXT(150)|Notas:LONGTEXT|MotivoAnulacion:LONGTEXT|AnuladaPor:TEXT(200)|FechaAnulacion:DATETIME|DesgloseCompleto:YESNO|BeneficioEmpresa:TEXT(200)|RevisionBeneficio:LONG|HuellaOrigen:TEXT(64)')
table('DetalleFacturas','IdFactura:LONG|Linea:LONG|IdProducto:LONG|Producto:TEXT(200)|Cantidad:DOUBLE|PrecioUnitario:CURRENCY|ImporteAntesDescuento:CURRENCY|DescuentoLinea:CURRENCY|TipoImpuesto:TEXT(30)|SinDescuento:YESNO|OrigenDetalle:TEXT(60)')
table('PagosFactura','IdFactura:LONG|Medio:TEXT(30)|Cobrado:CURRENCY|Productos:CURRENCY|Envio:CURRENCY')
table('TurnosCaja','IdTurno:LONG|IdSucursal:LONG|Sucursal:TEXT(200)|IdTerminal:LONG|Terminal:TEXT(100)|IdEmpleado:LONG|AperturaPor:TEXT(200)|FechaApertura:DATETIME|Estado:TEXT(30)|FondoInicial:CURRENCY|VentasProductos:CURRENCY|EfectivoVentas:CURRENCY|TarjetaVentas:CURRENCY|Transferencias:CURRENCY|Entradas:CURRENCY|Salidas:CURRENCY|EsperadoActual:CURRENCY|EsperadoCierre:CURRENCY|Contado:CURRENCY|Diferencia:CURRENCY|FechaCierre:DATETIME|CierrePor:TEXT(200)')
table('MovimientosCaja','IdMovimiento:LONG|IdTurno:LONG|IdSucursal:LONG|Fecha:DATETIME|Tipo:TEXT(30)|Concepto:TEXT(200)|Referencia:TEXT(200)|Importe:CURRENCY|RegistradoPor:TEXT(200)')
table('AlmuerzosEmpleado','IdAlmuerzo:LONG|IdSucursal:LONG|Sucursal:TEXT(200)|IdTerminal:LONG|IdEmpleado:LONG|IdTurno:LONG|Empleado:TEXT(200)|Fecha:DATETIME|Costo:CURRENCY|CostoPendiente:YESNO|Cobrado:CURRENCY|ValorReferencia:CURRENCY|Notas:LONGTEXT')
table('DetalleAlmuerzos','IdAlmuerzo:LONG|Linea:LONG|IdProducto:LONG|Producto:TEXT(200)|Cantidad:DOUBLE|PrecioReferencia:CURRENCY|ImporteReferencia:CURRENCY')
table('ConsumosInternos','IdConsumo:LONG|IdSucursal:LONG|Sucursal:TEXT(200)|IdTerminal:LONG|IdTurno:LONG|Beneficiario:TEXT(200)|Fecha:DATETIME|ValorReferencia:CURRENCY|Cobrado:CURRENCY|CorreoDestino:TEXT(200)|EstadoCorreo:TEXT(30)|Notas:LONGTEXT')
table('DetalleConsumos','IdConsumo:LONG|Linea:LONG|IdProducto:LONG|Producto:TEXT(200)|Cantidad:DOUBLE|PrecioReferencia:CURRENCY|ImporteReferencia:CURRENCY')
table('NotasCredito','IdNota:LONG|IdFactura:LONG|IdSucursal:LONG|IdTurno:LONG|Fecha:DATETIME|RegistradaPor:TEXT(200)|Motivo:LONGTEXT|Total:CURRENCY|ISV15:CURRENCY|ISV18:CURRENCY')
table('DescuentosIdentificados','IdFactura:LONG|Perfil:TEXT(30)|IdEmpleado:LONG|Beneficiario:TEXT(200)|Identidad:TEXT(30)')
table('MetasVentas','IdMeta:LONG|IdSucursal:LONG|Nombre:TEXT(200)|Meta:CURRENCY|Desde:DATETIME|Hasta:DATETIME|Activa:YESNO')
table('BeneficiosEmpresa','IdBeneficio:LONG|Empresa:TEXT(200)|RTN:TEXT(30)|Tipo:TEXT(30)|Activa:YESNO|Revision:LONG|FechaActualizacion:DATETIME')
table('ProductosAutorizados','IdBeneficio:LONG|IdProducto:LONG')
table('Auditoria','IdEvento:LONG|Fecha:DATETIME|Usuario:TEXT(200)|Accion:TEXT(120)|Referencia:TEXT(150)|Detalle:LONGTEXT')
table('Comandas','IdComanda:LONG|IdSucursal:LONG|Tipo:TEXT(30)|IdOrigen:LONG|Fecha:DATETIME|Servicio:TEXT(40)|NombrePedido:TEXT(200)|Notas:LONGTEXT')
table('ControlSincronizacion','Origen:TEXT(100)|Actualizado:DATETIME|UltimaFactura:LONG|TotalFacturas:LONG|FacturasVigentes:LONG|FacturasAnuladas:LONG|EventosPendientes:LONG|UltimoEvento:LONG|VersionModelo:LONG|Estado:TEXT(200)')

WATCH=['invoices','branches','products','customers','employees','terminals','cash_sessions','cash_movements','employee_meals','special_orders','credit_notes','discount_beneficiaries','sales_goals','company_benefits','audit','kitchen_orders','invoice_items']
def amount(v):
 return None if v is None else format((Decimal(str(v))/100).quantize(Decimal('.01'),rounding=ROUND_HALF_UP),'f')
def date(v):
 if not v:return None
 try:return datetime.fromisoformat(str(v).replace('Z','+00:00')).replace(tzinfo=None).isoformat(timespec='seconds')
 except ValueError:return None
def obj(s):
 try:return json.loads(s or '{}')
 except (ValueError,TypeError):return {}
def rows(c,t):return [dict(x) for x in c.execute('SELECT * FROM '+t)] if c.execute("SELECT 1 FROM sqlite_master WHERE name=?",(t,)).fetchone() else []
def build(db):
 source=sqlite3.connect(Path(db).resolve().as_uri()+'?mode=ro',uri=True,timeout=20)
 c=sqlite3.connect(':memory:');c.row_factory=sqlite3.Row
 try:source.backup(c)
 finally:source.close()
 try:return extract(c)
 finally:c.close()
def extract(c):
 import delivery
 data={k:[] for k in SCHEMA}
 def add(t,key,**values):
  row=dict(ClaveRegistro=str(key),**values)
  row={k:row.get(k) for k in SCHEMA[t]}
  for k,typ in SCHEMA[t].items():
   if isinstance(row[k],str) and typ.startswith('TEXT('):row[k]=row[k][:int(typ[5:-1])]
  digest=hashlib.sha256(json.dumps(row,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
  data[t].append(dict(values=row,hash=digest))
 branches={r['id']:r for r in rows(c,'branches')};terminals={r['id']:r for r in rows(c,'terminals')}
 for r in branches.values():add('Sucursales',r['id'],IdSucursal=r['id'],Nombre=r['name'],Direccion=r['address'],RTN=r.get('rtn'),Activa=bool(r.get('active',1)))
 for r in rows(c,'employees'):add('Empleados',r['id'],IdEmpleado=r['id'],Nombre=r['name'],NombreFactura=(r.get('first_name','')+' '+r.get('first_surname','')).strip(),Activo=bool(r['active']))
 add('Terminales',0,IdTerminal=0,Nombre='PC 1',Activa=True)
 for r in terminals.values():add('Terminales',r['id'],IdTerminal=r['id'],IdSucursal=r['branch_id'],Nombre=pc_labels.name(r['id']),Activa=bool(r['active']))
 for r in rows(c,'customers'):add('Clientes',r['rtn'],RTN=r['rtn'],Nombre=r['name'])
 for r in rows(c,'products'):add('Productos',r['id'],IdProducto=r['id'],Nombre=r['name'],Categoria=r['category'],Precio=amount(r['price']),TipoImpuesto=r['tax_type'])
 inv=rows(c,'invoices');payments={};snapshots={};legacy={}
 for entry in rows(c,'invoice_items'):legacy.setdefault(entry['invoice_id'],[]).append(entry)
 for r in inv:
  s=obj(r.get('snapshot'));snapshots[r['id']]=s;p=s.get('payments')
  if not isinstance(p,dict):p={r['payment_method']:r['total']}
  payments[r['id']]=p;fee=s.get('delivery_fee',r.get('delivery_fee',0)) or 0;ps,pd=delivery.split_payments(p,fee)
  fiscal=s.get('fiscal',{});extra=s.get('extra',{});benefit=s.get('company_benefit') or {}
  values=dict(IdFactura=r['id'],IdSucursal=r['branch_id'],Sucursal=branches.get(r['branch_id'],{}).get('name',''),IdTerminal=r.get('terminal_id',0),Terminal=pc_labels.name(r.get('terminal_id',0)),IdEmpleado=s.get('cashier_id'),Empleado=s.get('cashier_full_name',s.get('cashier','HISTORICO')),IdTurno=r.get('cash_session_id'),Orden=r['number'],NumeroFiscal=r.get('fiscal_number'),Documento=r.get('fiscal_number') or 'INTERNO-'+str(r['number']),Fiscal=bool(r.get('fiscal_number')),Fecha=date(r['created_at']),FechaISO=r['created_at'],Cliente=r['customer_name'],RTN=r['customer_rtn'],Modalidad=r['invoice_type'],Servicio=s.get('service','HISTORICO'),Estado=r['status'],MedioPrincipal=r['payment_method'],Envio=amount(fee),VentaProductos=amount(r['total']-fee),TotalCobrado=amount(r['total']),Efectivo=amount(p.get('Efectivo',0)),Tarjeta=amount(p.get('Tarjeta',0)),Transferencia=amount(p.get('Transferencia',0)),OtrosPagos=amount(sum(v for k,v in p.items() if k not in ['Efectivo','Tarjeta','Transferencia'])),Recibido=amount(r['amount_received']),Cambio=amount(r['amount_received']-r['total']),CAI=fiscal.get('cai','') if r.get('fiscal_number') else '',FechaLimite=fiscal.get('deadline',''),RangoInicial=fiscal.get('range_start'),RangoFinal=fiscal.get('range_end'),OrdenCompra=extra.get('purchase_order'),Constancia=extra.get('exemption_certificate'),RegistroSAG=extra.get('sag'),Notas=s.get('notes',''),MotivoAnulacion=r.get('void_reason'),AnuladaPor=r.get('void_actor'),FechaAnulacion=date(r.get('void_at')),DesgloseCompleto='taxable_15' in s,BeneficioEmpresa=benefit.get('name'),RevisionBeneficio=benefit.get('revision'),HuellaOrigen=hashlib.sha256((r.get('snapshot') or '').encode()).hexdigest())
  values['DesgloseCompleto']=all(k in s for k in ['taxable_15','taxable_18','exempt','exempted'])
  for src,dst in [('subtotal','Subtotal'),('tax_15','ISV15'),('tax_18','ISV18'),('discount','Descuento')]:values[dst]=amount(r.get(src))
  for src,dst in [('exempt','Exento'),('exempted','Exonerado'),('taxable_15','Base15'),('taxable_18','Base18')]:values[dst]=amount(s.get(src))
  add('Facturas',r['id'],**values)
  items=s.get('items',[])
  if not items:items=[dict(id=x['product_id'],name=x['product_name'],quantity=x['quantity'],price=x['unit_price'],line_total=x['line_total'],tax_type=x['tax_type']) for x in legacy.get(r['id'],[])]
  for i,it in enumerate(items,1):add('DetalleFacturas',f"{r['id']}:{i}",IdFactura=r['id'],Linea=i,IdProducto=it.get('id'),Producto=it['name'],Cantidad=it['quantity'],PrecioUnitario=amount(it['price']),ImporteAntesDescuento=amount(it['line_total']),DescuentoLinea=amount(it.get('line_discount')),TipoImpuesto=it['tax_type'],SinDescuento=bool(it.get('no_discount')),OrigenDetalle='SNAPSHOT' if s.get('items') else 'HISTORICO - VERIFICAR')
  for medium,value in p.items():
   if value:add('PagosFactura',f"{r['id']}:{medium}",IdFactura=r['id'],Medio=medium,Cobrado=amount(value),Productos=amount(ps.get(medium,0)),Envio=amount(pd.get(medium,0)))
 movements=rows(c,'cash_movements');shifts=rows(c,'cash_sessions');byshift={};moveshift={}
 for x in inv:
  if x['status']=='EMITIDA':byshift.setdefault(x.get('cash_session_id'),[]).append(x)
 for m in movements:moveshift.setdefault(m['session_id'],[]).append(m)
 for r in shifts:
  active=byshift.get(r['id'],[]);p={k:sum(payments[x['id']].get(k,0) for x in active) for k in ['Efectivo','Tarjeta','Transferencia']}
  ms=moveshift.get(r['id'],[]);ins=sum(m['amount'] for m in ms if m['kind']=='INGRESO');outs=sum(m['amount'] for m in ms if m['kind']=='EGRESO')
  add('TurnosCaja',r['id'],IdTurno=r['id'],IdSucursal=r['branch_id'],Sucursal=branches.get(r['branch_id'],{}).get('name'),IdTerminal=r.get('terminal_id',0),Terminal=pc_labels.name(r.get('terminal_id',0)),IdEmpleado=r.get('cashier_id'),AperturaPor=r['opened_by'],FechaApertura=date(r['opened_at']),Estado=r['status'],FondoInicial=amount(r['opening']),VentasProductos=amount(sum(x['total']-(x.get('delivery_fee') or 0) for x in active)),EfectivoVentas=amount(p['Efectivo']),TarjetaVentas=amount(p['Tarjeta']),Transferencias=amount(p['Transferencia']),Entradas=amount(ins),Salidas=amount(outs),EsperadoActual=amount(r['opening']+p['Efectivo']+ins-outs),EsperadoCierre=amount(r.get('expected')),Contado=amount(r.get('counted')),Diferencia=amount(r.get('difference')),FechaCierre=date(r.get('closed_at')),CierrePor=r.get('closed_by'))
 shiftmap={r['id']:r for r in shifts}
 for r in movements:add('MovimientosCaja',r['id'],IdMovimiento=r['id'],IdTurno=r['session_id'],IdSucursal=shiftmap.get(r['session_id'],{}).get('branch_id'),Fecha=date(r['created_at']),Tipo=r['kind'],Concepto=r['concept'],Referencia=r['reference'],Importe=amount(r['amount']),RegistradoPor=r['actor'])
 for source,target,detail,idname in [('employee_meals','AlmuerzosEmpleado','DetalleAlmuerzos','IdAlmuerzo'),('special_orders','ConsumosInternos','DetalleConsumos','IdConsumo')]:
  for r in rows(c,source):
   s=obj(r['snapshot']);values={idname:r['id'],'IdSucursal':r['branch_id'],'Sucursal':branches.get(r['branch_id'],{}).get('name'),'IdTerminal':r.get('terminal_id',0),'IdTurno':r.get('cash_session_id'),'Fecha':date(r['created_at']),'ValorReferencia':amount(s.get('total',0)),'Cobrado':amount(0),'Notas':s.get('notes','')}
   if source=='employee_meals':values.update(IdEmpleado=r.get('employee_id'),Empleado=r['recipient'],Costo=amount(r['cost']),CostoPendiente=not bool(r['cost']))
   else:values.update(Beneficiario=r['recipient'],CorreoDestino=r['email_to'],EstadoCorreo=r['email_status'])
   add(target,r['id'],**values)
   for i,it in enumerate(s.get('items',[]),1):add(detail,f"{r['id']}:{i}",**{idname:r['id'],'Linea':i,'IdProducto':it.get('id'),'Producto':it['name'],'Cantidad':it['quantity'],'PrecioReferencia':amount(it['price']),'ImporteReferencia':amount(it['line_total'])})
 for r in rows(c,'credit_notes'):add('NotasCredito',r['id'],IdNota=r['id'],IdFactura=r['invoice_id'],IdSucursal=r['branch_id'],IdTurno=r.get('cash_session_id'),Fecha=date(r['created_at']),RegistradaPor=r['actor'],Motivo=r['reason'],Total=amount(r['total']),ISV15=amount(r['tax_15']),ISV18=amount(r['tax_18']))
 for r in rows(c,'discount_beneficiaries'):add('DescuentosIdentificados',r['invoice_id'],IdFactura=r['invoice_id'],Perfil=r['profile'],IdEmpleado=r['employee_id'],Beneficiario=r['name'],Identidad=r['identity'])
 for r in rows(c,'sales_goals'):add('MetasVentas',r['id'],IdMeta=r['id'],IdSucursal=r['branch_id'],Nombre=r['title'],Meta=amount(r['target']),Desde=date(r['start']),Hasta=date(r['end']),Activa=bool(r['active']))
 for r in rows(c,'company_benefits'):
  add('BeneficiosEmpresa',r['id'],IdBeneficio=r['id'],Empresa=r['name'],RTN=r['rtn'],Tipo=r['kind'],Activa=bool(r['active']),Revision=r['revision'],FechaActualizacion=date(r['updated_at']))
  for pid in obj(r['products']):add('ProductosAutorizados',f"{r['id']}:{pid}",IdBeneficio=r['id'],IdProducto=pid)
 for r in rows(c,'audit'):add('Auditoria',r['id'],IdEvento=r['id'],Fecha=date(r['created_at']),Usuario=r['actor'],Accion=r['event'],Referencia=r['entity'],Detalle=r['detail'])
 for r in rows(c,'kitchen_orders'):
  s=obj(r['snapshot']);add('Comandas',r['id'],IdComanda=r['id'],IdSucursal=r['branch_id'],Tipo=r['kind'],IdOrigen=r['source_id'],Fecha=date(r['created_at']),Servicio=s.get('service'),NombrePedido=s.get('order_name'),Notas=s.get('notes'))
 ev=c.execute("SELECT COALESCE((SELECT seq FROM sqlite_sequence WHERE name='access_sync_outbox'),0)").fetchone()[0] if c.execute("SELECT 1 FROM sqlite_master WHERE name='access_sync_outbox'").fetchone() else 0
 identity=c.execute("SELECT value FROM settings WHERE key='session_key'").fetchone();origin=hashlib.sha256(str(identity[0]).encode()).hexdigest() if identity else ''
 # No se exporta la ruta de la base ni secretos de configuración.
 add('ControlSincronizacion','principal',Origen=origin or 'FRY-ORIGEN',Actualizado=datetime.now().isoformat(timespec='seconds'),UltimaFactura=max([r['id'] for r in inv],default=0),TotalFacturas=len(inv),FacturasVigentes=sum(r['status']=='EMITIDA' for r in inv),FacturasAnuladas=sum(r['status']=='ANULADA' for r in inv),EventosPendientes=0,UltimoEvento=ev,VersionModelo=1,Estado='ACTUALIZADO - COPIA CONTABLE DE SOLO CONSULTA')
 return dict(schema=SCHEMA,tables=data,last_event=ev,origin=origin or 'FRY-ORIGEN',version=1)
