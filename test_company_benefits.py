import unittest,io,base64
import test_operations as fixtures
import app,fiscal
from PIL import Image
class CompanyTests(unittest.TestCase):
 def setUp(self):
  self.f=fixtures.OperationsTests('test_permissions_and_validation');self.f._testMethodName=self._testMethodName;self.f.setUp();self.c=self.f.c;self.h=self.f.h
 def save(self,**kw):
  return self.f.post('admin/company-benefits',dict(name='EMPRESA PRUEBA',rtn='12345678901234',kind='EXONERADO',active=True,products=[1])|kw)
 def data(self,**kw):return self.f.data(invoice_type='RTN',customer_name='EMPRESA PRUEBA',customer_rtn='12345678901234',items=[dict(id=1,quantity=1),dict(id=2,quantity=1)])|kw
 def test_selected_products_and_no_forgery(self):
  self.assertEqual(self.c.get('/api/admin/company-benefits').get_json(),[])
  self.assertEqual(self.save().status_code,200)
  q=self.f.post('quote',self.data()).get_json();self.assertEqual(q['exempted'],10000);self.assertEqual(q['total'],12500);self.assertEqual(q['tax_15'],326);self.assertEqual(q['company_benefit']['products'],[1]);self.assertEqual(q['items'][1]['tax_type'],'15')
  normal=self.f.post('quote',self.data(invoice_type='NORMAL',company_benefit={'kind':'EXENTO'},tax_type='EXENTO')).get_json();self.assertEqual(normal['total'],14000);self.assertIsNone(normal['company_benefit'])
  unknown=self.f.post('quote',self.data(customer_rtn='99999999999999')).get_json();self.assertEqual(unknown['exempted'],0)
 def test_invoice_snapshot_history_and_photo_optional(self):
  self.assertEqual(self.save(kind='EXENTO').status_code,200)
  r=self.f.post('invoices',self.data());self.assertEqual(r.status_code,200,r.data)
  inv=self.c.get('/api/invoices/'+str(r.get_json()['id'])).get_json();self.assertEqual(inv['snapshot']['exempt'],10000);self.assertEqual(inv['snapshot']['company_benefit']['revision'],1)
  self.assertNotIn('Impuesto al 18 % Lps.:',inv['receipt_html']);self.assertNotIn('Efectivo: L 0.00',inv['receipt_html'])
  self.assertEqual(self.save(id=1,active=False).status_code,200)
  self.assertEqual(self.f.post('quote',self.data()).get_json()['total'],14000)
  inv2=self.c.get('/api/invoices/'+str(r.get_json()['id'])).get_json();self.assertEqual(inv2['snapshot'],inv['snapshot'])
  with app.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM company_benefit_history').fetchone()[0],2)
 def test_enabled_cai_optional_photo_and_exclusive_prices(self):
  from datetime import date,timedelta
  cfg=dict(fiscal.DEFAULT,branch_id=1,enabled=True,legal_name='PRUEBA',commercial_name='PRUEBA',rtn='12345678901234',address='Centro',head_address='Matriz',phone='12345678',email='demo@example.com',cai='ABCDEF-ABCDEF-ABCDEF-ABCDEF-ABCDEF-AB',establishment='000',point='001',range_start=1,range_end=10,next_number=1,deadline=(date.today()+timedelta(days=10)).isoformat())
  response=self.f.post('admin/fiscal',cfg);self.assertEqual(response.status_code,200,response.data)
  self.save();r=self.f.post('invoices',self.data());self.assertEqual(r.status_code,200,r.data)
  inv=self.c.get('/api/invoices/'+str(r.get_json()['id'])).get_json();self.assertEqual(inv['fiscal_number'],'000-001-01-00000001')
  self.assertEqual(self.f.post('invoices',self.data()).get_json()['id'],r.get_json()['id'])
  with app.connect() as c:self.assertEqual(fiscal.config(c,1)['next_number'],2)
  self.assertEqual(self.f.post('admin/fiscal',cfg|dict(price_mode='EXCLUSIVE',next_number=2)).status_code,200)
  q=self.f.post('quote',self.data()).get_json();self.assertEqual(q['exempted'],11500);self.assertEqual(q['tax_15'],375);self.assertEqual(q['total'],14375)
 def test_photo_validation_permissions_and_discount(self):
  self.assertEqual(self.save(products=[]).status_code,400);self.assertEqual(self.save(photo='bad').status_code,400)
  b=io.BytesIO();Image.new('RGB',(20,20),'white').save(b,format='PNG');encoded=base64.b64encode(b.getvalue()).decode()
  r=self.save(photo=encoded);self.assertEqual(r.status_code,200,r.data);self.assertTrue(r.get_json()[0]['has_photo'])
  self.assertEqual(self.c.get('/api/admin/company-benefits/1/photo').status_code,200)
  self.assertEqual(self.save(id=1,remove_photo=True).status_code,200);self.assertEqual(self.c.get('/api/admin/company-benefits/1/photo').status_code,404);self.assertEqual(self.c.get('/api/admin/company-benefits/1/photo?revision=1').status_code,200)
  self.assertEqual(self.f.post('quote',self.data(discount_profile='EMPLOYEE',discount_employee_id=1)).status_code,400)
  self.f.post('auth/logout',{});self.f.post('auth/login',dict(role='local',branch_id=1,employee_code='ANA123'))
  self.assertEqual(self.c.get('/api/admin/company-benefits').status_code,403);self.assertEqual(self.save().status_code,403)
if __name__=='__main__':unittest.main()
