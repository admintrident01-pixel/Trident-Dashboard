import copy, unittest
import timesheets, weekly_report, leave, test_accounts
from core import Problem
class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.payload={'technician':'Scott Yearbury','signature':'Scott','weekStart':'2027-02-01','days':[{'status':'Work','method':'direct','hours':8,'unpaidLunch':True,'notes':'Original'}]+[{'status':'Work','method':'direct','hours':0} for _ in range(6)]}
        self.state,self.row=timesheets.save({},self.payload)
        self.change={**self.payload,'id':self.row['id'],'revision':1,'editReason':'Correct missed hours','days':copy.deepcopy(self.payload['days'])}
        self.change['days'][0]['hours']=9
        self.change['days'][0]['notes']='Corrected note'
    def test_identity_signature_and_audit_preserved(self):
        state,row=timesheets.edit_submission(self.state,{**self.change,'signature':'Spoofed'},'admin@example.nz')
        self.assertEqual(row['id'],self.row['id']);self.assertEqual(row['signature'],'Scott');self.assertEqual(row['submittedAt'],self.row['submittedAt'])
        self.assertEqual(row['revision'],2);self.assertEqual(row['total'],8.5);self.assertEqual(len(state['timesheets']),1)
        self.assertEqual(row['editHistory'][0]['previous']['total'],7.5);self.assertEqual(row['updatedBy'],'admin@example.nz')
        self.assertEqual(self.state['timesheets'][row['id']]['total'],7.5)
        report=next(r for r in weekly_report.read(state,'2027-02-01')['rows'] if r['name']=='Scott Yearbury')
        self.assertEqual(report['days'][0]['work'],8.5);self.assertEqual(report['days'][0]['note'],'Corrected note')
    def test_reason_week_and_revision_required(self):
        for data in [{**self.change,'editReason':''},{**self.change,'revision':0},{**self.change,'weekStart':'2027-02-09'},{**self.change,'technician':'Someone else'}]:
            with self.assertRaises(Problem):timesheets.edit_submission(self.state,data,'admin@example.nz')
    def test_approved_leave_and_no_double_count(self):
        state,request=leave.create(self.state,{'technician':'Scott Yearbury','leaveType':'Annual leave','startDate':'2027-02-01','endDate':'2027-02-01','hoursPerDay':4,'reason':'Holiday'})
        state,_=leave.decide(state,{'id':request['id'],'revision':request['revision'],'status':'Approved'},'admin@example.nz')
        with self.assertRaises(Problem):timesheets.edit_submission(state,self.change,'admin@example.nz')
        change=copy.deepcopy(self.change);change['days'][0].update(status='Annual leave',hours=4,unpaidLunch=False)
        state,row=timesheets.edit_submission(state,change,'admin@example.nz')
        report=next(r for r in weekly_report.read(state,'2027-02-01')['rows'] if r['name']=='Scott Yearbury')
        self.assertEqual(row['total'],4);self.assertEqual(report['days'][0]['annual'],4);self.assertEqual(report['days'][0]['work'],0)
    def test_api_admin_only_and_conflicts(self):
        api=test_accounts.AccountsAPI();api.setUp();api.store.state.update(copy.deepcopy(self.state))
        self.assertEqual(api.call('/api/timesheets',token='tech')[0],200)
        self.assertTrue(all(r['technician']=='Scott Yearbury' for r in api.call('/api/timesheets',token='tech')[1]['timesheets']))
        self.assertEqual(api.call('/api/timesheet-edit','POST',self.change,token='tech')[0],403)
        self.assertEqual(api.call('/api/timesheet-edit','POST',self.change,match=False)[0],409)
        status,payload,_=api.call('/api/timesheet-edit','POST',self.change)
        self.assertEqual(status,200);self.assertEqual(payload['timesheet']['total'],8.5)
        self.assertEqual(api.call('/api/timesheet-edit','POST',self.change)[0],409)

    def test_editing_earlier_submission_becomes_current_report(self):
        # Seed historical duplicates to verify their reporting and correction support.
        state,later=timesheets.save(self.state,self.payload,check_period=False)
        later['submittedAt']='2027-02-02T00:00:00+00:00'
        state['timesheets'][self.row['id']]['submittedAt']='2027-02-01T00:00:00+00:00'
        state,row=timesheets.edit_submission(state,self.change,'admin@example.nz')
        row['updatedAt']='2027-02-03T00:00:00+00:00'
        report=next(r for r in weekly_report.read(state,'2027-02-01')['rows'] if r['name']=='Scott Yearbury')
        self.assertEqual(report['days'][0]['work'],8.5)
        self.assertEqual(row['submittedAt'],'2027-02-01T00:00:00+00:00')
        self.assertEqual(len(state['timesheets']),2)

    def test_move_week_and_times_updates_reports_with_audit(self):
        change=copy.deepcopy(self.change);change['weekStart']='2027-02-08';change['days'][0].update(method='times',start='08:00',finish='17:00',unpaidLunch=True)
        state,row=timesheets.edit_submission(self.state,change,'another-admin@example.nz')
        self.assertEqual(row['total'],8.5);self.assertEqual(row['weekStart'],'2027-02-08')
        self.assertEqual(row['editHistory'][0]['previous']['weekStart'],'2027-02-01')
        for week,expected in [('2027-02-01',0),('2027-02-08',8.5)]:
            report=next(r for r in weekly_report.week_rows(state,week) if r['name']=='Scott Yearbury')
            self.assertEqual(report['days'][0]['work'],expected)
        self.assertEqual(self.state['timesheets'][row['id']]['weekStart'],'2027-02-01')
    def test_destination_collision_cannot_create_a_second_submission(self):
        state,existing=timesheets.save(self.state,{**self.payload,'weekStart':'2027-02-08'})
        change={**self.change,'weekStart':'2027-02-08'}
        with self.assertRaises(Problem):timesheets.edit_submission(state,change,'admin@example.nz')
        with self.assertRaises(Problem):timesheets.edit_submission(state,{**change,'replaceWeekConfirmed':True},'admin@example.nz')
        self.assertEqual(state['timesheets'][existing['id']],existing)
