import unittest,json,io
import test_operations as fixture
import app,sar_reports
from openpyxl import load_workbook
class DeliveryTests(unittest.TestCase):
 def setUp(self):
  self.base=fixture.OperationsTests('test_sale_command_goals_cancellation_and_retry');self.base._testMethodName=self._testMethodName;self.base.setUp();self.c=self.base.c
 def post(self,path,d):return self.base.post(path,d)
 def data(self,**kw):return self.base.data(service='PARA ENVIO',delivery_fee='35',**kw)
 def test_invoice_reports_goals_sar_and_cash(self):
  self.base.goal();r=self.post('invoices',self.data(payment_method='Efectivo',amount_received='200'));self.assertEqual(r.status_code,200,r.data)
  inv=self.c.get('/api/invoices/'+str(r.get_json()['id'])).get_json();self.assertEqual(inv['total'],15000);self.assertEqual(inv['snapshot']['sales_total'],11500);self.assertEqual(inv['tax_15'],1500);self.assertIn('Envío por cuenta de tercero',inv['receipt_html'])
  book=self.c.get('/api/accounting?scope=all').get_json();self.assertEqual(book['totals']['total'],11500);self.assertEqual(book['totals']['delivery_fee'],3500);self.assertEqual(book['totals']['collected_total'],15000)
  self.assertEqual(self.c.get('/api/cash?branch_id=1').get_json()['shift']['live_expected'],65000)
  self.assertEqual(self.c.get('/api/goals').get_json()[0]['sales'],11500)
  html=self.c.get('/api/kitchen-orders/'+str(r.get_json()['kitchen_id'])).get_json()['html'];self.assertNotIn('>NOTAS<',html);self.assertEqual(html.count('PARA ENVIO'),1)
  self.post('invoices/1/void',dict(reason='Pedido cancelado'));self.assertEqual(self.c.get('/api/accounting?scope=all').get_json()['totals']['delivery_fee'],0);self.assertEqual(self.c.get('/api/goals').get_json()[0]['sales'],0)
 def test_all_cards_mixed_and_exports(self):
  for key,kw in [('card',{}),('mixed',dict(payment_method='Mixto',amount_received='110',payments=dict(Efectivo=110,Tarjeta=40,Transferencia=0)))]:
   r=self.post('invoices',self.data(key=key,**kw));self.assertEqual(r.status_code,200,r.data)
  data=self.c.get('/api/accounting/sar?scope=fiscal&payment=Efectivo&type=RTN').get_json();self.assertEqual(len(data['rows']),2);self.assertEqual(data['total_gravado_sin_impuesto'],20000);self.assertTrue(all(not r['documento_fiscal'] for r in data['rows']));self.assertEqual({r['pago'] for r in data['rows']},{'Tarjeta','Mixto'})
  for r in self.c.get('/api/reports').get_json():self.assertEqual(sum(r['sales_payments'].values()),11500);self.assertEqual(sum(r['delivery_payments'].values()),3500)
  export=self.c.get('/api/accounting/sar/export/xlsx?scope=fiscal');self.assertEqual(export.status_code,200,export.data[:100]);wb=load_workbook(io.BytesIO(export.data));self.assertEqual(wb['Detalle sin impuesto'].max_row,3)
  self.assertEqual(self.c.get('/api/accounting/sar/export/pdf?scope=fiscal').status_code,200)
 def test_bad_fee_modes_quote_and_non_delivery(self):
  for fee in [-1,'nan','texto']:
   d=self.base.data(service='ENVIO',delivery_fee=fee);self.assertEqual(self.post('invoices',d).status_code,400);self.assertEqual(self.post('quote',d).status_code,400)
  self.assertEqual(self.post('invoices',self.base.data(service='COMER AQUI',delivery_fee=10)).status_code,400)
  for mode in ['COMER AQUI','PARA LLEVAR']:
   r=self.post('invoices',self.base.data(mode,service=mode));self.assertEqual(r.status_code,200,r.data)
   html=self.c.get('/api/kitchen-orders/'+str(r.get_json()['kitchen_id'])).get_json()['html'];self.assertEqual(html.count(mode),1)
  q=self.post('quote',self.data()).get_json();self.assertEqual(q['total'],15000);self.assertEqual(q['delivery_fee'],3500)
 def test_free_meal_has_no_delivery_charge(self):
  d=self.base.data(employee_id=1,employee_meal=True,service='ENVIO',delivery_fee=5)
  self.assertEqual(self.post('quote',d).status_code,400);self.assertEqual(self.post('employee-meals',d).status_code,400)
if __name__=='__main__':unittest.main()
