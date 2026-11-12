"""Immutable, administrator-only source job captures. Never writes to dbFLEX."""
import copy,datetime as dt,hashlib,json,math,re
from urllib.parse import urlsplit,parse_qs,urlencode
from core import Problem

UUID=re.compile(r'^[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}$')
LIMITS={'client':160,'street':500,'suburb':160,'city':160,'contact':160,'phone':200,'workPhone':200,'email':254,'invoiceTo':160,'poNumber':200,'assetNumber':200,'make':200,'model':200,'serial':200,'jobType':120,'problem':16000,'jobNotes':16000}
MAPPING_DEFAULTS={'client':'client','address':'clientAddress','phones':'clientAddress','equipment':'equipment','email':'recipientEmail','invoiceTo':'to','problem':'job','reference':'ref','jobNumber':'notes'}
MAPPING_TARGETS={'','client','clientAddress','clientLocality','to','recipientEmail','address','orgLocality','job','ref','equipment','vehicle','rego','by','message','notes'}

def mapping(state,user):
 require(user)
 return {'mappings':{**MAPPING_DEFAULTS,**state.get('jobImportMappings',{})}}

def save_mapping(state,user,data):
 require(user);values=data.get('mappings') if isinstance(data,dict) else None
 if not isinstance(values,dict) or set(values)!=set(MAPPING_DEFAULTS) or any(not isinstance(v,str) or v not in MAPPING_TARGETS for v in values.values()):raise Problem(400,'Choose a supported quote field for each source value.')
 before=mapping(state,user)['mappings'];result=copy.deepcopy(state)
 if values!=before:
  result['jobImportMappings']=copy.deepcopy(values)
  result.setdefault('jobImportMappingHistory',[]).append({'at':dt.datetime.now(dt.timezone.utc).isoformat(),'actor':user['email'],'before':before,'after':copy.deepcopy(values)})
 return result
def excluded(value):return re.sub('[^a-z0-9]','',str(value).casefold()) in ('hireloan','wheelchairservices','hiretotal','loanhireitems','solutioninvoiceremarks')

def require(user):
 if user.get('role')!='admin' or str(user.get('email','')).strip().casefold()=='scott@trice.nz' or str(user.get('technician','')).strip().casefold()=='scott yearbury':raise Problem(403,'Job imports are available to authorised administrators only.')

def text(value,limit):
 if not isinstance(value,str) or len(value)>limit or any(ord(c)<32 and c not in '\t\r\n' for c in value):raise Problem(400,'The imported job has invalid or oversized text. Nothing was shortened.')
 return value

def rows(value,limit):
 if not isinstance(value,list) or len(value)>limit:raise Problem(400,'The imported job has too many fields or rows. Nothing was shortened.')
 return value

def link(value):
 if not isinstance(value,dict):raise Problem(400,'Invalid source link.')
 try:u=urlsplit(text(value.get('url'),4000))
 except ValueError:raise Problem(400,'Invalid source link.')
 if u.scheme!='https' or u.netloc!='capitalmobility.dbflex.net' or not re.fullmatch(r'/secure/db/96562/(preview|documentopen|file|attachment|download|image)[^/]*',u.path,re.I):raise Problem(400,'Unsupported source link.')
 params=parse_qs(u.query,keep_blank_values=True);params.pop('back',None)
 return {'label':text(value.get('label'),1000),'url':u._replace(query=urlencode(params,doseq=True)).geturl()}

def cell(value):
 if not isinstance(value,dict):raise Problem(400,'Invalid source field.')
 return {'text':text(value.get('text'),16000),'links':[link(v) for v in rows(value.get('links',[]),30)]}

