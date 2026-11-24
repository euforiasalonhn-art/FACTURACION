import os,tempfile,sys,unittest,io,json
from pathlib import Path
os.environ['FRY_CHICKEN_DATA_DIR']=tempfile.mkdtemp()
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import app
from openpyxl import load_workbook
class AccountingTests(unittest.TestCase):
 def setUp(self):
  # Cada caso debe tener tambien su respaldo aislado y una sucursal existente.
  app.DATA=Path(tempfile.mkdtemp(prefix='fry-accounting-test-'))
  app.DB=app.DATA/(self._testMethodName+'.db');app.init_db();app.FAILURES.clear();self.c=app.app.test_client();self.h={'X-POS-Token':app.TOKEN};self.admin()
  self.assertEqual(self.post('branches',dict(name='Centro',address='Centro',password='1234',next_invoice=1)).status_code,200)
  self.post('admin/config',dict(current_password='FRY2026',email='frychickencompany@gmail.com',branch_id=1))
  self.c.patch('/api/products/1',json=dict(name='Producto existente',price='115',tax_type='15'),headers=self.h)
  self.assertEqual(self.post('cash',dict(action='open',branch_id=1,opening=500)).status_code,200)
 def post(self,p,d,c=None):return(c or self.c).post('/api/'+p,json=d,headers=self.h)
 def admin(self):return self.post('auth/login',dict(role='admin',email='frychickencompany@gmail.com',password='FRY2026'))
 def sale(self,key='sale',**kw):return self.post('invoices',dict(branch_id=1,items=[dict(id=1,quantity=1)],discount=0,invoice_type='NORMAL',payment_method='Tarjeta',request_id=key)|kw)
 def create_account(self):
  r=self.post('admin/accountants',dict(email='contador@example.com',password='Temporal2026'));self.assertEqual(r.status_code,200,r.data);return r.get_json()[0]['id']
 def accountant(self):
  c=app.app.test_client();r=self.post('auth/login',dict(role='accountant',email='CONTADOR@example.com',password='Temporal2026'),c);self.assertEqual(r.status_code,200,r.data);return c
 def test_account_permissions_change_reset_disable(self):
  uid=self.create_account();c=self.accountant();self.assertEqual(c.get('/api/accounting').status_code,403)
  self.assertEqual(self.post('auth/password',dict(current_password='wrong',password='MiClave2026'),c).status_code,400)
  self.assertEqual(self.post('auth/password',dict(current_password='Temporal2026',password='MiClave2026'),c).status_code,200)
  self.assertEqual(c.get('/api/accounting').status_code,200)
  for path,data in [('invoices',{}),('admin/fiscal',{}),('admin/accountants',{}),('cash',{}),('customers',{})]:self.assertEqual(self.post(path,data,c).status_code,403,path)
  self.assertEqual(c.patch('/api/products/1',json={'price':1},headers=self.h).status_code,403)
  self.assertEqual(c.get('/api/reports').status_code,200)
  self.c.patch('/api/admin/accountants/'+str(uid),json=dict(email='contador@example.com',active=False),headers=self.h)
  self.assertEqual(c.get('/api/accounting').status_code,401)
  self.c.patch('/api/admin/accountants/'+str(uid),json=dict(email='contador@example.com',active=True,password='OtraTemporal2026'),headers=self.h)
  self.assertEqual(self.post('auth/login',dict(role='accountant',email='contador@example.com',password='MiClave2026'),c).status_code,401)
  self.assertEqual(self.post('auth/login',dict(role='accountant',email='contador@example.com',password='OtraTemporal2026'),c).status_code,200)
 def test_mixed_percentage_cash_and_void(self):
  with app.connect() as c:app.save_setting(c,'commerce',dict(senior=10))
  r=self.sale(discount_profile='SENIOR',discount_beneficiary_name='Cliente autorizado',discount_beneficiary_identity='0801195012345',payment_method='Mixto',payments=dict(Efectivo=50,Tarjeta=30,Transferencia='23.50'),amount_received=60);self.assertEqual(r.status_code,200,r.data)
  invoice=self.c.get('/api/invoices/1').get_json();self.assertEqual(invoice['total'],10350);self.assertEqual(invoice['amount_received']-invoice['total'],1000);self.assertEqual(invoice['cash_session_id'],1)
  self.assertEqual(self.sale('bad',payment_method='Mixto',payments=dict(Efectivo=1)).status_code,400)
  self.sale('card');void=self.sale('void').get_json()['id'];self.assertEqual(self.post(f'invoices/{void}/void',dict(reason='Operación anulada de prueba')).status_code,200)
  for kind,amount in [('INGRESO',25),('EGRESO',20)]:self.post('cash',dict(action='movement',branch_id=1,kind=kind,amount=amount,concept='Movimiento de prueba'))
  shift=self.c.get('/api/cash?branch_id=1').get_json()['shift'];self.assertEqual(shift['live_expected'],55500)
  r=self.post('cash',dict(action='close',branch_id=1,shift_id=shift['id'],counted=550));self.assertEqual(r.status_code,200,r.data);self.assertEqual(r.get_json()['last_closed']['difference'],-500)
  self.assertEqual(self.post('invoices/1/void',dict(reason='No debe alterar cierre')).status_code,400)
  data=self.c.get('/api/accounting?scope=all').get_json();self.assertEqual(data['totals']['total'],21850);self.assertEqual(data['totals']['Efectivo'],5000);self.assertEqual(data['totals']['Tarjeta'],14500);self.assertEqual(data['voided'],1)
  self.assertEqual(self.c.get('/api/accounting?payment=Transferencia').get_json()['count'],1)
  self.assertEqual(self.c.get('/api/accounting?scope=fiscal').get_json()['count'],0)
 def test_exports_real_formats_and_formula_safety(self):
  sale=self.sale(customer_name='=HYPERLINK("x")',invoice_type='RTN',customer_rtn='08011990123456');self.assertEqual(sale.status_code,200,sale.data)
  self.create_account();c=self.accountant();self.post('auth/password',dict(current_password='Temporal2026',password='MiClave2026'),c)
  r=c.get('/api/accounting/export/xlsx?scope=all');self.assertEqual(r.status_code,200,r.data[:300]);wb=load_workbook(io.BytesIO(r.data))
  self.assertIn('Libro de ventas',wb.sheetnames);ws=wb['Libro de ventas'];self.assertEqual(ws['E6'].value,'=HYPERLINK("x")');self.assertEqual(ws['E6'].data_type,'s');self.assertEqual(ws['T6'].value,115)
  r=c.get('/api/accounting/export/pdf?scope=all');self.assertEqual(r.status_code,200,r.data[:300]);self.assertTrue(r.data.startswith(b'%PDF'))
  html=c.get('/api/accounting/export/print?scope=all');self.assertEqual(html.status_code,200);self.assertIn(b'Clientes RTN',html.data)
  if os.environ.get('FRY_TEST_EXPORT_DIR'):
   from pathlib import Path
   target=Path(os.environ['FRY_TEST_EXPORT_DIR']);target.mkdir(exist_ok=True,parents=True);(target/'contabilidad-prueba.xlsx').write_bytes(c.get('/api/accounting/export/xlsx?scope=all').data);(target/'contabilidad-prueba.pdf').write_bytes(r.data)
 def test_upgrade_preserves_products_and_historical_fields(self):
  self.sale()
  with app.connect() as c:
   before=[tuple(r) for r in c.execute('SELECT * FROM products ORDER BY id')];c.execute("UPDATE invoices SET snapshot=? WHERE id=1",(json.dumps(dict(items=[],branch={'name':'Antigua'})),));c.execute('DROP TABLE accountants')
  app.init_db()
  self.assertTrue(list(app.DATA.glob('respaldo-antes-v5-*.db')))
  with app.connect() as c:self.assertEqual(before,[tuple(r) for r in c.execute('SELECT * FROM products ORDER BY id')])
  data=self.c.get('/api/accounting').get_json();self.assertEqual(data['incomplete'],1);self.assertIsNone(data['invoices'][0]['taxable_15']);self.assertEqual(data['totals']['total'],11500)
if __name__=='__main__':unittest.main()
