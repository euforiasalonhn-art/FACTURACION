import re
from flask import request,session,jsonify
import accounting

def register(app,connect):
 @app.get('/api/invoice-reprint')
 def reprint_lookup():
  if session.get('role') not in ['admin','local']:return jsonify(error='Acceso no permitido'),403
  number=str(request.args.get('number','')).strip()
  if not number or len(number)>60:raise ValueError('Ingresa el número de factura')
  branch=session['branch_id'] if session['role']=='local' else request.args.get('branch_id',type=int)
  with connect() as c:
   fields='id,number,fiscal_number,total,status'
   rows=c.execute('SELECT '+fields+' FROM invoices WHERE branch_id=? AND fiscal_number=?',(branch,number)).fetchall()
   if not rows and re.fullmatch(r'(?:MUESTRA-|INTERNO-)?[0-9]+',number,re.I):
    n=int(number.rsplit('-',1)[-1]);rows=c.execute('SELECT '+fields+' FROM invoices WHERE branch_id=? AND number=?',(branch,n)).fetchall()
    if not rows and len(str(n))<=8:rows=c.execute('SELECT '+fields+" FROM invoices WHERE branch_id=? AND substr(fiscal_number,-8)=?",(branch,str(n).zfill(8))).fetchall()
   if not rows:return jsonify(error='No se encontró esa factura en esta sucursal'),404
   if len(rows)!=1:raise ValueError('Ingresa el número fiscal completo para identificar una sola factura')
   return jsonify(dict(rows[0]))
 @app.post('/api/invoice-reprint/<int:i>/request')
 def reprint_request(i):
  if session.get('role') not in ['admin','local']:return jsonify(error='Acceso no permitido'),403
  with connect() as c:
   row=c.execute('SELECT id,branch_id,number FROM invoices WHERE id=?',(i,)).fetchone()
   if not row:return jsonify(error='Factura no encontrada'),404
   if session['role']=='local' and row['branch_id']!=session['branch_id']:return jsonify(error='Factura de otra sucursal'),403
   accounting.audit(c,'REIMPRESION_SOLICITADA',i,dict(number=row['number'],copy='COPIA'))
  return jsonify(ok=True)
