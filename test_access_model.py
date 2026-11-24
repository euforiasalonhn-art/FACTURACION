import unittest,json
from decimal import Decimal
import test_operations as fixture
import app,access_model

class AccessProjectionTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.OperationsTests('test_permissions_and_validation');self.f._testMethodName=self._testMethodName;self.f.setUp()
 def records(self,p,table):return [r['values'] for r in p['tables'][table]]
 def test_delivery_and_mixed_payments_reconcile(self):
  d=self.f.data('access-mixto',service='PARA ENVIO',delivery_fee='35',payment_method='Mixto',payments={'Efectivo':'50','Tarjeta':'100','Transferencia':'0'},amount_received='100')
  result=self.f.post('invoices',d);self.assertEqual(result.status_code,200,result.data)
  p=access_model.build(app.DB);f=self.records(p,'Facturas')[0]
  self.assertEqual((f['VentaProductos'],f['Envio'],f['TotalCobrado']),('115.00','35.00','150.00'))
  self.assertEqual((f['Efectivo'],f['Tarjeta'],f['Cambio']),('50.00','100.00','50.00'))
  rows=self.records(p,'PagosFactura');self.assertEqual(sum(Decimal(r['Cobrado']) for r in rows),Decimal('150'))
  self.assertEqual(sum(Decimal(r['Productos']) for r in rows),Decimal('115'));self.assertEqual(sum(Decimal(r['Envio']) for r in rows),Decimal('35'))
  shift=self.records(p,'TurnosCaja')[0];self.assertEqual(shift['EsperadoActual'],'550.00')
 def test_void_updates_same_document(self):
  r=self.f.post('invoices',self.f.data('access-void'));self.assertEqual(r.status_code,200)
  before=access_model.build(app.DB);self.assertEqual(self.f.post('invoices/1/void',dict(reason='Prueba de anulación contable')).status_code,200)
  after=access_model.build(app.DB);self.assertEqual(len(after['tables']['Facturas']),1)
  self.assertEqual(self.records(after,'Facturas')[0]['Estado'],'ANULADA');self.assertEqual(len(after['tables']['NotasCredito']),0)
  self.assertNotEqual(before['tables']['Facturas'][0]['hash'],after['tables']['Facturas'][0]['hash'])
 def test_meal_is_cost_not_sale_or_cash(self):
  result=self.f.post('employee-meals',self.f.data('access-meal',employee_id=1,cost='40'));self.assertEqual(result.status_code,200,result.data)
  p=access_model.build(app.DB);self.assertEqual(p['tables']['Facturas'],[])
  m=self.records(p,'AlmuerzosEmpleado')[0];self.assertEqual((m['Costo'],m['Cobrado'],m['CostoPendiente']),('40.00','0.00',False));self.assertEqual(len(p['tables']['DetalleAlmuerzos']),2)
  self.assertEqual(self.records(p,'TurnosCaja')[0]['EsperadoActual'],'500.00')
 def test_no_credentials_and_read_only_source(self):
  with app.connect() as c:c.execute("INSERT OR REPLACE INTO settings VALUES('test_secret','SENTINEL-NO-EXPORTAR')")
  with app.connect() as c:before=c.execute('SELECT COUNT(*) FROM access_sync_outbox').fetchone()[0]
  p=access_model.build(app.DB);text=json.dumps(p)
  self.assertNotIn('SENTINEL-NO-EXPORTAR',text);self.assertNotIn('code_hash',text);self.assertNotIn('smtp_secret',text)
  with app.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM access_sync_outbox').fetchone()[0],before)
 def test_outbox_rolls_back_with_financial_change(self):
  with app.connect() as c:before=c.execute('SELECT COUNT(*) FROM access_sync_outbox').fetchone()[0]
  with self.assertRaises(RuntimeError):
   with app.connect() as c:c.execute("UPDATE products SET price=12000 WHERE id=1");raise RuntimeError('Revertir')
  with app.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM access_sync_outbox').fetchone()[0],before);self.assertEqual(c.execute('SELECT price FROM products WHERE id=1').fetchone()[0],11500)
 def test_unknown_historical_bases_are_not_invented(self):
  r=self.f.post('invoices',self.f.data('access-historic'));self.assertEqual(r.status_code,200)
  with app.connect() as c:
   r=c.execute('SELECT snapshot FROM invoices WHERE id=1').fetchone();s=json.loads(r[0]);s.pop('taxable_15');s.pop('taxable_18');c.execute('UPDATE invoices SET snapshot=? WHERE id=1',(json.dumps(s),))
  row=self.records(access_model.build(app.DB),'Facturas')[0];self.assertFalse(row['DesgloseCompleto']);self.assertIsNone(row['Base15']);self.assertIsNone(row['Base18'])
 def test_status_permissions(self):
  self.assertEqual(self.f.c.get('/api/accounting/access-status').status_code,200)
  self.f.post('auth/logout',{});self.f.post('auth/login',dict(role='local',branch_id=1,employee_code='ANA123'))
  self.assertEqual(self.f.c.get('/api/accounting/access-status').status_code,403);self.assertEqual(self.f.post('admin/access-sync',{}).status_code,403)
if __name__=='__main__':unittest.main()
