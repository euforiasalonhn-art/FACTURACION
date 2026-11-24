import terminals
import cash_safety
import employee_sessions
import delivery
"""Libro de ventas, turnos y trazabilidad. Importes internos en centavos."""
import json,io,re
import fiscal
from datetime import datetime
from decimal import Decimal
from flask import request,jsonify,session,send_file,render_template
from werkzeug.security import generate_password_hash,check_password_hash

LABELS={'subtotal':'Subtotal neto','tax_15':'ISV 15%','tax_18':'ISV 18%','discount':'Descuento aplicado','total':'Venta de productos (sin envío)','delivery_fee':'Envíos por cuenta de tercero','collected_total':'Total cobrado con envío','exempt':'Importe exento','exempted':'Importe exonerado','taxable_15':'Base gravada 15%','taxable_18':'Base gravada 18%'}
def label(key):return LABELS.get(key,key)
def filter_text(args):return 'Sucursal: '+str(args.get('branch_id','all')).replace('all','Todas')+' | Desde: '+str(args.get('start') or 'Sin límite')+' | Hasta: '+str(args.get('end') or 'Sin límite')+' | Documentos: '+{'all':'Todos','fiscal':'Con número fiscal','internal':'Internos / muestras'}.get(args.get('scope','all'),'Todos')+' | Estado: '+str(args.get('status') or 'Todos')+' | Modalidad: '+str(args.get('type') or 'Todas')+' | Pago: '+str(args.get('payment') or 'Todos')
def now():return datetime.now().astimezone().isoformat(timespec='seconds')

def format_cash_datetime(value):
 if not value:return '—'
 try:
  date=datetime.fromisoformat(str(value).replace('Z','+00:00'))
  date=date.replace(tzinfo=cash_safety.HONDURAS) if date.tzinfo is None else date.astimezone(cash_safety.HONDURAS)
 except (ValueError,TypeError):return 'FECHA NO DISPONIBLE'
 months=('ENERO','FEBRERO','MARZO','ABRIL','MAYO','JUNIO','JULIO','AGOSTO','SEPTIEMBRE','OCTUBRE','NOVIEMBRE','DICIEMBRE')
 return f"{date.day:02d} {months[date.month-1]} {date.year} · {date.hour%12 or 12:02d}:{date.minute:02d}:{date.second:02d} {'AM' if date.hour<12 else 'PM'}"

def actor():return ((session['cashier_full_name']+' [Empleado #'+str(session['cashier_id'])+']') if session.get('cashier_id') else session.get('email') or session.get('role','sistema'))+' · '+terminals.terminal_name()

def audit(c,event,entity,detail):c.execute('INSERT INTO audit(created_at,actor,event,entity,detail) VALUES(?,?,?,?,?)',(now(),actor(),event,str(entity),json.dumps(detail,ensure_ascii=False)))
def init(c):
 c.executescript('''CREATE TABLE IF NOT EXISTS accountants(id INTEGER PRIMARY KEY,email TEXT UNIQUE NOT NULL,password TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1,version INTEGER NOT NULL DEFAULT 1,must_change INTEGER NOT NULL DEFAULT 1);
 CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,created_at TEXT,actor TEXT,event TEXT,entity TEXT,detail TEXT);
 CREATE TABLE IF NOT EXISTS cash_sessions(id INTEGER PRIMARY KEY,branch_id INTEGER REFERENCES branches(id),opened_by TEXT,opened_at TEXT,opening INTEGER,status TEXT DEFAULT 'ABIERTA',closed_by TEXT,closed_at TEXT,counted INTEGER,expected INTEGER,difference INTEGER);

 CREATE TABLE IF NOT EXISTS cash_movements(id INTEGER PRIMARY KEY,session_id INTEGER REFERENCES cash_sessions(id),kind TEXT,amount INTEGER,concept TEXT,reference TEXT,actor TEXT,created_at TEXT);''')
 cols=[r['name'] for r in c.execute('PRAGMA table_info(invoices)')]
 for name,typ in [('cash_session_id','INTEGER REFERENCES cash_sessions(id)'),('void_reason','TEXT'),('void_actor','TEXT'),('void_at','TEXT')]:
  if name not in cols:c.execute(f'ALTER TABLE invoices ADD COLUMN {name} {typ}')
