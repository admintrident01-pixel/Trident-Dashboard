import copy,datetime as dt,unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo
import reminders,test_accounts,stocktake_sessions
from core import Problem

class ReminderRecipients(unittest.TestCase):
 def setUp(self):
  self.state={'users':{}}
  for email,name,role,tech,active,verified in [('admin@example.nz','Admin','admin','Admin',True,True),('staff@example.nz','Staff','tech','Staff',True,True),('pending@example.nz','Pending','tech','Pending',True,False),('inactive@example.nz','Inactive','tech','Inactive',False,True)]:
   self.state['users'][email]=dict(email=email,name=name,role=role,technician=tech,active=active,verified=verified)
  self.state['reminderSettings']={**reminders.DEFAULTS,'automaticTimesheets':True,'automaticVehicles':True}
  self.state['stockTakeSettings']={'intervalDays':90,'automatic':True,'futureSetting':'keep'}
  self.state['stock']={'products':{'preserve':{'code':'123'}}};self.state['quotes']={'preserve':1}
  self.now=dt.datetime(2026,10,20,15,tzinfo=ZoneInfo('Pacific/Auckland'))
  self.rows=[{'id':kind+email,'kind':kind,'recipient':email,'name':email,'due':'2026-10-01T15:00:00+13:00' if kind=='timesheet' else '2026-10-01','daysRemaining':-19,'weekStart':'2026-09-28','lastCompleted':'','registration':'TEST'} for kind in ('timesheet','vehicle','stocktake') for email in ('admin@example.nz','staff@example.nz') if kind!='stocktake' or email.startswith('admin')]
 def count(self,state):
  with patch.object(reminders,'dashboard',return_value=self.rows):return reminders.due_reminders(state,self.now)
 def test_legacy_rules_unchanged_and_no_mutation(self):
  before=copy.deepcopy(self.state);result,count=self.count(self.state)
  self.assertEqual(count,5);self.assertEqual(self.state,before);self.assertEqual(self.count(result)[1],0)
 def test_independent_selection_and_empty_means_nobody(self):
  data={**reminders.settings_view(self.state),'timesheetRecipients':['staff@example.nz'],'vehicleRecipients':[],'stocktakeRecipients':['admin@example.nz']}
  state=reminders.save_settings(self.state,data);result,count=self.count(state)
  self.assertEqual(count,2);self.assertEqual({(m['kind'],m['to']) for m in result['mailOutbox'].values()},{('timesheet','staff@example.nz'),('stocktake','admin@example.nz')})
  self.assertEqual(state['quotes'],self.state['quotes']);self.assertEqual(state['stock'],self.state['stock'])
 def test_older_client_preserves_new_settings(self):
  self.state['reminderSettings']['timesheetRecipients']=[]
  data={k:v for k,v in reminders.DEFAULTS.items() if not k.endswith('Recipients')}
  state=reminders.save_settings(self.state,data)
  self.assertEqual(state['reminderSettings']['timesheetRecipients'],[]);self.assertEqual(state['stockTakeSettings'],self.state['stockTakeSettings'])
 def test_recipient_validation_and_no_partial_changes(self):
  for field,value in [('timesheetRecipients','bad'),('vehicleRecipients',[123]),('timesheetRecipients',['unknown@example.nz']),('stocktakeRecipients',['staff@example.nz']),('stocktakeIntervalDays',0),('stocktakeIntervalDays',True),('automaticStocktakes','yes')]:
   with self.subTest(field=field,value=value):
    before=copy.deepcopy(self.state)
    with self.assertRaises(Problem):reminders.save_settings(self.state,{**reminders.settings_view(self.state),field:value})
    self.assertEqual(before,self.state)
 def test_shared_stocktake_interval_and_status(self):
  data={**reminders.settings_view(self.state),'stocktakeIntervalDays':45,'automaticStocktakes':False}
  state=reminders.save_settings(self.state,data)
  self.assertEqual(stocktake_sessions.config(state)['intervalDays'],45);self.assertFalse(stocktake_sessions.config(state)['automatic']);self.assertEqual(state['stockTakeSettings']['futureSetting'],'keep')
  state['stockTakeSettings']['intervalDays']=30
  self.assertEqual(reminders.settings_view(state)['stocktakeIntervalDays'],30)
 def test_unverified_accounts_never_receive_selected_reminders(self):
  self.state['reminderSettings']['timesheetRecipients']=['pending@example.nz']
  rows=[{**self.rows[0],'recipient':'pending@example.nz','kind':'timesheet'}]
  with patch.object(reminders,'dashboard',return_value=rows):self.assertEqual(reminders.due_reminders(self.state,self.now)[1],0)
 def test_api_permissions_roundtrip_and_etag(self):
  api=test_accounts.AccountsAPI();api.setUp()
  status,view,headers=api.call('/api/reminder-settings');self.assertEqual(status,200)
  self.assertIn('recipientOptions',view);self.assertIn('stocktakeIntervalDays',view)
  view.update(timesheetRecipients=['tech@example.nz'],vehicleRecipients=[],stocktakeRecipients=[],stocktakeIntervalDays=45,automaticStocktakes=False)
  self.assertEqual(api.call('/api/reminder-settings','POST',view,token='tech')[0],403)
  self.assertEqual(api.call('/api/reminder-settings','POST',view,match=False)[0],409)
  self.assertEqual(api.call('/api/reminder-settings','POST',view)[0],200)
  saved=api.call('/api/reminder-settings')[1]
  for key in ('timesheetRecipients','vehicleRecipients','stocktakeRecipients','stocktakeIntervalDays','automaticStocktakes'):self.assertEqual(saved[key],view[key])

if __name__=='__main__':unittest.main()
