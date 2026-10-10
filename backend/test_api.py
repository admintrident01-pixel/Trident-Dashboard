import os,sys,unittest,tempfile,base64,json,io,zipfile,uuid,copy,threading
from pathlib import Path
from xml.etree import ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parent))
from app import Application
from storage import SQLiteStore,LocalObjects
from core import workbook_info
from test_support import TestDirectory
NS='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
def write_row(book,n,id,revision,status,name):
 with zipfile.ZipFile(io.BytesIO(book)) as zin:entries={p:zin.read(p) for p in zin.namelist()}
 wb=ET.fromstring(entries['xl/workbook.xml']);sheet=next(s for s in wb.find('{'+NS+'}sheets') if s.get('name')=='Quote Register');rid=sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id');rel=next(r for r in ET.fromstring(entries['xl/_rels/workbook.xml.rels']) if r.get('Id')==rid);target=rel.get('Target');target=target.lstrip('/') if target.startswith('/') else 'xl/'+target
 doc=ET.fromstring(entries[target]);rows=doc.find('{'+NS+'}sheetData');row=None
 for r in rows:
  a=r.find("{*}c[@r='A"+r.get('r')+"']")
  if a is not None and ''.join(a.itertext())==str(n):row=r;break
 if row is None:row=ET.SubElement(rows,'{'+NS+'}row',r=str(max(int(r.get('r')) for r in rows)+1))
 row.clear();row.set('r',str(max([5,*[int(r.get('r')) for r in rows if r is not row]])+1));rn=row.get('r')
 for col,value in {'A':str(n),'AE':status,'AF':id,'AG':str(revision),'AC':name}.items():
  c=ET.SubElement(row,'{'+NS+'}c',r=col+rn,t='inlineStr');s=ET.SubElement(c,'{'+NS+'}is');ET.SubElement(s,'{'+NS+'}t').text=value
 entries[target]=ET.tostring(doc,encoding='utf-8');out=io.BytesIO()
 with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
  for p,data in entries.items():z.writestr(p,data)
 return out.getvalue()
