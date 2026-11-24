"""Aplicación autónoma del receptor para Windows x64."""
import argparse,base64,json,logging,os,secrets,socket,subprocess,sys,threading
from pathlib import Path
import backup_protocol as protocol,backup_discovery
DATA=Path(os.environ.get('PROGRAMDATA',r'C:\ProgramData'))/'FRYChickenBackup'
ROOT=Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).parent

def configuration(data):
 return json.loads((data/'receptor.json').read_text('utf-8'))
def prepare(data):
 data.mkdir(parents=True,exist_ok=True)
 if not (data/'receptor.json').exists():protocol.atomic(data/'receptor.json',json.dumps(dict(key=secrets.token_urlsafe(32))).encode())
def powershell(script,args):
 exe=Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
 result=subprocess.run([str(exe),'-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(ROOT/script),*args],capture_output=True,text=True,creationflags=0x08000000)
 if result.returncode:raise RuntimeError(result.stderr or result.stdout or 'No se pudo configurar Windows')
def serve(data):
 from backup_receiver import create_receiver
 from werkzeug.serving import run_simple
 logging.basicConfig(filename=str(data/'receptor.log'),level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
 key=configuration(data)['key'];threading.Thread(target=backup_discovery.serve,args=(key,),daemon=True).start()
 run_simple('0.0.0.0',5058,create_receiver(data,key),threaded=True,use_reloader=False)
def gui(data):
 import tkinter as tk
 from tkinter import ttk,messagebox,filedialog
 prepare(data);key=configuration(data)['key'];window=tk.Tk();window.title('FRY Chicken · PC de respaldo');window.geometry('760x640');window.minsize(650,560)
 frame=ttk.Frame(window,padding=24);frame.pack(fill='both',expand=True)
 ttk.Label(frame,text='FRY CHICKEN · RECEPTOR DE RESPALDOS',font=('Segoe UI',16,'bold')).pack(anchor='w',pady=(0,16))
 ttk.Label(frame,text='Recibe copias independientes de todas tus cajas. Cerrar esta ventana no detiene el receptor.',wraplength=690).pack(anchor='w')
 status=tk.StringVar(value='Comprobando receptor…');ttk.Label(frame,textvariable=status,font=('Segoe UI',11,'bold')).pack(anchor='w',pady=12)
 ttk.Label(frame,text='Clave de vinculación · cópiala una vez en cada caja:').pack(anchor='w')
 entry=ttk.Entry(frame,show='•');entry.insert(0,key);entry.pack(fill='x',pady=6)
 def copy():window.clipboard_clear();window.clipboard_append(key);messagebox.showinfo('Clave copiada','En caja: Administrador > Respaldos en red > pega la clave > Buscar receptor > Guardar y comprobar.')
 ttk.Button(frame,text='Copiar clave de vinculación',command=copy).pack(anchor='w')
 ttk.Label(frame,text='Conexión por cable/red local o Internet con Tailscale. Bluetooth requiere una red PAN configurada por Windows en ambos equipos.',wraplength=690).pack(anchor='w',pady=12)
 ttk.Button(frame,text='Abrir configuración de Bluetooth',command=lambda:os.startfile('ms-settings:bluetooth')).pack(anchor='w')
 ttk.Label(frame,text='Últimos respaldos confirmados:').pack(anchor='w',pady=(15,5));listing=tk.Listbox(frame,height=7);listing.pack(fill='both',expand=True);manifests=[]
 def refresh():
  nonlocal manifests
  try:
   import urllib.request
   path='/status/'+'0'*32;headers=protocol.headers(key,'GET',path)
   with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(urllib.request.Request('http://127.0.0.1:5058'+path,headers=headers),timeout=.6) as r:reply=json.loads(protocol.unseal(key,r.read()))
   if reply.get('nonce')!=headers['X-FRY-Nonce']:raise ValueError()
   status.set('RECEPTOR ACTIVO · cable / LAN / Bluetooth PAN / Tailscale')
  except Exception:status.set('RECEPTOR DETENIDO · pulsa Iniciar receptor')
  manifests=sorted(data.glob('*/manifest.json'));listing.delete(0,'end')
  for p in manifests:
   try:
    m=json.loads(p.read_text('utf-8'));last=m.get('last_invoice') or {};listing.insert('end',p.parent.name[:10]+' · Factura '+str(last.get('fiscal_number') or last.get('number','—'))+' · '+m.get('confirmed_at',''))
   except Exception:continue
 def start():
  import ctypes
  result=ctypes.windll.shell32.ShellExecuteW(None,'runas',str(sys.executable),'--start',str(ROOT),0)
  if result<=32:messagebox.showerror('No se pudo iniciar','Se requiere autorización de Windows para iniciar la tarea.')
  else:window.after(2000,refresh)
 def export():
  selection=listing.curselection()
  if not selection:messagebox.showinfo('Selecciona una caja','Selecciona el respaldo de la caja que quieres recuperar.');return
  try:
   mp=manifests[selection[0]];m=json.loads(mp.read_text('utf-8'));blob=(mp.parent/m['file']).read_bytes()
   if protocol.digest(blob)!=m['sha256']:raise ValueError('El archivo no coincide con la confirmación')
   protocol.validate(blob);dest=filedialog.asksaveasfilename(defaultextension='.json.gz',initialfile='FRYChicken-'+mp.parent.name+'-'+str(m['sequence'])+'.json.gz')
   if dest:protocol.atomic(Path(dest),blob);messagebox.showinfo('Respaldo exportado','Copia este archivo a la PC nueva y utiliza Restaurar respaldo del POS.')
  except Exception as e:messagebox.showerror('Error al exportar',str(e))
 buttons=ttk.Frame(frame);buttons.pack(fill='x',pady=10)
 for text,command in [('Actualizar',refresh),('Iniciar receptor',start),('Exportar respaldo',export),('Abrir carpeta',lambda:os.startfile(str(data)))]:ttk.Button(buttons,text=text,command=command).pack(side='left',padx=3)
 ttk.Label(frame,text='Datos: '+str(data),wraplength=690).pack(anchor='w');refresh();window.mainloop()
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--data',default=str(DATA));parser.add_argument('--serve',action='store_true');parser.add_argument('--start',action='store_true');parser.add_argument('--install',action='store_true');parser.add_argument('--autostart',action='store_true');parser.add_argument('--remove',action='store_true');parser.add_argument('--self-test',action='store_true');args=parser.parse_args();data=Path(args.data)
 if args.self_test:
  assert protocol.unseal('test',protocol.seal('test',b'OK'))==b'OK'
  import tkinter as tk
  test=tk.Tk();test.withdraw();test.destroy()
  protocol.atomic(data/'self-test-ok.txt',b'OK');return
 if args.start:powershell('start_receiver.ps1',[]);return
 if args.install:
  prepare(data);powershell('register_receiver.ps1',['-InstallDir',str(ROOT),'-DataDir',str(data),'-AutoStart',str(int(args.autostart))]);return
 if args.remove:powershell('remove_receiver.ps1',[]);return
 if args.serve:serve(data)
 else:gui(data)
if __name__=='__main__':
 try:main()
 except Exception as e:
  if '--serve' not in sys.argv and '--install' not in sys.argv and '--remove' not in sys.argv:
   import tkinter.messagebox;tkinter.messagebox.showerror('FRY Chicken respaldo',str(e))
  sys.exit(1)
