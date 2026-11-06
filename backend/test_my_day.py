import copy, datetime as dt, unittest
from unittest.mock import patch
import my_day, schedule_routes, test_accounts
from core import Problem

class MyDayTests(unittest.TestCase):
 def setUp(self):
  self.user={'email':'bala@trice.nz','technician':'Bala','role':'admin'}
  self.now=dt.datetime(2026,11,5,0,0,tzinfo=dt.timezone.utc);self.day='2026-11-05'
  self.state={'staffSettings':{'technicians':[{'name':'Bala'},{'name':'Other'}]},'vehicles':[],
   'users':{'bala@trice.nz':{**self.user,'active':True}},'quotes':{'keep':{'id':'keep'}},'appointments':{
   'a':{'id':'a','date':self.day,'start':'09:00','duration':60,'technician':'Other','technicians':['Other','Bala'],'client':'Team client','address':'Road','notes':'Stored job notes','bookingControlsVersion':1,'bookingStatus':'confirmed','type':'Repair'},
   'b':{'id':'b','date':self.day,'start':'11:00','duration':30,'technician':'Other','client':'Private other job'},
   'c':{'id':'c','date':self.day,'start':'12:00','duration':30,'technician':'Bala','client':'Cancelled','cancelled':True}}}
 def command(self,state,action,**extra):
  command={'operationId':'operation_'+str(len(my_day.book(state,self.user)['operations'])).zfill(20),'date':self.day,'revision':my_day.book(state,self.user)['revision'],'action':action,'jobId':'a',**extra}
  return my_day.operation(state,self.user,command,self.now),command
 def test_private_filtered_route_free_and_read_does_not_write(self):
  original=copy.deepcopy(self.state)
  with patch.object(schedule_routes,'_provider',side_effect=AssertionError('No Google')):
   data=my_day.read(self.state,self.user,self.day,self.now)
  self.assertEqual([a['id'] for a in data['appointments']],['a']);self.assertEqual(data['plannedMinutes'],60)
  self.assertEqual(data['appointments'][0]['notes'],'Stored job notes');self.assertEqual(self.state,original)
  for user in ({**self.user,'email':''},{**self.user,'role':'guest'}):
   with self.assertRaises(Problem):my_day.read(self.state,user,self.day,self.now)
 def test_members_have_private_logs_and_unlinked_accounts_get_setup_guidance(self):
  (state,_),_=self.command(self.state,'times',sessions=[{'start':'08:00','end':'09:00'}])
  other={'email':'other@example.nz','technician':'Other','role':'tech'}
  view=my_day.read(state,other,self.day,self.now)
  self.assertEqual(set(a['id'] for a in view['appointments']),{'a','b'})
  self.assertEqual(view['day']['jobs'],{})
  command={'operationId':'other_member_operation_123','revision':0,'date':self.day,'action':'times','jobId':'b','sessions':[{'start':'10:00','end':'11:00'}],'email':self.user['email'],'technician':'Bala'}
  updated,_=my_day.operation(state,other,command,self.now)
  self.assertEqual(my_day.book(updated,self.user),my_day.book(state,self.user))
  self.assertIn('b',my_day.book(updated,other)['days'][self.day]['jobs'])
  unlinked={**other,'technician':''}
  self.assertTrue(my_day.read(updated,unlinked,self.day,self.now)['setupRequired'])
  with self.assertRaises(Problem):my_day.operation(updated,unlinked,command,self.now)
 def test_scott_is_excluded_by_verified_account_or_linked_identity(self):
  before=copy.deepcopy(self.state)
  for user in ({**self.user,'email':' SCOTT@TRICE.NZ '},{**self.user,'technician':' Scott Yearbury '}):
   with self.assertRaises(Problem):my_day.read(self.state,user,self.day,self.now)
   with self.assertRaises(Problem):my_day.operation(self.state,user,{},self.now)
  self.assertEqual(self.state,before)
 def test_timer_retry_is_idempotent_and_preserves_all_other_sections(self):
  (state,_),command=self.command(self.state,'start');again,replayed=my_day.operation(state,self.user,command,self.now+dt.timedelta(minutes=20))
  self.assertTrue(replayed);self.assertEqual(state,again)
  for key in self.state:self.assertEqual(state[key],self.state[key])
  self.now+=dt.timedelta(minutes=30);(state,_),_=self.command(state,'stop')
  s=state['myDayLogs'][self.user['email']]['days'][self.day]['jobs']['a']['sessions'][0]
  self.assertEqual((dt.datetime.fromisoformat(s['end'])-dt.datetime.fromisoformat(s['start'])).total_seconds(),1800)
  self.assertEqual(len(state['myDayLogs'][self.user['email']]['history']),2)
 def test_stale_revision_double_timer_and_ownership_rejected(self):
  (state,_),command=self.command(self.state,'start')
  for raw in ({**command,'operationId':'different_operation_1'},{**command,'revision':1,'operationId':'different_operation_2','jobId':'b'},{**command,'revision':1,'operationId':'different_operation_3'}):
   before=copy.deepcopy(state)
   with self.assertRaises(Problem):my_day.operation(state,self.user,raw,self.now)
   self.assertEqual(state,before)
 def test_custom_manual_times_overlap_finish_reopen_and_history(self):
  (state,_),_=self.command(self.state,'create',jobId='custom:1234567890123456',title='Workshop work')
  (state,_),_=self.command(state,'times',jobId='custom:1234567890123456',sessions=[{'start':'08:00','end':'09:00'}])
  before=copy.deepcopy(state)
  with self.assertRaises(Problem):self.command(state,'times',sessions=[{'start':'08:30','end':'09:30'}])
  self.assertEqual(before,state)
  (state,_),_=self.command(state,'finish')
  with self.assertRaises(Problem):self.command(state,'start')
  (state,_),_=self.command(state,'reopen');(state,_),_=self.command(state,'times',jobId='custom:1234567890123456',sessions=[])
  history=state['myDayLogs'][self.user['email']]['history']
  self.assertEqual(history[-1]['before']['jobs']['custom:1234567890123456']['sessions'][0]['start'],'2026-11-04T19:00:00+00:00')
 def test_manual_future_times_and_dates_preserve_other_records_and_history(self):
  original=copy.deepcopy(self.state)
  (state,_),command=self.command(self.state,'times',sessions=[{'start':'13:00','end':'14:00'}])
  session=my_day.book(state,self.user)['days'][self.day]['jobs']['a']['sessions'][0]
  self.assertEqual(my_day.local_time(self.day,'14:00').isoformat(),session['end'])
  again,replayed=my_day.operation(state,self.user,command,self.now)
  self.assertTrue(replayed);self.assertEqual(state,again)
  for key in original:self.assertEqual(state[key],original[key])
  tomorrow='2026-11-06';custom='custom:1234567890123456'
  (state,_),_=self.command(state,'create',date=tomorrow,jobId=custom,title='Custom work')
  (state,_),_=self.command(state,'times',date=tomorrow,jobId=custom,sessions=[{'start':'18:00','end':'19:00'}])
  self.assertEqual(len(my_day.book(state,self.user)['history']),3)
  with self.assertRaises(Problem):self.command(state,'start',date=tomorrow,jobId=custom)
  self.assertEqual(self.state,original)
 def test_invalid_order_and_dst_ambiguity_fail_without_mutation(self):
  original=copy.deepcopy(self.state)
  for sessions in ([{'start':'09:00','end':'08:00'}],[{'start':'09:00','end':'09:00'}],[{'start':'09:99','end':'10:00'}]):
   with self.assertRaises(Problem):self.command(self.state,'times',sessions=sessions)
  self.assertEqual(self.state,original)
  with self.assertRaises(Problem):my_day.local_time('2026-09-27','02:30')
  with self.assertRaises(Problem):my_day.local_time('2026-04-05','02:30')
 def test_cross_midnight_requires_explicit_correction(self):
  (state,_),_=self.command(self.state,'start');self.now+=dt.timedelta(days=1)
  with self.assertRaises(Problem):self.command(state,'stop')
  (state,_),_=self.command(state,'times',sessions=[{'start':'13:00','end':'14:00'}])
  self.assertIsNone(my_day.read(state,self.user,self.day,self.now)['active'])