class TestAPI(unittest.TestCase):
 def setUp(self):
  self.tmp=TestDirectory();self.store=SQLiteStore(str(Path(self.tmp.name)/'state.db'));self.objects=LocalObjects(Path(self.tmp.name)/'pdfs');self.book=Path(os.environ['TEST_WORKBOOK']).read_bytes();self.store.initialise({'workbook':base64.b64encode(self.book).decode(),'quotes':{},'pdfs':{}});self.app=Application(self.store,self.objects,lambda token:'nikita.trident2024@gmail.com' if token=='owner' else 'other@gmail.com',origin='https://trident.nikita-trident2024.workers.dev');start,rows=workbook_info(self.book);self.n=max([start-1,*rows])+1
 def tearDown(self):self.tmp.cleanup()
 def call(self,path,method='GET',body=None,revision=None,token='owner',origin='https://trident.nikita-trident2024.workers.dev'):
  b=json.dumps(body).encode() if isinstance(body,dict) else body or b'';e={'REQUEST_METHOD':method,'PATH_INFO':path.split('?')[0],'QUERY_STRING':path.partition('?')[2],'HTTP_ORIGIN':origin,'HTTP_AUTHORIZATION':'Bearer '+token if token else '', 'CONTENT_LENGTH':str(len(b)),'wsgi.input':io.BytesIO(b)}
  if revision is not None:e['HTTP_IF_MATCH']=f'"{revision}"'
  meta=[];result=b''.join(self.app(e,lambda status,headers:meta.append((int(status[:3]),dict(headers)))));return meta[0][0],meta[0][1],result
 def payload(self,status='Draft',id=None,revision=0,n=None):
  n=n or self.n;id=id or str(uuid.uuid4());book=base64.b64decode(self.store.read()[1]['workbook']);filename=f'Client - Repair - Scooter - {n} - 09-10-2026.pdf';p={'id':id,'revision':revision,'state':status,'data':{'version':1,'fields':{'number':str(n),'client':'Test client','date':'2026-10-09','job':'Repair'},'lines':[{'description':'Repairs','qty':1,'rate':100}]},'workbook':base64.b64encode(write_row(book,n,id,revision+1,status,filename)).decode()}
  if status=='Finalised':p.update(filename=filename,pdf=base64.b64encode(b'%PDF-test-fixture').decode())
  return p
 def test_auth_and_origin(self):
  self.assertEqual(self.call('/api/catalog',token='')[0],401);self.assertEqual(self.call('/api/catalog',token='wrong')[0],403);self.assertEqual(self.call('/api/catalog',origin='https://evil.example')[0],403);self.assertEqual(self.call('/api/catalog',method='OPTIONS')[0],200);self.assertEqual(self.call('/api/session')[0],200)
 def test_draft_finalise_edit_delete_reserved(self):
  p=self.payload();self.assertEqual(self.call('/api/quote-save','POST',p,1)[0],200)
  p=self.payload('Finalised',p['id'],1);self.assertEqual(self.call('/api/quote-save','POST',p,2)[0],200);self.assertEqual(self.call('/api/pdf?name='+p['filename'])[2],b'%PDF-test-fixture')
  stale=copy.deepcopy(p);p=self.payload('Finalised',p['id'],2);self.assertEqual(self.call('/api/quote-save','POST',p,3)[0],200);self.assertEqual(self.call('/api/quote-save','POST',stale,4)[0],409)
  p=self.payload('Deleted',p['id'],3);self.assertEqual(self.call('/api/quote-save','POST',p,4)[0],200);self.assertEqual(len(self.store.read()[1]['pdfs']),0);self.assertEqual(self.call('/api/quote-save','POST',self.payload(),5)[0],409);self.assertEqual(self.call('/api/quote-save','POST',self.payload(n=self.n+1),5)[0],200)
 def test_recycle_quote_preserves_pdf_restores_and_purges_reserved_number(self):
  p=self.payload('Finalised');self.assertEqual(self.call('/api/quote-save','POST',p,1)[0],200)
  old=self.store.read()[1];key=old['pdfs'][p['filename']];number=self.n
  deleted=self.payload('Deleted',p['id'],1);self.assertEqual(self.call('/api/quote-save','POST',deleted,2)[0],200)
  self.assertEqual(self.objects.get(key),b'%PDF-test-fixture')
  status,headers,body=self.call('/api/recycle-bin');items=json.loads(body)['items'];self.assertEqual(status,200)
  self.assertEqual(items[0]['type'],'quote')
  self.assertEqual(self.call('/api/recycle-bin','POST',{'action':'restore','ids':[items[0]['id']]},3)[0],200)
  restored=self.store.read()[1];self.assertEqual(restored['quotes'][str(number)]['state'],'Finalised')
  self.assertEqual(restored['quotes'][str(number)]['revision'],3)
  self.assertEqual(self.call('/api/pdf?name='+p['filename'])[2],b'%PDF-test-fixture')
  self.assertEqual(workbook_info(base64.b64decode(restored['workbook']))[1][number]['AE'],'Finalised')
  deleted=self.payload('Deleted',p['id'],3);self.assertEqual(self.call('/api/quote-save','POST',deleted,4)[0],200)
  self.assertEqual(self.call('/api/recycle-bin','POST',{'action':'purge','ids':['quote:'+str(number)],'confirmed':True},5)[0],200)
  purged=self.store.read()[1];self.assertTrue(purged['quotes'][str(number)]['purged'])
  self.assertIn(number,workbook_info(base64.b64decode(purged['workbook']))[1])
  self.assertEqual(json.loads(self.call('/api/recycle-bin')[2])['items'],[])
  self.assertFalse((self.objects.path/key).exists())
  self.assertEqual(self.call('/api/quote-save','POST',self.payload(n=number),6)[0],409)

 def test_recycle_restores_quote_type_without_reverting_register(self):
  import quote_settings
  revision,state=self.store.read();config=quote_settings.read(state)
  removed=config['types'].pop()
  self.assertTrue(config['types'])
  before=workbook_info(base64.b64decode(state['workbook']))[1]
  self.assertEqual(self.call('/api/quote-settings','POST',config,revision)[0],200)
  items=json.loads(self.call('/api/recycle-bin')[2])['items']
  item=next(row for row in items if row['type']=='quoteType' and row['title']==removed['name'])
  self.assertEqual(self.call('/api/recycle-bin','POST',{'action':'restore','ids':[item['id']]},revision+1)[0],200)
  restored=self.store.read()[1]
  self.assertIn(removed,quote_settings.read(restored)['types'])
  self.assertEqual(before,workbook_info(base64.b64decode(restored['workbook']))[1])

 def test_workbook_conflict_and_history(self):
  self.assertEqual(self.call('/api/quote-save','POST',self.payload(),99)[0],409);p=self.payload();self.assertEqual(self.call('/api/quote-save','POST',p,1)[0],200);self.assertEqual(self.call('/api/workbook','POST',self.book,2)[0],400)
 def test_staged_pdf_cleanup_after_cas_conflict(self):
  old=self.store.commit;self.store.commit=lambda *args:False;p=self.payload('Finalised');self.assertEqual(self.call('/api/quote-save','POST',p,1)[0],409);self.assertEqual(len(list(Path(self.tmp.name).rglob('*.pdf'))),0);self.store.commit=old
 def test_atomic_compare_and_swap(self):
  revision,state=self.store.read();results=[];threads=[threading.Thread(target=lambda:results.append(self.store.commit(revision,state))) for _ in range(2)]
  for t in threads:t.start()
  for t in threads:t.join()
  self.assertEqual(sorted(results),[False,True])
 def test_timesheet_validation_and_conflicts(self):
  p={'technician':'Test technician','signature':'Signed name','weekStart':'2026-10-05','notes':'Weekly note','days':[{'status':'Work','method':'direct','hours':8 if i<5 else 0,'notes':''} for i in range(7)]}
  p['days'][0]={'status':'Work','method':'times','start':'08:00','finish':'15:30'}
  p['days'][1]={'status':'Work','method':'direct','hours':4}
  self.assertEqual(self.call('/api/timesheets/config',token='')[0],401)
  for alter in ('signature','weekStart','hours','finish','leave'):
   bad=copy.deepcopy(p)
   if alter=='signature':bad['signature']=''
   elif alter=='weekStart':bad['weekStart']='2026-10-06'
   elif alter=='hours':bad['days'][2]['hours']=7.3
   elif alter=='finish':bad['days'][0]['finish']='07:00'
   else:bad['days'][1]={'status':'Sick leave','method':'times','start':'08:00','finish':'12:00'}
   self.assertEqual(self.call('/api/timesheets','POST',bad,1)[0],400,alter)
  self.assertEqual(self.store.read()[0],1)
  code,headers,body=self.call('/api/timesheets','POST',p,1)
  self.assertEqual(code,200);self.assertEqual(json.loads(body)['total'],35.5)
  self.assertEqual(self.call('/api/timesheets','POST',p,1)[0],409)
  self.assertEqual(len(json.loads(self.call('/api/timesheets')[2])['timesheets']),1)
  self.assertIn('Test technician',json.loads(self.call('/api/timesheets/config')[2])['technicians'])
  self.assertEqual(base64.b64decode(self.store.read()[1]['workbook']),self.book)
 def test_leave_approval_sync_and_history(self):
  p={'technician':'Scott Yearbury','leaveType':'Annual leave','startDate':'2026-10-05','endDate':'2026-10-06','hoursPerDay':8,'includeWeekends':False,'reason':'Holiday','status':'Approved'}
  self.assertEqual(self.call('/api/leave',token='')[0],401)
  code,headers,body=self.call('/api/leave','POST',p,1);self.assertEqual(code,200);r=json.loads(body)['request'];self.assertEqual(r['status'],'Pending');self.assertEqual(r['totalHours'],16)
  self.assertEqual(json.loads(self.call('/api/timesheets/config')[2])['approvedLeave'],[])
  self.assertEqual(self.call('/api/leave','POST',p,2)[0],409)
  sheet={'technician':'Scott Yearbury','signature':'Scott','weekStart':'2026-10-05','notes':'','days':[{'status':'Annual leave' if i<2 else 'Work','method':'direct','hours':8 if i<5 else 0} for i in range(7)]}
  self.assertEqual(self.call('/api/timesheets','POST',sheet,2)[0],400)
  decision={'id':r['id'],'revision':1,'status':'Approved','decisionNotes':'Approved holiday'}
  self.assertEqual(self.call('/api/leave-decision','POST',decision,2,token='wrong')[0],403)
  self.assertEqual(self.call('/api/leave-decision','POST',decision,2)[0],200)
  self.assertEqual(len(json.loads(self.call('/api/timesheets/config')[2])['approvedLeave']),1)
  self.assertEqual(self.call('/api/leave-decision','POST',decision,3)[0],409)
  bad=copy.deepcopy(sheet);bad['days'][0]['hours']=4;self.assertEqual(self.call('/api/timesheets','POST',bad,3)[0],400)
  self.assertEqual(self.call('/api/timesheets','POST',sheet,3)[0],200)
  recorded=list(self.store.read()[1]['timesheets'].values())[0];self.assertIn(r['id'],recorded['approvedLeaveIds'])
  self.assertEqual(self.call('/api/leave-decision','POST',{'id':r['id'],'revision':2,'status':'Cancelled'},4)[0],200)
  self.assertEqual(json.loads(self.call('/api/timesheets/config')[2])['approvedLeave'],[])
  self.assertEqual(list(self.store.read()[1]['timesheets'].values())[0],recorded)
  code,headers,body=self.call('/api/leave','POST',p,5);self.assertEqual(code,200);new=json.loads(body)['request']
  d={'id':new['id'],'revision':1,'status':'Declined'};self.assertEqual(self.call('/api/leave-decision','POST',d,6)[0],400)
  d['decisionNotes']='Alternative dates needed';self.assertEqual(self.call('/api/leave-decision','POST',d,6)[0],200)
  self.assertEqual(len(json.loads(self.call('/api/leave')[2])['requests']),2)
  self.assertEqual(self.call('/api/timesheets','POST',sheet,7)[0],400)
 def test_staff_settings_persist_and_validate(self):
  self.assertEqual(self.call('/api/staff-settings',token='')[0],401)
  self.assertEqual(len(json.loads(self.call('/api/staff-settings')[2])['technicians']),8)
  bad={'technicians':[{'name':'Nikita','rego':'ABC123'},{'name':' nikita ','rego':''}]}
  self.assertEqual(self.call('/api/staff-settings','POST',bad,1)[0],400)
  self.assertEqual(self.call('/api/staff-settings','POST',{'technicians':[{'name':''}]},1)[0],400)
  valid={'technicians':[{'name':' Test technician ','rego':' abc123 '}]}
  self.assertEqual(self.call('/api/staff-settings','POST',valid,1)[0],200)
  self.assertEqual(json.loads(self.call('/api/staff-settings')[2])['technicians'],[{'name':'Test technician','rego':'ABC123','staffType':'technician','hasVehicle':True}])
  self.assertIn('Test technician',json.loads(self.call('/api/timesheets/config')[2])['technicians'])
  self.assertEqual(self.call('/api/staff-settings','POST',valid,1)[0],409)
  self.assertEqual(base64.b64decode(self.store.read()[1]['workbook']),self.book)
 def test_vehicle_checks_history_edits_and_validation(self):
  self.assertEqual(self.call('/api/vehicles',token='')[0],401)
  fleet=json.loads(self.call('/api/vehicles')[2]);self.assertEqual(len(fleet['vehicles']),10)
  p={'vehicleId':'VEH-01','registration':'QEK183','driver':'Joby Shearing','checkDate':'2026-10-09','vehicleYear':'2020','overall':'All OK','checklist':['']*22,'comments':'No issues','serviceDue':'2027-01-09','serviceDueKm':100000,'wofExpiry':'2027-09-25','wofDueKm':100000,'alignmentDue':'2027-01-09','alignmentDueKm':100000,'regoExpiry':'2027-09-26','odometer':90009,'rucCurrent':101020,'rucDue':None,'signature':'Joby'}
  bad=copy.deepcopy(p);bad['checklist'][0]='Fail';self.assertEqual(self.call('/api/vehicle-checks','POST',bad,1)[0],400)
  bad=copy.deepcopy(p);bad['overall']='Issues found';self.assertEqual(self.call('/api/vehicle-checks','POST',bad,1)[0],400)
  bad=copy.deepcopy(p);bad['odometer']=-1;self.assertEqual(self.call('/api/vehicle-checks','POST',bad,1)[0],400)
  bad=copy.deepcopy(p);bad['signature']='';self.assertEqual(self.call('/api/vehicle-checks','POST',bad,1)[0],400)
  code,headers,body=self.call('/api/vehicle-checks','POST',p,1);self.assertEqual(code,200);saved=json.loads(body)['check'];self.assertEqual(saved['checklist'],['Pass']*22);self.assertEqual(saved['revision'],1)
  edit=copy.deepcopy(saved);edit['comments']='Revised notes';edit['overall']='Issues found';edit['checklist'][0]='Fail';self.assertEqual(self.call('/api/vehicle-checks','POST',edit,2)[0],200)
  self.assertEqual(self.call('/api/vehicle-checks','POST',edit,3)[0],409)
  checks=json.loads(self.call('/api/vehicles')[2])['checks'];self.assertEqual(len(checks),1);self.assertEqual(checks[0]['revision'],2);self.assertEqual(checks[0]['comments'],'Revised notes')
  rows=json.loads(self.call('/api/vehicles')[2])['vehicles'];self.assertEqual(self.call('/api/vehicles','POST',{'vehicles':rows[1:]},3)[0],200)
  removed=json.loads(self.call('/api/vehicles')[2]);self.assertEqual(len(removed['checks']),1);self.assertEqual(removed['removedVehicles'][0]['id'],'VEH-01')
  checks[0]['comments']='Edit after removal';self.assertEqual(self.call('/api/vehicle-checks','POST',checks[0],4)[0],200)
  self.assertEqual(self.call('/api/vehicle-checks','POST',p,5)[0],400)
  self.assertEqual(self.call('/api/vehicles','POST',{'vehicles':rows},5)[0],400)
  self.assertEqual(self.call('/api/vehicles','POST',{'vehicles':[]},5)[0],200)
  self.assertEqual(json.loads(self.call('/api/vehicles')[2])['vehicles'],[])
  self.assertEqual(base64.b64decode(self.store.read()[1]['workbook']),self.book)
 def test_fleet_edits_preserve_initial_readings(self):
  rows=json.loads(self.call('/api/vehicles')[2])['vehicles'];rows[0]['registration']='NEW123';rows[0]['baseline']={};self.assertEqual(self.call('/api/vehicles','POST',{'vehicles':rows},1)[0],200)
  saved=json.loads(self.call('/api/vehicles')[2])['vehicles'];self.assertEqual(saved[0]['registration'],'NEW123');self.assertEqual(saved[0]['baseline']['odometer'],90009)
  bad=copy.deepcopy(rows);bad[1]['registration']='NEW123';self.assertEqual(self.call('/api/vehicles','POST',{'vehicles':bad},2)[0],400)
  self.assertEqual(self.call('/api/vehicles','POST',{'vehicles':rows[1:]},2)[0],200)
 def test_quote_settings_migrate_and_preserve_register(self):
  self.assertEqual(self.call('/api/quote-settings',token='')[0],401)
  cfg=json.loads(self.call('/api/quote-settings')[2]);self.assertGreaterEqual(len(cfg['types']),4)
  p=self.payload();self.assertEqual(self.call('/api/quote-save','POST',p,1)[0],200)
  before=copy.deepcopy(self.store.read()[1]);_,records=workbook_info(base64.b64decode(before['workbook']))
  cfg['business'].update(gstPercent=17.5,validDays=45,bankNumber='123456',company='Updated business')
  cfg['emailSettings']['subjectPrefix']='Updated quote';cfg['startNumber']=1800
  cfg['types'].append({'name':'New web quote','category':'Other','message':'Custom scope','by':'Nikita','job':'Default job','notes':'Default notes','items':[{'description':'New service','qty':2,'rate':123.45}]})
  self.assertEqual(self.call('/api/quote-settings','POST',cfg,2)[0],200)
  saved=json.loads(self.call('/api/quote-settings')[2]);self.assertEqual(saved,cfg)
  after=self.store.read()[1];self.assertEqual(after['quotes'],before['quotes']);self.assertEqual(after['pdfs'],before['pdfs']);start,newrecords=workbook_info(base64.b64decode(after['workbook']));self.assertEqual(start,1800);self.assertEqual(newrecords,records)
  bad=copy.deepcopy(cfg);bad['business']['gstPercent']=101;self.assertEqual(self.call('/api/quote-settings','POST',bad,3)[0],400)
  bad=copy.deepcopy(cfg);bad['types'][0]['message']='bad\x00text';self.assertEqual(self.call('/api/quote-settings','POST',bad,3)[0],400)
  self.assertEqual(self.call('/api/quote-settings','POST',cfg,2)[0],409)
 def test_time_defaults(self):
  self.assertEqual(json.loads(self.call('/api/time-settings')[2]),{'start':'08:00','finish':'16:00'})
  self.assertEqual(self.call('/api/time-settings','POST',{'start':'09:00','finish':'17:30'},1)[0],200)
  self.assertEqual(json.loads(self.call('/api/timesheets/config')[2])['defaultTimes'],{'start':'09:00','finish':'17:30'})
  self.assertEqual(self.call('/api/time-settings','POST',{'start':'09:10','finish':'17:30'},2)[0],400)
  self.assertEqual(self.call('/api/time-settings','POST',{'start':'17:00','finish':'08:00'},2)[0],400)
if __name__=='__main__':unittest.main()
