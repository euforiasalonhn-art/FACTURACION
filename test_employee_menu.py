import unittest
from test_operations import OperationsTests
import app
class EmployeeMenuTests(unittest.TestCase):
 def setUp(self):
  base=OperationsTests('test_sale_command_goals_cancellation_and_retry');base._testMethodName=self._testMethodName;base.setUp();self.base=base;self.c=base.c;self.h=base.h
  for pid,name,cat in [(1,'Plato pollo','Platos'),(2,'Refresco','Refrescos'),(3,'Papas extra','Complementos'),(4,'Plato arroz','Platos')]:
   r=self.c.patch('/api/products/'+str(pid),json=dict(name=name,category=cat,price='20',tax_type='15'),headers=self.h);self.assertEqual(r.status_code,200,r.data)
 def post(self,path,d):return self.base.post(path,d)
 def configure(self):
  r=self.post('admin/employee-menu',dict(products=[dict(id=1,kind='DISH'),dict(id=4,kind='DISH'),dict(id=2,kind='DRINK')]));self.assertEqual(r.status_code,200,r.data)
 def meal(self,items,key='meal'):
  return self.post('employee-meals',self.base.data(key,employee_id=1,cost=10,employee_meal=True,items=items))
 def test_default_closed_and_admin_permissions(self):
  self.post('admin/employee-menu',dict(products=[]))
  self.assertEqual(self.c.get('/api/employee-menu').get_json(),[])
  self.assertEqual(self.meal([dict(id=1,quantity=1),dict(id=2,quantity=1)]).status_code,400)
  self.configure();self.post('auth/logout',{});self.assertEqual(self.post('auth/login',dict(role='local',branch_id=1,employee_code='ANA123')).status_code,200)
  self.assertEqual(self.post('admin/employee-menu',dict(products=[])).status_code,403)
  self.assertEqual(self.c.get('/api/admin/employee-menu').status_code,403)
  self.assertEqual(len(self.c.get('/api/employee-menu').get_json()),3)
  self.assertEqual(self.meal([dict(id=1,quantity=1),dict(id=2,quantity=1)]).status_code,200)
 def test_strict_shape_and_no_complements(self):
  self.configure()
  invalid=[[],[dict(id=1,quantity=1)],[dict(id=1,quantity=2),dict(id=2,quantity=1)],[dict(id=1,quantity=True),dict(id=2,quantity=1)],[dict(id=1,quantity=1),dict(id=4,quantity=1)],[dict(id=2,quantity=1),dict(id=2,quantity=1)],[dict(id=1,quantity=1),dict(id=3,quantity=1)],[dict(id=1,quantity=1),dict(id=2,quantity=1),dict(id=3,quantity=1)]]
  for n,items in enumerate(invalid):
   self.assertEqual(self.meal(items,str(n)).status_code,400,items)
   self.assertEqual(self.post('quote',self.base.data(items=items,employee_meal=True)).status_code,400,items)
  with app.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM employee_meals').fetchone()[0],0)
 def test_valid_free_meal_retry_and_revoked_product(self):
  self.configure();items=[dict(id=1,quantity=1),dict(id=2,quantity=1)]
  r=self.meal(items);self.assertEqual(r.status_code,200,r.data);mid=r.get_json()
  self.post('admin/employee-menu',dict(products=[]))
  self.assertEqual(self.meal(items).get_json(),mid)
  self.assertEqual(self.meal(items,'new').status_code,400)
  with app.connect() as c:
   self.assertEqual(c.execute('SELECT COUNT(*) FROM employee_meals').fetchone()[0],1)
   self.assertEqual(c.execute('SELECT COUNT(*) FROM invoices').fetchone()[0],0)
   self.assertEqual(c.execute('SELECT next_invoice FROM branches WHERE id=1').fetchone()[0],1)
  self.assertEqual(self.c.get('/api/cash?branch_id=1').get_json()['shift']['live_expected'],50000)
 def test_bad_assignments_and_paid_orders_unaffected(self):
  for rows in [[dict(id=1,kind='DISH'),dict(id=1,kind='DRINK')],[dict(id=99999,kind='DISH')],[dict(id=1,kind='EXTRA')]]:
   self.assertEqual(self.post('admin/employee-menu',dict(products=rows)).status_code,400)
  self.assertEqual(self.post('invoices',self.base.data(items=[dict(id=3,quantity=3)])).status_code,200)
if __name__=='__main__':unittest.main()
