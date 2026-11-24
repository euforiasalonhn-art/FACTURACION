"""Transporte cifrado entre terminales y PC 1; la base nunca viaja como archivo compartido."""
import base64,json,urllib.request,urllib.error,ipaddress
from urllib.parse import urlsplit
import backup_protocol as protocol
MAX_PACKET=256*1024*1024
class CentralUnavailable(Exception):pass

def server_url(value):
 value=str(value).strip().rstrip('/');p=urlsplit(value)
 if p.scheme not in ['http','https'] or not p.hostname or p.username or p.password or p.query or p.fragment or p.path:raise ValueError('Dirección inválida. Ejemplo: http://192.168.1.50:5060')
 if p.scheme=='http':
  try:ip=ipaddress.ip_address(p.hostname)
  except ValueError:raise ValueError('Usa la IP de PC 1, o HTTPS con certificado válido')
  if not any(ip in ipaddress.ip_network(n) for n in ['127.0.0.0/8','10.0.0.0/8','172.16.0.0/12','192.168.0.0/16','100.64.0.0/10']):raise ValueError('HTTP cifrado solo se admite en red privada o Tailscale')
 return value

def call(cfg,packet,timeout=60):
 key=cfg['key'];wire=protocol.seal(key,json.dumps(packet).encode());headers=protocol.headers(key,'POST','/rpc',wire);headers['X-FRY-Terminal']=str(cfg['terminal_id'])
 class NoRedirect(urllib.request.HTTPRedirectHandler):
  def redirect_request(self,*args,**kw):return None
 opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
 # Un POST no se repite automáticamente: la terminal conserva el mismo identificador de venta.
 req=urllib.request.Request(server_url(cfg['server_url'])+'/rpc',data=wire,headers=headers,method='POST')
 try:
  with opener.open(req,timeout=timeout) as response:
   raw=response.read(MAX_PACKET+1)
   if len(raw)>MAX_PACKET:raise ValueError('Respuesta demasiado grande')
   result=json.loads(protocol.unseal(key,raw))
   if result.get('nonce')!=headers['X-FRY-Nonce']:raise ValueError('Confirmación ajena a esta solicitud')
   return result
 except urllib.error.HTTPError as e:
  raise CentralUnavailable('PC 1 rechazó la vinculación. Revisa el número de terminal, la clave, sus permisos y la hora de ambas PCs.') from e
 except (OSError,ValueError,KeyError) as e:raise CentralUnavailable('No se recibió confirmación de PC 1. Revisa conexión y servidor. Si estabas cobrando, consulta el cobro pendiente antes de repetirlo.') from e
