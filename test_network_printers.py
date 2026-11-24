import unittest,socketserver,threading,queue,json,concurrent.futures
from unittest.mock import patch
from pathlib import Path
import network_receipt,network_printers
import test_operations as fixture
import app,print_queue,terminals
from datetime import date,timedelta
import fiscal

class Server:
 def __enter__(self):
  self.data=queue.Queue();target=self.data
  class Handler(socketserver.BaseRequestHandler):
   def handle(self):
    self.request.settimeout(5);raw=b''
    while True:
     part=self.request.recv(8192)
     if not part:break
     raw+=part
    target.put(raw)
  self.server=socketserver.ThreadingTCPServer(('127.0.0.1',0),Handler);self.server.daemon_threads=True
  threading.Thread(target=self.server.serve_forever,daemon=True).start();self.options=network_printers.validate(dict(host='127.0.0.1',port=self.server.server_address[1]));return self
 def __exit__(self,*args):self.server.shutdown();self.server.server_close()

class TextTests(unittest.TestCase):
 def test_no_images_controls_or_logo(self):
  html='<div>Factura ñ áéíóú<img src="logo.png"><script>NO</script><p>Cliente \x1b@ \x1dV</p></div>'
  text=network_receipt.document_text(html,42)
  self.assertIn('ñ áéíóú',text);self.assertNotIn('logo',text);self.assertNotIn('NO',text);self.assertNotIn('\x1b',text);self.assertNotIn('\x1d',text)
  raw=network_receipt.payload(html,network_printers.DEFAULT)
  self.assertIn('ñ áéíóú'.encode('cp850'),raw)
  for graphics in [b'\x1dv0',b'\x1b*',b'\x1c p',b'\x1d(L',b'\x1d(k']:
   self.assertNotIn(graphics,raw)
 def test_long_tables_fit_without_losing_amounts(self):
  html='<table><tr><th>Cant.</th><th>Descripción</th><th>Precio</th><th>Total</th></tr><tr><td>2</td><td>SUPER COMBO FAMILIAR CON REFRESCO Y COMPLEMENTOS</td><td>999,999.99</td><td>1,999,999.98</td></tr></table><table><tr><td>Total de la factura con envío</td><td>1,999,999.98</td></tr></table>'
  for columns in [32,42,48]:
   text=network_receipt.document_text(html,columns)
   self.assertTrue(all(len(line)<=columns for line in text.splitlines()))
   for amount in ['999,999.99','1,999,999.98']:self.assertIn(amount,text)
 def test_text_only_profile_has_no_commands(self):
  raw=network_receipt.payload('<p>PECHUGA Ñ</p>',network_printers.DEFAULT|dict(protocol='plain',encoding='ascii'))
  self.assertIn(b'PECHUGA N',raw);self.assertNotIn(b'\x1b',raw);self.assertNotIn(b'\x1d',raw)
 def test_config_migration_validation_and_discovery(self):
  self.assertEqual(network_printers.normalize(dict(name='Impresora Windows',width=58))['transport'],'windows')
  self.assertEqual(network_printers.normalize(None)['transport'],'network')
  for cfg in [dict(host='http://192.168.1.1'),dict(host='192.168.1.5',port=0),dict(host='192.168.1.5',columns=2)]:
   with self.assertRaises(ValueError):network_printers.validate(cfg)
  with patch.object(network_printers,'probe',side_effect=lambda host,port: str(host).endswith('.2')):
   self.assertEqual(network_printers.discover('192.168.1.0/30'),[dict(host='192.168.1.2',port=9100)])
  with self.assertRaises(ValueError):network_printers.discover('192.168.0.0/16')
 def test_probe_discovery_does_not_send_print_data(self):
  with Server() as server:
   rows=network_printers.discover('127.0.0.1/32',server.options['port'])
   self.assertEqual(len(rows),1);self.assertEqual(server.data.get(timeout=3),b'')

class DurableNetworkTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.OperationsTests('test_permissions_and_validation');self.f._testMethodName='network59_'+self._testMethodName;self.f.setUp()
  r=self.f.post('invoices',self.f.data('network-sale'));self.assertEqual(r.status_code,200,r.data)
 def claim(self,role):
  with app.connect() as c:return print_queue.claim(c,[role])
 def state(self,jid):
  with app.connect() as c:return dict(c.execute('SELECT * FROM print_jobs WHERE id=?',(jid,)).fetchone())
 def test_separate_endpoints_receive_text_and_no_duplicate(self):
  cash=self.claim('cash');kitchen=self.claim('kitchen')
  with Server() as a,Server() as b:
   with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    futures=[pool.submit(network_printers.deliver,row,s.options,app.connect,terminals.REQUEST_LOCK) for row,s in [(cash,a),(kitchen,b)]]
    self.assertTrue(all(f.result()[0] for f in futures))
   receipt=a.data.get(timeout=3);order=b.data.get(timeout=3)
   self.assertIn(b'Factura Original',receipt);self.assertNotIn(b'Factura Original',order)
   self.assertIn(b'PECHUGA',order);self.assertNotIn(b'COMANDA',order)
   self.assertIn(b'100.00',receipt);self.assertIn(b'115.00',receipt)
   folder=Path(__file__).resolve().parents[2]/'v59-tests';folder.mkdir(exist_ok=True)
   (folder/'factura-texto.txt').write_text(network_receipt.document_text(cash['html'],42),encoding='utf-8')
   (folder/'comanda-texto.txt').write_text(network_receipt.document_text(kitchen['html'],42),encoding='utf-8')
  self.assertEqual(self.state(cash['id'])['state'],'SPOOLED');self.assertEqual(self.state(kitchen['id'])['state'],'SPOOLED')
  self.assertIsNone(self.claim('cash'));self.assertIsNone(self.claim('kitchen'))
  with app.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM invoices').fetchone()[0],1)
 def test_connect_failure_is_retryable_without_losing_html(self):
  row=self.claim('cash')
  with patch.object(network_printers.socket,'create_connection',side_effect=ConnectionRefusedError('Sin conexión')):
   ok,_=network_printers.deliver(row,network_printers.DEFAULT|dict(host='127.0.0.1'),app.connect,terminals.REQUEST_LOCK)
  self.assertFalse(ok);result=self.state(row['id']);self.assertEqual(result['state'],'FAILED');self.assertTrue(result['html']);self.assertIn('Sin conexión',result['last_error'])
 def test_partial_send_stays_uncertain_and_is_not_retried(self):
  row=self.claim('cash')
  class BrokenSocket:
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def settimeout(self,*args):pass
   def sendall(self,raw):raise OSError('Corte durante el envío')
  with patch.object(network_printers.socket,'create_connection',return_value=BrokenSocket()):
   ok,_=network_printers.deliver(row,network_printers.DEFAULT|dict(host='127.0.0.1'),app.connect,terminals.REQUEST_LOCK)
  self.assertFalse(ok);self.assertEqual(self.state(row['id'])['state'],'UNCERTAIN');self.assertIsNone(self.claim('cash'))
 def test_cancelled_before_send_sends_no_text(self):
  row=self.claim('cash');self.assertEqual(self.f.post('invoices/1/void',dict(reason='Cancelar antes de imprimir')).status_code,200)
  with Server() as server:
   ok,_=network_printers.deliver(row,server.options,app.connect,terminals.REQUEST_LOCK)
   self.assertFalse(ok);self.assertEqual(server.data.get(timeout=3),b'')
  self.assertEqual(self.state(row['id'])['state'],'CANCELLED')
 def test_fiscal_fields_and_mixed_payments_are_preserved_as_text(self):
  cfg=dict(fiscal.DEFAULT,branch_id=1,enabled=True,legal_name='EMPRESA PRUEBA',commercial_name='FRY CHICKEN',rtn='12345678901234',address='DIRECCION SUCURSAL',head_address='DIRECCION MATRIZ',phone='12345678',email='prueba@example.com',cai='ABCDEF-ABCDEF-ABCDEF-ABCDEF-ABCDEF-AB',establishment='000',point='001',range_start=1,range_end=10,next_number=1,deadline=(date.today()+timedelta(days=10)).isoformat())
  r=self.f.post('admin/fiscal',cfg);self.assertEqual(r.status_code,200,r.data)
  data=self.f.data('native-fiscal',invoice_type='RTN',customer_name='CLIENTE FISCAL',customer_rtn='12345678901235',service='PARA ENVIO',delivery_fee='35',payment_method='Mixto',payments={'Efectivo':'50','Tarjeta':'100','Transferencia':'0'},amount_received='100')
  r=self.f.post('invoices',data);self.assertEqual(r.status_code,200,r.data)
  with app.connect() as c:html=c.execute("SELECT html FROM print_jobs WHERE role='cash' AND source_id=?",(r.get_json()['id'],)).fetchone()[0]
  text=network_receipt.document_text(html,42);compact=''.join(text.split())
  for required in [cfg['cai'],cfg['rtn'],cfg['deadline'],'CLIENTE FISCAL',data['customer_rtn'],'150.00','100.00','50.00','35.00','15.00']:
   self.assertIn(''.join(required.split()),compact)
  self.assertIn('Envío por cuenta de tercero',text)

if __name__=='__main__':unittest.main(verbosity=2)
