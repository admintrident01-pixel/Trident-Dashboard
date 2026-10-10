import base64,copy,io,math,posixpath,re,zipfile
from xml.etree import ElementTree as ET
from core import Problem,decode,workbook_info
NS='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
RNS='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
BASE={'company':'Trident Community Equipment','street':'255 Port Road, Whangarei','postal':'PO Box 583, Whangarei','phone':'09 4302104','email':'support@trice.nz','account':'Trident Community Equipment','bank':'ASB','bankNumber':'12-3106-0008610-00','validDays':30,'gstPercent':15}
LABELS={'Company name':'company','Street address':'street','Postal address':'postal','Phone':'phone','Email':'email','Account name':'account','Bank':'bank','Account number':'bankNumber','Quote validity (days)':'validDays','GST percent':'gstPercent'}
TYPE_HEADERS=['Quote type','Category','Introduction / scope','Quoted by','Default job details','Default notes']
ITEM_HEADERS=['Quote type','Description','Quantity','Unit price excl GST']

def unpack(state):
 data=decode(state['workbook'],10*1024*1024);workbook_info(data)
 with zipfile.ZipFile(io.BytesIO(data)) as z:entries={name:z.read(name) for name in z.namelist()}
 wb=ET.fromstring(entries['xl/workbook.xml']);rels=ET.fromstring(entries['xl/_rels/workbook.xml.rels']);paths={}
 for s in wb.find('{'+NS+'}sheets'):
  target=next(r.get('Target') for r in rels if r.get('Id')==s.get('{'+RNS+'}id'))
  paths[s.get('name')]=posixpath.normpath(target.lstrip('/') if target.startswith('/') else 'xl/'+target)
 shared=[''.join(s.itertext()) for s in ET.fromstring(entries['xl/sharedStrings.xml'])] if 'xl/sharedStrings.xml' in entries else []
 def sheet(name):
  if name not in paths:return []
  rows=[]
  for row in ET.fromstring(entries[paths[name]]).findall('.//{'+NS+'}sheetData/{'+NS+'}row'):
   values={}
   for c in row:
    ref=re.sub(r'\d','',c.get('r',''));v=c.find('{'+NS+'}v');value=v.text if v is not None else ''
    if c.get('t')=='s':value=shared[int(value)]
    elif c.get('t')=='inlineStr':value=''.join(c.find('{'+NS+'}is').itertext())
    values[ref]=value or ''
   rows.append(values)
  return rows
 return entries,paths,sheet
def records(rows,first):
 at=next((i for i,row in enumerate(rows) if row.get('A')==first),None)
 if at is None:raise Problem(400,f'Missing settings column header: {first}.')
 header=rows[at]
 return [{title:row.get(col,'') for col,title in header.items()} for row in rows[at+1:] if any(row.values())]
def read(state):
 _,_,sheet=unpack(state);business=copy.deepcopy(BASE)
 for r in records(sheet('Business Details'),'Setting'):
  key=LABELS.get(r.get('Setting'),r.get('Setting'))
  if key=='GST (%)':key='gstPercent'
  if key in business:business[key]=float(r.get('Value') or 0) if key in ('gstPercent','validDays') else r.get('Value','')
 types=[]
 for r in records(sheet('Quote Types'),'Quote type'):
  name=r.get('Quote type','').strip()
  if not name:continue
  category=r.get('Category') or ('Vehicle' if 'vehicle' in name.lower() else 'Equipment' if 'equipment' in name.lower() else 'Other')
  types.append({'name':name,'category':category,'message':r.get('Introduction / scope',''),'by':r.get('Quoted by',''),'job':r.get('Default job details',''),'notes':r.get('Default notes',''),'items':[]})
 for r in records(sheet('Default Items'),'Quote type'):
  t=next((t for t in types if t['name']==r.get('Quote type','').strip()),None)
  if t and r.get('Description'):t['items'].append({'description':r['Description'],'qty':float(r.get('Quantity') or 0),'rate':float(r.get('Unit price excl GST') or 0)})
 email={'subjectPrefix':'Trident Community Equipment Quote','body':'Hello,\n\nPlease find the attached quote for the proposed work, Let us know if you have any questions.'}
 for r in records(sheet('Email Details'),'Setting'):
  if r.get('Setting')=='Subject prefix':email['subjectPrefix']=r.get('Value','')
  if r.get('Setting')=='Email message':email['body']=r.get('Value','')
 start,_=workbook_info(decode(state['workbook'],10*1024*1024))
 return {'business':business,'types':types,'emailSettings':email,'startNumber':start}
def text(v,label,limit=4000,required=False):
 if not isinstance(v,str) or len(v)>limit or re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]',v) or (required and not v.strip()):raise Problem(400,f'Enter a valid {label}.')
 return v
def num(v,label,minimum=0,maximum=100000000,integer=False):
 if isinstance(v,bool):raise Problem(400,f'Enter a valid {label}.')
 try:n=float(v)
 except (TypeError,ValueError):raise Problem(400,f'Enter a valid {label}.')
 if not math.isfinite(n) or not minimum<=n<=maximum or (integer and n!=int(n)):raise Problem(400,f'Enter a valid {label}.')
 return int(n) if integer else n