def clean(data):
 if not isinstance(data,dict) or len(json.dumps(data,ensure_ascii=False).encode())>1500000:raise Problem(400,'The imported job is too large. Nothing was shortened.')
 identifier=data.get('transferId','');source=data.get('source',{});fields=data.get('fields',{})
 if not isinstance(identifier,str) or not UUID.fullmatch(identifier) or type(data.get('version')) is not int or data.get('version') not in (1,2) or not isinstance(source,dict) or not isinstance(fields,dict):raise Problem(400,'Invalid job capture.')
 created=data.get('createdAt')
 if isinstance(created,bool) or not isinstance(created,(int,float)) or not math.isfinite(created) or created<0 or created>dt.datetime.now(dt.timezone.utc).timestamp()*1000+60000:raise Problem(400,'Invalid capture date.')
 record=source.get('recordId','');number=source.get('jobNumber','')
 if not isinstance(record,str) or not re.fullmatch(r'\d{1,12}',record) or not isinstance(number,str) or not re.fullmatch(r'\d{1,20}',number):raise Problem(400,'Invalid source job identity.')
 try:u=urlsplit(text(source.get('url'),4000));params=parse_qs(u.query)
 except ValueError:raise Problem(400,'Invalid source job URL.')
 if u.scheme!='https' or u.netloc!='capitalmobility.dbflex.net' or u.path!='/secure/db/96562/preview.aspx' or params.get('t')!=['736016'] or params.get('id')!=[record]:raise Problem(400,'Invalid source job URL.')
 result={'version':data['version'],'transferId':identifier,'createdAt':created,'source':{'recordId':record,'jobNumber':number,'url':f'https://capitalmobility.dbflex.net/secure/db/96562/preview.aspx?t=736016&id={record}'},'fields':{k:text(fields.get(k,''),n) for k,n in LIMITS.items()}}
 if not result['fields']['client'].strip():raise Problem(400,'A client name is required.')
 if data['version']==2:
  capture=data.get('capture')
  if not isinstance(capture,dict):raise Problem(400,'Full job capture is missing.')
  sections=[];tables=[]
  for s in rows(capture.get('sections'),100):
   if not isinstance(s,dict):raise Problem(400,'Invalid job section.')
   if excluded(s.get('title')):continue
   fields=[]
   for f in rows(s.get('fields'),200):
    if not isinstance(f,dict):raise Problem(400,'Invalid source field.')
    if excluded(f.get('label')):continue
    fields.append({'label':text(f.get('label'),200),**cell(f)})
   sections.append({'title':text(s.get('title'),200),'fields':fields})
  for t in rows(capture.get('tables'),30):
   if not isinstance(t,dict):raise Problem(400,'Invalid job table.')
   if excluded(t.get('title')):continue
   columns=[text(c,200) for c in rows(t.get('columns'),40)];values=[]
   for r in rows(t.get('rows'),1000):
    if not isinstance(r,dict) or len(rows(r.get('cells'),40))!=len(columns):raise Problem(400,'A table row does not match its headings.')
    if r.get('kind','data') not in ('data','summary'):raise Problem(400,'Invalid table row type.')
    values.append({'kind':r.get('kind','data'),'cells':[cell(c) for c in r['cells']]})
   tables.append({'title':text(t.get('title'),200),'columns':columns,'rows':values})
  extras=[]
  for s in rows(capture.get('extras',[]),30):
   if not isinstance(s,dict):raise Problem(400,'Invalid related section.')
   if excluded(s.get('title')):continue
   extras.append({'title':text(s.get('title'),200),**cell(s)})
  result['capture']={'sections':sections,'tables':tables,'extras':extras,'warnings':[text(v,1000) for v in rows(capture.get('warnings',[]),100)]}
 return result

def save(state,user,data,objects):
 require(user);payload=clean(data);identifier=payload['transferId'];raw=json.dumps(payload,sort_keys=True,separators=(',',':')).encode();digest=hashlib.sha256(raw).hexdigest()
 old=state.get('jobImports',{}).get(identifier)
 if old:
  if old['sha256']!=digest:raise Problem(409,'This capture is already saved with different contents. Send the source job again for a new capture.')
  return state,old,True
 object_key='job-imports/'+identifier+'/'+digest+'.json'
 try:objects.put(object_key,raw)
 except Exception:
  try:stored=objects.get(object_key)
  except Exception:raise Problem(503,'The source capture could not be stored. Retry this same capture safely.') from None
  if stored!=raw:raise Problem(409,'The stored source capture does not match. Nothing was overwritten.')
 result=copy.deepcopy(state);entry={'id':identifier,'objectKey':object_key,'source':payload['source'],'client':payload['fields']['client'],'street':payload['fields']['street'],'sha256':digest,'importedBy':user['email'],'importedAt':dt.datetime.now(dt.timezone.utc).isoformat()}
 result.setdefault('jobImports',{})[identifier]=entry
 return result,entry,False

def read(state,user,params,objects):
 require(user);identifier=params.get('id',[''])[0]
 if identifier:
  entry=state.get('jobImports',{}).get(identifier)
  if not entry:raise Problem(404,'This saved job capture was not found.')
  try:raw=objects.get(entry['objectKey'])
  except Exception:raise Problem(503,'The saved source file is unavailable. No job data was changed.') from None
  if hashlib.sha256(raw).hexdigest()!=entry['sha256']:raise Problem(409,'The source file failed its integrity check. No job data was changed.')
  return {'entry':{**copy.deepcopy(entry),'payload':clean(json.loads(raw))}}
 search=text(params.get('search',[''])[0],200).casefold()
 try:page=max(1,int(params.get('page',['1'])[0]))
 except ValueError:raise Problem(400,'Choose a valid page.')
 entries=sorted(state.get('jobImports',{}).values(),key=lambda e:e['importedAt'],reverse=True)
 entries=[e for e in entries if search in (e['source']['jobNumber']+' '+e['client']+' '+e['street']).casefold()]
 total=len(entries);page=min(page,max(1,math.ceil(total/20)))
 return {'entries':[{'id':e['id'],'jobNumber':e['source']['jobNumber'],'client':e['client'],'importedAt':e['importedAt']} for e in entries[(page-1)*20:page*20]],'page':page,'pages':max(1,math.ceil(total/20)),'total':total}

def remove_all(state,user,data):
 """Remove reviewed captures recoverably, without touching their allocated records/files."""
 require(user)
 if not isinstance(data,dict) or data.get('confirmed') is not True:raise Problem(400,'Confirm removal of imported job records.')
 expected=data.get('ids');current=state.get('jobImports',{})
 if not isinstance(expected,list) or any(not isinstance(i,str) for i in expected) or len(set(expected))!=len(expected) or set(expected)!=set(current):raise Problem(409,'Imported jobs changed. Review the current list before removing them.')
 result=copy.deepcopy(state)
 import recycle
 for key,entry in current.items():recycle.put(result,'importedJob',key,entry,entry.get('client') or key,user['email'])
 result['jobImports']={}
 return result
