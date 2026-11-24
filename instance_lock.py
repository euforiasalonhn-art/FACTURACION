"""Bloqueo de proceso Windows: adquirir antes de leer cualquier byte."""
import errno,msvcrt
from pathlib import Path
class AlreadyRunning(RuntimeError):pass

def acquire(path,message):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 handle=path.open('a+b')
 try:
  # Windows permite bloquear una región más allá del final del archivo.
  # No leer ni escribir: una instancia anterior puede tener bloqueado ese byte.
  handle.seek(0)
  try:msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
  except OSError as error:
   if error.errno in (errno.EACCES,errno.EAGAIN,errno.EDEADLK) or getattr(error,'winerror',None) in (32,33,36):raise AlreadyRunning(message) from error
   raise
  return handle
 except BaseException:
  handle.close();raise
