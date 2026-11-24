import os,tempfile,unittest,json
from pathlib import Path
os.environ['FRY_CHICKEN_DATA_DIR']=str(Path(__file__).resolve().parents[2]/'test-data')
import app,fiscal
from datetime import date,timedelta
class OperationsTests(unittest.TestCase):
 def setUp(self):
  app.DATA.mkdir(exist_ok=True);app.DB=app.DATA/(self._testMethodName+'.db')
  if app.DB.exists():app.DB.unlink()
  # Evitar restaurar el respaldo de otro caso aislado.
  backup=app.DATA/'FRYChickenPOS-RESPALDO-COMPLETO.json'
  if backup.exists():backup.unlink()
  app.init_db();app.FAILURES.clear();self.c=app.app.test_client();self.h={'X-POS-Token':app.TOKEN}
  self.post('auth/login',dict(role='admin',email='frychickencompany@gmail.com',password='FRY2026'))
  self.assertEqual(self.post('branches',dict(name='Centro',address='Centro',password='1234',next_invoice=1)).status_code,200)
  self.post('admin/config',dict(current_password='FRY2026',email='frychickencompany@gmail.com',branch_id=1))
  self.c.patch('/api/products/1',json=dict(name='Pollo',price='115',tax_type='15'),headers=self.h)
  self.post('admin/employees',dict(name='ANA PEREZ',identity='0801199012345',first_name='ANA',first_surname='PEREZ',access_code='ANA123'))
  self.c.patch('/api/products/2',json=dict(name='Refresco autorizado',price='25',tax_type='15'),headers=self.h)
  self.post('admin/employee-menu',dict(products=[dict(id=1,kind='DISH'),dict(id=2,kind='DRINK')]))
  self.post('cash',dict(action='open',branch_id=1,opening=500))
 def post(self,path,d):
  if path=='auth/login' and d.get('role')=='local' and not d.get('stage'):
   first=self.c.post('/api/auth/login',json=dict(role='local',branch_id=d.get('branch_id'),stage='BRANCH',password='1234'),headers=self.h)
   if first.status_code!=200:return first
   d=dict(d,stage='EMPLOYEE')
  return self.c.post('/api/'+path,json=d,headers=self.h)
 def data(self,key='a',**kw):return dict(branch_id=1,items=([dict(id=1,quantity=1),dict(id=2,quantity=1)] if 'employee_id' in kw else [dict(id=1,quantity=1)]),notes='PIEZA PECHUGA <script>no</script>',order_name='Cliente',service='Para llevar',request_id=key,invoice_type='NORMAL',payment_method='Tarjeta',amount_received=0)|kw
 def goal(self):
  today=date.today().isoformat();return self.post('goals',dict(branch_id=1,title='Meta de hoy',target=100,start=today,end=today))
 def test_meal_has_no_invoice_cai_cash_or_goal_income(self):
  cfg=dict(fiscal.DEFAULT,branch_id=1,enabled=True,legal_name='PRUEBA',commercial_name='PRUEBA',rtn='12345678901234',address='Centro',head_address='Matriz',phone='12345678',email='demo@example.com',cai='ABCDEF-ABCDEF-ABCDEF-ABCDEF-ABCDEF-AB',establishment='000',point='001',range_start=1,range_end=10,next_number=1,deadline=(date.today()+timedelta(days=10)).isoformat())
  f=self.post('admin/fiscal',cfg);self.assertEqual(f.status_code,200,f.data)
  self.goal();r=self.post('employee-meals',self.data(employee_id=1,cost='42.50'));self.assertEqual(r.status_code,200,r.data);d=r.get_json()
  self.assertEqual(self.post('employee-meals',self.data(employee_id=1,cost=42.50)).get_json(),d)
  with app.connect() as c:
   self.assertEqual(c.execute('SELECT COUNT(*) FROM invoices').fetchone()[0],0)
   self.assertEqual(fiscal.config(c,1)['next_number'],1)
   self.assertEqual(c.execute('SELECT next_invoice FROM branches WHERE id=1').fetchone()[0],1)
  shift=self.c.get('/api/cash?branch_id=1').get_json()['shift'];self.assertEqual(shift['live_expected'],50000)
  self.assertEqual(self.c.get('/api/goals').get_json()[0]['sales'],0)
  self.assertEqual(self.c.get('/api/accounting?scope=all').get_json()['totals']['total'],0)
  r=self.c.get('/api/employee-meals').get_json()[0];self.assertEqual(r['cost'],4250)
  html=self.c.get('/api/kitchen-orders/'+str(d['kitchen_id'])).get_json()['html'];self.assertIn('ALIMENTACIÓN DE ANA PEREZ',html);self.assertIn('PIEZA PECHUGA',html);self.assertNotIn('<script>',html)
  self.post('admin/employee-meals/1/cost',dict(cost=45));self.assertEqual(self.c.get('/api/employee-meals').get_json()[0]['cost'],4500)
 def test_sale_command_goals_cancellation_and_retry(self):
  self.goal();r=self.post('invoices',self.data());self.assertEqual(r.status_code,200,r.data);d=r.get_json();self.assertEqual(self.post('invoices',self.data()).get_json(),d)
  row=self.c.get('/api/goals').get_json()[0];self.assertTrue(row['reached']);self.assertEqual(row['sales'],11500);self.assertEqual(row['progress'],100)
  inv=self.c.get('/api/invoices/'+str(d['id'])).get_json();self.assertEqual(inv['kitchen_id'],d['kitchen_id']);self.assertEqual(inv['snapshot']['notes'],self.data()['notes']);self.assertIn('Orden #:',inv['receipt_html'])
  html=self.c.get('/api/kitchen-orders/'+str(d['kitchen_id'])).get_json()['html'];self.assertIn('PARA LLEVAR',html);self.assertIn('Pollo',html)
  self.post('invoices/1/void',dict(reason='Prueba de devolución'));self.assertFalse(self.c.get('/api/goals').get_json()[0]['reached'])
  self.assertEqual(self.post('invoices',self.data('x',employee_meal=True)).status_code,400)
 def test_permissions_and_validation(self):
  self.goal();self.post('employee-meals',self.data(employee_id=1));self.post('branches',dict(name='Otra',address='Otra',password='1234',next_invoice=1))
  self.post('auth/logout',{});r=self.post('auth/login',dict(role='local',branch_id=2,employee_code='ANA123'));self.assertEqual(r.status_code,200,r.data)
  self.assertEqual(self.c.get('/api/kitchen-orders/1').status_code,403)
  self.assertEqual(self.post('employee-meals',self.data(employee_id=1)).status_code,403)
  self.assertEqual(self.c.get('/api/employee-meals').status_code,403)
  self.assertEqual(self.goal().status_code,403)
  self.assertEqual(self.c.get('/api/goals').get_json(),[])
  self.assertEqual(self.post('admin/employee-meals/1/cost',dict(cost=20)).status_code,403)
if __name__=='__main__':unittest.main()


