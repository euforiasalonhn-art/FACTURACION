from contextlib import closing
import json,threading,tempfile,gzip,sqlite3,base64,time
from pathlib import Path
from unittest.mock import patch
from werkzeug.serving import make_server
from test_operations import OperationsTests
import app,network_backup as net,backup_receiver,backup_protocol as protocol,cancellation,commerce
class NetworkBackupTests(OperationsTests):
 def setUp(self):
  super().setUp();self.remote_dir=tempfile.TemporaryDirectory(dir=app.DATA);self.key='test-key-'+'A'*40
  self.receiver=backup_receiver.create_receiver(self.remote_dir.name,self.key);self.server=make_server('127.0.0.1',0,self.receiver,threaded=True);threading.Thread(target=self.server.serve_forever,daemon=True).start();self.url=f'http://127.0.0.1:{self.server.server_port}'
  r=self.post('admin/network-backup',dict(enabled=True,url=self.url,key=self.key));self.assertEqual(r.status_code,200,r.data);self.assertTrue(r.get_json()['status']['online'],r.data)
  with app.connect() as c:self.instance=net.value(c,'network_instance')
 def tearDown(self):self.server.shutdown();self.remote_dir.cleanup()
 def remote_database(self):
  p=Path(self.remote_dir.name)/self.instance;manifest=json.loads((p/'manifest.json').read_text('utf-8'));doc,_,_=protocol.validate((p/manifest['file']).read_bytes());c=sqlite3.connect(':memory:');c.row_factory=sqlite3.Row;c.deserialize(base64.b64decode(doc['database_base64']));return c,manifest
 def test_confirm_before_local_commit_and_restore(self):
  real=net.synchronize;seen=[]
  def inspect(c,data):
   result=real(c,data)
   if c.in_transaction and c.execute('SELECT COUNT(*) FROM invoices').fetchone()[0]:
    remote,manifest=self.remote_database();seen.append(remote.execute('SELECT COUNT(*) FROM invoices').fetchone()[0]);remote.close()
    # La venta todavía no está confirmada en otra conexión local.
    with sqlite3.connect(app.DB) as other:self.assertEqual(other.execute('SELECT COUNT(*) FROM invoices').fetchone()[0],0)
   return result
  with patch.object(net,'synchronize',side_effect=inspect):r=self.post('invoices',self.data())
  self.assertEqual(r.status_code,200,r.data);self.assertIn(1,seen)
  remote,m=self.remote_database();self.assertEqual(remote.execute('SELECT COUNT(*) FROM invoices').fetchone()[0],1);self.assertEqual(m['last_invoice']['number'],1)
  self.assertIsNotNone(remote.execute("SELECT name FROM sqlite_master WHERE name='sales_goals'").fetchone());remote.close()
  retry=self.post('invoices',self.data());self.assertEqual(retry.get_json()['id'],r.get_json()['id'])
 def test_offline_blocks_without_invoice_and_recovers(self):
  real=net.remote
  with patch.object(net,'remote',side_effect=net.BackupUnavailable('Receptor apagado')):
   r=self.post('invoices',self.data());self.assertEqual(r.status_code,503,r.data)
  with app.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM invoices').fetchone()[0],0)
  self.assertEqual(self.post('invoices',self.data()).status_code,200)
 def test_disconnect_before_commit_rolls_back(self):
  real=net.remote
  def fail(cfg,method,path,body=b'',previous=''):
   if method=='POST':raise net.BackupUnavailable('Desconectado antes de confirmar')
   return real(cfg,method,path,body,previous)
  with patch.object(net,'remote',side_effect=fail):r=self.post('invoices',self.data())
  self.assertEqual(r.status_code,503,r.data)
  with app.connect() as c:
   self.assertEqual(c.execute('SELECT COUNT(*) FROM invoices').fetchone()[0],0)
   self.assertEqual(c.execute('SELECT next_invoice FROM branches').fetchone()[0],1)
 def test_emergency_same_totp_replay_and_resync(self):
  secret='JBSWY3DPEHPK3PXP';step=int(time.time()//300)
  # DPAPI se prueba en Windows con la misma protección usada por anulación.
  with app.connect() as c:app.save_setting(c,'cancellation_totp',dict(secret=commerce.protect(secret),period=300,used_step=-1))
  code=cancellation.totp(secret)
  with patch.object(net,'remote',side_effect=net.BackupUnavailable('PC apagada')):
   self.assertEqual(self.post('network-backup/emergency',dict(code='000000' if code!='000000' else '000001',reason='Equipo dañado')).status_code,403)
   r=self.post('network-backup/emergency',dict(code=code,reason='Equipo dañado'));self.assertEqual(r.status_code,200,r.data)
   self.assertEqual(self.post('network-backup/emergency',dict(code=code,reason='Equipo dañado')).status_code,409)
   self.assertEqual(self.post('invoices',self.data()).status_code,200)
  r=self.post('network-backup/check',{});self.assertTrue(r.get_json()['online'],r.data)
  remote,m=self.remote_database();self.assertEqual(m['invoice_count'],1);remote.close()
  with self.c.session_transaction() as s:s['backup_override_until']=time.time()-1
  with patch.object(net,'remote',side_effect=net.BackupUnavailable('Apagado')):self.assertEqual(self.post('invoices',self.data('b')).status_code,503)
 def test_restore_new_pc_and_preserve_history(self):
  from restaurar_respaldo import restore
  self.post('invoices',self.data())
  self.post('invoices',self.data('second'))
  remote,m=self.remote_database();remote.close()
  source=Path(self.remote_dir.name)/self.instance/m['file']
  with tempfile.TemporaryDirectory(dir=app.DATA) as new:
   with self.assertRaises(ValueError):restore(source,new,'incorrecta')
   last=restore(source,new,'FRY2026');self.assertEqual(last[0],2)
   with closing(sqlite3.connect(Path(new)/'fry_chicken.db')) as c:
    self.assertEqual(c.execute('SELECT COUNT(*) FROM invoices').fetchone()[0],2)
    self.assertEqual(c.execute('SELECT next_invoice FROM branches WHERE id=1').fetchone()[0],3)
   with self.assertRaises(ValueError):restore(source,new,'FRY2026')

 def test_alternative_connection_and_encryption(self):
  r=self.post('admin/network-backup',dict(enabled=True,url='http://127.0.0.1:1',fallback_url=self.url,key=''))
  self.assertEqual(r.status_code,200,r.data);self.assertTrue(r.get_json()['status']['online'],r.data)
  self.assertEqual(self.post('invoices',self.data()).status_code,200)
  text=b'FACTURA PRIVADA 123'
  wire=protocol.seal(self.key,text);self.assertNotIn(text,wire);self.assertEqual(protocol.unseal(self.key,wire),text)
  with self.assertRaises(ValueError):protocol.unseal('otra clave',wire)
  with self.assertRaises(ValueError):protocol.unseal(self.key,wire[:-8]+b'00000000')

 def test_auth_integrity_and_no_remote_regression(self):
  client=self.receiver.test_client();self.assertEqual(client.get('/status/'+self.instance).status_code,403)
  self.post('invoices',self.data());remote,m=self.remote_database();remote.close()
  with app.connect() as c:raw=net.document(c,app.DATA)
  doc=json.loads(raw);bad=sqlite3.connect(':memory:');bad.deserialize(base64.b64decode(doc['database_base64']));bad.execute('DELETE FROM invoices');bad.commit();doc['database_base64']=base64.b64encode(bad.serialize()).decode();bad.close()
  blob=gzip.compress(json.dumps(doc).encode());path='/snapshot/'+self.instance;wire=protocol.seal(self.key,blob);h=protocol.headers(self.key,'POST',path,wire,m['sha256']);h['X-FRY-Previous']=m['sha256']
  r=client.post(path,data=wire,headers=h);self.assertEqual(r.status_code,409,r.data)
  remote,m=self.remote_database();self.assertEqual(m['invoice_count'],1);remote.close()
if __name__=='__main__':
 import unittest;unittest.main()