def valid_account(c):
 if session.get('role')=='local':
  employee=c.execute('SELECT active,version FROM employees WHERE id=?',(session.get('cashier_id'),)).fetchone()
  return bool(employee and employee['active'] and employee['version']==session.get('cashier_version') and employee_sessions.valid(c,session))
 if session.get('role')!='accountant':return True
 a=c.execute('SELECT * FROM accountants WHERE id=?',(session.get('accountant_id'),)).fetchone()
 return bool(a and a['active'] and a['version']==session.get('accountant_version'))
def account_state(c):
 if session.get('role')!='accountant':return {}
 a=c.execute('SELECT email,must_change FROM accountants WHERE id=?',(session['accountant_id'],)).fetchone();return dict(email=a['email'],must_change=bool(a['must_change']))
def payments(r,s):
 if 'payments' in s:return s['payments']
 p={'Efectivo':0,'Transferencia':0,'Tarjeta':0,'Otros':0};p[r['payment_method'] if r['payment_method'] in p else 'Otros']=r['total'];return p

def book(c,args):
 args=dict(args)|{'scope':'fiscal'}
 if session.get('role')=='accountant':args=dict(args)|{'scope':'fiscal'}
 where=[];vals=[]
 if args.get('branch_id') and args['branch_id']!='all':where.append('i.branch_id=?');vals.append(int(args['branch_id']))
 for key,op in [('start','>='),('end','<=')]:
  if args.get(key):datetime.strptime(args[key],'%Y-%m-%d');where.append(f'substr(i.created_at,1,10){op}?');vals.append(args[key])
 if args.get('start') and args.get('end') and args['start']>args['end']:raise ValueError('La fecha inicial supera a la final')
 if args.get('type') in ['NORMAL','RTN']:where.append('i.invoice_type=?');vals.append(args['type'])
 if args.get('status') in ['EMITIDA','ANULADA']:where.append('i.status=?');vals.append(args['status'])
 scope=args.get('scope','all')
 if scope=='fiscal':where.append('i.fiscal_number IS NOT NULL')
 if scope=='internal':where.append('i.fiscal_number IS NULL')
 records=c.execute('SELECT i.*,b.name branch_name FROM invoices i JOIN branches b ON b.id=i.branch_id'+(' WHERE '+' AND '.join(where) if where else '')+' ORDER BY i.created_at,i.id',vals).fetchall()
 rows=[];details=[];totals={k:0 for k in ['subtotal','tax_15','tax_18','discount','total','exempt','exempted','taxable_15','taxable_18','Efectivo','Transferencia','Tarjeta','Otros','delivery_fee','collected_total']};incomplete=0
 for record in records:
  r=dict(record);s=json.loads(r.pop('snapshot') or '{}');p=payments(r,s)
  r['delivery_fee']=s.get('delivery_fee',r.get('delivery_fee',0)) or 0;r['sales_total']=r['total']-r['delivery_fee'];r['collected_total']=r['total'];r['sales_payments'],r['delivery_payments']=delivery.split_payments(p,r['delivery_fee'])
  if args.get('payment') and p.get(args['payment'],0)<=0:continue
  r.update(terminal_name=terminals.pc_labels.name(r.get('terminal_id',0)),cashier_id=s.get('cashier_id'),extra=s.get('extra',{}),payments=p,cai=s.get('fiscal',{}).get('cai','') if r['fiscal_number'] else '',deadline=s.get('fiscal',{}).get('deadline',''),range_start=s.get('fiscal',{}).get('range_start',''),range_end=s.get('fiscal',{}).get('range_end',''),cashier=s.get('cashier',''),price_mode=s.get('price_mode','HISTÓRICO'),discount_type=s.get('discount_type','AMOUNT'),discount_rate=s.get('discount_rate',''),quality='Completo' if 'taxable_15' in s else 'Desglose histórico incompleto')
  for k in ['exempt','exempted','taxable_15','taxable_18']:r[k]=s.get(k)
  if r['quality']!='Completo':incomplete+=1
  if r['status']=='EMITIDA':
   for k in totals:totals[k]+=p.get(k,0) if k in p else (r['sales_total'] if k=='total' else (r.get(k) or 0))
  rows.append(r)
  for item in s.get('items',[]):details.append(dict(invoice_id=r['id'],number=r['fiscal_number'] or str(r['number']),status=r['status'],name=item['name'],quantity=item['quantity'],unit_price=item['price'],line_total=item['line_total'],line_discount=item.get('line_discount'),tax_type=item['tax_type']))
 return dict(invoices=rows,items=details,totals=totals,count=len(rows),issued=sum(r['status']=='EMITIDA' for r in rows),voided=sum(r['status']=='ANULADA' for r in rows),incomplete=incomplete,filters=dict(args),generated_at=now())

