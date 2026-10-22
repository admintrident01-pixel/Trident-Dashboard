import copy,io,json,unittest
from unittest.mock import patch
import accounts,schedule_history,schedule_routes,test_accounts

class ScheduleETagTests(unittest.TestCase):
 def setUp(self):
  self.api=test_accounts.AccountsAPI();self.api.setUp()
  self.date='2027-02-01'
  self.booking={'date':self.date,'technician':'Scott Yearbury','client':'Sample','address':'1 Sample Road','start':'09:00','duration':30,'type':'Repair','timing':'flexible','notes':''}
  self.config=patch.object(schedule_routes,'configuration',return_value={'key':'','depot':'Depot'});self.config.start();self.addCleanup(self.config.stop)
 def call(self,method='GET',body=None,tag='',conditional=''):
  raw=json.dumps(body).encode() if body is not None else b''
  env={'REQUEST_METHOD':method,'PATH_INFO':'/api/schedule','QUERY_STRING':'date='+self.date,'HTTP_ORIGIN':'http://127.0.0.1:18780','HTTP_AUTHORIZATION':'Bearer admin','HTTP_IF_MATCH':tag,'HTTP_IF_NONE_MATCH':conditional,'CONTENT_LENGTH':str(len(raw)),'REMOTE_ADDR':'127.0.0.1','wsgi.input':io.BytesIO(raw)}
  meta=[];raw=b''.join(self.api.app(env,lambda s,h:meta.append((int(s[:3]),dict(h)))))
  return meta[0][0],json.loads(raw),meta[0][1]
 def unrelated_save(self):
  rev,state=self.api.store.read();state['stock']={'preserve':'new stock'};state['reminderJob']={'finishedAt':'new'};self.assertTrue(self.api.store.commit(rev,state))
 def test_background_saves_do_not_block_booking_and_are_preserved(self):
  _,_,headers=self.call();tag=headers['ETag'];self.assertTrue(tag.startswith('"schedule-'))
  self.unrelated_save();status,data,h=self.call('POST',self.booking,tag)
  self.assertEqual(status,200,data);self.assertEqual(self.api.store.state['stock'],{'preserve':'new stock'});self.assertEqual(self.api.store.state['reminderJob'],{'finishedAt':'new'});self.assertTrue(h['ETag'].startswith('"schedule-'))
 def test_actual_schedule_change_still_blocks_stale_edit(self):
  _,_,h=self.call();tag=h['ETag'];self.assertEqual(self.call('POST',self.booking,tag)[0],200)
  saved=copy.deepcopy(self.api.store.state);status,data,_=self.call('POST',{**self.booking,'start':'11:00'},tag)
  self.assertEqual(status,409,data);self.assertEqual(self.api.store.state,saved)
 def test_settings_leave_and_versions_invalidate_token(self):
  base={'appointments':{'a':{'version':1}},'stock':{'value':1}}
  for key,value in [('scheduleSettings',{'lunchStart':'13:00'}),('leaveRequests',{'a':{'status':'Approved'}}),('scheduleNoteSeries',{'n':{'title':'Meeting'}}),('appointments',{'a':{'version':2}}),('staffSettings',{'technicians':[]})]:
   self.assertNotEqual(schedule_history.etag(base),schedule_history.etag({**base,key:value}),key)
 def test_conditional_read_ignores_unrelated_saves(self):
  _,_,h=self.call();self.unrelated_save();status,data,_=self.call(conditional=h['ETag']);self.assertEqual(status,200);self.assertEqual(data,{'unchanged':True})
 def test_existing_global_revision_clients_remain_supported(self):
  self.assertEqual(self.call('POST',self.booking,'"1"')[0],200)
 def test_missing_token_does_not_bypass_conflict_protection(self):
  self.assertEqual(self.call('POST',self.booking)[0],409)

if __name__=='__main__':unittest.main()
