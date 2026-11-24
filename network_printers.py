"""Detección TCP local y entrega durable de texto; sin controladores gráficos."""
import ipaddress,socket,threading
from concurrent.futures import ThreadPoolExecutor
import network_receipt

DEFAULT=dict(name='',transport='network',host='',port=9100,width=80,automatic=True,protocol='escpos',encoding='cp850',columns=42,cut=True,feed=3)
ENDPOINT_GUARD=threading.Lock()
ENDPOINT_LOCKS={}

def endpoint_lock(cfg):
 with ENDPOINT_GUARD:return ENDPOINT_LOCKS.setdefault((cfg['host'],cfg['port']),threading.Lock())

def normalize(value):
 value=dict(value or {});result=DEFAULT|value
 if 'transport' not in value and value.get('name'):result['transport']='windows'
 if 'columns' not in value:result['columns']=32 if result['width']==58 else 42
 return result

def validate(value):
 cfg=normalize(value)
 if cfg['transport']=='windows' and 'onenote' in cfg.get('name','').casefold():raise ValueError('Selecciona la impresora de caja o cocina. OneNote es una impresora virtual.')
 if cfg['transport'] not in ['network','windows']:raise ValueError('Conexión no admitida')
 if cfg['width'] not in [58,80]:raise ValueError('Selecciona papel de 58 u 80 mm')
 if cfg['transport']=='network':
  try:ip=ipaddress.IPv4Address(str(cfg['host']).strip())
  except ValueError:raise ValueError('Escribe la dirección IPv4 de la impresora, por ejemplo 192.168.1.50')
  if ip.is_multicast or ip.is_unspecified or str(ip)=='255.255.255.255':raise ValueError('Escribe una dirección de impresora válida')
  cfg['host']=str(ip);cfg['port']=int(cfg['port'])
  if not 1<=cfg['port']<=65535:raise ValueError('Puerto TCP inválido')
  cfg['columns']=int(cfg['columns']);cfg['feed']=int(cfg['feed'])
  if not 24<=cfg['columns']<=64:raise ValueError('Selecciona entre 24 y 64 caracteres por línea')
  if not 1<=cfg['feed']<=8:raise ValueError('Selecciona entre 1 y 8 líneas de avance')
  if cfg['protocol'] not in ['escpos','plain'] or cfg['encoding'] not in ['cp850','cp437','cp1252','ascii']:raise ValueError('Perfil de texto no admitido')
  cfg['name']=cfg['host']+':'+str(cfg['port'])
 return cfg

def local_networks():
 from PySide6.QtNetwork import QNetworkInterface
 found=[]
 for interface in QNetworkInterface.allInterfaces():
  if not interface.flags() & QNetworkInterface.IsUp or interface.flags() & QNetworkInterface.IsLoopBack:continue
  for entry in interface.addressEntries():
   host=entry.ip().toString()
   try:
    ip=ipaddress.IPv4Address(host);prefix=entry.prefixLength()
    if ip.is_loopback or ip.is_unspecified or prefix<0:continue
    network=ipaddress.ip_network(f'{host}/{max(24,prefix)}',strict=False)
    if str(network) not in found:found.append(str(network))
   except ValueError:continue
 return found

def probe(host,port=9100,timeout=.5):
 try:
  with socket.create_connection((str(host),int(port)),timeout=timeout):return True
 except OSError:return False

def discover(cidr,port=9100,cancel=None):
 network=ipaddress.ip_network(str(cidr).strip(),strict=False);port=int(port)
 if network.version!=4 or network.num_addresses>1024:raise ValueError('Indica una red IPv4 de hasta 1024 direcciones, por ejemplo 192.168.1.0/24')
 if not 1<=port<=65535:raise ValueError('Puerto TCP inválido')
 cancel=cancel or threading.Event()
 def check(host):return None if cancel.is_set() else str(host) if probe(host,port) else None
 with ThreadPoolExecutor(max_workers=32) as pool:found=[host for host in pool.map(check,network.hosts()) if host]
 return [dict(host=host,port=port) for host in sorted(found,key=ipaddress.IPv4Address)]

def send_test(options,role):
 cfg=validate(options)
 raw=network_receipt.payload('<h2>PRUEBA '+('CAJA' if role=='cash' else 'COCINA')+'</h2><p>Texto sin logo ni imagen</p><p>Español: ñ Ñ á é í ó ú</p><p>No es una venta</p>',cfg,role)
 with endpoint_lock(cfg):
  with socket.create_connection((cfg['host'],cfg['port']),timeout=5) as sock:sock.settimeout(8);sock.sendall(raw)

def deliver(row,options,connect,lock):
 import print_queue
 def finish(ok,error=''):
  with lock:
   with connect() as c:print_queue.finish(c,row['id'],ok,error)
 try:
  cfg=validate(options);raw=network_receipt.payload(row['html'],cfg,row['role'])
  with endpoint_lock(cfg):
   with socket.create_connection((cfg['host'],cfg['port']),timeout=5) as sock:
    sock.settimeout(8)
    with lock:
     with connect() as c:ready=print_queue.spooling(c,row['id'])
    if not ready:return False,'Pedido cancelado antes del envío a la impresora.'
    sock.sendall(raw)
  finish(True)
  return True,'Texto enviado por red a '+cfg['name']+'. Comprueba la salida en papel.'
 except Exception as error:
  reason=str(error) or type(error).__name__
  try:finish(False,reason)
  except Exception:return False,'No se confirmó el registro del envío. Revisa el papel y la cola antes de pedir una copia.'
  return False,'No se confirmó el envío a '+str(options.get('host','impresora'))+': '+reason+'. Revisa la cola antes de reimprimir.'
