import terminals,print_queue
import cash_safety
import delivery
import employee_menu
import json
from datetime import datetime,date
from flask import request,jsonify,session,render_template
import accounting,fiscal


def init(c):
 c.executescript('''CREATE TABLE IF NOT EXISTS kitchen_orders(id INTEGER PRIMARY KEY,branch_id INTEGER NOT NULL,kind TEXT NOT NULL,source_id INTEGER NOT NULL,snapshot TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(kind,source_id));
 CREATE TABLE IF NOT EXISTS employee_meals(id INTEGER PRIMARY KEY,branch_id INTEGER NOT NULL,employee_id INTEGER NOT NULL,recipient TEXT NOT NULL,created_at TEXT NOT NULL,snapshot TEXT NOT NULL,cost INTEGER NOT NULL DEFAULT 0,request_id TEXT NOT NULL UNIQUE,cash_session_id INTEGER,actor TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS sales_goals(id INTEGER PRIMARY KEY,branch_id INTEGER NOT NULL,title TEXT NOT NULL,target INTEGER NOT NULL,start TEXT NOT NULL,end TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1,revision INTEGER NOT NULL DEFAULT 1);''')
 columns={r[1] for r in c.execute('PRAGMA table_info(sales_goals)')}
 for name,kind in [('goal_type',"TEXT NOT NULL DEFAULT 'SALES'"),('product_id','INTEGER'),('product_name',"TEXT NOT NULL DEFAULT ''")]:
  if name not in columns:c.execute('ALTER TABLE sales_goals ADD COLUMN '+name+' '+kind)


def order_fields(d):
 notes=str(d.get('notes','')).strip();name=str(d.get('order_name','')).strip();service=delivery.service(d)
 if len(notes)>1000 or len(name)>200:raise ValueError('Máximo 1000 caracteres de notas y 200 de nombre')
 return dict(notes=notes,order_name=name,service=service)


def kitchen(c,branch,kind,source,snapshot,d,recipient=''):
 fields=order_fields(d)
 snap=dict(terminal_name=terminals.terminal_name(),items=snapshot['items'],cashier=session.get('cashier_name','ADMINISTRADOR'),**fields)
 if recipient:snap['order_name']=recipient
 snap['branch_name']=c.execute('SELECT name FROM branches WHERE id=?',(branch,)).fetchone()[0]
 kid=c.execute('INSERT INTO kitchen_orders(branch_id,kind,source_id,snapshot,created_at) VALUES(?,?,?,?,?)',(branch,kind,source,json.dumps(snap,ensure_ascii=False),accounting.now())).lastrowid
 print_queue.kitchen_original(c,kid)
 return kid


