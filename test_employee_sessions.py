import unittest,concurrent.futures,json,base64,tempfile
from pathlib import Path
from unittest.mock import patch
import test_operations as fixture
from test_central import Remote
import app,central_gateway,employee_sessions,cash_safety,central_transport,backup_protocol as protocol

class EmployeeSessionTests(unittest.TestCase):
 def setUp(self):
  cash_safety.CLOSING.clear()
  self.f=fixture.OperationsTests('test_permissions_and_validation');self.f._testMethodName='sessions62_'+self._testMethodName;self.f.setUp()
  self.f.post('cash',dict(action='close',branch_id=1,shift_id=1,counted=500))
  self.f.post('admin/employees',dict(name='OTRO EMPLEADO',identity='0801199012346',first_name='OTRO',first_surname='EMPLEADO',access_code='OTRO123'))
  self.gateway=central_gateway.create_gateway(app.app,app.connect);self.remotes=[]
  for n in [2,3]:
   response=self.f.post('admin/terminals',dict(name='PC '+str(n),branch_id=1,employee_ids=[1,2])).get_json()
   self.remotes.append(Remote(self.gateway,response['id'],response['key']))
  self.pc1=app.app.test_client()
 def primary(self,stage='EMPLOYEE',code='ANA123'):
  return self.pc1.post('/api/auth/login',json=dict(role='local',branch_id=1,stage=stage,password='1234',employee_code=code),headers=self.f.h)
 def login_primary(self,code='ANA123'):
  self.assertEqual(self.primary('BRANCH').status_code,200)
  return self.primary(code=code)
 def login_remote(self,index=0,code='ANA123'):
  return self.remotes[index].request('/api/auth/login',dict(role='local',branch_id=1,employee_code=code))
 def test_pc1_blocks_other_pc_with_clear_name(self):
  self.assertEqual(self.login_primary().status_code,200)
  status,result=self.login_remote();self.assertEqual(status,409);self.assertEqual(result['active_pc'],'PC 1')
  self.assertEqual(self.pc1.get('/api/auth/state').get_json()['role'],'local')
 def test_remote_pc_blocks_pc1(self):
  self.assertEqual(self.login_remote()[0],200)
  r=self.login_primary();self.assertEqual(r.status_code,409);self.assertEqual(r.get_json()['active_pc'],'PC 2')
 def test_different_employees_can_use_different_pcs(self):
  self.assertEqual(self.login_primary().status_code,200)
  self.assertEqual(self.login_remote(code='OTRO123')[0],200)
  status,result=self.login_remote(1);self.assertEqual(status,409);self.assertEqual(result['active_pc'],'PC 1')
 def test_simultaneous_login_has_one_winner(self):
  self.assertEqual(self.primary('BRANCH').status_code,200)
  remote=self.remotes[0];self.assertEqual(remote.request('/api/auth/login',dict(role='local',branch_id=1,stage='BRANCH',password='1234'))[0],200)
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
   a=pool.submit(lambda:self.primary().status_code)
   b=pool.submit(lambda:remote.request('/api/auth/login',dict(role='local',branch_id=1,stage='EMPLOYEE',employee_code='ANA123'))[0])
   self.assertEqual(sorted([a.result(),b.result()]),[200,409])
  with app.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM employee_sessions WHERE employee_id=1').fetchone()[0],1)
 def test_logout_releases_employee_for_other_pc(self):
  self.assertEqual(self.login_primary().status_code,200)
  self.assertEqual(self.pc1.post('/api/auth/logout',json={},headers=self.f.h).status_code,200)
  self.assertEqual(self.login_remote()[0],200)
 def test_lost_cookie_preserves_lock_but_same_pc_can_resume(self):
  self.assertEqual(self.login_primary().status_code,200);old_cookie=self.pc1.get_cookie('session').value
  self.pc1=app.app.test_client();self.assertEqual(self.login_remote()[0],409)
  self.assertEqual(self.login_primary().status_code,200)
  stale=app.app.test_client();stale.set_cookie('session',old_cookie)
  self.assertEqual(stale.get('/api/products').status_code,401)
 def test_open_cash_blocks_logout_and_admin_release(self):
  self.assertEqual(self.login_primary().status_code,200)
  r=self.pc1.post('/api/cash',json=dict(action='open',branch_id=1,opening=100),headers=self.f.h);self.assertEqual(r.status_code,200)
  self.assertEqual(self.pc1.post('/api/auth/logout',json={},headers=self.f.h).status_code,400)
  self.assertEqual(self.f.post('admin/employees/1/release-session',{}).status_code,400)
  self.assertEqual(self.login_remote()[0],409)
  state=self.f.c.get('/api/admin/employees').get_json()[0]['active_session'];self.assertTrue(state['open_cash']);self.assertEqual(state['pc'],'PC 1')
 def test_admin_can_release_closed_session_and_old_cookie_is_revoked(self):
  self.assertEqual(self.login_primary().status_code,200)
  self.assertEqual(self.f.post('admin/employees/1/release-session',{}).status_code,200)
  self.assertEqual(self.login_remote()[0],200)
  self.assertEqual(self.pc1.get('/api/products').status_code,401)
  status,_=self.remotes[0].request('/api/admin/employees/1/release-session',{});self.assertEqual(status,403)
 def test_admin_role_switch_does_not_free_an_open_cash_reservation(self):
  self.assertEqual(self.login_primary().status_code,200)
  self.pc1.post('/api/cash',json=dict(action='open',branch_id=1,opening=100),headers=self.f.h)
  r=self.pc1.post('/api/auth/login',json=dict(role='admin',email='frychickencompany@gmail.com',password='FRY2026'),headers=self.f.h);self.assertEqual(r.status_code,200)
  self.assertEqual(self.login_remote()[0],409)
 def test_normal_pc_close_releases_only_its_employee_session(self):
  self.assertEqual(self.login_remote()[0],200);remote=self.remotes[0]
  cfg=dict(mode='client',terminal_id=remote.tid,key=remote.key,server_url='http://127.0.0.1:5060')
  def relay(cfg,packet,timeout=5):
   wire=protocol.seal(cfg['key'],json.dumps(packet).encode());headers=protocol.headers(cfg['key'],'POST','/rpc',wire);headers['X-FRY-Terminal']=str(cfg['terminal_id'])
   response=self.gateway.test_client().post('/rpc',data=wire,headers=headers);self.assertEqual(response.status_code,200)
   return json.loads(protocol.unseal(cfg['key'],response.data))
  with tempfile.TemporaryDirectory() as folder,patch.object(central_transport,'call',side_effect=relay):
   self.assertTrue(cash_safety.native_guard(cfg,Path(folder)/'data',final=True)['can_exit'])
  self.assertEqual(self.login_primary().status_code,200)
  self.assertIsNone(remote.request('/api/auth/state')[1]['role'])

if __name__=='__main__':unittest.main()
