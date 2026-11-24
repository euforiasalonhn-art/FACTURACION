"""PC 1 aloja base/impresión; las terminales solo tienen un proxy cifrado."""
import sys,threading,ctypes,os
from pathlib import Path
from werkzeug.serving import make_server
from PySide6.QtWidgets import QApplication,QMainWindow,QFileDialog,QMessageBox
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtCore import QUrl,QStandardPaths,Signal
from PySide6.QtGui import QShortcut,QKeySequence
import terminal_setup
import instance_lock
import pc_labels
import traceback,tempfile
from datetime import datetime

class LocalPage(QWebEnginePage):
 def __init__(self,origin,parent):super().__init__(parent);self.origin=origin
 def acceptNavigationRequest(self,url,kind,main):return url.scheme() in ['about','qrc','data'] or (url.scheme()=='http' and url.host()=='127.0.0.1' and url.port()==self.origin.port())

class Window(QMainWindow):
 exitVerified=Signal(bool,str,bool)
 def __init__(self,url,server_mode,exit_guard=None):
  super().__init__();self.server_mode=server_mode;self.exit_guard=exit_guard;self._checking_exit=False;self._allow_close=False;self._exit_action='exit';self.exitVerified.connect(self.exit_decision);self.setWindowTitle('FRY Chicken · '+('PC 1 / SERVIDOR' if server_mode else 'TERMINAL CONECTADA'));self.resize(1400,900)
  self.fullscreenShortcut=QShortcut(QKeySequence('F12'),self);self.fullscreenShortcut.activated.connect(lambda:self.showNormal() if self.isFullScreen() else self.showFullScreen())
  self.configShortcut=QShortcut(QKeySequence('F8'),self);self.configShortcut.activated.connect(self.configure)
  self.exitShortcut=QShortcut(QKeySequence('F4'),self);self.exitShortcut.activated.connect(self.close)
  self.web=QWebEngineView();self.web.setPage(LocalPage(QUrl(url),self.web));self.setCentralWidget(self.web)
  if server_mode:
   from printing import PrinterController
  else:
   from client_printing import ClientPrinterController as PrinterController
  self.printer=PrinterController(self.web,self);self.channel=QWebChannel(self.web.page());self.channel.registerObject('printer',self.printer);self.web.page().setWebChannel(self.channel)
  self.web.page().profile().downloadRequested.connect(self.download);self.web.printRequested.connect(self.printer.request_print);self.web.load(QUrl(url))
 def configure(self):
  if self._checking_exit:return
  if self.exit_guard:self._exit_action='configure';self.check_exit();return
  self.configure_now()
 def configure_now(self):
  if terminal_setup.configure(self):QMessageBox.information(self,'Configuración guardada','Cierra y vuelve a abrir el programa para aplicar esta configuración.')
 def check_exit(self,final=False):
  if self._checking_exit:return
  self._checking_exit=True;self.web.setEnabled(False);self.statusBar().showMessage('Comprobando cajas pendientes…')
  def run():
   try:
    result=self.exit_guard(final=final);allowed=result.get('can_exit') is True;message=result.get('message','')
    if not allowed and result.get('shifts'):
     # Incluso si el servidor devuelve un aviso antiguo, nunca usar el ID del turno.
     boxes=sorted({pc_labels.number(r['terminal_id']) for r in result['shifts'] if r.get('terminal_id') is not None})
     message='Debes cuadrar y cerrar la caja antes de salir.'+(' Cajas pendientes: '+', '.join('CAJA #'+str(n) for n in boxes)+'.' if boxes else '')
   except Exception as error:allowed=False;message='No se pudo comprobar el cierre de caja. '+str(error)
   try:self.exitVerified.emit(allowed,message,final)
   except RuntimeError:pass
  threading.Thread(target=run,daemon=True,name='FRY-verificar-cierre').start()
 def exit_decision(self,allowed,message,final):
  self._checking_exit=False;self.statusBar().clearMessage()
  if not allowed:
   self.web.setEnabled(True);QMessageBox.information(self,'Caja pendiente de cuadre',message or 'Debes cuadrar la caja antes de salir.');self.web.page().runJavaScript('window.cashExitRequested && window.cashExitRequested()');return
  if self._exit_action=='configure':self.web.setEnabled(True);self.configure_now();return
  if final:self._allow_close=True;self.close();return
  if self.server_mode and QMessageBox.question(self,'Cerrar PC 1','Todas las cajas están cerradas. Se detendrá el servidor y la impresión. ¿Cerrar?',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:self.web.setEnabled(True);return
  self.check_exit(final=True)
 def closeEvent(self,event):
  if self._allow_close:event.accept();return
  if self.exit_guard:
   event.ignore()
   if not self._checking_exit:self._exit_action='exit';self.check_exit()
   return
  if self.server_mode and QMessageBox.question(self,'Cerrar PC 1','Se detendrá la facturación y la impresión de todas las terminales. ¿Cerrar el servidor?',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:event.ignore();return
  event.accept()
 def download(self,item):
  folder=QStandardPaths.writableLocation(QStandardPaths.DownloadLocation);path,_=QFileDialog.getSaveFileName(self,'Guardar reporte',str(Path(folder)/item.downloadFileName()))
  if not path:item.cancel();return
  item.setDownloadDirectory(str(Path(path).parent));item.setDownloadFileName(Path(path).name);item.accept()

def main():
 application=QApplication(sys.argv);servers=[];lockfile=None;stage='leer configuración'
 try:
  cfg=terminal_setup.load() or terminal_setup.configure()
  if not cfg:return 0
  if cfg['mode']=='server':
   stage='comprobar si PC 1 ya está abierta'
   lockfile=instance_lock.acquire(terminal_setup.DATA/'central.lock','PC 1 ya está abierta en esta computadora. Usa la ventana existente. Si vas a actualizar, cierra primero el sistema de facturación y vuelve a iniciarlo.')
   from app import app,init_db,connect
   from central_gateway import create_gateway
   stage='iniciar base de datos y servidor central'
   init_db()
   import access_sync
   access_sync.start(terminal_setup.DATA/'fry_chicken.db',terminal_setup.DATA,Path(getattr(sys,'_MEIPASS',Path(__file__).parent)))
   servers.append(make_server('0.0.0.0',5060,create_gateway(app,connect),threaded=True));webapp=app
  else:
   from terminal_proxy import create_proxy
   stage='comprobar si la terminal ya está abierta'
   folder=terminal_setup.DATA.parent/('terminal-'+str(cfg['terminal_id']))
   lockfile=instance_lock.acquire(folder/'terminal-process.lock','Esta terminal ya está abierta en esta computadora. Usa la ventana existente. Si vas a actualizar, cierra primero el sistema de facturación y vuelve a iniciarlo.')
   webapp=create_proxy(cfg,folder)
  stage='iniciar ventana del punto de venta'
  local=make_server('127.0.0.1',0,webapp,threaded=True);servers.append(local)
  for server in servers:threading.Thread(target=server.serve_forever,daemon=True).start()
  import cash_safety
  exit_guard=lambda final=False:cash_safety.native_guard(cfg,terminal_setup.DATA,connect if cfg['mode']=='server' else None,final)
  window=Window(f'http://127.0.0.1:{local.server_port}',cfg['mode']=='server',exit_guard);window.setWindowTitle('FRY Chicken · '+pc_labels.name(cfg.get('terminal_id',0))+(' / Servidor' if cfg['mode']=='server' else ''));window.showFullScreen()
  application.aboutToQuit.connect(lambda:[s.shutdown() for s in servers]);return application.exec()
 except instance_lock.AlreadyRunning as error:
  QMessageBox.information(None,'FRY Chicken ya está abierto',str(error));return 0
 except Exception as error:
  detail=datetime.now().astimezone().isoformat()+' · '+stage+'\n'+traceback.format_exc()+'\n'
  logfile=None
  for folder in [terminal_setup.DATA.parent/'logs',Path(tempfile.gettempdir())/'FRYChickenPOS-logs']:
   try:
    folder.mkdir(parents=True,exist_ok=True);logfile=folder/'inicio.log'
    with logfile.open('a',encoding='utf-8') as log:log.write(detail)
    break
   except OSError:logfile=None
  message='No se pudo '+stage+'.\n'+str(error)
  if isinstance(error,PermissionError):message+='\nWindows denegó el acceso. Revisa si otro proceso está usando el archivo o si la carpeta permite escritura. No borres la base de datos.'
  if logfile:message+='\nDetalle del error: '+str(logfile)
  QMessageBox.critical(None,'No se pudo iniciar FRY Chicken',message);return 1
 finally:
  for server in servers:server.server_close()
  if lockfile:lockfile.close()
if __name__=='__main__':sys.exit(main())