def visible_shift(c,row):
 # Un cierre sin operaciones restantes no debe reaparecer tras borrar las pruebas.
 if row['status']!='CERRADA':return True
 sid=row['id']
 return any(c.execute('SELECT 1 FROM '+table+' WHERE '+column+'=? LIMIT 1',(sid,)).fetchone() for table,column in [('invoices','cash_session_id'),('cash_movements','session_id'),('special_orders','cash_session_id'),('employee_meals','cash_session_id')])

def shift_summary(c,row):
 r=dict(row);r['must_close']=r['status']=='ABIERTA' and cash_safety.must_close(r);r['business_date']=cash_safety.business_date(r['opened_at']);r['terminal_name']=terminals.pc_labels.name(r.get('terminal_id',0));r['cash_number']=terminals.pc_labels.number(r.get('terminal_id',0));ps={'Efectivo':0,'Transferencia':0,'Tarjeta':0,'Otros':0};sales=0
 for x in c.execute("SELECT * FROM invoices WHERE cash_session_id=? AND status='EMITIDA'",(r['id'],)):
  sales+=x['total']-(x['delivery_fee'] or 0)
  for k,v in payments(x,json.loads(x['snapshot'] or '{}')).items():ps[k]=ps.get(k,0)+v
 r['mixed_total']=c.execute("SELECT COALESCE(SUM(total),0) FROM invoices WHERE cash_session_id=? AND status='EMITIDA' AND payment_method='Mixto'",(r['id'],)).fetchone()[0]
 correction=c.execute("SELECT id,created_at,actor,detail FROM audit WHERE event='RECTIFICACION_CIERRE' AND entity=? ORDER BY id DESC LIMIT 1",(str(r['id']),)).fetchone()
 r['correction']=dict(json.loads(correction['detail']),revision=correction['id'],at=correction['created_at'],actor=correction['actor']) if correction else None
 movements=[dict(x) for x in c.execute('SELECT * FROM cash_movements WHERE session_id=? ORDER BY id',(r['id'],))]
 ins=sum(m['amount'] for m in movements if m['kind']=='INGRESO');outs=sum(m['amount'] for m in movements if m['kind']=='EGRESO')
 special=c.execute("SELECT COUNT(*),COALESCE(SUM(json_extract(snapshot,'$.total')),0) FROM special_orders WHERE cash_session_id=?",(r['id'],)).fetchone()
 r.update(special_count=special[0],special_value=special[1],payments=ps,sales=sales,inputs=ins,outputs=outs,live_expected=r['opening']+ps['Efectivo']+ins-outs,movements=movements);return r

