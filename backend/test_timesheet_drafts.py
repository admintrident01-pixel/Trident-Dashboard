import copy, unittest
import timesheet_drafts, test_accounts, weekly_report
from core import Problem
class TimesheetDraftTests(unittest.TestCase):
 def setUp(self):
  self.api=test_accounts.AccountsAPI();self.api.setUp()
  self.payload={'technician':'Scott Yearbury','weekStart':'2026-10-12','signature':'','notes':'unfinished notes','days':[{'status':'Work','method':'direct','hours':'8.5','start':'07:30','finish':'16:00','unpaidLunch':True,'notes':''} for _ in range(7)]}
 def save(self,payload=None,token='tech'):
  return self.api.call('/api/timesheet-drafts','POST',payload or self.payload,token=token)
 def test_partial_draft_persists_without_submission_and_is_private(self):
  self.payload['days'][0].update(hours='',status='Other',other='')
  report_before=weekly_report.read(self.api.store.state,'2026-10-12')
  status,data,_=self.save();self.assertEqual(status,200);draft=data['draft']
  self.assertEqual(draft['days'][0]['hours'],'');self.assertEqual(draft['signature'],'')
  self.assertEqual(self.api.store.state['timesheets'],{})
  self.assertEqual(weekly_report.read(self.api.store.state,'2026-10-12'),report_before)
  self.assertEqual(self.api.call('/api/timesheets',token='tech')[1]['drafts'][0]['id'],draft['id'])
  self.api.store.state['users']['tech@example.nz']['technician']='Andrew'
  self.assertEqual(self.api.call('/api/timesheets',token='tech')[1]['drafts'],[])
  self.assertEqual(self.save()[0],403)
 def test_resume_update_conflicts_and_submit_replaces_draft(self):
  draft=self.save()[1]['draft'];p={**self.payload,'draftId':draft['id'],'draftRevision':1}
  p['days']=copy.deepcopy(p['days']);p['days'][0]['notes']='continued'
  saved=self.save(p)[1]['draft'];self.assertEqual(saved['revision'],2);self.assertEqual(saved['days'][0]['notes'],'continued')
  self.assertEqual(self.save(p)[0],409)
  p['draftRevision']=2
  self.assertEqual(self.api.call('/api/timesheets','POST',p,token='tech')[0],400)
  self.assertIn(draft['id'],self.api.store.state['timesheetDrafts'])
  p['signature']='Scott';status,data,_=self.api.call('/api/timesheets','POST',p,token='tech');self.assertEqual(status,200)
  self.assertEqual(data['total'],56);self.assertEqual(self.api.store.state['timesheetDrafts'],{})
  self.assertEqual(len(self.api.call('/api/timesheets',token='tech')[1]['timesheets']),1)
 def test_history_filters_other_staff_and_duplicate_drafts(self):
  self.save();self.assertEqual(self.save()[0],409)
  other={**self.payload,'technician':'Andrew','signature':'Andrew'}
  self.assertEqual(self.api.call('/api/timesheets','POST',other)[0],200)
  self.assertEqual(self.api.call('/api/timesheets',token='tech')[1]['timesheets'],[])
  self.assertEqual(len(self.api.call('/api/timesheets')[1]['timesheets']),1)
 def test_permissions_validation_and_conflicting_draft_submission(self):
  self.assertEqual(self.api.call('/api/timesheet-drafts','POST',self.payload,token='')[0],401)
  self.assertEqual(self.api.call('/api/timesheet-drafts','POST',self.payload,token='tech',match=False)[0],409)
  bad={**self.payload,'weekStart':'2026-10-13'};self.assertEqual(self.save(bad)[0],400)
  draft=self.save()[1]['draft']
  bad={**self.payload,'draftId':draft['id'],'draftRevision':1,'weekStart':'2026-10-19'};self.assertEqual(self.save(bad)[0],400)
  p={**self.payload,'draftId':draft['id'],'draftRevision':0,'signature':'Scott'}
  self.assertEqual(self.api.call('/api/timesheets','POST',p,token='tech')[0],409)
