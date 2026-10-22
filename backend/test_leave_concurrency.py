"""Scoped leave commands tested against genuine competing register commits."""
import copy,concurrent.futures,threading,time,unittest,uuid
from unittest.mock import patch
import accounts,test_accounts

class LeaveConcurrency(unittest.TestCase):
 def setUp(self):
  self.api=test_accounts.AccountsAPI();self.api.setUp();self.store=self.api.store
  self.store.state['users'][accounts.FIRST_ADMIN]['verified']=True
  self.store.state['reminderSettings']={'leaveRecipients':[accounts.FIRST_ADMIN]}
  self.request={'technician':'Scott Yearbury','leaveType':'Annual leave','startDate':'2027-02-01','endDate':'2027-02-01','startTime':'08:00','endTime':'16:00','hoursPerDay':8,'reason':'Synthetic concurrency test','operationId':uuid.uuid4().hex}
  self.sleep=patch('app.time.sleep');self.sleep.start();self.addCleanup(self.sleep.stop)
 def submit(self,**changes):return self.api.call('/api/leave','POST',{**self.request,**changes},token='tech',match=False)
 def entry(self):
  code,data,_=self.submit();self.assertEqual(code,200,data);return data['request']
 def command(self,entry,**changes):return {'id':entry['id'],'revision':entry['revision'],'status':'Approved','decisionNotes':'','operationId':uuid.uuid4().hex,**changes}
 def mails(self):return self.store.state.get('mailOutbox',{})
 def test_unrelated_save_during_commit_is_rebased_and_preserved(self):
  original=self.store.commit;first=True
  def racing(revision,state):
   nonlocal first
   if first:
    first=False;rev,current=self.store.read();current['appointments']={'sample':{'id':'sample','client':'Concurrent schedule save'}};current['reminderJob']={'queued':7};original(rev,current)
   return original(revision,state)
  with patch.object(self.store,'commit',side_effect=racing):code,data,_=self.submit()
  self.assertEqual(code,200,data);self.assertEqual(self.store.state['appointments']['sample']['client'],'Concurrent schedule save');self.assertEqual(self.store.state['reminderJob'],{'queued':7})
  self.assertEqual(len(self.store.state['leaveRequests']),1);self.assertEqual(len(self.mails()),2)
 def test_uncertain_commit_and_lost_http_response_replay_one_leave_and_mail_event(self):
  original=self.store.commit;first=True
  def uncertain(revision,state):
   nonlocal first
   committed=original(revision,state)
   if first and committed:first=False;raise TimeoutError('Synthetic lost commit acknowledgement')
   return committed
  with patch.object(self.store,'commit',side_effect=uncertain):code,data,_=self.submit()
  self.assertEqual(code,200,data);self.assertTrue(data['replayed'])
  saved=copy.deepcopy(self.store.state);code,replayed,_=self.submit()
  self.assertEqual(code,200,replayed);self.assertEqual(replayed['request']['id'],data['request']['id']);self.assertTrue(replayed['replayed']);self.assertEqual(self.store.state,saved);self.assertEqual(len(self.mails()),2)
 def test_lost_decision_response_replays_without_email_or_revision_increment(self):
  entry=self.entry();command=self.command(entry)
  code,first,_=self.api.call('/api/leave-decision','POST',command,match=False);self.assertEqual(code,200,first)
  saved=copy.deepcopy(self.store.state);code,replayed,_=self.api.call('/api/leave-decision','POST',command,match=False)
  self.assertEqual(code,200,replayed);self.assertTrue(replayed['replayed']);self.assertEqual(saved,self.store.state);self.assertEqual(replayed['request']['revision'],2);self.assertEqual(len(self.mails()),3)
 def test_global_etag_can_be_stale_but_per_leave_revision_must_match(self):
  entry=self.entry();command=self.command(entry)
  self.assertEqual(self.api.call('/api/leave-decision','POST',command,match=False)[0],200)
  stale=self.command(entry,status='Declined',decisionNotes='Concurrent decision')
  code,data,_=self.api.call('/api/leave-decision','POST',stale,match=False)
  self.assertEqual(code,409,data);self.assertIn('leave request changed',data['error']);self.assertEqual(len(self.mails()),3)
 def test_reusing_a_key_for_different_details_is_rejected(self):
  self.entry();before=copy.deepcopy(self.store.state);code,data,_=self.submit(reason='Edited after an uncertain response')
  self.assertEqual(code,409,data);self.assertIn('different details',data['error']);self.assertEqual(before,self.store.state)
 def test_receipts_survive_cancellation_and_permanent_removal(self):
  entry=self.entry();command=self.command(entry,status='Cancelled')
  self.assertEqual(self.api.call('/api/leave-decision','POST',command)[0],200)
  count=len(self.mails());code,data,_=self.submit();self.assertEqual(code,200,data);self.assertEqual(data['request']['status'],'Cancelled');self.assertEqual(len(self.mails()),count)
  self.store.state['leaveRequests'].pop(entry['id']);code,data,_=self.submit();self.assertEqual(code,409,data);self.assertIn('later removed',data['error']);self.assertEqual(self.store.state['leaveRequests'],{})
 def test_replayed_approval_returns_current_cancellation(self):
  entry=self.entry();command=self.command(entry);code,data,_=self.api.call('/api/leave-decision','POST',command);self.assertEqual(code,200,data)
  self.assertEqual(self.api.call('/api/leave-decision','POST',self.command(data['request'],status='Cancelled'))[0],200)
  saved=copy.deepcopy(self.store.state);code,data,_=self.api.call('/api/leave-decision','POST',command);self.assertEqual(code,200,data);self.assertEqual(data['request']['status'],'Cancelled');self.assertEqual(self.store.state,saved)
 def test_authority_is_rechecked_after_competing_privilege_change(self):
  original=self.store.commit;first=True
  def revoked(revision,state):
   nonlocal first
   if first:
    first=False;rev,current=self.store.read();current['users']['tech@example.nz']['active']=False;original(rev,current)
   return original(revision,state)
  with patch.object(self.store,'commit',side_effect=revoked):code,data,_=self.submit()
  self.assertEqual(code,403,data);self.assertEqual(self.store.state['leaveRequests'],{});self.assertFalse(self.mails());self.assertFalse(self.store.state.get('leaveOperations'))
 def test_admin_demotion_during_decision_never_saves_stale_authority(self):
  entry=self.entry();original=self.store.commit;first=True
  def demoted(revision,state):
   nonlocal first
   if first:
    first=False;rev,current=self.store.read();current['users'][accounts.FIRST_ADMIN]['role']='tech';original(rev,current)
   return original(revision,state)
  with patch.object(self.store,'commit',side_effect=demoted):code,data,_=self.api.call('/api/leave-decision','POST',self.command(entry))
  self.assertEqual(code,403,data);self.assertEqual(self.store.state['leaveRequests'][entry['id']]['status'],'Pending');self.assertEqual(len(self.mails()),2)
 def test_revoked_email_session_is_rechecked_during_retry(self):
  token='trident_synthetic_session';self.store.state['sessions']={accounts.digest(token):{'email':'tech@example.nz','expires':time.time()+100}}
  original=self.store.commit;first=True
  def revoked(revision,state):
   nonlocal first
   if first:
    first=False;rev,current=self.store.read();current['sessions']={};original(rev,current)
   return original(revision,state)
  with patch.object(self.store,'commit',side_effect=revoked):code,data,_=self.api.call('/api/leave','POST',self.request,token=token,match=False)
  self.assertEqual(code,401,data);self.assertFalse(self.store.state['leaveRequests'])
 def test_contention_has_a_bound_and_keeps_the_same_key_for_later_retry(self):
  with patch.object(self.store,'commit',return_value=False) as commit:code,data,_=self.submit()
  self.assertEqual(code,503,data);self.assertEqual(commit.call_count,7);self.assertFalse(self.store.state['leaveRequests'])
  self.assertEqual(self.submit()[0],200);self.assertEqual(self.submit()[0],200);self.assertEqual(len(self.store.state['leaveRequests']),1)
 def test_validation_and_owner_checks_still_apply_with_stale_etags(self):
  for changes,expected in [({'hoursPerDay':25},400),({'startTime':'08:07'},400),({'technician':'Another technician'},403),({'operationId':'bad'},400)]:
   with self.subTest(changes=changes):self.assertEqual(self.submit(**changes)[0],expected)
  self.assertFalse(self.store.state['leaveRequests']);self.assertFalse(self.mails())
 def run_together(self,functions):
  original=self.store.commit;barrier=threading.Barrier(len(functions));seen=threading.local()
  def concurrent_commit(revision,state):
   if not getattr(seen,'waited',False):seen.waited=True;barrier.wait(timeout=10)
   return original(revision,state)
  with patch.object(self.store,'commit',side_effect=concurrent_commit),concurrent.futures.ThreadPoolExecutor(max_workers=len(functions)) as pool:return list(pool.map(lambda fn:fn(),functions))
 def test_three_simultaneous_creates_and_retries_preserve_every_request(self):
  payloads=[{**self.request,'startDate':date,'endDate':date,'operationId':uuid.uuid4().hex} for date in ('2027-02-01','2027-02-02','2027-02-03')]
  results=self.run_together([lambda p=p:self.api.call('/api/leave','POST',p,token='tech',match=False) for p in payloads])
  self.assertEqual([r[0] for r in results],[200]*3,results);self.assertEqual(len(self.store.state['leaveRequests']),3);self.assertEqual(len(self.mails()),6)
  for payload,result in zip(payloads,results):self.assertEqual(self.api.call('/api/leave','POST',payload,token='tech',match=False)[1]['request']['id'],result[1]['request']['id'])
  self.assertEqual(len(self.mails()),6)
 def test_three_identical_concurrent_replays_create_one_leave(self):
  results=self.run_together([lambda:self.submit() for _ in range(3)])
  self.assertEqual([r[0] for r in results],[200]*3,results);self.assertEqual(len({r[1]['request']['id'] for r in results}),1);self.assertEqual(len(self.store.state['leaveRequests']),1);self.assertEqual(len(self.mails()),2)
 def test_competing_overlapping_requests_keep_business_validation(self):
  results=self.run_together([lambda:self.submit(operationId=uuid.uuid4().hex) for _ in range(2)])
  self.assertEqual(sorted(r[0] for r in results),[200,409],results);self.assertEqual(len(self.store.state['leaveRequests']),1);self.assertEqual(len(self.mails()),2)
 def test_competing_decisions_conflict_on_the_leave_revision(self):
  entry=self.entry();commands=[self.command(entry),self.command(entry,status='Declined',decisionNotes='Synthetic competing decision')]
  results=self.run_together([lambda p=p:self.api.call('/api/leave-decision','POST',p,match=False) for p in commands])
  self.assertEqual(sorted(r[0] for r in results),[200,409],results);self.assertEqual(self.store.state['leaveRequests'][entry['id']]['revision'],2);self.assertEqual(len(self.mails()),3)

if __name__=='__main__':unittest.main()
