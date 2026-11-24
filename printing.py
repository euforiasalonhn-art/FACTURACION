"""Impresión central: texto por red y alternativa mediante colas de Windows."""
import threading
import network_printers,printer_dialog
import print_queue,terminals
from PySide6.QtCore import QObject, Slot, Signal, QUrl, QSizeF, QMarginsF, QTimer
from PySide6.QtGui import QPageSize, QPageLayout
from PySide6.QtPrintSupport import QPrinter, QPrinterInfo, QPrintDialog
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage
from app import connect, setting, save_setting, ROOT

class PrinterController(QObject):
 message=Signal(str)
 changed=Signal(str)
 networkDone=Signal(str,int,bool,str)
 def __init__(self,view,parent=None):
  super().__init__(parent); self.view=view; self.job=None; self.printer=None; self.reports=[]; self.queue=[]; self.print_options=None;self.active_job_id=None;self.has_spooled=False;self.network_busy=set();self.networkDone.connect(self.network_finished)
  with connect() as c:print_queue.recover_worker(c)
  self.poller=QTimer(self);self.poller.timeout.connect(self.poll_jobs);self.poller.start(1200)
 def options(self,role='cash'):
  with connect() as c: return network_printers.normalize(setting(c,'kitchen_printer' if role=='kitchen' else 'printer',None))
 @Slot(result=str)
 def status(self):
  parts=[]
  for role,title in [('cash','Caja'),('kitchen','Cocina')]:
   s=self.options(role);target=(s.get('host','')+':'+str(s['port']) if s.get('host') else 'sin IP') if s['transport']=='network' else (s.get('name') or 'sin seleccionar');parts.append(f"{title}: {target} · {'Red / texto' if s['transport']=='network' else 'Windows'} · {s['width']} mm · Automática: {'sí' if s['automatic'] else 'no'}")
  return ' | '.join(parts)
 @Slot()
 def configure(self): self.configure_role('cash')
 @Slot()
 def configureKitchen(self): self.configure_role('kitchen')
 def configure_role(self,role):
  def persist(options):
   with connect() as c:save_setting(c,'kitchen_printer' if role=='kitchen' else 'printer',options)
   self.changed.emit(self.status())
  printer_dialog.configure(self.view,role,self.options(role),persist)
 @Slot(str)
 def openReport(self,url):
  target=QUrl(url);origin=self.view.url()
  if target.scheme()!=origin.scheme() or target.host()!=origin.host() or target.port()!=origin.port() or target.path()!='/api/accounting/export/print':
   self.message.emit('Reporte no autorizado');return
  report=QWebEngineView();report.setPage(QWebEnginePage(self.view.page().profile(),report));report.setWindowTitle('FRY · Reporte contable para imprimir');report.resize(1200,850);self.reports.append(report)
  def print_report():
   printer=QPrinter(QPrinter.HighResolution);printer.setPageOrientation(QPageLayout.Landscape);printer.setPageSize(QPageSize(QPageSize.A4));dialog=QPrintDialog(printer,report)
   if dialog.exec():
    report.report_printer=printer;report.print(printer)
  report.printRequested.connect(print_report);report.load(target);report.show()
 @Slot()
 def autoPrint(self):pass # El original ya quedó en la cola dentro de la transacción de venta.
 @Slot()
 def request_print(self):self.view.page().runJavaScript("window.requestCentralReprint && window.requestCentralReprint('cash')")
 @Slot(str,str,bool)
 def printHtml(self,body,role,automatic):
  if not automatic:self.view.page().runJavaScript("window.requestCentralReprint && window.requestCentralReprint('kitchen')")
 def network_finished(self,role,jid,ok,message):
  self.network_busy.discard(role);self.message.emit(('Caja: ' if role=='cash' else 'Cocina: ')+message)
  QTimer.singleShot(0,self.poll_jobs)
 def poll_jobs(self):
  if not terminals.REQUEST_LOCK.acquire(blocking=False):return
  tasks=[];row=None
  try:
   profiles={role:self.options(role) for role in ['cash','kitchen']};names=[];windows=[]
   if any(options['transport']=='windows' for options in profiles.values()):
    try:names=QPrinterInfo.availablePrinterNames()
    except Exception:self.message.emit('No se pudo leer la lista de Windows; las impresoras de red siguen disponibles.')
   for role,options in profiles.items():
    if options['transport']=='network':
     if options.get('host') and role not in self.network_busy:
      with connect() as c:item=print_queue.claim(c,[role])
      if item:self.network_busy.add(role);tasks.append((role,item,options))
    elif options.get('name') in names and 'onenote' not in options.get('name','').casefold():windows.append(role)
   if not self.job and self.active_job_id is None:
    with connect() as c:row=print_queue.claim(c,windows)
    if row:self.active_job_id=row['id'];self.has_spooled=False;self.print_options=self.options(row['role']);self.print_role=row['role']
  except Exception as error:self.message.emit('No se pudo preparar la cola central: '+str(error))
  finally:terminals.REQUEST_LOCK.release()
  for role,item,options in tasks:
   def send(role=role,item=item,options=options):
    ok,message=network_printers.deliver(item,options,connect,terminals.REQUEST_LOCK)
    try:self.networkDone.emit(role,item['id'],ok,message)
    except RuntimeError:pass
   threading.Thread(target=send,daemon=True,name='FRY-red-'+role).start()
  if row:self.prepare(row['html'])
 def prepare(self,body):
  if not body: self.message.emit('Abre un comprobante para imprimirlo.');return
  if self.job: return
  s=self.print_options;margin=2 if self.print_role=='kitchen' else 3;content_width=s['width']-2*margin;self.job=QWebEngineView();self.job.setPage(QWebEnginePage(self.view.page().profile(),self.job));self.job.resize(round(content_width*96/25.4),1000)
  html='<!doctype html><meta charset="utf-8"><style>@page{margin:'+str(margin)+'mm}*{box-sizing:border-box}body{margin:0;color:#000;background:#fff;font:11px Arial;width:'+str(content_width)+'mm;overflow-wrap:anywhere}article{text-align:center}h1{font-size:20px}table{width:100%;table-layout:fixed;border-collapse:collapse}td{text-align:left;padding:5px 0;vertical-align:top}td:first-child{width:72%}td:last-child{text-align:right}.sum{display:flex;justify-content:space-between;gap:5px;margin:8px 0}p{margin:9px 0}</style><article>'+body+'</article>'
  html=html.replace('</style>',(ROOT/'static'/'receipt.css').read_text(encoding='utf-8-sig')+'</style>')
  self.job.loadFinished.connect(self.loaded);self.job.printFinished.connect(self.finished);self.job.setHtml(html)
 def loaded(self,ok):
  if not ok: self.finished(False);return
  self.job.page().runJavaScript('Math.ceil(document.querySelector("article").getBoundingClientRect().height)',self.print_job)
 def print_job(self,height):
  if self.has_spooled or self.active_job_id is None:return
  if not terminals.REQUEST_LOCK.acquire(blocking=False):
   QTimer.singleShot(150,lambda:self.print_job(height));return
  try:
   with connect() as c:ready=print_queue.spooling(c,self.active_job_id)
  finally:terminals.REQUEST_LOCK.release()
  if not ready:self.finished(False);return
  self.has_spooled=True
  s=self.print_options;self.printer=QPrinter(QPrinter.HighResolution);self.printer.setPrinterName(s['name']);self.printer.setResolution(300)
  margin=2 if self.print_role=='kitchen' else 3
  height=max(30 if self.print_role=='kitchen' else 50,min(3000,(height or 400)*25.4/96+(5 if self.print_role=='kitchen' else 8)))
  page=QPageSize(QSizeF(s['width'],height),QPageSize.Millimeter,'Ticket',QPageSize.ExactMatch)
  self.printer.setPageLayout(QPageLayout(page,QPageLayout.Portrait,QMarginsF(margin,margin,margin,margin),QPageLayout.Millimeter));self.printer.setDocName('FRY #'+str(self.active_job_id)+' · '+('Comanda cocina' if self.print_role=='kitchen' else 'Comprobante caja'))
  self.job.print(self.printer)
 def finished(self,ok):
  if not terminals.REQUEST_LOCK.acquire(blocking=False):
   QTimer.singleShot(150,lambda:self.finished(ok));return
  try:
   if self.active_job_id is not None:
    with connect() as c:print_queue.finish(c,self.active_job_id,ok)
  except Exception as error:self.message.emit('Impresión sin confirmación de registro. Revisa la cola antes de pedir copia: '+str(error))
  finally:terminals.REQUEST_LOCK.release()
  self.message.emit('Documento enviado a la cola de Windows; comprueba la salida en papel.' if ok else 'Impresión no confirmada. Revisa conexión y papel antes de solicitar una copia.')
  if self.job:self.job.deleteLater()
  self.job=None;self.printer=None;self.active_job_id=None;self.has_spooled=False
  QTimer.singleShot(0,self.poll_jobs)
