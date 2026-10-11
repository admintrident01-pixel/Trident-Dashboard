import base64, copy, datetime, io, json, re, uuid, zipfile
from xml.etree import ElementTree as ET
class Problem(Exception):
 def __init__(self,status,message):self.status=status;super().__init__(message)
def decode(value,limit):
 try:data=base64.b64decode(value,validate=True)
 except Exception:raise Problem(400,'Invalid uploaded file.')
 if len(data)>limit:raise Problem(400,'Uploaded file is too large.')
 return data
def workbook_info(data):
 try:
  with zipfile.ZipFile(io.BytesIO(data)) as z:
   if sum(i.file_size for i in z.infolist())>32*1024*1024:raise ValueError('Oversized archive')
   ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
   wb=ET.fromstring(z.read('xl/workbook.xml'));rels=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
   shared=[]
   if 'xl/sharedStrings.xml' in z.namelist():shared=[''.join(si.itertext()) for si in ET.fromstring(z.read('xl/sharedStrings.xml'))]
   sheet=next((s for s in wb.find('s:sheets',ns) if s.get('name')=='Quote Register'),None)
   if sheet is None:raise ValueError('Missing Quote Register')
   rid=sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id');target=next(r.get('Target') for r in rels if r.get('Id')==rid)
   path=target.lstrip('/') if target.startswith('/') else 'xl/'+target
   rows={}
   for row in ET.fromstring(z.read(path)).findall('.//s:sheetData/s:row',ns):
    values={}
    for cell in row:
     ref=re.sub(r'\d','',cell.get('r',''));v=cell.find('s:v',ns);text=v.text if v is not None else ''
     if cell.get('t')=='s':text=shared[int(text)]
     elif cell.get('t')=='inlineStr':text=''.join(cell.find('s:is',ns).itertext())
     values[ref]=text or ''
    rows[int(row.get('r'))]=values
   start=int(rows.get(2,{}).get('A',1750));records={}
   if start<1:raise ValueError('Invalid starting number')
   for rowno,row in rows.items():
    if rowno<6 or not any(row.values()):continue
    number=row.get('A','')
    if not number:
     m=re.search(r' - (\d+) - \d{2}-\d{2}-\d{4}\.pdf$',row.get('AC',''));number=m.group(1) if m else ''
    n=int(number)
    if n<1 or n in records:raise ValueError('Duplicate or invalid quote number')
    records[n]=row
   return start,records
 except Problem:raise
 except Exception:raise Problem(400,'Choose a valid Excel workbook with its Quote Register and existing quote numbers intact.')
def safe_pdf(name):
 if not isinstance(name,str) or not name.lower().endswith('.pdf') or len(name)>240 or re.search(r'[\\/:*?"<>|\x00-\x1f]',name):raise Problem(400,'Invalid PDF filename.')
 return name
def save_quote(state,p,objects,actor=None):
 state=copy.deepcopy(state);data=p.get('data',{});fields=data.get('fields',{})
 try:number=int(fields['number']);uuid.UUID(p['id']);revision=int(p.get('revision',0))
 except Exception:raise Problem(400,'Invalid quote identity or number.')
 status=p.get('state');lines=data.get('lines')
 if number<1 or status not in ('Draft','Finalised','Deleted') or not isinstance(lines,list) or not lines:raise Problem(400,'Invalid quote data.')
 if len(json.dumps(data))>1024*1024:raise Problem(400,'Quote text is too large.')
 start,rows=workbook_info(decode(state['workbook'],10*1024*1024));existing=state['quotes'].get(str(number));legacy=bool(p.get('legacy'))
 if existing:
  if existing['state']=='Deleted':raise Problem(409,'This quote has been deleted. Its number remains reserved.')
  if existing['id']!=p['id'] or existing['revision']!=revision:raise Problem(409,'This quote changed in another window. Open it again from Home before editing.')
 elif number in rows:
  if rows[number].get('AE')=='Deleted' or not legacy or revision!=int(rows[number].get('AG') or 0):raise Problem(409,'This quote number is already reserved.')
 else:
  if status=='Deleted':raise Problem(404,'This quote no longer exists.')
  next_number=max([start-1,*rows,*[int(n) for n in state['quotes']]])+1
  if number<next_number:raise Problem(409,f'Quote number is unavailable. The next number is {next_number}.')
 newbook=decode(p.get('workbook',''),10*1024*1024);_,newrows=workbook_info(newbook)
 if not set(rows).issubset(newrows):raise Problem(400,'Existing quote numbers must remain in Excel.')
 row=newrows.get(number,{})
 if row.get('AE')!=status or row.get('AF')!=p['id'] or int(row.get('AG') or 0)!=revision+1:raise Problem(400,'Quote status or identity is missing from Excel.')
 if status=='Finalised' and (not (fields.get('client','').strip() or fields.get('to','').strip()) or not fields.get('date') or not fields.get('job','').strip()):raise Problem(400,'Enter the client, date and job details.')
 previous=existing.get('pdfFilename','') if existing else rows.get(number,{}).get('AC','');pdfname=previous;upload=None;garbage=[]
 if status=='Finalised':
  pdfname=safe_pdf(p.get('filename'));pdf=decode(p.get('pdf',''),15*1024*1024)
  if not pdf.startswith(b'%PDF-'):raise Problem(400,'Invalid PDF.')
  if pdfname in state['pdfs'] and pdfname!=previous:raise Problem(409,'Another quote already uses this PDF filename.')
  upload='quotes/'+str(uuid.uuid4())+'.pdf';objects.put(upload,pdf)
  if previous in state['pdfs']:garbage.append(state['pdfs'].pop(previous))
  state['pdfs'][pdfname]=upload
 if status=='Deleted':
  import recycle
  snapshot=existing or {'id':p['id'],'revision':revision,'state':'Finalised' if previous in state['pdfs'] else 'Draft','createdAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'pdfFilename':previous,'data':data}
  recycle.put(state,'quote',str(number),snapshot,'Quote '+str(number),extra={'pdfKey':state['pdfs'].get(previous)})
  state['pdfs'].pop(previous,None) # Object remains available through the recycle-bin snapshot.
 stamp=datetime.datetime.now(datetime.timezone.utc).isoformat();entry={'id':p['id'],'revision':revision+1,'state':status,'createdAt':existing['createdAt'] if existing else stamp,'updatedAt':stamp,'pdfFilename':pdfname,'sourceDraftName':'','data':data}
 creator=existing.get('createdByName') or existing.get('data',{}).get('fields',{}).get('by','') if existing else rows.get(number,{}).get('C','') if legacy else ''
 if not creator and not (existing or legacy):creator=(actor or {}).get('technician') or (actor or {}).get('name') or (actor or {}).get('email') or fields.get('by','')
 entry['createdByName']=creator
 entry['createdByEmail']=existing.get('createdByEmail','') if existing else (actor or {}).get('email','') if not legacy else ''
 state['quotes'][str(number)]=entry;state['workbook']=base64.b64encode(newbook).decode()
 return state,entry,upload,garbage
