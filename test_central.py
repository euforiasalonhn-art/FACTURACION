import unittest,json,base64,secrets,concurrent.futures,uuid,sqlite3,tempfile,gzip
from pathlib import Path
from datetime import date,timedelta
import test_operations as fixture
import app,backup_protocol as protocol,print_queue,central_gateway

class Remote:
 def __init__(self,gateway,tid,key):self.gateway=gateway;self.tid=tid;self.key=key;self.cookie=''
 def request(self,path,data=None,method=None,cookie=None):
  if path=='/api/auth/login' and data and data.get('role')=='local' and not data.get('stage'):
   status,body=self.request(path,dict(role='local',branch_id=data.get('branch_id'),stage='BRANCH',password='1234'),cookie=cookie)
   if status!=200:return status,body
   data=dict(data,stage='EMPLOYEE')
  from urllib.parse import urlsplit
  p=urlsplit(path);verb=method or ('POST' if data is not None else 'GET');headers={'X-POS-Token':app.TOKEN,'Content-Type':'application/json','Cookie':self.cookie if cookie is None else cookie}
  packet=dict(method=verb,path=p.path,query=p.query,headers=headers,body=base64.b64encode(json.dumps(data).encode() if data is not None else b'').decode());wire=protocol.seal(self.key,json.dumps(packet).encode());h=protocol.headers(self.key,'POST','/rpc',wire);h['X-FRY-Terminal']=str(self.tid)
  response=self.gateway.test_client().post('/rpc',data=wire,headers=h)
  if response.status_code!=200:return response.status_code,response.get_json(silent=True)
  r=json.loads(protocol.unseal(self.key,response.data));assert r['nonce']==h['X-FRY-Nonce']
  for k,v in r['headers']:
   if k.lower()=='set-cookie':self.cookie=v.split(';')[0]
  raw=base64.b64decode(r['body'])
  try:body=json.loads(raw)
  except ValueError:body=raw.decode('utf-8',errors='replace')
  return r['status'],body

