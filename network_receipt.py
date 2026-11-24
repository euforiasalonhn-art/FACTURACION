"""Texto nativo para impresoras de red: conserva el contenido, nunca rasteriza."""
from html.parser import HTMLParser
import textwrap,unicodedata

class Node:
 def __init__(self,tag='',attrs=()):self.tag=tag;self.attrs=dict(attrs);self.children=[]

class TicketParser(HTMLParser):
 def __init__(self):super().__init__(convert_charrefs=True);self.root=Node();self.stack=[self.root]
 def handle_starttag(self,tag,attrs):
  node=Node(tag,attrs);self.stack[-1].children.append(node)
  if tag not in ['br','hr','img','meta','link','input','col','wbr']:self.stack.append(node)
 def handle_startendtag(self,tag,attrs):self.handle_starttag(tag,attrs);self.handle_endtag(tag)
 def handle_endtag(self,tag):
  for i in range(len(self.stack)-1,0,-1):
   if self.stack[i].tag==tag:del self.stack[i:];break
 def handle_data(self,data):self.stack[-1].children.append(data)

def clean(value):
 value=unicodedata.normalize('NFC',str(value))
 value=value.replace('\u00a0',' ').replace('·','-').replace('—','-').replace('−','-')
 return ''.join(ch if ch=='\n' or not unicodedata.category(ch).startswith('C') else ' ' for ch in value)

def inline(node):
 if isinstance(node,str):return node
 if node.tag in ['img','script','style','head']:return ''
 if node.tag=='br':return '\n'
 if node.tag=='input':return ''
 return ' '.join(inline(x) for x in node.children)

def wrapped(value,columns):
 result=[]
 for part in clean(value).splitlines():
  text=' '.join(part.split())
  if text:result.extend(textwrap.wrap(text,columns,break_long_words=True,break_on_hyphens=False))
 return result

def descendants(node,tag):
 for child in node.children:
  if isinstance(child,Node):
   if child.tag==tag:yield child
   else:yield from descendants(child,tag)

def table_lines(node,columns):
 rows=[[ ' '.join(clean(inline(c)).split()) for c in row.children if isinstance(c,Node) and c.tag in ['td','th']] for row in descendants(node,'tr')]
 rows=[r for r in rows if r]
 if not rows:return []
 result=[];items=rows[0][0].lower().startswith('cant')
 if items:result.append('-'*columns)
 for i,row in enumerate(rows):
  if items and len(row)>=2:
   if i==0:result.extend(wrapped('Cant. Descripción',columns))
   else:
    result.extend(wrapped(row[0]+' x '+row[1],columns))
    if len(row)>=4:
     left='P/U: '+row[2];right='Total: '+row[3]
     result.extend([left+' '*(columns-len(left)-len(right))+right] if len(left)+len(right)<columns else wrapped(left+' / '+right,columns))
   if i==0:result.append('-'*columns)
  elif len(row)==2:
   left,right=row
   if len(right)<columns-4:
    parts=wrapped(left,max(4,columns-len(right)-1)) or ['']
    result.extend(parts[:-1]);result.append(parts[-1]+' '*(columns-len(parts[-1])-len(right))+right)
   else:result.extend(wrapped(left+' '+right,columns))
  else:result.extend(wrapped(' '.join(row),columns))
 if items:result.append('-'*columns)
 return result

def document_text(html,columns=48):
 columns=int(columns)
 if not 24<=columns<=64:raise ValueError('Selecciona entre 24 y 64 caracteres por línea')
 parser=TicketParser();parser.feed(html);parser.close()
 blocks={'div','p','h1','h2','h3','h4','table','hr','section','article','header','footer','ul','li'}
 def render(node):
  if isinstance(node,str):return wrapped(node,columns)
  if node.tag in ['img','script','style','head']:return []
  if node.tag=='table':return table_lines(node,columns)
  if node.tag=='hr':return ['-'*columns]
  if not any(isinstance(c,Node) and c.tag in blocks for c in node.children):return wrapped(inline(node),columns)
  result=[];pending=[]
  for child in node.children:
   if isinstance(child,Node) and child.tag in blocks:
    result.extend(wrapped(' '.join(pending),columns));pending=[];result.extend(render(child))
   else:pending.append(inline(child))
  result.extend(wrapped(' '.join(pending),columns));return result
 return '\n'.join(render(parser.root)).strip()+'\n'

def payload(html,options,role='cash'):
 text=document_text(html,options.get('columns',32 if options.get('width')==58 else 48))
 encoding=options.get('encoding','cp850')
 pages={'cp850':2,'cp437':0,'cp1252':16,'ascii':0}
 if encoding not in pages:raise ValueError('Codificación de impresora no admitida')
 if encoding=='ascii':text=unicodedata.normalize('NFKD',text).encode('ascii','ignore').decode('ascii')
 raw=text.encode(encoding,errors='replace')
 feed=max(1,min(8,int(options.get('feed',3))))
 protocol=options.get('protocol','escpos')
 if protocol=='plain':return raw+b'\n'*feed
 if protocol!='escpos':raise ValueError('Selecciona ESC/POS o texto simple')
 start=b'\x1b@\x1bt'+bytes([pages[encoding]])+b'\x1bM\x00\x1b!\x00\x1da\x00\x1ba\x00\x1br\x00\x1bE'+bytes([1 if role=='kitchen' else 0])
 end=b'\x1bE\x00'+b'\n'*feed+(b'\x1dV\x01' if options.get('cut',True) else b'')
 return start+raw+end
