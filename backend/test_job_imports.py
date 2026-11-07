import copy,io,json,unittest
from pathlib import Path
import accounts,job_imports,schedule,schedule_history
from app import Application
from core import Problem
from test_accounts import MemoryStore

FIXTURE=Path(__file__).resolve().parents[1]/'work-tests/fixtures/dbflex-full-job.json'
def payload():return json.loads(FIXTURE.read_text(encoding='utf-8'))
ADMIN={'email':'bala@trice.nz','role':'admin','technician':'Example technician'}

class MemoryObjects:
 def __init__(self):self.files={}
 def put(self,key,data):
  if key in self.files:raise FileExistsError(key)
  self.files[key]=data
 def get(self,key):return self.files[key]

class JobImportTests(unittest.TestCase):
 def setUp(self):self.objects=MemoryObjects()
 def test_excluded_remarks_are_neither_archived_nor_returned(self):
  data=payload();data['fields']['solution']='NEVER COPY THIS'
  data['capture']['sections'][0]['fields'].append({'label':'Solution/Invoice Remarks','text':'NEVER COPY THIS','links':[]})
  state,entry,_=job_imports.save({},ADMIN,data,self.objects)
  self.assertNotIn(b'NEVER COPY THIS',self.objects.get(entry['objectKey']))
  self.assertNotIn('NEVER COPY THIS',json.dumps(job_imports.read(state,ADMIN,{'id':[entry['id']]},self.objects)))
 def test_full_capture_is_immutable_idempotent_and_retains_every_source_value(self):
  initial={'appointments':{'existing':{'notes':'Keep this'}},'uploads':{'old':'keep'}};original=copy.deepcopy(initial)
  result,entry,replayed=job_imports.save(initial,ADMIN,payload(),self.objects)
  self.assertEqual(initial,original);self.assertFalse(replayed)
  self.assertEqual(json.loads(self.objects.get(entry['objectKey']))['capture']['tables'][0]['rows'][0]['cells'][5]['text'],'25%')
  self.assertEqual(json.loads(self.objects.get(entry['objectKey']))['capture']['sections'][0]['fields'][1]['text'],'EXAMPLE-CLAIM')
  self.assertEqual(result['appointments'],original['appointments']);self.assertNotIn('payload',result['jobImports'][entry['id']]);self.assertLess(len(json.dumps(result['jobImports'])),1200)
  stored=json.loads(self.objects.get(entry['objectKey']));self.assertFalse(any(t['title']=='Hire/Loan' for t in stored['capture']['tables']));self.assertFalse(any(f['label']=='Hire Total' for s in stored['capture']['sections'] for f in s['fields']))
  same,again,replayed=job_imports.save(result,ADMIN,payload(),self.objects);self.assertTrue(replayed);self.assertIs(same,result);self.assertEqual(again,entry)
  changed=payload();changed['fields']['client']='Another value'
  with self.assertRaises(Problem):job_imports.save(result,ADMIN,changed,self.objects)
  self.assertEqual(result['jobImports'][entry['id']],entry)

 def test_only_admins_except_scott_can_save_list_or_read_captures(self):
  state,entry,_=job_imports.save({},ADMIN,payload(),self.objects)
  for user in ({'role':'tech','email':'tech@example.invalid'},{'role':'admin','email':' Scott@trice.nz '},{'role':'admin','email':'alias@example.invalid','technician':'Scott Yearbury'}):
   for operation in (lambda:job_imports.save(state,user,payload(),self.objects),lambda:job_imports.read(state,user,{},self.objects),lambda:job_imports.read(state,user,{'id':[entry['id']]},self.objects)):
    with self.assertRaises(Problem) as ctx:operation()
    self.assertEqual(ctx.exception.status,403)
  self.assertEqual(job_imports.read(state,ADMIN,{'search':['90001']},self.objects)['total'],1)
  self.assertEqual(job_imports.read(state,ADMIN,{'id':[entry['id']]},self.objects)['entry']['payload']['source']['recordId'],'70001')

 def test_invalid_captures_rejected_without_partial_writes(self):
  for change in (lambda p:p.update(transferId='bad'),lambda p:p.update(createdAt=float('nan')),lambda p:p['source'].update(url='https://evil.invalid/'),lambda p:p['capture']['extras'][0]['links'][0].update(url='javascript:alert(1)'),lambda p:p['capture']['tables'][0]['rows'][0]['cells'].pop(),lambda p:p['capture']['sections'][0]['fields'][0].update(text='x'*16001)):
   data=payload();change(data)
   with self.assertRaises(Problem):job_imports.save({},ADMIN,data,self.objects)
 def test_capture_file_integrity_is_checked_before_details_are_returned(self):
  state,entry,_=job_imports.save({},ADMIN,payload(),self.objects)
  self.objects.files[entry['objectKey']]=b'changed file'
  with self.assertRaises(Problem) as ctx:job_imports.read(state,ADMIN,{'id':[entry['id']]},self.objects)
  self.assertEqual(ctx.exception.status,409)

 def test_appointment_keeps_source_link_through_edit_and_undo_redo(self):
  state,entry,_=job_imports.save({'staffSettings':{'technicians':[{'name':'Example technician'}]}},ADMIN,payload(),self.objects)
  booking={'date':'2026-11-09','technician':'Example technician','technicians':['Example technician'],'start':'09:00','duration':60,'client':'Example Client','address':'12 Example Road','type':'Repair','notes':'2 x Replacement castor','jobImportId':entry['id']}
  changed,appointment=schedule.save(state,booking,ADMIN)
  self.assertEqual(appointment['jobImportId'],entry['id'])
  changed=schedule_history.record(state,changed,ADMIN['email'],booking['date'],'Imported job')
  undone=schedule_history.apply(changed,ADMIN['email'],booking['date'],'undo');self.assertNotIn(appointment['id'],undone.get('appointments',{}))
  redone=schedule_history.apply(undone,ADMIN['email'],booking['date'],'redo');self.assertEqual(redone['appointments'][appointment['id']]['jobImportId'],entry['id'])
  _,edited=schedule.save(redone,{**redone['appointments'][appointment['id']],'notes':'Edited notes'},ADMIN);self.assertEqual(edited['jobImportId'],entry['id'])
  with self.assertRaises(Problem):schedule.save(state,{**booking,'jobImportId':'22345678-1234-4234-8234-123456789012'},ADMIN)