# Presentation uses the same already-calculated ledger as the screen; it does not recalculate taxes.
def tables(data,extras):
 rows=data['invoices'];amount=lambda x:None if x is None else Decimal(x)/100
 ledger=[['Fecha','Sucursal','Factura','Modalidad','Cliente','RTN','Estado','CAI','Límite','Rango inicial','Rango final','Exento L','Exonerado L','Base 15 L','Base 18 L','Subtotal neto L','ISV 15 L','ISV 18 L','Descuento L','Total factura con envío L','Envío cobrado L','Venta de productos L','Efectivo L','Transferencia L','Tarjeta L','Otros L','Turno','Motivo anulación','Responsable anulación','Fecha anulación','Calidad','Orden compra exenta','Constancia exoneración','Registro SAG']]
 for r in rows:ledger.append([r['created_at'],r['branch_name'],r['fiscal_number'] or 'INTERNO-'+str(r['number']),r['invoice_type'],r['customer_name'],r['customer_rtn'],r['status'],r['cai'],r['deadline'],r['range_start'],r['range_end'],*[amount(r[k]) for k in ['exempt','exempted','taxable_15','taxable_18','subtotal','tax_15','tax_18','discount','total']],amount(r['delivery_fee']),amount(r['sales_total']),*[amount(r['payments'].get(k,0)) for k in ['Efectivo','Transferencia','Tarjeta','Otros']],r['cash_session_id'],r['void_reason'],r['void_actor'],r['void_at'],r['quality'],r['extra'].get('purchase_order',''),r['extra'].get('exemption_certificate',''),r['extra'].get('sag','')])
 summary=[['Concepto','Importe / cantidad'],['Facturas consultadas',data['count']],['Emitidas',data['issued']],['Anuladas',data['voided']],['Desglose histórico incompleto',data['incomplete']]]+[[label(k),amount(v)] for k,v in data['totals'].items()]
 detail=[['Factura','Estado','Producto (histórico)','Cantidad','Precio L','Importe línea L','Descuento línea L','Clasificación']]+[[r['number'],r['status'],r['name'],r['quantity'],amount(r['unit_price']),amount(r['line_total']),amount(r['line_discount']),r['tax_type']] for r in data['items']]
 shifts=[['Turno','Sucursal ID','Apertura','Responsable','Estado','Inicial L','Ventas L','Efectivo L','Transferencia L','Tarjeta L','Ingresos L','Egresos L','Esperado L','Contado L','Diferencia L','Cierre']]
 for r in extras['shifts']:shifts.append([r['id'],r['branch_id'],r['opened_at'],r['opened_by'],r['status'],*[amount(r[k]) for k in ['opening','sales']],*[amount(r['payments'].get(k,0)) for k in ['Efectivo','Transferencia','Tarjeta']],amount(r['inputs']),amount(r['outputs']),amount(r['expected'] if r['status']=='CERRADA' else r['live_expected']),amount(r['counted']),amount(r['difference']),r['closed_at']])
 moves=[['Turno','Fecha','Tipo','Concepto','Referencia','Responsable','Importe L']]+[[s['id'],m['created_at'],m['kind'],m['concept'],m['reference'],m['actor'],amount(m['amount'])] for s in extras['shifts'] for m in s['movements']]
 auditrows=[['Fecha','Responsable','Acción','Entidad','Detalle']]+[[r[k] for k in ['created_at','actor','event','entity','detail']] for r in extras['audit']]
 clients=[['RTN','Nombre']]+[[r['rtn'],r['name']] for r in extras['customers']]
 authorizations=[['Sucursal','Razón social','RTN emisor','CAI','Estado','Establecimiento','Punto','Inicio','Fin','Siguiente','Fecha límite','Precios']]+[[r[k] for k in ['branch_name','legal_name','rtn','cai','enabled','establishment','point','range_start','range_end','next_number','deadline','price_mode']] for r in extras['authorizations']]
 return [('Resumen',summary),('Autorizaciones',authorizations),('Libro de ventas',ledger),('Detalle histórico',detail),('Turnos',shifts),('Movimientos de caja',moves),('Auditoría',auditrows),('Clientes RTN',clients)]

def export_excel(data,extras):
 from openpyxl import Workbook
 from openpyxl.styles import Font,PatternFill,Alignment
 from openpyxl.utils import get_column_letter
 wb=Workbook();wb.remove(wb.active)
 for name,grid in tables(data,extras):
  ws=wb.create_sheet(name);ws.append(['FRY CHICKEN · Contabilidad']);ws.append(['Filtros: '+filter_text(data['filters'])]);ws.append(['Importes originales; resumen suma solo EMITIDAS. Vacío = dato histórico no disponible.']);ws.append([])
  for row in grid:
   ws.append(row)
   for cell,value in zip(ws[ws.max_row],row):
    if isinstance(value,str):cell.data_type='s' # User strings must never become spreadsheet formulas.
    if isinstance(value,Decimal):cell.number_format='#,##0.00;[Red](#,##0.00)'
  for cell in ws[5]:cell.fill=PatternFill('solid',fgColor='183B45');cell.font=Font(color='FFFFFF',bold=True);cell.alignment=Alignment(wrap_text=True)
  ws.row_dimensions[5].height=32;ws.freeze_panes='A6';ws.auto_filter.ref=f'A5:{get_column_letter(len(grid[0]))}{ws.max_row}'
  for col in range(1,len(grid[0])+1):ws.column_dimensions[get_column_letter(col)].width=min(42,max(16,len(str(grid[0][col-1]))+3))
  ws.print_title_rows='1:5';ws.sheet_properties.pageSetUpPr.fitToPage=True;ws.page_setup.orientation='landscape';ws.page_setup.paperSize=ws.PAPERSIZE_A3;ws.page_setup.fitToWidth=1;ws.page_setup.fitToHeight=0
 out=io.BytesIO();wb.save(out);out.seek(0);return out

