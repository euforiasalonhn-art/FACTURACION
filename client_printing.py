"""Puente nativo de terminal: jamás abre una base local ni imprime facturas locales."""
from PySide6.QtCore import QObject,Slot,Signal
class ClientPrinterController(QObject):
 message=Signal(str);changed=Signal(str)
 def __init__(self,view,parent=None):super().__init__(parent);self.view=view;self.reports=[]
 @Slot(result=str)
 def status(self):return 'Facturas y comandas: cola central de PC 1'
 @Slot()
 def configure(self):self.message.emit('Configura la impresora de caja en PC 1.')
 @Slot()
 def configureKitchen(self):self.message.emit('Configura la impresora de cocina en PC 1.')
 @Slot()
 def autoPrint(self):pass
 @Slot()
 def request_print(self):self.view.page().runJavaScript("window.requestCentralReprint && window.requestCentralReprint('cash')")
 @Slot(str,str,bool)
 def printHtml(self,body,role,automatic):
  if not automatic:self.view.page().runJavaScript("window.requestCentralReprint && window.requestCentralReprint('kitchen')")
 @Slot(str)
 def openReport(self,url):
  from PySide6.QtCore import QUrl
  from PySide6.QtWebEngineWidgets import QWebEngineView
  from PySide6.QtWebEngineCore import QWebEnginePage
  from PySide6.QtGui import QPageLayout,QPageSize
  from PySide6.QtPrintSupport import QPrinter,QPrintDialog
  target=QUrl(url);origin=self.view.url()
  if target.scheme()!=origin.scheme() or target.host()!=origin.host() or target.port()!=origin.port() or target.path()!='/api/accounting/export/print':self.message.emit('Reporte no autorizado');return
  report=QWebEngineView();report.setPage(QWebEnginePage(self.view.page().profile(),report));report.resize(1200,850);self.reports.append(report)
  def print_report():
   printer=QPrinter(QPrinter.HighResolution);printer.setPageOrientation(QPageLayout.Landscape);printer.setPageSize(QPageSize(QPageSize.A4));dialog=QPrintDialog(printer,report)
   if dialog.exec():report.report_printer=printer;report.print(printer)
  report.printRequested.connect(print_report);report.load(target);report.show()
