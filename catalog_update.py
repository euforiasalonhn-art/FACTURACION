"""Completa únicamente campos vacíos de productos existentes de V14."""
import json, hashlib, unicodedata, sqlite3
from datetime import datetime
def normalize(value):
 return ''.join(c for c in unicodedata.normalize('NFD',value.casefold()) if unicodedata.category(c)!='Mn').strip()
def apply(connect,root,data):
 manifest=root/'catalog_enrichment.json'
 if not manifest.exists():return
 entries={normalize(e['name']):e for e in json.loads(manifest.read_text(encoding='utf-8'))}
 with connect() as c:
  saved=c.execute("SELECT value FROM settings WHERE key='catalog_enrichment_v15'").fetchone()
  done=set(json.loads(saved[0])) if saved else set();changes=[];matched=[]
  for row in c.execute('SELECT id,name,price FROM products'):
   e=entries.get(normalize(row['name']))
   if not e or row['id'] in done:continue
   matched.append(row['id']);price=e.get('price_cents') if not row['price'] or row['price']<=0 else None
   image=None
   if e.get('image') and not c.execute('SELECT 1 FROM product_images WHERE product_id=?',(row['id'],)).fetchone():
    asset=root/'catalog_assets'/e['image']
    if asset.is_file():image=asset.read_bytes()
   if price is not None or image:changes.append((row['id'],price,image))
  if changes:
   backup=data/('respaldo-antes-catalogo-v15-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.db')
   with sqlite3.connect(backup) as target:c.backup(target)
  for pid,price,image in changes:
   if price is not None:c.execute('UPDATE products SET price=? WHERE id=? AND (price IS NULL OR price<=0)',(price,pid))
   if image:c.execute('INSERT OR IGNORE INTO product_images(product_id,data,digest) VALUES(?,?,?)',(pid,image,hashlib.sha256(image).hexdigest()))
  if matched:
   done.update(matched);c.execute("INSERT OR REPLACE INTO settings VALUES('catalog_enrichment_v15',?)",(json.dumps(sorted(done)),))
