from flask import request,jsonify
import accounting

def init(c):c.execute('CREATE TABLE IF NOT EXISTS discount_exclusions(product_id INTEGER PRIMARY KEY REFERENCES products(id))')
def register(app,connect):
 @app.get('/api/admin/no-discount')
 def no_discount_list():
  with connect() as c:return jsonify([dict(r) for r in c.execute('SELECT p.id,p.name,p.category,CASE WHEN e.product_id IS NULL THEN 0 ELSE 1 END AS excluded FROM products p LEFT JOIN discount_exclusions e ON e.product_id=p.id WHERE p.active=1 ORDER BY p.category COLLATE NOCASE,p.name COLLATE NOCASE')])
 @app.post('/api/admin/no-discount')
 def no_discount_save():
  d=request.json or {};changes=d.get('changes',[dict(id=d.get('id'),excluded=d.get('excluded'))])
  if not isinstance(changes,list) or len(changes)>10000:raise ValueError('Lista de cambios inválida')
  ids=set()
  for change in changes:
   if not isinstance(change,dict) or not isinstance(change.get('id'),int) or isinstance(change.get('id'),bool) or not isinstance(change.get('excluded'),bool) or change['id'] in ids:raise ValueError('Lista de productos inválida')
   ids.add(change['id'])
  with connect() as c:
   c.execute('BEGIN IMMEDIATE')
   for change in changes:
    if not c.execute('SELECT id FROM products WHERE id=?',(change['id'],)).fetchone():raise ValueError('Producto no encontrado; recarga la lista')
   for change in changes:
    pid=change['id'];excluded=change['excluded']
    if excluded:c.execute('INSERT OR IGNORE INTO discount_exclusions VALUES(?)',(pid,))
    else:c.execute('DELETE FROM discount_exclusions WHERE product_id=?',(pid,))
    accounting.audit(c,'PRODUCTO_SIN_DESCUENTO',pid,dict(excluded=excluded))
  return jsonify(ok=True,saved=len(changes))
