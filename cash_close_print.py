"""Impresión explícita del cierre guardado mediante la impresora central de caja."""
import uuid
from decimal import Decimal
from flask import request,jsonify,session,render_template
import accounting,print_queue,terminals

def register(app,connect):
 @app.post('/api/cash/<int:sid>/print')
 def print_cash_close(sid):
  if session.get('role') not in ['admin','local']:return jsonify(error='Acceso no permitido'),403
  data=request.json or {};key=str(data.get('request_id',''))
  try:uuid.UUID(key)
  except (ValueError,AttributeError):raise ValueError('Identificador de impresión inválido')
  copy=data.get('copy') is True
  with connect() as c:
   c.execute('BEGIN IMMEDIATE');record=c.execute('SELECT * FROM cash_sessions WHERE id=?',(sid,)).fetchone()
   if not record:return jsonify(error='Caja no encontrada'),404
   if session['role']=='local' and (record['branch_id']!=session.get('branch_id') or record['terminal_id']!=terminals.terminal_id()):return jsonify(error='Cierre de otra sucursal o PC'),403
   if record['status']!='CERRADA':raise ValueError('Primero cuenta el efectivo y guarda el cierre de caja')
   request_key='CASH_CLOSE:'+str(terminals.terminal_id())+':'+str(sid)+':'+key
   previous=c.execute('SELECT job_id FROM print_requests WHERE request_key=?',(request_key,)).fetchone()
   if previous:
    job=c.execute('SELECT * FROM print_jobs WHERE id=?',(previous['job_id'],)).fetchone()
    if job['state'] in ['PAUSED','FAILED']:
     c.execute("UPDATE print_jobs SET state='PENDING',last_error='',updated_at=? WHERE id=?",(accounting.now(),job['id']))
     return jsonify(id=job['id'],state='PENDING',is_copy=bool(job['is_copy']),queued=True)
    return jsonify(id=job['id'],state=job['state'],is_copy=bool(job['is_copy']),queued=True)
   original=c.execute("SELECT * FROM print_jobs WHERE source_kind='CASH_CLOSE' AND source_id=? AND is_copy=0 ORDER BY id LIMIT 1",(sid,)).fetchone()
   waiting=c.execute("SELECT * FROM print_jobs WHERE source_kind='CASH_CLOSE' AND source_id=? AND state IN ('PENDING','CLAIMED','SPOOLING','PAUSED','FAILED') ORDER BY is_copy,id LIMIT 1",(sid,)).fetchone()
   if not waiting and not copy and original and original['state'] in ['SPOOLED','UNCERTAIN']:
    return jsonify(needs_copy=True,message='Este cierre ya se envió o tiene un envío dudoso. Revisa el papel. ¿Quieres imprimir una copia?')
   if waiting:
    jid=waiting['id']
    if waiting['state'] in ['PAUSED','FAILED']:c.execute("UPDATE print_jobs SET state='PENDING',last_error='',updated_at=? WHERE id=?",(accounting.now(),jid))
   else:
    if not original:copy=False
    row=accounting.shift_summary(c,record);branch=c.execute('SELECT name FROM branches WHERE id=?',(record['branch_id'],)).fetchone()
    if row.get('correction'):copy=True
    html=render_template('cash_close.html',r=row,branch=branch,copy=copy,fmt=lambda n:f'L {Decimal(n)/100:,.2f}',format_cash_datetime=accounting.format_cash_datetime)
    origin=request_key if copy else 'ORIGINAL:CASH_CLOSE:'+str(sid)
    jid=print_queue.enqueue(c,'cash','CASH_CLOSE',sid,record['branch_id'],html,origin,copy)
    c.execute("UPDATE print_jobs SET state='PENDING',terminal_id=? WHERE id=?",(record['terminal_id'],jid))
   c.execute('INSERT INTO print_requests(request_key,job_id) VALUES(?,?)',(request_key,jid))
   accounting.audit(c,'IMPRESION_CIERRE_CAJA',sid,dict(job_id=jid,copy=copy))
   job=c.execute('SELECT state,is_copy FROM print_jobs WHERE id=?',(jid,)).fetchone()
   return jsonify(id=jid,state=job['state'],is_copy=bool(job['is_copy']),queued=True)