def validate(data):
 if not isinstance(data,dict) or not isinstance(data.get('business'),dict) or not isinstance(data.get('emailSettings'),dict):raise Problem(400,'Invalid quote settings.')
 business={k:text(data['business'].get(k),k,500) for k in BASE if k not in ('validDays','gstPercent')}
 business['validDays']=num(data['business'].get('validDays'),'validity days',1,3650,True)
 business['gstPercent']=num(data['business'].get('gstPercent'),'GST percent',0,100)
 email={k:text(data['emailSettings'].get(k),k,10000 if k=='body' else 250) for k in ('subjectPrefix','body')}
 start=num(data.get('startNumber'),'starting quote number',1,999999999,True)
 source=data.get('types')
 if not isinstance(source,list) or not 1<=len(source)<=200:raise Problem(400,'Keep at least one quote type (up to 200).')
 types=[];seen=set()
 for t in source:
  if not isinstance(t,dict):raise Problem(400,'Invalid quote type.')
  name=text(t.get('name'),'quote type name',160,True).strip()
  if name.casefold() in seen:raise Problem(400,'Quote type names must be unique.')
  seen.add(name.casefold());category=t.get('category')
  if category not in ('Equipment','Vehicle','Other'):raise Problem(400,'Choose a quote category.')
  row={'name':name,'category':category,**{k:text(t.get(k,''),k,12000 if k=='message' else 4000) for k in ('message','by','job','notes')},'items':[]}
  if not isinstance(t.get('items'),list) or len(t['items'])>200:raise Problem(400,'Invalid default items.')
  for item in t['items']:
   if not isinstance(item,dict):raise Problem(400,'Invalid default item.')
   row['items'].append({'description':text(item.get('description'),'item description',4000,True),'qty':num(item.get('qty'),'quantity'),'rate':num(item.get('rate'),'unit price')})
  types.append(row)
 return {'business':business,'emailSettings':email,'types':types,'startNumber':start}
def save(state,data):
 config=validate(data);entries,paths,_=unpack(state)
 def column(i):
  result=''
  while i:i,n=divmod(i-1,26);result=chr(65+n)+result
  return result
 def cell(ref,value):
  c=ET.Element('{'+NS+'}c',r=ref)
  if isinstance(value,(int,float)):ET.SubElement(c,'{'+NS+'}v').text=str(value)
  else:
   c.set('t','inlineStr');t=ET.SubElement(ET.SubElement(c,'{'+NS+'}is'),'{'+NS+'}t');t.set('{http://www.w3.org/XML/1998/namespace}space','preserve');t.text=str(value)
  return c
 def write(name,rows):
  if name not in paths:raise Problem(400,f'The original workbook is missing {name}.')
  doc=ET.fromstring(entries[paths[name]]);body=doc.find('{'+NS+'}sheetData');styles={}
  oldrows=list(body)
  def value(c):
   if c.get('t')=='s':
    shared=ET.fromstring(entries['xl/sharedStrings.xml']);return ''.join(shared[int(c.find('{'+NS+'}v').text)].itertext())
   return ''.join(c.itertext())
  header=next((r for r in oldrows if any(c.get('r')=='A'+r.get('r') and value(c)==rows[0][0] for c in r)),None)
  if header is None:raise Problem(400,f'Missing column headings in {name}.')
  first=int(header.get('r'));sample=next((r for r in oldrows if int(r.get('r'))>first),header)
  for role,old in [('header',header),('data',sample)]:
   for c in old:styles[(role,re.sub(r'\d','',c.get('r')))]=c.get('s')
  for old in oldrows:
   if int(old.get('r'))>=first:body.remove(old)
  for offset,values in enumerate(rows):
   n=first+offset;row=ET.SubElement(body,'{'+NS+'}row',r=str(n))
   for i,v in enumerate(values,1):
    col=column(i);c=cell(col+str(n),v);style=styles.get(('header' if offset==0 else 'data',col))
    if style:c.set('s',style)
    row.append(c)
  dimension=doc.find('{'+NS+'}dimension')
  if dimension is not None:dimension.set('ref',f'A1:{column(max(map(len,rows)))}{first+len(rows)-1}')
  entries[paths[name]]=ET.tostring(doc,encoding='utf-8',xml_declaration=True)
 write('Business Details',[['Setting','Value']]+[[label,config['business'][key]] for label,key in LABELS.items()])
 write('Email Details',[['Setting','Value'],['Subject prefix',config['emailSettings']['subjectPrefix']],['Email message',config['emailSettings']['body']]])
 write('Quote Types',[TYPE_HEADERS]+[[t['name'],t['category'],t['message'],t['by'],t['job'],t['notes']] for t in config['types']])
 write('Default Items',[ITEM_HEADERS]+[[t['name'],i['description'],i['qty'],i['rate']] for t in config['types'] for i in t['items']])
 # Only A2 changes in the register; all reserved numbers, records and styles remain.
 doc=ET.fromstring(entries[paths['Quote Register']]);body=doc.find('{'+NS+'}sheetData');row=next((r for r in body if r.get('r')=='2'),None)
 if row is None:row=ET.SubElement(body,'{'+NS+'}row',r='2')
 old=next((c for c in row if c.get('r')=='A2'),None);new=cell('A2',config['startNumber'])
 if old is not None:
  if old.get('s'):new.set('s',old.get('s'))
  index=list(row).index(old);row.remove(old);row.insert(index,new)
 else:row.insert(0,new)
 entries[paths['Quote Register']]=ET.tostring(doc,encoding='utf-8',xml_declaration=True)
 output=io.BytesIO()
 with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
  for name,value in entries.items():z.writestr(name,value)
 blob=output.getvalue();_,before=workbook_info(decode(state['workbook'],10*1024*1024));_,after=workbook_info(blob)
 if before!=after:raise Problem(400,'Quote history changed unexpectedly. Settings were not saved.')
 result=copy.deepcopy(state);result['workbook']=base64.b64encode(blob).decode()
 return result
