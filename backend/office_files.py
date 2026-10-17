"""Authenticated office library; metadata in app state, bytes in object storage."""
import base64,copy,datetime,mimetypes,re,uuid,zipfile,io
from xml.etree import ElementTree as ET
from core import Problem
MAX_FILE=25*1024*1024
def listing(state):
 return {'items':[{k:v for k,v in row.items() if k!='key'} for row in state.get('officeFiles',{}).values()]}
def name(value):
 value=str(value or '').strip()
 if not value or len(value)>180 or re.search(r'[\\/\x00-\x1f]',value):raise Problem(400,'Enter a name of up to 180 characters without slashes.')
 return value
def parent_check(rows,parent,exclude=''):
 seen={exclude} if exclude else set()
 while parent:
  row=rows.get(parent)
  if parent in seen or not row or row.get('deleted') or row['kind']!='folder':raise Problem(400,'Choose a valid folder. Folders cannot be moved inside themselves.')
  seen.add(parent);parent=row['parent']
def action(state,p,user,objects,commit):
 if p.get('action') in ('copy-items','move-items'):return transfer(state,p,user,objects,commit)
 result=copy.deepcopy(state);rows=result.setdefault('officeFiles',{});action=p.get('action');uploaded=None
 if action in ('folder','upload'):
  parent=str(p.get('parent',''));parent_check(rows,parent);title=name(p.get('name'))
  row={'id':str(uuid.uuid4()),'kind':'folder' if action=='folder' else 'file','name':title,'parent':parent,'updated':datetime.datetime.now(datetime.timezone.utc).isoformat(),'by':user['email'],'deleted':False,'version':1}
  if action=='upload':
   try:raw=base64.b64decode(p.get('content',''),validate=True)
   except Exception:raise Problem(400,'The file could not be read. Choose it again.')
   if not raw or len(raw)>MAX_FILE:raise Problem(413,'Choose a non-empty file up to 25 MB.')
   row.update(size=len(raw),key='office-files/'+row['id'],mime=mimetypes.guess_type(title)[0] or 'application/octet-stream')
   objects.put(row['key'],raw);uploaded=row['key']
  rows[row['id']]=row
 else:
  row=rows.get(p.get('id'))
  if not row:raise Problem(404,'This file or folder is no longer available.')
  if p.get('version')!=row['version']:raise Problem(409,'This item changed. Refresh and try again.')
  if action=='rename':row['name']=name(p.get('name'))
  elif action=='move':parent_check(rows,str(p.get('parent','')),row['id']);row['parent']=str(p.get('parent',''))
  elif action in ('trash','restore'):
   if action=='restore':parent_check(rows,row['parent'])
   row['deleted']=action=='trash'
  else:raise Problem(400,'Choose a file action.')
  row['version']+=1;row['updated']=datetime.datetime.now(datetime.timezone.utc).isoformat();row['by']=user['email']
 try:commit(result)
 except Exception:
  if uploaded:
   try:objects.delete(uploaded)
   except Exception:pass
  raise
 return listing(result)