def export_pdf(data,extras):
 from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak
 from reportlab.lib import colors
 from reportlab.lib.styles import getSampleStyleSheet
 from reportlab.lib.pagesizes import A4,landscape
 from xml.sax.saxutils import escape
 out=io.BytesIO();styles=getSampleStyleSheet();style=styles['BodyText'];style.fontSize=8;style.leading=10
 doc=SimpleDocTemplate(out,pagesize=landscape(A4),leftMargin=25,rightMargin=25,topMargin=28,bottomMargin=28)
 story=[Paragraph('FRY CHICKEN · Reporte contable',styles['Title']),Paragraph(escape(filter_text(data['filters'])),style),Paragraph('Importes en lempiras. Los totales excluyen anuladas. Las muestras se identifican como internas. Datos históricos no disponibles se dejan en blanco.',style),Spacer(1,12)]
 def add(title,grid,widths):
  story.append(Paragraph(title,styles['Heading2']))
  cells=[[Paragraph(escape('' if v is None else f'{v:,.2f}' if isinstance(v,Decimal) else str(v)),style) for v in row] for row in grid]
  table=Table(cells,colWidths=widths,repeatRows=1,hAlign='LEFT');table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e6edf0')),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),.5,colors.grey),('BOTTOMPADDING',(0,0),(-1,-1),4),('TOPPADDING',(0,0),(-1,-1),4)]));story.append(table);story.append(Spacer(1,12))
 def paired(grid):
  rows=grid[1:];return [grid[0]+grid[0]]+[rows[i]+(rows[i+1] if i+1<len(rows) else ['','']) for i in range(0,len(rows),2)]
 grids=dict(tables(data,extras));add('Resumen · solo emitidas',grids['Resumen'],[260,200])
 # Keep invoice-level fiscal fields legible rather than shrinking a 29-column table.
 for r in data['invoices']:
  story.append(PageBreak());story.append(Paragraph(escape((r['fiscal_number'] or 'INTERNO-'+str(r['number']))+' · '+r['status']),styles['Heading1']))
  meta=[['Campo','Valor'],['Sucursal / fecha',r['branch_name']+' / '+r['created_at']],['Cliente / RTN',r['customer_name']+' / '+r['customer_rtn']],['CAI / vencimiento',r['cai']+' / '+r['deadline']],['Rango',str(r['range_start'])+' — '+str(r['range_end'])],['Turno / caja',str(r['cash_session_id'] or 'Sin turno')+' / '+r['cashier']],['Anulación',str(r['void_reason'] or '')+' / '+str(r['void_actor'] or '')],['Calidad',r['quality']],['Orden compra exenta',r['extra'].get('purchase_order','')],['Constancia exoneración / SAG',r['extra'].get('exemption_certificate','')+' / '+r['extra'].get('sag','')]];add('Datos de la operación',paired(meta),[100,270,100,270])
  add('Importes originales', paired([['Concepto','Lempiras']]+[[label(k),Decimal(r[k])/100 if r.get(k) is not None else None] for k in ['exempt','exempted','taxable_15','taxable_18','subtotal','tax_15','tax_18','discount','total']]+[[k,Decimal(v)/100] for k,v in r['payments'].items()]),[180,190,180,190])
  add('Detalle histórico',[grids['Detalle histórico'][0]]+[row for row,it in zip(grids['Detalle histórico'][1:],data['items']) if it['invoice_id']==r['id']],[100,60,220,45,65,80,85,85])
 for name in ['Autorizaciones','Turnos','Movimientos de caja','Auditoría','Clientes RTN']:
  
  if name=='Autorizaciones':story.append(PageBreak())
  grid=grids[name]
  if name in ['Turnos','Autorizaciones']:
   for row in grid[1:]:add(('Turno ' if name=='Turnos' else 'Autorización ')+str(row[0]),[['Campo','Valor']]+list(map(list,zip(grid[0],row))),[200,540])
   if len(grid)==1:story.append(Paragraph('Sin turnos en el período.',style))
  else:add(name,grid,[740/len(grid[0])]*len(grid[0]))
 def page(canvas,document):canvas.setFont('Helvetica',8);canvas.drawString(25,15,'FRY Chicken · '+data['generated_at']);canvas.drawRightString(815,15,str(document.page))
 doc.build(story,onFirstPage=page,onLaterPages=page);out.seek(0);return out

