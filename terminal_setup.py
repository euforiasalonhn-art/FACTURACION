"""Configuración por computadora, fuera de la base de facturación."""
import json,os
from pathlib import Path
from PySide6.QtWidgets import QDialog,QVBoxLayout,QFormLayout,QComboBox,QLineEdit,QLabel,QPushButton,QHBoxLayout
import backup_protocol as protocol
from central_transport import server_url
DATA=Path(os.environ.get('FRY_CHICKEN_DATA_DIR',Path(os.environ.get('LOCALAPPDATA',Path.home()))/'FRYChickenPOS'/'data'))
CONFIG=DATA.parent/'terminal.json'
def load():
 try:return json.loads(CONFIG.read_text('utf-8'))
 except (OSError,ValueError):return None

def configure(parent=None):
 previous=load() or {};dlg=QDialog(parent);dlg.setWindowTitle('FRY · Función de esta computadora');dlg.resize(620,440);layout=QVBoxLayout(dlg)
 label=QLabel('PC 1 conserva la base actual, el correlativo y las impresoras.\nUna TERMINAL se conecta a PC 1 y no genera facturas por su cuenta.');label.setWordWrap(True);layout.addWidget(label)
 form=QFormLayout();layout.addLayout(form);mode=QComboBox();mode.addItem('PC 1 · Servidor central','server');mode.addItem('PC 2, PC 3… · Caja conectada','client');mode.setCurrentIndex(1 if previous.get('mode')=='client' else 0);form.addRow('Función',mode)
 url=QLineEdit(previous.get('server_url',''));url.setPlaceholderText('http://192.168.1.50:5060');form.addRow('Dirección de PC 1',url)
 tid=QLineEdit(str(previous.get('terminal_id','')));form.addRow('ID de vinculación autorizado',tid)
 pc_name=QLabel();form.addRow('Nombre visible',pc_name)
 def preview_pc():pc_name.setText('PC '+str(int(tid.text())+1) if tid.text().isdigit() and int(tid.text())>0 else 'PC 2, PC 3…')
 tid.textChanged.connect(preview_pc);preview_pc()
 key=QLineEdit(previous.get('key',''));key.setEchoMode(QLineEdit.Password);form.addRow('Clave de vinculación',key)
 admin_password=QLineEdit();admin_password.setEchoMode(QLineEdit.Password);form.addRow('Contraseña del administrador de la base existente',admin_password)
 message=QLabel('El administrador crea la terminal y su clave en PC 1 > Terminales e impresión.');message.setWordWrap(True);layout.addWidget(message)
 result={};buttons=QHBoxLayout();save=QPushButton('Guardar');cancel=QPushButton('Cancelar');buttons.addWidget(save);buttons.addWidget(cancel);layout.addLayout(buttons)
 def toggle():
  for el in [url,tid,key]:el.setEnabled(mode.currentData()=='client')
  admin_password.setEnabled((DATA/'fry_chicken.db').exists() and (mode.currentData()=='server' or previous.get('mode')=='server'))
 mode.currentIndexChanged.connect(toggle);toggle()
 def persist():
  try:
   cfg=dict(mode=mode.currentData())
   if (DATA/'fry_chicken.db').exists() and (cfg['mode']=='server' or previous.get('mode')=='server'):
    import sqlite3
    from contextlib import closing
    from werkzeug.security import check_password_hash
    with closing(sqlite3.connect((DATA/'fry_chicken.db').resolve().as_uri()+'?mode=ro',uri=True)) as c:
     row=c.execute("SELECT value FROM settings WHERE key='auth'").fetchone()
    if not row or not check_password_hash(json.loads(row[0])['password'],admin_password.text()):raise ValueError('Contraseña del administrador incorrecta. No se cambió la función de esta PC.')
   if cfg['mode']=='client':
    if int(tid.text())<=0 or len(key.text().strip())<32:raise ValueError('Indica número y clave proporcionados por el administrador')
    cfg.update(server_url=server_url(url.text()),terminal_id=int(tid.text()),key=key.text().strip())
   # No permite cambiar la identidad mientras existe un cobro sin confirmar.
   if previous.get('mode')=='client' and (DATA.parent/('terminal-'+str(previous.get('terminal_id')))/'cobro-pendiente.json').exists() and (cfg.get('mode')!=previous.get('mode') or cfg.get('terminal_id')!=previous.get('terminal_id')):raise ValueError('Resuelve el cobro pendiente antes de cambiar esta configuración')
   protocol.atomic(CONFIG,json.dumps(cfg).encode());result.update(cfg);dlg.accept()
  except (ValueError,TypeError) as e:message.setText(str(e))
 save.clicked.connect(persist);cancel.clicked.connect(dlg.reject)
 return result if dlg.exec() else None