def transfer(state,p,user,objects,commit):
 result=copy.deepcopy(state);rows=result.setdefault('officeFiles',{});refs=p.get('items');destination=str(p.get('parent',''));parent_check(rows,destination)
 if not isinstance(refs,list) or not refs or len(refs)>200:raise Problem(400,'Select between 1 and 200 items.')
 ids=set()
 for ref in refs:
  if not isinstance(ref,dict):raise Problem(400,'Choose valid files.')
  row=rows.get(ref.get('id'))
  if not row or row.get('deleted'):raise Problem(404,'A selected item is no longer available. Refresh the file list.')
  parent_check(rows,row['parent'])
  if ref.get('version')!=row['version']:raise Problem(409,row['name']+' changed. Select it again before pasting.')
  ids.add(row['id'])
 roots=[]
 for id in ids:
  parent=rows[id]['parent'];nested=False
  while parent:
   if parent in ids:nested=True;break
   parent=rows[parent]['parent']
  if not nested:roots.append(id)
 for id in roots:
  if rows[id]['kind']=='folder':parent_check(rows,destination,id)
 now=datetime.datetime.now(datetime.timezone.utc).isoformat();created=[]
 def unique(title,parent):
  names={r['name'].casefold() for r in rows.values() if r['parent']==parent and not r.get('deleted')}
  if title.casefold() not in names:return title
  stem,dot,extension=title.rpartition('.')
  if not dot:stem=title;extension=''
  for n in range(1,10001):
   suffix=' (copy)' if n==1 else ' (copy '+str(n)+')';candidate=stem[:max(1,180-len(suffix)-len(extension)-(1 if dot else 0))]+suffix+('.'+extension if dot else '')
   if candidate.casefold() not in names:return candidate
  raise Problem(400,'Too many duplicate names in this folder.')
 original=copy.deepcopy(rows)
 def duplicate(id,parent):
  source=original[id];row={**source,'id':str(uuid.uuid4()),'parent':parent,'name':unique(source['name'],parent),'version':1,'updated':now,'by':user['email']}
  if row['kind']=='file':
   raw=objects.get(source['key']);row['key']='office-files/'+row['id'];objects.put(row['key'],raw);created.append(row['key'])
  rows[row['id']]=row
  if row['kind']=='folder':
   for child in original.values():
    if child['parent']==id and not child.get('deleted'):duplicate(child['id'],row['id'])
 try:
  for id in roots:
   if p['action']=='copy-items':duplicate(id,destination)
   elif rows[id]['parent']!=destination:rows[id].update(parent=destination,version=rows[id]['version']+1,updated=now,by=user['email'])
  commit(result)
 except Exception:
  for key in created:
   try:objects.delete(key)
   except Exception:pass
  raise
 return listing(result)
def read(state,id,objects):
 row=state.get('officeFiles',{}).get(id)
 if not row or row.get('deleted') or row['kind']!='file':raise Problem(404,'This file is unavailable.')
 parent_check(state['officeFiles'],row['parent'])
 raw=objects.get(row['key']);preview=None;ext=row['name'].rsplit('.',1)[-1].lower()
 if ext in ('docx','pptx','xlsx'):
  try:
   with zipfile.ZipFile(io.BytesIO(raw)) as z:
    if sum(i.file_size for i in z.infolist())>60*1024*1024:raise ValueError('Expanded file too large')
    if ext=='docx':
     doc=ET.fromstring(z.read('word/document.xml'));ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
     preview='\n'.join(''.join(p.itertext()) for p in doc.findall('.//w:p',ns))[:250000]
    elif ext=='pptx':
     paths=sorted((p for p in z.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml',p)),key=lambda p:int(re.search(r'(\d+)\.xml',p).group(1)))
     preview='\n\n'.join('Slide '+str(i+1)+'\n'+'\n'.join(n.text or '' for n in ET.fromstring(z.read(p)).iter() if n.tag.endswith('}t')) for i,p in enumerate(paths[:100]))[:250000]
    else:
     ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'};strings=[]
     if 'xl/sharedStrings.xml' in z.namelist():strings=[''.join(n.itertext()) for n in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',ns)]
     sheets=[]
     for path in sorted(p for p in z.namelist() if re.fullmatch(r'xl/worksheets/sheet\d+\.xml',p))[:20]:
      lines=[]
      for rowxml in ET.fromstring(z.read(path)).findall('.//s:row',ns)[:200]:
       values=[]
       for cell in rowxml.findall('s:c',ns)[:50]:
        v=cell.find('s:v',ns);value=v.text or '' if v is not None else ''.join(cell.itertext())
        if cell.get('t')=='s':value=strings[int(value)]
        values.append(cell.get('r','')+': '+value)
       lines.append(' | '.join(values))
      sheets.append(path.rsplit('/',1)[-1]+'\n'+'\n'.join(lines))
     preview='\n\n'.join(sheets)[:250000]
  except Exception:preview=None
 return {'name':row['name'],'mime':row['mime'],'content':base64.b64encode(raw).decode(),'preview':preview}
