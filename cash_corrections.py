"""Rectificación autorizada del efectivo contado; nunca altera ventas o medios de pago."""
import json,time,hmac
from flask import request,session,jsonify
import accounting,terminals,cancellation

def register(app,connect,setting,save_setting,money):
 @app.get('/api/cash/corrections')
 def closed_cash():
  if session.get('role') not in ['admin','local']:return jsonify(error='Acceso no permitido'),403
  branch=int(session['branch_id'] if session['role']=='local' else request.args.get('branch_id',0))
  with connect() as c:
   rows=c.execute("SELECT * FROM cash_sessions WHERE status='CERRADA' AND branch_id=? AND terminal_id=? ORDER BY id DESC",(branch,terminals.terminal_id())).fetchall()
   return jsonify([accounting.shift_summary(c,r) for r in rows if accounting.visible_shift(c,r)])

 @app.post('/api/cash/<int:sid>/correct')
 def correct_cash(sid):
  if session.get('role') not in ['admin','local']:return jsonify(error='Acceso no permitido'),403
  d=request.json or {};reason=str(d.get('reason','')).strip()
  if not 5<=len(reason)<=300:raise ValueError('Escribe el motivo de la rectificación (5 a 300 caracteres)')
  if 'counted' not in d:raise ValueError('Indica el efectivo físico contado correcto')
  counted=money(d['counted'])
  if counted<0:raise ValueError('El efectivo contado no puede ser negativo')
  with connect() as c:
   c.execute('BEGIN IMMEDIATE')
   r=c.execute('SELECT * FROM cash_sessions WHERE id=?',(sid,)).fetchone()
   if not r:return jsonify(error='Cierre no encontrado'),404
   if session['role']=='local' and (r['branch_id']!=session.get('branch_id') or r['terminal_id']!=terminals.terminal_id()):return jsonify(error='Cierre de otra caja o sucursal'),403
   if r['status']!='CERRADA':raise ValueError('Solo se puede rectificar un cierre guardado')
   if d.get('previous_counted')!=r['counted']:return jsonify(error='El cierre cambió. Vuelve a consultarlo antes de rectificar'),409
   if counted==r['counted']:raise ValueError('El importe coincide con el cierre actual')
   if c.execute("SELECT 1 FROM print_jobs WHERE source_kind='CASH_CLOSE' AND source_id=? AND state IN ('PENDING','CLAIMED','SPOOLING')",(sid,)).fetchone():return jsonify(error='Espera a que termine la impresión del cierre antes de rectificar'),409
   step=int(time.time()//300);key='cash_correction_attempts:'+str(terminals.terminal_id())
   attempts=setting(c,key,{'step':step,'count':0})
   if attempts['step']!=step:attempts={'step':step,'count':0}
   if attempts['count']>=5:return jsonify(error='Demasiados códigos incorrectos. Espera el siguiente código'),429
   cfg=setting(c,'cancellation_totp')
   if not cfg:return jsonify(error='El administrador debe activar el autenticador en AJUSTES'),409
   if not hmac.compare_digest(str(d.get('code','')),cancellation.totp(cancellation.protect(cfg['secret'],True))):
    attempts['count']+=1;save_setting(c,key,attempts)
    accounting.audit(c,'RECTIFICACION_CODIGO_RECHAZADO',sid,dict(intentos=attempts['count']))
    return jsonify(error='Código incorrecto o vencido'),403
   if cfg['used_step']>=step:return jsonify(error='Código ya utilizado. Espera el siguiente código del autenticador'),409
   detail=dict(previous_counted=r['counted'],previous_difference=r['difference'],counted=counted,difference=counted-r['expected'],expected=r['expected'],reason=reason,authorized_by='AUTENTICADOR DE AJUSTES')
   c.execute('UPDATE cash_sessions SET counted=?,difference=? WHERE id=?',(counted,counted-r['expected'],sid))
   c.execute("UPDATE print_jobs SET state='CANCELLED',last_error='Sustituido por una rectificación',updated_at=? WHERE source_kind='CASH_CLOSE' AND source_id=? AND state IN ('PAUSED','FAILED')",(accounting.now(),sid))
   cfg['used_step']=step;save_setting(c,'cancellation_totp',cfg)
   accounting.audit(c,'RECTIFICACION_CIERRE',sid,detail)
   return jsonify(shift=accounting.shift_summary(c,c.execute('SELECT * FROM cash_sessions WHERE id=?',(sid,)).fetchone()))
