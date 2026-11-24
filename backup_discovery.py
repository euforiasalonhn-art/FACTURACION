"""Descubrimiento LAN/PAN con desafío firmado; nunca anuncia la clave."""
import socket,json,hmac,hashlib,secrets,time,threading
PORT=5059

def signed(key,d):return hmac.new(key.encode(),json.dumps(d,sort_keys=True,separators=(',',':')).encode(),hashlib.sha256).hexdigest()
def serve(key,stop=None,port=5058):
 stop=stop or threading.Event();sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);sock.bind(('',PORT));sock.settimeout(1)
 try:
  while not stop.is_set():
   try:
    data,peer=sock.recvfrom(2048);d=json.loads(data)
    if d.get('protocol')!='FRY-DISCOVERY-1' or len(d.get('nonce',''))!=32:continue
    reply=dict(protocol='FRY-DISCOVERY-1',nonce=d['nonce'],name=socket.gethostname(),port=port);reply['signature']=signed(key,reply);sock.sendto(json.dumps(reply).encode(),peer)
   except (ValueError,OSError):continue
 finally:sock.close()
def discover(key,timeout=1.0,targets=None):
 nonce=secrets.token_hex(16);request=json.dumps(dict(protocol='FRY-DISCOVERY-1',nonce=nonce)).encode();sockets=[];found={}
 try:
  addresses={r[4][0] for r in socket.getaddrinfo(socket.gethostname(),None,socket.AF_INET)} if targets is None else {'0.0.0.0'}
  addresses.add('0.0.0.0')
  for addr in addresses:
   try:
    s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1);s.bind((addr,0));s.setblocking(False);sockets.append(s)
    for target in targets or [('255.255.255.255',PORT)]:s.sendto(request,target)
   except OSError:continue
  import select
  end=time.monotonic()+timeout
  while sockets and time.monotonic()<end:
   ready,_,_=select.select(sockets,[],[],max(0,end-time.monotonic()))
   for s in ready:
    try:
     raw,peer=s.recvfrom(4096);d=json.loads(raw);signature=d.pop('signature','')
     if d.get('nonce')!=nonce or d.get('protocol')!='FRY-DISCOVERY-1' or not hmac.compare_digest(signature,signed(key,d)):continue
     port=int(d['port'])
     if not 1<=port<=65535:continue
     url=f'http://{peer[0]}:{port}';found[url]=dict(url=url,name=d['name'])
    except (ValueError,OSError,KeyError):continue
  return list(found.values())
 finally:
  for s in sockets:s.close()
