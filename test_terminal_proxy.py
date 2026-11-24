import unittest,json,tempfile,threading,uuid
from pathlib import Path
from unittest.mock import patch
from werkzeug.serving import make_server
import test_central as fixtures
import app,terminal_proxy
from central_transport import CentralUnavailable

class ProxyRecoveryTests(unittest.TestCase):
 def setUp(self):
  self.case=fixtures.CentralTests('test_retry_no_duplicate_and_cash_isolated');self.case._testMethodName=self._testMethodName;self.case.setUp()
  self.server=make_server('127.0.0.1',0,self.case.gateway,threaded=True);threading.Thread(target=self.server.serve_forever,daemon=True).start()
  r=self.case.remotes[0];self.cfg=dict(server_url=f'http://127.0.0.1:{self.server.server_port}',terminal_id=r.tid,key=r.key);self.temp=tempfile.TemporaryDirectory(dir=app.DATA);self.folder=Path(self.temp.name)
  self.proxy=terminal_proxy.create_proxy(self.cfg,self.folder);self.client=self.proxy.test_client();self.headers={'X-POS-Token':app.TOKEN};self.login()
 def tearDown(self):self.server.shutdown();self.server.server_close();self.temp.cleanup()
 def post(self,path,d):return self.client.post(path,json=d,headers=self.headers)
 def login(self):
  r=self.post('/api/auth/login',dict(role='local',branch_id=1,employee_code='ANA123'));self.assertEqual(r.status_code,200,r.data);self.assertEqual(r.content_type,'application/json')
 def test_lost_reply_recovers_same_invoice_after_restart(self):
  real=terminal_proxy.call
  def lost(cfg,p):
   r=real(cfg,p)
   if p['path']=='/api/invoices':raise CentralUnavailable('Respuesta perdida después de guardar')
   return r
  data=self.case.base.data('lost-reply')
  with patch.object(terminal_proxy,'call',side_effect=lost):r=self.post('/api/invoices',data)
  self.assertEqual(r.status_code,503,r.data);self.assertTrue((self.folder/'cobro-pendiente.json').exists())
  self.assertEqual(self.post('/api/invoices',self.case.base.data('different')).status_code,409)
  self.client=terminal_proxy.create_proxy(self.cfg,self.folder).test_client();self.login()
  recovered=self.client.get('/api/local-pending/result');self.assertEqual(recovered.status_code,200,recovered.data);self.assertTrue(recovered.get_json()['found']);self.assertTrue((self.folder/'cobro-pendiente.json').exists());self.assertEqual(self.post('/api/local-pending/ack',dict(invoice_id=recovered.get_json()['invoice']['id'])).status_code,200);self.assertFalse((self.folder/'cobro-pendiente.json').exists())
  with app.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM invoices').fetchone()[0],1);self.assertEqual(c.execute('SELECT COUNT(*) FROM print_jobs').fetchone()[0],2)
 def test_request_never_arrived_retry_or_cancel(self):
  real=terminal_proxy.call
  def lost(cfg,p):
   if p['path']=='/api/invoices':raise CentralUnavailable('Servidor desconectado antes de recibir')
   return real(cfg,p)
  with patch.object(terminal_proxy,'call',side_effect=lost):self.assertEqual(self.post('/api/invoices',self.case.base.data('retry-not-arrived')).status_code,503)
  result=self.client.get('/api/local-pending/result');self.assertFalse(result.get_json()['found'])
  result=self.post('/api/local-pending/retry',{});self.assertEqual(result.status_code,200,result.data);self.assertEqual(self.post('/api/local-pending/ack',dict(invoice_id=result.get_json()['id'])).status_code,200)
  with patch.object(terminal_proxy,'call',side_effect=lost):self.assertEqual(self.post('/api/invoices',self.case.base.data('cancel-not-arrived')).status_code,503)
  result=self.post('/api/local-pending/cancel',{});self.assertEqual(result.status_code,200,result.data);self.assertFalse((self.folder/'cobro-pendiente.json').exists())
  with app.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM invoices').fetchone()[0],1)
 def test_offline_does_not_create_new_local_invoice(self):
  with patch.object(terminal_proxy,'call',side_effect=CentralUnavailable('Máquina 1 apagada')):
   r=self.post('/api/invoices',self.case.base.data('offline'));self.assertEqual(r.status_code,503)
  with app.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM invoices').fetchone()[0],0)
if __name__=='__main__':unittest.main()
