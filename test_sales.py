import os,tempfile,sys,unittest,sqlite3,json,io
from PIL import Image
from concurrent.futures import ThreadPoolExecutor
os.environ['FRY_CHICKEN_DATA_DIR']=tempfile.mkdtemp()
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import app
class SecurityAndSales(unittest.TestCase):
 def setUp(self):
  app.DB=app.DATA/(self._testMethodName+'.db');app.init_db();app.FAILURES.clear();self.c=app.app.test_client();self.h={'X-POS-Token':app.TOKEN}
 def post(self,path,data,client=None):return (client or self.c).post('/api/'+path,json=data,headers=self.h)
 def admin(self):
  r=self.post('auth/login',dict(role='admin',email='frychickencompany@gmail.com',password='FRY2026'));self.assertEqual(r.status_code,200,r.data)
 def configure(self,branch=1,**kwargs):
  return self.post('admin/config',dict(current_password='FRY2026',email='frychickencompany@gmail.com',branch_id=branch,**kwargs))
 def local(self):
  self.post('auth/logout',{});r=self.post('auth/login',dict(role='local',password='1234'));self.assertEqual(r.status_code,200,r.data)
 def product(self):
  r=self.c.patch('/api/products/1',json=dict(name='Pollo',category='Menú',price='100',tax_type='15'),headers=self.h);self.assertEqual(r.status_code,200,r.data)
 def sale(self,**kwargs):
  d=dict(branch_id=1,items=[dict(id=1,quantity=2)],discount='10',invoice_type='NORMAL',payment_method='Efectivo',amount_received='250',request_id='a');d.update(kwargs);return self.post('invoices',d)
 def test_roles_and_settings(self):
  self.assertEqual(self.c.get('/api/products').status_code,401)
  self.assertEqual(self.post('auth/login',dict(role='local',password='1234')).status_code,401)
  self.admin();self.assertEqual(self.configure().status_code,200);self.product();self.local()
  self.assertEqual(self.c.patch('/api/products/1',json=dict(price=1),headers=self.h).status_code,403)
  for path in ['reports','admin/config','branches','invoices/1/void']:
   r=self.c.get('/api/'+path) if path=='reports' else self.post(path,{})
   self.assertEqual(r.status_code,403,r.data)
  self.assertEqual(len(self.c.get('/api/branches').get_json()),1)
  self.assertEqual(self.sale(branch_id=99).status_code,403)
  self.assertEqual(self.sale().status_code,200)
  self.assertEqual(self.post('customers',dict(name='Empresa',rtn='12345678901234')).status_code,200)
 def test_sale_reporting_and_retry(self):
  self.admin();self.configure();self.product()
  r=self.sale();self.assertEqual(r.status_code,200,r.data);i=r.get_json()['id']
  self.assertEqual(self.sale().get_json()['id'],i)
  for method,key,typ in [('Transferencia','b','RTN'),('Tarjeta','c','NORMAL')]:
   r=self.sale(request_id=key,invoice_type=typ,customer_name='Empresa',customer_rtn='12345678901234',payment_method=method);self.assertEqual(r.status_code,200,r.data)
  rows=self.c.get('/api/reports').get_json();self.assertEqual([r['number'] for r in rows],[1,2,3]);self.assertEqual(rows[0]['total'],19000)
  self.assertEqual(self.c.get('/api/reports?payment=Tarjeta').get_json()[0]['number'],3)
  self.assertEqual(self.c.get('/api/reports?type=RTN&payment=Transferencia').get_json()[0]['number'],2)
  self.post('invoices/1/void',{'reason':'Prueba de anulación'});self.assertEqual(self.c.get('/api/invoices/1').get_json()['status'],'ANULADA')
  self.assertEqual(self.sale(request_id='d',amount_received='1').status_code,400)
  self.assertEqual(self.c.get('/api/branches').get_json()[0]['next_invoice'],4)
  self.assertEqual(self.c.get('/api/customers').get_json()[0]['name'],'Empresa')
 def test_change_login_and_branch(self):
  self.admin();self.product();self.post('branches',dict(name='Centro',address='Calle 1',next_invoice=40))
  r=self.post('admin/config',dict(current_password='FRY2026',email='nuevo@example.com',password='NUEVA2026',pin='5678',branch_id=2));self.assertEqual(r.status_code,200,r.data)
  self.post('auth/logout',{})
  self.assertEqual(self.post('auth/login',dict(role='admin',email='frychickencompany@gmail.com',password='FRY2026')).status_code,401)
  self.assertEqual(self.post('auth/login',dict(role='admin',email='nuevo@example.com',password='NUEVA2026')).status_code,200)
  self.post('auth/logout',{});self.assertEqual(self.post('auth/login',dict(role='local',password='1234')).status_code,401)
  self.assertEqual(self.post('auth/login',dict(role='local',password='5678')).status_code,200)
  self.assertEqual(self.c.get('/api/branches').get_json()[0]['name'],'Centro')
  self.assertEqual(self.sale().status_code,403);r=self.sale(branch_id=2);self.assertEqual(r.status_code,200,r.data)
  with app.connect() as c:
   cfg=app.auth_config(c);self.assertNotEqual(cfg['pin'],'5678');self.assertNotEqual(cfg['password'],'NUEVA2026')
 def test_session_invalidation_and_throttle(self):
  self.admin();self.configure();other=app.app.test_client();self.post('auth/login',dict(role='local',password='1234'),other)
  self.configure(pin='8888');self.assertEqual(other.get('/api/products').status_code,401)
  for i in range(5): self.post('auth/login',dict(role='local',password='bad'),other)
  self.assertEqual(self.post('auth/login',dict(role='local',password='8888'),other).status_code,429)
 def test_upgrade_preserves_data(self):
  self.admin();self.configure();self.product();self.sale()
  with app.connect() as c:
   c.execute('DROP TABLE settings');c.execute('DROP TABLE customers')
  app.init_db()
  with app.connect() as c:
   self.assertEqual(c.execute('SELECT total FROM invoices').fetchone()[0],19000)
   self.assertEqual(c.execute('SELECT price FROM products WHERE id=1').fetchone()[0],10000)
   self.assertEqual(c.execute('SELECT next_invoice FROM branches WHERE id=1').fetchone()[0],2)
 def test_photos_and_inline_prices(self):
  self.admin();self.configure();self.product()
  def image():
   f=io.BytesIO();Image.new('RGB',(1200,800),'orange').save(f,'PNG');f.seek(0);return f
  r=self.c.post('/api/products/1/photo',data={'photo':(image(),'pollo.png')},headers=self.h);self.assertEqual(r.status_code,200,r.data)
  p=next(x for x in r.get_json() if x['id']==1);self.assertTrue(p['image_url'])
  photo=self.c.get(p['image_url']);self.assertEqual(photo.status_code,200);self.assertEqual(photo.mimetype,'image/jpeg')
  with Image.open(io.BytesIO(photo.data)) as im:self.assertLessEqual(max(im.size),1024)
  self.sale();r=self.c.patch('/api/products/1',json={'price':'125.50'},headers=self.h);self.assertEqual(r.status_code,200,r.data)
  p=next(x for x in r.get_json() if x['id']==1);self.assertEqual(p['price'],12550);self.assertEqual(p['name'],'Pollo');self.assertTrue(p['image_url'])
  self.assertEqual(self.c.get('/api/invoices/1').get_json()['snapshot']['items'][0]['price'],10000)
  r=self.c.patch('/api/products/1',data={'price':'10','photo':(io.BytesIO(b'bad file'),'fake.jpg')},headers=self.h);self.assertEqual(r.status_code,400)
  self.assertEqual(next(x for x in self.c.get('/api/products').get_json() if x['id']==1)['price'],12550)
  self.assertEqual(self.c.patch('/api/products/1',json={'price':'-1'},headers=self.h).status_code,400)
  app.init_db();self.assertEqual(self.c.get(p['image_url']).status_code,200)
  self.local()
  self.assertEqual(self.c.get(p['image_url']).status_code,200)
  self.assertEqual(self.c.post('/api/products/1/photo',data={'photo':(image(),'pollo.png')},headers=self.h).status_code,403)
  self.assertEqual(self.c.delete('/api/products/1/photo',headers=self.h).status_code,403)
  self.admin();self.assertEqual(self.c.delete('/api/products/1/photo',headers=self.h).status_code,200)
  self.assertIsNone(next(x for x in self.c.get('/api/products').get_json() if x['id']==1)['image_url'])
 def test_create_product_with_photo_atomic(self):
  self.admin()
  before=len(self.c.get('/api/products').get_json())
  r=self.c.post('/api/products',data={'name':'Nuevo','category':'Combos','price':'90','tax_type':'15','photo':(io.BytesIO(b'bad'),'x.png')},headers=self.h)
  self.assertEqual(r.status_code,400);self.assertEqual(len(self.c.get('/api/products').get_json()),before)
  photo=io.BytesIO();Image.new('RGB',(20,20),'red').save(photo,'JPEG');photo.seek(0)
  r=self.c.post('/api/products',data={'name':'Nuevo','category':'Combos','price':'90','tax_type':'15','photo':(photo,'pollo.jpg')},headers=self.h)
  self.assertEqual(r.status_code,200,r.data);self.assertEqual(len(r.get_json()),before+1);self.assertTrue(next(x for x in r.get_json() if x['name']=='Nuevo')['image_url'])
if __name__=='__main__':unittest.main()

