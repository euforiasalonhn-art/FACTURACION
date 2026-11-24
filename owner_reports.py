"""Reportes del propietario basados en los comprobantes históricos."""
import io,json
from collections import defaultdict
from decimal import Decimal
from html import escape
from flask import request,session,jsonify,Response,send_file
import accounting

def amount(value):return f'{Decimal(value)/100:,.2f}'

def build(c,kind,args):
 data=accounting.book(c,args);rows=[r for r in data['invoices'] if r['status']=='EMITIDA']
 if kind=='ventas':
  headers=['Medio','Factura','Fecha','Cliente','Efectivo L','Tarjeta L','Transferencia L','Otros L','Total L']
  result=[]
  for r in rows:
   p=r['payments'];active=[k for k,v in p.items() if v]
   result.append([active[0] if len(active)==1 else 'MIXTO',r['fiscal_number'] or str(r['number']),r['created_at'],r['customer_name'],*[amount(p.get(k,0)) for k in ['Efectivo','Tarjeta','Transferencia','Otros']],amount(r['total'])])
  result.sort(key=lambda r:(r[0],r[2],r[1]))
  result.append(['TOTAL','','','',*[amount(sum(r['payments'].get(k,0) for r in rows)) for k in ['Efectivo','Tarjeta','Transferencia','Otros']],amount(sum(r['total'] for r in rows))])
  return 'REPORTE DE VENTAS',headers,result
 if kind=='productos':
  grouped=defaultdict(lambda:[0,0,0,0]);missing=0
  for r in rows:
   snap=json.loads(c.execute('SELECT snapshot FROM invoices WHERE id=?',(r['id'],)).fetchone()[0] or '{}')
   for item in snap.get('items',[]):
    key=(item.get('category','Sin categoría histórica'),item['name'],item['price'])
    g=grouped[key];g[0]+=item['quantity'];g[1]+=item['price']*item['quantity'];g[2]+=item.get('line_discount') or 0;g[3]+=item['line_total']
  result=[]
  for (category,name,price),g in sorted(grouped.items()):result.append([category,name,str(g[0]),amount(price),amount(g[1]),amount(g[2]),amount(g[3])])
  result.append(['TOTAL','',str(sum(g[0] for g in grouped.values())),'',*[amount(sum(g[i] for g in grouped.values())) for i in [1,2,3]]])
  return 'VENTAS POR PRODUCTO',['Categoría','Producto','Cantidad','Precio L','Bruto L','Descuento L','Neto L'],result
 if kind=='cierre':
  result=[]
  for raw in c.execute('SELECT * FROM cash_sessions ORDER BY id DESC'):
   if not accounting.visible_shift(c,raw):continue
   r=dict(raw)
   if args.get('branch_id') not in [None,'','all'] and r['branch_id']!=int(args['branch_id']):continue
   if args.get('start') and r['opened_at'][:10]<args['start']:continue
   if args.get('end') and r['opened_at'][:10]>args['end']:continue
   s=accounting.shift_summary(c,raw)
   invoices=c.execute("SELECT COALESCE(fiscal_number,CAST(number AS TEXT)) n FROM invoices WHERE cash_session_id=? ORDER BY id",(r['id'],)).fetchall()
   name=c.execute('SELECT name FROM branches WHERE id=?',(r['branch_id'],)).fetchone()[0]
   for label,value in [('Sucursal',name),('Turno',str(r['id'])),('Responsable apertura',r['opened_by']),('Responsable cierre',r['closed_by'] or ''),('Fecha apertura',r['opened_at']),('Estado',r['status']),('Factura inicial',invoices[0]['n'] if invoices else ''),('Factura final',invoices[-1]['n'] if invoices else ''),('Efectivo apertura',amount(r['opening'])),('Ingreso efectivo',amount(s['payments']['Efectivo'])),('Ingreso tarjeta',amount(s['payments']['Tarjeta'])),('Ingreso transferencia',amount(s['payments']['Transferencia'])),('Otras entradas',amount(s['inputs'])),('Egresos',amount(s['outputs'])),('Efectivo esperado',amount(r['expected'] if r['status']=='CERRADA' else s['live_expected'])),('Efectivo contado',amount(r['counted']) if r['counted'] is not None else ''),('Diferencia',amount(r['difference']) if r['difference'] is not None else '')]:result.append([str(r['id']),label,value])
  return 'CIERRE DE CAJA',['Turno','Concepto','Valor'],result
 raise ValueError('Reporte inválido')

def register(app,connect):
 @app.get('/api/accounting/owner-report/<kind>',endpoint='owner_business_report')
 def report(kind):
  if kind=='cierre' and session.get('role')!='admin':return jsonify(error='Acceso exclusivo de ajustes'),403
  with connect() as c:title,headers,rows=build(c,kind,request.args)
  output=request.args.get('format','json')
  if output=='json':return jsonify(title=title,headers=headers,rows=rows)
  if output=='xlsx':
   from openpyxl import Workbook
   wb=Workbook();ws=wb.active;ws.title='Reporte';ws.append([title]);ws.append(headers)
   for row in rows:
    ws.append(row)
    for cell in ws[ws.max_row]:
     if isinstance(cell.value,str):cell.data_type='s'
   ws.freeze_panes='A3';ws.auto_filter.ref=ws.dimensions
   for col in ws.columns:ws.column_dimensions[col[0].column_letter].width=min(45,max(16,max(len(str(x.value or '')) for x in col)+2))
   stream=io.BytesIO();wb.save(stream);stream.seek(0)
   return send_file(stream,as_attachment=True,download_name=kind+'.xlsx')
  if output=='pdf':
   from reportlab.platypus import SimpleDocTemplate,Table,TableStyle,Paragraph,Spacer
   from reportlab.lib.pagesizes import A4,landscape
   from reportlab.lib.styles import getSampleStyleSheet
   from reportlab.lib import colors
   stream=io.BytesIO();doc=SimpleDocTemplate(stream,pagesize=landscape(A4),leftMargin=22,rightMargin=22)
   styles=getSampleStyleSheet();grid=[[Paragraph(escape(str(x)),styles['BodyText']) for x in row] for row in [headers]+rows]
   table=Table(grid,repeatRows=1);table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.lightgrey),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),.5,colors.grey)]))
   doc.build([Paragraph(title,styles['Title']),Paragraph(escape(str(dict(request.args))),styles['BodyText']),Spacer(1,12),table]);stream.seek(0)
   return send_file(stream,as_attachment=True,download_name=kind+'.pdf',mimetype='application/pdf')
  html='<h1>'+title+'</h1><table border="1" cellspacing="0" cellpadding="7"><thead><tr>'+''.join('<th>'+escape(x)+'</th>' for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+escape(str(x))+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table>'
  return Response('<meta charset="utf-8"><style>body{font:12px Arial}thead{display:table-header-group}table{border-collapse:collapse;width:100%}</style>'+html+'<script>window.print()</script>',mimetype='text/html')
