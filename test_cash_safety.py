import unittest,json,base64,tempfile
from pathlib import Path
from datetime import date
from unittest.mock import patch
import test_operations as fixture
import app,cash_safety,accounting,central_transport

class CashSafetyTests(unittest.TestCase):
 def setUp(self):
  cash_safety.CLOSING.clear();self.addCleanup(cash_safety.CLOSING.clear)
  self.f=fixture.OperationsTests('test_permissions_and_validation');self.f._testMethodName='cash60_'+self._testMethodName;self.f.setUp()
  with app.connect() as c:c.execute("UPDATE cash_sessions SET opened_at='2026-11-15T09:00:00-06:00'")
 def test_previous_day_blocks_sales_and_requires_real_close(self):
  with patch.object(cash_safety,'today',return_value=date(2026,11,16)):
   r=self.f.post('invoices',self.f.data('next-day'));self.assertEqual(r.status_code,400,r.data);self.assertIn('cuadrar',r.get_json()['error'])
   shift=self.f.c.get('/api/cash?branch_id=1').get_json()['shift'];self.assertTrue(shift['must_close']);self.assertEqual(shift['business_date'],'2026-11-15')
   self.assertEqual(self.f.post('cash',dict(action='open',branch_id=1,opening=500)).status_code,400)
   self.assertEqual(self.f.post('cash',dict(action='close',branch_id=1,shift_id=1,counted=500)).status_code,200)
   with patch.object(accounting,'now',return_value='2026-11-16T09:10:00-06:00'):
    self.assertEqual(self.f.post('cash',dict(action='open',branch_id=1,opening=500)).status_code,200)
   self.assertEqual(self.f.post('invoices',self.f.data('new-day-valid')).status_code,200)
   with app.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM invoices').fetchone()[0],1)
 def test_employee_cannot_logout_until_cash_is_counted(self):
  self.f.post('auth/logout',{});self.assertEqual(self.f.post('auth/login',dict(role='local',branch_id=1,employee_code='ANA123')).status_code,200)
  self.assertEqual(self.f.post('auth/logout',{}).status_code,400)
  self.assertEqual(self.f.c.get('/api/auth/state').get_json()['role'],'local')
  self.assertEqual(self.f.post('cash',dict(action='close',branch_id=1,shift_id=1,counted=500)).status_code,200)
  self.assertEqual(self.f.post('auth/logout',{}).status_code,200)
 def test_branch_change_cannot_hide_an_open_cash_session(self):
  self.assertEqual(self.f.post('branches',dict(name='Otra',address='Otra',password='1234',next_invoice=1)).status_code,200)
  self.assertEqual(self.f.post('cash',dict(action='open',branch_id=2,opening=500)).status_code,400)
 def test_primary_exit_checks_all_sessions_and_fences_new_writes(self):
  state=cash_safety.native_guard(dict(mode='server'),app.DATA,app.connect);self.assertFalse(state['can_exit'])
  self.f.post('cash',dict(action='close',branch_id=1,shift_id=1,counted=500))
  state=cash_safety.native_guard(dict(mode='server'),app.DATA,app.connect,True);self.assertTrue(state['can_exit']);self.assertTrue(cash_safety.CLOSING.is_set())
  self.assertEqual(self.f.post('cash',dict(action='open',branch_id=1,opening=500)).status_code,503)
 def test_full_synchronous_and_timezone(self):
  with app.connect() as c:self.assertEqual(c.execute('PRAGMA synchronous').fetchone()[0],3)
  self.assertEqual(cash_safety.business_date('2026-11-16T01:00:00+00:00'),'2026-11-15')
 def test_confirmed_sale_can_be_recovered_on_next_day_without_duplicate(self):
  with patch.object(cash_safety,'today',return_value=date(2026,11,15)):
   first=self.f.post('invoices',self.f.data('confirmed-yesterday'));self.assertEqual(first.status_code,200)
  with patch.object(cash_safety,'today',return_value=date(2026,11,16)):
   recovered=self.f.post('invoices',self.f.data('confirmed-yesterday'));self.assertEqual(recovered.get_json(),first.get_json())
   self.assertEqual(self.f.post('employee-meals',self.f.data('old-meal',employee_id=1,cost='40')).status_code,400)
  with app.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM invoices').fetchone()[0],1)
 def test_terminal_exit_needs_central_confirmation_and_pending_resolution(self):
  with tempfile.TemporaryDirectory() as folder:
   data=Path(folder)/'data';data.mkdir();cfg=dict(mode='client',terminal_id=5,key='test',server_url='http://127.0.0.1:5060')
   answer=dict(status=200,body=base64.b64encode(json.dumps(dict(can_exit=True)).encode()).decode())
   with patch.object(central_transport,'call',return_value=answer):self.assertTrue(cash_safety.native_guard(cfg,data)['can_exit'])
   pending=Path(folder)/'terminal-5/cobro-pendiente.json';pending.parent.mkdir();pending.write_text('{}')
   with patch.object(central_transport,'call',side_effect=AssertionError('No debe salir con pendiente')):self.assertFalse(cash_safety.native_guard(cfg,data)['can_exit'])

if __name__=='__main__':unittest.main()
