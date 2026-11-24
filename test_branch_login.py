import unittest,time
import test_operations as fixtures
import app
class BranchLoginTests(unittest.TestCase):
 def setUp(self):
  self.f=fixtures.OperationsTests('test_permissions_and_validation');self.f._testMethodName=self._testMethodName;self.f.setUp();self.c=app.app.test_client();self.h=self.f.h
 def post(self,**d):return self.c.post('/api/auth/login',json=dict(role='local',branch_id=1)|d,headers=self.h)
 def branch(self,**d):return self.post(stage='BRANCH',password='1234',**d)
 def employee(self,**d):return self.post(stage='EMPLOYEE',employee_code='ANA123',**d)
 def test_cannot_skip_password_and_no_access_between_steps(self):
  self.assertEqual(self.post(employee_code='ANA123').status_code,401)
  self.assertEqual(self.employee().status_code,401)
  self.assertEqual(self.post(stage='BRANCH',password='incorrecta').status_code,401)
  r=self.branch();self.assertEqual(r.status_code,200,r.data);self.assertEqual(r.get_json()['next_step'],'EMPLOYEE')
  self.assertIsNone(self.c.get('/api/auth/state').get_json()['role'])
  self.assertEqual(self.c.get('/api/products').status_code,401)
  # A validated branch is still not an authenticated cashier session.
  self.branch();r=self.employee();self.assertEqual(r.status_code,200,r.data);self.assertEqual(r.get_json()['cashier']['id'],1)
  self.assertEqual(self.c.get('/api/products').status_code,200)
 def test_catalog_preview_and_photo_scope(self):
  self.assertEqual(self.c.get('/api/products/1/photo').status_code,401)
  r=self.branch();self.assertEqual(r.status_code,200);self.assertTrue(r.get_json()['products']);self.assertNotIn('password',r.get_json()['branch'])
  # A photo may be viewed, but an employee is still required for operations.
  self.assertEqual(self.c.get('/api/products/1/photo').status_code,404)
  self.assertEqual(self.c.get('/api/customers').status_code,401)
  self.assertEqual(self.c.post('/api/quote',json=self.f.data(),headers=self.h).status_code,401)
  with self.c.session_transaction() as session:session['branch_login']=dict(session['branch_login'],expires=time.time()-1)
  self.assertEqual(self.c.get('/api/products/1/photo').status_code,401)
 def test_wrong_employee_expiry_and_branch_binding(self):
  self.f.post('branches',dict(name='Otra',address='Otra',password='5678',next_invoice=1))
  self.branch();self.assertEqual(self.post(stage='EMPLOYEE',employee_code='MAL').status_code,401)
  self.assertIsNone(self.c.get('/api/auth/state').get_json()['role'])
  self.assertEqual(self.employee(branch_id=2).status_code,401)
  self.branch()
  with self.c.session_transaction() as s:s['branch_login']=dict(s['branch_login'],expires=time.time()-1)
  self.assertEqual(self.employee().status_code,401)
  app.FAILURES.clear();self.branch();r=self.employee();self.assertEqual(r.status_code,200,r.data)
 def test_changed_password_invalidates_step_and_session(self):
  self.branch();r=self.f.c.patch('/api/branches/1',json=dict(password='nueva'),headers=self.h);self.assertEqual(r.status_code,200,r.data)
  self.assertEqual(self.employee().status_code,401)
  self.assertEqual(self.branch().status_code,401)
  self.assertEqual(self.post(stage='BRANCH',password='nueva').status_code,200)
  self.assertEqual(self.employee().status_code,200)
  self.f.c.patch('/api/branches/1',json=dict(password='otra'),headers=self.h)
  self.assertIsNone(self.c.get('/api/auth/state').get_json()['role'])
 def test_rate_limit_and_administrator_unchanged(self):
  for n in range(5):self.assertEqual(self.post(stage='BRANCH',password='mal').status_code,401)
  self.assertEqual(self.branch().status_code,429)
  r=self.c.post('/api/auth/login',json=dict(role='admin',email='frychickencompany@gmail.com',password='FRY2026'),headers=self.h);self.assertEqual(r.status_code,200,r.data)
if __name__=='__main__':unittest.main()