class CentralTests(unittest.TestCase):
 def setUp(self):
  self.base=fixture.OperationsTests('test_sale_command_goals_cancellation_and_retry');self.base._testMethodName=self._testMethodName;self.base.setUp();self.c=self.base.c;self.h=self.base.h
  for i in range(2,5):
   r=self.base.post('admin/employees',dict(name='EMPLEADO '+str(i),identity='080119901234'+str(i+4),first_name='EMPLEADO',first_surname=str(i),access_code='EMP'+str(i)+'123'));self.assertEqual(r.status_code,200,r.data)
  self.gateway=central_gateway.create_gateway(app.app,app.connect);self.remotes=[]
  for i in range(1,5):
   r=self.base.post('admin/terminals',dict(name='CAJA '+str(i+1),branch_id=1,employee_ids=[i]));self.assertEqual(r.status_code,200,r.data);d=r.get_json();remote=Remote(self.gateway,d['id'],d['key']);self.remotes.append(remote)
   code='ANA123' if i==1 else 'EMP'+str(i)+'123';status,body=remote.request('/api/auth/login',dict(role='local',branch_id=1,employee_code=code));self.assertEqual(status,200,body)
   status,body=remote.request('/api/cash',dict(action='open',branch_id=1,opening=100*i));self.assertEqual(status,200,body)
 def sale(self,r,key=None,**kw):return r.request('/api/invoices',self.base.data(key or str(uuid.uuid4()),**kw))
 def test_concurrent_correlative_and_independent_sessions(self):
  import fiscal
  cfg=dict(fiscal.DEFAULT,branch_id=1,enabled=True,legal_name='PRUEBA',commercial_name='PRUEBA',rtn='12345678901234',address='Centro',head_address='Matriz',phone='12345678',email='demo@example.com',cai='ABCDEF-ABCDEF-ABCDEF-ABCDEF-ABCDEF-AB',establishment='000',point='001',range_start=501,range_end=999,next_number=501,deadline=(date.today()+timedelta(days=10)).isoformat())
  result=self.base.post('admin/fiscal',cfg);self.assertEqual(result.status_code,200,result.data)
  with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(lambda n:self.sale(self.remotes[n%4]),range(8)))
  self.assertTrue(all(s==200 for s,_ in results),results)
  with app.connect() as c:
   rows=list(c.execute('SELECT number,fiscal_number,snapshot,terminal_id FROM invoices ORDER BY id'));self.assertEqual(len(rows),8);self.assertEqual([r['number'] for r in rows],list(range(1,9)));self.assertEqual([int(r['fiscal_number'].rsplit('-',1)[1]) for r in rows],list(range(501,509)))
   self.assertEqual(c.execute('SELECT COUNT(*) FROM print_jobs').fetchone()[0],16)
   for r in rows:self.assertEqual(json.loads(r['snapshot'])['cashier_id'],r['terminal_id'])
  for i,remote in enumerate(self.remotes,1):
   status,state=remote.request('/api/auth/state');self.assertEqual(state['cashier']['id'],i);self.assertEqual(state['terminal']['id'],i)
   status,cash=remote.request('/api/cash?branch_id=1');self.assertEqual(cash['shift']['terminal_id'],i);self.assertEqual(cash['shift']['sales'],23000)
 def test_retry_no_duplicate_and_cash_isolated(self):
  r=self.remotes[0];payload=self.base.data('same-request',payment_method='Efectivo',amount_received=200)
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:r.request('/api/invoices',payload),range(2)))
  self.assertTrue(all(status==200 for status,_ in results),results);self.assertEqual(results[0][1],results[1][1])
  status,cash=r.request('/api/cash?branch_id=1');self.assertEqual(cash['shift']['live_expected'],21500)
  _,other=self.remotes[1].request('/api/cash?branch_id=1');self.assertEqual(other['shift']['live_expected'],20000)
  status,body=self.remotes[1].request('/api/cash',dict(action='close',branch_id=1,shift_id=cash['shift']['id'],counted=215));self.assertEqual(status,400)
  with app.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM invoices').fetchone()[0],1);self.assertEqual(c.execute('SELECT COUNT(*) FROM print_jobs').fetchone()[0],2)
  status,body=r.request('/api/invoices',payload|dict(amount_received=250));self.assertEqual(status,409)
 def test_auth_permissions_binding_and_revocation(self):
  r=self.remotes[0];status,body=r.request('/api/admin/terminals');self.assertEqual(status,403)
  status,body=self.remotes[1].request('/api/auth/state',cookie=r.cookie);self.assertIsNone(body.get('role'))
  status,state=r.request('/api/cash?branch_id=1');self.assertEqual(status,200)
  self.assertEqual(r.request('/api/cash',dict(action='close',branch_id=1,shift_id=state['shift']['id'],counted=100))[0],200)
  status,body=r.request('/api/auth/login',dict(role='local',branch_id=1,employee_code='EMP2123'));self.assertEqual(status,403)
  result=self.base.post('admin/terminals',dict(id=r.tid,name='CAJA 2',branch_id=1,employee_ids=[1],active=False));self.assertEqual(result.status_code,200)
  status,body=r.request('/api/auth/state');self.assertEqual(status,403)
 def test_print_lifecycle_copies_and_restore(self):
  status,result=self.sale(self.remotes[0]);self.assertEqual(status,200,result)
  with app.connect() as c:job=print_queue.claim(c,['cash'])
  self.assertIsNotNone(job)
  with app.connect() as c:self.assertTrue(print_queue.spooling(c,job['id']))
  with app.connect() as c:print_queue.recover_worker(c)
  with app.connect() as c:self.assertEqual(c.execute('SELECT state FROM print_jobs WHERE id=?',(job['id'],)).fetchone()[0],'UNCERTAIN')
  req=dict(role='cash',source_id=result['id'],request_id=str(uuid.uuid4()))
  first=self.remotes[0].request('/api/printing/reprint',req);second=self.remotes[0].request('/api/printing/reprint',req);self.assertEqual(first,second)
  self.assertEqual(self.base.post('admin/printing/jobs/'+str(job['id'])+'/release',{}).status_code,400)
  with app.connect() as c:copy=print_queue.claim(c,['cash'])
  with app.connect() as c:self.assertTrue(print_queue.spooling(c,copy['id']));print_queue.finish(c,copy['id'],True)
  with app.connect() as c:
   row=c.execute('SELECT state,html FROM print_jobs WHERE id=?',(copy['id'],)).fetchone();self.assertEqual((row['state'],row['html']),('SPOOLED',''));self.assertEqual(c.execute('SELECT COUNT(*) FROM invoices').fetchone()[0],1)
 def test_primary_assignment_and_turn_owner(self):
  previous=self.remotes[1];status,cash=previous.request('/api/cash?branch_id=1');self.assertEqual(status,200)
  self.assertEqual(previous.request('/api/cash',dict(action='close',branch_id=1,shift_id=cash['shift']['id'],counted=200))[0],200)
  self.assertEqual(previous.request('/api/auth/logout',{})[0],200)
  self.assertEqual(self.base.post('admin/primary-employees',dict(employee_ids=[2])).status_code,200)
  self.assertEqual(self.base.post('auth/login',dict(role='local',branch_id=1,employee_code='ANA123')).status_code,403)
  self.assertEqual(self.base.post('auth/login',dict(role='local',branch_id=1,employee_code='EMP2123')).status_code,200)
  self.assertEqual(self.base.post('cash',dict(action='close',branch_id=1,shift_id=1,counted=500)).status_code,200)
  self.assertEqual(self.base.post('auth/logout',{}).status_code,200)
  self.base.post('auth/login',dict(role='admin',email='frychickencompany@gmail.com',password='FRY2026'))
  r=self.remotes[0];self.base.post('admin/terminals',dict(id=r.tid,name='CAJA 2',branch_id=1,employee_ids=[1,2],active=True))
  status,state=r.request('/api/auth/login',dict(role='local',branch_id=1,employee_code='EMP2123'));self.assertEqual(status,409,state)
  listing=self.c.get('/api/admin/terminals').get_json();shift=next(x for x in listing if x['id']==r.tid)['open_shift']
  closed=self.base.post('admin/terminals/'+str(r.tid)+'/cash-close',dict(shift_id=shift['id'],counted=100));self.assertEqual(closed.status_code,200,closed.data)
  status,state=r.request('/api/auth/login',dict(role='local',branch_id=1,employee_code='EMP2123'));self.assertEqual(status,409,state)
  self.assertEqual(self.base.post('admin/employees/1/release-session',{}).status_code,200)
  status,state=r.request('/api/auth/login',dict(role='local',branch_id=1,employee_code='EMP2123'));self.assertEqual(status,200,state)
  self.assertEqual(r.request('/api/cash',dict(action='open',branch_id=1,opening=200))[0],200)
  self.assertEqual(self.sale(r)[0],200)
 def test_restored_queue_does_not_print_historical_originals(self):
  from contextlib import closing
  import full_backup
  self.assertEqual(self.sale(self.remotes[0])[0],200)
  with tempfile.TemporaryDirectory(dir=app.DATA) as folder:
   folder=Path(folder);(folder/full_backup.NAME).write_bytes((app.DATA/full_backup.NAME).read_bytes())
   full_backup.restore_if_missing(folder/'restored.db',folder)
   with closing(sqlite3.connect(folder/'restored.db')) as c:
    states=[r[0] for r in c.execute('SELECT state FROM print_jobs')];self.assertEqual(states,['UNCERTAIN','UNCERTAIN'])
 def test_manual_print_while_pending_does_not_create_a_copy(self):
  status,result=self.sale(self.remotes[0]);self.assertEqual(status,200,result);r=self.remotes[0]
  for _ in range(2):self.assertEqual(r.request('/api/printing/reprint',dict(role='cash',source_id=result['id'],request_id=str(uuid.uuid4())))[0],200)
  with app.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM print_jobs').fetchone()[0],2)
  self.base.post('invoices/'+str(result['id'])+'/void',dict(reason='Pedido cancelado antes de imprimir'))
  with app.connect() as c:self.assertEqual([r[0] for r in c.execute('SELECT state FROM print_jobs')],['CANCELLED','CANCELLED'])

 def test_inflight_pending_and_late_packet_cannot_emit_after_cancel(self):
  r=self.remotes[0];key='late-packet'
  with app.connect() as c:c.execute('INSERT INTO terminal_requests(terminal_id,request_id,payload_hash,last_status) VALUES(?,?,?,0)',(r.tid,key,'pending'))
  status,body=r.request('/api/terminal/recover?request_id='+key);self.assertEqual(status,200);self.assertTrue(body['processing']);self.assertFalse(body['found'])
  self.assertEqual(r.request('/api/terminal/cancel-pending',dict(request_id=key))[0],409)
  with app.connect() as c:c.execute('UPDATE terminal_requests SET last_status=499 WHERE request_id=?',(key,))
  self.assertEqual(r.request('/api/terminal/cancel-pending',dict(request_id=key))[0],200)
  self.assertEqual(self.sale(r,key)[0],409)
  with app.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM invoices').fetchone()[0],0)

 def test_edit_after_rejected_payment(self):
  r=self.remotes[0];p=self.base.data('bad-cash',payment_method='Efectivo',amount_received=1);status,b=r.request('/api/invoices',p);self.assertEqual(status,400)
  status,b=r.request('/api/invoices',p|dict(amount_received=200));self.assertEqual(status,200,b)
if __name__=='__main__':unittest.main()