class JobImportAPI(unittest.TestCase):
 def setUp(self):
  users={u['email']:{**u,'active':True,'verified':True,'name':u['email']} for u in (ADMIN,{'email':'scott@trice.nz','role':'admin','technician':'Scott Yearbury'},{'email':'tech@example.invalid','role':'tech','technician':'Example technician'})}
  self.store=MemoryStore({'users':users,'appointments':{},'quotes':{},'pdfs':{}})
  self.app=Application(self.store,MemoryObjects(),lambda token:{'admin':ADMIN['email'],'scott':'scott@trice.nz','tech':'tech@example.invalid'}.get(token,''),'http://127.0.0.1:18790',local=True)
 def call(self,token='admin',body=None,query=''):
  raw=json.dumps(body).encode() if body is not None else b'';meta=[]
  env={'REQUEST_METHOD':'POST' if body is not None else 'GET','PATH_INFO':'/api/job-imports','QUERY_STRING':query,'HTTP_ORIGIN':'http://127.0.0.1:18790','HTTP_AUTHORIZATION':'Bearer '+token,'CONTENT_LENGTH':str(len(raw)),'wsgi.input':io.BytesIO(raw),'REMOTE_ADDR':'127.0.0.1'}
  result=b''.join(self.app(env,lambda status,headers:meta.append(status)))
  return int(meta[0][:3]),json.loads(result)
 def test_api_permissions_and_duplicate_retry(self):
  for token in ('scott','tech'):
   self.assertEqual(self.call(token,body=payload())[0],403);self.assertEqual(self.call(token)[0],403)
  self.assertEqual(self.call(body=payload())[0],200);revision=self.store.revision
  self.assertEqual(self.call(body=payload())[0],200);self.assertEqual(self.store.revision,revision)
  self.assertEqual(self.call(query='id='+payload()['transferId'])[1]['entry']['payload']['fields']['client'],'Example Client')
 def test_scoped_save_retries_and_preserves_concurrent_appointment(self):
  commit=self.store.commit;first=True
  def conflict(revision,state):
   nonlocal first
   if first:
    first=False;self.store.state['appointments']['concurrent']={'notes':'Live user edit'};self.store.revision+=1;return False
   return commit(revision,state)
  self.store.commit=conflict
  self.assertEqual(self.call(body=payload())[0],200);self.assertEqual(self.store.state['appointments']['concurrent']['notes'],'Live user edit')
 def test_permission_revocation_during_retry_is_respected(self):
  def revoke(revision,state):
   self.store.state['users'][ADMIN['email']]['role']='tech';self.store.revision+=1;return False
  self.store.commit=revoke
  self.assertEqual(self.call(body=payload())[0],403);self.assertEqual(self.store.state.get('jobImports',{}),{})
 def test_uncertain_commit_is_recovered_without_a_duplicate(self):
  commit=self.store.commit;first=True
  def uncertain(revision,state):
   nonlocal first
   saved=commit(revision,state)
   if first:first=False;raise RuntimeError('Response lost after successful commit')
   return saved
  self.store.commit=uncertain
  self.assertEqual(self.call(body=payload())[0],200);self.assertEqual(len(self.store.state['jobImports']),1)
 def test_malformed_nested_values_return_400_without_storing_any_capture(self):
  for modify in (lambda p:p['capture']['sections'][0]['fields'].append(None),lambda p:p['capture']['extras'].append(None),lambda p:p['source'].update(url='https://[invalid/'),lambda p:p.update(version=True)):
   data=payload();modify(data);self.assertEqual(self.call(body=data)[0],400)
  self.assertEqual(self.store.state.get('jobImports',{}),{})

if __name__=='__main__':unittest.main()
