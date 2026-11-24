import unittest,tempfile,subprocess,sys,os
from pathlib import Path
from unittest.mock import patch
import instance_lock
class InstanceLockTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)/'central.lock'
 def holder(self):
  code="import sys;from pathlib import Path;sys.path.insert(0,sys.argv[2]);import instance_lock;h=instance_lock.acquire(Path(sys.argv[1]),'duplicado');print('READY',flush=True);sys.stdin.readline();h.close()"
  p=subprocess.Popen([sys.executable,'-c',code,str(self.path),str(Path(instance_lock.__file__).parent)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  self.assertEqual(p.stdout.readline().strip(),'READY');self.addCleanup(self.stop,p);return p
 def stop(self,p):
  if p.poll() is None:p.communicate('\n',timeout=5)
  for f in [p.stdin,p.stdout,p.stderr]:
   if f and not f.closed:f.close()
 def test_empty_and_stale_file_can_start(self):
  h=instance_lock.acquire(self.path,'duplicado');h.close()
  h=instance_lock.acquire(self.path,'duplicado');h.close()
  self.path.write_bytes(b'0');h=instance_lock.acquire(self.path,'duplicado');h.close()
 def test_second_process_is_friendly_and_reopens_after_close(self):
  self.path.write_bytes(b'0');p=self.holder()
  # Reproduce exactamente el fallo del arranque anterior.
  with self.path.open('a+b') as old:
   old.seek(0)
   with self.assertRaises(PermissionError):old.read(1)
  with self.assertRaisesRegex(instance_lock.AlreadyRunning,'ventana existente'):instance_lock.acquire(self.path,'Usa la ventana existente')
  self.stop(p);h=instance_lock.acquire(self.path,'duplicado');h.close()
 def test_desktop_duplicate_does_not_initialize_database(self):
  import desktop_main as desktop
  self.path.write_bytes(b'0');self.holder();messages=[]
  with patch.object(desktop,'QApplication',return_value=object()),patch.object(desktop.terminal_setup,'DATA',Path(self.tmp.name)),patch.object(desktop.terminal_setup,'load',return_value={'mode':'server'}),patch.object(desktop.QMessageBox,'information',side_effect=lambda *a:messages.append(a)),patch.object(desktop.QMessageBox,'critical',side_effect=AssertionError('No debe mostrar error crítico')):
   self.assertEqual(desktop.main(),0)
  self.assertIn('ya está abierta',messages[0][2]);self.assertFalse((Path(self.tmp.name)/'fry_chicken.db').exists())
 def test_real_permission_failure_keeps_diagnostic_log(self):
  import desktop_main as desktop
  from types import SimpleNamespace
  messages=[];data=Path(self.tmp.name)/'data'
  fake_app=SimpleNamespace(app=object(),init_db=lambda:None,connect=lambda:None)
  with patch.object(desktop,'QApplication',return_value=object()),patch.object(desktop.terminal_setup,'DATA',data),patch.object(desktop.terminal_setup,'load',return_value={'mode':'server'}),patch.dict(sys.modules,{'app':fake_app,'central_gateway':SimpleNamespace(create_gateway=lambda *a:object())}),patch.object(desktop,'make_server',side_effect=PermissionError(13,'Permission denied')),patch.object(desktop.QMessageBox,'critical',side_effect=lambda *a:messages.append(a)):
   self.assertEqual(desktop.main(),1)
  log=Path(self.tmp.name)/'logs'/'inicio.log';self.assertTrue(log.exists());self.assertIn('PermissionError',log.read_text(encoding='utf-8'));self.assertIn(str(log),messages[0][2])
  h=instance_lock.acquire(data/'central.lock','duplicado');h.close()
if __name__=='__main__':unittest.main()
