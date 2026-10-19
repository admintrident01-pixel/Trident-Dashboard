import base64,copy,datetime as dt,io,os,unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo
import openpyxl
import weekly_export,weekly_report,timesheets,reminders,test_accounts

class ExcelExport(unittest.TestCase):
 def setUp(self):
  self.week='2027-02-01'
  self.state={'staffSettings':{'technicians':[{'name':'Scott Yearbury','rego':''}]},'quotes':{'keep':{'value':1}}}
  self.state,self.sheet=timesheets.save(self.state,{'technician':'Scott Yearbury','weekStart':self.week,'signature':'Scott','days':[{'status':'Work','method':'times','start':'08:00','finish':'17:00','unpaidLunch':True,'notes':'=HYPERLINK("https://example.nz")'}]+[{'status':'Work','method':'direct','hours':0} for _ in range(6)]})
  self.state=weekly_report.save_charged(self.state,{'week':self.week,'charged':[{'technician':'Scott Yearbury','date':self.week,'hours':0}]})
 def book(self,data):return openpyxl.load_workbook(io.BytesIO(base64.b64decode(data['file'])))
 def test_weekly_numbers_blanks_notes_and_no_mutation(self):
  before=copy.deepcopy(self.state);book=self.book(weekly_export.weekly(self.state,{'week':self.week}))
  self.assertEqual(book.sheetnames,['Weekly hours','Daily detail','13-week averages','Report details'])
  self.assertEqual(book['Weekly hours']['C2'].value,8.5);self.assertEqual(book['Weekly hours']['C3'].value,0);self.assertIsNone(book['Weekly hours']['D3'].value)
  self.assertEqual(book['Daily detail']['J2'].data_type,'s');self.assertTrue(book['Daily detail']['J2'].value.startswith('='))
  self.assertEqual(book['Weekly hours'].freeze_panes,'B2');self.assertEqual(book['Weekly hours'].page_setup.orientation,'landscape')
  self.assertEqual(self.state,before)
 def test_selected_period_and_corrected_week(self):
  change={**self.sheet,'weekStart':'2027-02-08','revision':1,'editReason':'Wrong week','days':[{'status':'Work','method':'direct','hours':9}]+[{'status':'Work','method':'direct','hours':0} for _ in range(6)]}
  state,_=timesheets.edit_submission(self.state,change,'admin@example.nz')
  b=self.book(weekly_export.period(state,{'start':self.week,'end':'2027-02-08'}));self.assertEqual(b.active['B2'].value,9);self.assertEqual(b.active['D2'].value,4.5)
 def test_api_admin_only_read_only(self):
  api=test_accounts.AccountsAPI();api.setUp();api.store.state.update(self.state)
  before=copy.deepcopy(api.store.state);revision=api.store.revision
  for path,payload in [('/api/weekly-report-excel',{'week':self.week}),('/api/report-periods-excel',{'start':self.week,'end':self.week})]:
   self.assertEqual(api.call(path,'POST',payload,token='tech')[0],403)
   status,data,_=api.call(path,'POST',payload);self.assertEqual(status,200);self.assertTrue(data['filename'].endswith('.xlsx'));self.book(data)
  self.assertEqual(api.store.state,before);self.assertEqual(api.store.revision,revision)

class ReminderFix(unittest.TestCase):
 def test_friday_three_exact_boundary_and_dedupe(self):
  rules=test_accounts.ReminderRules();rules.setUp();state=rules.state
  state['reminderSettings']={**reminders.DEFAULTS,'automaticTimesheets':True,'timesheetWeekday':5,'timesheetTime':'15:00','timesheetLeadHours':24}
  state['timesheets']={'old':{'technician':'Scott','weekStart':'2026-10-05'}}
  friday=dt.datetime(2026,10,16,15,tzinfo=ZoneInfo('Pacific/Auckland'))
  self.assertEqual(reminders.due_reminders(state,friday-dt.timedelta(seconds=1))[1],0)
  result,count=reminders.due_reminders(state,friday);self.assertEqual(count,1)
  self.assertEqual(reminders.due_reminders(result,friday)[1],0)
  state['timesheets']['new']={'technician':'Scott','weekStart':'2026-10-12'};self.assertEqual(reminders.due_reminders(state,friday)[1],0)
 def test_scheduler_status_does_not_claim_connection(self):
  with patch.dict(os.environ,{},clear=True):self.assertEqual(reminders.scheduler_status({})['status'],'not-connected')
  now=dt.datetime.now(dt.timezone.utc)
  with patch.dict(os.environ,{'REMINDER_JOB_TOKEN':'private'}):
   self.assertEqual(reminders.scheduler_status({})['status'],'not-running')
   self.assertEqual(reminders.scheduler_status({'reminderJob':{'finishedAt':now.isoformat()}},now=now)['status'],'running')
   self.assertEqual(reminders.scheduler_status({'reminderJob':{'finishedAt':(now-dt.timedelta(hours=1)).isoformat()}},now=now)['status'],'stale')
 def test_record_run_preserves_business_records(self):
  store=test_accounts.MemoryStore({'quotes':{'a':1},'stock':{'b':2}});reminders.record_run(store,3,3)
  self.assertEqual(store.state['quotes'],{'a':1});self.assertEqual(store.state['stock'],{'b':2});self.assertEqual(store.state['reminderJob']['queued'],3)
 def test_scheduler_connection_check_sends_nothing(self):
  api=test_accounts.AccountsAPI();api.setUp();before=copy.deepcopy(api.store.state);revision=api.store.revision
  with patch.dict(os.environ,{'REMINDER_JOB_TOKEN':'private-job-secret'}):
   self.assertEqual(api.call('/api/reminders/check','POST',token='admin')[0],401)
   status,data,_=api.call('/api/reminders/check','POST',token='private-job-secret')
   self.assertEqual(status,200);self.assertTrue(data['checked'])
  self.assertEqual(api.store.state,before);self.assertEqual(api.store.revision,revision)

if __name__=='__main__':unittest.main()
