"""Menú gratuito autorizado: exactamente un plato y un refresco."""
from flask import request,session,jsonify
import accounting

def init(c):
 c.execute("CREATE TABLE IF NOT EXISTS employee_menu(product_id INTEGER PRIMARY KEY REFERENCES products(id) ON DELETE CASCADE,kind TEXT NOT NULL CHECK(kind IN ('DISH','DRINK')))")

def validate(c,d):
 items=d.get('items')
 if not isinstance(items,list) or len(items)!=2:raise ValueError('El almuerzo gratis permite exactamente un plato y un refresco autorizados, sin complementos')
 selected=[]
 for item in items:
  if not isinstance(item,dict) or type(item.get('id')) is not int or type(item.get('quantity')) is not int or item['quantity']!=1:raise ValueError('Solo se permite una unidad de plato y una unidad de refresco')
  row=c.execute('SELECT m.kind FROM employee_menu m JOIN products p ON p.id=m.product_id WHERE m.product_id=? AND p.active=1',(item['id'],)).fetchone()
  if not row:raise ValueError('Producto no autorizado por el administrador para el almuerzo gratis')
  selected.append((item['id'],row['kind']))
 if len({p[0] for p in selected})!=2 or {p[1] for p in selected}!={'DISH','DRINK'}:raise ValueError('Selecciona un único plato y un único refresco del menú autorizado')

def register(app,connect):
 @app.get('/api/employee-menu')
 def employee_menu_public():
  if session.get('role') not in ['admin','local']:return jsonify(error='Acceso no permitido'),403
  with connect() as c:return jsonify([dict(r) for r in c.execute('SELECT p.id,p.name,p.category,p.price,m.kind FROM employee_menu m JOIN products p ON p.id=m.product_id WHERE p.active=1 ORDER BY m.kind,p.name')])
 @app.route('/api/admin/employee-menu',methods=['GET','POST'])
 def employee_menu_admin():
  with connect() as c:
   if request.method=='POST':
    rows=(request.json or {}).get('products')
    if not isinstance(rows,list) or len(rows)>1000:raise ValueError('Lista de productos inválida')
    cleaned={}
    for r in rows:
     if not isinstance(r,dict) or type(r.get('id')) is not int or r.get('kind') not in ['DISH','DRINK']:raise ValueError('Asignación de producto inválida')
     if r['id'] in cleaned:raise ValueError('Un producto no puede ser plato y refresco a la vez')
     if not c.execute('SELECT id FROM products WHERE id=?',(r['id'],)).fetchone():raise ValueError('El catálogo cambió. Recarga los productos')
     cleaned[r['id']]=r['kind']
    c.execute('BEGIN IMMEDIATE');c.execute('DELETE FROM employee_menu')
    c.executemany('INSERT INTO employee_menu(product_id,kind) VALUES(?,?)',cleaned.items())
    accounting.audit(c,'MENU_GRATUITO_EMPLEADOS','catalogo',dict(products=cleaned))
   return jsonify([dict(r) for r in c.execute("SELECT p.id,p.name,p.category,p.price,COALESCE(m.kind,'') AS kind FROM products p LEFT JOIN employee_menu m ON m.product_id=p.id WHERE p.active=1 ORDER BY p.category,p.name")])
