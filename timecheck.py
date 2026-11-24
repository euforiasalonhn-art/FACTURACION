"""Consulta NTP de Google para validar, sin modificar, el reloj de la PC."""
import socket, struct, time, threading
NTP_EPOCH=2208988800
LOCK=threading.Lock()
STATE={'status':'PENDIENTE','checked_at':None,'offset_seconds':None}
STARTED=False
def timestamp(raw,offset,anchor):
 seconds,fraction=struct.unpack_from('!II',raw,offset)
 if not seconds and not fraction:raise ValueError('Marca NTP vacía')
 era=round((anchor+NTP_EPOCH-seconds)/(2**32))
 return seconds+era*2**32-NTP_EPOCH+fraction/2**32
def parse(packet,request,t1,t4,elapsed):
 if len(packet)<48 or packet[0]&7!=4 or (packet[0]>>3)&7 not in [3,4] or packet[0]>>6==3 or not 1<=packet[1]<=15:raise ValueError('Respuesta NTP no válida')
 if packet[24:32]!=request[40:48]:raise ValueError('Respuesta NTP no corresponde a la consulta')
 if elapsed>4 or abs((t4-t1)-elapsed)>1:raise ValueError('El reloj cambió durante la consulta')
 t2=timestamp(packet,32,t1);t3=timestamp(packet,40,t1)
 delay=(t4-t1)-(t3-t2)
 if t3<t2 or delay<-.05 or delay>3:raise ValueError('Respuesta de hora imprecisa')
 return ((t2-t1)+(t3-t4))/2
def query():
 packet=bytearray(48);packet[0]=0x23
 with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
  sock.settimeout(3);sock.connect(('time.google.com',123))
  t1=time.time();mono=time.monotonic();ntp=t1+NTP_EPOCH
  struct.pack_into('!II',packet,40,int(ntp)%(2**32),int((ntp-int(ntp))*2**32))
  sock.send(packet);answer=sock.recv(512);t4=time.time();elapsed=time.monotonic()-mono
 return parse(answer,packet,t1,t4,elapsed)
def validate():
 try:
  offset=query();wall=time.time();mono=time.monotonic()
  with LOCK:STATE.update(status='VALIDADA' if abs(offset)<=5 else 'DESAJUSTADA',checked_at=wall,offset_seconds=round(offset,3),wall=wall,mono=mono)
 except Exception:
  with LOCK:STATE['status']='SIN_VALIDACION'
def status():
 with LOCK:out=dict(STATE)
 if out['status'] in ['VALIDADA','DESAJUSTADA']:
  if time.time()-out['wall']>1000 or abs((time.time()-out['wall'])-(time.monotonic()-out['mono']))>2:out['status']='PENDIENTE'
 out.pop('wall',None);out.pop('mono',None)
 return out|{'server':'time.google.com','timezone':'America/Tegucigalpa','pc_epoch':time.time()}
def start():
 global STARTED
 if STARTED:return
 STARTED=True
 def worker():
  while True:
   validate()
   with LOCK:ok=STATE['status'] in ['VALIDADA','DESAJUSTADA']
   threading.Event().wait(900 if ok else 60)
 threading.Thread(target=worker,daemon=True,name='FRY-validacion-hora').start()
