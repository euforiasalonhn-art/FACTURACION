import unittest,json
from pathlib import Path
import test_operations as fixture
import app,access_model

class PaymentEntryTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.OperationsTests('test_permissions_and_validation');self.f._testMethodName=self._testMethodName;self.f.setUp()
 def entry(self,key,method,amount,**extra):
  return self.f.post('invoices',self.f.data(key,payment_method=method,payment_entry_version=2,payments={k:amount if k==method else '0.00' for k in ['Efectivo','Tarjeta','Transferencia']},**extra))
 def test_card_and_transfer_require_exact_amount(self):
  for method in ['Tarjeta','Transferencia']:
   for bad in ['',0,'114.99','115.01','-1','abc']:
    r=self.entry('invalid-'+method+str(bad),method,bad);self.assertEqual(r.status_code,400,r.data)
   r=self.entry('valid-'+method,method,'115.00');self.assertEqual(r.status_code,200,r.data)
   self.assertEqual(self.entry('valid-'+method,method,'115.00').get_json(),r.get_json())
  with app.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM invoices').fetchone()[0],2)
 def test_single_method_cannot_hide_a_second_payment(self):
  data=self.f.data('wrong-method',payment_method='Tarjeta',payment_entry_version=2,payments={'Tarjeta':'115','Efectivo':'1','Transferencia':'0'})
  self.assertEqual(self.f.post('invoices',data).status_code,400)
  with app.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM invoices').fetchone()[0],0)
 def test_cash_close_and_access_keep_methods_separate(self):
  self.assertEqual(self.entry('card','Tarjeta','115').status_code,200)
  self.assertEqual(self.entry('transfer','Transferencia','115').status_code,200)
  self.assertEqual(self.entry('cash','Efectivo','115',amount_received='200').status_code,200)
  r=self.f.post('invoices',self.f.data('mixed',payment_method='Mixto',payment_entry_version=2,payments={'Efectivo':'40','Tarjeta':'50','Transferencia':'25'},amount_received='50'));self.assertEqual(r.status_code,200,r.data)
  self.f.post('invoices/1/void',dict(reason='Anulación de tarjeta de prueba'))
  r=self.f.c.get('/api/cash?branch_id=1').get_json()['shift']
  self.assertEqual(r['payments'],{'Efectivo':15500,'Tarjeta':5000,'Transferencia':14000,'Otros':0})
  self.assertEqual(r['live_expected'],65500)
  closed=self.f.post('cash',dict(action='close',branch_id=1,shift_id=r['id'],counted='650'));self.assertEqual(closed.status_code,200,closed.data)
  closed=closed.get_json()['last_closed'];self.assertEqual((closed['expected'],closed['counted'],closed['difference']),(65500,65000,-500))
  p=access_model.build(app.DB);turn=p['tables']['TurnosCaja'][0]['values'];self.assertEqual((turn['EfectivoVentas'],turn['TarjetaVentas'],turn['Transferencias'],turn['Contado']),('155.00','50.00','140.00','650.00'))
  pdf=self.f.c.get('/api/cash/'+str(r['id'])+'/pdf');self.assertEqual(pdf.status_code,200);self.assertTrue(pdf.data.startswith(b'%PDF'))
  target=Path(__file__).resolve().parents[2]/'v56-tests';target.mkdir(exist_ok=True);(target/'cierre-prueba.pdf').write_bytes(pdf.data)
if __name__=='__main__':unittest.main()
