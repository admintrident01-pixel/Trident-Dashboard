import json,os,unittest
from unittest.mock import patch
import schedule_live,test_accounts

class ScheduleLiveTests(unittest.TestCase):
 def test_ticket_disabled_until_both_ends_are_configured(self):
  with patch.dict(os.environ,{'SCHEDULE_LIVE_SECRET':'','FRONTEND_ORIGIN':'https://example.test'}):self.assertEqual(schedule_live.ticket(),{'enabled':False})
 def test_ticket_has_no_business_or_account_details(self):
  with patch.dict(os.environ,{'SCHEDULE_LIVE_SECRET':'x'*32,'FRONTEND_ORIGIN':'https://example.test'}):
   value=schedule_live.ticket();self.assertTrue(value['enabled']);self.assertNotIn('@',json.dumps(value));self.assertEqual(len(value['ticket'].split('.')[1]),64)
 def test_ticket_endpoint_requires_existing_active_session(self):
  api=test_accounts.AccountsAPI();api.setUp()
  self.assertEqual(api.call('/api/schedule/live-ticket',token='')[0],401)
  self.assertEqual(api.call('/api/schedule/live-ticket',token='tech')[0],200)
 def test_technicians_can_read_but_cannot_mutate_schedule(self):
  api=test_accounts.AccountsAPI();api.setUp()
  self.assertEqual(api.call('/api/schedule',token='tech')[0],400) # Missing date, not a permission rejection.
  for path in ['/api/schedule','/api/schedule/travel','/api/schedule-notes','/api/schedule-settings']:
   self.assertEqual(api.call(path,'POST',{'action':'delete_selection','ids':['anything']},token='tech')[0],403,path)
 def test_committed_schedule_changes_notify_but_stock_and_rejected_writes_do_not(self):
  api=test_accounts.AccountsAPI();api.setUp()
  with patch.object(schedule_live,'configuration',return_value=('x'*32,'https://example.test')),patch.object(schedule_live,'notify') as notify:
   revision,state=api.store.read();state['stock']={'keep':1};api.app.commit(revision,state);notify.assert_not_called()
   revision,state=api.store.read();state['appointments']={'new':{'id':'new'}};api.app.commit(revision,state);notify.assert_called_once()
   with self.assertRaises(Exception):api.app.commit(revision,state)
   notify.assert_called_once()
 def test_notification_failure_does_not_fail_a_committed_write(self):
  with patch.dict(os.environ,{'SCHEDULE_LIVE_SECRET':'x'*32,'FRONTEND_ORIGIN':'https://example.test'}),patch.object(schedule_live,'urlopen',side_effect=TimeoutError):schedule_live.notify()

if __name__=='__main__':unittest.main()
