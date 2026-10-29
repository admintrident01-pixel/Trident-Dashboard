import copy,unittest
from unittest.mock import patch
import schedule,schedule_search,schedule_routes,timesheets,timesheet_drafts,test_accounts
from core import Problem

class ScheduleRefinements(unittest.TestCase):
 def test_search_covers_dates_addresses_and_notes_without_routing(self):
  state={'appointments':{str(i):{'id':str(i),'date':'2026-10-'+str(20+i),'start':'09:00','duration':60,'client':'A client','address':'Walton Street','notes':'Wheelchair assessment','type':'Repair','technician':'Alex','cancelled':i==2} for i in (1,2,3)}}
  before=copy.deepcopy(state)
  with patch.object(schedule_routes,'estimate',side_effect=AssertionError('No route calls')):
   result=schedule_search.search(state,{'q':['walton assessment']})
  self.assertEqual([r['id'] for r in result['results']],['3','1']);self.assertEqual(state,before)
  self.assertEqual(schedule_search.search(state,{'q':['walton'],'cancelled':['1']})['total'],3)
 def test_shared_widths_validate_and_are_returned_on_any_date(self):
  state={'staffSettings':{'technicians':[{'name':'Alex','rego':''},{'name':'Office','rego':'','staffType':'office'}]}}
  cfg=schedule.settings(state);state=schedule.save_settings(state,{**cfg,'columnWidths':{'Alex':125,'Office':50}})
  for date in ('2026-10-29','2026-11-02'):self.assertEqual(schedule.read(state,date,fast=True)['columnWidths'],{'Alex':125,'Office':50})
  cfg=schedule.settings(state);cfg.pop('columnWidths');self.assertEqual(schedule.save_settings(state,cfg)['scheduleSettings']['columnWidths'],{'Alex':125,'Office':50})
  for value in (0,49,201,True,'100'):
   with self.assertRaises(Problem):schedule.save_settings(state,{**cfg,'columnWidths':{'Alex':value}})

class TimesheetPeriodTests(unittest.TestCase):
 def setUp(self):
  self.user={'email':'admin@example.nz','role':'admin'};self.state={}
  self.data={'technician':'Alex','weekStart':'2026-10-26','signature':'Alex','notes':'keep','days':[{'status':'Work','method':'direct','hours':8 if i<5 else 0,'notes':'','unpaidLunch':False} for i in range(7)]}
 def test_submission_and_draft_cannot_duplicate_each_other(self):
  state,saved=timesheets.save(self.state,self.data,user=self.user);before=copy.deepcopy(state)
  for save in (lambda:timesheets.save(state,self.data,user=self.user),lambda:timesheet_drafts.save(state,self.data,self.user)):
   with self.assertRaises(Problem) as error:save()
   self.assertEqual(error.exception.status,409);self.assertFalse(error.exception.details['existingTimesheets'][0]['isDraft'])
  self.assertEqual(state,before)
 def test_draft_owner_does_not_allow_a_second_person_week_record(self):
  state,draft=timesheet_drafts.save(self.state,self.data,self.user)
  other={'email':'another@example.nz','role':'admin'}
  with self.assertRaises(Problem):timesheet_drafts.save(state,self.data,other)
  with self.assertRaises(Problem):timesheet_drafts.submit(state,self.data,other)
  state,saved=timesheet_drafts.submit(state,{**self.data,'draftId':draft['id'],'draftRevision':draft['revision']},self.user)
  self.assertEqual(state['timesheetDrafts'],{});self.assertEqual(len(state['timesheets']),1)
 def test_existing_draft_updates_and_different_people_and_weeks_are_allowed(self):
  state,draft=timesheet_drafts.save(self.state,self.data,self.user)
  state,updated=timesheet_drafts.save(state,{**self.data,'draftId':draft['id'],'draftRevision':1,'notes':'updated'},self.user)
  self.assertEqual(updated['id'],draft['id']);self.assertEqual(updated['revision'],2)
  state,_=timesheet_drafts.save(state,{**self.data,'technician':'Other'},self.user)
  state,_=timesheet_drafts.save(state,{**self.data,'weekStart':'2026-11-02'},self.user)
  self.assertEqual(len(state['timesheetDrafts']),3)
 def test_corrections_keep_identity_and_cannot_move_into_an_occupied_week(self):
  state,first=timesheets.save(self.state,self.data,user=self.user)
  corrected,entry=timesheets.edit_submission(state,{**self.data,'id':first['id'],'revision':1,'editReason':'Correction'},self.user['email'])
  self.assertEqual(entry['id'],first['id']);self.assertEqual(len(corrected['timesheets']),1)
  state,_=timesheets.save(state,{**self.data,'weekStart':'2026-11-02'},user=self.user)
  with self.assertRaises(Problem):timesheets.edit_submission(state,{**self.data,'weekStart':'2026-11-02','id':first['id'],'revision':1,'editReason':'Move','replaceWeekConfirmed':True},self.user['email'])
 def test_api_returns_open_existing_action_even_for_a_stale_second_submission(self):
  api=test_accounts.AccountsAPI();api.setUp()
  self.assertEqual(api.call('/api/timesheets','POST',self.data)[0],200)
  status,data,_=api.call('/api/timesheets','POST',self.data,match=False)
  self.assertEqual(status,409);self.assertTrue(data['existingTimesheets'][0]['canOpen']);self.assertEqual(len(api.store.state['timesheets']),1)
 def test_tech_cannot_open_another_owners_draft_or_probe_another_person(self):
  api=test_accounts.AccountsAPI();api.setUp();data={**self.data,'technician':'Scott Yearbury'}
  self.assertEqual(api.call('/api/timesheet-drafts','POST',data)[0],200)
  status,result,_=api.call('/api/timesheets','POST',data,token='tech')
  self.assertEqual(status,409);self.assertFalse(result['existingTimesheets'][0]['canOpen'])
  self.assertEqual(api.call('/api/timesheets','POST',{**data,'technician':'Alex'},token='tech',match=False)[0],403)

if __name__=='__main__':unittest.main()
