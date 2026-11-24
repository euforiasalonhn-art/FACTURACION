"""Configuración independiente de caja y cocina, con búsqueda de impresoras LAN."""
import threading,logging
import network_printers
from PySide6.QtCore import QObject,Signal,Qt
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QComboBox,QPushButton,QCheckBox,QListWidget,QLineEdit,QSpinBox,QWidget,QScrollArea
from PySide6.QtPrintSupport import QPrinterInfo

class SearchResult(QObject):
 done=Signal(int,object,str)

def configure(parent,role,current,persist):
 cfg=network_printers.normalize(current);title='CAJA' if role=='cash' else 'COCINA'
 dlg=QDialog(parent);dlg.setWindowTitle('Impresora de '+title+' · FRY Chicken');dlg.resize(640,700)
 layout=QVBoxLayout(dlg);heading=QLabel('Impresora de '+title);heading.setStyleSheet('font-size:20px;font-weight:bold');layout.addWidget(heading)
 connection=QComboBox();connection.addItem('Cable de red · texto directo','network');connection.addItem('Impresora instalada en Windows','windows');connection.setCurrentIndex(1 if cfg['transport']=='windows' else 0);layout.addWidget(connection)
 net=QWidget();netlayout=QVBoxLayout(net);netlayout.setContentsMargins(6,6,6,6);scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(net);layout.addWidget(scroll,1)
 info=QLabel('Perfil preparado para 3nStar RPT006: papel de 80 mm, texto ESC/POS sin imágenes. Conecta la impresora al router o switch del local y enciéndela. Busca su IP o escríbela manualmente.');info.setWordWrap(True);netlayout.addWidget(info)
 networks=QComboBox();networks.setEditable(True);networks.addItems(network_printers.local_networks());networks.setPlaceholderText('Ejemplo: 192.168.1.0/24')
 search=QPushButton('Buscar en la red');row=QHBoxLayout();row.addWidget(networks,1);row.addWidget(search);netlayout.addLayout(row)
 devices=QListWidget();devices.setMaximumHeight(110);netlayout.addWidget(devices)
 note=QLabel('La búsqueda detecta puertos de impresión abiertos; no identifica por sí sola marca o modelo. Selecciona un resultado y prueba la impresión.');note.setWordWrap(True);netlayout.addWidget(note)
 fields=QFormLayout();host=QLineEdit(cfg.get('host',''));host.setPlaceholderText('192.168.1.50');host.setObjectName('printerHost');port=QSpinBox();port.setRange(1,65535);port.setValue(cfg.get('port',9100));port.setObjectName('printerPort');fields.addRow('IP de la impresora',host);fields.addRow('Puerto TCP',port)
 protocol=QComboBox();protocol.addItem('3nStar RPT006 / ESC/POS · texto','escpos');protocol.addItem('Texto simple · sin comandos de corte','plain');protocol.setCurrentIndex(1 if cfg['protocol']=='plain' else 0);fields.addRow('Lenguaje de la impresora',protocol)
 encoding=QComboBox()
 for label,key in [('Español PC850 · ESC/POS página 2','cp850'),('Windows occidental · página 16','cp1252'),('PC437 · página 0','cp437'),('ASCII · sin tildes','ascii')]:encoding.addItem(label,key)
 encoding.setCurrentIndex(max(0,encoding.findData(cfg['encoding'])));fields.addRow('Caracteres',encoding)
 columns=QSpinBox();columns.setRange(24,64);columns.setValue(cfg['columns']);fields.addRow('Caracteres por línea',columns)
 feed=QSpinBox();feed.setRange(1,8);feed.setValue(cfg['feed']);fields.addRow('Líneas finales de avance',feed)
 cut=QCheckBox('Cortar papel al terminar (si la impresora tiene cortador)');cut.setChecked(cfg['cut']);fields.addRow(cut);netlayout.addLayout(fields)
 win=QWidget();winlayout=QVBoxLayout(win);winlayout.setContentsMargins(0,0,0,0);combo=QComboBox();winlayout.addWidget(QLabel('Cola instalada en Windows · formato mediante controlador'));winlayout.addWidget(combo)
 def refresh():
  name=combo.currentText() or cfg.get('name','');combo.clear()
  try:combo.addItems(QPrinterInfo.availablePrinterNames())
  except Exception:pass
  combo.setCurrentText(name)
 refresh();refreshbutton=QPushButton('Actualizar impresoras de Windows');refreshbutton.clicked.connect(refresh);winlayout.addWidget(refreshbutton);layout.addWidget(win)
 width=QComboBox();width.addItems(['58 mm','80 mm']);width.setCurrentIndex(0 if cfg['width']==58 else 1);form=QFormLayout();form.addRow('Ancho del rollo',width);layout.addLayout(form)
 width.currentIndexChanged.connect(lambda index:columns.setValue(32 if index==0 else 42))
 auto=QCheckBox('Imprimir automáticamente al confirmar la venta');auto.setChecked(cfg['automatic']);layout.addWidget(auto)
 testrow=QHBoxLayout();probe=QPushButton('Probar conexión');test=QPushButton('Imprimir prueba de texto');testrow.addWidget(probe);testrow.addWidget(test);layout.addLayout(testrow)
 result=QLabel('');result.setWordWrap(True);result.setObjectName('printerResult');layout.addWidget(result)
 actions=QHBoxLayout();save=QPushButton('Guardar impresora de '+title);save.setObjectName('savePrinter');cancel=QPushButton('Cancelar');actions.addWidget(save);actions.addWidget(cancel);layout.addLayout(actions)
 active={'kind':None,'generation':0};cancel_search=threading.Event();bridge=SearchResult(dlg)
 def get_options():
  return network_printers.validate(dict(transport=connection.currentData(),host=host.text().strip(),port=port.value(),name=combo.currentText(),width=58 if width.currentIndex()==0 else 80,automatic=auto.isChecked(),protocol=protocol.currentData(),encoding=encoding.currentData(),columns=columns.value(),feed=feed.value(),cut=cut.isChecked()))
 def set_busy(kind):
  active['kind']=kind;busy=kind is not None
  for button in [search,probe,test,save]:button.setEnabled(not busy)
 def mode():
  isnet=connection.currentData()=='network';scroll.setVisible(isnet);win.setVisible(not isnet);probe.setVisible(isnet);test.setVisible(isnet)
 mode();connection.currentIndexChanged.connect(mode)
 protocol.currentIndexChanged.connect(lambda:cut.setEnabled(protocol.currentData()=='escpos'))
 def completed(generation,data,error):
  if generation!=active['generation'] or not dlg.isVisible():return
  kind=active['kind'];set_busy(None)
  if error:result.setText(error);return
  if kind=='search':
   devices.clear()
   for item in data:devices.addItem(item['host']+':'+str(item['port']))
   result.setText(str(len(data))+' equipo(s) con el puerto abierto. Selecciona el que corresponda a '+title+'.' if data else 'No se encontraron equipos. Revisa la red, el puerto o escribe la IP manualmente.')
  else:result.setText(str(data))
 bridge.done.connect(completed)
 def background(kind,task):
  if active['kind'] is not None:return
  active['generation']+=1;generation=active['generation'];set_busy(kind)
  def run():
   try:data=task();error=''
   except Exception as e:
    logging.getLogger('impresoras_red').exception('No se pudo completar %s',kind)
    data=None;error=str(e)
   try:bridge.done.emit(generation,data,error)
   except RuntimeError:pass
  threading.Thread(target=run,daemon=True,name='FRY-impresora-'+kind).start()
 def scan():
  cidr=networks.currentText();scanport=port.value();cancel_search.clear();devices.clear();result.setText('Buscando en '+cidr+'…')
  background('search',lambda:network_printers.discover(cidr,scanport,cancel_search))
 search.clicked.connect(scan)
 def selected():
  item=devices.currentItem()
  if item:
   address,number=item.text().rsplit(':',1);host.setText(address);port.setValue(int(number))
 devices.itemSelectionChanged.connect(selected)
 def check():
  try:options=get_options()
  except ValueError as e:result.setText(str(e));return
  result.setText('Comprobando conexión…')
  def run():
   if not network_printers.probe(options['host'],options['port'],3):raise ValueError('Sin respuesta de '+options['name']+'. Revisa cable, IP y puerto.')
   return 'Conexión TCP disponible. La prueba de texto confirma el lenguaje y los caracteres.'
  background('probe',run)
 probe.clicked.connect(check)
 def print_test():
  try:options=get_options()
  except ValueError as e:result.setText(str(e));return
  result.setText('Enviando prueba a '+options['name']+'…')
  def run():network_printers.send_test(options,role);return 'Prueba de '+title+' enviada. Comprueba la salida en papel y las tildes antes de guardar.'
  background('test',run)
 test.clicked.connect(print_test)
 def save_options():
  try:
   options=get_options()
   if options['transport']=='windows' and (not options['name'] or options['name'] not in QPrinterInfo.availablePrinterNames()):raise ValueError('Selecciona una impresora instalada en Windows.')
   persist(options);dlg.accept()
  except Exception as e:result.setText(str(e))
 save.clicked.connect(save_options);cancel.clicked.connect(dlg.reject)
 dlg.finished.connect(lambda _:cancel_search.set());dlg.finished.connect(lambda _:active.update(generation=active['generation']+1))
 dlg.exec()