def register(app,connect,money):
 @app.get('/api/kitchen-orders/<int:oid>')
 def kitchen_detail(oid):
  with connect() as c:
   r=c.execute('SELECT * FROM kitchen_orders WHERE id=?',(oid,)).fetchone()
   if not r:return jsonify(error='Comanda no encontrada'),404
   if session.get('role') not in ['admin','local'] or (session['role']=='local' and r['branch_id']!=session.get('branch_id')):return jsonify(error='Acceso no permitido'),403
   r=dict(r);r['snapshot']=json.loads(r['snapshot']);r['html']=print_queue.kitchen_html(c,oid)
   return jsonify(r)

 @app.get('/api/kitchen-orders')
 def kitchen_list():
  if session.get('role') not in ['admin','local']:return jsonify(error='Acceso no permitido'),403
  branch=session['branch_id'] if session['role']=='local' else int(request.args.get('branch_id',0))
  with connect() as c:
   return jsonify([dict(r) for r in c.execute('SELECT id,kind,source_id,created_at FROM kitchen_orders WHERE branch_id=? ORDER BY id DESC LIMIT 100',(branch,))])

 @app.route('/api/employee-meals',methods=['GET','POST'])
 def meals():
  if session.get('role') not in ['admin','local']:return jsonify(error='Acceso no permitido'),403
  with connect() as c:
   if request.method=='GET':
    if session['role']!='admin':return jsonify(error='Solo administrador'),403
    where=[];values=[]
    for k,op in [('branch_id','='),('start','>='),('end','<=')]:
     val=request.args.get(k)
     if val and val!='all':where.append(('m.branch_id' if k=='branch_id' else 'substr(m.created_at,1,10)')+op+'?');values.append(val)
    rows=[dict(r) for r in c.execute('SELECT m.*,b.name branch_name,k.id kitchen_id FROM employee_meals m JOIN branches b ON b.id=m.branch_id LEFT JOIN kitchen_orders k ON k.kind=\'MEAL\' AND k.source_id=m.id'+(' WHERE '+' AND '.join(where) if where else '')+' ORDER BY m.id DESC',values)]
    for r in rows:r['snapshot']=json.loads(r['snapshot'])
    return jsonify(rows)
   c.execute('BEGIN IMMEDIATE');d=request.json or {};branch=int(d.get('branch_id',0));key=str(d.get('request_id','')).strip()
   if not key or len(key)>100:raise ValueError('Identificador del registro inválido')
   if session['role']=='local' and branch!=session.get('branch_id'):return jsonify(error='Sucursal incorrecta'),403
   prev=c.execute('SELECT id,branch_id,terminal_id FROM employee_meals WHERE request_id=?',(key,)).fetchone()
   if prev:
    if prev['branch_id']!=branch or prev['terminal_id']!=terminals.terminal_id():return jsonify(error='Registro de otra sucursal'),403
    return jsonify(id=prev['id'],kitchen_id=c.execute("SELECT id FROM kitchen_orders WHERE kind='MEAL' AND source_id=?",(prev['id'],)).fetchone()[0])
   delivery.fee(dict(d,employee_meal=True),money)
   employee_menu.validate(c,d)
   employee=c.execute('SELECT id,name FROM employees WHERE id=? AND active=1',(d.get('employee_id'),)).fetchone()
   if not employee:raise ValueError('Selecciona un empleado activo')
   shift=c.execute("SELECT id FROM cash_sessions WHERE branch_id=? AND terminal_id=? AND status='ABIERTA'",(branch,terminals.terminal_id())).fetchone()
   cash_safety.require_current(c,branch,terminals.terminal_id())
   if not shift:raise ValueError('Inicia caja antes de registrar el almuerzo')
   if not c.execute('SELECT id FROM branches WHERE id=? AND active=1',(branch,)).fetchone():raise ValueError('Sucursal no disponible')
   calc=fiscal.calculate(c,dict(d,discount=0,discount_type='PERCENT'),money)
   # El precio de venta es referencia; el gasto usa exclusivamente el costo indicado.
   cost=money(d.get('cost',0));fields=order_fields(d);calc.update(fields)
   mid=c.execute('INSERT INTO employee_meals(branch_id,employee_id,recipient,created_at,snapshot,cost,request_id,cash_session_id,actor) VALUES(?,?,?,?,?,?,?,?,?)',(branch,employee['id'],employee['name'],accounting.now(),json.dumps(calc,ensure_ascii=False),cost,key,shift['id'],accounting.actor())).lastrowid
   c.execute('UPDATE employee_meals SET terminal_id=? WHERE id=?',(terminals.terminal_id(),mid))
   kid=kitchen(c,branch,'MEAL',mid,calc,d,'ALIMENTACIÓN DE '+employee['name'])
   accounting.audit(c,'ALMUERZO_EMPLEADO',mid,dict(cost=cost,employee_id=employee['id'],charged=0))
   return jsonify(id=mid,kitchen_id=kid)

 @app.post('/api/admin/employee-meals/<int:mid>/cost')
 def meal_cost(mid):
  with connect() as c:
   cost=money((request.json or {}).get('cost',0))
   if not c.execute('UPDATE employee_meals SET cost=? WHERE id=?',(cost,mid)).rowcount:return jsonify(error='Almuerzo no encontrado'),404
   accounting.audit(c,'COSTO_ALMUERZO',mid,dict(cost=cost))
  return jsonify(ok=True)

 @app.route('/api/goals',methods=['GET','POST'])
 def goals():
  if session.get('role') not in ['admin','local']:return jsonify(error='Acceso no permitido'),403
  with connect() as c:
   if request.method=='POST':
    if session['role']!='admin':return jsonify(error='Solo el administrador asigna metas'),403
    d=request.json or {};branch=int(d.get('branch_id',0));title=str(d.get('title','')).strip();goal_type=d.get('goal_type','SALES');product_id=None;product_name=''
    if goal_type not in ['SALES','PRODUCT']:raise ValueError('Selecciona una meta de ventas o por producto')
    if goal_type=='PRODUCT':
     raw=str(d.get('target',''))
     if not raw.isascii() or not raw.isdigit() or not 1<=int(raw)<=999999999:raise ValueError('La cantidad debe ser un número entero mayor que cero')
     target=int(raw);product_id=int(d.get('product_id') or 0)
     product=c.execute('SELECT name FROM products WHERE id=?',(product_id,)).fetchone()
     if not product:raise ValueError('Selecciona un producto del catálogo')
     product_name=product['name']
    else:target=money(d.get('target',0))
    if not title or len(title)>200 or target<=0:raise ValueError('Indica nombre y monto mayor que cero')
    start=date.fromisoformat(str(d.get('start',''))).isoformat();end=date.fromisoformat(str(d.get('end',''))).isoformat()
    if end<start:raise ValueError('La fecha final no puede ser anterior a la inicial')
    if not c.execute('SELECT id FROM branches WHERE id=? AND active=1',(branch,)).fetchone():raise ValueError('Selecciona una sucursal activa')
    if d.get('id'):
     if not c.execute('SELECT id FROM sales_goals WHERE id=?',(d['id'],)).fetchone():raise ValueError('Meta no encontrada')
     c.execute('UPDATE sales_goals SET branch_id=?,title=?,target=?,start=?,end=?,active=?,goal_type=?,product_id=?,product_name=?,revision=revision+1 WHERE id=?',(branch,title,target,start,end,int(d.get('active',True)),goal_type,product_id,product_name,d['id']))
    else:c.execute('INSERT INTO sales_goals(branch_id,title,target,start,end,goal_type,product_id,product_name) VALUES(?,?,?,?,?,?,?,?)',(branch,title,target,start,end,goal_type,product_id,product_name))
    accounting.audit(c,'META_GUARDADA',d.get('id','nueva'),dict(branch_id=branch,title=title,target=target,goal_type=goal_type,product_id=product_id))
   branch=session['branch_id'] if session['role']=='local' else request.args.get('branch_id','all')
   where=' WHERE g.active=1 AND g.branch_id=?' if session['role']=='local' else (' WHERE g.branch_id=?' if branch!='all' else '')
   rows=[dict(r) for r in c.execute('SELECT g.*,b.name branch_name FROM sales_goals g JOIN branches b ON b.id=g.branch_id'+where+' ORDER BY g.active DESC,g.end,g.id',([branch] if where else []))]
   today=date.today().isoformat()
   for r in rows:
    if r['goal_type']=='PRODUCT':
     r['sales']=0
     for invoice in c.execute("SELECT snapshot FROM invoices WHERE branch_id=? AND status='EMITIDA' AND fiscal_number IS NOT NULL AND trim(fiscal_number)<>'' AND substr(created_at,1,10) BETWEEN ? AND ?",(r['branch_id'],r['start'],r['end'])):
      try:items=json.loads(invoice['snapshot'] or '{}').get('items',[])
      except (ValueError,AttributeError):continue
      if not isinstance(items,list):continue
      for item in items:
       if isinstance(item,dict) and item.get('id')==r['product_id'] and type(item.get('quantity')) is int and item['quantity']>0:r['sales']+=item['quantity']
    else:r['sales']=c.execute("SELECT COALESCE(SUM(total-delivery_fee),0) FROM invoices WHERE branch_id=? AND status='EMITIDA' AND substr(created_at,1,10) BETWEEN ? AND ?",(r['branch_id'],r['start'],r['end'])).fetchone()[0]
    r['remaining']=max(0,r['target']-r['sales']);r['progress']=min(100,round(r['sales']*100/r['target'],2));r['reached']=r['sales']>=r['target'];r['period_status']='Próxima' if today<r['start'] else 'Finalizada' if today>r['end'] else 'En curso'
    # El contador de la meta termina en su objetivo; no modifica las ventas reales.
    r['sales']=min(r['sales'],r['target'])
   return jsonify(rows)