class MyDayAPI(unittest.TestCase):
 def setUp(self):
  self.api=test_accounts.AccountsAPI();self.api.setUp();self.day=dt.datetime.now(my_day.ZONE).date().isoformat()
  self.api.store.state['vehicles']=[]
  self.api.store.state['users']['tech@example.nz'].update(name='Other member',technician='Other member')
 def test_scott_denied_on_read_and_write_for_both_roles_without_mutation(self):
  for role in ('admin','tech'):
   self.api.store.state['users']['tech@example.nz'].update(role=role,technician='Scott Yearbury')
   before=copy.deepcopy(self.api.store.state)
   for method in ('GET','POST'):self.assertEqual(self.api.call('/api/my-day',method,{'date':self.day},token='tech')[0],403)
   self.assertEqual(self.api.store.state,before)
 def test_authenticated_members_can_read_own_day_but_anonymous_access_is_denied(self):
  before=copy.deepcopy(self.api.store.state)
  self.assertEqual(self.api.call('/api/my-day',token='tech')[0],200)
  for method in ('GET','POST'):self.assertIn(self.api.call('/api/my-day',method,{'date':self.day},token='')[0],(401,403))
  self.assertEqual(before,self.api.store.state)
  self.assertEqual(self.api.call('/api/my-day')[0],200)
 def test_cas_rebase_rechecks_receipt_and_preserves_concurrent_business_edit(self):
  command={'date':self.day,'revision':0,'operationId':'create_custom_operation1','action':'create','jobId':'custom:1234567890123456','title':'Pilot work'}
  original=self.api.store.commit;calls=[]
  def racing(revision,state):
   if not calls:
    calls.append(True);self.api.store.state['quotes']['concurrent']={'id':'concurrent'};self.api.store.revision+=1;return False
   return original(revision,state)
  with patch.object(self.api.store,'commit',side_effect=racing):self.assertEqual(self.api.call('/api/my-day','POST',command)[0],200)
  self.assertIn('concurrent',self.api.store.state['quotes'])
  saved=copy.deepcopy(self.api.store.state);self.assertEqual(self.api.call('/api/my-day','POST',command)[0],200);self.assertEqual(saved,self.api.store.state)
 def test_uncertain_commit_retry_recovers_exact_receipt(self):
  command={'date':self.day,'revision':0,'operationId':'uncertain_custom_operation','action':'create','jobId':'custom:1234567890123456','title':'Pilot work'}
  original=self.api.store.commit
  def timeout(revision,state):original(revision,state);raise TimeoutError()
  with patch.object(self.api.store,'commit',side_effect=timeout):self.assertEqual(self.api.call('/api/my-day','POST',command)[0],200)
  self.assertEqual(len(self.api.store.state['myDayLogs']['bala@trice.nz']['history']),1)

if __name__=='__main__':unittest.main()
