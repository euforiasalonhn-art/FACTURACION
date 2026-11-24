import os,tempfile,sys,unittest,json
from datetime import date,timedelta
from concurrent.futures import ThreadPoolExecutor
os.environ['FRY_CHICKEN_DATA_DIR']=tempfile.mkdtemp()
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import app,fiscal
class FiscalTests(unittest.TestCase):
 def setUp(self):
  app.DB=app.DATA/(self._testMethodName+'.db');app.init_db();app.FAILURES.clear();self.c=app.app.test_client();self.h={'X-POS-Token':app.TOKEN}
  self.post('auth/login',dict(role='admin',email='frychickencompany@gmail.com',password='FRY2026'))
  self.post('admin/config',dict(current_password='FRY2026',email='frychickencompany@gmail.com',branch_id=1))
  self.c.patch('/api/products/1',json=dict(name='TENEDOR',price='2',tax_type='15'),headers=self.h)
  self.cfg=dict(fiscal.DEFAULT,branch_id=1,enabled=True,legal_name='EMISOR DE PRUEBA SIN VALIDEZ FISCAL',commercial_name='FRY CHICKEN — MUESTRA',rtn='12345678901234',address='DIRECCIÓN DE PRUEBA',head_address='CASA MATRIZ DE PRUEBA',phone='0000-0000',email='demo@example.com',cai='ABCDEF-ABCDEF-ABCDEF-ABCDEF-ABCDEF-AB',establishment='000',point='003',range_start=55001,range_end=55003,next_number=55001,deadline=(date.today()+timedelta(days=60)).isoformat())
 def post(self,path,data,c=None):return (c or self.c).post('/api/'+path,json=data,headers=self.h)
 def configure(self,**kw):return self.post('admin/fiscal',self.cfg|kw)
 def sale(self,key='a',**kw):return self.post('invoices',dict(branch_id=1,items=[dict(id=1,quantity=1)],discount=0,invoice_type='NORMAL',payment_method='Efectivo',amount_received='10',request_id=key)|kw)
 def test_sample_matches_and_snapshot(self):
  self.assertEqual(self.configure().status_code,200)
  r=self.sale();self.assertEqual(r.status_code,200,r.data);invoice=self.c.get('/api/invoices/'+str(r.get_json()['id'])).get_json()
  self.assertEqual(invoice['fiscal_number'],'000-003-01-00055001');self.assertEqual((invoice['subtotal'],invoice['tax_15'],invoice['total']),(174,26,200))
  html=invoice['receipt_html']
  for text in ['ABCDEF-ABCDEF','00055001','Fecha límite','TENEDOR','IMPUESTOS' if False else 'Total Impuestos','DOS LEMPIRAS Y 00/100','ORDEN COMPRA EXENTA','SAG','ORIGINAL']:self.assertIn(text,html)
  copy=self.c.get('/api/invoices/1?copy=COPIA').get_json()['receipt_html'];self.assertIn('COPIA · OBLIGADO',copy)
  self.configure(legal_name='NUEVA RAZÓN SOCIAL',next_number=55002)
  self.assertEqual(self.c.get('/api/invoices/1').get_json()['snapshot']['fiscal']['legal_name'],'EMISOR DE PRUEBA SIN VALIDEZ FISCAL')
 def test_range_void_and_no_reuse(self):
  self.configure()
  for key in ['a','b','c']:self.assertEqual(self.sale(key).status_code,200)
  self.assertEqual(self.sale('d').status_code,400)
  self.assertEqual(self.sale('a').get_json()['id'],1)
  self.post('invoices/1/void',{'reason':'Prueba de anulación'})
  self.assertEqual(self.configure(next_number=55001).status_code,400)
  with app.connect() as c:self.assertEqual(c.execute('SELECT next_invoice FROM branches WHERE id=1').fetchone()[0],4)
  self.assertEqual(len(self.c.get('/api/reports').get_json()),3)
 def test_expiry_and_invalid_config(self):
  for kw in [dict(cai='MAL'),dict(rtn='1'),dict(next_number=4),dict(deadline='2020-01-01')]:self.assertEqual(self.configure(**kw).status_code,400)
  self.configure()
  with app.connect() as c:
   cfg=fiscal.config(c,1);cfg['deadline']='2020-01-01';fiscal.save(c,1,cfg)
  self.assertEqual(self.sale().status_code,400);self.assertIn('vencido',self.c.get('/api/fiscal/state?branch_id=1').get_json()['warning'])
  with app.connect() as c:self.assertEqual(c.execute('SELECT count(*) FROM invoices').fetchone()[0],0)
 def test_mixed_taxes_discounts_and_modes(self):
  self.configure(enabled=False)
  for price,tax in [('118','18'),('50','EXENTO'),('20','EXONERADO')]:self.post('products',dict(name=tax,category='Mixtos',price=price,tax_type=tax))
  with app.connect() as c:
   d=dict(branch_id=1,items=[dict(id=i,quantity=1) for i in [1,12,13,14]],discount='19')
   result=app.calculate(c,d)
   self.assertEqual(result['listed_total'],19000);self.assertEqual(result['total'],17100)
   self.assertEqual(result['discount'],sum(i['line_discount'] for i in result['items']))
   self.assertEqual(result['total'],result['subtotal']+result['tax_15']+result['tax_18'])
   cfg=fiscal.config(c,1);cfg['price_mode']='EXCLUSIVE';fiscal.save(c,1,cfg)
  self.c.patch('/api/products/1',json={'price':'100'},headers=self.h)
  q=self.post('quote',dict(branch_id=1,items=[dict(id=1,quantity=2)],discount=10)).get_json();self.assertEqual((q['subtotal'],q['tax_15'],q['total']),(19000,2850,21850))
 def test_local_permissions_and_exoneration(self):
  self.configure();self.c.patch('/api/products/1',json={'tax_type':'EXONERADO'},headers=self.h)
  self.assertEqual(self.sale().status_code,400)
  r=self.sale(invoice_type='RTN',customer_name='EMPRESA',customer_rtn='12345678901234',purchase_order='OC-001');self.assertEqual(r.status_code,200,r.data)
  self.post('auth/logout',{});self.post('auth/login',dict(role='local',password='1234'))
  self.assertEqual(self.configure().status_code,403)
  self.assertEqual(self.c.get('/api/fiscal/state?branch_id=2').status_code,403)
 def test_atomic_concurrent_numbering(self):
  self.configure()
  def sell(i):
   c=app.app.test_client();self.post('auth/login',dict(role='local',password='1234'),c)
   return self.post('invoices',dict(branch_id=1,items=[dict(id=1,quantity=1)],invoice_type='NORMAL',payment_method='Tarjeta',request_id='parallel-'+str(i)),c).status_code
  with ThreadPoolExecutor(max_workers=3) as pool:self.assertEqual(list(pool.map(sell,range(3))),[200]*3)
  with app.connect() as c:self.assertEqual(len(set(r[0] for r in c.execute('SELECT fiscal_number FROM invoices'))),3)
 def test_unconfigured_marks_sample_and_195_total(self):
  self.c.patch('/api/products/1',json={'price':'195'},headers=self.h)
  r=self.sale(amount_received='200');self.assertEqual(r.status_code,200,r.data)
  invoice=self.c.get('/api/invoices/1').get_json();self.assertIsNone(invoice['fiscal_number']);self.assertIn('NO VÁLIDA PARA EFECTOS FISCALES',invoice['receipt_html'])
  self.assertEqual((invoice['subtotal'],invoice['tax_15'],invoice['total']),(16957,2543,19500))
if __name__=='__main__':unittest.main()