def register(app,connect,money):
 @app.route('/api/admin/accountants',methods=['GET','POST'])
 @app.patch('/api/admin/accountants/<int:uid>')
 def accounts(uid=None):
  with connect() as c:
   if request.method!='GET':
    d=request.json;email=str(d.get('email','')).strip().lower();password=str(d.get('password',''))
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email):raise ValueError('Correo inválido')
    if password and len(password)<8:raise ValueError('La contraseña requiere al menos 8 caracteres')
    if uid:
     old=c.execute('SELECT * FROM accountants WHERE id=?',(uid,)).fetchone()
     if not old:raise ValueError('Cuenta no encontrada')
     c.execute('UPDATE accountants SET email=?,active=?,password=?,must_change=?,version=version+1 WHERE id=?',(email,int(d.get('active',True)),generate_password_hash(password) if password else old['password'],1 if password else old['must_change'],uid));event='CUENTA_CONTADOR_ACTUALIZADA'
    else:
     if len(password)<8:raise ValueError('Introduce una contraseña temporal de al menos 8 caracteres')
     uid=c.execute('INSERT INTO accountants(email,password) VALUES(?,?)',(email,generate_password_hash(password))).lastrowid;event='CUENTA_CONTADOR_CREADA'
    audit(c,event,uid,dict(email=email))
   return jsonify([dict(r) for r in c.execute('SELECT id,email,active,must_change FROM accountants ORDER BY email')])
 @app.post('/api/auth/password')
 def own_password():
  if session.get('role')!='accountant':return jsonify(error='Acceso de contador requerido'),403
  d=request.json;password=str(d.get('password',''))
  if len(password)<8:raise ValueError('La contraseña requiere al menos 8 caracteres')
  with connect() as c:
   a=c.execute('SELECT * FROM accountants WHERE id=?',(session['accountant_id'],)).fetchone()
   if not check_password_hash(a['password'],str(d.get('current_password',''))):raise ValueError('Contraseña actual incorrecta')
   if check_password_hash(a['password'],password):raise ValueError('Elige una contraseña diferente')
   c.execute('UPDATE accountants SET password=?,must_change=0,version=version+1 WHERE id=?',(generate_password_hash(password),a['id']));session['accountant_version']=a['version']+1;audit(c,'CAMBIO_CLAVE_CONTADOR',a['id'],{})
  return jsonify(ok=True)
 def extra(c,args):
  if session.get('role')!='admin':return dict(authorizations=[],shifts=[],audit=[],customers=[])
  shifts=[]
  for r in c.execute('SELECT * FROM cash_sessions ORDER BY id DESC'):
   if not visible_shift(c,r):continue
   if args.get('branch_id') not in [None,'','all'] and r['branch_id']!=int(args['branch_id']):continue
   # Turnos que se solapan con el período consultado, no solo abiertos ese día.
   if args.get('end') and r['opened_at'][:10]>args['end']:continue
   if args.get('start') and r['closed_at'] and r['closed_at'][:10]<args['start']:continue
   shifts.append(shift_summary(c,r))
  logs=[dict(r) for r in c.execute('SELECT * FROM audit ORDER BY id DESC') if (not args.get('start') or r['created_at'][:10]>=args['start']) and (not args.get('end') or r['created_at'][:10]<=args['end'])]
  configs=[dict(branch_id=r['id'],branch_name=r['name'],**fiscal.config(c,r['id'])) for r in c.execute('SELECT id,name FROM branches') if args.get('branch_id') in [None,'','all'] or r['id']==int(args['branch_id'])]
  return dict(authorizations=configs,shifts=shifts,audit=logs,customers=[dict(r) for r in c.execute('SELECT * FROM customers ORDER BY name')])
 @app.get('/api/accounting')
 def report():
  with connect() as c:
   c.execute('BEGIN');data=book(c,request.args);data.update(extra(c,request.args));return jsonify(data)
 @app.get('/api/accounting/export/<kind>')
 def export(kind):
  if kind not in ['pdf','xlsx','print']:raise ValueError('Formato no admitido')
  with connect() as c:
   c.execute('BEGIN');data=book(c,request.args);extras=extra(c,request.args)
  if kind=='print':return render_template('accounting_print.html',data=data,extras=extras,label=label,filters_text=filter_text(data['filters']),fmt=lambda n:f'{Decimal(n)/100:,.2f}')
  output=export_excel(data,extras) if kind=='xlsx' else export_pdf(data,extras)
  with connect() as c:audit(c,'EXPORTACION_CONTABLE',kind,dict(filters=dict(request.args),rows=data['count']))
  return send_file(output,as_attachment=True,download_name='FRY-Contabilidad-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.'+kind,mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' if kind=='xlsx' else 'application/pdf')
 @app.get('/api/cash/<int:sid>/pdf')
 def cash_pdf(sid):
  with connect() as c:
   r=c.execute('SELECT * FROM cash_sessions WHERE id=?',(sid,)).fetchone()
   if not r:return jsonify(error='Caja no encontrada'),404
   if session['role']=='local' and (r['branch_id']!=session.get('branch_id') or r['terminal_id']!=terminals.terminal_id()):return jsonify(error='Caja de otra sucursal o terminal'),403
   row=shift_summary(c,r);b=c.execute('SELECT name FROM branches WHERE id=?',(r['branch_id'],)).fetchone()
  from reportlab.pdfgen import canvas
  output=io.BytesIO();pdf=canvas.Canvas(output,pagesize=(595,842));y=800
  def line(text):
   nonlocal y
   if y<45:pdf.showPage();y=800
   pdf.setFont('Helvetica',11);pdf.drawString(36,y,str(text)[:100]);y-=20
  money_text=lambda n:f'L {n/100:,.2f}'
  line('FRY CHICKEN - CIERRE DE CAJA' if row['status']=='CERRADA' else 'FRY CHICKEN - CAJA ABIERTA')
  line(b['name']);line(row['terminal_name']);line(f"CAJA #{row['cash_number']} - {row['status']}");line('Apertura: '+format_cash_datetime(row['opened_at']));line('Responsable: '+row['opened_by'])
  if row['closed_at']:line('Cierre: '+format_cash_datetime(row['closed_at']));line('Cerrada por: '+row['closed_by'])
  line('RESUMEN DE CIERRE')
  line('Venta de productos: '+money_text(row['sales']))
  line('Fondo inicial: '+money_text(row['opening']))
  for label,value in row['payments'].items():
   if value>0:line(label+': '+money_text(value))
  line('Total cobrado: '+money_text(sum(row['payments'].values())))
  if row['mixed_total']>0:line('Pagos mixtos (ya incluidos por medio): '+money_text(row['mixed_total']))
  if row.get('correction'):
   line('CIERRE RECTIFICADO - '+format_cash_datetime(row['correction']['at']))
   line('Motivo: '+row['correction']['reason'])
   line('Contado anterior: '+money_text(row['correction']['previous_counted']))
  for label,value in [('Otras entradas de efectivo (+)',row['inputs']),('Salidas de efectivo (-)',row['outputs'])]:
   if value:line(label+': '+money_text(value))
  line('Efectivo que debe haber en caja: '+money_text(row['expected'] if row['status']=='CERRADA' else row['live_expected']))
  if row['status']=='CERRADA':
   line('Efectivo fisico contado: '+money_text(row['counted']))
   line(('Sobrante' if row['difference']>0 else 'Faltante' if row['difference']<0 else 'Diferencia - caja cuadrada')+': '+money_text(abs(row['difference'])))
  line('Tarjetas y transferencias no forman parte del efectivo fisico.')
  line(f"Registros especiales sin cobro: {row['special_count']} - valor de referencia: {money_text(row['special_value'])}")
  for m in row['movements']:line(m['kind']+' - '+m['concept']+' - '+money_text(m['amount']))
  pdf.save();output.seek(0);return send_file(output,as_attachment=True,download_name=f"Cierre-caja-{row['cash_number']}-turno-{sid}.pdf",mimetype='application/pdf')
 @app.route('/api/cash',methods=['GET','POST'])
 def cash():
  with connect() as c:
   if request.method=='POST':
    d=request.json;branch=int(d.get('branch_id',0));actor_branch=session.get('branch_id') if session.get('role')=='local' else json.loads(c.execute("SELECT value FROM settings WHERE key='auth'").fetchone()[0])['branch_id']
    if session['role']=='local' and branch!=actor_branch:return jsonify(error='Sucursal no asignada'),403
    c.execute('BEGIN IMMEDIATE')
    if not c.execute('SELECT 1 FROM branches WHERE id=? AND active=1',(branch,)).fetchone():raise ValueError('Sucursal no disponible')
    action=d.get('action');r=c.execute("SELECT * FROM cash_sessions WHERE branch_id=? AND terminal_id=? AND status='ABIERTA'",(branch,terminals.terminal_id())).fetchone()
    if action=='open':
     cash_safety.require_closed(c,terminals.terminal_id())
     if r:raise ValueError('Ya hay un turno abierto')
     cur=c.execute('INSERT INTO cash_sessions(branch_id,terminal_id,cashier_id,opened_by,opened_at,opening) VALUES(?,?,?,?,?,?)',(branch,terminals.terminal_id(),session.get('cashier_id'),actor(),now(),money(d.get('opening',0))));audit(c,'APERTURA_CAJA',cur.lastrowid,dict(branch_id=branch));r=c.execute('SELECT * FROM cash_sessions WHERE id=?',(cur.lastrowid,)).fetchone()
    elif action=='movement':
     if not r:raise ValueError('Abre un turno primero')
     kind=d.get('kind');concept=str(d.get('concept','')).strip();amount=money(d.get('amount',0))
     if kind not in ['INGRESO','EGRESO'] or not 3<=len(concept)<=200 or amount<=0:raise ValueError('Completa tipo, concepto e importe positivo')
     c.execute('INSERT INTO cash_movements(session_id,kind,amount,concept,reference,actor,created_at) VALUES(?,?,?,?,?,?,?)',(r['id'],kind,amount,concept,str(d.get('reference',''))[:100],actor(),now()));audit(c,'MOVIMIENTO_CAJA',r['id'],dict(kind=kind,amount=amount,concept=concept))
    elif action=='close':
     if not r:raise ValueError('No hay turno abierto')
     if d.get('shift_id') is None or int(d['shift_id'])!=r['id']:raise ValueError('La caja cambió. Vuelve a abrir la ventana de cierre.')
     if 'counted' not in d:raise ValueError('Indica el efectivo contado')
     expected=shift_summary(c,r)['live_expected'];counted=money(d.get('counted',0));c.execute("UPDATE cash_sessions SET status='CERRADA',closed_by=?,closed_at=?,counted=?,expected=?,difference=? WHERE id=?",(actor(),now(),counted,expected,counted-expected,r['id']));audit(c,'CIERRE_CAJA',r['id'],dict(expected=expected,counted=counted,difference=counted-expected))
    else:raise ValueError('Acción inválida')
   branch=int(request.args.get('branch_id',(request.get_json(silent=True) or {}).get('branch_id',1)))
   if session['role']=='local':branch=session.get('branch_id')
   r=c.execute("SELECT * FROM cash_sessions WHERE branch_id=? AND terminal_id=? AND status='ABIERTA'",(branch,terminals.terminal_id())).fetchone();closed=c.execute("SELECT * FROM cash_sessions WHERE branch_id=? AND terminal_id=? AND status='CERRADA' ORDER BY id DESC LIMIT 1",(branch,terminals.terminal_id())).fetchone();return jsonify(shift=shift_summary(c,r) if r else None,last_closed=shift_summary(c,closed) if closed else None)

