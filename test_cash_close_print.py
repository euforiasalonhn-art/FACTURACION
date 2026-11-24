import unittest,uuid,json
import test_operations as fixture
import app,print_queue,network_receipt
from test_central import Remote
import central_gateway

class CashClosePrintTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.OperationsTests('test_permissions_and_validation');self.f._testMethodName='close63_'+self._testMethodName;self.f.setUp()
 def request(self,key=None,copy=False):return self.f.post('cash/1/print',dict(request_id=key or str(uuid.uuid4()),copy=copy))
 def close(self):
  for key,method in [('cash','Efectivo'),('card','Tarjeta'),('transfer','Transferencia')]:
   r=self.f.post('invoices',self.f.data(key,payment_method=method,amount_received=200 if method=='Efectivo' else 0));self.assertEqual(r.status_code,200,r.data)
  r=self.f.post('cash',dict(action='close',branch_id=1,shift_id=1,counted=615));self.assertEqual(r.status_code,200,r.data)
 def getjob(self,jid):
  with app.connect() as c:return dict(c.execute('SELECT * FROM print_jobs WHERE id=?',(jid,)).fetchone())
 def test_requires_saved_close_and_valid_request(self):
  self.assertEqual(self.request().status_code,400)
  self.close();self.assertEqual(self.request('bad').status_code,400)
 def test_cash_destination_and_complete_summary_without_invoice_changes(self):
  self.close();r=self.request();self.assertEqual(r.status_code,200,r.data);job=self.getjob(r.get_json()['id'])
  self.assertEqual((job['role'],job['source_kind'],job['source_id'],job['state']),('cash','CASH_CLOSE',1,'PENDING'))
  text=network_receipt.document_text(job['html'],42)
  for value in ['CIERRE DE CAJA #1','PC 1','Efectivo cobrado','Tarjeta','Transferencia','L 345.00','L 615.00','Caja cuadrada']:
   self.assertIn(value,text)
  self.assertNotIn('<img',job['html']);self.assertNotIn('COPIA',text)
  with app.connect() as c:
   self.assertEqual(c.execute('SELECT COUNT(*) FROM invoices').fetchone()[0],3)
   self.assertEqual(c.execute('SELECT next_invoice FROM branches WHERE id=1').fetchone()[0],4)
 def test_double_click_and_pending_copy_reuse_one_job(self):
  self.close();key=str(uuid.uuid4());first=self.request(key).get_json()
  self.assertEqual(self.request(key).get_json()['id'],first['id'])
  self.assertEqual(self.request().get_json()['id'],first['id'])
  self.assertEqual(self.request(copy=True).get_json()['id'],first['id'])
  with app.connect() as c:self.assertEqual(c.execute("SELECT COUNT(*) FROM print_jobs WHERE source_kind='CASH_CLOSE'").fetchone()[0],1)
 def test_sent_and_uncertain_jobs_require_explicit_copy(self):
  self.close();jid=self.request().get_json()['id']
  with app.connect() as c:c.execute("UPDATE print_jobs SET state='UNCERTAIN' WHERE id=?",(jid,))
  self.assertTrue(self.request().get_json()['needs_copy'])
  copy=self.request(copy=True);self.assertEqual(copy.status_code,200);self.assertNotEqual(copy.get_json()['id'],jid)
  self.assertIn('COPIA',self.getjob(copy.get_json()['id'])['html'])
 def test_manual_print_works_when_automatic_printing_is_off(self):
  self.close()
  with app.connect() as c:app.save_setting(c,'printer',dict(automatic=False,width=80,name=''))
  result=self.request().get_json();self.assertEqual(self.getjob(result['id'])['state'],'PENDING')
 def test_invoice_reprint_never_reuses_close_with_same_numeric_id(self):
  self.close();closeid=self.request().get_json()['id']
  with app.connect() as c:c.execute("UPDATE print_jobs SET state='SPOOLED' WHERE source_kind='SALE'")
  r=self.f.post('printing/reprint',dict(role='cash',source_id=1,request_id=str(uuid.uuid4())));self.assertEqual(r.status_code,200,r.data)
  self.assertNotEqual(r.get_json()['id'],closeid);self.assertEqual(self.getjob(r.get_json()['id'])['source_kind'],'SALE')
  jobs=self.f.c.get('/api/printing/jobs').get_json();self.assertTrue(any(r['source_kind']=='CASH_CLOSE' for r in jobs))
 def test_other_pc_cannot_print_this_close(self):
  self.close()
  self.f.post('admin/employees',dict(name='OTRO EMPLEADO',identity='0801199012346',first_name='OTRO',first_surname='EMPLEADO',access_code='OTRO123'))
  cfg=self.f.post('admin/terminals',dict(name='PC 2',branch_id=1,employee_ids=[2])).get_json()
  r=Remote(central_gateway.create_gateway(app.app,app.connect),cfg['id'],cfg['key'])
  self.assertEqual(r.request('/api/auth/login',dict(role='local',branch_id=1,employee_code='OTRO123'))[0],200)
  self.assertEqual(r.request('/api/cash/1/print',dict(request_id=str(uuid.uuid4())))[0],403)

if __name__=='__main__':unittest.main()
